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

New support-condition exports retain their 144 Hz originals in
`sources/support-batch-20260924/`. Use `devtools/repack_support_media.py` to build
separate 32 FPS production sheets, then `devtools/import_support_condition_media.py`
to install the selected group. Preserve durations, camera banks, pivots and crop
offsets; casting hands keep their rig frame rate. This packer handles billboards,
not paired XYZ/cloud banks. Recipes remain independently authored in `game/data/`.

Five maintained clouds now use two-second formation and two-second loops at
32 FPS from `sources/cloud-two-second-20260924/`. Import the five stationary
`cloud-two-second-surfaces-v1/<spell>/surface-manifest.json` entry points using
`devtools.import_persistent_spells.import_volume`. Source frames 0–63 become
application; 64–127 become hold, whose runtime start stays 0. Frame 128 is a
diagnostic duplicate, never playback. The optional rolling variants remain
archived and unbound; Cloudkill's rolling art has a fixed source +X bias.

Insect Plague retains `sources/cloud-height-companion32-v1/`. Production still
uses 24 ZIP banks containing matched RGBA/XYZ/ownership samples. Keep all three
coordinates; dropping Y prevents correct spherical clipping. Keep numerical
camera registration and crop pivots. Prior source banks remain in
`sources/short-cloud-loops32-v1/`, `sources/cloud-height-companion32-v1/` and the
previous releases; old XZ pages are in `sources/cloud-installed-before-xyz-20260924/`.

Install explicitly:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
```

Current release: `spell-fps32-20260924`, extending `cloud-two-second-20260924`
and the prior XYZ/support/cleanup releases. It contains **4,430 files / 2.669 GB**,
saving 1.616 GB (37.7%) from the preceding 4.285 GB installation. Selected media
for 248 spell asset records uses 32 FPS; actor animation and slower projectile
phases retain their authored clocks. Fireball's explosion uses 64 genuine samples
from its dense original. Full delivery sources are preserved in
`sources/spell-fps32-20260924/`. The five two-second clouds remain unchanged;
their complete XYZ archives occupy 636 MB instead of 1.963 GB.
Keep shared footpoint pages even when one consuming spell gets repacked.
Its paths require the matching frame registrations and hold lengths; the
original snapshot alone cannot replace this release. Normal game startup does
not install, scan or verify the asset library.

Keep the code revision paired with its art release. Preserve originals before
accepting a new delivery; regenerate production into a separate staging directory.
Private remote publication and removal from historical Git commits are separate
from ignoring/untracking the current files.

Detailed setup is in [PRIVATE_ART.md](PRIVATE_ART.md). Current packaging decisions
are in the [asset inventory](agent_docs/PRODUCTION_ASSET_INVENTORY_2026-09-24.md).
