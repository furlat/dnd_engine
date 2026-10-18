# Minimal XYZ addition from production

Date: 2026-10-15. Status: implementation proposal. Base: committed production `feature/speedupsensory`, `229ce025f3ffbf876cbb34f63d0de26a9051d088`.

Add several simultaneously occupied support locations at the same XY while retaining production's existing spatial registry, Tile memberships, movement rules, perception, light, spell policies, events, capture and delivery. Optimize a reader only when XYZ requires changing it and a real measurement shows avoidable work. Do not restart the failed material/world-facts redesign.

This replaces the implementation strategy of the October 13 multifloor plan and the failed October 14 native redesign. Their source inventories and behavioral cases remain useful evidence, not instructions to import their architecture. This request authorizes a plan, not engine implementation. The production source remains unchanged.

## Base and scope

Any later implementation starts in a fresh worktree at the exact committed production base above, with its compact-light fixes. Do not use literal `main`, the old `792ec024` baseline, or cherry-pick either failed multifloor worktree. Inspect newer production commits before starting if HEAD changes; explicitly adopt the new committed base and repeat the short baseline. Uncommitted spell documents and work in other branches are separate.

The requested native result is an authored two-floor encounter: exact stacked occupancy; stairs and current ramps; same-XY paid vertical connectors; cross-floor visibility, light and targeted spells through openings; correctly blocked slabs and finite walls; floor-specific areas and ground effects; ledge shove and landing; server/SDK commands, reconnect and cold replay. Existing AI and sandbox consumers must understand the complete locations. Flight and hovering remain excluded.

Production does not have the generic load-bearing assembly/dependency system attempted in the failed branch. Its `_support_columns` is a lookup index, not structural engineering. Preserve the constructor/editor's directional authoring constraints when supplying a building, plus native placement and overlap validation. Do not replace physical support with “a Tile exists below.” General bearing inference, arbitrary-solid admission and load-bearing collapse are separate features, outside this XYZ addition. Existing forced falls and supported relocation remain included.

## Existing systems to preserve

| Production mechanism | XYZ work | Preserve |
| --- | --- | --- |
| `GridMap._tiles`, UUID reverse lookup and sorted `_support_columns` | Store and select full supported addresses. | Direct dictionary reads and the existing bounded support index. |
| Tile entity, condition, center-band and side-band membership | Distinguish receiving supports and absolute occupied bands. | Exact membership and cheap boolean side checks. |
| GridMap placement, elevation and connector commits | Maintain old/new addressed membership coherently. | Existing declaration, cancellation, mutation, rollback and completion owners. |
| BFS/Dijkstra and direct-route preference | Enumerate supported XYZ neighbors. | Costs, direction order, solver choice and established equal-cost preferences. |
| Cached shadowcasting and optimized directional visibility | Add narrowly bounded height admission where needed. | Both planar kernels, their respective corner rules, cached results and incremental boundary overlap. |
| Observer computation and light deltas | Carry full addresses and correct dependencies. | Shared physical candidates, mode results, narrow changed-light sets and compact source descriptors. |
| AoE shapes, propagation and selected previews | Resolve exact receiving supports. | Per-spell propagation policy, shared action tables and on-demand previews. |
| Native events, capture, world facts and projection | Carry XYZ and apply addressed rekeys locally. | Mutable Event history, source order, extension-safe detachment and incremental recorded folds. |
| Server and current SDKs | Regenerate spatial values and fix address keys. | Current transport, receipts, command dispatch and sandbox lifecycle. |

No new world manager, event family replacing existing commits, second capture pipeline, body-ray model, convex material framework, compiled module or parallel floor engine belongs here. A derived index is allowed when an existing mutation owner maintains it. Deleting a cheap index is not a cleanup goal.

## Address contract

Use a dependency-neutral alias for an exact three-integer supported position. X and Y remain grid cells. Z uses production's existing **five-foot support-height steps**: `(12, 8, 2)` is a support ten feet above `(12, 8, 0)`. Z is physical height, not the sorted rank or name of a floor. Negative heights and sparse gaps are legal; inserting a support does not renumber others.

Keep integer identity and the existing tactical ramp unit. Finer authored precision is not added implicitly. A later fractional-height requirement needs a single exact representation decision at the import boundary; do not round a fine tread into another support or manufacture extra tactical walking actions.

`Tile.position[2]` becomes the live height authority. Existing `height` reads can be a derived property during migration; writes go through `GridMap.set_tile_elevation`. Frozen recorded/presentation `elevation_steps` may remain for consumers, derived from Z and checked for consistency. It is not separately mutable state.

Exact live lookups require XYZ. There is no highest-floor, nearest-floor, all-floors or default-zero fallback inside gameplay. Explicit old authored-input adapters can lift XY plus its authored height once before construction. New wire requests require exact XYZ.

Do not mechanically widen every pair. Map width/height, footprint offsets, cardinal deltas, planar geometry, angle calculations and XY aiming vectors stay two-dimensional. Removed object bands already use `(x, y, absolute_band_height)`; that is a material-band identity, not a support address. Matching a removed band uses the support's XY plus the absolute band, not a fourth coordinate appended blindly.

Distances keep their present owners. `grid_distance_feet` remains planar. `support_distance_feet` retains its current `max(planar distance, rounded vertical feet)` rule. FOV/light retain their present XY circle cutoff; any new vertical bound is explicit. Do not substitute Euclidean 3D distance or one universal metric across spells, senses and movement.

## Map membership and mutation

Change `_tiles` to XYZ → Tile and its UUID reverse lookup to UUID → XYZ. Retain `_support_columns[(x, y // 16)]`, sorted by complete position. Bisect the actual neighboring XY column and relevant Z range for stairs, ramps, receiving supports and lower landings. No additional floor registry is necessary.

Preserve Tile-owned entity/condition membership and object bands. Placement remains anchored to exact support UUIDs and full addresses; its material base/top bands remain absolute. A tall object anchored below can affect an upper receiving band or the opposite incident boundary. Acquire those neighboring providers once at the existing placement/query boundary, or maintain an exact derived receiving-membership index there if the proof requires it. Do not scan broad material-owner candidates inside every hazard, side or center lookup. Placing, moving, damaging and removing a provider must update every affected receiver and preserve owner identity.

Creation/removal/rekey/reset update the existing indexes and local subscriptions. A height edit becomes an addressed rekey retaining Tile UUID. Preflight destination conflicts and prepare resident/placement/connector effects before mutation; retain the current restrictions on edits that cannot be safely admitted. Revalidate exact source UUID/address and destination after declaration callbacks, since they can mutate the world before commitment. A canceled edit changes nothing. Successful edits invalidate both old and new cells, boundaries, dependent observers and light contributions. There is no whole-support validation pass on an actor or illumination commit.

Do not silently relax or tighten occupied support, object or connector restrictions. Current elevation edits permit occupants, Tile/spatial conditions and boundary placements; center placements and anchored connectors have existing restrictions. Rekey residents, condition-owner reverse positions, subscriptions, collision memories, object/contact/boundary candidates, attached light locations and optical obscurement membership. Update a boundary's support address while retaining its authored absolute base/top bands: raising a Tile does not automatically raise that material. Add a mixed actor/condition/light/boundary rekey case. Existing prohibited cases stay prohibited until their specific lifecycle is proved.

## Navigation and falls

Adapt existing BFS/Dijkstra to receive one ordered supported-neighbor iterator from GridMap rather than constructing XY neighbors internally. Keep the existing cardinal/diagonal order, diagonal tie penalty, budget and predecessor behavior. Ordinary same-height movement remains direct indexed lookup. Height-changing candidates come only from the bounded neighboring support column and then pass the current transition predicate.

Current ramp/stair walking requires both endpoints to have the same progressive kind, aligned slope axis and a one-step height difference. Preserve it. Ordinary entry/top landings remain at the same height as the adjacent progressive contact. Reject height-changing off-axis edges as today; equal-height lateral movement is not newly prohibited. Preserve destination terrain costs.

Walking diagonals still require equal endpoint heights and a complete two-cardinal-leg bridge. Resolve each bridge to real compatible supports; an upper bridge cannot unblock a lower corner. Keep optical and propagation corner policies separate from walking.

Direct-route preference can lift its projected candidate only through admitted support transitions. An empty optical ray does not authorize walking. If this required rewrite exposes repeated hazard/risk reads, reuse their value within the same stable route materialization; invalidate on the revisions that already invalidate that query. Preserve the chosen route and spent cost before claiming an optimization.

Allow appropriate existing paid vertical connectors to have distinct XYZ endpoints at the same XY. Retain cardinal-adjacent aperture/frame constraints and the current restrictions on arbitrary XY transfer. Their support UUIDs, enabled state, costs, action economy and source-exit reactions remain unchanged. Stacked Tiles alone never create a vertical walking edge.

Use one existing forced-landing resolver for shove preview and execution: try the legal supported step, then the physically applicable nearest lower receiver. Do not skip an occupied/blocking receiver to find a convenient farther floor. Preserve fall damage, prone, interruption and entry effects, each once. A missing landing is an explicit existing-policy failure, not an invented void destination.

## Sight and light

There is one unavoidable new passive fact: an upper support/roof needs a **horizontal-face channel policy**. Current Tile center opacity describes XY blocking and cannot describe a slab between two floors. Add one tuple of blocked existing channels to Tile and its frozen after-value, plus `WorldTileChanges` and current tile comparison/projection. Its existing authoring/mutation owner invalidates affected optical/propagation/light dependencies when the policy changes. An absent face is an opening; an authored transparent face transmits its permitted channels. Do not infer transmission solely from a material name. This is not a solid-volume or bearing model.

Keep the existing planar shadowcast and directional kernels unchanged for their current planar cases. Same-origin caches include full origin address and the existing relevant revisions. Preserve incremental boundary overlap; acquire exact local sides and horizontal faces once for the query batch, not once per endpoint, callback or receiving floor.

Cross-floor obstruction is a projected XY crossing plus scalar height. For a side at `x=b`, use the existing XY crossing parameter `t=(b-source_x)/(target_x-source_x)` and test `source_z+t*(target_z-source_z)` against the provider's existing absolute height interval. For a horizontal face `z=h`, use its crossing parameter and test the projected XY point against that cell face. Same-XY/different-Z uses ordered intervening faces in that single column.

The proof must specify one tactical source/receiver point in the current contact band, or the declared emitter height, without body samples. A source face is ignored only while the segment remains on/above it; an actual downward crossing of its opaque slab must block. Prove an upper observer can see a lower receiver beyond a ledge when the segment leaves the slab footprint before descending through its height, but cannot see straight through its own opaque floor. An opaque upper face approached from below blocks access to the occupant above it; its top approached from above can be the visible terminal support. Keep current common support/occupant observation, with exact planar behavior retained; do not introduce a separate visible-creature/hidden-floor model.

**The batched height algorithm is the first proof gate, not a solved claim.** Production's sparse solver stores one depth cutoff per XY angular interval. It cannot represent a low blocked endpoint and a higher clear endpoint with one cutoff. Reuse XY angular/rank acquisition and introduce only the extra height-slope admission needed for the overlapping endpoint masks. Prove exact corners and terminal rules. Do not implement per-target FOV, one complete solve per floor, target-by-blocker enumeration or a new generic geometry hierarchy as the fallback. If a bounded mask extension does not meet the gate, stop this design before broad migration; do not bury an expensive fallback.

Sight, physical propagation and light retain separate channel policies. Magical darkness does not become a physical spell wall. Sensory computation continues sharing physical candidates and boundary snapshots across modes. Subscription/dependency keys distinguish Z while retaining coarse XY acquisition where useful; an irrelevant remote floor must not trigger a new global observer recomputation.

Proposed vertical candidate rule for bounded sight/light queries: retain the current XY circle of radius R and admit only receiving supports within R height steps of the tactical source point. This adds a finite vertical bound without changing the XY cutoff or imposing a spherical distance. Use each owner's existing radius, including the source's maximum active light radius. Prove the rule at its boundary before accepting cross-floor behavior. A genuinely unbounded query uses the finite authored world extent and cannot promise independence from every remote floor. Other senses and spell ranges keep their own current metric/policy; do not copy this bound universally.

Preserve committed production's light repair: cell work follows actual changed illumination; emitter observation follows its separate notification. Source position becomes XYZ, source revisions and contribution-owner behavior remain. Perceived/exported source descriptors retain empty `affected_tiles`; internal source contribution footprints remain owned by GridMap for incremental updates and removal. Do not publish those footprints or repeated full observed-position lists. Incremental result must agree with a full light refresh for stacked overlapping emitters, caps, source movement/removal and door changes.

## Targets and effects

Retain the current finite subject/position tables and exact selection validation. Candidate membership, inverse eligibility and remembered contacts use full addresses. Compute geometry only for the selected AoE preview/execution as today. Do not add per-tile spell lists, eager area previews or duplicate target records for every spell.

An exact spell target may be above or below its caster when its existing owner's range, perception and delivery checks permit it. Apply cross-floor physical-access gating only when that owner already requires physical access; remote/noncontact actions must not gain a new wall restriction. Preview and execution use the same receiving locations and relevant channel predicates. Intervening slabs and walls block the channels required by that action; stairs and navigation never establish spell access.

The following are explicit proposed vertical extensions, not hidden consequences of changing tuple length:

| Effect | Proposed bounded rule | Existing policy retained |
| --- | --- | --- |
| Ground patch, trap, residue or surface deposit | Attach to the exact receiving support and its existing ground band. | No duplication onto every floor with the same XY. |
| Direct creature/object spell | Extend its existing perception/range/delivery checks; use bounded cross-floor physical access only for owners already requiring it. | Existing remote/noncontact exceptions, target filters, saves, damage, resources and special strict filters. |
| Sphere/radial volume | Existing XY circle plus a vertical radius bound in current tactical units; use the existing support-distance convention where the owner already uses it. | Existing footprint, corner and propagation policies on the original plane. No new mesh/body intersection. |
| Cone/line | Retain existing XY direction and shape; define the finite vertical inclusion from the selected endpoint and existing width/angle before implementing this owner. A zero XY direction remains rejected in this addition. | No new arbitrary vertical aiming interface or eye/body receiver model. |
| Cube/cylinder | Use existing authored size/height to bound included supports. Keep the cylinder's current lateral-wall exception. | Do not replace every shape with radial LOS. Roof transmission is a separate explicit face decision. |
| Connected spread, including Fireball | Unresolved conservative proposal: keep existing planar connected propagation and its doorway/corner results; admit cross-floor receivers through bounded propagation access from the effect origin within the shared finite footprint. Prove explicit entry/seed semantics, including when the origin has no support at a receiving elevation, before changing this owner. This does not mean a complete FOV/flood solve for each elevation. | No movement costs, stair reachability, room-air graph or repeated vertical transfers that let a blast climb over a wall and return behind it. |

Before modifying those area owners, write the small vertical-extent table for their actual spell inputs and the expected opening/slab/wall cases. The cone/line inclusion formula, cylinder roof delivery and conservative cross-floor connected-spread behavior need an explicit product check if their cases differ from the human's intended rule. Do not change an existing expectation or infer approval from this document. Direct cross-floor targeted spells, exact same-floor areas and the proof fixtures can progress independently.

## Events and clients

Extend existing spatial hints, actor steps, support/object/connector facts and handler membership keys to full addresses. Keep indexed dispatch and phase/source ordering. Do not broadcast an ordinary event to every floor or introduce a general replacement `WorldCommit`.

`dnd/world_facts.py` keeps its current event-specific folds, object memberships and separation of changed light cells from object-observation inputs. `dnd/player/capture.py` keeps its contact-focused checkpoint and extension-safe detachment. XYZ adds neither a full audience reconstruction nor complete world validation to capture. `projection.py` keeps local touched-position projection and known-tile field updates.

One wire addition is necessary: current `WorldUpdate` can insert/patch Tiles but cannot remove an addressed Tile. Extend that existing update and reducer with addressed removals carrying **old position and Tile UUID**. Proposed reducer contract: reject an unknown/mismatched old base before mutating that update; never delete a replacement Tile merely because it occupies the same address. Existing receipt/order handling owns duplicate delivery. A disclosed elevation rekey uses removal plus insertion with the same Tile UUID in its event-associated update. Extend `TileElevationChangeEvent` and its current fold; `WorldModifiedEvent` currently requires before/after at one address and does not already admit rekeys. Disclosure follows current audience evidence; hidden old memories cannot be erased merely because the authoritative Tile moved. Test subsequent removal/replacement at the old address and hidden old memories. Do not add a global Tile-UUID uniqueness sweep to projection: a remembered stale observation is not another live Tile. Unknown-base patches still reject. Ordinary light changes remain field-only patches.

Use current generators: `devtools/export_player_protocol.py`, `devtools/generate_player_python.py`, and `sdk/player-typescript/tools/generate.mjs`. Current versions are protocol 1, player schema 9, native recording 2 and offline player sequence 5. Bump the affected spatial schemas together; no transport-lifecycle rewrite. Do not revive the obsolete `sdk/typescript` or historical generator importing removed server modules.

Python and TypeScript SDK position eligibility must distinguish identical XY at different Z. Adapt current AI knowledge/projection/control addresses and exact selections. Update Monty sandbox examples and installed package; exercise real SDK movement and target selection. Provide Godot with the schema change, XYZ picking/render height and event-associated rekey handoff. Client renderer redesign is not server scope, and client readiness cannot be claimed until its actual consumer is tested.

Retain a small fixed set of supported production native recordings before changing producers: flat movement, raised/ramp scene, elevation edit, hidden contact and moving compact light. Include a committed and a canceled elevation edit. A versioned read adapter resolves old XY from initialization and preceding recorded support/elevation facts in actual source/phase order, updating its support lookup only for completed, uncanceled facts. It preserves unsupported input and reports an explicit unsupported/ambiguous migration when recorded evidence cannot resolve the location. Never assume all old XY is ground zero, inspect final live state, or recursively widen every pair in a serialized object. Preserve native events, UUIDs, mutable live history and supported extension values. Keep the current policy that old public schema requires native reprojection instead of inventing universal public-format compatibility.

## Implementation order and stopping gates

Use three coherent deliveries, with a plan-adherence sub-agent continuously checking the whole requested slice. Each delivery includes its affected fixture migration and real-command timing; migration is not a final cleanup project.

**Prove the address and height seam first.** Record the committed baseline. Before bulk schema/test edits, build tiny executable cases for stacked supports, the current ramp/diagonal rules, an opaque slab/opening, same-XY visibility and a finite wall with low/high endpoints. Include grounded light blocked below its own slab, ledge sight beyond the slab edge and terminal top visibility. Exercise the proposed batch operation through a stable query boundary; compare planar outputs against both current solver modes. Prove one local obstruction acquisition, exact memberships and no target-by-blocker/global-floor scan. Then make the earliest real flat worker command with XYZ values pass and measure it, including capture and JSON. Failure here stops expansion.

**Complete one building through existing owners.** Adapt the address contracts, placement/membership, movement, observer/light/effects and delivery described above. Migrate existing fixtures as their owners change. Keep a working two-floor server/SDK journey throughout; add stairs, opening versus slab casts/light, floor-local areas, paid transfer and ledge shove. Any optional local optimization is a separate reviewable diff with before/after real-command evidence and identical required output. Do not import old failed runtime code to save migration time.

**Qualify the same result.** Run the affected existing suite, current SDK/sandbox/schema/architecture checks, a real two-agent sandbox encounter on the authored building and fresh-process replay/reconnect. Include both ordinary flat performance and local stacked-wall scaling. Antislop and antiOOP reviewers read the entire final diff and evidence. Report exact remaining failures; do not call a green subset complete or merge while a gate remains open.

## Tests and measurement

Follow `HOW_TO_TEST.MD`. Capture baseline collection/results before edits, distinguishing current historical collection failures from regressions. Root pytest does not discover SDK or Monty tests. Use the documented uv environment and report source location. Run inexpensive focused checks during each change, then the affected broad batch; do not keep rerunning unrelated suites.

Migrate coordinates at fixture construction before `EntityConfig` validation. Existing `tests/engine/support.py` receives an already constructed config and cannot repair rejected input afterward. Flat fixture adapters declare their plane explicitly; raised fixtures use actual heights. Preserve original damage, saves, resources, concentration, costs, event order, privacy and replay assertions. Do not normalize results back to XY, regenerate all expectations, blanket-skip old tests or count setup errors as executed gameplay coverage.

Use the existing multifloor plan's section 19 fixture inventory, checked against this base, without its generic physical redesign. Sensitive anchors include grid paths/direct routes, world geometry and modification, multicell objects, connectors, telekinesis landing, occupied elevation raise/restore, globe/cloud propagation, recorded facts, payload isolation, local projection/tile changes and the committed compact-light tests. Preserve the flat 36/49-support Fireball doorway outcomes.

| New observable case | Required result |
| --- | --- |
| Same XY, different Z actors/items/hazards/lights | Independent occupancy, effects, selections and remembered state. |
| Ramp/stair up/down and wrong-axis/missing contact | Exact intermediate supports, current costs, correct interruption/rejection. |
| Lower corner with an upper bridge | Existing lower corner remains blocked. |
| Opening versus opaque slab; same-XY ray; finite wall | Sight, light and direct casts obey their channel and terminal policies. |
| Ground area and cross-floor area | Exact receivers; preview/execution agree; no wall climbing or stair-based propagation. |
| Tall object and opposite incident boundary | Correct absolute-band receiver membership without query scans. |
| Paid same-XY connector | Normal resource/provocation rules and correct departure/arrival. |
| Ledge shove | First applicable lower landing; fall damage/prone/entry once. |
| Rekey or canceled edit | Same Tile UUID after admitted transfer; correct audience/replay updates; cancellation leaves state unchanged. |
| Declaration callback changes source/destination | Revalidate and reject cleanly, without partially moved membership. |
| Remote floor insertion and different insertion order | Local results and required local work unchanged. |
| Replay/reconnect and installed SDK inverse selection | Exact full locations and intermediate values, without live grid access. |

Performance uses actual `worker.start` → Choices → `worker.dispatch(Command)`, normal GC, identical creatures/audiences/seed/route and JSON encoding. Measure Choices and setup separately. Keep source and environment comparable on Linux. Alternate serial baseline/candidate cohorts and repeat a suspected regression; do not run simultaneous benchmark agents. Diagnostic profiles and kernel timings never substitute for plain command latency.

Postmortem reference medians against this committed base were 101.58 ms Gallery movement, 52.51 ms small movement and 67.73 ms Gallery Choices, with roughly 168 KB per Gallery command. These are eight-sample observations, not new targets or p95 evidence. Establish fresh paired noise before choosing a numeric tolerance. Acceptance is no reproducible unexplained flat-command, phase, Choices or setup regression; no payload growth beyond necessary addresses/new face/rekey data. The older 9.5 ms goal is not a promised outcome of XYZ.

Record total execution, capture/projection, JSON, bytes, event/observer work, allocation/GC and retained-history behavior. Relevant local stacked surfaces may add work; unrelated remote floors must not. Vary flat map size, local stacks and wall count independently. Reject repeated candidate acquisition, full support scans on movement, full-state capture copies, new light footprints or target-by-blocker fallback even if a tiny isolated example is fast. Longer history gets a deliberate bounded measurement, not a history redesign.

## Optimization and review rules

An optimization belongs here only when all four conditions hold: XYZ requires touching that owner; measured work is avoidable; current outputs and rules remain; the diff removes/reuses work without another authority. Candidates are one acquisition for incident receiving bands, query-local hazard reuse during route materialization, and reusing old/new boundary overlap. Evidence may show no optimization is necessary; keep the existing code in that case.

Whole-system antislop review checks that every nonmechanical addition names the XYZ behavior requiring it, its input size, invalidation owner and actual command cost. AntiOOP review checks existing ECS ownership, passive values, import DAG and absence of a parallel world/transaction/geometry hierarchy. Neither source line reduction nor a manager-name check establishes speed. Generated declarations and coordinate-only fixture churn are reported separately from added algorithms; no arbitrary line target justifies deleting useful indexes.

The first proof gate must pass before a large fixture/protocol migration. The final reviewers must inspect the actual saved plan, then the actual implementation if later authorized. Plan approval does not certify a fast height-mask implementation or settle the explicitly named new vertical area rules.

Independent review completed on 2026-10-15 against the saved and revised proposal:

| Reviewer | Material corrections incorporated | Disposition |
| --- | --- | --- |
| Antislop, `xyz_plan_optics_effects` | Public/internal light footprint distinction; remote delivery exceptions; source/terminal height and ledge tests; unresolved propagation seeds; explicit proposed vertical candidate bound. | Acceptable for the bounded first proof only. |
| AntiOOP, `xyz_plan_grid_navigation` | Equal-height lateral movement; complete mixed rekey; declaration callback revalidation; narrow connector relaxation; shared propagation acquisition. | Approved for the bounded first proof only; no extra authority/framework required. |
| Contracts and plan adherence, `xyz_plan_contract_validation` | Legacy completed-fact ordering and ambiguity; removal address/UUID contract; face-policy patches and invalidation. | Ready for the bounded first proof only. |

All three reviewers reread the corrections and reported no further material blocker to that proof. They did not approve an unimplemented height algorithm, bulk migration, performance or the unresolved vertical area rules. Implementation has not started.
