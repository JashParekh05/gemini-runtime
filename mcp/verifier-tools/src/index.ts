import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { execSync } from "child_process";

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || process.cwd();

const server = new Server(
  { name: "verifier-tools", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "run_pytest",
      description: "Run pytest in the workspace and return test results",
      inputSchema: {
        type: "object",
        properties: {
          test_path: { type: "string", description: "Path to run tests in (default: all)" },
          coverage: { type: "boolean", description: "Collect coverage report" },
        },
      },
    },
    {
      name: "run_mypy",
      description: "Run mypy type checker on the workspace",
      inputSchema: {
        type: "object",
        properties: {
          paths: {
            type: "array",
            items: { type: "string" },
            description: "Paths to check (default: workspace root)",
          },
        },
      },
    },
    {
      name: "run_ruff",
      description: "Run ruff linter on the workspace",
      inputSchema: {
        type: "object",
        properties: {
          paths: { type: "array", items: { type: "string" } },
          fix: { type: "boolean", description: "Auto-fix issues" },
        },
      },
    },
    {
      name: "check_test_coverage",
      description: "Parse coverage.xml or .coverage to get coverage percentage",
      inputSchema: { type: "object", properties: {} },
    },
  ],
}));

function runCmd(cmd: string, cwd: string = WORKSPACE_ROOT): { output: string; exitCode: number } {
  try {
    const output = execSync(cmd, { cwd, encoding: "utf-8", stdio: "pipe", timeout: 120_000 });
    return { output, exitCode: 0 };
  } catch (e: any) {
    return { output: e.stdout || e.message || "", exitCode: e.status || 1 };
  }
}

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "run_pytest": {
      const { test_path = ".", coverage = true } = z
        .object({ test_path: z.string().default("."), coverage: z.boolean().default(true) })
        .parse(args);
      const covArgs = coverage ? "--cov=. --cov-report=term-missing" : "";
      const { output, exitCode } = runCmd(
        `python -m pytest ${test_path} ${covArgs} -v --tb=short --no-header -q 2>&1 | tail -50`,
      );
      return { content: [{ type: "text", text: `exit_code=${exitCode}\n${output}` }] };
    }

    case "run_mypy": {
      const { paths = ["."] } = z
        .object({ paths: z.array(z.string()).default(["."]) })
        .parse(args);
      const { output, exitCode } = runCmd(`python -m mypy ${paths.join(" ")} --ignore-missing-imports 2>&1 | head -80`);
      return { content: [{ type: "text", text: `exit_code=${exitCode}\n${output}` }] };
    }

    case "run_ruff": {
      const { paths = ["."], fix = false } = z
        .object({ paths: z.array(z.string()).default(["."]), fix: z.boolean().default(false) })
        .parse(args);
      const fixArg = fix ? "--fix" : "";
      const { output, exitCode } = runCmd(`python -m ruff check ${fixArg} ${paths.join(" ")} 2>&1 | head -60`);
      return { content: [{ type: "text", text: `exit_code=${exitCode}\n${output}` }] };
    }

    case "check_test_coverage": {
      const { output } = runCmd("python -m coverage report --format=total 2>/dev/null || echo 'n/a'");
      return { content: [{ type: "text", text: output.trim() }] };
    }

    default:
      return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
