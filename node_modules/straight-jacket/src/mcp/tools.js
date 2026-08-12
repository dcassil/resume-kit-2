import { explainViolation } from "./explain-violation.js";
import { toolSchemas } from "./tool-schemas.js";

export function createToolRegistry(core = {}) {
  const tools = new Map([
    [toolSchemas.listProtectedFiles.name, {
      ...toolSchemas.listProtectedFiles,
      call: (args) => core.listProtectedFiles(args)
    }],
    [toolSchemas.verify.name, {
      ...toolSchemas.verify,
      call: (args) => core.verifyRepository(args)
    }],
    [toolSchemas.explainViolation.name, {
      ...toolSchemas.explainViolation,
      call: (args) => explainViolation(args.violation)
    }]
  ]);

  return {
    listTools() {
      return [...tools.values()].map(({ call, ...schema }) => schema);
    },
    async callTool(name, args) {
      const tool = tools.get(name);
      if (!tool) {
        throw new Error("TOOL_NOT_FOUND");
      }

      return tool.call(args);
    }
  };
}
