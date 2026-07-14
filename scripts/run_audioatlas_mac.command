#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INPUT_DIR="$PROJECT_DIR/input_audio"
OUTPUT_DIR="$PROJECT_DIR/output_reports"

finish() {
  echo
  printf "Press Return to close this window..."
  read -r || true
}

if ! command -v audioatlas >/dev/null 2>&1; then
  echo "AudioAtlas was not found. Install it first, or run this from an activated environment."
  finish
  exit 1
fi

mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"

echo "AudioAtlas batch run"
echo "Input:  $INPUT_DIR"
echo "Output: $OUTPUT_DIR"
echo

audioatlas batch "$INPUT_DIR" --out "$OUTPUT_DIR"
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "AudioAtlas completed successfully."
  if [ -f "$OUTPUT_DIR/catalog.html" ]; then
    open "$OUTPUT_DIR/catalog.html" >/dev/null 2>&1 || true
  else
    echo "catalog.html was not created."
  fi
else
  echo "AudioAtlas failed with exit status $status."
  echo "Review the messages above; existing files were left in place."
fi

finish
exit "$status"
