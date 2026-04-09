#!/bin/bash
# check-sync.sh — SessionStart hook for cross-machine learning
#
# Configure these two variables:
MACHINE_NAME="machine-a"  # Change to your machine's name
SYNC_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/claude-code-sync"  # Change to your sync folder

LAST_SCAN_FILE="$SYNC_DIR/raw/$MACHINE_NAME/.last-scan"
SCAN_INTERVAL_SECONDS=$((3 * 86400))  # 3 days

# Exit silently if sync folder doesn't exist
[ -d "$SYNC_DIR" ] || exit 0

needs_scan=false
scan_message=""

# Check if scan is due
if [ -f "$LAST_SCAN_FILE" ]; then
    last_scan=$(cat "$LAST_SCAN_FILE")
    now=$(date +%s)
    age=$(( now - last_scan ))
    if [ "$age" -ge "$SCAN_INTERVAL_SECONDS" ]; then
        needs_scan=true
        days_ago=$(( age / 86400 ))
        scan_message="Environment scan is ${days_ago} days old."
    fi
else
    needs_scan=true
    scan_message="No previous scan found."
fi

# Run scan if needed
if [ "$needs_scan" = true ]; then
    python3 "$SYNC_DIR/scripts/scan-environment.py" "$MACHINE_NAME" "$SYNC_DIR" >/dev/null 2>&1
    date +%s > "$LAST_SCAN_FILE"
    echo "[sync] $scan_message Fresh snapshot written."
fi

# Check for other machines' data
NEEDS_UPDATE_FLAG="$SYNC_DIR/.needs-update"

for other_snapshot in "$SYNC_DIR"/raw/*/latest.md; do
    [ -f "$other_snapshot" ] || continue

    # Skip our own snapshot
    other_dir=$(dirname "$other_snapshot")
    other_name=$(basename "$other_dir")
    [ "$other_name" = "$MACHINE_NAME" ] && continue

    # Check if other machine's snapshot is newer than wiki
    wiki_index="$SYNC_DIR/wiki/INDEX.md"
    other_date=$(stat -f %m "$other_snapshot" 2>/dev/null || stat -c %Y "$other_snapshot" 2>/dev/null || echo "0")
    wiki_date=$(stat -f %m "$wiki_index" 2>/dev/null || stat -c %Y "$wiki_index" 2>/dev/null || echo "0")

    if [ "$other_date" -gt "$wiki_date" ]; then
        echo "$other_name" > "$NEEDS_UPDATE_FLAG"
        echo "[sync] New data from $other_name detected."
    fi
done

# Surface pending suggestions
pending_file="$SYNC_DIR/suggestions/pending.md"
if [ -f "$pending_file" ]; then
    pending_count=$(grep -c "^- " "$pending_file" 2>/dev/null) || pending_count=0
    if [ "$pending_count" -gt "0" ]; then
        echo "[sync] $pending_count pending suggestions from cross-machine comparison."
    fi
fi
