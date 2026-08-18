# career-mcp

`career-mcp` exposes the narrow `career.*` tool surface over a stdio JSON-RPC MCP server backed by `career-store`.

## Running Locally

Launch the server with an explicit career-store database path:

```sh
python3 -m career_mcp --db /absolute/path/to/career.db
```

If `--db` is omitted, the entry point falls back to `CAREER_MCP_DB`:

```sh
CAREER_MCP_DB=/absolute/path/to/career.db python3 -m career_mcp
```

The process reads newline-delimited JSON-RPC requests from stdin and writes responses to stdout. Stderr is reserved for startup failures.

## Host Registration

Example Claude Code-style MCP host configuration:

```json
{
  "mcpServers": {
    "career-mcp": {
      "command": "python3",
      "args": ["-m", "career_mcp", "--db", "/absolute/path/to/career.db"]
    }
  }
}
```

Generic stdio MCP hosts should use `python3` as the command, pass `["-m", "career_mcp", "--db", "..."]` as arguments, and keep the process stdin/stdout connected for the JSON-RPC session.
