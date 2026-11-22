# lukes-skills - agent instructions

<!-- >>> agent-handoff (managed) -->
## Agent handoff (managed - do not edit between the markers)

This repo carries its own agent memory so any harness (Claude Code, Codex, Cursor, Gemini, ...) can continue where the last one stopped.

1. **Read first:** `.agent/handoff.md` (where work stopped, next steps, open decisions), then `.agent/memory/MEMORY.md` (durable project rules and facts).
2. **Hard rules live in `.agent/memory/`** - obey them before anything else.
3. **Write back:** record decisions and lessons as Markdown in `.agent/memory/` (one fact per file, index in `MEMORY.md`), decisions in `docs/adr/` or `openspec/`, and run `/save-handoff` (or edit `.agent/handoff.md` by hand) before you stop.
4. **Layout:** `.agent/memory/` agent memory; `.agent/graphs/` graph/diagram sources (JSON, Mermaid, SVG).
5. **Derived and rebuilt, never committed:** caches and `.env`.
6. **Never commit secrets.** Memory can contain pasted text; scan before pushing.
<!-- <<< agent-handoff -->
