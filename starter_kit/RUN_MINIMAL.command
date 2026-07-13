#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUDIO_DIR="$SCRIPT_DIR/PUT_AUDIO_HERE"
REPORTS_DIR="$SCRIPT_DIR/REPORTS"
PROFILE="minimal"

finish() {
  echo
  read -r -p "Press Return to close this window..."
}

if ! command -v audioatlas >/dev/null 2>&1; then
  echo "AudioAtlas was not found. Install AudioAtlas first, or run this from an activated environment."
  finish
  exit 1
fi

mkdir -p "$AUDIO_DIR" "$REPORTS_DIR"

shopt -s nullglob nocaseglob
files=("$AUDIO_DIR"/*.wav "$AUDIO_DIR"/*.wave "$AUDIO_DIR"/*.flac "$AUDIO_DIR"/*.ogg "$AUDIO_DIR"/*.aiff "$AUDIO_DIR"/*.aif "$AUDIO_DIR"/*.mp3)
shopt -u nullglob nocaseglob

if [ "${#files[@]}" -eq 0 ]; then
  echo "Put one audio file into PUT_AUDIO_HERE, then run this again."
  finish
  exit 1
fi

if [ "${#files[@]}" -gt 1 ]; then
  echo "More than one audio file was found. Choose one:"
  for i in "${!files[@]}"; do
    printf "  %d) %s\n" "$((i + 1))" "$(basename "${files[$i]}")"
  done
  read -r -p "Enter a number: " choice
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#files[@]}" ]; then
    echo "Invalid selection."
    finish
    exit 1
  fi
  input="${files[$((choice - 1))]}"
else
  input="${files[0]}"
fi

stem="$(basename "$input")"
stem="${stem%.*}"
out_dir="$REPORTS_DIR/${stem}_${PROFILE}"

echo "Chosen file: $input"
echo "Output folder: $out_dir"
echo

audioatlas analyze "$input" --out "$out_dir" --graphs-profile compact
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "Report succeeded."
  echo "Output folder: $out_dir"
  echo "Open report.html to view the report."
  open "$out_dir/report.html" >/dev/null 2>&1 || true
else
  echo "Report failed."
  echo "Output folder: $out_dir"
fi

finish
exit "$status"
