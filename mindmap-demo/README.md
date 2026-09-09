# mindmap-demo

A **dummy** mind map that tests the "module -> h2 -> h3 -> leaf with a diagram"
navigation idea on a phone. It mirrors the real course shape used in
`modules/05-data-engineering-2/README.md` (the demo adds one dummy root level;
for real modules the module `#` heading would BE the root).

## Files

| File | What it is |
|---|---|
| `demo.md` | Human-readable source. Markdown headings = the tree; a list item that is only an image becomes a diagram node at the leaf. |
| `images/*.svg` | Dummy UML-style diagrams (stand-ins for real Mermaid/UML renders). |
| `demo-map.html` | **The interactive map** — self-contained, opens on any phone browser. |
| `build.sh` | Regenerates `demo-map.html` from `demo.md`. |

## How the content maps to the tree

- `## M5 — …` -> a module branch (one per module)
- `### Drift at ingestion …` -> an H2 section
- `#### Volume and arrival rate` -> an H3 subsection
- `##### Stage A — ingestion gate` -> a leaf "stage"
- bullets under it -> children of the stage; the image-only list item -> the diagram node

Navigation chain on the phone: **M5 -> Drift at ingestion -> Volume and
arrival rate -> Stage A** -> diagram.

## Why the build rewrites image URLs

markmap refuses `data:` image URIs and only keeps `<img>` elements for real
HTTP(S) URLs, so `build.sh` rewrites the relative `images/*.svg` references in
`demo.md` to absolute `raw.githubusercontent.com/akshayDev17/ML-Engineer/main/...`
URLs before rendering. Consequences:

- The images load **only after the repo is pushed to GitHub** (they 404 before).
- This works because the repo is **public**.
- `demo.md` itself keeps relative paths, so GitHub's Markdown preview renders it.

Regenerate after editing `demo.md` or `images/`:

```bash
bash mindmap-demo/build.sh
```

## Viewing on an Android phone (short version)

After `git push origin main`:

1. **Zero-setup:** open this in Chrome on the phone —
   `https://htmlpreview.github.io/?https://github.com/akshayDev17/ML-Engineer/blob/main/mindmap-demo/demo-map.html`
2. **Best:** enable GitHub Pages (repo Settings -> Pages -> Deploy from branch
   `main`, folder `/`), then open
   `https://akshaydev17.github.io/ML-Engineer/mindmap-demo/demo-map.html`
3. **Download:** GitHub app/browser -> repo -> `mindmap-demo/demo-map.html` ->
   Raw/download -> open the file with Chrome.

Gestures: **drag** = pan, **pinch** = zoom, **tap a circle** = expand/collapse
that branch; a floating toolbar (bottom-right) has +/−/fit controls.
