# mindmap-demo

A **dummy** mind map that tests the "module -> h2 -> h3 -> leaf with a diagram"
navigation idea — **online and offline**. It mirrors the real course shape used
in `modules/05-data-engineering-2/README.md` (the demo adds one dummy root
level; for real modules the module `#` heading would BE the root).

## Files

| File | What it is |
|---|---|
| `demo.md` | Human-readable source. Markdown headings = the tree; a list item that is only an image becomes a diagram node at the leaf. |
| `images/*.svg` | Dummy UML-style diagrams (stand-ins for real Mermaid/UML renders). |
| `demo-map.html` | **The interactive map — one self-contained file that works with ZERO internet** (viewer code + all diagrams are baked in). |
| `build.sh` | Regenerates `demo-map.html` from `demo.md`. |
| `build-offline.mjs` | The build logic (see "Why it works offline" below). |

## How the content maps to the tree

- `## M5 — …` -> a module branch
- `### Drift at ingestion …` -> an H2 section
- `#### Volume and arrival rate` -> an H3 subsection
- `##### Stage A — ingestion gate` -> a leaf "stage"
- bullets under it -> children of the stage; the image-only list item -> the diagram node

Navigation chain: **M5 -> Drift at ingestion -> Volume and arrival rate ->
Stage A** -> diagram.

## Why it works offline

`demo-map.html` is fully self-contained:

- the viewer (d3 + markmap + toolbar) and all CSS are **inlined** into the file,
- the diagram SVGs are embedded as base64 **data: URIs** directly in the map's
  data tree.

One subtlety: markmap's Markdown parser refuses `data:` image URLs, so the
build (`build-offline.mjs`) first transforms `demo.md` into the markmap tree,
then rewrites every `<img src>` in the tree to a data: URI — the file has no
`<script src>`, `<link>`, or `<img src="http…">` left in it at all. The same
file therefore also works perfectly online (GitHub Pages, htmlpreview, …).

Regenerate after editing `demo.md` or `images/`:

```bash
bash mindmap-demo/build.sh    # requires node + internet once (installs deps)
```

## Viewing on an Android phone

**Online (portfolio / sharing):** push to GitHub, then either

- GitHub Pages: repo -> Settings -> Pages -> Deploy from branch `main`, folder `/`,
  then open `https://akshaydev17.github.io/ML-Engineer/mindmap-demo/demo-map.html`
- or zero-setup preview:
  `https://htmlpreview.github.io/?https://github.com/akshayDev17/ML-Engineer/blob/main/mindmap-demo/demo-map.html`

**Offline:** download the single file once while you have a connection, then
open it any time with Chrome — no network needed after that:

1. GitHub app (or browser) -> repo -> `mindmap-demo` -> `demo-map.html` ->
   **⋮ -> Download** (saves the raw file).
2. In the Files/Downloads app, tap the file -> **open with Chrome**.
   (If your phone asks, always pick Chrome, not a text/HTML-code viewer.)
3. Verify: turn on airplane mode, open it again — it still works.

Gestures: **drag** = pan, **pinch** = zoom, **tap a circle** = expand/collapse;
a floating toolbar (bottom-right) has +/−/fit controls.
