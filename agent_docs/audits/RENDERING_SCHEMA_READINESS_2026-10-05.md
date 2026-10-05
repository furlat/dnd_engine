# Rendering readiness audit before schema migration

2026-10-05. Status: source inventory and independent branch reviews complete; per-combination timing/disclosure/visual certification remains open. No production migration is authorized by this document.

The user's correction governs this work: understand all current rendering behaviors and specify their repairs before freezing a structure that otherwise changes at every exception. The [earlier presentation plan](../SHARED_PRESENTATION_AND_TEXT_RENDERER_PLAN_2026-10-05.md) is provisional. Its previous architecture reviews are not approval that its schema covers the implementation.

## Evidence and denominator

The reproducible [inventory](rendering-readiness-20261005/inventory.py) loads the effective catalog with the encounter's complete rig set. It does not decode artwork or execute encounters. [Provenance](rendering-readiness-20261005/provenance.json) records the revision, relevant source/data hashes and rig paths.

- 149 effective cast recipes, 5 attack recipes, 85 body-action recipes.
- 160 condition recipes, 25 spatial-media recipes, 3 construction-media recipes.
- 44 rigs and 44 creature-rig assignments.
- 27 public fact kinds, with an additional damage-stage distinction.
- 420 candidate source dispatch branches. The AST search is an index, not proof of exhaustive control-flow coverage.
- Historical gallery manifests provide 348 case rows across the original 298-case gallery and 50-case repair gallery. Direct spell identities link 142 of 149 cast recipes. Seven unlinked identities require alias/reaction/variant resolution; this does not establish missing recordings.

Artifacts: [effective catalog](rendering-readiness-20261005/effective-catalog.json), [spell matrix](rendering-readiness-20261005/spell-matrix.csv), [detailed spell evidence](rendering-readiness-20261005/spell-matrix.json), [feature owners](rendering-readiness-20261005/feature-owners.json), [candidate branches](rendering-readiness-20261005/dispatch-branches.json), [historical cases](rendering-readiness-20261005/historical-case-links.json).

Existing coverage reports four missing cast bindings. Counterspell is actually selected through its reaction body-action recipe; Aegis Spark belongs to a developer extension; Necrotic Bless and Prismatic Spray were already documented as backend definitions without full cast recipes. Do not call these four new asset regressions or invent replacement visuals. Inventory ownership resolution needs improvement.

## What the structure must represent

Keep five responsibilities distinct, using existing ownership wherever possible:

1. **Received evidence:** exact projected node/version, resolution/application identity, observations and world updates. This controls what either renderer may know.
2. **Bound presentation:** selected authored recipe, attachments, measured gesture/socket data, explicit dependencies and semantic descriptions. Native ancestry is preserved; presentation dependencies do not fabricate gameplay causality.
3. **Retained lifetime:** existing condition, item-effect, concentration-slot, spatial-owner and construction-section histories. Cross-action references use these identities rather than another parallel lifetime map.
4. **Sampling:** pure family-specific operators evaluating geometry, materials, loops, crossfades and historical trails at a time. Their internal mathematical constants are not automatically authoring settings.
5. **Output:** graphics draws samples; narrative describes meaningful witnessed occurrences/current observations. An invisible sample is not an ended condition, and a particle is not a narrative event.

A finite maximum-of-anchors scheduler can resolve joins. It cannot replace continuous samplers or retained histories. The common contract must expose their clocks and dependencies without turning every equation into a scripting language.

## Blocking design repairs

| Gap | Required design repair | Evidence to demonstrate before migration |
|---|---|---|
| Dependencies outside child lists | Bind AreaReach destruction prerequisites, previous reach, Sensory observed changes and reaction triggers into explicit references from their actual source fields; define empty/unknown cases | Zero, one and multiple destruction prerequisites; independent reaction root; observation commit |
| Lifetimes span actions | Reference existing retained owner milestones and preserve original clocks | Suppression/reactivation, reacquisition, consumption, return, partial destruction |
| Initial state differs from an occurrence | Separate state inspection, first observation and witnessed application; deduplicate native membership edges across groups | Cold snapshot, hidden changes then reacquisition, nested repeated exposure |
| Fact-only completeness misses inputs | Include observations, world updates, cancellation receipts, logs/attribution and factless nodes | Child-only damage with unknown caster; snapshot-only gear/HP change |
| Generic start/end loses meaning | Distinguish removal, suppression, loss of sight, expiration, consumption, partial retirement and return | No removal animation or narration caused merely by sight loss |
| One clock loses frozen/overlapping phases | Preserve local sampling clocks, frozen outgoing samples and independently advancing masks | Interrupted projectile, condition release, maintained loop crossfade |
| One completion time conflates jobs | Keep contact, mechanical commit, body availability and decorative completion distinct | Trail cannot delay movement; damage cannot precede its assigned impact |
| Coverage labels omit provenance | Add exact source-to-application-to-marker-to-commit evidence in the eventual verification harness | Repeated A/B/A missiles distinguish request/result pairs and separate impacts |

Source anchors: `game/player_facts.py:164,408,429`; `game/choreography.py:159,229,726`; `game/player_projection.py:1153`; `game/presentation_coverage.py:186`; `game/condition_media_lifetime.py:124`; `game/concentration_media.py:50`; `game/item_attachment_lifetime.py`; `game/spatial_media_lifetime.py`.

## Rendering family obligations

Each row requires a concrete encoding example and retained fixture, not just a claim that generic tracks can handle it.

| Family / owner | Behavior that must survive |
|---|---|
| Cast sprite — animation_draw, animation | Prepare/travel/impact; billboard versus XYZ; application identity; registration; ground/world/overlay depth; support cuts |
| Cast attachments — cast_media | Release/contact dates, displayed pose/socket, hit/miss selection, recipient clearance and admitted cells |
| Finite body material — finite_material | Interior strength and pulse curves, local age and recipient deduplication |
| Arcs/lines/ground strikes — directed_media | Individual arrivals, propagation links, advancing fronts and charge/contact/decay overlap |
| Plasma/ribbon/darkness — directed_* | Current versus release socket, per-application age, camera-facing geometry, deterministic procedural tails |
| Particles/strips/vapor — particle_media | Local ballistic age, recorded landing support, progressive reveal, historical vapor origin |
| Weapon trails — weapon_trail_media | Measured blade history, contact retiming, distinct flash lifetime and explicit unavailable-pose behavior |
| Motion — motion_media | Leg-start condition selection, cadence through corners, reaction holds, takeoff/landing; tails do not extend joins |
| Stationary media — stationary_media | Following versus frozen attachment, original facing, temporary missing socket without lifetime termination |
| Interrupted delivery — interruption_draw | Frozen incoming carrier with advancing reaction/mask clock; camera reprojection still works |
| Actor composition — animation_draw | Item UUID ownership, body materials, hit flash, copies, shadows, distortion, absence and painter roles |
| Condition phases — condition_sampling | Intro/hold/release, frozen outgoing formation with moving release mask, phase overlap |
| Condition ownership — condition_media_lifetime | Quiet reacquisition, last-owner removal, counted copies, activation; head-marker cycling is display only |
| Maintained media — maintained_media | Unknown start, hold phase, loop crossfade, delayed removal bank/fade |
| Spatial dispatch — spatial_media_draw | Orbit, modules, assembly, field and whole-bank geometry; per-family disclosure requirements |
| Moving fields — spatial_field_media | Old/new sight grants, translated geometry, support and fringe ownership; permission does not move with artwork |
| Cell modules — cell_media | Stable variants, witnessed per-cell retirement, owned versus decorative pixels, complementary frame mixing |
| Fire walls/rings — wall_media | Canonical ordinal, arbitrary path orientation, hot side, front/rear depth; full-shell disclosure for whole rings |
| Thorns/wind/frigid air — wall_assembly_media | Physical shell selection, curved sections, formation/damage contacts and removal |
| Constructions — construction_media/surface | Section versus owner destruction, collapse/dust, suppression, formation versus native commit |
| Orbits/wakes/motes — orbit_media/component_particles | Historical samples, continuous phase and original/translated ownership; no per-mote narration |
| Tethers — sustained_draw | Disclosed concentration slot/endpoints, moving muzzle, intervening section disclosure |
| Portals — portal_draw | Opening/departure/arrival/settling/closing, independently known endpoints, apertures and actor clipping |
| Absence/return — absence_media | Witnessed departed/returned pose, native disposition, distinct envelopes |
| Deposits/residue — deposit_draw/surface_residue | Recorded geometry, landing reveal, material age; remembered ground versus currently visible airborne matter |
| Environment/devices/items | Object-state pose, apertures, wreck transition, owned item modifiers and suppression |
| Final composition — registered_media/volume_media/area_media/media_blend | Shared rounding/registration, XYZ and boundary cuts, painter grouping, frame mixing after independent depth cuts |

These specialist operators are not automatically duplication. The audit must separate justified geometry/material math from duplicated ownership, scheduling or spell-specific dispatch.

### Concrete authoring-boundary debt to resolve

These are not confirmed visual defects. Record current behavior and decide whether each is an asset constraint or an authorable choice:

- `absence_media.py:72`: return-source retiming literals 1020/720/300 ms.
- `wall_assembly_media.py:117,143`: thorns removal 1000 ms and quiet-air geometry envelopes 750/850 ms.
- `weapon_trail_media.py:46`: donor contact fraction and active/history bounds.
- `directed_media.py:486`: ribbon lifetime/envelope constants.
- `orbit_media.py:164`: 32 Hz/16-frame source assumptions.

Do not expose every shader constant as a schema field. Asset metadata owns actual source timing; recipe data owns content choices; operator constants stay implementation when they define reusable math.

## Public evidence and narrative crosswalk

| Inputs | Required distinctions |
|---|---|
| action, attack, spell | Root/child, identity disclosure, item/body origin, hit/miss/block, interruption, reaction result, repeated application |
| area_reach | First/later reach and disclosed destruction prerequisites |
| movement, step | Received path only, committed step, hidden path, mode/connector and interrupted continuation |
| forced_movement, shove | Attempt versus actual/partial/zero displacement, landing and child damage |
| portal_transfer | Committed/failed and independently disclosed departure/arrival |
| damage | Taken/request versus applied/result, temp/normal HP, zero result, unknown source, resolution/application identity |
| saving_throw, death_save | Success is not necessarily no damage; optional rolls and rerolls |
| heal, temporary_hit_points | Blocked/full/partial/zero healing, grant/replacement/loss; no fabricated restoration |
| life | Dying/stable/dead/revive, disposition and associated body transitions |
| condition, item_effect | Apply/remove/change, consume/expire/suppress, creature/item owner and original clock |
| equipment, item_charge | Loadout versus inventory, charge consumption/recharge, destruction, snapshot-only changes |
| spatial, faction | Commit version, birth/departure, control loss versus ordinary faction change |
| sensory | Initial/delta, source dependencies, remembered state and contact changes |
| spatial_effect_state, mechanism_activation | Footprint/state changes, known origin, committed versus failed activation |
| object_damage, object_destroyed | HP versus destruction, section versus whole, remains and disclosure |
| turn | Start/end/round/encounter, state-only policy and unknown identity |
| observations/world updates | Newly observed current state is not evidence of the unseen action that produced it |
| cancellation metadata | Phase, spent economy, outcome and completed surviving children |
| factless logs/attribution | Admit permitted content without inventing a cast or mechanical event |
| initial persistent state | Describe existing state without fabricating application time |

Narrative occurrence identity must survive duplicate exposure of the same native edge in different groups. Repeated actual applications remain distinct. A group identifier alone is not sufficient deduplication.

## Verification work required before freezing

For every effective supported combination record:

`public channel/variant → source branch → source references → clock owner and measured markers → proposed encoding → fixture/perspective → evidence status`.

Evidence statuses remain separate: declared, input observed, binding observed, timing compared, disclosure asserted, visual reviewed. All current spell-matrix visual reviews are pending; archived clips are not fresh acceptance.

1. Resolve aliases and reaction owners, then finish each family encoding example against actual bound data. Record unsupported authored content explicitly without adding features.
2. Build dependency/clock evidence for repeated applications, cross-action conditions, construction/visibility commits, cancellation and hidden-source outcomes. Existing traces omit some bound collections and record state dates without complete provenance; describe the required additions before implementing them.
3. Inspect combinations visually by meaningful differences: motion/socket, geometry, palette/material, rig/body size, camera, attachment and lifecycle. Reuse shared-family evidence only where the same operator and parameters justify it. Audit every spell's semantic assignment separately.
4. Review transition boundaries immediately before/at/after impact, commit, suppression, retirement and return. Settled-state equality cannot detect an early HP change.
5. Check paired observers separately from four cameras. Four cameras share one observer's permissions; they cannot prove information safety between observers.
6. Compare procedural text expectations with the same evidence: hidden attacker stays unknown, initial condition is not newly applied, no narration per decorative particle, blocked healing remains a factual outcome.
7. Close design gaps with independent anti-slop and anti-OOP/ECS review of concrete mappings, then revise the implementation plan. Migration cannot begin with unrepresented existing behavior disguised as a generic fallback.

## Independent review disposition

Three read-only reviews covered finite/persistent graphics branches, ECS/fact/lifetime ownership, and serialization/coverage. All found material omissions in the provisional plan. Findings are incorporated above. This is a reviewed audit of readiness gaps, **not approval of a finished schema**. No runtime tests or production edits were needed for this documentation pass; visual and timing work is still required.
