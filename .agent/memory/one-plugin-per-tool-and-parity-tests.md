---
name: one-plugin-per-tool-and-parity-tests
description: How tools are packaged here (one plugin each, stdlib only) and how a port from claude-config is checked.
metadata:
  type: project
---

Each tool is its own plugin under `plugins/<name>/`, listed in `.claude-plugin/marketplace.json`, version 1.0.0, license `UNLICENSED`. Python tools use only the standard library and a bash launcher that never fails a hook. Files use LF (`.gitattributes`). Hook commands quote `${CLAUDE_PLUGIN_ROOT}`.

**Why:** each tool must install alone, work on Windows and macOS, and never break a session.

**How to apply:** when porting something from claude-config, run the old and the new tool on scratch projects with a scratch HOME (and APPDATA on Windows) and diff the files; keep the result identical with the integrations on. Run `claude plugin validate` on the marketplace and on each plugin. A change to agent-handoff needs a pin bump in claude-config's `tools/git-sources.txt`.
