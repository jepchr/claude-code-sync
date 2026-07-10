# Mento Retirement + Machine Registry — Design

**Date:** 2026-07-10
**Status:** Approved (brainstormed with Jeppe; approach B selected)
**Applies to:** the *live* insights system in
`~/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/` plus
`~/.claude/` config on the Personal Mac. The public `claude-code-sync` repo is
out of scope except for hosting this spec (see §5).

## Context

Jeppe no longer works at Mento. The Mento laptop was offboarded 2026-06-03
(consolidation to the Personal Mac is complete and verified — see
`migration/mento-status.md` in the sync folder). A new company laptop is coming
**but nothing is known about it yet** — not the hostname, not whether personal
iCloud or Claude Code are permitted on it.

Since June the system has been comparing against a dead machine: every session
start reports stale "pending suggestions," the wiki lists Mento as active, and
the machine pair (`mento`, `personal`) is hardcoded in four places.

**Decisions made (2026-07-10):**

1. New laptop: unknown → design transport-agnostic, finish enrollment when it arrives.
2. Mento data: archive **off iCloud** (local-only) so no future work laptop syncs it.
3. Scope: full sweep — insights system + `~/CLAUDE.md` Mento section + Mento skills + stale role line.
4. Mechanics: **approach B — config-driven machine registry** (vs. minimal rename or teardown).
5. Machine labels are role-based from now on (`personal`, `work`) — never employer names.

## §1 Machine registry

New file `machines.json` at the sync-folder root — single source of truth for
what machines exist:

```json
{
  "machines": [
    { "label": "mento",
      "hostnamePatterns": ["mento"],
      "status": "retired",
      "retiredDate": "2026-06-03",
      "archive": "~/Archives/mento/" },
    { "label": "personal",
      "hostnamePatterns": ["Jeppes-MacBook-Pro"],
      "status": "active" }
  ]
}
```

**Matching rule:** case-insensitive substring match (any of a machine's
patterns) against the machine's hostname; machines are evaluated **in file
order, first match wins**;
therefore more-specific machines are listed first. (Mento's hostname
`Jeppes-MacBook-Pro-Mento.local` contains the personal pattern too — order
resolves it, same logic as the original `detect_machine()` guard.) A hostname
matching **no** entry is unenrolled: the scanner refuses to run and points at
the onboarding runbook.

**New helper `scripts/registry.py`** (small, shared by hook and scanner):
- `self_label()` — hostname → label, or error if unenrolled
- `others_active(label)` — list of other machines with `status: active`
- CLI: `registry.py --self`, `registry.py --others-active`

**Consumers updated:**

- `scripts/scan-environment.py` — replace hardcoded `detect_machine()` with
  registry lookup. Refuses to write when: the passed label ≠ the registry's
  label for this hostname (kills the May-2026 mislabel-bug class), **or** the
  matched machine is `retired` (dead hardware never writes again).
- `scripts/check-insights.sh` — `MACHINE_NAME` derived via `registry.py --self`
  (drop the hardcoded `"personal"`); the `OTHER_MACHINE` ternary becomes a loop
  over `--others-active`. Zero other active machines → skip comparison, remove
  any `.needs-update` flag, print nothing about other machines.
- `skills/insights-update/SKILL.md` — Phase 1 reads `machines.json`, then
  `raw/<label>/latest.md` for each listed machine (active → compared; retired →
  mentioned only as history). The hardcoded `raw/mento/latest.md` line goes away.
- Missing/corrupt `machines.json` → hook exits silently (same pattern as the
  existing missing-folder guard); scanner errors loudly with instructions.

## §2 Mento retirement + archive (full sweep)

Archive root: **`~/Archives/mento/`** — local disk, never inside iCloud.
iCloud→local is a cross-volume move, so every step is **copy → verify (`diff -r`
/ file counts) → delete source**. Nothing is destroyed, only relocated.

| What | From | To / action |
|---|---|---|
| Mento snapshots | `raw/mento/` | `~/Archives/mento/raw-snapshots/` |
| Consolidation archive | `migration/` | `~/Archives/mento/migration/` |
| Consolidation notes | `suggestions/consolidate-to-personal.md` | `~/Archives/mento/` |
| Improvement history (has Mento ad-account IDs) | `suggestions/adopted.md` | archived whole; fresh `adopted.md` starts with a one-line pointer to the archive so `/discover`'s dedupe trail survives |
| Deferred items | `suggestions/deferred.md` | Mento-only items → archive; generic items stay |
| Pending items | `suggestions/pending.md` | rewritten. Rule: items requiring action *on Mento* → resolved-moot; consolidation status notes → archive; the "add a hostname guard" item → resolved-fixed-by-this-work. Expected end state: **0 pending** (startup banner goes quiet) |
| Wiki (7 articles + INDEX) | `wiki/` | **not hand-edited** — after the mechanics land, run the updated `/insights-update` once and let the system recompile its own wiki solo (retired machines shown as history with archive pointer; the moot "personal snapshots are actually Mento" warning drops out). Hand-fix only what the run misses |
| "Mento Work" section | `~/CLAUDE.md` | excised to `~/Archives/mento/mento-CLAUDE-section.md`; one-line breadcrumb left: employer era ended 2026-06, archive location |
| Mento skills ×5: `mento-brand-voice`, `mento-editorial-doctrine`, `mento-internal-memo`, `ld-audience-voice`, `querying-mento-bigquery` | `~/.claude/skills/` symlinks → iCloud `skills/desktop/` (all five verified 2026-07-10 to be **Claude-Desktop-mirrored** — Claude Desktop is their source of truth, and `sync-desktop-skills.py` re-creates anything removed) | add a `.sync-ignore` exclusion list to `skills/desktop/` + a filter in `sync-desktop-skills.py` (the existing stale-symlink cleanup then removes the links); move the iCloud copies to `~/Archives/mento/skills/`. Generic writing skills (`ai-tell-editor`, `humanizer`, `editorial-style-guide`, `resume-draft-reviewer`) **stay** |
| Stale role line | `~/.claude/skills/discover/SKILL.md:69` | placeholder: "starting new role (2026-07) — update on day 1 of new job" |
| Mento wording | `~/.claude/skills/learn/SKILL.md` (description + line 192) | machine-agnostic: "all enrolled machines pick it up via the sync hook" |
| Auto-update prompt hook | `~/.claude/settings.json` | reword "both machine snapshots" → "all enrolled machines" |
| Mento hook variant | iCloud `scripts/check-insights*.sh` | if a Mento-specific variant exists, archive it |

**Manual checklist for Jeppe (agent must not touch accounts):**
- claude.ai remote connectors that look Mento-tied: Sanity (project `sd8wddo4`), Google Cloud BigQuery (mento-analytics), Zapier — disconnect or keep, your call.
- `linear-server` MCP in `~/.claude.json` — confirm whether Linear was Mento's or personal before removing.
- Optionally delete the five Mento skills inside the Claude Desktop app (they're `.sync-ignore`d, so leaving them is harmless — they just won't mirror).
- Notion "Marketing OS" access — leaves with the Mento account; nothing to do locally beyond the CLAUDE.md excision above.

## §3 Interim single-machine behavior

Until the new laptop enrolls: the scanner keeps journaling this Mac every
3 days (so the new machine's day-1 comparison is against fresh data); the hook
finds zero other active machines and skips comparison — no `.needs-update`
flags, no phantom pending banner; `/insights-update` compiles a solo wiki (it
already tolerates a single snapshot).

## §4 New-laptop onboarding kit

New runbook `onboarding/new-machine.md` in the sync folder. Written for
day 1 at the new company; also readable from the Personal Mac. Contents:

1. **Pre-flight policy check** — is Claude Code allowed on company hardware?
   Is personal iCloud Drive allowed? Record the answers before installing anything.
2. **Transport decision** — the folder is transport-agnostic. If iCloud is
   blocked, any synced folder or a private git repo works. Exactly three swap
   points reference the path: the hook command in `~/.claude/settings.json`,
   the `INSIGHTS_DIR` variable at the top of `scripts/check-insights.sh`, and
   the `Location` line in `skills/insights-update/SKILL.md`.
3. **Privacy review (both directions)** — what personal data the folder carries
   onto employer hardware (wiki mentions travel/finance MCPs, personal skills),
   and the reminder that work-machine scans will flow back into personal storage.
   Conscious decision required.
4. **Enrollment** — install Claude Code → run `hostname` → add a
   `machines.json` entry (`label: "work"`, `status: "active"`, hostname pattern,
   listed above `personal` if patterns could collide) → install the hook block
   into `~/.claude/settings.json` → run
   `python3 scripts/scan-environment.py work` → run `/insights-update`.
   The comparison output **is** the setup checklist ("work is missing skills X,
   Y, Z…"), auto-generated.
5. **Day-1 config updates** — new role/company into the `discover` skill line
   and any relevant CLAUDE.md sections.

## §5 Out of scope

- **Public `claude-code-sync` repo backport** (registry pattern + onboarding/
  retirement docs as v1.2) — deliberately deferred until the pattern has proven
  itself on the live system. This spec lives in the repo; no repo code changes now.
- claude-mem memory content about Mento — already merged history; stays as-is.
- The `~/mento-migration/` local folder (pre-merge DB backup) — untouched.

## Verification

- Scanner: wrong label → rejected with clear error; correct label → snapshot
  written to the right `raw/<label>/`; unenrolled hostname → refused with
  runbook pointer.
- Hook: run directly → clean output, no phantom pending banner, no
  `.needs-update` flag created, exits 0.
- `/insights-update` end-to-end → solo wiki compiles; INDEX shows personal
  active + mento retired w/ archive pointer.
- Fresh Claude Code session → startup line clean; `mento-*` skills absent from
  the skill list.
- Archive: `diff -r` (or file-count comparison) passes for every moved tree
  **before** any source deletion.
- `~/CLAUDE.md` renders without the Mento section; breadcrumb present.

## Open items (expected, not blockers)

- New company/role name — unknown until the job starts; placeholders noted above.
- Transport for the new laptop — decided at enrollment via the runbook's
  pre-flight check.
