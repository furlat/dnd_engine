# Production-gap selected asset intake — 4 October 2026

Scope: step 1 of `agent_docs/SPELL_GAP_INTEGRATION_PLAN_2026-10-04.md` only.
`devtools/import_production_gap_media.py` preserves and installs the accepted
`production-gaps-20261004-v1` selection using the existing verified-payload
installer and projectile storage. It does not edit recipes or runtime consumers.

Source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/production-gap-delivery-2026-10-04`.
Preserved originals: `/home/tommaso/Dev/neurodragon_art/sources/production-gaps-20261004`.
Installed copies: local `game/assets/` and `/home/tommaso/Dev/neurodragon_art-production`.
Source `media.json` SHA256: `46c1ed40e37dd25191a198a355d2340e3130a6c540cb5165e4486aff36cfae49`.
Source `delivery-receipt.json` SHA256: `941f36df34d9be54884579bef87737bb875513cc0941ece62ad860927022fc52`.

| Bundle | Selected identities | Files / bytes |
| --- | --- | --- |
| `weather_solar_media` | `weather.cone.{near,middle,far,ground}` and `weather.cone.contact.{back,front}` | 102 / 61,035,985 |
| `lightning_media` | `lightning.call_lightning.v5.q0` through `.q3` | 4 / 2,007,139 |
| `wall_media` | `wall.wind.block.h0` through `.h7`, plus continuous original components | 10 / 473,185 |

Total: **116 files / 63,516,309 bytes**. This is 112 unchanged RGBA atlas pages
from 46 selected banks, three unchanged donor textures, and one extracted mesh/
parameter record. No Thorns banks are duplicated. Source metadata and required
donors are copied only from explicit receipt entries; directories are not copied
recursively. Each bundle's `production-gap-source.json` retains source hashes,
selected identities, original paths, complete pivots and depth values. The
previous private production manifest is preserved before installation.

## Registration for the existing consumers

All banks retain 32 FPS and their explicit empty frames. No RGB/alpha rewriting,
crop repacking, rescaling or 2D rotation occurs. Source samples represent
`(frameIndex+1)/32` seconds. Recipe clocks remain the caller's responsibility.

| Selection | Cell / frames | Capture zoom | Original pivot | Pixel scale at reference zoom |
| --- | --- | --- | --- | --- |
| Cone field/ground | 1024 / 96 | 0.67 | Per facing, in receipt | `1/0.67` |
| Cone recipient back/front | 512 / 48 | 0.85 | `[256,309.300896802962]` | `1/0.85` |
| Call Lightning q0–q3 | 768 / 48 | 0.75 | `[384,560.3632614803888]` | `1/0.75` |
| Wind interception h0–h7 | 384 / 32 | 1 | `[192,210.47520861406804]` | `1` |

Each Cone asset uses existing `partsByFacing` and `anchorsByFacing`.
`E,SE,S,SW,W,NW,N,NE` map to source `h7,h0,h1,h2,h3,h4,h5,h6`.
Source +X is therefore SE, matching existing solar delivery. Camera-relative
heading is `(worldHeading + 2*gameCamera)%8`; no new asset selector is needed.
Call retains four separate original camera banks. Wind raster banks retain their
literal heading; arbitrary tangents consume the continuous source below.

The exact required drawing scale is `camera.zoom/captureZoom`. In the current
cast consumer, whose existing tile/rig factor is 2, corresponding track scales
are `1/(2*0.67)`, `1/(2*0.85)`, `1/(2*0.75)` and `0.5`. These are recipe values,
not additional resizing in the importer. Asset default scale remains 1.

Cone depth bands are portions of one finite field, not flight stages. The
canonical X+Z depth offsets below add to the caster ground depth. Exact
unrounded values are in `weather_solar_media/production-gap-source.json`.

| Facing | Near | Middle | Far |
| --- | ---: | ---: | ---: |
| E | -5.048151990409 | -0.000000000000004 | 5.048151990409 |
| SE | 2.25 | 6.75 | 12 |
| S | 2.828427124746 | 8.485281374239 | 14.142135623731 |
| SW | 2.25 | 6.75 | 12.546793048271 |
| W | -5.048151990409 | 0.000000000000001 | 5.048151990409 |
| NW | -13.411321747118 | -8.046793048271 | -2.682264349424 |
| N | -14.142135623731 | -8.485281374239 | -2.828427124746 |
| NE | -13.411321747118 | -8.046793048271 | -2.682264349424 |

Ground remains a separate transient terrain-composited image. The delivered
three depth bands do not claim arbitrary per-pixel actor occlusion or XYZ data.
Call's accepted contact is release plus 31.25 ms; the captured volume's bounds
are presentation bounds, not gameplay targeting or cloud geometry.

## Continuous Wind donor

Resources `/wind/block-components.json` and `/wind/block-texture.png` point to
the original K1 cross-plane mesh and `T_WindWave_Single_A1.png` (RGBA735×1030).
Godot 4.6.2 loaded `VFX_WindHit_K1.tscn` headlessly and exported its one mesh
surface: eight vertices, twelve indices, and original UVs. The tiny imported
plane coordinates `-0.0000152587890625` are retained. No frames were rendered and
the source project was not edited. Export script, command and log are archived.

The component retains five instances; stagger `.022` seconds, duration `.70`,
scale `[.33,.48,.33]`, yaw step `1.1`, base RGB `[.78,.87,.91]`, opacity `.66`,
5×2 sprite sheet, horizontal units/cell `2.121320344`, and vertical units/cell
`sqrt(3)`. Frame index is `floor(u*9)`; UVs divide by `[5,2]` and add the frame
offset. Shader output is fixed RGB and sampled source alpha times the original
opacity envelope. The adapted shader is unshaded, double-sided and does not
write depth. Original K1 particle emitter randomness is not used: the accepted
component explicitly instantiates five ordinary meshes.

`wall_media/production-gap-source.json` records the exact position, growth,
opacity, orientation and postprocess equations. The unchanged GDScript is
preserved. Palette mapping samples the lower-right RGB of each source 2×2 block,
selects the nearest original sRGB palette color, retains original alpha and
zeros alpha below 3. No additional unpremultiplication is authorized.

## Cone body-material dependencies

Registered unchanged `/cold/freeze-noise.png` and `/cold/freeze-normal.webp`.
The accepted `cold-weather-batch/cone-of-cold-v1/body-material.js`, notes and
`review.js` are preserved. Body-material SHA256:
`4159ab3b46d9e9e013fb9f069ea4b77988f9ad071337ff3af3ac6fea56a81b71`.
Noise SHA256: `9cd820fc0e056d10127a518d840627e222af68010816cba963bbfec468bde5f8`.
Normal SHA256: `200f813f31da7cdfc8aed56a76d3a8efca1427eb14a432c7a9564c6901de19fa`.

Survivor amount is `.33*ease(0,.06,t)*(1-ease(.28,.75,t))`, with frozen=false.
The shader's cold ramp is `[.4307,.54221,.59]` to `[.753754,.934002,1]`, combined
with the original noise, normal, reveal and facet equations. The source's fixed
TakeDamage4 statue pose is a preview choice, not a new native status or required
body-pose override. Runtime material integration belongs to the parent lane.

## Verification

- `tests/game/test_production_gap_media_import.py`: **6 passed in 2.64 s**.
  Covers exact pixels/crops/pivots, full selection, existing recipes/resources,
  repeat installation, and checksum/crop/missing-bank/path-escape/missing-export
  rejection before installed changes.
- Importer typing: **0 errors, 0 warnings**. Scoped `git diff --check`: passed.
- All 116 local/private payload hashes and all archived originals verified.
- Exact source crop/pivot/page parity: **46 distinct banks / 7,424 registered
  facing-frame addresses**.
- Fresh ordinary `load_animation_data()`: all 18 new assets loaded among 1,091
  current assets at this checkpoint.

Evidence: `.runtime/production-gap-intake-20261004/{install.log,tests-final.log,typing-final.log,installed-verification.log,export.log,diff-check.log}`.
This is an asset-intake checkpoint; runtime/galleries and independent reviews
remain in their assigned parent/reviewer lanes.
