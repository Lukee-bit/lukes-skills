# Handoff

<!-- handoff:narrative:begin -->
## Where I stopped
- Luke's skills 1.0.0 contains five tools, each its own plugin in `.claude-plugin/marketplace.json`: `agent-handoff`, `ask`, `modularize`, `vault-bootstrap`, `opencode-hooks-bridge`. All validate with `claude plugin validate`, and the tests pass (`python -m unittest discover -s tests`, `node --test tests/bridge.test.js`).
- `agent-handoff` was ported from the claude-config repo's `bin/agent-handoff`. With its three integrations on, its output is byte-identical to the original (checked on scratch projects).
- `vault-bootstrap` is a Python rewrite of the original bash script plus `obsidian_trust.py` (a copy of the original helper). With `localRestApi` on, its output matches the original (12 files, parsed JSON equal).
- `opencode-hooks-bridge` is a generalized rewrite of the OpenCode adapter, with no third-party coupling. It is tested with a fake OpenCode context and in a live OpenCode 2.3.2 run (prompt, session-start and edit hooks fire).
- `install.py` installs any tool alone or all of them on Claude Code, Cursor and OpenCode (version 1.1.0 on `feat/installers`).
- The claude-config repo installs `agent-handoff` from this repo at a pinned commit (PR #22 there). It does not use the other four tools yet.

## Next steps
0. Job 1 (installers) is on branch `feat/installers`. After it merges, tag `v1.1.0`, then run Job 2 in `.agent/next-session.md` (switch claude-config over to vault-bootstrap, ask, modularize and the bridge).
1. Cursor hooks have not fired live from the `agent` CLI here; try the Cursor IDE, and check SessionEnd in a full OpenCode session.
2. Optional: switch claude-config's installers to `vault-bootstrap` and the bridge. Do it in a claude-config PR, and bump its pin in `tools/git-sources.txt`.
3. Whenever agent-handoff changes here, bump the pin in claude-config.

## Open decisions
- Rewrite the borderline claude-config items (`sycophancy-transform`, `semgrep-roots-shim`, the Cursor wrapper) before adding them here, so the repo stays free of upstream wording and third-party names.
<!-- handoff:narrative:end -->

<!-- handoff:auto:begin -->
## Auto status (2026-11-21 19:40)
- branch: `main`
- uncommitted files: 13
- recent commits:
  - c24ee6a initial
  - 63a4040 README
  - 0e0dda8 Quote plugin root in hooks, pin LF line endings
  - 46f2f81 Mark launcher executable
  - 7b1deb7 agent-handoff 1.0.0: per-project agent memory and handoff
<!-- handoff:auto:end -->
