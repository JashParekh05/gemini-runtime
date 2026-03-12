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
  { name: "executor-tools", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "write_file",
      description: "Write content to a file in the workspace (creates or overwrites)",
      inputSchema: {
        type: "object",
        properties: {
          file_path: { type: "string" },
          content: { type: "string" },
        },
        required: ["file_path", "content"],
      },
    },
    {
      name: "apply_unified_diff",
      description: "Apply a unified diff patch to files in the workspace",
      inputSchema: {
        type: "object",
        properties: {
          patch: { type: "string", description: "Unified diff string" },
        },
        required: ["patch"],
      },
    },
    {
      name: "run_shell_command",
      description: "Run a shell command in the workspace (e.g. pip install, npm install)",
      inputSchema: {
        type: "object",
        properties: {
          command: { type: "string" },
          timeout_ms: { type: "number", description: "Timeout in ms (default 30000)" },
        },
        required: ["command"],
      },
    },
    {
      name: "delete_file",
      description: "Delete a file from the workspace",
      inputSchema: {
        type: "object",
        properties: {
          file_path: { type: "string" },
        },
        required: ["file_path"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "write_file": {
      const { file_path, content } = z
        .object({ file_path: z.string(), content: z.string() })
        .parse(args);
      const fullPath = path.resolve(WORKSPACE_ROOT, file_path);
      if (!fullPath.startsWith(WORKSPACE_ROOT)) {
        return { content: [{ type: "text", text: "Error: path outside workspace" }] };
      }
      await fs.mkdir(path.dirname(fullPath), { recursive: true });
      await fs.writeFile(fullPath, content, "utf-8");
      return { content: [{ type: "text", text: `Written: ${file_path}` }] };
    }

    case "apply_unified_diff": {
      const { patch } = z.object({ patch: z.string() }).parse(args);
      const tmpFile = `/tmp/patch_${Date.now()}.diff`;
      await fs.writeFile(tmpFile, patch, "utf-8");
      try {
        const output = execSync(`patch -p1 < '${tmpFile}'`, {
          cwd: WORKSPACE_ROOT,
          encoding: "utf-8",
        });
        return { content: [{ type: "text", text: `Patch applied:\n${output}` }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Patch failed: ${e.message}` }] };
      } finally {
        await fs.unlink(tmpFile).catch(() => {});
      }
    }

    case "run_shell_command": {
      const { command, timeout_ms = 30000 } = z
        .object({ command: z.string(), timeout_ms: z.number().default(30000) })
        .parse(args);
      // Restrict to safe commands only
      const blocked = ["rm -rf", "sudo", "curl", "wget", "nc ", "netcat"];
      if (blocked.some((b) => command.includes(b))) {
        return { content: [{ type: "text", text: `Command blocked: ${command}` }] };
      }
      try {
        const output = execSync(command, {
          cwd: WORKSPACE_ROOT,
          encoding: "utf-8",
          timeout: timeout_ms,
        });
        return { content: [{ type: "text", text: output || "(no output)" }] };
      } catch (e: any) {
        return { content: [{ type: "text", text: `Command error: ${e.message}\n${e.stderr || ""}` }] };
      }
    }

    case "delete_file": {
      const { file_path } = z.object({ file_path: z.string() }).parse(args);
      const fullPath = path.resolve(WORKSPACE_ROOT, file_path);
      if (!fullPath.startsWith(WORKSPACE_ROOT)) {
        return { content: [{ type: "text", text: "Error: path outside workspace" }] };
      }
      await fs.unlink(fullPath);
      return { content: [{ type: "text", text: `Deleted: ${file_path}` }] };
    }

    default:
      return { content: [{ type: "text", text: `Unknown tool: ${name}` }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
