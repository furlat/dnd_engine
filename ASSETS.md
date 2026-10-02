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

Wall of Fire retains its complete pinned delivery in
`sources/wall-of-fire-20261001/`. `devtools/import_wall_media.py` installs the
82 original atlas pages (31,027,806 bytes) into `game/assets/wall_media/` and the
private production repository. Application selects frames 0–47; hold selects
48–111 at 32 FPS, sharing the same pages. Keep all four native camera rows,
front/back layers, crop offsets and pivot. These pages already fit 128×64 tile
supports at pixel scale 1; do not apply the character rig's tile scale. Rings,
diagonals, fine XYZ occlusion and physical height registration remain undelivered.
Public phase registrations and the independently authored cast recipe live in
`game/data/wall_media/`; spatial composition lives in `world_bindings.json`.

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

Fixed Fantasy windows preserve the full delivery in
`sources/fixed-windows-20261001/`. `devtools/import_windows.py` packs the approved
four-view selections into 66 production sheets/masks (21,128,454 bytes) under
`game/assets/environment/windows/`. These are copied into the private production
repository and included in its installer manifest. Public bindings remain in
`game/data/environment_art.json` and `game/data/window_media_sources.json`.
Keep uneven 24 FPS sample times, exact source pivots, selection masks, and both
parent-break variants; the after-insert variant prevents broken bars reappearing.

The October 1 passive environment batch preserves full sources in
`sources/environment-content-20261001/`. Its 53 native props use 306 additional
production PNGs (38,197,511 bytes) under `game/assets/environment/props/content-*`.
Use `devtools/import_environment_props.py --bank <authored-id>` for a bounded
selection, then the existing environment pager; preserve the accepted source's
12 FPS timing, frame count, pivots and row ordering. Installed and private copies
are included in `art-manifest.json`; the full local release now totals 4,945 files
and 2,858,909,585 bytes. Unselected/candidate art remains archived and unbound.

Install explicitly:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
```

Base release: `spell-fps32-20260924`, now extended by `fixed-windows-20261001`, following `cloud-two-second-20260924`
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

Fixed windows now retain the dense missing-frame delivery beside the original
sparse exports in `sources/fixed-windows-20261001/destruction-showcase/dense-production/`.
`devtools/import_windows.py` installs its112 directional sheets (128,033,920bytes)
and seven matching existing solid-wall banks. All source models/transforms remain
unchanged; dense bank times are24FPS,61frames except G9 insert37. Original intact
pixels and pivot160240 remain separate; never substitute the Blender rest render.

Window parent walls also carry separate aperture masks aligned with the intact
bank. These ten sheets exempt only the authored opening from finite actor-face
occlusion; selection masks and ordinary RGBA transparency have separate roles.
Solid sibling banks opt in without an aperture. Masks are preserved privately
with the production sheets and installer receipt.

Window insert destruction now comes from
`sources/fixed-window-inserts-20261001/`, passed as the required
`--insert-source` argument to `devtools/import_windows.py`. The old dense
`window` banks are combined previews: they include a standing parent wall and
must never be drawn as independent inserts. The replacement manifest explicitly
identifies insert-only components; all 36 sheets retain the original raw RGBA,
24 FPS timing, frames and registration. Full-parent and after-insert parent banks
are unchanged. Previous installed sheets remain preserved in
`sources/fixed-window-inserts-before-fix-20261001/`. Replacement media totals
7,462,104 bytes (previously 21,927,043); both installation manifests are updated.

Review floors use the four unchanged Fantasy Ground H1 paving sprites, registered
as `terrain.paving.*`. Source provenance is in `game/data/review_floor_source.json`;
originals are preserved in `sources/review-floor-h1-20261001/` and the private
production repository. The review recorder selects them for stone floors by
default; `--floor scene` restores the original scene bindings. No procedural
floor replacement, altered gameplay material or new rendering path is involved.

Environment registration corrections are preserved in
`sources/environment-content-20261001/placement-registration-20261001/`.
`game/data/environment_prop_sources.json` owns optional `ground_pivot` and
`pivots_by_pose` overrides; the importer applies them equally to intact and
breaking banks. Table anchors and two-cell cart/wagon/log registrations change
no pixels, frame counts, timing or scale. Sprite pose names follow
`game.projection.camera_pose`, not native cardinal rotation names. Keep the
original pivot as the geometric centre when authoring an offset anchor cell.
B13 remains a source hold; do not place it as a flat floor decal.

Wall heat accents preserve the complete delivery in
`sources/surface-ignition-20261001/`. `devtools/import_surface_contacts.py`
installs only eight directional formation banks, 48 frames at 32 FPS and original
paired camera layers: 64 atlas pages, 33,069,487 bytes. These are decorative
contacts; they do not create terrain. `devtools/import_wall_masks.py` preserves
`sources/wall-safe-mask-20261001/` and installs matching raw R8 masks
(4,119,132 bytes). Keep mask rectangles/pivots/clocks matched to original wall
crops. Masks classify native physical sides/base height; they are not XYZ data.
Tint copies RGB through the bounded frame cache and preserves original alpha.

October 1 diagonal Wall of Fire companion: preserve the complete pinned delivery
in `sources/wall-diagonal-20261001/`. Import with `devtools/import_wall_media.py
--merge`, then `devtools/import_wall_masks.py --merge`; these retain cardinal
registrations/masks and prior release receipts. Four new banks add 31,891,557
RGBA bytes and 3,903,128 mask bytes. Both physical-side masks travel with their
exact color/camera/frame crop. Canonical camera-relative reuse is visually accepted by the user. Preserve
full originals; production replacement still needs typed mapping integration.

Matched-height circular Wall of Fire originals are preserved in
`sources/wall-ring-gameplay-20261001/`. Existing merge importers install
27,629,255 RGBA bytes and 4,852,565 mask bytes, retaining four views, crop offsets,
original pivot and formation48/hold64 at32FPS. Public optional `wallRing` banks
register fixed radius10ft/width1ft. Donor outer/inner masks map to positive/negative;
safe outside tints front only, safe inside rear only. Whole-ring media requires
complete received shell coverage and no suppression; partial views remain an
explicit gap pending the requested matching ownership companion. No radius warp.

October 2 item media: preserve the complete `Stand-alone Character creator - 2D
Fantasy V1.3.zip` in `sources/item-equipment-20261002/`. The explicit public
`game/data/item_media_sources.json` selects 645 unchanged sheets, 86,538,120 bytes:
weapon/shield/offhand action banks, original Slash1/Slash2 Attack5 accents, and
separated apparel Idle frames. Import with
`uv run --no-sync python devtools/import_item_media.py --archive <original.zip>
--preserved /home/tommaso/Dev/neurodragon_art/sources/item-equipment-20261002
--production /home/tommaso/Dev/neurodragon_art-production`. The importer installs
private production and local assets, updates the production manifest, and writes
an exact SHA-256 receipt. Original alpha, frame clocks and pixels remain intact.
`game/data/item_appearances.json` explicitly registers category-qualified hand
substitutions and sampled ground frames/pivots/tints/contact shadows. Offhand
geometry reuse is approximate and accepted; floor apparel retains its separated
layer composite. The archive supplies no separate consumable bottle/potion art;
those ground appearances remain unbound.
