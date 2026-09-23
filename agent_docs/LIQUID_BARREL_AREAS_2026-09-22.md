# Correction: barrels spill over a surrounding area

## User contract

The user rejected the one-tile result and explicitly selected **all liquid
barrels** for an area one tile outward: up to a 3×3 footprint around the broken
barrel. That correction supersedes the earlier one-cell limit in
LIQUID_BARRELS_PLAN_2026-09-22.md and its implementation record.

The user also requires an **animation of liquid spilling**, observing that water
currently pops into existence. That work may be queued, but is a necessary final
result. Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` received an explicit
asset request for the outward spill, floor landing and persistent-pool handoff.
The current correction must not call static pools finished animation. The later
ownership handoff below includes Grease by reusing its accepted spell material;
provisional replacements are not authorized for installation. No hand-made replacement
VFX or enlargement of pixels pretending to enlarge the native area.

**Further visual correction:** the user rejects the stamped/square-looking
result and asks for material tile maps that follow the desired pattern, with a
more circular outline. The procedural repeated-field experiment is withdrawn.
It must not become another retained rendering path. The gameplay footprint stays
the agreed surrounding cells; a rounded authored border occupies those cells
without claiming unobserved or mechanically unaffected ground.

## Implementation boundary

Input: a real attack breaks a placed barrel; actors on/around it then move or
jump. Output: surrounding native material cells, their real effects/costs and
public observations, with a visibly larger coherent pool in saved replay.

1. One passive radius in the existing contents profile controls the native
   footprint. All six authored barrel variants use radius one cell; radius zero
   remains useful for explicitly small authored containers and isolated tests.
   Do not alter shared sphere geometry: this is the requested neighboring-cell
   footprint, including diagonals on open ground.
2. A small bounded footprint resolver reuses existing map support and physical
   boundary queries. Reach only connected ground on the same elevation. No
   uphill flow, falling-liquid model, terrain mutation or creature avoidance.
   Closed walls/doors and unsupported cells constrain the spill. Diagonal
   corners cannot tunnel through blocked or raised cardinal cells.
3. Keep existing material arbitration. Oil/water/grease occupy one shared area
   each; skip cells whose existing ground owner would reject creation.
   Do not overwrite another material, make destruction throw after breakage, or
   invent mixing rules. Tile-owned blood/poison/dread retain their established
   coexistence. Fire destruction ignites the oil footprint actually activated.
4. Preserve declared contact timing. Water/Grease have appearance effects on
   grounded occupants. Poison/dread residue and fire retain their existing entry
   or turn triggers; do not manufacture a movement event to imply splash damage.
5. Wider dread footprints make the adjacent-tile reversal defect relevant.
   Resolve it within existing residue fear ownership: crossing internal cells
   of the same ground residue must not replace the original fear/retreat heading
   or oscillate. The existing initial paid return step remains; fear clears on
   leaving that material. Retained fear allows movement outward along the same
   retreat heading, with ordinary cost; blocked/exhausted movement stays feared.
   Actual tile state controls membership. No pool registry or world-wide scan.
6. The next visual unit uses authored material interiors, edges, rounded outer
   corners and inner corners selected from currently disclosed same-material
   neighbors on the same support height. Unknown/remembered neighbors do not
   establish a currently visible join.
   A compact quarter-tile atlas can cover irregular joins without dozens of
   separately authored full tiles. Reuse existing floor projection, clipping,
   lighting and depth. Keep palette, tile rectangles and scale in passive data
   reusable by TypeScript. Do not add a general tile engine, new simulation or
   runtime art generation. Existing directional injury contributions remain
   intact; this concerns unshaped persistent pools.
7. Match the spill animation's landing coverage to the persistent tile output.
   Request isolated, rounded 3×3, L-shaped, joined-pool and wall-trimmed previews,
   including a missing diagonal and a one-cell remnant after partial removal.
   Whole-cell gameplay remains discrete: rounded transparent tile corners do
   not establish subcell collision rules. Native material and observed cells
   constrain drawing; art does not expand gameplay or visibility.

## Artwork ownership

**Latest handoff:** the user reassigned both persistent materials and animations
to Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec`. Environment art task
`01a0b501-8a27-7413-ba24-4a36e5b140d2` paused overlapping authoring and delivered
[topology research](</home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/material-pools/HANDOFF.md>).
That handoff supersedes the earlier split between persistent-art and animation
owners. It includes all six materials, with Grease reusing the accepted spell
shader from `terrain-spells-review`, not the rejected ochre replacement.

The Godot delivery owns shader materials, GPU pixelation before export,
discharge/settling and restrained persistent loops. Exported tiles must share
world-aligned texture coordinates, palette, texel density and animation phase;
tiles must not restart their loops independently. Python/Pygame still consumes
exported assets. This does not introduce a Godot runtime dependency.

The research PNGs, atlas indexing and preview positioning are provisional.
Do not import those PNGs as finished liquids or copy manually calibrated preview
wall pivots into production. Its current 3×3 study still resembles a rounded
rectangle, so the user's circular-outline requirement remains unresolved.
Candidates need visual review; static seam tests and delivery alone are not approval.

## Tests and review clips

- Each authored barrel produces the full nine cells on open ground; near walls,
  closed/open doors, map edges and changed elevation it reaches only admitted
  connected cells. Nearby creatures do not shrink the footprint.
- Water/Grease appearance, walking through outer cells, exit/re-entry and landing
  prove mechanics extend beyond the original barrel cell. Jump beyond the entire
  area to test noncontact; landing in an outer cell contacts it.
- Incompatible existing ground material remains intact. Whole-area fire-caused
  destruction and partial later material interactions retain native ownership.
- Dread entry at the edge retreats out; landing/teleport inside can retreat into
  another dread cell without bouncing or a reversed new save. Leaving the pool
  clears only that fear; insufficient movement retains it.
- Saved two-observer clips show all six larger spills and boundary cases from
  four cameras. Existing destructive-item/replay tests keep their meaningful
  behavior; explicitly one-cell isolation fixtures author radius zero.
- The authored tile unit must check joins, rounded outline, native-cell clipping
  and all camera orientations; existing injury geometry remains unchanged.

Required anti-slop review: `backend_ecs_review` (native footprint/arbitration)
and `presentation_antislop_review` (shared pool drawing).
Required anti-OOP/ECS review: `spell_orientation_antislop` (ownership and bounded
dread repair). Review comments and final results will be recorded below.

## Review decisions

- Native anti-slop review approved the bounded floor flood, existing admission
  and contact rules. The dependency-neutral helper belongs in `dnd/core/ground.py`;
  placing it under `spatial` would cycle through that package's action imports.
- Independent ECS review accepted same-item destruction and tile-owned material,
  the one paid retreat followed by ordinary paid steps, and dynamic connected
  material contact without a second pool-owner registry.
- Both reviewers accepted the revised authored-tile direction. Reuse existing
  floor projection/clipping rather than add a general tile engine. Quarter tiles
  are a recommendation, subject to the approved asset metadata.
- Visual review added same-height/disclosed-neighbor selection plus concave and
  remaining-single-cell cases. Static material art and spilling animation remain
  separate unfinished deliverables; neither is approved by tests alone.

## Completion accounting

Native AoE: implemented and verified; see the
[result and remaining visual work](LIQUID_BARREL_AREAS_RESULT_2026-09-22.md).
Authored material tile maps and rounded persistent pools: requested, not integrated.
Animated spill and maintained material loops: **required, owned by Godot;
not yet integrated**, including Grease from its accepted spell source.
Persistent burning-floor media: separate pending handoff.
