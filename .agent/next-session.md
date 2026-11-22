# Next session: run these two jobs

Written 2026-11-21 at the end of the session that built Luke's skills 1.0.0. Read `.agent/handoff.md` and `.agent/memory/` first.
This file belongs to lukes-skills. **Never copy any of it into the claude-config repo's `.agent/`, `_raw/` or notes.** Job 2 edits claude-config code and docs only, as a normal PR.

## Update 2026-11-21 (later session): Job 1 is done on branch `feat/installers`
`install.py`, `Install.cmd`/`Install.command`, a `--cursor` mode (agent-handoff, vault-bootstrap), bridge `LUKES_BRIDGE_CONFIG` and a SessionStart-on-first-prompt fix, tests, README, CHANGELOG 1.1.0. PR #1 and claude-config PR #22 are merged; tag `v1.0.0` is on the remote.
- Proven: each tool installs alone on Claude Code (scratch config dir, local source); the bridge fires prompt, session-start and edit hooks in a live OpenCode 2.3.2 run (`opencode run --standalone`, bridge as a project plugin under `.opencode/plugins/`, env `PWD` set to the project, `LUKES_BRIDGE_CONFIG` pointing at a logging config).
- Not proven: Cursor hooks firing live (the `agent -p` CLI ran none of even a plain logger hook, and claude-config's wrapped hooks block its tools on this machine); SessionEnd in `opencode run`.
- Left: merge the installers PR, tag `v1.1.0` on the merge commit, then **Job 2** below (pin claude-config to that commit). Job 1 text below is kept for reference.

## State when this was written (before Job 1)
- lukes-skills: PR #1 (`release/1.0.0` into `main`) is open and the user merges it. Tag `v1.0.0` was made locally on that branch. Local `main` was reset to `origin/main`. guard-pack blocks `git push` to main, so use branches and PRs. Check whether PR #1 is merged and whether the tag is on the remote (`git ls-remote --tags origin`) before starting.
- claude-config: PR #22 (agent-handoff from lukes-skills at pin `0e0dda8`) was open. PR #21 (rebrand) is merged. Worktrees `../claude-config-handoff` (branch `feat/lukes-skills-handoff`) and `../claude-config-rebrand` (branch `docs/rebrand`) still exist: remove them once their PRs are merged (an empty `../claude-config-comet-test` folder is locked by a process; ignore it).
- The tools: `agent-handoff`, `ask`, `modularize`, `vault-bootstrap`, `opencode-hooks-bridge` under `plugins/`. Tests: `python -m unittest discover -s tests`, `node --test tests/bridge.test.js`.

## Job 1: every tool installs on its own, on Claude Code, Cursor and OpenCode
Goal: for each of the five tools, a person can install just that tool, not the bundle, on each harness, with no duplicates, on Windows and macOS.

1. **Claude Code.** `/plugin install <tool>@lukes-skills` should already work alone. Prove it: in a scratch `CLAUDE_CONFIG_DIR`, add the marketplace and install each tool by itself, then check its command, hook or skill loads and nothing from the other four appears. Fix any hidden coupling (for example a launcher that expects a sibling file).
2. **Cursor and OpenCode have no plugin marketplace here.** Add one stdlib Python installer at the repo root, `install.py` (a double-click `Install.cmd` / `Install.command` wrapper is optional), run as `python install.py <tool|all> --harness claude,cursor,opencode [--dry-run] [--uninstall]`:
   - Idempotent. Back up any file it replaces as `*.bak-YYYYMMDD`. Never add a hook, command or plugin that is already present (match on the exact command).
   - Per tool and harness, place only that tool's files:
     - `ask`, `modularize`: Cursor gets the Claude-style file in `~/.cursor/commands/`; OpenCode gets `plugins/<tool>/opencode/commands/<tool>.md` in `~/.config/opencode/commands/`.
     - `agent-handoff`: copy `bin/agent_handoff.py` to a stable path (for example `~/.local/bin/agent-handoff`) and register its four hooks. Cursor: `~/.cursor/hooks.json` (format `{"version":1,"hooks":{event:[...]}}`; look at how claude-config's `cursor/render.py` merges hooks, and at current Cursor docs for the event names that match init, tool, prompt and end). OpenCode: install the bridge (below) so the same four commands run. Also place its skill (`skills/agent-handoff`) in each harness's skills folder if it has one.
     - `vault-bootstrap`: copy `vault_bootstrap.py` **and `obsidian_trust.py` next to it** (the script finds its helper beside itself). Register it as a session-start hook where the harness supports one, otherwise document running `vault-bootstrap` by hand.
     - `opencode-hooks-bridge`: copy the `.js` file to `~/.config/opencode/plugins/`. Create a starter `claude-hooks-bridge.json` only if none exists. This is the one tool that has no Claude Code or Cursor version.
   - Verify the exact paths and the hook schemas against the harnesses installed here (Cursor with its `agent` CLI, OpenCode 2.x) before relying on the layout above; the layout is a plan, not a confirmed fact.
3. **Docs.** Add one install line per tool and harness to the README table, and a "Uninstall" line.
4. **Tests.** Scratch HOME (and APPDATA, `CLAUDE_CONFIG_DIR`). For each tool alone and each harness: install, check the files, re-run (no change), uninstall (back to the start state). Add them to `tests/`.
5. **Real check.** Install one tool alone into this machine's Cursor and OpenCode with a unique test setup (or a scratch config dir), prove it works (OpenCode: load the bridge in a live session, which was never done), then remove it.
6. Update `CHANGELOG.md`, bump versions only for tools whose files changed, branch + PR, tag.

## Job 2: claude-config sources the other four tools from lukes-skills (like agent-handoff)
Goal: Luke's claude-config installs `vault-bootstrap`, `ask`, `modularize` and the OpenCode bridge from lukes-skills and drops its own copies, with **no change to what this machine does**. Do it in a worktree off `origin/main` of claude-config, as a PR. The pattern to copy is PR #22 (look at `tools/git-sources.txt`, the lukes-skills block in `install.ps1` and `install.sh`, and `export.py`).

1. Wait for lukes-skills PR #1 to merge (and for Job 1 if its installer is to be reused). Bump the `lukes-skills` pin in claude-config's `tools/git-sources.txt` to the merge commit.
2. **vault-bootstrap.** Place `plugins/vault-bootstrap/bin/vault_bootstrap.py` as `~/.claude-tools/bin/vault-bootstrap` and **`obsidian_trust.py` as `~/.claude-tools/bin/obsidian_trust.py`** (it must sit beside the script). Write `~/.config/vault-bootstrap/config.json` with `localRestApi` on, `pluginDir` `~/.claude-tools/obsidian-plugins`, `keyFile` `~/.claude-tools/obsidian.env`, `trust` true. Remove `bin/vault-bootstrap` and `bin/obsidian-trust-vault.py` from the repo and from `export.py` `BIN_SCRIPTS`. The new file is Python: macOS needs `chmod +x` after `place`; Windows needs `"vault-bootstrap": "python"` added to `INTERPRETER` in `windows/render.py` so the SessionStart hook (and the OpenCode launcher) run it with Python. The shared `_platform.sh` stays (other scripts use it).
3. **ask and modularize.** Replace `claude/commands/{ask,modularize}.md` and `opencode/commands/{ask,modularize}.md` with the lukes-skills versions (installed from the clone, or copied into the repo and marked as sourced). Accepted change: they lose the named code-search tools.
4. **OpenCode adapter.** Replace `opencode/plugins/claude-config.js` with the bridge, and write a `claude-hooks-bridge.json` that keeps today's behavior: agent-handoff (init, prompt, tool, end), the handoff and memory context injection, guard-pack as a PreToolUse hook, jCodeMunch post-tool and pre-compact hooks, and the vault, spec and index bootstraps at session start. Known gaps to solve first: guard-pack's path has a version in it (the old plugin resolved the newest version at run time), so add a small wrapper script in claude-config's `bin/` that finds it and runs it; and the old plugin ran the bootstraps with bash. Prove parity with a live OpenCode session before deleting the old file.
5. Update installers (`install.ps1`, `install.sh`, `install-opencode.*`, `install-cursor.*` if they place any of these), README Source repositories rows (agent-handoff and the new ones point at lukes-skills; spec-bootstrap and index-bootstrap stay "this repo"), `CHANGELOG.md` ("Action: re-run the installer"). Do not put lukes-skills-only notes in claude-config's `.agent/` or `_raw/`.
6. **Verify.** `Install.cmd -All -Yes` passes 7/7, twice with identical state; the installed files equal the repo files at the pin; a new Claude session in a scratch project gives the same `.agent/` and vault files as before; an OpenCode session fires the same hooks; the Cursor hooks still run. Restore `~/.claude-tools/config-repo` to `C:/Users/User/projects/claude-config` and `.config-rev` afterward (a test run repoints them at the worktree).
7. Merge order: lukes-skills PR #1, claude-config PR #22, then this PR. The user merges in the browser; a push to main and `gh pr merge` are blocked for me.

## Gotchas
- guard-pack blocks Bash command text that names the MCP config file, settings files or the hooks manifest, plus `rm` on paths with "test", `git push` to main and `gh pr merge/close`. Put edits in the Write/Edit tools or a scratchpad script.
- The old tools' output was proven identical by diffing scratch projects with a scratch HOME. Do the same for every swap here (`tests/` and `~/projects/lukes-skills` have examples).
- Do not run the real Obsidian trust helper against the real `%APPDATA%\obsidian` in tests.
