#!/usr/bin/env python3
"""vault-bootstrap: make a project folder an Obsidian vault (part of Luke's skills).

  vault-bootstrap [init] [DIR]   create .obsidian/ starter files, Home.md and Notes.md, and register the vault
                                 with the Obsidian app. Idempotent, never overwrites, skips non-project folders.
  vault-bootstrap trust DIR      Windows: turn Obsidian's Restricted mode off for DIR (Obsidian must be closed)

Needs only Python 3.8+. Opt out for one project: touch DIR/.vault-bootstrap-off

Config (later layers override earlier ones): ~/.config/vault-bootstrap/config.json, then environment variables.
  {"integrations": {"localRestApi": false},
   "localRestApi": {"pluginDir": "", "keyFile": "", "trust": true}}
With localRestApi on, the community plugin folder `pluginDir/obsidian-local-rest-api` is copied into the vault,
the plugin is enabled, its data.json gets an API key read from `keyFile` (created, mode 0600, if missing) and, on
Windows, Restricted mode is turned off for the vault. Environment: VAULT_BOOTSTRAP_LOCAL_REST_API=1.
"""
import copy, hashlib, json, os, re, secrets, subprocess, sys, time
from pathlib import Path

HOME = Path.home()
DEFAULTS = {
    "integrations": {"localRestApi": False},
    "localRestApi": {"pluginDir": "", "keyFile": "", "trust": True},
}
PLUGIN_ID = "obsidian-local-rest-api"
CORE_PLUGINS = ["file-explorer", "global-search", "graph", "backlink", "outgoing-link", "tag-pane", "properties",
                "outline", "bookmarks", "page-preview"]
GRAPH = {"showTags": True, "showAttachments": False, "showOrphans": True, "colorGroups": []}
MARKERS = (".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "CLAUDE.md", "AGENTS.md", "Makefile", "README.md")


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config() -> dict:
    c = copy.deepcopy(DEFAULTS)
    try:
        v = json.loads((HOME / ".config" / "vault-bootstrap" / "config.json").read_text(encoding="utf-8"))
        if isinstance(v, dict):
            _merge(c, v)
    except Exception:
        pass
    e = os.environ.get("VAULT_BOOTSTRAP_LOCAL_REST_API")
    if e is not None:
        c["integrations"]["localRestApi"] = e.strip().lower() in ("1", "true", "yes", "on")
    return c


def eligible(d: Path) -> bool:
    """Real project folders only: not home, system, app-data or document-library folders."""
    if (d / ".vault-bootstrap-off").exists():
        return False
    s, h = str(d), str(HOME.resolve())
    if os.name == "nt":
        s, h = s.replace("\\", "/").lower(), h.replace("\\", "/").lower()
        if re.match(r"^[a-z]:/?$", s) or re.match(r"^[a-z]:/(windows|program files|programdata)", s):
            return False
        if any(s.startswith(f"{h}/{p}") for p in ("appdata", "scoop", ".claude", ".claude-tools", ".cache", ".local", ".npm")):
            return False
        if s in (h, f"{h}/desktop", f"{h}/documents", f"{h}/downloads", f"{h}/projects"):
            return False
    if s in (h, "/") or s.startswith(("/tmp", "/private/tmp", "/private/var", "/var/", "/usr", "/etc", "/System", "/Library", "/Applications")):
        return False
    for p in ("Library", ".claude", ".claude-tools", ".cache", ".local", ".npm"):
        if s.startswith(f"{h}/{p}"):
            return False
    if s in (f"{h}/Desktop", f"{h}/Documents", f"{h}/Downloads", f"{h}/Projects"):
        return False
    if (d / ".obsidian" / "app.json").is_file():
        return False  # already a vault
    try:
        n = len(os.listdir(d))
    except OSError:
        return False
    return n <= 3 or any((d / m).exists() for m in MARKERS)


def write_if_missing(p: Path, text: str):
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def obsidian_json() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or HOME / "AppData" / "Roaming") / "obsidian" / "obsidian.json"
    if sys.platform == "darwin":
        return HOME / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    return HOME / ".config" / "obsidian" / "obsidian.json"


def register(d: Path):
    """List the vault in the Obsidian app's vault switcher."""
    oc, path = obsidian_json(), str(d)
    try:
        c = json.loads(oc.read_text(encoding="utf-8"))
    except Exception:
        c = {}
    v = c.setdefault("vaults", {})
    if not any(x.get("path") == path for x in v.values()):
        v[hashlib.sha1(path.encode()).hexdigest()[:16]] = {"path": path, "ts": int(time.time() * 1000)}
        oc.parent.mkdir(parents=True, exist_ok=True)
        oc.write_text(json.dumps(c), encoding="utf-8")


def rest_api_key(key_file: Path) -> str:
    if not key_file.exists():
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(f"OBSIDIAN_API_KEY={secrets.token_hex(32)}\n", encoding="utf-8")
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    m = re.search(r"^OBSIDIAN_API_KEY=(.*)$", key_file.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else ""


def trust(d: Path, quiet=False) -> int:
    helper = Path(__file__).resolve().with_name("obsidian_trust.py")
    r = subprocess.run([sys.executable, str(helper), str(d)], capture_output=True, text=True)
    if not quiet and (r.stdout or r.stderr):
        print((r.stdout or r.stderr).strip())
    return r.returncode


def init(d: Path):
    if not eligible(d):
        return
    cfg = load_config()
    rest = cfg["integrations"]["localRestApi"]
    ob = d / ".obsidian"
    ob.mkdir(parents=True, exist_ok=True)
    plugins = []
    if rest:
        rc = cfg["localRestApi"]
        src = Path(os.path.expanduser(rc["pluginDir"])) / PLUGIN_ID if rc.get("pluginDir") else None
        dst = ob / "plugins" / PLUGIN_ID
        (ob / "plugins").mkdir(exist_ok=True)
        if src and src.is_dir() and not dst.exists():
            import shutil
            shutil.copytree(src, dst)
        plugins = [PLUGIN_ID]
    write_if_missing(ob / "app.json", "{}\n")
    write_if_missing(ob / "community-plugins.json", json.dumps(plugins) + "\n")
    write_if_missing(ob / "core-plugins.json", json.dumps(CORE_PLUGINS) + "\n")
    write_if_missing(ob / "graph.json", json.dumps(GRAPH) + "\n")
    if rest and cfg["localRestApi"].get("keyFile"):
        key = rest_api_key(Path(os.path.expanduser(cfg["localRestApi"]["keyFile"])))
        write_if_missing(ob / "plugins" / PLUGIN_ID / "data.json",
                         json.dumps({"apiKey": key, "enableInsecureServer": True, "insecurePort": 27123, "port": 27124}) + "\n")
    gi = d / ".gitignore"
    if (d / ".git").is_dir():
        cur = gi.read_text(encoding="utf-8") if gi.exists() else ""
        if not re.search(r"^\.obsidian/plugins", cur, re.M):
            gi.write_text(cur + "\n# obsidian vault\n.obsidian/plugins/\n.obsidian/workspace*.json\n", encoding="utf-8")
    write_if_missing(d / "Home.md", f"# {d.name}\n\nProject vault. Created {time.strftime('%Y-%m-%d')} by vault-bootstrap.\n\n- [[Notes]]\n")
    write_if_missing(d / "Notes.md", "# Notes\n\nBack to [[Home]].\n")
    register(d)
    if rest and os.name == "nt" and cfg["localRestApi"].get("trust", True):
        trust(d)
    print(f"vault-bootstrap: created Obsidian vault at {d}")


def main():
    cursor = "--cursor" in sys.argv  # Cursor hook mode: project from the JSON payload, JSON-only stdout
    a = [x for x in sys.argv[1:] if x != "--cursor"]
    cmd = a.pop(0) if a and a[0] in ("init", "trust") else "init"
    d = a[0] if a else os.environ.get("CLAUDE_PROJECT_DIR")
    if not d and cursor:
        try:
            d = (json.load(sys.stdin).get("workspace_roots") or [None])[0]
        except Exception:
            d = None
    if cursor:
        sys.stdout = sys.stderr
    d = Path(d or os.getcwd())
    try:
        d = d.resolve()
        if not d.is_dir():
            return 0
        if cmd == "trust":
            return trust(d)
        init(d)
    except SystemExit:
        raise
    except Exception as e:  # a hook must never break the session
        print(f"vault-bootstrap: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
