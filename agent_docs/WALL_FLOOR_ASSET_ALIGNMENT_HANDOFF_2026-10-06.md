# Wall, doorway and floor alignment — manual asset review handoff

## October 6 numerical and native audit follow-up

See [the production registration and animation audit](audits/WALL_FLOOR_ASSET_ALIGNMENT_AUDIT_2026-10-06.md)
for the static-versus-destruction binding inventory, source continuity measurements,
owner/camera contracts, sampled native comparisons, and bounded repair proposals.
All 112 directional destruction atlases and 76 original intact component crops
preserve their sources; the separate intact-to-frame-0 comparisons are not exact.
The audit adds no production artwork or rendering/collision changes. Its four-view
evidence gallery is served locally at http://127.0.0.1:8794/.

Final receipts: 216 focused tests passed; 102 native cases / 408 captures,
including full-parent cascades, independent wall/insert highlights, mid-window
crawl and raised-door passage. Four preserved original solid-wall explosion
sequences are present, with all 64 recovered image hashes verified; native
per-family matching remains uncertified. The durable JSON inventory is saved
beside the audit Markdown. Do not report plain-wall source effects as universally
missing or substitute window-wall banks for solid/corner media.

## Follow-up: lighting fixed; plain-wall destruction is a separate gap

The October 6 wall-check captures now include two further bounded corrections:
walls use observed incident-support lighting, matching the door path rather than
constant 62% brightness; the entrance desk is at (2,4), away from the wall base.
All four cameras were checked. See the UI repair audit for regression receipts.
The older before/candidate diagnostics retain the old lighting.

The human also asked why walls are not animated. Current source evidence:

- `build_directional_wall()` creates `environment.directional_wall`, with
  `DirectionalWall.is_targetable=False` and no authored destruction bank.
- `devtools/import_windows.py` imports the seven solid siblings A1, C1, D1, D8,
  F1, F8 and G1 as one-frame intact banks. Each
  `game/data/environment_art.json` prop has `destructions: {}`.
- Window parent walls and inserts have their own break banks; those walls
  contain an opening and cannot substitute for intact solid masonry.
- D2 joined corners use the legacy static composite. No installed matching D2
  destruction bank has been identified.

Thus this is not evidence that every plain wall was delivered/animated, nor a
lighting-specific problem. Check preserved source deliveries for actual matching
solid/corner destruction media before proposing new art. Record missing source
media versus unintegrated source media separately. A future integration must use
the existing item destruction and boundary lifecycle, retaining source geometry
and normal attack/area-damage behavior; do not create another wall system.

## Scope and current result

The human reported stepped wall joins, apparent floor/wall penetration and a wall
base occupying too much of the tile in the Lantern Crypt UI captures. Fix the
reported scene first, then hand this wider asset audit to another agent **through
the human**. No other-chat communication is authorized.

The visible discontinuities in the entrance room were reproduced and corrected
in `dnd/scenarios/battlefield_catalog.py`. Native movement barriers were correct,
but two internal partitions used the opposite owner side from their adjoining
outer walls. The source masonry has thickness inset into its owner cell; these
opposite registrations are not visually interchangeable.

| Partition | Previous mount | Corrected mount | Unchanged physical edge |
|---|---|---|---|
| Entry → passage, y=5..7, door at y=6 | (8,y), WEST | (7,y), EAST | x=7.5, y±0.5 |
| Entry → vault, x=4..7, door at x=5 | (x,9), SOUTH | (x,8), NORTH | y=8.5, x±0.5 |
| Passage → hall, y=5..7 | (12,y), WEST | unchanged | x=11.5, y±0.5 |

The entrance's east and north walls now join in one existing D2 corner at (7,8).
The passage preview uses the corrected mount as well. Door names, destinations,
channel blocking, floor cells and sprite registrations are retained. No new
renderer offsets, clipping masks, art, collision rules or wall system were added.

**This closes the reported entrance-room joins, not a full library acceptance.**
The floor/base overlap and actual thickness versus the engine edge remain
explicit subjects of the broader numerical and visual audit below. Do not treat
an attractive closed-room screenshot as proof of every wall's geometry.

## Evidence

Workspace: `/mnt/c/users/tommaso/documents/dev/dnd_engine`.

- Corrected actual gameplay: `.runtime/ui-repair-20261006/wall-check/fixed-native-q0.png`
  through `fixed-native-q3.png`; all four native captures report zero presentation gaps.
- Controlled before/after geometry comparison: `wall-check/before-q0.png` through
  `before-q3.png` and `candidate-q0.png` through `candidate-q3.png`. Candidate
  images change only the two projected mounts for diagnosis; the `fixed-native`
  images come from the corrected native scene, not those modified packets.
- Original user crop was recovered from
  `/mnt/c/Users/tommaso/AppData/Local/Temp/codex-clipboard-c9550b05-2e26-4237-893c-2064c2f317a5.png`.
- Numeric production excerpt:
  `.runtime/ui-repair-20261006/wall-check/registered-assets.json`.
  It lists 36 static resources, seven solid sibling registrations, ten window
  parents/nine independent inserts, 17 door registrations (including the generic
  alias), and 164 referenced banks with first/last frame regions. This is a data
  inventory, not proof all those resources were visually checked.
- `wall-check/session-tests.log`: complete `tests/game/test_session.py`,
  **4 passed in 5.09s**. The native Crypt case verifies sealed room routes and
  successful access after opening each of its three doors.
- Actual UI captures are refreshed in the existing UI gallery at all three
  supported review resolutions. No source sprites are altered in these captures.

## Existing numeric contracts to inspect first

Read `ASSETS.md` before changing/importing artwork.

- `game/projection.py`: one cell = 128×64 projected pixels; one elevation step
  = 64 pixels. Engine NORTH is (0,+1), EAST (+1,0). Poses and camera quarters
  have one `camera_pose` conversion. Sprite pivots use the owner-cell contact;
  painter ordering uses the physical boundary. Those are different quantities.
- `game/data/assets.json`: legacy D1 straight, D2 corner and D6 doorway frames
  have source canvas 256×256, pivot (128,207.36), scale 128/127.
  Stone Ground D1 uses (128,208), scale 1. These small registration differences
  exist; do not blame them for the much larger owner-side discontinuity without
  measuring actual pixels and source occurrence evidence.
- `game/data/environment_art.json`: animated Fantasy A1 doorway has canvas
  256×256, mounting pivot (128,209.92), scale 128/127. Its per-pose geometric
  ground origins differ and decode depth; they must not replace mounting pivots.
- Fixed window banks and their seven solid siblings use a 320×320 padded canvas,
  pivot (160,240), scale 1. Intact 256×256 pixels start at (32,32), equivalent to
  original pivot (128,208). `devtools/import_windows.py` preserves these values.
  Matching legacy D1 and fixed D1 images therefore use different registrations;
  examine joins across the paths, not just each bank in isolation.
- `game/data/window_media_sources.json`: window families A4, A5, C4, D16, D7,
  F16, F7, G7, G8, G9; solid siblings A1, C1, D1, D8, F1, F8, G1.
- `game/data/environment_art.json` door `pose_offset` is nonzero for Fantasy C1,
  C3 and Desert C7, C9. Inspect their real physical edge and matching frame;
  the source pose suffix alone is not its world direction.
- `game/data/stone_floor_source.json` and `review_floor_source.json` retain the
  original Ground D1 and H1 provenance. Inspect ground top plane and slab side
  independently; the bottom of the entire alpha bounds is not the floor contact.

Preserved source material includes
`/home/tommaso/Dev/neurodragon_art/sources/fixed-windows-20261001/`.
Its model fit and source-registration JSON provide measured geometry, original
canvas/padding and aperture locations. Original file status labels may describe
an earlier draft: compare them with the later accepted delivery and production
bindings. Do not silently assume a status string certifies or rejects the pixels.

## Prior studies with relevant evidence

1. `agent_docs/DND_PYGAME_V0_BOUNDARY_GEOMETRY_DEPTH_CORRECTION_PLAN_2026-09-03.md`
   — exact D1/D2/D6 family, pivots, camera table and corner ownership. Its
   historical sorting sections are not a replacement for current rendering.
2. `agent_docs/DND_PYGAME_V0_DOORWAY_PRESENTATION_FOLLOWUP_2026-09-03.md`
   — earlier doorway join was explicitly not certified fixed by source metadata.
3. `agent_docs/audits/RENDER_XYZ_AUDIT_2026-09-23.md`, finding 3 — native height-2
   wall raster cap extends beyond its zero-thickness occluder; measured far-side
   rays crossed at height 2.0036..2.2542 and affected 267 cap pixels. Reproduce
   against current code before assuming this historical finding still behaves
   identically. Do not raise gameplay wall height or mask all VFX as a shortcut.
4. `agent_docs/WINDOWS_IMPLEMENTATION_PLAN_2026-10-01.md` and
   `agent_docs/DOORS_AND_TRAP_DESTRUCTION_2026-09-21.md` — aperture transparency,
   owner-side clipping, doors, independent inserts and destruction registration.

## Required manual audit and deliverable

Use existing assets and existing runtime. Keep findings separate from proposed
repairs. Before implementation planning, obtain anti-slop and anti-OOP/ECS review
of any shared registration/rendering change; do not build another wall framework.

For each family, record source, canvas/padding, mounting pivot, scale, physical
edge, visual base extent, top extent, opening extent and camera/pose mapping.
Then show actual game comparisons of:

- a continuous run and a doorway/window within it, across all four camera views;
- both possible incident owner cells for the same edge, with numeric transforms;
- convex and concave corners and T junctions, including joins whose owners differ;
- ground-only, wall-only and combined views with diagnostic cell boundaries;
- a creature at the adjacent cell centre, movement alongside and through an open
  door/window, including the selected target and shadow;
- closed/open/reclosed/broken doors and intact/insert-broken/parent-broken windows;
- ordinary stone floor versus accepted H1 paving, including slab undersides;
- representative raised supports and finite camera zooms after flat alignment.

Distinguish (a) bad scene ownership, (b) wrong imported registration, (c) actual
source shape/thickness, (d) sorting/clipping, and (e) physics versus picture.
Report the floor/base complaint directly: how much of the interior cell is
covered and whether the actor's legal footpoint is inside the visible base.
Do not fix it by concealing the floor, shrinking sprites, inventing an offset,
changing collision height, or rescaling the whole library without source proof.

Deliver a compact issue table with numeric evidence and labeled before/after
in-game images, then the smallest justified repair proposal for each real defect.
The current room fix does not authorize new artwork or a general renderer rewrite.
