"""install.py: every tool alone and all together, on each harness, in a scratch home."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = ["agent-handoff", "ask", "modularize", "vault-bootstrap", "opencode-hooks-bridge"]


def tree(root: Path):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lukes-install-"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "claude.log"
        if os.name == "nt":
            (self.bin / "claude.bat").write_text(f'@echo %* >> "{self.log}"\r\n')
        else:
            f = self.bin / "claude"
            f.write_text(f'#!/bin/sh\necho "$@" >> "{self.log}"\n')
            f.chmod(0o755)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *args):
        env = {**os.environ, "LUKES_SKILLS_HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
               "PATH": str(self.bin) + os.pathsep + os.environ["PATH"]}
        r = subprocess.run([sys.executable, str(REPO / "install.py"), *args], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def snapshot(self):
        return tree(self.home)

    def hooks(self, p):
        return json.loads(p.read_text())["hooks"]

    # ---- each tool alone, each harness: install, re-run, uninstall ---------------------------
    def cycle(self, tool, harness):
        (self.home / ".cursor").mkdir(exist_ok=True)
        (self.home / ".config" / "opencode").mkdir(parents=True, exist_ok=True)
        before = self.snapshot()
        self.run_install(tool, "--harness", harness)
        after = self.snapshot()
        self.run_install(tool, "--harness", harness)
        self.assertEqual(self.snapshot(), after, f"{tool}/{harness}: second run changed files")
        self.run_install(tool, "--harness", harness, "--uninstall")
        self.assertEqual(self.snapshot(), before, f"{tool}/{harness}: uninstall left files behind")
        return before, after

    def test_each_tool_each_harness(self):
        for tool in TOOLS:
            for harness in ("cursor", "opencode"):
                with self.subTest(tool=tool, harness=harness):
                    before, after = self.cycle(tool, harness)
                    if tool == "opencode-hooks-bridge" and harness == "cursor":
                        self.assertEqual(before, after)
                    else:
                        self.assertNotEqual(before, after)

    def test_claude_runs_plugin_commands(self):
        self.run_install("vault-bootstrap", "--harness", "claude")
        log = self.log.read_text()
        self.assertIn("plugin marketplace add Lukee-bit/lukes-skills", log)
        self.assertIn("plugin install vault-bootstrap@lukes-skills", log)
        self.assertNotIn("agent-handoff", log)
        self.run_install("vault-bootstrap", "--harness", "claude", "--uninstall")
        self.assertIn("plugin uninstall vault-bootstrap@lukes-skills", self.log.read_text())

    # ---- placement details ----------------------------------------------------------------------
    def test_cursor_agent_handoff_alone(self):
        self.run_install("agent-handoff", "--harness", "cursor")
        h = self.hooks(self.home / ".cursor" / "hooks.json")
        self.assertEqual(set(h), {"sessionStart", "beforeSubmitPrompt", "afterFileEdit", "sessionEnd"})
        self.assertTrue(all("--cursor" in v[0]["command"] for v in h.values()))
        self.assertTrue((self.home / ".local/share/lukes-skills/agent-handoff/agent_handoff.py").exists())
        self.assertFalse((self.home / ".local/share/lukes-skills/vault-bootstrap").exists())
        cmd = (self.home / ".cursor/commands/save-handoff.md").read_text()
        self.assertNotIn("CLAUDE_PLUGIN_ROOT", cmd)
        self.assertNotIn("allowed-tools", cmd)
        self.assertTrue((self.home / ".cursor/skills/agent-handoff/SKILL.md").exists())

    def test_vault_bootstrap_ships_its_helper_beside_it(self):
        self.run_install("vault-bootstrap", "--harness", "opencode")
        d = self.home / ".local/share/lukes-skills/vault-bootstrap"
        self.assertTrue((d / "vault_bootstrap.py").exists() and (d / "obsidian_trust.py").exists())

    def test_opencode_tools_share_one_bridge_config(self):
        self.run_install("agent-handoff", "vault-bootstrap", "--harness", "opencode")
        cfg = json.loads((self.home / ".config/opencode/claude-hooks-bridge.json").read_text())
        self.assertEqual(len(cfg["hooks"]), 5)
        self.assertEqual(len(cfg["contextFiles"]), 2)
        self.run_install("agent-handoff", "--harness", "opencode", "--uninstall")
        cfg = json.loads((self.home / ".config/opencode/claude-hooks-bridge.json").read_text())
        self.assertEqual(len(cfg["hooks"]), 1)
        self.assertTrue((self.home / ".config/opencode/plugins/claude-hooks-bridge.js").exists())
        self.run_install("vault-bootstrap", "--harness", "opencode", "--uninstall")
        self.assertFalse((self.home / ".config/opencode/plugins/claude-hooks-bridge.js").exists())

    def test_existing_hook_and_file_are_kept(self):
        cur = self.home / ".cursor"
        cur.mkdir()
        (cur / "hooks.json").write_text(json.dumps({"version": 1, "hooks": {"stop": [{"command": "mine"}]}}))
        (cur / "commands").mkdir()
        (cur / "commands" / "ask.md").write_text("my own ask")
        self.run_install("agent-handoff", "ask", "--harness", "cursor")
        self.assertEqual(self.hooks(cur / "hooks.json")["stop"], [{"command": "mine"}])
        self.assertTrue(list((cur / "commands").glob("ask.md.bak-*")))
        self.run_install("agent-handoff", "ask", "--harness", "cursor", "--uninstall")
        self.assertEqual(json.loads((cur / "hooks.json").read_text()), {"version": 1, "hooks": {"stop": [{"command": "mine"}]}})
        self.assertEqual((cur / "commands" / "ask.md").read_text(), "my own ask")

    def test_other_adapter_is_not_doubled(self):
        plugins = self.home / ".config/opencode/plugins"
        plugins.mkdir(parents=True)
        (plugins / "claude-config.js").write_text("// other adapter")
        out = self.run_install("agent-handoff", "--harness", "opencode")
        self.assertIn("note:", out)
        self.assertFalse((self.home / ".config/opencode/claude-hooks-bridge.json").exists())

    def test_dry_run_changes_nothing(self):
        (self.home / ".cursor").mkdir()
        before = self.snapshot()
        self.run_install("all", "--dry-run", "--harness", "cursor,opencode")
        self.assertEqual(self.snapshot(), before)

    def test_all_installs_everything(self):
        (self.home / ".cursor").mkdir()
        (self.home / ".config/opencode").mkdir(parents=True)
        self.run_install("all", "--harness", "cursor,opencode")
        self.assertTrue((self.home / ".cursor/commands/ask.md").exists())
        self.assertTrue((self.home / ".config/opencode/commands/modularize.md").exists())
        self.run_install("all", "--harness", "cursor,opencode", "--uninstall")
        left = [k for k in self.snapshot() if "installed.json" not in k]
        self.assertEqual(left, [])


class CursorModeTests(unittest.TestCase):
    """The same hook scripts, called the way Cursor calls them."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lukes-cursor-"))
        self.home = self.tmp / "home"
        self.proj = self.tmp / "proj"
        self.home.mkdir()
        self.proj.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home), "APPDATA": str(self.home / "AppData"),
                    "CLAUDE_PROJECT_DIR": ""}
        self.env.pop("CLAUDE_PROJECT_DIR")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, script, *args, payload):
        return subprocess.run([sys.executable, str(REPO / script), *args], input=json.dumps(payload), capture_output=True,
                              text=True, env=self.env, cwd=self.home)

    def test_agent_handoff_cursor_flow(self):
        ah = "plugins/agent-handoff/bin/agent_handoff.py"
        r = self.call(ah, "init", "--cursor", payload={"workspace_roots": [str(self.proj)], "session_id": "s1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.proj / ".agent" / "handoff.md").exists())
        self.call(ah, "tool", "--cursor", payload={"workspace_roots": [str(self.proj)], "conversation_id": "s1",
                                                   "file_path": str(self.proj / "a.txt")})
        self.assertTrue(list((self.proj / ".agent" / ".buffer").glob("s1.jsonl")))
        r = self.call(ah, "prompt", "--cursor", payload={"workspace_roots": [str(self.proj)], "prompt": "hi"})
        self.assertEqual(json.loads(r.stdout), {"continue": True})
        (self.proj / ".agent" / "handoff.md").write_text("# Handoff\nwhere I stopped: here\n")
        r = self.call(ah, "init", "--cursor", payload={"workspace_roots": [str(self.proj)]})
        self.assertIn("where I stopped: here", json.loads(r.stdout)["additional_context"])

    def test_vault_bootstrap_cursor_prints_nothing_to_stdout(self):
        r = self.call("plugins/vault-bootstrap/bin/vault_bootstrap.py", "--cursor", payload={"workspace_roots": [str(self.proj)]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertTrue((self.proj / ".obsidian").is_dir())


if __name__ == "__main__":
    unittest.main()
