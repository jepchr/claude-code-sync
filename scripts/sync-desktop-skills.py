#!/usr/bin/env python3
"""
sync-desktop-skills.py

Mirrors Claude Desktop skills into Claude Code so they're available in both.

Flow:
  Claude Desktop skills  ──►  iCloud shared folder  ──►  ~/.claude/skills/ (symlinks)
    (source of truth)         (skills/desktop/)            (what Claude Code loads)

Behavior:
- Copies new Claude Desktop skills into iCloud (skills/desktop/<name>/).
- Refreshes iCloud copy when Claude Desktop's SKILL.md is newer.
- Creates symlinks in ~/.claude/skills/ pointing at the iCloud copy.
- Removes stale symlinks when a skill disappears from Claude Desktop.
- NEVER overwrites a Claude Code skill that's a real directory (not a symlink).
  If ~/.claude/skills/<name> exists as a directory, we skip that name and warn.

Run silently on SessionStart or on demand.
"""

import os
import shutil
import sys
from pathlib import Path

CLAUDE_CODE_SKILLS = Path.home() / ".claude" / "skills"

# Override via CLAUDE_SYNC_DIR env var. Default is iCloud on macOS.
_sync_dir = os.environ.get("CLAUDE_SYNC_DIR")
if _sync_dir:
    ICLOUD_DESKTOP_SKILLS = Path(_sync_dir) / "skills" / "desktop"
else:
    ICLOUD_DESKTOP_SKILLS = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "claude-code-sync"
        / "skills"
        / "desktop"
    )
CLAUDE_DESKTOP_BASE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Claude"
    / "local-agent-mode-sessions"
    / "skills-plugin"
)


def find_desktop_skills():
    """Find all Claude Desktop skills, dedup by name, keep newest by mtime."""
    if not CLAUDE_DESKTOP_BASE.exists():
        return {}
    found = {}  # name -> (mtime, skill_dir)
    for skill_md in CLAUDE_DESKTOP_BASE.glob("*/*/skills/*/SKILL.md"):
        skill_dir = skill_md.parent
        name = skill_dir.name
        try:
            mtime = skill_md.stat().st_mtime
        except OSError:
            continue
        if name in found and found[name][0] >= mtime:
            continue
        found[name] = (mtime, skill_dir)
    return found


def copy_skill(src_dir, dest_dir):
    """Copy a skill directory, preserving all files."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)


def needs_update(src_dir, dest_dir):
    """Check if dest is missing or older than src."""
    src_md = src_dir / "SKILL.md"
    dest_md = dest_dir / "SKILL.md"
    if not dest_md.exists():
        return True
    try:
        return src_md.stat().st_mtime > dest_md.stat().st_mtime
    except OSError:
        return True


def ensure_symlink(name, target_dir):
    """Create or update a symlink in ~/.claude/skills/<name> pointing to target_dir.

    Returns (action, message) — action is 'linked', 'updated', 'skipped', or 'collision'.
    """
    link_path = CLAUDE_CODE_SKILLS / name

    if link_path.is_symlink():
        current = link_path.resolve()
        if current == target_dir.resolve():
            return ("ok", None)
        link_path.unlink()
        link_path.symlink_to(target_dir)
        return ("updated", f"retargeted {name}")

    if link_path.exists():
        # It's a real directory — don't overwrite a local Claude Code skill
        return ("collision", f"{name} exists as a real directory in Claude Code, skipping")

    link_path.symlink_to(target_dir)
    return ("linked", f"linked {name}")


def cleanup_stale_symlinks(current_names):
    """Remove symlinks in ~/.claude/skills/ that point into iCloud desktop/ but
    no longer correspond to an existing Claude Desktop skill.
    """
    removed = []
    if not CLAUDE_CODE_SKILLS.exists():
        return removed
    for link in CLAUDE_CODE_SKILLS.iterdir():
        if not link.is_symlink():
            continue
        try:
            target = link.resolve()
        except OSError:
            continue
        try:
            target.relative_to(ICLOUD_DESKTOP_SKILLS)
        except ValueError:
            continue  # not a desktop-synced symlink
        if link.name not in current_names:
            link.unlink()
            removed.append(link.name)
    return removed


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    CLAUDE_CODE_SKILLS.mkdir(parents=True, exist_ok=True)
    ICLOUD_DESKTOP_SKILLS.mkdir(parents=True, exist_ok=True)

    desktop_skills = find_desktop_skills()
    if not desktop_skills:
        if verbose:
            print("No Claude Desktop skills found.")
        return 0

    stats = {"copied": 0, "updated": 0, "linked": 0, "retargeted": 0, "unchanged": 0, "collisions": []}

    for name, (_mtime, src_dir) in desktop_skills.items():
        dest_dir = ICLOUD_DESKTOP_SKILLS / name

        if needs_update(src_dir, dest_dir):
            copy_skill(src_dir, dest_dir)
            if dest_dir.exists():
                stats["updated"] += 1 if stats.get("_was_new", False) is False else 0
            stats["copied"] += 1

        action, message = ensure_symlink(name, dest_dir)
        if action == "linked":
            stats["linked"] += 1
        elif action == "updated":
            stats["retargeted"] += 1
        elif action == "collision":
            stats["collisions"].append(name)
        elif action == "ok":
            stats["unchanged"] += 1

    removed = cleanup_stale_symlinks(set(desktop_skills.keys()))

    # Report (silent unless something changed or --verbose)
    changed = stats["copied"] or stats["linked"] or stats["retargeted"] or removed or stats["collisions"]
    if changed or verbose:
        parts = []
        if stats["copied"]:
            parts.append(f"{stats['copied']} copied")
        if stats["linked"]:
            parts.append(f"{stats['linked']} linked")
        if stats["retargeted"]:
            parts.append(f"{stats['retargeted']} retargeted")
        if removed:
            parts.append(f"{len(removed)} removed ({', '.join(removed)})")
        if stats["collisions"]:
            parts.append(f"{len(stats['collisions'])} collisions ({', '.join(stats['collisions'])})")
        if parts:
            print(f"[desktop-sync] {', '.join(parts)}")
        elif verbose:
            print(f"[desktop-sync] {len(desktop_skills)} skills, no changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
