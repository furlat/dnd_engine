# Remaining producer evidence after body/reaction and retained lanes

Bounded source audit, 2026-10-05. This supersedes completed entries in timing-remaining-producer-lanes.md, not the wider presentation plan.

Remaining concrete producer families:

1. `choreography._bind_jump` and `bind_motion`: existing elapsed increments from physical legs, jump-media lead, hidden-boundary dwell and actual nested/landing group completion. Preserve admitted event identities; never infer hidden route points. `_flight_path_phases` supplies existing takeoff/landing classification and `_resolve_motion_body` adds selected recovery duration. These currently remain clocks without producer operands. No per-frame trajectory nodes needed.
2. `choreography.preceding_damage_commit` and `bind_standalone_damage`: the maximum of earlier same-recipient applied HP clocks; existing directed response serialization/start and response.contact_ms delay; sweep contactDelayMs override; final start passed to `damage.bind_damage`. Annotate the branch that actually wins, including the sweep override, not a fictional maximum of both delays. `damage.bind_damage` itself owns applied contact/HP/damage-body timing outside attack/cast owners.
3. `choreography.bind_life_transition` and `bind_lifecycle`: actual death/body transition ends, owned-versus-unowned life distinction, and departure's existing maximum of prior target damage/life-body ends. `entity_lifecycle.bind_entity_lifecycle` owns phase body/media durations. Preserve native life/departure identity separately; no new death mechanism.

Already annotated in bounded lanes: cast/attack producer clocks, AreaReach joins, world/sensory floors, body/equipment joins, reaction/interruption/child gates (two provenance corrections under review), portal/standalone displacement/shove, condition transitions, six retained-owner registrations and condition fade bound.

No claim that all source references form one globally linked DAG: some are explicitly measured external admission anchors. Per-frame fades, marker carousel, sprite modulo and trajectory sampling remain ordinary deterministic sampling, not missing scheduling systems.
