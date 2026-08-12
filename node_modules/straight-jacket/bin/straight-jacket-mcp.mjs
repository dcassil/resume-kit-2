#!/usr/bin/env node
// Read-only stdio MCP server for Straight Jacket.
//
// Speaks JSON-RPC 2.0 over stdin/stdout (newline-delimited) and exposes the
// read-only tool registry from src/mcp.js. It performs no mutations, captures
// no secrets, and never touches private signing material.

import { callTool, listTools } from "../src/mcp.js";
import { readFileSync } from "node:fs";

const PROTOCOL_VERSION = "2024-11-05";
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const SERVER_INFO = { name: "straight-jacket", version: packageJson.version };

function write(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function reply(id, result) {
  write({ jsonrpc: "2.0", id, result });
}

function replyError(id, code, message) {
  write({ jsonrpc: "2.0", id, error: { code, message } });
}

async function handle(message) {
  const { id, method, params } = message;

  switch (method) {
    case "initialize":
      reply(id, {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: { tools: {} },
        serverInfo: SERVER_INFO
      });
      return;
    case "notifications/initialized":
      return;
    case "ping":
      reply(id, {});
      return;
    case "tools/list": {
      const tools = await listTools();
      reply(id, { tools });
      return;
    }
    case "tools/call": {
      const name = params?.name;
      const args = params?.arguments ?? {};
      try {
        const result = await callTool(name, args);
        reply(id, {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }]
        });
      } catch (error) {
        reply(id, {
          isError: true,
          content: [{ type: "text", text: String(error?.message ?? error) }]
        });
      }
      return;
    }
    default:
      if (id !== undefined) {
        replyError(id, -32601, `Method not found: ${method}`);
      }
  }
}

let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  let index = buffer.indexOf("\n");
  while (index !== -1) {
    const line = buffer.slice(0, index).trim();
    buffer = buffer.slice(index + 1);
    if (line) {
      let message;
      try {
        message = JSON.parse(line);
      } catch {
        index = buffer.indexOf("\n");
        continue;
      }
      Promise.resolve(handle(message)).catch((error) => {
        if (message?.id !== undefined) {
          replyError(message.id, -32603, String(error?.message ?? error));
        }
      });
    }
    index = buffer.indexOf("\n");
  }
});

process.stdin.on("end", () => process.exit(0));
