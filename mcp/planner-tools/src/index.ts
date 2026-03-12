import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { execSync } from "child_process";
import * as path from "path";

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || process.cwd();

const server = new Server(
  { name: "planner-tools", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "inspect_project_structure",
      description: "Get a high-level overview of the project structure to inform task decomposition",
      inputSchema: {
        type: "object",
        properties: {
          max_depth: { type: "number", description: "Directory depth to show (default 3)" },
        },
      },
    },
    {
      name: "estimate_task_complexity",
      description: "Estimate the complexity of a task based on codebase size and affected files",
      inputSchema: {
        type: "object",
        properties: {
          task_description: { type: "string" },
          affected_paths: { type: "array", items: { type: "string" } },
        },
        required: ["task_description"],
      },
    },
    {
      name: "check_existing_tests",
      description: "Discover what test files exist and their coverage areas",
      inputSchema: {
        type: "object",
        properties: {
          test_directory: { type: "string", description: "Directory to look for tests (default: tests/ and test/)" },
        },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "inspect_project_structure": {
      const { max_depth = 3 } = z.object({ max_depth: z.number().default(3) }).parse(args);
      try {
        const output = execSync(
          `find '${WORKSPACE_ROOT}' -maxdepth ${max_depth} -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/__pycache__/*' | sort | head -150`,
          { encoding: "utf-8" }
        );
        const files = output.trim().split("\n").map(f => path.relative(WORKSPACE_ROOT, f));
        return { content: [{ type: "text", text: files.join("\n") }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Error: ${e.message}` }] };
      }
    }

    case "estimate_task_complexity": {
      const { task_description, affected_paths = [] } = z
        .object({ task_description: z.string(), affected_paths: z.array(z.string()).default([]) })
        .parse(args);

      let fileCount = 0;
      let lineCount = 0;
      for (const p of affected_paths) {
        try {
          const full = path.resolve(WORKSPACE_ROOT, p);
          const wc = execSync(`wc -l '${full}' 2>/dev/null || echo 0`, { encoding: "utf-8" });
          lineCount += parseInt(wc.trim().split(" ")[0] || "0", 10);
          fileCount++;
        } catch {}
      }

      const complexity = fileCount === 0 ? "unknown"
        : lineCount > 1000 ? "high"
        : lineCount > 200 ? "medium"
        : "low";

      return {
        content: [{
          type: "text",
          text: JSON.stringify({ task_description, affected_files: fileCount, total_lines: lineCount, complexity }),
        }],
      };
    }

    case "check_existing_tests": {
      const { test_directory } = z
        .object({ test_directory: z.string().optional() })
        .parse(args);
      try {
        const searchDir = test_directory
          ? path.resolve(WORKSPACE_ROOT, test_directory)
          : WORKSPACE_ROOT;
        const output = execSync(
          `find '${searchDir}' -name 'test_*.py' -o -name '*_test.py' -o -name '*.test.ts' -o -name '*.spec.ts' 2>/dev/null | sort | head -50`,
          { encoding: "utf-8" }
        );
        const tests = output.trim().split("\n").filter(Boolean).map(f => path.relative(WORKSPACE_ROOT, f));
        return { content: [{ type: "text", text: tests.join("\n") || "No test files found." }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Error: ${e.message}` }] };
      }
    }

    default:
      return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
