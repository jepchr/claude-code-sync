---
name: sync-update
description: Update the cross-machine Claude Code wiki. Reads environment snapshots from all machines, compiles wiki articles, compares environments, and generates improvement suggestions.
---

# Cross-Machine Sync Update

You are maintaining a knowledge base about Claude Code environments across multiple machines. Raw snapshots are compiled into a wiki that gets smarter over time.

## Location

The sync folder path varies by setup. Check for it at the path configured in the check-sync.sh hook, or ask the user.

## Process

### Phase 1: Read Current State

1. Read all `raw/*/latest.md` snapshot files
2. Read `wiki/INDEX.md`
3. Read `suggestions/pending.md`, `suggestions/adopted.md`, `suggestions/deferred.md`

If only one machine snapshot exists, compile what you have.

### Phase 2: Compile Wiki Articles

Create or update these wiki articles based on the snapshots:

1. **wiki/skills-inventory.md** — Skills across all machines. Flag skills that exist on one machine but not others.
2. **wiki/hooks-and-automation.md** — Hook patterns and their purposes. Note which machines have which hooks.
3. **wiki/settings-decisions.md** — Key settings and reasoning. Note differences between machines.
4. **wiki/mcp-ecosystem.md** — MCP servers on each machine and what they enable. No credentials.
5. **wiki/plugins-and-tools.md** — Plugins with versions, custom commands, scripts. Flag version mismatches.
6. **wiki/workflow-patterns.md** — CLAUDE.md conventions and workflow rules.
7. **wiki/improvements-log.md** — History of cross-pollinated improvements.

Article guidelines:
- Focus on the *why* behind configurations, not just listing them
- Note which machine each item comes from
- Cross-reference between articles

### Phase 3: Compare and Generate Suggestions

**Auto-adopt (just do it):**
- Skills on one machine but not another that are clearly useful
- Plugin version mismatches (suggest updating the older one)
- Non-conflicting CLAUDE.md additions

**Surface (FYI):**
- Different MCP servers (expected for different contexts)
- Minor settings differences

**Ask (add to pending.md):**
- Conflicting CLAUDE.md rules
- Ambiguous settings differences
- Changes requiring credentials

### Phase 4: Update Tracking

1. Update `wiki/INDEX.md` with article list and last-updated dates
2. Update suggestion files
3. Update quick stats

### Phase 5: Health Check

Write findings to `health/latest.md`:
- Stale skills or plugins
- Version mismatches
- Hooks referencing missing scripts
- Suggestions pending too long

### Phase 6: Report

Brief summary (3-5 lines): articles updated, suggestions generated, health warnings.
