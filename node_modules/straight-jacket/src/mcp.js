import * as core from "./index.js";
import { createToolRegistry } from "./mcp/tools.js";

const registry = createToolRegistry(core);

export async function listTools() {
  return registry.listTools();
}

export async function callTool(name, args) {
  return registry.callTool(name, args);
}
