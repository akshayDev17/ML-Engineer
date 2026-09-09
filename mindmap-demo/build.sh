#!/usr/bin/env bash
# Regenerate demo-map.html from demo.md.
#
# The output file is FULLY self-contained and works OFFLINE: d3, the markmap
# viewer, the toolbar and every diagram SVG are baked into the single HTML
# file (see build-offline.mjs for how diagrams become data: URIs in the tree).
#
# Usage:  bash mindmap-demo/build.sh      (from the repo root)
set -euo pipefail
cd "$(dirname "$0")"

# npm's global cache is broken (root-owned files); use a private cache here.
export npm_config_cache="${npm_config_cache:-$(pwd)/.npm-cache}"

if [ ! -d build/deps/node_modules/markmap-lib ]; then
  echo "Installing build dependencies (one-time)..."
  mkdir -p build/deps
  (cd build/deps && npm init -y >/dev/null 2>&1 && \
    npm install --no-audit --no-fund \
      d3@7.9.0 markmap-view@0.18.12 markmap-toolbar@0.18.12 markmap-lib@0.18.12)
fi

node build-offline.mjs
echo "Done. Open mindmap-demo/demo-map.html (works with no internet)."
