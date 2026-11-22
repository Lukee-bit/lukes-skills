"""Self-check for vault-bootstrap. Run: python -m unittest discover -s tests -v"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "plugins" / "vault-bootstrap" / "bin"
SCRIPT = BIN / "vault_bootstrap.py"


class VaultBootstrap(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=".vb-test-", dir=Path.home()))
        self.home = self.root / "home"
        self.proj = self.home / "proj"
        self.proj.mkdir(parents=True)
        (self.proj / "README.md").write_text("x\n")
        (self.proj / ".git").mkdir()
        self.env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home),
                    "APPDATA": str(self.home / "AppData" / "Roaming")}
        self.env.pop("VAULT_BOOTSTRAP_LOCAL_REST_API", None)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_tool(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                              env=env or self.env, cwd=str(self.proj), timeout=60)

    def registry(self):
        if os.name == "nt":
            p = self.home / "AppData" / "Roaming" / "obsidian" / "obsidian.json"
        elif sys.platform == "darwin":
            p = self.home / "Library" / "Application Support" / "obsidian" / "obsidian.json"
        else:
            p = self.home / ".config" / "obsidian" / "obsidian.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_default_needs_no_plugin(self):
        r = self.run_tool(str(self.proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        ob = self.proj / ".obsidian"
        for f in ("app.json", "core-plugins.json", "graph.json", "community-plugins.json"):
            self.assertTrue((ob / f).exists(), f)
        self.assertEqual(json.loads((ob / "community-plugins.json").read_text()), [])
        self.assertFalse((ob / "plugins").exists())
        self.assertTrue((self.proj / "Home.md").exists() and (self.proj / "Notes.md").exists())
        self.assertIn(".obsidian/plugins/", (self.proj / ".gitignore").read_text())
        self.assertEqual(len(self.registry()["vaults"]), 1)

    def test_idempotent_and_registers_once(self):
        self.run_tool(str(self.proj))
        snap = {p: p.read_bytes() for p in self.proj.rglob("*") if p.is_file() and ".git" not in p.parts}
        (self.proj / ".obsidian" / "app.json").unlink()  # a second run must restore, never duplicate
        self.run_tool(str(self.proj))
        self.assertEqual(len(self.registry()["vaults"]), 1)
        self.assertEqual(snap, {p: p.read_bytes() for p in self.proj.rglob("*") if p.is_file() and ".git" not in p.parts})

    def test_existing_vault_is_left_alone(self):
        (self.proj / ".obsidian").mkdir()
        (self.proj / ".obsidian" / "app.json").write_text('{"x":1}')
        self.run_tool(str(self.proj))
        self.assertFalse((self.proj / "Home.md").exists())

    def test_opt_out_and_home_are_skipped(self):
        (self.proj / ".vault-bootstrap-off").write_text("")
        self.run_tool(str(self.proj))
        self.assertFalse((self.proj / ".obsidian").exists())
        self.run_tool(str(self.home))
        self.assertFalse((self.home / ".obsidian").exists())

    def test_rest_api_integration(self):
        plug = self.home / "plugins" / "obsidian-local-rest-api"
        plug.mkdir(parents=True)
        (plug / "main.js").write_text("//")
        cfg = self.home / ".config" / "vault-bootstrap"
        cfg.mkdir(parents=True)
        key = self.home / "obsidian.env"
        (cfg / "config.json").write_text(json.dumps({"integrations": {"localRestApi": True},
                                                     "localRestApi": {"pluginDir": str(self.home / "plugins"), "keyFile": str(key), "trust": False}}))
        self.run_tool(str(self.proj))
        ob = self.proj / ".obsidian"
        self.assertEqual(json.loads((ob / "community-plugins.json").read_text()), ["obsidian-local-rest-api"])
        self.assertTrue((ob / "plugins" / "obsidian-local-rest-api" / "main.js").exists())
        data = json.loads((ob / "plugins" / "obsidian-local-rest-api" / "data.json").read_text())
        self.assertEqual(len(data["apiKey"]), 64)
        self.assertIn(data["apiKey"], key.read_text())

    def test_trust_helper_math(self):
        sys.path.insert(0, str(BIN))
        import obsidian_trust as t
        self.assertEqual(t.crc32c(b"123456789"), 0xE3069283)  # standard CRC-32C check value
        self.assertEqual(t.varint(300), b"\xac\x02")


if __name__ == "__main__":
    unittest.main()
