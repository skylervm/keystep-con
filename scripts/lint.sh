#!/bin/sh
# Use installed development tools. No firmware input or device access.
set -e
cd "$(dirname "$0")/.."
ruff check .
"${ESLINT:-eslint}" .
