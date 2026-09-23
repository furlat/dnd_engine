# Approved four-spell handoff — queued after current corrections

The artwork task delivered user-approved Inflict Wounds v11, Hellish Rebuke v4, Shatter v8 and Misty Step v4. Intake is complete; these are **not yet production-integrated**. Current user priority is restored approved Fire Bolt and correct Sleep fall/rest/hit/wake.

Frozen source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-next-spells-approved-v1`.
Requested genuine camera-direction supplement, now delivered: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-next-spells-directions-v1`.
Both HANDOFF.md and the base manifest were read. The supplement manifest maps each E/SE/S/SW/W/NW/N/NE direction to back/front pages. It retains the original SE art. No asset audit or hash validation belongs in runtime.

Native study already performed:
- Inflict Wounds is an existing melee spell action; bind finite target-ground media at its actual successful hit, omit on miss. No caster translation.
- Shatter already owns its 10-foot sphere, simultaneous Constitution saves and Thunder damage; use area-ground media, preserve native affected cells and walls. No animation-driven damage propagation or invented knockback.
- Hellish Rebuke is an existing damage reaction, but its processor currently creates an ActionEvent with no semantic behavior identity. Study normal native event admission/provenance before wiring its reaction presentation; do not infer from display names or lose reaction ancestry. Effect belongs on the triggering attacker.
- Misty Step already uses a body-action relocation with real Spatial LEFT/ENTER children and subjective departure-only/arrival-only clips. Preserve one committed relocation. Add finite stationary departure/arrival mist on shared authored tracks; do not turn it into a projectile, duplicate the body or leak the unwitnessed endpoint.

Art contract: straight alpha, full fixed cells/pivots, 144Hz observations, rear → actor → front. Ground registration already includes torso height for Inflict/Hellish. Exact palettes drive actual hand layers and the existing 150ms damage flash. Preview timestamps are audition offsets, not hardcoded native event times.

Before implementing, finish the bounded shared-path design for Hellish reaction identity and Misty endpoint media, then obtain the required anti-slop and ECS reviews. Root owns integration; artwork task is consulted only for necessary new renders. The requested eight-view banks are now available, so they are no longer a blocker.
