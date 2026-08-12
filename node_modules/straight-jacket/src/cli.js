#!/usr/bin/env node
import { runCommand } from "./cli/commands.js";
import { exitCodeForError, exitCodeForResult } from "./cli/exit-codes.js";
import { formatError, formatOutput } from "./cli/output.js";
import { parseArgs } from "./cli/parse-args.js";

const argv = process.argv.slice(2);
let json = false;

try {
  json = parseArgs(argv).flags.json === true;
  const result = await runCommand({
    argv,
    cwd: process.cwd(),
    stdin: process.stdin,
    stdout: process.stdout,
    stderr: process.stderr
  });
  const output = formatOutput({ json, result });
  process.stdout.write(output.stdout);
  process.stderr.write(output.stderr);
  process.exitCode = exitCodeForResult(result);
} catch (error) {
  const output = formatError({ json, error });
  process.stdout.write(output.stdout);
  process.stderr.write(output.stderr);
  process.exitCode = exitCodeForError(error);
}
