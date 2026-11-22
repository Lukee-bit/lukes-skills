"use strict";
/**
 * claude-hooks-bridge for OpenCode V2 (part of Luke's skills).
 *
 * Runs command-line hooks written for the Claude Code hook contract (JSON on stdin, optional JSON
 * decision on stdout) when the matching OpenCode event fires. Copy this file to
 * ~/.config/opencode/plugins/ (OpenCode loads loose .js files there).
 *
 *   session.created      -> SessionStart hooks        (background)
 *   session.deleted      -> SessionEnd hooks          (background)
 *   session "prompt"     -> UserPromptSubmit hooks    (stdout queued, added to the next request)
 *   session "context"    -> adds contextFiles and the queued text to the system prompt
 *   session "compaction" -> PreCompact hooks          (background)
 *   tool execute.before  -> PreToolUse hooks          (a {"permissionDecision":"deny"} answer blocks the call)
 *   tool execute.after   -> PostToolUse hooks         (file-editing tools only)
 *
 * Config: ~/.config/opencode/claude-hooks-bridge.json (or the file named by LUKES_BRIDGE_CONFIG)
 *   { "hooks": [ { "event": "PostToolUse", "matcher": "Edit|Write", "command": "my-hook arg", "timeout": 5000 } ],
 *     "contextFiles": [ { "path": ".agent/handoff.md", "max": 6000 } ] }
 * Without a config file the bridge uses the `agent-handoff` tool of Luke's skills when it is installed.
 * Every failure is ignored (fail open). Turn the bridge off with LUKES_BRIDGE=0.
 */
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const HOME = os.homedir();
const CONFIG = path.join(HOME, ".config", "opencode", "claude-hooks-bridge.json");

// OpenCode tool id -> Claude tool name (V2 renamed bash->shell and apply_patch->patch; accept both).
const TOOL_MAP = {
  bash: "Bash", shell: "Bash", read: "Read", grep: "Grep", glob: "Glob", write: "Write", edit: "Edit",
  apply_patch: "MultiEdit", patch: "MultiEdit", multi_edit: "MultiEdit",
  webfetch: "WebFetch", web_search: "WebSearch", websearch: "WebSearch", task: "Task", subagent: "Task",
};
const EDIT_TOOLS = new Set(["write", "edit", "apply_patch", "patch", "multi_edit"]);

// OpenCode arguments -> Claude tool_input.
function mapInput(input) {
  const out = {};
  if (!input || typeof input !== "object") return out;
  const file = input.filePath || input.file_path || input.path || input.fileName;
  if (file) out.file_path = file;
  for (const [from, to] of [["content", "content"], ["new_string", "new_string"], ["newString", "new_string"],
    ["old_string", "old_string"], ["oldString", "old_string"], ["command", "command"], ["pattern", "pattern"],
    ["prompt", "prompt"], ["description", "description"], ["url", "url"], ["query", "query"]]) {
    if (input[from] !== undefined) out[to] = input[from];
  }
  return out;
}

function onPath(name) {
  const exts = process.platform === "win32" ? ["", ".exe", ".cmd", ".bat"] : [""];
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    for (const e of exts) if (dir && fs.existsSync(path.join(dir, name + e))) return path.join(dir, name + e);
  }
  return null;
}

// Default hooks: the agent-handoff tool, if it is installed.
function defaultConfig() {
  const exe = onPath("agent-handoff") || [path.join(HOME, ".claude-tools", "bin", "agent-handoff")].find((p) => fs.existsSync(p));
  if (!exe) return { hooks: [], contextFiles: [] };
  const q = `"${exe}"`;
  return {
    hooks: [
      { event: "SessionStart", command: `${q} init` },
      { event: "UserPromptSubmit", command: `${q} prompt`, timeout: 5000 },
      { event: "PostToolUse", matcher: "Edit|Write|MultiEdit", command: `${q} tool`, timeout: 5000 },
      { event: "SessionEnd", command: `${q} end` },
    ],
    contextFiles: [{ path: ".agent/handoff.md", max: 6000 }, { path: ".agent/memory/MEMORY.md", max: 2500 }],
  };
}

function loadConfig() {
  try {
    const c = JSON.parse(fs.readFileSync(process.env.LUKES_BRIDGE_CONFIG || CONFIG, "utf8"));
    return { hooks: Array.isArray(c.hooks) ? c.hooks : [], contextFiles: Array.isArray(c.contextFiles) ? c.contextFiles : [] };
  } catch {
    return defaultConfig();
  }
}

function matches(hook, claudeTool) {
  if (!hook.matcher) return true;
  try { return new RegExp(`^(?:${hook.matcher})$`).test(claudeTool || ""); } catch { return false; }
}

function run(hook, payload, cwd, blocking) {
  const env = { ...process.env, CLAUDE_PROJECT_DIR: cwd || "" };
  try {
    if (blocking) {
      const r = spawnSync(hook.command, { shell: true, input: JSON.stringify(payload), encoding: "utf8", cwd, env,
        timeout: hook.timeout || 10000, windowsHide: true, maxBuffer: 1024 * 1024 });
      return r.stdout || "";
    }
    const child = spawn(hook.command, { shell: true, cwd, env, windowsHide: true, stdio: ["pipe", "ignore", "ignore"] });
    child.on("error", () => {});
    if (child.stdin) { child.stdin.on("error", () => {}); child.stdin.write(JSON.stringify(payload)); child.stdin.end(); }
  } catch {}
  return "";
}

function readContext(files, dir) {
  const parts = [];
  for (const f of files) {
    try {
      const text = fs.readFileSync(path.join(dir, f.path), "utf8");
      const max = f.max || 6000;
      parts.push(text.length > max ? `### ${f.path} (truncated, read the full file)\n${text.slice(0, max)}\n...` : `### ${f.path}\n${text}`);
    } catch {}
  }
  return parts.length ? "Project context files follow.\n\n" + parts.join("\n\n") : "";
}

// Pull a Claude-contract deny decision out of a hook's stdout.
function denyReason(stdout) {
  try {
    const d = JSON.parse(stdout).hookSpecificOutput;
    if (d && d.permissionDecision === "deny") return d.permissionDecisionReason || "blocked by a hook";
  } catch {}
  return null;
}

async function setup(ctx) {
  if (process.env.LUKES_BRIDGE === "0") return () => {};
  const dir = typeof ctx.location?.directory === "string" && ctx.location.directory ? ctx.location.directory : undefined;
  const cfg = loadConfig();
  const byEvent = (e, tool) => cfg.hooks.filter((h) => h.event === e && matches(h, tool));
  const pending = new Map(); // sessionID -> queued prompt-hook output
  const ended = new Set();
  const started = new Set();
  // SessionStart runs once per session: on the created event, or on the first prompt if that event was missed.
  const start = (sessionID) => {
    if (started.has(sessionID)) return;
    started.add(sessionID);
    for (const h of byEvent("SessionStart")) run(h, { session_id: sessionID, cwd: dir, source: "startup" }, dir, false);
  };
  const end = (sessionID) => {
    if (ended.has(sessionID)) return;
    ended.add(sessionID);
    for (const h of byEvent("SessionEnd")) run(h, { session_id: sessionID, cwd: dir, reason: "clear" }, dir, false);
  };
  const sameLocation = (e) => !e.location || (e.location.directory === ctx.location.directory && e.location.workspaceID === ctx.location.workspaceID);

  const controller = new AbortController();
  (async () => {
    try {
      for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
        try {
          if (!sameLocation(event)) continue;
          const sessionID = event.data?.sessionID;
          if (typeof sessionID !== "string" || !sessionID) continue;
          if (event.type === "session.created") start(sessionID);
          if (event.type === "session.deleted") { end(sessionID); pending.delete(sessionID); }
        } catch {}
      }
    } catch {}
  })();

  await ctx.session.hook("prompt", (event) => {
    start(event.sessionID);
    for (const h of byEvent("UserPromptSubmit")) {
      const out = run(h, { session_id: event.sessionID, cwd: dir }, dir, true).trim();
      if (out) pending.set(event.sessionID, out.slice(0, 2000));
    }
  });
  await ctx.session.hook("context", (event) => {
    const text = readContext(cfg.contextFiles, dir || "");
    if (text) event.system.push({ type: "text", text });
    const hint = pending.get(event.sessionID);
    if (hint) { event.system.push({ type: "text", text: hint }); pending.delete(event.sessionID); }
  });
  await ctx.session.hook("compaction", (event) => {
    for (const h of byEvent("PreCompact")) run(h, { session_id: event.sessionID, cwd: dir }, dir, false);
  });
  await ctx.tool.hook("execute.before", (event) => {
    const tool = TOOL_MAP[String(event.tool || "").toLowerCase()];
    if (!tool) return;
    const payload = { tool_name: tool, tool_input: mapInput(event.input), session_id: event.sessionID, cwd: dir };
    for (const h of byEvent("PreToolUse", tool)) {
      const reason = denyReason(run(h, payload, dir, true));
      if (reason) throw new Error(reason);
    }
  });
  await ctx.tool.hook("execute.after", (event) => {
    if (event.status !== "completed") return;
    const key = String(event.tool || "").toLowerCase();
    if (!EDIT_TOOLS.has(key)) return;
    const payload = { session_id: event.sessionID, tool_name: TOOL_MAP[key], tool_input: mapInput(event.input), cwd: dir };
    for (const h of byEvent("PostToolUse", TOOL_MAP[key])) run(h, payload, dir, true);
  });

  return () => {
    controller.abort();
    for (const id of started) end(id);
    pending.clear();
  };
}

module.exports = { id: "claude-hooks-bridge", setup, _test: { mapInput, matches, denyReason, readContext, loadConfig, TOOL_MAP } };
