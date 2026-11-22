---
name: no-third-party-code
description: Luke's skills must contain only original work. No third-party code, text or branding, and no required third-party tool.
metadata:
  type: feedback
---

Every file in this repo is written from scratch. Do not copy code, prompts or documentation from other projects, and do not name another product as a requirement.

**Why:** the repo is Luke's intellectual property under an all-rights-reserved license; third-party material would bring other people's copyright into it.

**How to apply:** a link to another tool is allowed only as an optional setting that is off by default (agent-handoff's `integrations.*`, vault-bootstrap's `integrations.localRestApi`). Before adding a tool, check that nothing in it comes from upstream, and keep its default output dependency-free.
