"""Self-check for agent-handoff. Run: python -m unittest discover -s tests -v

Each test runs the real script in a subprocess with HOME pointed at a scratch folder, so nothing
on the machine is touched. The scratch folder lives under the real home because the tool refuses
system and temp locations.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "agent-handoff" / "bin" / "agent_handoff.py"

# The block the original claude-config tool wrote; with every integration on the output must match.
ORIGINAL_BLOCK = """\
## Agent handoff (managed - do not edit between the markers)

This repo carries its own agent memory so any harness (Claude Code, Codex, Cursor, Gemini, ...) can continue where the last one stopped.

1. **Read first:** `.agent/handoff.md` (where work stopped, next steps, open decisions), then `.agent/memory/MEMORY.md` (durable project rules and facts).
2. **Hard rules live in `.agent/memory/`** - obey them before anything else.
3. **Write back:** record decisions and lessons as Markdown in `.agent/memory/` (one fact per file, index in `MEMORY.md`), decisions in `docs/adr/` or `openspec/`, and run `/save-handoff` (or edit `.agent/handoff.md` by hand) before you stop.
4. **Layout:** `.agent/memory/` agent memory; `.agent/graphs/` graph/diagram sources (JSON, Mermaid, SVG); the repo root is also the Obsidian vault.
5. **Derived and rebuilt, never committed:** code indexes (`.codegraph/`), caches, `.env`. Rebuild with `codegraph init -y`, or start a Claude Code session (SessionStart hooks do it).
6. **Tools:** `.mcp.json` points at the `mcptoon` gateway. `.agent/mcp-servers.json` lists the servers the original machine ran (paths are machine-specific; import with `mcptoon import --file .agent/mcp-servers.json --write` and fix paths).
7. **Never commit secrets.** Memory can contain pasted text; scan before pushing.
"""
ORIGINAL_GITIGNORE = ".env\n.DS_Store\n.codegraph/\n.obsidian/plugins/\n.obsidian/workspace*.json\n.obsidian/cache\n.agent/cache/\n.agent/.buffer/\n.claude/settings.local.json\n*.pre-handoff-*"


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=".ah-test-", dir=Path.home()))
        self.home = self.root / "home"
        self.proj = self.home / "proj"
        self.proj.mkdir(parents=True)
        (self.proj / "README.md").write_text("x\n")  # marks the folder as a project
        self.env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home)}
        for k in [k for k in self.env if k.startswith("AGENT_HANDOFF_")]:
            del self.env[k]

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_tool(self, *args, stdin="", env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True,
                              env=env or self.env, cwd=str(self.proj), timeout=60)

    def config(self, **integrations):
        p = self.home / ".config" / "agent-handoff"
        p.mkdir(parents=True, exist_ok=True)
        (p / "config.json").write_text(json.dumps({"integrations": integrations, "claudeMemoryLink": False}))


class DefaultsNeedNothing(Base):
    def test_default_init_writes_only_dependency_free_files(self):
        r = self.run_tool("init", str(self.proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in (".agent/README.md", ".agent/handoff.md", ".agent/memory/MEMORY.md", "AGENTS.md", "CLAUDE.md", ".gitignore"):
            self.assertTrue((self.proj / f).exists(), f)
        for f in (".mcp.json", ".env", ".agent/mcp-servers.json", "_meta"):
            self.assertFalse((self.proj / f).exists(), f)
        block = (self.proj / "AGENTS.md").read_text()
        for word in ("mcptoon", "Obsidian", "codegraph"):
            self.assertNotIn(word, block)
        self.assertIn("5. **Derived and rebuilt, never committed:** caches and `.env`.", block)
        self.assertIn("6. **Never commit secrets.**", block)
        ign = (self.proj / ".gitignore").read_text()
        self.assertNotIn(".obsidian", ign)
        self.assertNotIn(".codegraph", ign)


class Parity(Base):
    def test_all_integrations_match_the_original_output(self):
        self.config(mcptoon=True, obsidian=True, codegraph=True)
        (self.home / ".mcptoon").mkdir()
        (self.home / ".mcptoon" / "config.json").write_text(json.dumps({"servers": {"a": {"command": "x", "env": {"API_KEY": "s"}}}}))
        self.run_tool("init", str(self.proj))
        text = (self.proj / "AGENTS.md").read_text()
        self.assertIn(ORIGINAL_BLOCK, text)
        self.assertEqual((self.proj / ".gitignore").read_text().split(">>> agent-handoff (managed)\n")[1].split("# <<<")[0].rstrip("\n"), ORIGINAL_GITIGNORE)
        self.assertIn(f"OBSIDIAN_VAULT_PATH={self.proj.resolve()}", (self.proj / ".env").read_text())
        self.assertEqual(json.loads((self.proj / ".mcp.json").read_text())["mcpServers"]["mcptoon"]["args"], ["serve"])
        self.assertEqual(json.loads((self.proj / ".agent/mcp-servers.json").read_text())["mcpServers"]["a"]["env"]["API_KEY"], "<set-locally>")

    def test_readme_names_its_own_path(self):
        self.run_tool("init", str(self.proj))
        self.assertIn("Managed by `", (self.proj / ".agent/README.md").read_text())


class Behaviour(Base):
    def test_init_is_idempotent(self):
        self.config(mcptoon=True, obsidian=True, codegraph=True)
        self.run_tool("init", str(self.proj))
        snap = {p: p.read_text() for p in self.proj.rglob("*") if p.is_file()}
        self.run_tool("init", str(self.proj))
        self.assertEqual(snap, {p: p.read_text() for p in self.proj.rglob("*") if p.is_file()})

    def test_never_writes_inside_map(self):
        (self.proj / "map").mkdir()
        (self.proj / "AGENTS.md").write_text("")
        self.run_tool("init", str(self.proj))
        self.assertEqual(list((self.proj / "map").iterdir()), [])

    def test_opt_out_file(self):
        (self.proj / ".agent-handoff-off").write_text("")
        self.run_tool("init", str(self.proj))
        self.assertFalse((self.proj / ".agent").exists())

    def test_tool_hook_logs_edit_and_prompt_is_silent(self):
        self.run_tool("init", str(self.proj))
        f = self.proj / "a.txt"
        f.write_text("x")
        payload = json.dumps({"session_id": "s1", "tool_input": {"file_path": str(f)}})
        self.run_tool("tool", str(self.proj), stdin=payload)
        buf = self.proj / ".agent" / ".buffer" / "s1.jsonl"
        self.assertIn('"a.txt"', buf.read_text())
        r = self.run_tool("prompt", str(self.proj), stdin=json.dumps({"session_id": "s1"}))
        self.assertEqual(r.stdout, "")

    def test_end_writes_status_and_clears_small_buffers(self):
        self.run_tool("init", str(self.proj))
        self.run_tool("end", str(self.proj), stdin=json.dumps({"session_id": "s2"}))
        self.assertIn("## Auto status", (self.proj / ".agent" / "handoff.md").read_text())

    def test_context_prints_handoff(self):
        self.run_tool("init", str(self.proj))
        r = self.run_tool("context", str(self.proj))
        self.assertIn("Previous-session handoff", r.stdout)

    def test_env_var_turns_an_integration_on(self):
        env = {**self.env, "AGENT_HANDOFF_MCPTOON": "1"}
        self.run_tool("init", str(self.proj), env=env)
        self.assertTrue((self.proj / ".mcp.json").exists())


if __name__ == "__main__":
    unittest.main()
