# Environment asset inventory — 2026-09-24

This is an inventory and packaging recommendation, not a production edit or deletion authorization. It follows the current recovery scope and the `bug-fix` review discipline: distinguish a file that the current runtime can select from a file merely declared in a catalog, and retain valid states beyond those visible in a particular clip.

The physical baseline is the private art manifest for code commit `508f5f8d38cc2e6982b73c44ee7f911b794c042a`. Counts and encoded byte sizes come from its existing path/size fields. This audit performs no hashes, raster decoding, filesystem-wide asset scan or image rewriting.

## Deliverables and scope

- `.runtime/asset-inventory-20260924/environment/files.jsonl`: one decision per physical manifest file, with `path`, `production` boolean, `owners`, `reason`, source `evidence`, state/frame/camera selections, scale policy, current storage and proposed packing.
- `.runtime/asset-inventory-20260924/environment/summary.json`: complete counts and physical-family totals.
- `.runtime/asset-inventory-20260924/environment/selector-verification.json`: actual production selector checks, independent of catalog-name matching.
- `.runtime/asset-inventory-20260924/environment/build_inventory.py`: small offline audit reproducer; it writes only this audit directory.

Every manifest file under `game/assets/environment/`, `game/assets/torch/` and `game/assets/water/` is covered: **1,094 files / 85,132,487 bytes**. There are no unresolved rows in this bounded domain. Actor layers, spell VFX, liquid-export sequences and maintained spell media have other reviewers. Four shared body-release strips appear here with explicit VFX joins; their exact action windows belong to that ledger. Root merging must union concrete production uses across domains before exclusion.

| Current physical-file decision | Files | Encoded bytes |
| --- | ---: | ---: |
| Runtime required, including valid legacy/fallback branches | 1,006 | 77,104,888 |
| Unselected current variants, superseded resources or source-only files | 88 | 8,027,599 |
| Unresolved in this domain | 0 | 0 |

The retained byte count includes whole PNGs with only partially used regions. It is **not** an estimate of an optimally packed runtime size. Source-only means exclude from the candidate runtime payload, while preserving the private source/archive. It does not mean erase authoring material.

## What actually selects the pictures

| Family | Current production contract |
| --- | --- |
| Terrain, stairs and cliffs | `game/app.py:409` selects material and topology; four camera poses are valid. All authored earth/stone/wood ground, straight/corner cliff and whole-stair images remain. Water uses a separate procedural material. |
| Walls and old binary doors | Stone/wood straight and corner poses remain. `app.py:750–765` explicitly leaves old doors without a recorded swing on the binary path; the old open/closed images therefore remain despite newer smooth-door banks. |
| Smooth doors | All **17 bindings** use **16 distinct authored families**; generic directional door shares fantasy A1. Both swing directions, open/closed holds, forward/reverse opening, clear/jammed destruction where supported, and pre-open destruction variants remain. Indoor families intentionally have no jammed outcome. `environment_art.py:88` and `environment_animation.py:19` select them. |
| Props and furniture | All **34 item bindings** are supported by current native direct builders. This includes all three chest pairs, two-cell bed/table, crate, six barrel contents sharing one body, and the 21 newer freestanding objects. Chest open/closed destruction is distinct. Every destruction strip retains its full finite sequence and final persistent remnant. |
| Trap hardware | All **12 blade/crusher material × style bindings** remain, with ready/activated/deactivated and destruction-from-ready/from-active banks. Re-arming is a valid native option; it requires the full intact cycle beyond the active hold frame. There are **40 supported legacy wreck aliases** across doors and hardware. |
| Ground mechanisms | Pressure plate press **and release**, jaw close/rearm, dart launcher, vent, tripwire, ordinary/poisoned spikes, and bloodied spike overlays retain their entire selected sequences and four poses. Blade/crusher spatial-only pictures and depth remain valid for owners without a registered hardware body. `app.py:1322` skips them only when a disclosed hardware body already draws that owner. |
| Dart projectiles | All eight yaw columns in each of four camera poses remain. `mechanism_projectile.py:53` applies residual rotation toward the target. These resources are also shared with ranged attacks; they are not disposable because one trap emits cardinally. |
| Cannons | Fireball cannon and arcane device both author `launchPitchDegrees=15`. Every current emission and destruction producer calls `device_bank`, so only the 15° body and break banks are selected. All eight yaw rows and four cameras remain. Final wreck sheets retain all rows, including remembered aim after a shot. |
| Portals | Both entrance and exit banks remain in all four cameras. Bare portals use the exit bank on both sides; hatches also use the entrance bank. Each bank has **433 logical frames**: 72 opening, 288 hold, 73 closing. Indefinite maintained entrance state makes every hold frame reachable; these must not be limited to the short exit clip window. |
| Torch and water | All 16 torch flame frames and three body images remain. Water mask, normal and ripple are full procedural texture domains, not a finite filmstrip. |
| Ground residue | Blood/dread flat PNGs are always bypassed by current liquid bindings. Bone/corrosive flat PNGs remain reachable when residue has no geometric contributions. The contribution check at `app.py:1253` matters: merely seeing a region-particle binding would incorrectly delete these fallbacks. |
| Body-release fallbacks | All four `environment/releases/*.png` strips remain: `game/action_media.py:45–48` explicitly chooses them for absent release/pattern or airborne damage. Primary spell-projectile reachability alone does not see this branch. |

All **208 environment banks** are linked to a current selector. Presence alone was not the proof: a read-only check invoked production selectors over **226 concrete state selections**, checked every bank's forward/reverse frame reachability, verified all relevant item IDs exist in `DIRECT_ITEM_BUILDERS`, confirmed both selected cannon pitches, and sampled every portal phase. No native game was rerun and no fixture outcomes were fabricated.

## Proven runtime exclusions

| Files | Count | Bytes | Why they are not required by the current root |
| --- | ---: | ---: | --- |
| Indoor `leaf.png` component atlases | 12 | 1,110,610 | `EnvironmentBank.leaf_path` is decoded but never read by a production drawer. The full sheet supplies the visible body. |
| Device body/break pitch 0°, 30°, 45° sheets | 48 | 6,322,586 | Current authored launch pitch and every binder choose 15°. Pitch is derived during binding, not recovered as an arbitrary saved event value. Keep these as alternate authored exports. |
| Old flat chest pictures and SVG lever placeholders | 10 | 288,515 | Catalog entries remain, but current chest and lever bindings select different exact banks/frames. There is no corresponding old-chest fallback branch. |
| Old blood/dread ground residue pictures | 8 | 34,065 | Current liquid owner always takes precedence before `residue_ground`, even with no contributions. Bone/corrosive are retained separately. |
| Source metadata and READMEs under asset folders | 10 | 271,823 | Production reads normalized `game/data` contracts, not the delivered provenance documents. Keep metadata with source and licensing material. |

The prior ancillary inventory intentionally over-retained declared paths. This audit narrows those specific cases using their real consumers; it does not treat every auxiliary-only reference as dead.

## Concrete packing and bake decisions

1. **Environment color/depth banks: retain source resolution and page oversized strips.** Most color banks use 256px cells and fixed registration scale either `1` or `128/127`; depth cells can be 128px or 256px. At supported zoom `1`, these are already drawn at source size or slightly larger. There is no justified broad downsample. **177 color strips exceed 2,048px width; the largest is 39,936px.** Pack their same selected cells into bounded pages, grouped per authored bank, retaining logical frame indices, exact sample times, pose rows and pivots. A practical candidate is 2,048×2,048 pages, consistent with existing paged media; this is not an approved maximum-texture requirement. Paired depth pages must preserve the exact frame/pose mapping and encoded RG values. No temporal thinning is justified.

2. **Indoor structural frame atlases: keep only column zero.** `app.py:798–809` is the only frame-only draw; it always passes frame `0` for an out-of-sight but known doorway. The 12 full frame atlases declare 1,152 cells; only **48 cells** are selected, four poses per atlas. Extract those cells into a small structural-frame atlas with their original registration. Full visible door sheets and their depth stay separate. Leaf-only sheets can stay source-only.

3. **Ground mechanisms, spike overlays and levers: combine individual frame PNGs by family.** Preserve every reachable logical frame and all four poses. Pressure-plate release and jaw rearm frames are included. One shared blood overlay can remain referenced by ordinary and poison spike families; it does not need duplicated pixels. Dart camera/yaw entries remain separately indexed. This reduces file opens/packaging overhead without changing resolution or timing.

4. **Cannons: keep the existing selected sheets.** Sixteen 15° firing/break camera sheets plus eight wreck camera sheets are already useful local atlases. There is little reason to repack them immediately. Omit the 48 unselected pitch sheets from the current payload, without deleting them from source.

5. **Portals: keep the existing pages and exact phase clocks.** Each camera has seven pages. The last page uses **49 of 64 cells**; the remaining 15 need not occupy a new packed payload. The two hatch sheets have further exact subsets: body columns `0,2,3,4,5,6,7,8,9,10,11`; front occlusion mask columns `0,2,3,4,5,6`. All four camera rows remain. Front-mask closing columns are never sampled because that mask is used only for a falling entrance body. Preserve logical indices rather than shifting the authored opening/closing lists.

6. **Ashen floor/wall atlases: retain only the four top-row motifs.** The actual reader `_motif` at `surface_residue.py:83` divides each 1,254px square into a 4×4 grid but both consumers always pass row `0`. Selected source rectangles have x edges `[0,314,627,940,1254]` and y range `[0,314)`. The remaining three rows are not runtime requirements. The floor sampler always first scales each motif to **70×70**; these four exact nearest-scaled intermediates are a legitimate fixed bake candidate. Preserve its later rotations and opacity. Wall motifs have runtime size variation (width 70–106, height 80–179): crop their original top-row regions but do not claim one fixed bake fits all walls. Any cropped pack must retain explicit motif rectangles; simply shortening the old image while keeping `height/4` addressing would be wrong.

7. **Static terrain/walls/torch: lossless region atlas is sufficient.** Keep source pixels and per-region pivot/size. Camera zoom is a supported finite set: `.15`, `.35`, `.5`, `.75`, `1`. Do not bake the default `.5` camera view as if it were the sole production scale. For scale `128/127`, direct source-to-final nearest sampling is not generally equivalent to baking the fixed correction once and then resampling at each zoom. Preserve the current one-pass transform or validate exact derivatives for each supported size; no need to add those derivatives merely for this inventory.

8. **Water: keep independent canonical textures.** Ripple/normal use repeated UV sampling and their own local dimensions; packing them into an ordinary color atlas without preserving that sampling domain risks seams. A bundle may contain them unchanged. The water mask remains source-sized and uses camera zoom.

These are file/region choices, not a new runtime packaging framework. Current environment readers address full images or regular strips. Applying the partial/repaged recommendations later needs a small explicit frame-to-page/rectangle adapter and equivalent pivot/depth sampling; moving bytes alone is insufficient. Until that work is authorized and checked, existing runtime paths remain unchanged.

## Limits and merge rules

- All rows describe the **current checked-in data root**, including explicit supported legacy branches. Changing authoring to another cannon pitch would change the required payload; the source archive retains those alternatives.
- No roof/window/building prefab image was discovered in this environment manifest domain with an unclassified production owner. The larger external interiors source handoff is not silently declared integrated by this report. Root owns its broader source/archive manifest reconciliation.
- Lighting, hit flashes, alpha, world height, yaw, camera rotation, residue amount and portal timing still vary at runtime. They are not reasons to export every possible rendered frame; the selected source banks are their common inputs.
- No compression ratio, duplicate-pixel equality or visual equivalence was invented from filenames. Existing manifest byte totals describe encoded files only. Hash/deduplication proposals from other work are not runtime checks here.
- This audit does not fix the known destruction JSON decoder, alter mechanics, retune scales or regenerate clips. Production-read reachability and selector checks establish inventory decisions, not new artistic approval.

## Independent merge review

Reviewed `.runtime/asset-inventory-20260924/reconcile.py` and its joined output read-only. At this checkpoint it emits exactly one row for all **62,769** manifest paths, accounts for **26,660,655,022** source bytes, has no unmatched paths or unresolved decisions, and has no contradictory concrete positive/negative owner claims. Concrete positive usage is retained. A domain-specific negative supersedes only the older coarse ancillary claim.

All **44** environment/ancillary disagreements were checked individually: 12 unused leaf components, 8 shadowed blood/dread ground pictures, and 24 unused destruction-pitch sheets. The old ancillary program had deliberately retained all declared alternatives; none of these 44 has an alternate current legacy reader. Body-release strips and other real legacy branches remain retained.

The join's existing-manifest duplicate-content summary is an offline storage estimate, not a runtime audit or an instruction to discard alias metadata. Any later physical sharing must keep each logical resource's own frame rectangles, pivots, scale and owner semantics. Whole-file retention counts also do not measure within-atlas waste or certify a final compressed package size. With those distinctions, the merge is appropriately bounded; no new packaging framework is needed for this inventory.
