# Assets

| Location | Purpose |
| --- | --- |
| `/home/tommaso/Dev/neurodragon_art/` | Preserved full installed-art snapshot and inventory. Never prune or overwrite it to make a production build. |
| `/home/tommaso/Dev/neurodragon_art/sources/` | New original packs and full authored exports, kept privately. Existing external authoring projects stay in their own locations. |
| `/home/tommaso/Dev/neurodragon_art-production/` | Private production Git LFS repository: selected frames, shared payloads and packed sheets/geometry. Build separately from the archive. |
| `game/assets/` | Local installed production art. Ignored by Git; not the place to keep the only copy of an original. |
| `game/data/` | Public authored behavior, bindings, registration and schemas. The asset installer must not overwrite these. |

Keep pixels, binary geometry and generated previews private. Keep code and
authored JSON contracts public. Put review output in `.runtime/` or `output/`.
Importers update media registration/storage, never rewrite selected recipes.

Install explicitly:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
```

Current release: `recovery-cleanup-20260924`. Its packed paths require the matching
code/bindings; the original snapshot alone cannot replace this release. Normal
game startup does not install, scan or verify the asset library.

Keep the code revision paired with its art release. Preserve originals before
accepting a new delivery; regenerate production into a separate staging directory.
Private remote publication and removal from historical Git commits are separate
from ignoring/untracking the current files.

Detailed setup is in [PRIVATE_ART.md](PRIVATE_ART.md). Current packaging decisions
are in the [asset inventory](agent_docs/PRODUCTION_ASSET_INVENTORY_2026-09-24.md).
