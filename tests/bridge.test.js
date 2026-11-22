// Self-check for opencode-hooks-bridge. Run: node --test tests
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const bridge = require("../plugins/opencode-hooks-bridge/opencode/claude-hooks-bridge.js");
const t = bridge._test;

test("maps OpenCode tool arguments to the Claude shape", () => {
  assert.deepStrictEqual(t.mapInput({ filePath: "a.txt", newString: "n", oldString: "o" }), { file_path: "a.txt", new_string: "n", old_string: "o" });
  assert.strictEqual(t.TOOL_MAP.shell, "Bash");
  assert.strictEqual(t.TOOL_MAP.patch, "MultiEdit");
});

test("matcher is anchored and tolerates a bad pattern", () => {
  assert.ok(t.matches({ matcher: "Edit|Write" }, "Edit"));
  assert.ok(!t.matches({ matcher: "Edit" }, "MultiEdit"));
  assert.ok(!t.matches({ matcher: "(" }, "Edit"));
  assert.ok(t.matches({}, "anything"));
});

test("only a deny decision blocks", () => {
  assert.strictEqual(t.denyReason(JSON.stringify({ hookSpecificOutput: { permissionDecision: "deny", permissionDecisionReason: "no" } })), "no");
  assert.strictEqual(t.denyReason(JSON.stringify({ hookSpecificOutput: { permissionDecision: "ask" } })), null);
  assert.strictEqual(t.denyReason("not json"), null);
  assert.strictEqual(t.denyReason(""), null);
});

test("context files are read, truncated and skipped when missing", () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "bridge-"));
  fs.writeFileSync(path.join(d, "a.md"), "x".repeat(50));
  const out = t.readContext([{ path: "a.md", max: 10 }, { path: "missing.md" }], d);
  assert.match(out, /truncated/);
  assert.doesNotMatch(out, /missing/);
  assert.strictEqual(t.readContext([], d), "");
});

test("setup wires every event and a deny hook throws", async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "bridge-"));
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "bridge-home-"));
  fs.mkdirSync(path.join(home, ".config", "opencode"), { recursive: true });
  const denyCmd = `node -e "console.log(JSON.stringify({hookSpecificOutput:{permissionDecision:'deny',permissionDecisionReason:'blocked'}}))"`;
  fs.writeFileSync(path.join(home, ".config", "opencode", "claude-hooks-bridge.json"), JSON.stringify({ hooks: [{ event: "PreToolUse", matcher: "Bash", command: denyCmd }], contextFiles: [] }));
  const prev = { HOME: process.env.HOME, USERPROFILE: process.env.USERPROFILE };
  process.env.HOME = process.env.USERPROFILE = home;
  delete require.cache[require.resolve("../plugins/opencode-hooks-bridge/opencode/claude-hooks-bridge.js")];
  const fresh = require("../plugins/opencode-hooks-bridge/opencode/claude-hooks-bridge.js");
  const hooks = {};
  const ctx = {
    location: { directory: d },
    event: { subscribe: () => (async function* () {})() },
    session: { hook: async (n, f) => { hooks["session." + n] = f; } },
    tool: { hook: async (n, f) => { hooks["tool." + n] = f; } },
  };
  const dispose = await fresh.setup(ctx);
  assert.deepStrictEqual(Object.keys(hooks).sort(), ["session.compaction", "session.context", "session.prompt", "tool.execute.after", "tool.execute.before"]);
  assert.throws(() => hooks["tool.execute.before"]({ tool: "bash", input: { command: "ls" }, sessionID: "s" }), /blocked/);
  assert.doesNotThrow(() => hooks["tool.execute.before"]({ tool: "read", input: {}, sessionID: "s" }));
  dispose();
  Object.assign(process.env, prev);
});

test("LUKES_BRIDGE=0 turns it off", async () => {
  process.env.LUKES_BRIDGE = "0";
  let called = 0;
  await bridge.setup({ location: { directory: "x" }, event: { subscribe: () => (async function* () {})() }, session: { hook: async () => { called++; } }, tool: { hook: async () => { called++; } } });
  delete process.env.LUKES_BRIDGE;
  assert.strictEqual(called, 0);
});
