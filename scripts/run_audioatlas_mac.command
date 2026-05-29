#!/bin/bash
set -e

cd "$(dirname "$0")/.."

mkdir -p input_audio output_reports

echo "AudioAtlas batch run"
echo "Input:  input_audio"
echo "Output: output_reports"
echo

audioatlas batch input_audio --out output_reports

if [ -f output_reports/catalog.html ]; then
  open output_reports/catalog.html || true
else
  echo "catalog.html was not created."
fi

echo
echo "Done. Open output_reports/catalog.html if it did not open automatically."
