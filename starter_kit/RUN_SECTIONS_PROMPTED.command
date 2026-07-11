#!/bin/bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUDIO_DIR="$SCRIPT_DIR/PUT_AUDIO_HERE"
REPORTS_DIR="$SCRIPT_DIR/REPORTS"

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

read -r -p "Number of sections: " section_count
if ! [[ "$section_count" =~ ^[0-9]+$ ]] || [ "$section_count" -lt 1 ]; then
  echo "Enter a section count of 1 or more."
  finish
  exit 1
fi

section_args=()
for ((i = 1; i <= section_count; i++)); do
  echo
  read -r -p "Section $i name: " section_name
  read -r -p "Section $i start time in seconds: " section_start
  if [ "$i" -eq "$section_count" ]; then
    read -r -p "Section $i end time in seconds (blank for EOF): " section_end
  else
    read -r -p "Section $i end time in seconds: " section_end
  fi
  section_name="${section_name//:/_}"
  section_args+=(--section "$section_name:$section_start:$section_end")
done

stem="$(basename "$input")"
stem="${stem%.*}"
out_dir="$REPORTS_DIR/${stem}_sections"

echo
echo "Chosen file: $input"
echo "Output folder: $out_dir"
echo

audioatlas sections "$input" --out "$out_dir" "${section_args[@]}"
status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "Section report succeeded."
  echo "Output folder: $out_dir"
  echo "Open report.html inside a section folder, or open section_index.md."
  open "$out_dir" >/dev/null 2>&1 || true
else
  echo "Section report failed."
  echo "Output folder: $out_dir"
fi

finish
exit "$status"
