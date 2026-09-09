#!/usr/bin/env bash
# Regenerate the self-contained mind-map HTML from the Markdown source.
#
# 1) demo.md references images relatively (images/*.svg) so it stays readable
#    and renders on GitHub's own Markdown preview.
# 2) markmap cannot use data: URIs, so the build rewrites image references to
#    absolute raw.githubusercontent.com URLs (works after you push to GitHub),
#    then renders the map with markmap-cli into demo-map.html.
#
# Usage:  bash mindmap-demo/build.sh      (from the repo root)
set -euo pipefail
cd "$(dirname "$0")"

# npm's global cache is broken (root-owned files); use a private cache here.
export npm_config_cache="${npm_config_cache:-$(pwd)/.npm-cache}"

REPO="${REPO:-akshayDev17/ML-Engineer}"
BRANCH="${BRANCH:-main}"
BASE="https://raw.githubusercontent.com/$REPO/$BRANCH/mindmap-demo"

node -e '
const { readFileSync, writeFileSync, mkdirSync } = require("node:fs");
const base = process.argv[1];
const md = readFileSync("demo.md", "utf8");
const out = md.replace(/!\[([^\]]*)\]\((images\/[^)\s]+)\)/g, (m, alt, path) => {
  return `![${alt}](${base}/${path})`;
});
mkdirSync("build", { recursive: true });
writeFileSync("build/demo-embedded.md", out);
console.log("Rewrote image refs to " + base + " -> build/demo-embedded.md");
' "$BASE"

npx --yes markmap-cli build/demo-embedded.md -o demo-map.html --no-open
echo "Built: mindmap-demo/demo-map.html"
