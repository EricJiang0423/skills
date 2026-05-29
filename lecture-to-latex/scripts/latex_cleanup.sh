#!/usr/bin/env bash
set -euo pipefail

root="${1:-.}"

find "$root" \
  \( -name "*.aux" \
  -o -name "*.log" \
  -o -name "*.out" \
  -o -name "*.toc" \
  -o -name "*.fls" \
  -o -name "*.fdb_latexmk" \
  -o -name "*.synctex.gz" \) \
  -type f \
  -delete
