# Production fact repairs — 2026-10-22

Human authorization: “ok fix all three”, following review of the production
content blocker document. Preserve the existing uncommitted summon work.

## Scope and acceptance

1. Ice full-section Disintegrate: a real cast removes an actually observed wall
   section. Each entitled audience receives exactly one typed destruction fact
   with its previous contact, alongside the existing removal/Frigid Air effects.
   An unobserved section must not leak. Preserve Stone partial cuts and Force
   whole-owner retirement. Capture contact at the exact removal source boundary,
   before folding that source, using the existing walk-local observation guard.
2. Earth Myrmidon Burrow: the real child Landing action publishes its existing
   authored identity and parentage, preserving movement, costs and damage. Bind
   this transient child through existing runtime admission; do not grant another
   selectable action or change generic Entity.perform.
3. Arcane Sword: actual cast/move/repeat actions expose one independently observed
   retained blade anchor, with movement, sight loss/reacquisition, reconnect and
   linked removal. Compose a visible one-cell SpatialCondition child under the
   existing lifetime owner: FIELD, OVERLAPPING, INDEPENDENT_MOVABLE, no crossing
   channels, blocking, hazards or turn handlers. Relocate that same child and keep
   any retained owner coordinate aligned after successful movement. Move also
   supplies the existing ActionFact.target_position. Keep caster source_position
   and spell attack outcomes unchanged. Seeing the caster alone must not reveal
   the blade. Use existing spatial wire fields; no new sensory framework or API.
   Final review found that point placement alone leaves stationary repeat attacks
   without a durable caster/blade join after reconnect. Complete this same repair
   by publishing the actual accepted concentration slot on the observed marker
   through existing concentration_slot_uuid. This opaque reference on the
   observed blade resolves only against independently disclosed actor/item slot
   state; it carries no caster UUID or position. Keep it stable when caster sight
   changes, avoiding an unnecessary dependency in sensory invalidation.
   Resolve the native slot once after commitment, then create the blade with
   that metadata already present. This also prevents provisional blade creation
   if concentration admission fails. Do not invent a slot ID, scan all entities,
   or add a wire field.

## Execution and checks

- Record pre-change timings before source edits: bounded warmup and samples for
  affected operations/publication, plus an ordinary control. Record filesystem
  and environment; compare meaningful costs and event counts without chasing
  roughly one millisecond of busy-machine noise.
- Add regressions at real native action/application publication boundaries;
  retain worker/replica coverage for lifecycle and reconnect. First demonstrate
  the omissions, then implement the three bounded repairs.
- Run focused regressions and relevant wall/spell/projection/content checks;
  rerun the same timing setups. Broaden only for unresolved concerns.
- Record implementation, evidence and limitations in this plan and a backend
  client handoff. No client edits, other-chat communication, commit or push.

## Required independent review

- AntiOOP/ECS and ongoing plan adherence: production_facts_ecs_review.
- Antislop/scope: production_facts_scope_review.
- Reviewers must reject unrelated gameplay changes, raw hidden-anchor leakage,
  whole-operation observation borrowing, generic scans or new architecture.

Status: implemented and reviewed. Final combined validation: **219 passed,
1 xfailed in 57.37s**. No commit or push was requested or made.

## Implementation and evidence

- Ice: removal-only scheduling includes observed source cursors and captures the
  currently authorized object contact before the exact source fold. Four cases
  cover normal observation, prior sight loss, same-cast sight loss and veto.
- Landing: admit the transient child through the existing behavior gateway.
  A character-created level-11 Wizard's real rank-six summon/Burrow verifies
  identity, causal parentage, two-seat publication, damage, movement and costs.
- Arcane: one inert linked spatial point, real accepted concentration-slot join,
  move destination, and creation only after both memberships are accepted. Tests
  cover two casters, stationary/moving repeats, detached reconnect, caster/blade
  sight independently, drop, expiry and owner/concentration/blade vetoes.

The final combined run included all new regressions, solid-wall worker capture,
object looks, retired recording, emitted-update replicas, trap hardware,
high-level spell worker transport, duration/reinitialization, protocol schema,
content admission, remaining walls, spell fields/summons, spatial channels,
crossing declarations, spell catalog composition and condition/action identity.
Earlier focused runs and failing-before proofs are recorded in the linked audits.
`git diff --check` also passed for the three source slices and recovery pointer.

Both independent reviewers passed the final bounded changes. Review found and
closed two Arcane gaps before acceptance: a missing durable two-caster join and
provisional blade publication before a rejected concentration application. The
slot reference is deliberately immutable public metadata of an observed blade;
matching it requires separately public actor/item state. This avoids inventing
a sensory invalidation dependency merely to forget an already known association.

The [client handoff](../PRODUCTION_FACT_REPAIRS_CLIENT_HANDOFF_2026-10-22.md)
contains exact field usage and validation limits. Raw timings and reproducible
probes are linked from the [Ice audit](../audits/PRODUCTION_ICE_FACT_REPAIR_2026-10-22.md),
[Landing audit](../audits/PRODUCTION_FACT_REPAIRS_2026-10-22/landing_validation.md)
and [Arcane audit](../audits/PRODUCTION_FACT_REPAIRS_2026-10-22/arcane_validation.md).
Ice/Landing and ordinary control show no meaningful regression. Sword creation
and relocation add bounded observation/publication work; final native plus
capture/decode/fold medians are 13.9/4.7/4.9/7.4 ms for cast/move/stationary
Strike/moving Strike. No new Godot rendering or full live-match timing is claimed.

## Separate pre-existing finding

A broader run of `tests/architecture/test_creatable_models.py` failed
`test_a_summon_spell_builds_its_forms_content`: FlamingSphere/SpiritualWeapon's
shared factory now constructs InnateFlight, but `_SPELL_CONSTRUCT_FORMS` lacks
that prebuild declaration. Source comparison confirms this comes from the earlier
uncommitted summon work, not any of these three repairs. It remains unchanged;
the final selected run excludes that file and is not a claim of a clean full suite.
