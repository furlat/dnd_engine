# Timing evidence: AreaReach verdict and concrete remaining producers

2026-10-05, source-only independent review. No production edits or tests executed. This follows the bounded cast/attack receipt.

## AreaReach lane

Approved for the implemented subset. `choreography.visit` (~725) records the existing maximum of received stage admission and disclosed prerequisite destruction clearances. Missing prerequisite recordings are not replaced with invented dependencies. Per-application staged-area delay (~1228–1255) records the existing contact maximum, then shifts damage-start and HP by the difference between joined and original contact producers. `offset_producers` validates that actual difference and survives absolute normalization because both producers translate equally. Full delivery clocks continue to be changed by the existing binder, not by evidence evaluation. The typed application ID remains attached; the root cast is not recast for a later reach stage.

The resulting graph intentionally treats event admission/destruction clearance as external bound anchors unless their producer is annotated. This is accurate partial evidence, not proof that the entire earlier causal chain has been annotated. `previous_reach_lineage_uuid` still affects existing first-stage/media placement behavior; do not claim this subset independently models every propagation edge or decorative sampling policy.

## Concrete next subsets needed by approved plan D

Each row identifies an existing producer to annotate, not a request for a new scheduler or formula. Existing evidence records can reference these owners once captured; avoid copying arithmetic into consumers.

| Priority | Existing producer | Exact missing relation |
|---|---|---|
| 1 | `game/body_action.py:bind_body_action` ~228 and `join_body_action` ~237 | Start + selected effect-frame offset; body end; join=max(body end, actual owned child end); completion=join+recovery duration. Current milestone view reports outcomes but not producer operands. |
| 1 | `game/choreography.py:join_actor_subtrees` ~497 | Actual descendant end contributors across conditions/actions/equipment/movement/life etc.; cast recovery/complete shift by max(0, child end - recovery start); attack complete=max(original complete, child end). Preserve descendant identities and phase, not merely anonymous latest float. |
| 1 | `game/animation.py:compile_equipment` ~603 | Original hide/stance/equip frame and completion anchors. Stance switch and inventory/AC membership completion are separate effects, not one generic equip timestamp. |
| 2 | `game/choreography.py:join_reactions` ~430 | delay=max(0, reaction effect - incoming effect); each reaction start translation; common aligned effect. Record actual reaction UUIDs and native trigger relationships, not sibling-based inference. |
| 2 | `game/interruption.py:interruption_ms` ~100, `interrupt_body`/`interrupt_action` | Selected authored cancellation offset, protection-contact cutoff, anticipation/body/travel-fraction branch; interrupted body end/complete clipping. Full-action evidence is intentionally omitted today, so it does not explain played prefixes. |
| 2 | `game/choreography.py:_child_timing` ~86 | Movement waits for parent completion; forced displacement children wait for travel-end; non-spatial portal children wait for settled; ordered action groups wait for sequence end. Distinguish injury/HP state assignment from child's presentation start. |
| 3 | `game/choreography.py:_bind_jump` ~2261 and `bind_motion` ~2488 | Existing cumulative elapsed changes for committed legs, visible-boundary dwell, nested reaction groups and landing groups. Received speed/profile duration owns each leg; no hidden-path interpolation. Evidence must preserve which elapsed increments are dwell versus physical movement. |
| 3 | `_resolve_motion_body` ~2204, `_flight_path_phases` ~2450 | Recovery added after existing motion completion; native flight path takeoff/landing phase derivation. These are not new mechanical fly rules. |
| 3 | `game/portal_animation.py:bind_portal_transfer` ~33 | Fall=max(start, opening+delay); disappearance; exit-open placement; arrival=max(transit completion, exit readiness); settled/emerge completion. Only admitted endpoints are present. |
| 3 | `game/forced_movement.py:bind_forced_movement` ~109 / `bind_shove` ~73 | Selected source contact, displacement start after opening media, travel duration and optional arrival/recovery tail. Keep successful shove contact versus actual displacement separate. |
| 4 | `game/choreography.py:preceding_damage_commit` ~400, `bind_standalone_damage` ~589, `bind_life_transition` ~643 | Prior same-target HP floor before later native consequence; standalone damage has no cast/attack timing tuple; death-save/life pose and silhouette-tail joins need their existing timing source named. |
| 4 | `game/condition_animation.py:compile_condition`/`bind_condition_body`; `choreography.finish_conditions` ~470 | Application/removal transition body, feedback and effect completion; actual membership commit versus decorative end. Suppression/consumption should retain condition instance ownership. |
| 4 | `game/condition_media_lifetime.py:register_condition_lifetimes` ~124 | Existing removal-fade maximum (~143), activation, absence return and inherited original ages. `retained_milestones` currently reports dates, not the selecting trigger/callback equation. Do not invent application dates for quiet reacquisition. |
| 4 | `game/spatial_media_lifetime.py:register_spatial_lifetimes`, `construction_media_lifetime.py:register_construction_lifetimes`, `concentration_media.py:register_concentration_lifetimes` | Existing cue/observation-derived admission, partial cell retirement, destruction versus removal, concentration last-presence selection. Preserve separate retained owner identities. |
| 4 | `game/item_attachment_lifetime.py` / `game/deposit_media.py` registration | Existing witnessed application cursor and first admissible state cut; unknown/remembered-only starts remain unknown. No invented event from membership. |

The following should stay ordinary sampling code: trajectory interpolation, sprite-frame modulo, marker carousel, fade progress, ground-mask sampling and complementary blend weights. They need documented units/inputs and deterministic tests, **not** dependency nodes for every frame. Optional VFX tail lengths only need a recorded dependency when the current binder actually uses them to delay completion; do not make them newly blocking.

Recommended next bounded implementation is priority 1 (body/action/equipment joins), then priority 2 (reaction alignment/interruption/child timing). That connects existing shared clocks before adding the larger movement and retained-owner subsets. Reuse the current finite evidence format; expand reason/anchor tags only for actual equations encountered.
