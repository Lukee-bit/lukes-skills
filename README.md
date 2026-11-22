# Luke's skills

Original agent tools and skills by Luke, written from scratch and free of third-party code. Each tool works on its own with no dependencies. Anything that ties a tool to another product is a setting that is off by default.

| Tool | What it does | Claude Code | OpenCode | Cursor |
|---|---|---|---|---|
| [agent-handoff](#agent-handoff) | Per-project memory in the repo: handoff, durable facts, a managed `AGENTS.md` block, `/save-handoff`. | plugin | via the bridge | skill + command on PATH |
| [ask](#ask-and-modularize) | `/ask`: read-only Q&A that never changes anything. | plugin | copy command | copy to `.cursor/commands/` |
| [modularize](#ask-and-modularize) | `/modularize <function>`: split one function into small documented helpers. | plugin | copy command | copy to `.cursor/commands/` |
| [vault-bootstrap](#vault-bootstrap) | Turns a project folder into an Obsidian vault on the first session. | plugin | via the bridge | run the command |
| [opencode-hooks-bridge](#opencode-hooks-bridge) | Runs Claude-style command hooks from OpenCode events. | n/a | plugin file | n/a |

Claude Code: `/plugin marketplace add Lukee-bit/lukes-skills`, then `/plugin install <tool>@lukes-skills`.
Every tool needs only Python 3.8+ (Node for the bridge). Run the checks with `python -m unittest discover -s tests` and `node --test tests/bridge.test.js`.

## agent-handoff

Per-project agent memory that lives in the repo, so any harness can pick up where the last one stopped.
- Creates `.agent/` with `handoff.md` (where work stopped, next steps, open decisions), `memory/` (durable rules and facts, one per file) and `graphs/`.
- Keeps a managed block in `AGENTS.md`, plus a `CLAUDE.md` that includes it.
- Logs the files edited in a session, adds an automatic status block (branch, uncommitted files, recent commits), and at session end writes a short narrative.
- Adds `/save-handoff` and an Agent Skill that explains how to write a good handoff by hand.
- Never writes inside a `map/` folder. A project opts out with an empty `.agent-handoff-off` file.

Settings are read from `~/.config/agent-handoff/config.json`, then the project's `.agent/config.json`, then environment variables (see `plugins/agent-handoff/config.example.json`).

| Setting | Default | Effect |
|---|---|---|
| `integrations.mcptoon` | off | Also writes an `.mcp.json` entry for the mcptoon gateway, an `.agent/mcp-servers.json` export (secrets scrubbed) and the matching AGENTS line. Env: `AGENT_HANDOFF_MCPTOON=1`. |
| `integrations.obsidian` | off | Also writes `.env` with `OBSIDIAN_VAULT_PATH`, the `.obsidian` ignore lines and the vault line, and seeds `_meta/profile.md` from `obsidian.profileSeed`. Env: `AGENT_HANDOFF_OBSIDIAN=1`. |
| `integrations.codegraph` | off | Adds the `.codegraph/` ignore line and the rebuild hint. Env: `AGENT_HANDOFF_CODEGRAPH=1`. |
| `claudeMemoryLink` | on | Links Claude Code's per-project memory folder into `.agent/memory`. |
| `summary.enabled`, `summary.model` | on, `haiku` | The end-of-session narrative, written by one `claude -p` call. If it fails, the file list is kept instead. |
| `backupDir` | `~/.agent-handoff/backups` | Where migrated memory is backed up. |

## ask and modularize

Two prompt-only commands. `/ask <question>` puts the agent in a read-only mode: it explores, cites `file:line`, suggests changes and never makes them. `/modularize <function>` refactors one function into well-named helpers with validation, explicit errors and documentation, keeping behavior.
Claude Code gets both from the plugins. For OpenCode copy `plugins/<tool>/opencode/commands/<tool>.md` into `~/.config/opencode/commands/`. For Cursor copy the Claude version into `.cursor/commands/`.

## vault-bootstrap

On the first session in a project folder it creates the Obsidian starter files (`.obsidian/` settings, `Home.md`, `Notes.md`), adds the `.gitignore` lines for git projects and registers the vault in the Obsidian app. It never overwrites, skips home, system and app-data folders, and works on Windows, macOS and Linux. Run `vault-bootstrap [DIR]` by hand, or `vault-bootstrap trust DIR` (Windows) to turn Restricted mode off for a vault while Obsidian is closed. Opt a project out with `.vault-bootstrap-off`.
Setting `integrations.localRestApi` (off by default, `~/.config/vault-bootstrap/config.json` or `VAULT_BOOTSTRAP_LOCAL_REST_API=1`) also copies the Local REST API community plugin from `pluginDir`, enables it, seeds its API key from `keyFile` and, on Windows, trusts the vault.

## opencode-hooks-bridge

An OpenCode plugin file. Copy `plugins/opencode-hooks-bridge/opencode/claude-hooks-bridge.js` to `~/.config/opencode/plugins/`. It runs command hooks written for the Claude Code hook contract when OpenCode fires the matching event (session start and end, prompt, context, compaction, before and after a tool). A hook that answers `permissionDecision: "deny"` blocks the tool call. Configure hooks and context files in `~/.config/opencode/claude-hooks-bridge.json` (see `config.example.json`). With no config it bridges `agent-handoff` if that is installed. It fails open on any error; `LUKES_BRIDGE=0` turns it off.

## Used by

[Luke's claude-config](https://github.com/Lukee-bit/claude-config) installs agent-handoff with all three integrations on.

## License

Copyright (c) 2026 Lukee-bit. All rights reserved. See `LICENSE`.
