# Claude Code Sync

A system that lets multiple Claude Code environments learn from each other.

If you use Claude Code on more than one machine (say, work and personal), each one accumulates different skills, hooks, plugins, and conventions over time. This system creates a learning loop between them so improvements on one machine flow to the other automatically.

Inspired by [Andrej Karpathy's post on LLM Knowledge Bases](https://x.com/karpathy/status/1909364237498511558) — raw data goes in, an LLM compiles it into a wiki, and the wiki gets smarter over time.

## How it works

```
┌──────────────┐        Shared folder       ┌──────────────┐
│  Machine A   │◄────────────────────────►   │  Machine B   │
│              │                             │              │
│ 1. Scan env  │   raw/machine-a/latest.md   │ 1. Scan env  │
│ 2. Write     │──►                          │ 2. Write     │
│    snapshot   │   raw/machine-b/latest.md   │    snapshot  │
│ 3. Read B's  │◄──                       ◄──│ 3. Read A's  │
│ 4. Update    │        wiki/               │ 4. Update    │
│    wiki      │        suggestions/         │    wiki      │
└──────────────┘                             └──────────────┘
```

1. **Scanner** reads the local Claude Code config (skills, plugins, hooks, settings, CLAUDE.md) and writes a structured markdown snapshot
2. **SessionStart hook** triggers the scan every few days and detects when the other machine has new data
3. **Wiki compiler skill** (LLM-powered) reads both snapshots, maintains wiki articles, and generates suggestions
4. The shared folder syncs via iCloud, Dropbox, Google Drive, or any file sync tool

Most improvements apply automatically. Conflicts get flagged for you to decide.

## What the scanner captures

- Claude Code skills (name, description, count)
- Claude Desktop skills (macOS only — separate ecosystem from Claude Code)
- Plugins (name, version, scope)
- MCP servers (name, type — no credentials)
- Settings (thinking mode, effort level, token limits, permissions count)
- Hooks (what runs on SessionStart, Stop, etc.)
- Custom commands and scripts
- CLAUDE.md content (workflow rules, conventions, verification patterns)

## Folder structure

```
claude-code-sync/
├── scripts/
│   ├── scan-environment.py      # Environment scanner
│   └── check-sync.sh            # SessionStart hook
├── skills/
│   └── sync-update/
│       └── SKILL.md             # Wiki compiler skill (LLM-powered)
├── raw/
│   ├── machine-a/
│   │   └── latest.md            # Machine A's snapshot
│   └── machine-b/
│       └── latest.md            # Machine B's snapshot
├── wiki/
│   └── INDEX.md                 # Auto-maintained wiki index
└── suggestions/
    ├── pending.md               # Ideas not yet acted on
    ├── adopted.md               # What was brought over and when
    └── deferred.md              # "Not now" with reason
```

## Setup

### 1. Create the shared folder

Pick a location that syncs between your machines. iCloud example:

```bash
SYNC_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-sync"
mkdir -p "$SYNC_DIR"/{raw,wiki,suggestions,scripts,skills/sync-update}
```

### 2. Install the scanner

Copy `scripts/scan-environment.py` to your sync folder:

```bash
cp scripts/scan-environment.py "$SYNC_DIR/scripts/"
chmod +x "$SYNC_DIR/scripts/scan-environment.py"
```

Run it with your machine name:

```bash
python3 "$SYNC_DIR/scripts/scan-environment.py" machine-a
```

### 3. Install the SessionStart hook

Copy `scripts/check-sync.sh` to your sync folder and update `MACHINE_NAME` inside the script:

```bash
cp scripts/check-sync.sh "$SYNC_DIR/scripts/"
chmod +x "$SYNC_DIR/scripts/check-sync.sh"
```

Add the hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"/path/to/your/sync/folder/scripts/check-sync.sh\"",
            "once": true
          }
        ]
      }
    ]
  }
}
```

### 4. Install the wiki compiler skill

```bash
ln -sf "$SYNC_DIR/skills/sync-update" "$HOME/.claude/skills/sync-update"
```

Then run `/sync-update` in Claude Code to compile the wiki from your snapshots.

### 5. Repeat on your other machine

Same steps, different machine name. The shared folder handles the rest.

## What the system finds

In our first cycle, the system:

- Found stale plugins on both machines (the update script was checking a cached index instead of the source)
- Identified 6 skills on one machine that were useful on the other
- Discovered that one machine had a verification hook the other was missing
- Merged CLAUDE.md workflow patterns learned on one machine into the other

## Auto-update (optional)

Add a prompt hook so the wiki compiles automatically when new data arrives:

```json
{
  "hooks": [
    {
      "type": "prompt",
      "prompt": "Check if the file /path/to/sync/folder/.needs-update exists. If it does: read the sync-update skill, follow its process to compile the wiki, then delete the flag file. Report briefly. If the file does not exist, do nothing and say nothing.",
      "once": true
    }
  ]
}
```

The command hook writes `.needs-update` when it detects new data from the other machine. The prompt hook picks it up and runs the compilation.

## Adapting this

- **More than two machines**: Add more `raw/<machine-name>/` directories. The scanner and skill work with any number.
- **Different sync tool**: Replace iCloud with Dropbox, Google Drive, Syncthing, or even a git repo.
- **Different OS**: The scanner uses Python 3 and should work on macOS and Linux. The hook uses `stat -f %m` (macOS) — replace with `stat -c %Y` on Linux.
- **Team use**: Nothing stops this from working across team members' machines instead of one person's. Each person gets their own `raw/` directory.

## Requirements

- Claude Code
- Python 3.6+
- A folder sync solution (iCloud, Dropbox, etc.)
- Two or more machines running Claude Code

## Credits

Architecture inspired by [Andrej Karpathy's LLM Knowledge Bases](https://x.com/karpathy/status/1909364237498511558).

## License

MIT
