#!/usr/bin/env node
// Offline-capable build: turns demo.md into demo-map.html where EVERYTHING
// (d3 + markmap viewer + toolbar + CSS + diagrams) lives inside the one file.
//
// Why not just markdown images with data: URIs? markmap's Markdown parser
// refuses data: image URLs. Instead we transform to the markmap tree first,
// then rewrite <img> srcs in the tree JSON to data: URIs ourselves.
//
// Requires: node_modules deps under build/deps (see build.sh).

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const deps = join(here, 'build', 'deps');
const req = createRequire(join(deps, 'package.json'));
const { Transformer } = req('markmap-lib');

// ---- read + parse demo.md (strip YAML frontmatter, keep markmap options) ----
let md = readFileSync(join(here, 'demo.md'), 'utf8');
const options = { duration: 300 };
const fm = md.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
if (fm) {
  md = md.slice(fm[0].length);
  for (const key of ['maxWidth', 'initialExpandLevel', 'colorFreezeLevel']) {
    const m = fm[1].match(new RegExp(key + ':\\s*(-?\\d+)'));
    if (m) options[key] = Number(m[1]);
  }
}

// ---- transform markdown -> markmap tree ----
const transformer = new Transformer();
const { root } = transformer.transform(md);

// ---- embed images/*.svg as data: URIs in the tree content ----
const MIME = { svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif' };
function embedImages(node) {
  if (!node) return;
  if (node.content) {
    node.content = node.content.replace(/src="images\/([^"/]+)"/g, (m, file) => {
      const p = join(here, 'images', file);
      if (!existsSync(p)) return m;
      const b64 = readFileSync(p).toString('base64');
      const ext = file.split('.').pop().toLowerCase();
      return `src="data:${MIME[ext] || 'image/svg+xml'};base64,${b64}"`;
    });
  }
  (node.children || []).forEach(embedImages);
}
embedImages(root);
const treeJson = JSON.stringify(root).replace(/</g, '\\u003c');
const optsJson = JSON.stringify(options);

// ---- inline runtime assets ----
const read = (p) => readFileSync(join(deps, 'node_modules', p), 'utf8');
const d3js = read('d3/dist/d3.min.js');
const viewjs = read('markmap-view/dist/browser/index.js');
const toolbarjs = read('markmap-toolbar/dist/index.js');
const toolbarcss = read('markmap-toolbar/dist/style.css');

const html = `<!doctype html>
<html>
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=4.0, user-scalable=yes" />
<title>ML-Engineer mind map — offline demo</title>
<style>
* { margin: 0; padding: 0; }
html { font-family: ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'; }
#mindmap { display: block; width: 100vw; height: 100vh; }
.markmap-dark { background: #27272a; color: white; }
${toolbarcss}
</style>
</head>
<body>
<svg id="mindmap"></svg>
<script>${d3js}</script>
<script>${viewjs}</script>
<script>${toolbarjs}</script>
<script>
((r) => { setTimeout(r); })(() => {
  const { markmap, mm } = window;
  const toolbar = new markmap.Toolbar();
  toolbar.attach(mm);
  const el = toolbar.render();
  el.setAttribute('style', 'position:absolute;bottom:20px;right:20px');
  document.body.append(el);
});
</script>
<script>
(() => {
  const markmap = window.markmap;
  window.mm = markmap.Markmap.create('svg#mindmap', ${optsJson}, ${treeJson});
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.classList.add('markmap-dark');
  }
})();
</script>
</body>
</html>`;

writeFileSync(join(here, 'demo-map.html'), html);
console.log('Built offline-capable: mindmap-demo/demo-map.html (' + (html.length / 1024).toFixed(0) + ' KB)');
