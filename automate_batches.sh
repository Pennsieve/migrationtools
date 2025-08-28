#!/bin/bash

set -euo pipefail

# --- Config ---
MASTER_CSV="master.csv"
TEMP_PATHS="migration_paths.csv"
EPS_FILE="epsnumber.csv"
TOOLS_DIR="$HOME/migrationtools"
LOG_FILE="$TOOLS_DIR/migration_log.txt"

# --- Validate ---
[ ! -f "$MASTER_CSV" ] && { echo "Missing $MASTER_CSV"; exit 1; }
[ ! -f "$EPS_FILE" ] && { echo "Missing $EPS_FILE"; exit 1; }

# --- Initialize ---
> "$TEMP_PATHS"  # Clear existing migration_paths.csv
group=()
EPS_NUMBER=$(<"$EPS_FILE")
echo "Read in eps_number: $EPS_NUMBER"
((EPS_NUMBER++))
echo "working with: $EPS_NUMBER now"
if ! [[ "$EPS_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "❌ Invalid EPS number: $EPS_NUMBER"
    exit 1
fi

flush_group() {
    if [ "${#group[@]}" -eq 0 ]; then return; fi

    EPS_AUTO_NUMBER=$(printf "EPS%07d" "$((EPS_NUMBER))")
    echo "$(date '+%Y-%m-%d %H:%M:%S') ▶️ Starting group with $EPS_AUTO_NUMBER" | tee -a "$LOG_FILE"

    # Write current group to migration_paths.csv
    printf "%s\n" "${group[@]}" > "$TEMP_PATHS"

    # Run pipeline
    ./download.sh && /usr/bin/python3 merge_days.py ~/data/ && ./upload.sh

    echo "$(date '+%Y-%m-%d %H:%M:%S') ✅ Finished group" | tee -a "$LOG_FILE"
    # rm -rf ~/data/*

    # Reset group — we’ll handle increment outside
    group=()
    EPS_NUMBER=$(<"$EPS_FILE")
    echo "📍 EPSNUMBER READ IN: $EPS_NUMBER"
    echo "$EPS_NUMBER" > "epsnumber_sub.csv"
    echo "Wrote $EPS_NUMBER to epsnubmer_sub.csv"

}

# --- Read master.csv ---
while IFS= read -r line || [[ -n "$line" ]]; do
    # Trim whitespace
    line="${line%"${line##*[![:space:]]}"}"
    line="${line#"${line%%[![:space:]]*}"}"

    if [ -z "$line" ]; then
        flush_group
        echo "$EPS_NUMBER" > "$EPS_FILE"
    else
        group+=("$line")
    fi
    #EPS_NUMBER_SUB=$(<"$EPS_FILE")
    #((EPS_NUMBER_SUB++))
    #echo "$EPS_NUMBER_SUB" > "epsnumber_sub.csv"
done < "$MASTER_CSV"

# Flush final group if no trailing blank line
if [ "${#group[@]}" -gt 0 ]; then
    flush_group
    echo "$EPS_NUMBER" > "$EPS_FILE"
fi

echo "✅ All groups processed."
