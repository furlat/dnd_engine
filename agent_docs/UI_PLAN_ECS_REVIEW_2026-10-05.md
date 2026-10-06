# Player UI plan: independent ECS/import-DAG review

2026-10-05. Reviewer: schema_fit_antislop acting as independent ECS reviewer. Source/design review only; no production edits or test run. Reviewed rewritten PLAYER_UI_PLAN, linked targeting/log/character contracts, native Session gate/command capture, observer PlayerActor projection, replay encoding, encounter initiative/context, action discovery contracts and world-authoring owners.

## Initial verdict

Architecture is acceptable, but two incompatible contract statements must be reconciled before unconditional approval. These are bounded plan corrections, not requests for new systems.

1. **Target selection contract differs between integrated plan and native study.** Main section6 requests minimum/maximum and `as_selected|fill_primary|reject`. Targeting study section6 specifies current mandatory primary, existing num_projectiles cap, completion status plus `selected_only|fill_primary`, and explicitly rejects an invented minimum field. Use one exact contract. Recommendation: keep the source study's two-value completion semantics and complete-prefix validation; reject is a validation result, not a competing allocation mode.
2. **Combat-log retention limit differs.** Integrated plan says10,000, linked log contract says2,000. Choose one limit and ensure oversized active/single groups have the same bounded truncation policy. This is configuration consistency, not an architecture defect.

## Accepted boundaries and concrete implementation obligations

- **Passive UI / native execution:** retaining original AvailableActionInfo templates only inside Session, with detached serialized facts and a generation-scoped selection handle, preserves native configured variants and private source state. The current Session accepts action/target objects directly; the planned adapter must resolve the handle against its retained original result rather than execute the detached copy. Discovery invalidation and active `_current_player` gate are required together. No UI import of Entity/Encounter needed.
- **Displayed history versus live commands:** sheet/resource/initiative values are additional authorized passive snapshots, not widget queries. Native creation already provides semantic origin/class and initial ability fields; current PlayerActor lacks them. Subsequent effect/turn/resource commits need captured updated values. Selecting another portrait does not grant its observer history or change command ownership. Two humans remain existing combatants/controllers, not a new party ECS entity.
- **Shared geometry:** selection metadata follows existing DrawCommand transformations through boundary, fixture, terrain and world-depth cuts. InteractionFrame consumes final painter order/coverage. This avoids a second spatial resolver. Nonselectable opaque foreground coverage must still block hits; only post-composite physical body/equipment participates for actors. Raster masks belong in Pygame adapter, not native packets or semantic WorldHit.
- **Affordances / approach:** exact authored action/provider identity and source-item/target/connector binding make world classification data-driven. Existing manual contact can forward hypothetical origin to existing attack contact; approach filters native Move candidates and preserves their route/cost/exposure. Remote descriptor is explicitly non-executable. After displayed movement settles, fresh native discovery and exact operation match are mandatory. No client BFS, no predicted chest contents, no fabricated attack-object action.
- **Target metadata:** native combination validation and effective allocation remain in action owners. Typed variant facets belong in existing discovery records. Controls retains UUID/world-point choices and handles stale-generation cancellation; it must not parse tokens/names or switch on spell identities. The scope names actual missing metadata rather than inventing a generic formula evaluator.
- **Log capture:** node UUID identity owns ordinary projected logs; standalone immunity uses encounter-log append identity and observer projection at capture. Extending existing recorded sequences with optional append data is coherent and does not manufacture a rules event. Operation completion gates are conservative display boundaries, not causal ancestors. Listener removal and generation reset are required; replay must preserve append data rather than losing it through convenience decode return values.
- **Imports:** dnd stays unaware of game/UI. game/session is application/native bridge; passive game/UI types may import native value contracts, never live owners. Rendering geometry remains downstream of sampling. Rich text, panel state and selection reducer are functions/passive records; no widget inheritance/service locator/dispatch registry is justified.
- **Persistence:** full-world save is deferred. No easy live-world restore was found; passive recordings are not playable restores. The character study has been rewritten to remove the superseded character-only format proposal and speculative resource/coating persistence lane entirely. Creation drafts and live inventory remain in scope.

## Validation limits

This approves a design boundary, not implementation completeness. Each step still needs its requested source review and native tests. Critical behavioral proofs are exact template execution after detachment, historical snapshot nonleakage, second-member inspection without mutation, hidden initiative exclusion, post-cut world picking, approach interruption, repeated-target order and standalone-log replay. Full rendering/rules rewrites are not prerequisites for this UI scope.

## Recheck / final plan verdict

**Approved for implementation from the ECS/import-boundary perspective.** Root reconciled both findings: integrated section6 now uses `selected_only|fill_primary`, existing cap/repeat flags and native complete-prefix preview without speculative minimum; the linked log study now explicitly uses the integrated10,000-row bound and retains its oversized-group trimming/promotion policy. No architectural blocker remains in the reviewed design. This does not waive per-step/final implementation review or the behavioral proofs above.

### Final tightened-version recheck

Reviewed the subsequent integrated sections4/9/10 and linked pure-selection/Space clarification. Approval remains unchanged:

- Window solid component, actor through aperture and empty traversal aperture now have explicit picking priority; the aperture does not enlarge an attack hitbox. This is a clearer presentation contract without new mechanical targeting.
- Registered descriptor/icon authority is preserved. Exact direct-reference records fill only genuinely unregistered semantic IDs; the resolver does not probe/fallback across parallel ledgers. Player portrait preference changes presentation only.
- Sheet/resource/initiative/log additions name their passive payloads, authorization and existing presentation commit/operation-completion gates. Existing HP/items remain single-owned; historical display is not refreshed from current native state. Append-only immunity capture remains observer-bound and operation-gated.
- Selection previews now share pure native predicates instead of invoking arbitrary action validators during hover. Space/Enter semantics agree across plan and source study.

No new ECS/import/disclosure boundary blocker introduced by these refinements. Final review remains design approval only, with implementation acceptance gates intact.
