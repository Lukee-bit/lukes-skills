# Changelog

## 1.1.0 (2026-11-21)
- `install.py` (and `Install.cmd` / `Install.command`): install one tool, several or all on Claude Code, Cursor and OpenCode. Idempotent, keeps backups, `--dry-run`, `--uninstall`, records what it placed.
- agent-handoff 1.1.0 and vault-bootstrap 1.1.0: a `--cursor` mode for Cursor hooks (project from the payload, Cursor's JSON output).
- opencode-hooks-bridge 1.1.0: `LUKES_BRIDGE_CONFIG` names another config file; SessionStart also runs on the first prompt when OpenCode's created event is missed; SessionEnd covers every session the bridge saw. Checked in a live OpenCode 2.3.2 run (prompt, session start and edit hooks fire).
- ask, modularize: unchanged (1.0.0).


## 1.0.0 (2026-11-21)
- agent-handoff 1.0.0: per-project memory and handoff; mcptoon, obsidian and codegraph outputs are settings, off by default.
- ask 1.0.0: `/ask`, a read-only Q&A command (Claude Code and OpenCode versions).
- modularize 1.0.0: `/modularize <function>` (Claude Code and OpenCode versions).
- vault-bootstrap 1.0.0: makes a project an Obsidian vault; the Local REST API plugin setup is a setting, off by default.
- opencode-hooks-bridge 1.0.0: runs Claude-style command hooks from OpenCode events.
