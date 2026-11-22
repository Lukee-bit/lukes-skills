#!/usr/bin/env python3
"""Luke's skills installer: put one tool, several, or all of them on Claude Code, Cursor and OpenCode.

  python install.py <tool...|all> [--harness claude,cursor,opencode] [--dry-run] [--uninstall]
                                  [--source SRC] [--force]

Tools: agent-handoff, ask, modularize, vault-bootstrap, opencode-hooks-bridge.
Standard library only (Python 3.8+). Safe to re-run: nothing is added twice, any file it replaces is
kept as <file>.bak-YYYYMMDD, and --uninstall removes exactly what this installer placed.

  Claude Code  runs `claude plugin marketplace add` and `claude plugin install <tool>@lukes-skills`.
  Cursor       copies commands and skills and adds hooks to ~/.cursor/hooks.json.
  OpenCode     copies commands and skills, installs the hooks bridge and fills its config.

Environment: LUKES_SKILLS_HOME replaces the home folder (tests), CLAUDE_CONFIG_DIR the Claude folder.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent
HOME = Path(os.environ.get("LUKES_SKILLS_HOME") or Path.home())
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME / ".claude")
CURSOR_DIR = HOME / ".cursor"
OPENCODE_DIR = HOME / ".config" / "opencode"
STORE = HOME / ".local" / "share" / "lukes-skills"
MANIFEST = STORE / "installed.json"
STAMP = time.strftime("%Y%m%d")
MARKETPLACE = "lukes-skills"
DEFAULT_SOURCE = "Lukee-bit/lukes-skills"

TOOLS = ["agent-handoff", "ask", "modularize", "vault-bootstrap", "opencode-hooks-bridge"]
HARNESSES = ["claude", "cursor", "opencode"]
BRIDGE_CONFIG = OPENCODE_DIR / "claude-hooks-bridge.json"
BRIDGE_PLUGIN = OPENCODE_DIR / "plugins" / "claude-hooks-bridge.js"
CONTEXT_FILES = [{"path": ".agent/handoff.md", "max": 6000}, {"path": ".agent/memory/MEMORY.md", "max": 2500}]


def dump(p: Path, data):
    """Write JSON with LF line endings on every platform."""
    p.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))


class Installer:
    def __init__(self, dry, force, source):
        self.dry, self.force, self.source = dry, force, source
        self.m = {"files": {}, "hooks": [], "bridge": [], "created": []}
        if MANIFEST.exists():
            try:
                self.m.update(json.loads(MANIFEST.read_text(encoding="utf-8")))
            except ValueError:
                pass
        self.backed = set()
        self.notes = []

    # ---- bookkeeping -------------------------------------------------
    def say(self, msg):
        print(("[dry-run] " if self.dry else "") + msg)

    def save(self):
        if self.dry:
            return
        if not any(self.m[k] for k in ("files", "hooks", "bridge", "created")):
            MANIFEST.unlink(missing_ok=True)
            return
        STORE.mkdir(parents=True, exist_ok=True)
        dump(MANIFEST, self.m)

    def backup(self, p: Path):
        """Keep the first version of a file we are about to change: <file>.bak-YYYYMMDD."""
        b = p.with_name(p.name + ".bak-" + STAMP)
        if p.exists() and not b.exists() and p not in self.backed:
            if not self.dry:
                shutil.copy2(p, b)
            self.backed.add(p)
            return b.name
        return None

    # ---- files -------------------------------------------------------
    def put(self, dst: Path, data: bytes, owner: str):
        key = str(dst)
        ent = self.m["files"].get(key)
        if dst.exists() and dst.read_bytes() == data:
            if ent and owner not in ent["owners"]:
                ent["owners"].append(owner)
            return
        bak = self.backup(dst) if dst.exists() else None
        self.say(("update " if dst.exists() else "write  ") + str(dst))
        if not self.dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        if ent:
            if owner not in ent["owners"]:
                ent["owners"].append(owner)
        else:
            self.m["files"][key] = {"owners": [owner], "backup": bak}

    def put_file(self, src: Path, dst: Path, owner: str, render=None):
        data = src.read_bytes()
        if render:
            data = render(data.decode("utf-8")).encode("utf-8")
        self.put(dst, data, owner)

    def put_tree(self, src: Path, dst: Path, owner: str):
        for f in sorted(p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            self.put_file(f, dst / f.relative_to(src), owner)

    def drop_owner(self, owner: str):
        for key, ent in list(self.m["files"].items()):
            if owner not in ent["owners"]:
                continue
            ent["owners"].remove(owner)
            if ent["owners"]:
                continue
            p = Path(key)
            self.say("remove " + key)
            if not self.dry:
                try:
                    p.unlink()
                except OSError:
                    pass
                if ent.get("backup"):
                    b = p.with_name(ent["backup"])
                    if b.exists():
                        b.replace(p)
                for parent in [p.parent, p.parent.parent]:
                    try:
                        if parent.name in {t for t in TOOLS} or parent == STORE:
                            parent.rmdir()
                    except OSError:
                        pass
            del self.m["files"][key]

    # ---- JSON config files -------------------------------------------
    def load_json(self, p: Path, default):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def write_json(self, p: Path, data, owner):
        existed = p.exists()
        if existed and str(p) not in self.m["created"]:
            self.backup(p)
        elif str(p) not in self.m["created"]:
            self.m["created"].append(str(p))
        if not self.dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            dump(p, data)

    # ---- helpers -----------------------------------------------------
    def py(self):
        return f'"{sys.executable}"'

    def script_cmd(self, tool):
        s = {"agent-handoff": "agent_handoff.py", "vault-bootstrap": "vault_bootstrap.py"}[tool]
        return f'{self.py()} "{(STORE / tool / s).as_posix()}"'

    def command_render(self, tool):
        """Commands written for Claude Code name the plugin folder; point them at the installed script instead."""
        def r(text):
            text = re.sub(r"(?m)^allowed-tools:.*\n", "", text)
            if tool == "agent-handoff":
                text = text.replace("${CLAUDE_PLUGIN_ROOT}/bin/agent-handoff", self.script_cmd(tool))
            return text
        return r

    def install_store(self, tool, owner):
        """Copy the tool's scripts to a stable place that hooks can call."""
        src = REPO / "plugins" / tool / "bin"
        names = {"agent-handoff": ["agent_handoff.py"], "vault-bootstrap": ["vault_bootstrap.py", "obsidian_trust.py"]}[tool]
        for n in names:
            self.put_file(src / n, STORE / tool / n, owner)

    # ---- Cursor hooks ------------------------------------------------
    def cursor_hooks(self, owner, entries):
        p = CURSOR_DIR / "hooks.json"
        data = self.load_json(p, {"version": 1, "hooks": {}})
        hooks = data.setdefault("hooks", {})
        changed = False
        for event, cmd, timeout in entries:
            arr = hooks.setdefault(event, [])
            if any(h.get("command") == cmd for h in arr):
                continue
            foreign = [h for h in arr if "agent-handoff" in h.get("command", "") or "agent_handoff" in h.get("command", "")]
            if foreign and "agent_handoff" in cmd and not self.force:
                self.notes.append(f"Cursor already has an agent-handoff hook for {event}; left alone (use --force to add anyway).")
                continue
            arr.append({"command": cmd, "timeout": timeout})
            self.m["hooks"].append({"file": str(p), "event": event, "command": cmd, "owner": owner})
            self.say(f"hook   {event} -> {cmd}")
            changed = True
        if changed:
            self.write_json(p, data, owner)

    def drop_cursor_hooks(self, owner):
        mine = [h for h in self.m["hooks"] if h["owner"] == owner]
        for file in {h["file"] for h in mine}:
            p = Path(file)
            data = self.load_json(p, None)
            if data is None:
                continue
            for h in mine:
                if h["file"] != file:
                    continue
                arr = data.get("hooks", {}).get(h["event"], [])
                data["hooks"][h["event"]] = [x for x in arr if x.get("command") != h["command"]]
                if not data["hooks"][h["event"]]:
                    del data["hooks"][h["event"]]
                self.say(f"unhook {h['event']} -> {h['command']}")
            if not self.dry:
                if not data.get("hooks") and file in self.m["created"]:
                    p.unlink()
                    self.m["created"].remove(file)
                else:
                    dump(p, data)
        self.m["hooks"] = [h for h in self.m["hooks"] if h["owner"] != owner]

    # ---- OpenCode bridge ---------------------------------------------
    def bridge_hooks(self, owner, entries, context=False):
        if (OPENCODE_DIR / "plugins" / "claude-config.js").exists() and not self.force:
            self.notes.append("OpenCode already runs these hooks through claude-config's adapter; bridge hooks skipped (use --force to add anyway).")
            return
        self.install_bridge(owner)
        data = self.load_json(BRIDGE_CONFIG, {"hooks": [], "contextFiles": []})
        data.setdefault("hooks", [])
        data.setdefault("contextFiles", [])
        changed = False
        for e in entries:
            if any(h.get("command") == e["command"] and h.get("event") == e["event"] for h in data["hooks"]):
                continue
            data["hooks"].append(e)
            self.m["bridge"].append({"event": e["event"], "command": e["command"], "owner": owner})
            self.say(f"bridge {e['event']} -> {e['command']}")
            changed = True
        if context:
            for c in CONTEXT_FILES:
                if not any(x.get("path") == c["path"] for x in data["contextFiles"]):
                    data["contextFiles"].append(c)
                    self.m["bridge"].append({"context": c["path"], "owner": owner})
                    changed = True
        if changed:
            self.write_json(BRIDGE_CONFIG, data, owner)

    def install_bridge(self, owner):
        self.put_file(REPO / "plugins/opencode-hooks-bridge/opencode/claude-hooks-bridge.js", BRIDGE_PLUGIN, owner)

    def drop_bridge_hooks(self, owner):
        mine = [b for b in self.m["bridge"] if b["owner"] == owner]
        data = self.load_json(BRIDGE_CONFIG, None)
        if data is not None and mine:
            for b in mine:
                if "command" in b:
                    data["hooks"] = [h for h in data.get("hooks", []) if not (h.get("command") == b["command"] and h.get("event") == b["event"])]
                    self.say(f"unbridge {b['event']} -> {b['command']}")
                else:
                    others = [x for x in self.m["bridge"] if x is not b and x.get("context") == b["context"]]
                    if not others:
                        data["contextFiles"] = [c for c in data.get("contextFiles", []) if c.get("path") != b["context"]]
            if not self.dry:
                if not data.get("hooks") and BRIDGE_CONFIG.as_posix() in [Path(c).as_posix() for c in self.m["created"]]:
                    BRIDGE_CONFIG.unlink()
                    self.m["created"] = [c for c in self.m["created"] if Path(c) != BRIDGE_CONFIG]
                else:
                    dump(BRIDGE_CONFIG, data)
        self.m["bridge"] = [b for b in self.m["bridge"] if b["owner"] != owner]

    # ---- Claude Code -------------------------------------------------
    def claude(self, tool, uninstall):
        if tool == "opencode-hooks-bridge":
            self.notes.append("opencode-hooks-bridge is an OpenCode plugin; there is nothing to install on Claude Code.")
            return
        steps = ([["plugin", "uninstall", f"{tool}@{MARKETPLACE}"]] if uninstall else
                 [["plugin", "marketplace", "add", self.source], ["plugin", "install", f"{tool}@{MARKETPLACE}"]])
        exe = shutil.which("claude")
        for s in steps:
            line = "claude " + " ".join(s)
            if not exe or self.dry:
                self.say(("run: " if exe else "claude not found; run it yourself: ") + line)
                continue
            r = subprocess.run([exe] + s, capture_output=True, text=True, env={**os.environ, "CLAUDE_CONFIG_DIR": str(CLAUDE_DIR)})
            out = (r.stdout + r.stderr).strip().splitlines()
            self.say(line + (" -> ok" if r.returncode == 0 else f" -> exit {r.returncode}: {out[-1] if out else ''}"))

    # ---- per tool ----------------------------------------------------
    def cursor(self, tool, uninstall):
        owner = f"{tool}:cursor"
        if uninstall:
            self.drop_cursor_hooks(owner)
            self.drop_owner(owner)
            return
        if tool == "opencode-hooks-bridge":
            self.notes.append("opencode-hooks-bridge is an OpenCode plugin; there is nothing to install in Cursor.")
            return
        r = self.command_render(tool)
        cmds = CURSOR_DIR / "commands"
        if tool == "agent-handoff":
            self.install_store(tool, owner)
            self.put_file(REPO / "plugins/agent-handoff/commands/save-handoff.md", cmds / "save-handoff.md", owner, r)
            self.put_tree(REPO / "plugins/agent-handoff/skills/agent-handoff", CURSOR_DIR / "skills" / "agent-handoff", owner)
            c = self.script_cmd(tool)
            self.cursor_hooks(owner, [("sessionStart", f"{c} init --cursor", 30), ("beforeSubmitPrompt", f"{c} prompt --cursor", 5),
                                      ("afterFileEdit", f"{c} tool --cursor", 5), ("sessionEnd", f"{c} end --cursor", 30)])
        elif tool == "vault-bootstrap":
            self.install_store(tool, owner)
            self.cursor_hooks(owner, [("sessionStart", f"{self.script_cmd(tool)} --cursor", 30)])
        else:
            self.put_file(REPO / "plugins" / tool / "commands" / f"{tool}.md", cmds / f"{tool}.md", owner, r)

    def opencode(self, tool, uninstall):
        owner = f"{tool}:opencode"
        if uninstall:
            self.drop_bridge_hooks(owner)
            self.drop_owner(owner)
            return
        r = self.command_render(tool)
        cmds = OPENCODE_DIR / "commands"
        if tool == "opencode-hooks-bridge":
            self.install_bridge(owner)
        elif tool == "agent-handoff":
            self.install_store(tool, owner)
            self.put_file(REPO / "plugins/agent-handoff/commands/save-handoff.md", cmds / "save-handoff.md", owner, r)
            self.put_tree(REPO / "plugins/agent-handoff/skills/agent-handoff", OPENCODE_DIR / "skills" / "agent-handoff", owner)
            c = self.script_cmd(tool)
            self.bridge_hooks(owner, [{"event": "SessionStart", "command": f"{c} init"},
                                      {"event": "UserPromptSubmit", "command": f"{c} prompt", "timeout": 5000},
                                      {"event": "PostToolUse", "matcher": "Edit|Write|MultiEdit", "command": f"{c} tool", "timeout": 5000},
                                      {"event": "SessionEnd", "command": f"{c} end"}], context=True)
        elif tool == "vault-bootstrap":
            self.install_store(tool, owner)
            self.bridge_hooks(owner, [{"event": "SessionStart", "command": self.script_cmd(tool)}])
        else:
            self.put_file(REPO / "plugins" / tool / "opencode" / "commands" / f"{tool}.md", cmds / f"{tool}.md", owner)

    def run(self, tool, harness, uninstall):
        self.say(f"{'uninstall' if uninstall else 'install'} {tool} on {harness}")
        if harness == "claude":
            self.claude(tool, uninstall)
        elif harness == "cursor":
            self.cursor(tool, uninstall)
        else:
            self.opencode(tool, uninstall)


def detect():
    found = []
    if shutil.which("claude") or CLAUDE_DIR.exists():
        found.append("claude")
    if CURSOR_DIR.exists():
        found.append("cursor")
    if OPENCODE_DIR.exists():
        found.append("opencode")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description="Install Luke's skills on Claude Code, Cursor and OpenCode.")
    ap.add_argument("tools", nargs="+", help="tool names, or 'all'")
    ap.add_argument("--harness", help="comma list of claude,cursor,opencode (default: the ones found on this machine)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--uninstall", action="store_true", help="remove what this installer placed")
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="Claude marketplace source (GitHub owner/repo or a local path)")
    ap.add_argument("--force", action="store_true", help="add hooks even if another setup already provides them")
    a = ap.parse_args(argv)
    tools = TOOLS if "all" in a.tools else a.tools
    bad = [t for t in tools if t not in TOOLS]
    if bad:
        ap.error("unknown tool: " + ", ".join(bad) + " (known: " + ", ".join(TOOLS) + ")")
    harnesses = [h.strip() for h in a.harness.split(",")] if a.harness else detect()
    bad = [h for h in harnesses if h not in HARNESSES]
    if bad:
        ap.error("unknown harness: " + ", ".join(bad))
    if not harnesses:
        print("No Claude Code, Cursor or OpenCode found. Use --harness to choose one.")
        return 1
    inst = Installer(a.dry_run, a.force, a.source)
    for h in harnesses:
        for t in tools:
            inst.run(t, h, a.uninstall)
    inst.save()
    for n in dict.fromkeys(inst.notes):
        print("note: " + n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
