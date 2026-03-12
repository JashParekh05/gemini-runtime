import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import * as fs from "fs/promises";
import * as path from "path";
import { execSync } from "child_process";

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT || process.cwd();

const server = new Server(
  { name: "researcher-tools", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "read_workspace_file",
      description: "Read the contents of a file in the workspace",
      inputSchema: {
        type: "object",
        properties: {
          file_path: { type: "string", description: "Relative path from workspace root" },
        },
        required: ["file_path"],
      },
    },
    {
      name: "search_codebase",
      description: "Search for a pattern across all files in the workspace using ripgrep",
      inputSchema: {
        type: "object",
        properties: {
          pattern: { type: "string", description: "Regex pattern to search for" },
          file_glob: { type: "string", description: "Optional glob to limit file types, e.g. '*.py'" },
          context_lines: { type: "number", description: "Lines of context around each match (default 2)" },
        },
        required: ["pattern"],
      },
    },
    {
      name: "list_workspace_files",
      description: "List files in the workspace, optionally filtered by extension",
      inputSchema: {
        type: "object",
        properties: {
          directory: { type: "string", description: "Subdirectory to list (relative), defaults to root" },
          extension: { type: "string", description: "Filter by extension, e.g. '.py'" },
          max_depth: { type: "number", description: "Max directory depth (default 3)" },
        },
      },
    },
    {
      name: "get_git_history",
      description: "Get recent git commits for a file or the whole repo",
      inputSchema: {
        type: "object",
        properties: {
          file_path: { type: "string", description: "Optional file path to get history for" },
          limit: { type: "number", description: "Number of commits to return (default 10)" },
        },
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "read_workspace_file": {
      const { file_path } = z.object({ file_path: z.string() }).parse(args);
      const fullPath = path.resolve(WORKSPACE_ROOT, file_path);
      if (!fullPath.startsWith(WORKSPACE_ROOT)) {
        return { content: [{ type: "text", text: "Error: path outside workspace" }] };
      }
      try {
        const content = await fs.readFile(fullPath, "utf-8");
        return { content: [{ type: "text", text: content }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Error reading file: ${e.message}` }] };
      }
    }

    case "search_codebase": {
      const { pattern, file_glob, context_lines = 2 } = z
        .object({ pattern: z.string(), file_glob: z.string().optional(), context_lines: z.number().default(2) })
        .parse(args);
      try {
        const globArg = file_glob ? `--glob '${file_glob}'` : "";
        const cmd = `rg --with-filename --line-number -C ${context_lines} ${globArg} '${pattern.replace(/'/g, "\\'")}' '${WORKSPACE_ROOT}' 2>/dev/null | head -200`;
        const output = execSync(cmd, { encoding: "utf-8", cwd: WORKSPACE_ROOT });
        return { content: [{ type: "text", text: output || "No matches found." }] };
      } catch {
        return { content: [{ type: "text", text: "No matches found." }] };
      }
    }

    case "list_workspace_files": {
      const { directory = ".", extension, max_depth = 3 } = z
        .object({ directory: z.string().default("."), extension: z.string().optional(), max_depth: z.number().default(3) })
        .parse(args);
      try {
        const extFilter = extension ? `--include='*${extension}'` : "";
        const cmd = `find '${path.resolve(WORKSPACE_ROOT, directory)}' -maxdepth ${max_depth} -type f ${extFilter} | sort | head -100`;
        const output = execSync(cmd, { encoding: "utf-8" });
        const files = output.trim().split("\n").filter(Boolean).map(f => path.relative(WORKSPACE_ROOT, f));
        return { content: [{ type: "text", text: files.join("\n") || "No files found." }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Error: ${e.message}` }] };
      }
    }

    case "get_git_history": {
      const { file_path, limit = 10 } = z
        .object({ file_path: z.string().optional(), limit: z.number().default(10) })
        .parse(args);
      try {
        const fileArg = file_path ? `-- '${file_path}'` : "";
        const cmd = `git -C '${WORKSPACE_ROOT}' log --oneline -${limit} ${fileArg}`;
        const output = execSync(cmd, { encoding: "utf-8" });
        return { content: [{ type: "text", text: output || "No commits found." }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Git error: ${e.message}` }] };
      }
    }

    default:
      return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
