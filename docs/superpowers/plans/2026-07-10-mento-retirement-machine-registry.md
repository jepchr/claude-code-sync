# Mento Retirement + Machine Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Mento machine from the live cross-machine insights system, archive all Mento data off iCloud, replace the hardcoded two-machine model with a config-driven machine registry, and leave a day-1 onboarding runbook for the upcoming new-company laptop.

**Architecture:** A `machines.json` registry at the sync-folder root becomes the single source of truth for machine identity. A new `registry.py` helper serves lookups to the scanner (Python import) and the SessionStart hook (CLI). All Mento data moves to `~/Archives/mento/` (local disk, never synced). The Claude-Desktop skill mirror gets a `.sync-ignore` exclusion list so archived Mento skills don't resurrect. The wiki recompiles itself in single-machine mode via the updated insights-update skill.

**Tech Stack:** Python 3 (scanner/registry), Bash (SessionStart hook), Claude Code skills (Markdown), iCloud Drive (transport).

**Spec:** `docs/superpowers/specs/2026-07-10-mento-retirement-machine-registry-design.md` (same repo).

## Global Constraints

- **Live system root** (called `$SYNC` throughout): `$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights` — the path contains spaces; **always double-quote** it in shell.
- **Archive root:** `~/Archives/mento/` — must stay OUTSIDE any synced folder (local disk only).
- **The iCloud folder is not a git repo.** Live-system tasks therefore end with a verification step instead of a commit; every file modified or replaced is backed up to `~/Archives/mento/pre-change-backups/` in Task 1 **before** any edits. Only Tasks in the `claude-code-sync` repo commit to git (branch `mento-retirement-spec`).
- **Copy → verify → delete** for every cross-volume move (iCloud → local disk): `diff -r` must pass before the source is removed.
- Machine labels are lowercase, role-based (`personal`, `work`) — never employer names.
- Registry matching rule (verbatim from spec): case-insensitive substring match of any of a machine's `hostnamePatterns` against the hostname blob; machines evaluated **in file order, first match wins**; more-specific machines listed first.
- This machine's identifiers (verified 2026-07-10): `hostname` → `MacBookPro`, LocalHostName → `Jeppes-MacBook-Pro`. Mento's LocalHostName was `Jeppes-MacBook-Pro-Mento` — it contains the personal pattern, which is why the `mento` entry must be listed FIRST in machines.json.
- The hook counts pending suggestions with `grep -c "^- "` — the fresh `pending.md` must contain **no lines starting with `- `** or the phantom banner returns.
- Do not touch: `$SYNC/scripts/n8n-guardrails.sh` (unrelated UserPromptSubmit hook), `$SYNC/raw/claude-desktop/`, `$SYNC/raw/personal/`, `~/mento-migration/` (local pre-merge DB backup), `suggestions/deferred.md` content (audited 2026-07-10: zero Mento-only items — all entries are generic tool evaluations; Mento appears only in historical rationale, which stays).

---

### Task 1: Archive skeleton + pre-change backups

**Files:**
- Create: `~/Archives/mento/README.md`
- Create: `~/Archives/mento/pre-change-backups/` (copies of every file later tasks modify)

**Interfaces:**
- Produces: the archive directory tree all later tasks move data into; backups that make every later edit reversible.

- [x] **Step 1: Create the archive tree**

```bash
mkdir -p ~/Archives/mento/pre-change-backups ~/Archives/mento/skills
```

- [x] **Step 2: Write the archive README**

Write `~/Archives/mento/README.md` with exactly:

```markdown
# Mento archive (2026-07-10)

Jeppe left Mento in 2026-06. This folder holds everything Mento-related that
was removed from the live Claude Code setup and the iCloud insights folder
(`claude-code-insights`) during the retirement on 2026-07-10.

It lives on local disk **deliberately outside iCloud** so it never syncs to a
future employer's laptop.

Contents:
- `raw-snapshots/` — Mento machine environment snapshots (from `raw/mento/`)
- `migration/` — the 2026-06-03 Mento→Personal consolidation package
- `consolidate-to-personal.md` — consolidation suggestion/checklist
- `adopted-mento-era.md` — improvements log #1–#50 (contains Mento ad-account
  IDs — do not put back into any synced folder)
- `pending-final-2026-07-10.md` — last pre-retirement pending list
- `check-insights-mento.sh` — Mento's SessionStart hook variant
- `mento-CLAUDE-section.md` — the "Mento Work" section excised from ~/CLAUDE.md
- `skills/` — the five Mento marketing skills (were Claude-Desktop-synced):
  mento-brand-voice, mento-editorial-doctrine, mento-internal-memo,
  ld-audience-voice, querying-mento-bigquery
- `pre-change-backups/` — pristine copies of every live file the retirement
  modified, taken before any edit

Related but not here: Mento memories stay merged inside claude-mem (history);
`~/mento-migration/` holds the pre-merge claude-mem DB backup.

Spec: claude-code-sync repo, docs/superpowers/specs/2026-07-10-mento-retirement-machine-registry-design.md
```

- [x] **Step 3: Back up every file later tasks will modify**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
B=~/Archives/mento/pre-change-backups
cp "$SYNC/scripts/check-insights.sh" "$B/"
cp "$SYNC/scripts/scan-environment.py" "$B/"
cp "$SYNC/scripts/sync-desktop-skills.py" "$B/"
cp "$SYNC/skills/insights-update/SKILL.md" "$B/insights-update-SKILL.md"
cp "$SYNC/skills/learn/SKILL.md" "$B/learn-SKILL.md"
cp "$SYNC/skills/discover/SKILL.md" "$B/discover-SKILL.md"
cp "$SYNC/suggestions/pending.md" "$B/pending.md"
cp "$SYNC/suggestions/adopted.md" "$B/adopted.md"
cp "$SYNC/wiki/INDEX.md" "$B/wiki-INDEX.md"
cp ~/CLAUDE.md "$B/home-CLAUDE.md"
cp ~/.claude/settings.json "$B/settings.json"
ls -la "$B"
```

Expected: 11 files listed in `$B`.

- [x] **Step 4: Verify**

```bash
diff ~/Archives/mento/pre-change-backups/check-insights.sh "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/scripts/check-insights.sh" && echo BACKUPS-OK
```

Expected: `BACKUPS-OK`.

---

### Task 2: machines.json + registry.py

**Files:**
- Create: `$SYNC/machines.json`
- Create: `$SYNC/scripts/registry.py`

**Interfaces:**
- Produces (used by Tasks 3 and 4):
  - `registry.load_machines() -> list[dict]` — raises on missing/corrupt file
  - `registry.hostname_blob() -> str` — lowercased `hostname` + LocalHostName + ComputerName
  - `registry.match(blob: str, machines: list[dict]) -> dict | None` — first match in file order
  - `registry.self_machine() -> dict | None` — `match(hostname_blob(), load_machines())`
  - `registry.others_active(label: str) -> list[str]`
  - `registry.REGISTRY_PATH: Path`
  - CLI: `registry.py --self` prints the label **only if the matched machine is active** (exit 2 unenrolled, 3 registry missing/corrupt, 4 retired); `registry.py --others-active` prints other active labels one per line (exit 2 if self unenrolled).

- [x] **Step 1: Write machines.json**

Write `$SYNC/machines.json` with exactly (mento FIRST — see Global Constraints):

```json
{
  "machines": [
    {
      "label": "mento",
      "hostnamePatterns": ["mento"],
      "status": "retired",
      "retiredDate": "2026-06-03",
      "archive": "~/Archives/mento/",
      "notes": "Mento work laptop. Consolidated into personal 2026-06-03; Jeppe left the company 2026-06."
    },
    {
      "label": "personal",
      "hostnamePatterns": ["jeppes-macbook-pro", "macbookpro"],
      "status": "active",
      "notes": "Personal MacBook Pro."
    }
  ]
}
```

- [x] **Step 2: Write registry.py**

Write `$SYNC/scripts/registry.py` with exactly:

```python
#!/usr/bin/env python3
"""
registry.py — machine-registry lookups for the cross-machine insights system.

machines.json (sync-folder root) is the single source of truth for which
machines exist. Matching rule: case-insensitive substring match of any of a
machine's hostnamePatterns against this machine's hostname blob; machines are
evaluated in file order, first match wins — list more-specific machines first.

CLI:
  registry.py --self            print this machine's label (active machines only)
                                exit codes: 2 unenrolled, 3 registry missing/corrupt, 4 retired
  registry.py --others-active   print other active machines' labels, one per line
"""
import json
import subprocess
import sys
from pathlib import Path

INSIGHTS_DIR = Path(__file__).resolve().parent.parent
REGISTRY_PATH = INSIGHTS_DIR / "machines.json"


def load_machines():
    """Machine list from machines.json. Raises on missing/corrupt file."""
    return json.loads(REGISTRY_PATH.read_text())["machines"]


def hostname_blob():
    """Lowercased hostname + LocalHostName + ComputerName, space-joined."""
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip().lower()
        except Exception:
            return ""
    return " ".join([
        run(["hostname"]),
        run(["scutil", "--get", "LocalHostName"]),
        run(["scutil", "--get", "ComputerName"]),
    ])


def match(blob, machines):
    """First machine (file order) with any pattern substring-matching blob, else None."""
    blob = blob.lower()
    for m in machines:
        if any(p.lower() in blob for p in m.get("hostnamePatterns", [])):
            return m
    return None


def self_machine():
    """This machine's registry entry, or None if unenrolled."""
    return match(hostname_blob(), load_machines())


def others_active(label):
    """Labels of other machines with status 'active'."""
    return [m["label"] for m in load_machines()
            if m["label"] != label and m.get("status") == "active"]


def main():
    args = sys.argv[1:]
    try:
        me = self_machine()
    except Exception:
        sys.exit(3)  # registry missing or corrupt
    if "--self" in args:
        if me is None:
            sys.exit(2)  # unenrolled — see onboarding/new-machine.md
        if me.get("status") != "active":
            sys.exit(4)  # retired hardware never participates
        print(me["label"])
    elif "--others-active" in args:
        if me is None:
            sys.exit(2)
        for label in others_active(me["label"]):
            print(label)
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [x] **Step 3: Test the pure matcher (all four cases)**

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/scripts" && python3 - <<'EOF'
import registry
ms = registry.load_machines()
# Mento blob contains BOTH patterns — file order must resolve it to mento
m = registry.match("jeppes-macbook-pro-mento.local jeppes-macbook-pro-mento", ms)
assert m and m["label"] == "mento" and m["status"] == "retired", m
# Personal blob
m = registry.match("macbookpro jeppes-macbook-pro jeppe's macbook pro", ms)
assert m and m["label"] == "personal", m
# Unknown host → unenrolled
assert registry.match("some-new-work-laptop", ms) is None
# Live: this machine must resolve to personal
assert registry.self_machine()["label"] == "personal"
print("MATCH-TESTS-OK")
EOF
```

Expected: `MATCH-TESTS-OK`.

- [x] **Step 4: Test the CLI**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
python3 "$SYNC/scripts/registry.py" --self; echo "exit=$?"
python3 "$SYNC/scripts/registry.py" --others-active; echo "exit=$?"
```

Expected: `personal` / `exit=0`, then **no labels** (mento is retired) / `exit=0`.

---

### Task 3: Scanner reads the registry

**Files:**
- Modify: `$SYNC/scripts/scan-environment.py` — replace `_detect_machine_label()` (lines ~395–413) and the top of `main()` (lines ~416–435)

**Interfaces:**
- Consumes: `registry.self_machine()`, `registry.REGISTRY_PATH` from Task 2 (module import — registry.py sits in the same directory).
- Produces: `python3 scan-environment.py [label]` — label now **optional** (defaults to this machine's registry label); refuses on mismatch/unenrolled/retired. `--force` is retired (it was the misfiling vector).

- [x] **Step 1: Replace `_detect_machine_label()` with a registry import helper**

Delete the whole `_detect_machine_label()` function (including its docstring, lines 395–413) and put in its place:

```python
def _registry():
    """Import the registry module that lives next to this script."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import registry
    return registry
```

- [x] **Step 2: Replace the top of `main()`**

Replace everything from `def main():` down to (and including) the `sys.exit(2)` of the old hostname guard with:

```python
def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    if "--force" in sys.argv:
        print("note: --force is retired — machines.json is authoritative now.")

    reg = _registry()
    try:
        me = reg.self_machine()
    except Exception:
        print("⚠️  Cannot read machines.json — the machine registry is missing or corrupt.")
        print(f"    Expected at: {reg.REGISTRY_PATH}")
        sys.exit(3)

    if me is None:
        print("⚠️  This machine is not enrolled in machines.json.")
        print("    See onboarding/new-machine.md in the sync folder to enroll it.")
        sys.exit(2)

    if me.get("status") != "active":
        print(f"⚠️  Machine '{me['label']}' is retired ({me.get('retiredDate', 'date unknown')}).")
        print(f"    Retired machines never write snapshots. Archive: {me.get('archive', 'n/a')}")
        sys.exit(4)

    machine_name = args[0] if args else me["label"]
    if machine_name != me["label"]:
        print(f"⚠️  Refusing to scan: you passed '{machine_name}', but this machine is '{me['label']}' per machines.json.")
        print("    This guard prevents writing one machine's data into another's folder.")
        sys.exit(2)
```

The lines that follow (`snapshot = format_snapshot(machine_name)` onward) stay unchanged. Also update the usage docstring at the top of the file: `Usage: python3 scan-environment.py [machine-name]   (defaults to this machine's registry label)`.

- [x] **Step 3: Test — mismatched label refused**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
python3 "$SYNC/scripts/scan-environment.py" mento; echo "exit=$?"
python3 "$SYNC/scripts/scan-environment.py" work; echo "exit=$?"
```

Expected: both print the "Refusing to scan… this machine is 'personal'" warning; both `exit=2`. The guard fires before any write — no new files appear under `$SYNC/raw/` (no `raw/work/` is created, and `raw/mento/` — still present until Task 6 — gains nothing).

- [x] **Step 4: Test — no-arg scan writes personal snapshot**

```bash
python3 "$SYNC/scripts/scan-environment.py"; echo "exit=$?"
ls -la "$SYNC/raw/personal/latest.md"
```

Expected: `Snapshot written to …/raw/personal/latest.md`, `exit=0`, and the file's mtime is now.

- [x] **Step 5: Test — retired machine refused (simulated)**

```bash
cd "$SYNC/scripts" && python3 - <<'EOF'
import registry
ms = registry.load_machines()
m = registry.match("jeppes-macbook-pro-mento", ms)
assert m["status"] == "retired"
print("RETIRED-GUARD-DATA-OK (scanner exits 4 for any non-active match)")
EOF
```

Expected: `RETIRED-GUARD-DATA-OK…`. (The scanner's retired branch can't run for real on this hardware; the data path is what's testable.)

---

### Task 4: SessionStart hook reads the registry

**Files:**
- Modify: `$SYNC/scripts/check-insights.sh` — lines 6–9 (identity) and lines 87–106 (other-machine check)

**Interfaces:**
- Consumes: `registry.py --self` and `registry.py --others-active` CLI from Task 2.
- Produces: hook works with 0..N other active machines; `.needs-update` flag now contains one label per line (the prompt hook only tests existence, so this is compatible).

- [x] **Step 1: Replace the hardcoded identity block**

Replace lines 6–9:

```bash
INSIGHTS_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
MACHINE_NAME="personal"
LAST_SCAN_FILE="$INSIGHTS_DIR/raw/$MACHINE_NAME/.last-scan"
SCAN_INTERVAL_SECONDS=$((3 * 86400))  # 3 days
```

with:

```bash
INSIGHTS_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"

# Exit silently if insights system not set up
[ -d "$INSIGHTS_DIR" ] || exit 0

# Machine identity comes from the registry (machines.json). Unenrolled machine,
# retired machine, or missing/corrupt registry -> exit silently; enrollment is
# documented in onboarding/new-machine.md.
MACHINE_NAME=$(python3 "$INSIGHTS_DIR/scripts/registry.py" --self 2>/dev/null) || exit 0
[ -n "$MACHINE_NAME" ] || exit 0

LAST_SCAN_FILE="$INSIGHTS_DIR/raw/$MACHINE_NAME/.last-scan"
SCAN_INTERVAL_SECONDS=$((3 * 86400))  # 3 days
```

and DELETE the now-duplicated original guard at old lines 11–12 (`# Exit silently…` / `[ -d "$INSIGHTS_DIR" ] || exit 0`) that sits just below.

- [x] **Step 2: Replace the other-machine block**

Replace old lines 87–106 (from `# Check for other machine's data` through the `fi` that ends the `if [ -f "$other_snapshot" ]` block) with:

```bash
# Check for other ACTIVE machines' data (registry-driven; 0..N machines)
OTHERS=$(python3 "$INSIGHTS_DIR/scripts/registry.py" --others-active 2>/dev/null)

NEEDS_UPDATE_FLAG="$INSIGHTS_DIR/.needs-update"
wiki_index="$INSIGHTS_DIR/wiki/INDEX.md"
newer_machines=""

for other in $OTHERS; do
    other_snapshot="$INSIGHTS_DIR/raw/$other/latest.md"
    [ -f "$other_snapshot" ] || continue
    other_date=$(stat -f %m "$other_snapshot" 2>/dev/null || echo "0")
    wiki_date=$(stat -f %m "$wiki_index" 2>/dev/null || echo "0")
    if [ "$other_date" -gt "$wiki_date" ]; then
        newer_machines="$newer_machines $other"
    fi
done

if [ -n "$newer_machines" ]; then
    echo "$newer_machines" | tr ' ' '\n' | sed '/^$/d' > "$NEEDS_UPDATE_FLAG"
    echo "[insights] New data from$newer_machines detected — auto-update will run."
else
    rm -f "$NEEDS_UPDATE_FLAG"
fi
```

The pending-suggestions block below it (old lines 108–115) stays unchanged.

- [x] **Step 3: Test — direct hook run**

```bash
bash "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/scripts/check-insights.sh"; echo "exit=$?"
ls "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/.needs-update" 2>&1
```

Expected: `exit=0`; possibly a `[desktop-sync] …` line and (until Task 7 lands) the pending-suggestions banner; **no** "New data from" line; `.needs-update`: `No such file or directory`.

- [x] **Step 4: Syntax check**

```bash
bash -n "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/scripts/check-insights.sh" && echo SYNTAX-OK
```

Expected: `SYNTAX-OK`.

---

### Task 5: Desktop-sync exclusion list + de-link the five Mento skills

The five Mento skills are symlinks into the Claude-Desktop mirror (`$SYNC/skills/desktop/`), and **Claude Desktop is the source of truth** — without an exclusion list, `sync-desktop-skills.py` would re-copy and re-link anything we remove on its next run.

**Files:**
- Create: `$SYNC/skills/desktop/.sync-ignore`
- Modify: `$SYNC/scripts/sync-desktop-skills.py` (add `load_ignore_list()`, filter in `main()`)

**Interfaces:**
- Produces: `.sync-ignore` (one skill name per line, `#` comments) permanently excludes names from the Desktop→Code mirror; excluded names' symlinks are auto-removed by the existing `cleanup_stale_symlinks()`.

- [x] **Step 1: Write the exclusion list**

Write `$SYNC/skills/desktop/.sync-ignore` with exactly:

```
# Skills never mirrored from Claude Desktop into Claude Code.
# One name per line; # comments. Removing a line re-enables sync on next run.
# Mento era ended 2026-06 — archived at ~/Archives/mento/skills/.
mento-brand-voice
mento-editorial-doctrine
mento-internal-memo
ld-audience-voice
querying-mento-bigquery
```

- [x] **Step 2: Add `load_ignore_list()` to sync-desktop-skills.py**

Insert after the `find_desktop_skills()` function (after line 62):

```python
def load_ignore_list():
    """Skill names listed in skills/desktop/.sync-ignore — never mirrored."""
    ignore_file = ICLOUD_DESKTOP_SKILLS / ".sync-ignore"
    if not ignore_file.exists():
        return set()
    names = set()
    for line in ignore_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.add(line)
    return names
```

- [x] **Step 3: Apply the filter in `main()`**

In `main()`, directly after `desktop_skills = find_desktop_skills()` (line 137), insert:

```python
    ignored = load_ignore_list()
    desktop_skills = {n: v for n, v in desktop_skills.items() if n not in ignored}
```

(`cleanup_stale_symlinks(set(desktop_skills.keys()))` further down then treats ignored names as gone and removes their `~/.claude/skills/` symlinks automatically.)

- [x] **Step 4: Run and verify the links drop**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
python3 "$SYNC/scripts/sync-desktop-skills.py" --verbose
ls ~/.claude/skills/ | grep -E "mento|ld-audience" ; echo "grep-exit=$?"
```

Expected: output includes `5 removed (…)` naming the five skills; the `grep` prints nothing, `grep-exit=1`.

- [x] **Step 5: Verify exclusion is idempotent**

```bash
python3 "$SYNC/scripts/sync-desktop-skills.py" --verbose
```

Expected: no `new`/`removed` mentions of the five names (e.g. `NN skills, no changes` or unrelated refresh lines only).

---

### Task 6: Move all Mento data to the archive

**Files:**
- Move: `$SYNC/raw/mento/` → `~/Archives/mento/raw-snapshots/`
- Move: `$SYNC/migration/` → `~/Archives/mento/migration/`
- Move: `$SYNC/suggestions/consolidate-to-personal.md` → `~/Archives/mento/`
- Move: `$SYNC/scripts/check-insights-mento.sh` → `~/Archives/mento/`
- Move: `$SYNC/skills/desktop/{the five Mento skill dirs}` → `~/Archives/mento/skills/`

**Interfaces:**
- Consumes: Task 5's `.sync-ignore` must already be live (else the desktop mirror re-creates the five skill dirs).

- [x] **Step 1: Copy each tree, then verify with `diff -r` before deleting**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
A=~/Archives/mento
set -e
cp -R "$SYNC/raw/mento" "$A/raw-snapshots"
diff -r "$SYNC/raw/mento" "$A/raw-snapshots"
cp -R "$SYNC/migration" "$A/migration"
diff -r "$SYNC/migration" "$A/migration"
cp "$SYNC/suggestions/consolidate-to-personal.md" "$A/"
diff "$SYNC/suggestions/consolidate-to-personal.md" "$A/consolidate-to-personal.md"
cp "$SYNC/scripts/check-insights-mento.sh" "$A/"
diff "$SYNC/scripts/check-insights-mento.sh" "$A/check-insights-mento.sh"
for s in mento-brand-voice mento-editorial-doctrine mento-internal-memo ld-audience-voice querying-mento-bigquery; do
  cp -R "$SYNC/skills/desktop/$s" "$A/skills/$s"
  diff -r "$SYNC/skills/desktop/$s" "$A/skills/$s"
done
echo ALL-COPIES-VERIFIED
```

Expected: `ALL-COPIES-VERIFIED` (any diff output = STOP, do not delete).

- [x] **Step 2: Delete the sources (only after Step 1 printed ALL-COPIES-VERIFIED)**

```bash
rm -rf "$SYNC/raw/mento" "$SYNC/migration" "$SYNC/suggestions/consolidate-to-personal.md" "$SYNC/scripts/check-insights-mento.sh"
for s in mento-brand-voice mento-editorial-doctrine mento-internal-memo ld-audience-voice querying-mento-bigquery; do
  rm -rf "$SYNC/skills/desktop/$s"
done
ls "$SYNC/raw/"; ls "$SYNC/skills/desktop/" | head -25
```

Expected: `raw/` shows only `claude-desktop` and `personal`; `skills/desktop/` shows no mento/ld-audience names (`.sync-ignore` remains).

- [x] **Step 3: Confirm nothing resurrects**

```bash
python3 "$SYNC/scripts/sync-desktop-skills.py" --verbose | grep -E "mento|ld-audience"; echo "grep-exit=$?"
```

Expected: nothing printed, `grep-exit=1`.

---

### Task 7: Reset the suggestions files

**Files:**
- Move: `$SYNC/suggestions/adopted.md` → `~/Archives/mento/adopted-mento-era.md`, then create a fresh `$SYNC/suggestions/adopted.md`
- Replace: `$SYNC/suggestions/pending.md` (old content → `~/Archives/mento/pending-final-2026-07-10.md`)
- Verify-only: `$SYNC/suggestions/deferred.md` stays byte-identical (audited: zero Mento-only items).

- [x] **Step 1: Archive the old files, record deferred.md's checksum**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
cp "$SYNC/suggestions/adopted.md" ~/Archives/mento/adopted-mento-era.md
diff "$SYNC/suggestions/adopted.md" ~/Archives/mento/adopted-mento-era.md && echo ADOPTED-ARCHIVED
cp "$SYNC/suggestions/pending.md" ~/Archives/mento/pending-final-2026-07-10.md
diff "$SYNC/suggestions/pending.md" ~/Archives/mento/pending-final-2026-07-10.md && echo PENDING-ARCHIVED
md5 -q "$SYNC/suggestions/deferred.md"
```

Expected: `ADOPTED-ARCHIVED`, `PENDING-ARCHIVED`, and an md5 hash — note it down for Step 4.

- [x] **Step 2: Write the fresh adopted.md**

Overwrite `$SYNC/suggestions/adopted.md` with exactly:

```markdown
# Adopted Improvements

*What was brought over, from where, and when.*

*Entries #1–#50 (2026-04 → 2026-05, the Mento era — including the Google Ads
MCP runbook and the consolidation record) are archived locally at
`~/Archives/mento/adopted-mento-era.md` and deliberately kept out of this
synced folder. Numbering continues from #51 so wiki references stay valid.
`/discover` dedupe: for pre-2026-06 evaluations, also check that archive and
`deferred.md` (which keeps its full history here).*
```

- [x] **Step 3: Write the fresh pending.md**

Overwrite `$SYNC/suggestions/pending.md` with exactly (NOTE: no `- ` list lines — the hook counts `^- ` as pending items):

```markdown
# Pending Suggestions

*Items discovered by the comparison engine that haven't been acted on yet.*

*All items through 2026-07-10 were resolved during the Mento retirement:
completed/moot items are archived at `~/Archives/mento/pending-final-2026-07-10.md`,
and the long-standing "add a hostname guard to the scanner" item was fixed for
good by the machine registry (`machines.json` + `scripts/registry.py`).
The system runs in single-machine mode until the next machine enrolls — see
`onboarding/new-machine.md`.*
```

- [x] **Step 4: Verify the phantom banner is gone and deferred.md untouched**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
bash "$SYNC/scripts/check-insights.sh" | grep -c "pending suggestions"; true
md5 -q "$SYNC/suggestions/deferred.md"
```

Expected: grep count `0` (no banner), and the md5 hash is byte-identical to the one recorded in Step 1.

---

### Task 8: Skill + settings text edits (machine-agnostic wording)

**Files:**
- Modify: `$SYNC/skills/insights-update/SKILL.md` (lines 8, 10–12, 33–41, 70–72)
- Modify: `$SYNC/skills/learn/SKILL.md` (description line 3, intro line ~8, line ~192)
- Modify: `$SYNC/skills/discover/SKILL.md` (line 69)
- Modify: `~/.claude/settings.json` (prompt-hook wording)

(The `~/.claude/skills/` entries for these are symlinks into `$SYNC/skills/` — edit the iCloud source, both see it.)

- [x] **Step 1: insights-update SKILL.md — intro + Location**

Line 8: replace `You are maintaining a knowledge base about Claude Code environments across two machines.` with `You are maintaining a knowledge base about Claude Code environments across Jeppe's machines (registry: machines.json at the folder root).`

In the `## Location` section, after the folder path line, add: `The machine registry is machines.json at the folder root — labels, hostname patterns, and status (active/retired).`

- [x] **Step 2: insights-update SKILL.md — Phase 1 rewrite**

Replace the Phase 1 numbered list (old lines 35–41):

```markdown
1. Read `machines.json` — the machine registry (labels + status).
2. For each machine in the registry, read `raw/<label>/latest.md` if it exists.
   Machines with `status: "retired"` are history: never generate action items
   for them; mention them only as provenance (e.g. "adopted from mento, 2026-05").
3. Read `raw/claude-desktop/latest.md` (if it exists)
4. Read `wiki/INDEX.md`
5. Read `suggestions/pending.md`, `suggestions/adopted.md`, `suggestions/deferred.md`

If only one ACTIVE machine has a snapshot, compile what you have — single-machine
mode is normal (e.g. between jobs). Don't block on other machines.
```

- [x] **Step 3: insights-update SKILL.md — Phase 3 heading line**

Replace `Compare the two environments (if both snapshots exist) and categorize findings:` with `Compare the ACTIVE machines' environments (needs 2+ active snapshots; in single-machine mode skip the comparison and just refresh the wiki):`

- [x] **Step 4: learn SKILL.md — three spots**

1. Description (line 3), replace the final sentence `Writes to iCloud shared folder so both Personal and Mento pick it up automatically.` with `Writes to iCloud shared folder so all enrolled machines pick it up automatically.`
2. Intro line `Turn a useful discovery from the current session into a shared skill that works across both machines.` → `…that works across all your machines.`
3. Cross-machine propagation section (line ~192): `Learned skills live in `iCloud/skills/learned/`. On next Mento session, the hook will create a symlink for each learned skill automatically (via the `sync-learned-skills` step in `check-insights*.sh`).` → `Learned skills live in `iCloud/skills/learned/`. On each enrolled machine's next session, the hook creates a symlink for each learned skill automatically (via `check-insights.sh`).`

- [x] **Step 5: discover SKILL.md — role line**

Replace line 69 `- **Role:** Head of Growth at Mento. Applying for Head of Brand and Content roles.` with `- **Role:** Starting a new role (2026-07) — update this line on day 1 of the new job. Previously Head of Growth at Mento.`

- [x] **Step 6: settings.json — prompt-hook wording**

In `~/.claude/settings.json`, in the SessionStart prompt hook, replace the phrase `compile the wiki from both machine snapshots` with `compile the wiki from all enrolled machines' snapshots (see machines.json)`. Use a targeted string edit on the raw file (do NOT round-trip the JSON through a formatter).

- [x] **Step 7: Verify**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
grep -c "raw/mento/latest.md" "$SYNC/skills/insights-update/SKILL.md"; true
grep -c "both Personal and Mento" "$SYNC/skills/learn/SKILL.md"; true
grep -c "Head of Growth at Mento. Applying" "$SYNC/skills/discover/SKILL.md"; true
grep -c "both machine snapshots" ~/.claude/settings.json; true
python3 -c "import json; json.load(open('/Users/jeppe/.claude/settings.json')); print('SETTINGS-JSON-VALID')"
```

Expected: four `0` counts and `SETTINGS-JSON-VALID`.

---

### Task 9: Excise the Mento section from ~/CLAUDE.md

**Files:**
- Modify: `~/CLAUDE.md` — lines 129–161 (the `---` separator + `# Mento Work…` section, which runs to EOF)
- Create: `~/Archives/mento/mento-CLAUDE-section.md`

- [x] **Step 1: Archive the section**

Copy lines 129–161 of `~/CLAUDE.md` (from the `---` separator through the end of the file — the whole `# Mento Work (migrated from Mento machine, 2026-06-03)` section including "Mento tool pointers" and "Marketing OS protocol") into `~/Archives/mento/mento-CLAUDE-section.md`, prefixed with:

```markdown
# Excised from ~/CLAUDE.md on 2026-07-10 (Mento retirement)

```

- [x] **Step 2: Replace the section with a breadcrumb**

In `~/CLAUDE.md`, replace everything from line 129 (`---`) to EOF with:

```markdown
---

*(Mento era ended 2026-06 — Jeppe left the company. The former "Mento Work"
section — tool pointers, Marketing OS protocol — is archived at
`~/Archives/mento/mento-CLAUDE-section.md`.)*
```

- [x] **Step 3: Verify**

```bash
grep -c -i "mento" ~/CLAUDE.md
tail -5 ~/CLAUDE.md
diff <(sed -n '131,161p' ~/Archives/mento/pre-change-backups/home-CLAUDE.md) <(sed -n '/^# Mento Work/,$p' ~/Archives/mento/mento-CLAUDE-section.md) && echo SECTION-ARCHIVED-INTACT
```

Expected: count is `2` (both in the breadcrumb); tail shows the breadcrumb; `SECTION-ARCHIVED-INTACT`.

---

### Task 10: New-laptop onboarding runbook

**Files:**
- Create: `$SYNC/onboarding/new-machine.md`

- [x] **Step 1: Write the runbook**

Write `$SYNC/onboarding/new-machine.md` with exactly:

```markdown
# Enrolling a new machine

Day-1 guide for adding a machine (e.g. a new work laptop) to the cross-machine
insights system. Written 2026-07-10, when the system went single-machine after
the Mento retirement.

## 0. Pre-flight policy check (do this BEFORE installing anything)

On a company machine, answer these first and write the answers down here:

- [ ] Is **Claude Code** permitted on company hardware?
- [ ] Is **personal iCloud Drive** permitted? (The sync folder lives in
      Jeppe's personal iCloud.)
- [ ] Any MDM/DLP rules about personal cloud storage or dev tools?

If Claude Code isn't permitted: stop — the system stays single-machine.

## 1. Transport decision

The folder is transport-agnostic — any synced folder or a private git repo
works. If personal iCloud is blocked, pick a permitted transport and update
exactly THREE swap points on each machine:

1. The hook command path in `~/.claude/settings.json` (SessionStart)
2. `INSIGHTS_DIR` at the top of `scripts/check-insights.sh`
3. The `Location` line in `skills/insights-update/SKILL.md`

(`scripts/registry.py` and `scripts/scan-environment.py` derive the folder from
their own location — moving the folder moves them with it.)

## 2. Privacy review — both directions

Before syncing this folder to employer hardware, know what it carries:

- Personal skill/plugin/MCP names in the wiki and snapshots (travel, finance,
  wealth-tracker tooling, job-search automation).
- And the reverse: the new machine's scans (its skills, MCP names, CLAUDE.md
  rules) will flow back into personal storage. Keep company secrets out of
  CLAUDE.md files or accept that they sync; the scanner records names and
  descriptions, not credentials.

Make this a conscious yes/no. If "no", stay single-machine.

## 3. Enrollment

On the new machine:

1. Install Claude Code; sign in.
2. Make the sync folder available (iCloud sign-in or the chosen transport).
3. Run `hostname` and `scutil --get LocalHostName` — pick a distinctive
   substring for the patterns below.
4. Add an entry to `machines.json`. Label by ROLE, not employer (`work`, not
   the company name — company names in config are why the Mento retirement
   took work). Place it ABOVE `personal` if its hostname could contain a
   personal pattern:

   { "label": "work",
     "hostnamePatterns": ["<distinctive-hostname-substring>"],
     "status": "active",
     "notes": "<company> laptop, enrolled <date>" }

5. Add the SessionStart hook to `~/.claude/settings.json` (copy the two
   insights entries — command hook + prompt hook — from this machine's
   settings; adjust paths if the transport differs).
6. First scan: `python3 <sync-folder>/scripts/scan-environment.py work`
7. In Claude Code, run the `insights-update` skill. The cross-machine
   comparison output IS the setup checklist — it will list every skill,
   plugin, and setting the new machine is missing.

## 4. Day-1 config updates (easy to forget)

- Update the Role line in `skills/discover/SKILL.md` (currently a 2026-07
  placeholder) with the new title/company.
- Review `~/CLAUDE.md` on the personal machine for anything the new job makes
  stale.
- Revisit `suggestions/deferred.md` items whose "revisit if" mentioned a
  changed circumstance.

## Retiring a machine (for next time)

1. Set its `machines.json` entry to `"status": "retired"` + `"retiredDate"`.
2. Archive its `raw/<label>/` folder and any machine-specific files OUT of the
   synced folder (local `~/Archives/<label>/`).
3. Reset `suggestions/pending.md` items that referenced it.
4. Run the insights-update skill once to recompile the wiki.
   (Full worked example: the 2026-07-10 Mento retirement — spec + plan in the
   claude-code-sync repo under docs/superpowers/.)
```

- [x] **Step 2: Verify**

```bash
ls -la "$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights/onboarding/new-machine.md"
```

Expected: file exists, non-zero size.

---

### Task 11: Recompile the wiki + full-system verification sweep

**Files:**
- Regenerated by the skill run: `$SYNC/wiki/*.md`, `$SYNC/health/latest.md`

- [x] **Step 1: Run the updated insights-update skill end-to-end**

In Claude Code, invoke the `insights-update` skill and follow its (now registry-driven) process: Phase 0 desktop sync → Phase 1 reads `machines.json` + the single active snapshot → single-machine mode (no comparison) → recompile the 7 wiki articles + INDEX → health check → 3–5 line report.

Expected wiki outcomes to verify by reading `wiki/INDEX.md` afterwards:
- Machines table: `personal` active with a fresh snapshot date; `mento` shown as **retired 2026-06-03, archived at ~/Archives/mento/** (no "last snapshot age" warnings, no rescan advice).
- The 2026-05-28 "data-integrity finding" (personal snapshots were actually Mento) no longer appears as active — the registry + guard resolved it.
- Quick stats reflect personal-only counts; no pending suggestions.

- [x] **Step 2: Stray-reference sweep over the live system**

```bash
SYNC="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-insights"
grep -ril "mento" "$SYNC" | sort
```

Expected files ONLY (all historical/intentional):
- `machines.json` (the retired entry)
- `suggestions/deferred.md` (historical rationale — audited, stays)
- `suggestions/adopted.md` + `suggestions/pending.md` (archive pointers)
- `onboarding/new-machine.md` (the retirement worked example)
- `wiki/*.md` where the improvements-log/provenance mentions history ("adopted from mento, 2026-05")
- `skills/desktop/.sync-ignore` (exclusion comments)
- `skills/discover/SKILL.md` ("Previously Head of Growth at Mento")

Anything else in the list = a miss; fix it before proceeding.

- [x] **Step 3: Hook end-to-end, clean**

```bash
bash "$SYNC/scripts/check-insights.sh"; echo "exit=$?"
```

Expected: `exit=0`; no pending banner, no "New data from", no `.needs-update` file. (A `[desktop-sync]` or scan-freshness line is fine.)

- [x] **Step 4: Local skill surface check**

```bash
ls ~/.claude/skills/ | grep -iE "mento|ld-audience"; echo "grep-exit=$?"
readlink ~/.claude/skills/insights-update && readlink ~/.claude/skills/learn && readlink ~/.claude/skills/discover
```

Expected: first grep empty with `grep-exit=1`; the three readlinks still resolve into `$SYNC/skills/…` (shared skills intact).

- [x] **Step 5: Note for Jeppe**

The final proof is the next fresh Claude Code session: the startup line should show no `[insights] N pending suggestions` banner. Also hand Jeppe the manual checklist (spec §2): claude.ai connectors (Sanity `sd8wddo4`, Mento BigQuery, Zapier), the `linear-server` MCP personal-vs-Mento call, and optionally deleting the five Mento skills inside the Claude Desktop app (harmless if left — they're `.sync-ignore`d).

---

### Task 12: Commit docs + merge the branch

**Files:**
- Already on branch `mento-retirement-spec`: the spec (amended) + this plan
- Repo: `/Users/jeppe/Projects/claude-code-sync`

- [x] **Step 1: Commit any outstanding doc changes**

```bash
cd /Users/jeppe/Projects/claude-code-sync && git status --short
git add docs/ && git commit -m "Mento retirement executed: amend spec (desktop-skill exclusion), mark plan checkboxes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [x] **Step 2: Open PR and merge (per Jeppe's git workflow: feature branch → PR → self-merge when mergeable)**

```bash
git push -u origin mento-retirement-spec
gh pr create --title "Mento retirement + machine registry (spec + plan)" --body "Docs for retiring the Mento machine from the live insights system and generalizing to a config-driven machine registry. Live-system changes were applied outside this repo (iCloud folder + ~/.claude); this PR records the spec and plan.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --squash --delete-branch
```

Expected: PR merged into `main`.

---

## Execution notes (2026-07-10 — all 12 tasks completed)

Deviations discovered and handled during execution, per Task 11's "anything
else = a miss; fix it" rule:

1. **Five `raw/personal/` snapshots were Mento hardware** (hostname audit:
   2026-04-22, 05-04, 05-18, 05-21, 05-26 — the mislabel bug's droppings, and
   May's open "delete later" action). Archived to
   `~/Archives/mento/raw-snapshots/mislabeled-as-personal/`, removed from the
   synced folder. Remaining dated snapshots verified personal by hostname.
2. **`setup-mento.sh` (folder root)** — Mento bootstrap script the spec's sweep
   table missed. Archived; superseded by `onboarding/new-machine.md`.
3. **Root `README.md`** rewritten for the registry era (was two-machine
   framing; referenced the removed `/harvest-memories` and `setup-mento.sh`).
   `plan.md` deliberately kept as the system's historical build plan.
4. **Grep false positives** (no action): `@EnvironmentObject` (swiftui-pro
   data), `ST_MeasurementOrPercent` (ISO XML schemas), "mentorship"
   (ai-tell-editor). Three Desktop-owned skills (google-docs-formatting,
   managing-google-workspace-via-mcp) already say "Jeppe left Mento" — Desktop
   is their source of truth, left alone.
5. **`wiki/improvements-log.md`**: Mento ad-account/MCC identifiers redacted
   during the recompile (same privacy rationale as archiving adopted.md);
   unredacted history preserved in `~/Archives/mento/adopted-mento-era.md`.
6. Task 5 Step 2 used `def copy_skill(` as the insert anchor (same position as
   the plan's "after line 62").

Verified end state: hook exits 0 with no banner and no `.needs-update`; scanner
refuses `mento`/`work` labels and scans label-free as `personal`; zero
unexpected Mento references in the synced folder; `~/.claude/skills/` has no
mento-*/ld-audience links; `~/CLAUDE.md` carries only the breadcrumb.
