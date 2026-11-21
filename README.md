# Luke's skills

Original agent tools and skills by Luke, written from scratch and free of third-party code. Each tool works on its own with no dependencies, and anything that ties it to another tool is a setting that is off by default.

## agent-handoff

Per-project agent memory that lives in the repo, so any agent harness can pick up where the last one stopped.

What it does:
- Creates `.agent/` with `handoff.md` (where work stopped, next steps, open decisions), `memory/` (durable project rules and facts, one per file) and `graphs/`.
- Keeps a managed block in `AGENTS.md`, and a `CLAUDE.md` that includes it, so every harness is told to read the handoff first.
- Logs the files edited in a session, adds an automatic status block (branch, uncommitted files, recent commits) to the handoff, and at session end writes a short narrative of what happened.
- Adds the `/save-handoff` command and an Agent Skill that tell an agent how to write a good handoff by hand.
- Never writes inside a `map/` folder. A project opts out with an empty `.agent-handoff-off` file.

It needs only Python 3.8 or newer and, for the status block, git. The default output uses no other tool.

### Install

| Harness | How |
|---|---|
| Claude Code | `/plugin marketplace add Lukee-bit/lukes-skills`, then `/plugin install agent-handoff@lukes-skills`. The hooks, `/save-handoff` and the skill arrive together. |
| Any harness | Clone this repo and copy `plugins/agent-handoff/skills/agent-handoff` into the harness's skills folder. Put `plugins/agent-handoff/bin` on your PATH to use the `agent-handoff` command, and call `agent-handoff init`, `tool`, `prompt` and `end` from that harness's hooks. |

### Settings

Settings are read from `~/.config/agent-handoff/config.json`, then the project's `.agent/config.json`, then environment variables. See `plugins/agent-handoff/config.example.json`.

| Setting | Default | Effect |
|---|---|---|
| `integrations.mcptoon` | off | Also writes an `.mcp.json` entry for the mcptoon gateway, an `.agent/mcp-servers.json` export (secrets scrubbed) and the matching AGENTS line. Env: `AGENT_HANDOFF_MCPTOON=1`. |
| `integrations.obsidian` | off | Also writes `.env` with `OBSIDIAN_VAULT_PATH`, the `.obsidian` ignore lines and the vault line, and seeds `_meta/profile.md` from `obsidian.profileSeed`. Env: `AGENT_HANDOFF_OBSIDIAN=1`. |
| `integrations.codegraph` | off | Adds the `.codegraph/` ignore line and the rebuild hint. Env: `AGENT_HANDOFF_CODEGRAPH=1`. |
| `claudeMemoryLink` | on | Links Claude Code's per-project memory folder into `.agent/memory`. |
| `summary.enabled`, `summary.model` | on, `haiku` | The end-of-session narrative, written by one `claude -p` call. If it fails, the file list is kept instead. |
| `backupDir` | `~/.agent-handoff/backups` | Where migrated memory is backed up. |

### Tests

`python -m unittest discover -s tests -v`

## Used by

[Luke's claude-config](https://github.com/Lukee-bit/claude-config) installs agent-handoff with all three integrations on.

## License

Copyright (c) 2026 Lukee-bit. All rights reserved. See `LICENSE`.
