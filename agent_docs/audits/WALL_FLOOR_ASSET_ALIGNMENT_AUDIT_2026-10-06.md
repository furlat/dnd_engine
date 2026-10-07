# Production wall/floor registration and animation audit — 2026-10-06

The import and frame-registration checks pass. That does **not** certify every wall's physical thickness or every join. Ordinary structural walls are static and are not directly attackable by default; the delivered window parents and inserts have separate finite destruction banks. Seven imported solid siblings have intact images but no destruction binding. These are different asset paths, not an animation toggle on one wall family.

This is a follow-up to [the production handoff](../WALL_FLOOR_ASSET_ALIGNMENT_HANDOFF_2026-10-06.md). It changes no production artwork, game data, renderer, collision, or scene ownership. Existing production changes were retained, including the corrected Lantern Crypt partitions. Plans were reviewed by the required anti-slop and anti-OOP/ECS reviewers. No other chat was read or messaged.

## What production should distinguish

| Path | Intact media | Break media / native mechanics | Production implication |
|---|---|---|---|
| `environment.directional_wall` | Legacy stone D1/D2 or wood C1/C2 | No bound destruction bank; `DirectionalWall.is_targetable=False` | A static native boundary. An installed animation elsewhere does not make this item destructible. |
| `environment.wall.fantasy_{a1,c1,d1,d8,f1,f8,g1}` | Seven one-frame solid siblings | `destructions: {}`; these imports are art prop registrations, not seven authored destructible item constructors | Exact intact reuse exists. They must not be counted as delivered animated solid walls. |
| `environment.window.fantasy_{a4,a5,c4,d16,d7,f16,f7,g7,g8,g9}.wall` | One-frame parent; nine independent inserts, none on G7 | Native targets, HP, supported attachments; full-parent break and, where applicable, parent break after insert destruction | Keep parent and insert targets separate. Breaking the parent also destroys its supported insert; the full-parent break incorporates the intact insert once. Native inert wreck state is retained. |
| Window inserts | One-frame intact insert | Independent insert-only break bank; 61 frames, except G9 insert: 37 | Insert destruction does not destroy the supporting wall. Selection masks and transparent openings are separate data. |
| Doors | Explicit closed/open poses and finite swing banks | Native opening/reclosing and destruction; 17 registrations including the generic compatibility alias | Source pose suffix, physical direction, and camera pose must be decoded together. |

Window parent breaks have 61 samples over 2.5 seconds. G9 insert has 37 over 1.5 seconds. The recorded boundary clearance remains frame 10, approximately 416.7 ms. Selection of full-parent versus after-insert media follows recorded intact supported attachments, not camera direction or material. An intact one-frame bank is expected; “animated” here means a finite state transition, not an idle wall animation. Opening-window reconstruction remains outside this audit and the previously stopped track.

Existing native paths: `dnd/content/items/environment_item_builders.py`, `dnd/items/environment.py`, `dnd/content/items/window_builders.py`, `game/environment_art.py`, and `game/choreography.py`. Do not create a second wall lifecycle to resolve a missing binding.

## Compact findings and smallest justified next actions

| Finding | Evidence and significance | Smallest justified next action |
|---|---|---|
| **Verified: imported originals and deliveries are preserved** | All 112 directional destruction atlases match the preserved source hashes and registrations. All 76 intact component crops retain the original RGBA pixels. 13,968 selected frame rectangles are valid. Eight floor images match their authored provenance hashes. | Keep these imports. Reimporting identical deliveries will not repair source continuity or scene ownership. |
| **Source continuity discrepancy: intact versus destruction frame 0** | None of the 112 premultiplied-RGBA comparisons is exact. This includes 40 full-parent compositions, 36 after-insert parents, and 36 insert-only banks. Full-parent reference is **intact parent plus intact insert**, not parent alone. Transparent RGB is ignored. | Inspect the existing delivered transition against the original rest composition, distinguishing intentional damage changes from displacement/silhouette errors. Correct source registration/geometry only where that review proves a defect; check subsequent frames too. Do not paste an exact frame 0 over a misregistered sequence or compensate with renderer offsets. |
| **Binding/mechanics gap: ordinary walls and solid siblings are static** | Generic walls are not attack targets. Seven solid sibling props have empty destruction maps. Legacy D2 joined corners have no identified installed matching break bank. Four original solid-wall explosion sequences are present: 16 recovered images each, all 64 matching their original hashes. This does not certify native timing, source poses, pivots or exact replacement for each family. | Match the inventoried solid/corner effects before planning integration. Separate “source missing,” “source present but uncertified,” and “certified source unbound.” Admit matching media through existing native item destruction; never substitute a window parent for solid masonry. No new walls should be generated for this audit. |
| **D1 has two registrations for identical original pixels** | All four D1 originals match raw pixels. Legacy: pivot `(128,207.36)`, scale `128/127`. Padded fixed: equivalent original pivot `(128,208)`, scale `1`. Legacy full canvas width is 258.016 px versus 256 px. Top-left relative to contact is `(-129.008,-208.993)` versus `(-128,-208)`. C1 originals and equivalent registrations agree. | Treat mixed D1 runs as a registration risk, not proof of a large current seam. Sampled native mixed-run views showed no large discontinuity at zoom 1. Find the original prefab registration before unifying either path; do not rescale the entire library. |
| **Same physical edge does not imply interchangeable owner art** | `(x,y),EAST` and `(x+1,y),WEST` share the physical edge but their owner contacts differ by a full projected cell, `(64,32)` px at camera 0. The source thickness lies on opposite incident sides. This is much larger than the D1 registration difference above. | Preserve the existing Crypt ownership corrections. Choose owners consistently from adjacency and wall-side semantics. Do not move every sprite to the physical edge midpoint or invent per-scene pixel nudges. |
| **Corner grouping differs between static boundaries and registered props** | Legacy perpendicular walls sharing owner cell, base, and material can select the existing D2/C2 composite. Registered environment props use a separate existing draw path and bypass that grouping. Native convex/concave/T and registered-convex fixtures are captured separately. | Do not assume importing a solid sibling grants joined-corner behavior. Author corners through the existing adjacency/ownership rules; resolve any requested mixed-path join explicitly before exposing it in a constructor. Do not draw a duplicate corner over two full straight walls. |
| **Physical base thickness is not certified by the current data** | Projected opaque coverage of the owner diamond is 76.04–76.07% for front D1 E/S, about 37.00% for W/N; C1 ranges 19.73–68.16%. D1 E/S also covers the projected legal cell-centre contact (alpha 255), while W/N does not (alpha 0). This is silhouette coverage, not the amount of ground occupied by the base. | Do not claim the actor's legal footpoint is physically inside masonry from this image measurement. Certify irregular base geometry from the original prefab/source before changing collision, placement, or clearance. Keep floor top contact distinct from slab bottom alpha. |
| **Raster cap extends beyond a native zero-thickness height-2 wall ray** | D1 E/S reaches 2.257638 elevation steps over the physical-edge ray, with 856/859 opaque cap pixels above height 2 under this measurement. W/N reaches 1.997795. C1 E/S reaches 2.167969/2.160156. This measures raster versus native plane, not physical source geometry. | Retain the native height. Reproduce a current runtime cap/VFX leak before proposing an occlusion change; use source geometry if such a defect is verified. Do not raise gameplay height or mask all effects. |
| **Blender source proxy is not a certified native-cell footprint** | Under the installed mount, proxy normal centres range 0.3631–0.4469 cells versus native edge 0.5; projected endpoint spans range about 68.71–75.48 by 34.89–36.88 px versus native 64 by 32. Source units are proxy art units and its anchor is world origin, not wall midpoint. | Keep these as diagnostics only. Draft proxy fit/status and later accepted pixels are different evidence. Neither a proxy scale nor an acceptance label warrants shifting original sprites. |

The cap measurement above uses lateral rays inside the physical segment and alpha ≥128. Its denominator differs from the earlier September 23 “267 cap pixels” study; this is not an exact reproduction of that historical count or a runtime VFX failure.

### Source continuity examples, full-parent / E

| Family | Changed premultiplied-RGBA pixels | Changed alpha pixels | Premultiplied RGB RMSE, 0–255 scale | RGBA L2 |
|---|---:|---:|---:|---:|
| A4 | 8,765 | 1,739 | 9.193 | 9,264.306 |
| D7 | 10,782 | 2,687 | 13.576 | 13,306.209 |
| G9 | 7,291 | 1,229 | 4.956 | 6,383.317 |

All four source views for every family are shown together with intact/frame-0/error images. Those are unlit installed-media diagnostics. The separate native attack captures include legitimate hit flashes; their screen RGB differences must not be attributed entirely to asset discontinuity. Numerical non-identity alone does not establish subjective popping or a broken animation.

## Positioning contracts checked

- One tile is 128×64 projected pixels; one elevation step is 64 pixels. NORTH is `(0,+1)`, EAST is `(+1,0)`. Mount sprites at their owner contact; derive painter contact from the physical boundary. These contacts have different purposes.
- Camera quarters 0..3 map NORTH to `s,w,n,e`, EAST to `e,s,w,n`, SOUTH to `n,e,s,w`, WEST to `w,n,e,s`. Door `pose_offset` is inverted before source-row selection. Fantasy C1/C3 and Desert C7/C9 have nonzero offsets.
- Fixed windows/solid siblings: padded 320×320, original begins `(32,32)`, pivot `(160,240)`, scale 1. This is original pivot `(128,208)` without padding.
- Legacy D1/D2/D6: 256×256, pivot `(128,207.36)`, scale `128/127`. Stone Ground D1 and H1: pivot `(128,208)`, scale 1. Ground D1 includes slab side below its top contact; bottom-of-alpha is not its mounting pivot.
- Animated Fantasy A1 doorway: mounting pivot `(128,209.92)`, scale `128/127`. Its per-pose `ground_origins_by_pose` inform geometric depth and must not replace the mounting pivot.
- Native physical edge, wall base/cap, aperture, actor occlusion, selection highlight, and source alpha bounds are separate quantities. Legacy wall actor clipping defaults differ from registered props. A selection mask is not a collision footprint or occlusion mask.

Per-bank source paths, first/last regions, pivot/scale, alpha bounds, clearance times, aperture/selection registration presence, door mappings, and source-proxy points are recorded in the JSON evidence. Presence of an aperture mask is not a claim that every aperture contour has received new manual certification.

## Native evidence and limits

Review gallery: **http://127.0.0.1:8794/**. All four cameras remain visible together. The gallery includes 102 cases / 408 captures:

- Current actual Lantern Crypt gameplay, four cameras, zero reported presentation gaps. The corrected entry→passage mount remains `(7,y),EAST`; entry→vault remains `(x,8),NORTH`, preserving the same physical edges and the `(7,8)` D2 corner.
- Native continuous runs with both incident owners, mixed legacy/fixed D1, wood C1, convex/concave/T joins, registered-prop corner, raised supports and zoom 0.75. The T fixture's three segments meet at `(5.5,4.5)`: E at `(5,4)` and `(5,5)`, N at `(5,4)`.
- Combined, ground-only, wall-only, and H1 paving diagnostics, with an actor at the adjacent owner-cell centre. Isolating displayed layers occurs after native capture and does not change gameplay geometry.
- All ten window families: native intact, insert-broken where applicable, and parent-broken states; native recorded histories include attack/traversal. A4/D7/G9 show parent-impact frame 0 and boundary clearance after insert destruction, plus separate full-parent cascades with the insert still intact, before/frame-0/clearance/settled.
- G9's separate intact parent/insert target highlights use the existing compositor's surviving pick masks; both exact identities are independently pickable in all four cameras. Its native crawl is shown before, at the sill midpoint, and after, including the sampled actor and shadow.
- Representative Fantasy A1, Fantasy C1 (offset pose), and shabby indoor doors: native closed, open, reclosed, broken states. Raised C1 also shows actual open-door passage before/midpoint/after and a move alongside the wall. The alongside view uses the witness's recorded disclosure, not invented hidden trajectory fields.

This is full numerical review of the selected registrations, not full manual acceptance of the 368-bank environment library. Visual review is sampled and its exact reviewed images are recorded in `audit-summary.json`. Physical irregular wall-base extent, all aperture contours, every mixed-material junction, movement alongside each raised fixture, all door materials' live swings, and current runtime VFX cap leakage remain unverified. Native disclosure can leave unseen floor cells black; that is not evidence of removed support geometry. No art or shared rendering repair is justified solely by an attractive screenshot.

## Receipts and reproduction

Production checkout: `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine`. Base HEAD when the audit started: `bcea72668fd`; existing uncommitted production edits were retained. Evidence is pinned by file hashes, not just HEAD.

[Durable machine-readable audit](WALL_FLOOR_ASSET_ALIGNMENT_AUDIT_2026-10-06.json): selected registration inventory, source pins, camera/owner contracts, native fixture positions, original-effect inventory, preservation results and exact sampled review list. The PNG gallery and full per-frame metrics remain private diagnostics below.

Private diagnostics: `.runtime/wall-alignment-audit-20261006/`:

- `registration-audit.json`: 36 static resources, 164 selected banks, 13,968 frame rectangles, **zero rectangle errors**, floor hashes and transforms.
- `frame-continuity.json`: 112 directional source-atlas checks; 76 original-component comparisons; all 112 frame-0 comparisons, with paths, regions, alpha counts, L2 and RMSE.
- `source-solid-effects.json`: four original solid-wall effect sequences; all 64 recovered image hashes verified. These are present but uncertified for native per-family binding.
- `native-captures.json`, `*-placements.json`, `window-*-native.json`: native placements, recorded actions and chosen draw media. `images/crypt-native-q*.png` are the actual encounter run.
- `supplement-captures.json`: 21 additional native cascade/selection/crawl/raised-passage cases, 84 images; corresponding recorded source histories remain beside it.
- `index.html`, `images/`, `media/`: gallery and diagnostic copies; `browser-check.json` and `audit-summary.json`: review receipts.
- `tests.log`: **216 passed** across boundary rendering, window/environment presentation, projection and session tests. This validates existing behavioral boundaries; it does not certify source geometry.

Run from the production checkout:

```sh
.venv/bin/python .runtime/wall-alignment-audit-20261006/audit_registration.py
.venv/bin/python .runtime/wall-alignment-audit-20261006/measure_frame_continuity.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python .runtime/wall-alignment-audit-20261006/capture_native_audit.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python .runtime/wall-alignment-audit-20261006/capture_supplement.py
.venv/bin/python .runtime/wall-alignment-audit-20261006/build_gallery.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run --no-sync python -m pytest tests/game/test_boundary_rendering.py tests/game/test_window_presentation.py tests/game/test_environment_presentation.py tests/game/test_projection.py tests/game/test_session.py -q
```

Preserved fixed deliveries: `/home/tommaso/Dev/neurodragon_art/sources/fixed-windows-20261001/` and `fixed-window-inserts-20261001/`. Original solid-wall reuse mapping and source effects are documented in `/mnt/c/Users/tommaso/Documents/assets/window-reconstruction/destruction-showcase/existing-solid-siblings/REUSE-HANDOFF.txt`. A4/A5→A1, C4→C1, D7→D1, D16→D8, F7→F1, F16→F8, G7/G8/G9→G1. The timber-footed D16/F16 originals must not be replaced by D1/F1 plinths.

Production should use this report to distinguish verified import preservation, native ownership fixes, unbound static families, and source/geometry questions before selecting a repair. Keep the existing native ECS and finite boundary lifecycle.
