# Independent ECS / ownership review: full presentation coverage

2026-10-05. Reviewer role: anti-OOP/ECS and source-coverage audit. Read-only production inspection; no tests or visual certification claimed. This reviews the provisional plan and readiness audit against source, not the historical reviews' conclusions.

## Verdict

The existing readiness audit correctly identifies the difficult lifetime and evidence problems, but its denominator is still weighted toward spell recipes. It is **not sufficient to freeze a universal schema**. The rewrite must explicitly cover all projected facts, non-fact inputs, world transitions, static state rendering, and existing action/movement/reaction operators. This is not a recommendation to rewrite the backend spatial handler graph. Presentation consumes the handlers' projected consequences and must not recreate their rules.

## Missing independent denominators

1. **Public input channels**: all 27 `PlayerFact` kind tags, both damage stages, `PlayerObservation`, `WorldUpdate`, initialization, cancellation, attribution/log-only and factless nodes. `game/player_facts.py` and `game/player_reduction.py:85–102,239` demonstrate that not all changes arrive through facts.
2. **World transition variants**: all 10 `WorldTransition.field` values (`is_open`, `is_engaged`, `trap_state`, `pressed`, `activation`, `creation`, `removal`, `destruction`, `hit_flash`, `spatial_motion`). Derive these from the Literal in `game/world_animation.py:131`. Payload alternatives also matter: projectile, dust, collapse and membrane contact cannot be reduced to the field string.
3. **Tile state**: `WorldTileState` (`dnd/types/event_facts.py:152`) includes surface, optics, propagation, walking/flying/swimming/burrowing costs, elevation/slope, default/resolved light, condition names, residues. Even values without a graphical effect need deliberate inspect/narrative/state-only policy. Existing `presentation_inventory` does not enumerate this field contract.
4. **Connectors**: `WorldConnectorState` (`event_facts.py:177`) includes endpoints/support identities, elevations, enabled/directionality, costs and provocation policy. The presentation must use received path/connector facts and describe only permitted traversal; it must not infer traversability or opportunity attacks from appearance.
5. **Perceived spatial effects**: partial footprint, area geometry, propagation, upper volume sight, anchor actor/item, concentration slot, suppression, construction sections, deposit source (`dnd/types/senses.py:73`). These are independent dimensions, not 25 equivalent media rows.
6. **Static and state-selected world visuals**: floor/slope/stairs, boundary objects, ordinary props, doors, traps/devices, wrecks, loose items, object surface residues, tile residue surfaces and liquid surfaces. `game/app.py:172,280,1313–1387` contains rendering beyond `data.spatial_media`; `game/assets.py:147–154` resolves additional material bindings.
7. **Temporal ownership**: condition UUID, item effect UUID, concentration slot UUID, spatial effect UUID, section item UUID plus construction parent UUID, deposit source identity and action/application identity. Each needs acquired/unknown-start versus witnessed-start, retained phase, disclosure, and retirement rules.
8. **Action behavior**: inventory keys alone cannot establish coverage for attack hit/miss/block, body-only use actions, alternate loadouts, movement modes/connectors, interrupted/partial movement, reactive children and separate reaction roots. Concrete branch matrices must cover these behaviors even when no recipe key changes.

## Source-backed world and tile obligations

| Behavior | Existing owner / evidence | Required representation and proof |
|---|---|---|
| Initial/observed tiles, objects and connector snapshots | `player_reduction.apply_world_update`; `WorldUpdate` | Snapshot evidence at source event version; no invented action or cause. Tile change and connector replacement are not necessarily animations. |
| State staging for binding | `stage_lineage` | Absent contacts may be staged; this cannot authorize early visibility or narrative names. Bind evidence cuts separately from sampling time. |
| Door/lever state changes | `world_transitions`, `sample_world_transitions` | Explicit observed old/new values; hold observed prior pose until contact; acquisition alone has no opening animation. |
| Mechanism activation and projectile | `MechanismActivationFact`, `WorldTransition.projectile`, `world_transition_end` | Discharge, native result/contact, save hop and mechanism recovery distinct; fact may be meaningful without a visible actor. |
| World transition dedup | `merge_world_transitions` | Settled parent snapshot must not replay child change; repeated activation pulses remain distinct. Preserve native identity rather than dedup all equal-looking states. |
| Atomic surface update | `surface_reveal_delay` | Full residue after-values commit atomically at selected reveal delay, including wall-face changes without membership change. Do not split a native update into invented per-cell state commits. |
| Spatial cold acquisition | `register_spatial_lifetimes` | `applied_ms=None` means sustain without fabricated formation. Missing sight is not removal. |
| Creation before mechanical commit | `spatial_media_draw_commands` | Future shape may be sampled, but only with currently disclosed supports. Geometry admission and sight permission must be separate. |
| Partial field removal | `spatial_media_lifetime` removed_positions | Only witnessed removed cells retire. Disappearing visibility cannot trigger quenching/removal or narration. |
| Moving fields | `SpatialMediaMotion`, `spatial_field_media._moving_sight` | Old/new disclosed geometries plus independent permission sets; artwork translation never translates permissions. |
| Spatial damage responses | `SpatialDamageContact` | Actual committed packet identity and owner, retained contact and HP date; nearby creatures cannot generate contacts. |
| Construction section destruction | `register_construction_lifetimes` | Section identity and parent owner remain distinct. Parent collapse may affect multiple retained sections; partial dust is not whole-object retirement. |
| Construction sight loss | same | Clock survives without drawing undisclosed object or announcing break. |
| Suppression | perceived suppressions and draw exclusion volumes | Availability changes; original owner and start clock survive. Provider/source disclosure stays constrained. |
| Native deposits | `observed_deposits`, `register_deposit_starts` | Retain native fragment geometry/source, never infer full pool from partial cells. Only witnessed break/release starts intro; acquired pool sustains. |
| Remembered versus visible surfaces | app residue/deposit drawing | Ground memory and current airborne visibility are separate policies. Surface redraw is not an occurrence. |
| Item floor transfer and modifiers | `FloorItem`, equipment/item-effect facts/world update | Same item ownership identity, observed modifier/suppression state, no duplicate equipped and dropped item at commit. |

## Event and reaction traversal invariants

`presentation_groups` groups only consecutive reaction roots naming the following native root; unmatched reactions remain ordinary roots. `reduce_presentation_group` retains original native completion order. A new common traversal must not turn this presentation association into native parentage.

`walk_bound_timelines` includes nested movement and choreography with offsets. It is an appropriate existing traversal seam. New semantic annotations should be attached to existing bound owners and collected through this traversal, not derived by walking only `BoundChoreography.nodes`. Conditions, damage, world transitions, movement, body hops, portals, spatial responses and observation commits live in other collections.

State application remains `reduce_nodes` using versions/observations/world updates. Text output cannot become a second reducer. A save is not a damage result; canceled parent is not proof that all children were canceled; latest snapshot is not proof that an unseen action happened.

## Concrete architecture changes required in the revised plan

- Keep a finite sum of passive family payloads, with shared evidence/ownership/milestone references. Do not create an OO `Effect` hierarchy or force geometry, environment state and condition lifetimes into a universal bag.
- Existing lifetimes remain authorities for presentation dates. Cross-head milestone references point to them; no parallel universal lifetime store and no lookup by content name instead of instance identity.
- Extend coverage generation to the non-recipe denominators above. Each row names source input, current owner, operator, proposed representation, narrative disposition and evidence status.
- Include a complete **state-description** path alongside witnessed **occurrence** descriptions. Tile condition names currently are strings; they can support reported labels, not typed causality or inferred rule effects. Any additional semantic source field requires an actual demonstrated use, rather than parsing the labels.
- Partition temporal relations, sampling clocks and state evidence. Existing pure specialist samplers remain legitimate. Only content choices and reusable timing relationships move to authoring.
- Dedup occurrences by retained native edge/application identity, independently of whichever presentation group exposes them; distinct repeated applications stay distinct.
- Treat final compositing, caches and resource resolution as separate adapter concerns. Scene/narrative data cannot contain pygame surfaces, texture caches, NumPy depth arrays or Python callbacks.
- Imports flow from passive public data and resolved catalog to binding/sampling, then adapters. Narrative templates/operators cannot import live ECS systems or query their handlers.

## Evidence gate

For each family require a concrete source/bound-data encoding; a family is not covered by saying it will use generic tracks. Cases must include ordinary success, partial/canceled, initial acquisition, lost/reacquired visibility and relevant source ownership variations. These are source coverage obligations, not claims every Cartesian product needs a video.

Current review disposition: **changes required before plan freeze**, but proposed ownership direction is sound if the rewrite incorporates the above. Visual correctness remains unverified; no approval of current pixels or a future implementation is implied. A second pass must review the rewritten plan itself.

## Second pass: rewritten plan and full coverage report

Reviewed `agent_docs/SHARED_PRESENTATION_AND_TEXT_RENDERER_PLAN_2026-10-05.md` and `agent_docs/audits/FULL_PRESENTATION_COVERAGE_2026-10-05.md` after rewrite.

All substantive source-coverage/ownership findings above are represented: static world and material inputs, tile/connector facets, explicit non-fact channels, atomic WorldUpdates, native deposits, independent reaction roots, cross-head lifetime ownership, occurrence-versus-state semantics and source-specific instance identities. The plan correctly prohibits client-side gameplay-handler duplication and retains specialized functional sampling.

One requested textual tightening: the shared timing contract must explicitly reject dependency cycles, use stable topological evaluation with native version ordering for equal-time commits, and enforce commit causal floors despite visual anticipation. These are existing safety requirements from the earlier design, not a new scheduler feature.

**Disposition:** coverage-driven work plan approved subject to preserving that explicit timing invariant. This approves the proposed sequence and boundaries, not a frozen schema. Step A remains mandatory: actual received/bound examples for every effective variant, reviews of their encodings and explicit evidence gaps. There is no approval of production implementation, unseen visuals or runtime correctness from this documentation review. No production code was changed and no runtime test result is claimed.

### Final verification of requested tightening

Verified revised §4 explicitly states stable topological order/cycle validation, causal floors, equal-time native version ordering and no early HP/world commit from anticipation. §8 rejects missing required references and multiple producers and specifies stable native/track tie ordering. The requested condition is satisfied. **Approved: full-coverage audit/design work plan and its ECS boundaries.** Concrete schema-fit approval, production validation and visual acceptance remain the separate gates stated above.
