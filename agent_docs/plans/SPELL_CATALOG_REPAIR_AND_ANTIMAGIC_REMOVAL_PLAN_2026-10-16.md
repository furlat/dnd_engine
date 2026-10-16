# Spell catalog repair and Antimagic removal plan

Date: 2026-10-16. Worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
Branch: `codex/spells-rank-one-two`, current implementation over `a1349f52e8b`.
Status: proposed implementation plan; production implementation has not started.

## 1. Requested result and boundaries

The human requests a fixing plan for the full spell audit, explicitly including
**removing Antimagic Field and all the ad hoc engine work supporting it**.
Remove the live feature and its otherwise-unused machinery, rather than hiding
its catalog entry, disabling its handlers, retaining empty compatibility stubs,
or replacing it with another suppression framework.

Also repair the independent correctness and performance findings in
[the full audit](../SPELL_CATALOG_OWNERSHIP_AND_HANDLER_PERFORMANCE_AUDIT_2026-10-16.md).
Its [187-root inventory](../SPELL_CATALOG_AUDIT_COVERAGE_2026-10-16.csv),
[measured baseline](../SPELL_CATALOG_AUDIT_BENCHMARK_2026-10-16.jsonl) and four new
regression suites remain the evidence. Baseline qualification is 71 cases:
10 passing controls and 61 strict expected failures. Native scenarios exercised
51 spell identities; source review covered all 187. These counts do not imply
61 distinct spell identities are broken.

Preserve ECS composition, existing native event admission, condition ownership,
shared children, duration clocks, costs and factual publication. Reuse current
systems and proper owning handlers. No spell-name exceptions in Entity, damage,
conditions or the dispatcher; no new global effect manager, reaction manager,
size stack manager, cache registry or contribution interpreter. No late imports,
`getattr` workarounds or circular imports. No NDClient/Godot/frontend presentation work,
artwork changes, unrelated class features or new spells.

Rules preference remains BG3, then SRD 5.1, then eligible SRD 5.2 additions.
Do not use this repair to port every BG3 rule or expand spell identity scope.
The human has chosen removal; there is no pending decision about keeping AM.

Read before implementation: `AGENTS.md`, `RECOVERY_PLAN.md`, `HOW_TO_TEST.MD`,
the audit and this complete plan. Existing uncommitted class/spell work must be
preserved. This document does not authorize starting implementation in the
current planning turn.

## 2. What removing Antimagic actually removes

AM is one of four performance finding families, but has the widest cluster of
cross-system work. With an active field, an unrelated remote object move made
two world-item passes and 802 item snapshots at 100 registered items. Moving the
field also scanned every entity/area. It installed creation-return callbacks
even on never-suppressed berries, and those callbacks survived field removal.
Removing the feature eliminates these paths rather than optimizing them.

The evidence does not establish a percentage of total gameplay time saved:
profiled timings include normal operation work and instrumentation, and the
audit did not run a matched uninstrumented before/after removal comparison.
The heavy scans depend on an active field; merely registering the spell is not
equivalent to executing them. Some small AM queries currently run in other
mechanics even when no field exists, so those queries must be removed too.

Three independent costs remain: recipient handlers receiving unrelated events,
concentration searching old actor-target history, and Antilife Shell enumerating
all entities. Antilife's AM queries disappear, but its world scan still needs
repair. Removing AM does not cure the independent cancellation, damage,
immunity, lifetime, shared-child or granted-action bugs.

## 3. Removal inventory: delete, simplify, preserve

### 3.1 Live content and direct feature implementation

Delete the AM content reference, helper functions, zone and spell in
`dnd/spells/abjuration.py:3186–3618`, including item/entity/area refresh passes,
spell/transfer blockers, suppression mutation and retained creation/summon
return callbacks. Remove the matching imports/docstring entries.

Remove the `spell.antimagic_field` identity and metadata in
`dnd/spells/catalog_content.py`, the zone declaration in
`dnd/content_system/condition_definitions.py`, and the Cleric/Wizard spell-list
entries in `dnd/types/class_spells.py`. Remove the two exact live icon bindings
through the existing engine content-ledger/generation workflow. Do not import
artwork or edit NDClient assets. No current AM scroll or premade was found;
do not manufacture replacements or edit unrelated loadouts.

Expected content counts: **187 → 186** total identities, **182 → 181** primary
roots, level eight **six → five**, Cleric list **61 → 60**, Wizard list
**107 → 106**. Paladin stays 23. Recompute these through the actual installed
catalog, not a manually maintained second spell list.

### 3.2 Runtime removal matrix

| Source owner | Delete or simplify | Preserve and qualify |
| --- | --- | --- |
| `dnd/core/effect_types.py`; `dnd/actions.py`; `dnd/core/base_actions.py`; `dnd/items/property_composition.py` | Delete `AntimagicException`, its origin/spell fields and constructor arguments, and AM-only attack-path checks. Remove stripped magic bonuses, ability substitutions, dice filtering, the `ActionEvent.item_magic_suppression_provider_uuids` field and its item-property guard. | Ordinary `EffectOrigin`, base/effective rank, casting source, harmful/magical facts, weapon identity, magical damage/resistance and native spell-weapon handling. |
| `dnd/core/base_conditions.py` | Delete condition `suppression_provider_uuids`, `set_suppression`, `suppression_providers`, `antimagic_exempt`, AM return-handler fields and AM-only suppression callbacks. Simplify contribution activity by removing AM tokens. | Parent/additional-parent ownership, exact contribution-owner gates, shared children, membership admission/removal, clocks and Globe's spatial clipping records. |
| `dnd/core/base_block.py` | Delete AM provider lookup/seeding during condition preparation. | Prepared membership, required-child admission, rollback, replacement and factual publication. |
| `dnd/blocks/base_item.py` | Delete AM refresh method/calls, saved suspended placement, provider tokens, exemption state/method, and AM-only presentation fields. Remove `magically_created` and `creation_condition_uuid` and their dead authored assignments: their actual readers are AM-only. | `is_magical`, ordinary item/weapon contributions and actual lifetime identities: created-item batches, payload `lifetime_uuid`, Flame Blade lifetime, wall owner, guardian/feast owners. Keep `get_all_items()` for its existing non-AM container-disintegration caller; do not optimize that unrelated path in this batch. |
| `dnd/entity.py`; `dnd/game.py` | Delete `antimagic_presence_owner_uuid` and code solely servicing AM absent summons. | Generic suspended presence, prepared spatial returns, occupied-return retries, deployment checks and agency: Banishment uses them. |
| `dnd/spatial/area_conditions.py` | Delete AM queries during activation/move/change, `refresh_antimagic_suppression`, and absent-created-item anchor exceptions. Simplify protection application to Globe exclusion. | Generic anchor movement, Banishment-suspended entity anchors, own contribution gates, spatial transactions, footprint optics and Globe clipping. |
| `dnd/core/base_conditions.py::SpellProtectionRegistry`; `dnd/types/spell_suppression.py` | Delete `get_antimagic_suppressions`, `SpellProtection.suppresses_magic`, `SpellSuppression.antimagic` and their AM branches. | The registry and `SpellSuppression` provider/positions/geometry record. Globe excludes lower-base-rank spells from outside; that behavior remains. |
| `dnd/core/gridmap.py` | Delete `refresh_contribution_lights`, whose callers are all AM. | `set_block_light_suppressed` and ordinary anchored-light lifecycle; death, placement and Banishment need them. |
| `dnd/core/events.py` and maintenance callers | Remove AM-only handler construction. Rename the existing neutral `runs_while_suppressed` policy to `runs_while_owner_inactive` without a legacy alias; retain individual bypass arguments only where actual non-AM maintenance/expiry requires them, removing redundant AM-era arguments. | Maintenance while contributions are inactive. A verified non-AM example is Healing Incense following its holder while its mace is unequipped, so re-equipping resumes at the current position. Do not make damaging/healing effect handlers run under that maintenance policy. |
| `dnd/conditions.py`; `dnd/spells/conjuration.py`; `dnd/spells/necromancy.py` | Remove now-unreachable `on_suppression_changed` overrides for light/Feast/Harm compound owners. | Their actual commit/remove/membership refresh behavior and shared-source selection. |
| `dnd/spells/wall_constructions.py` | Delete AM exemption/refresh overrides and AM-only stone exceptions. | Actual stone/force construction, sections, destruction, provenance and Globe-clipped formation. |
| `dnd/spells/hit_effects.py`; `dnd/items/spell_payloads.py`; `dnd/monsters/spell_summon_actions.py`; `dnd/spells/evocation.py` | Delete AM guards in hit riders, payload blasts, magical technique propagation/warp/healing, Dancing Lights and Arcane Sword. | Physical propagation, Forcecage/Sphere contact, Globe, own conditions/lifetimes, actual save and damage delivery. |
| `dnd/classes/cleric.py`; `dnd/classes/paladin.py`; `dnd/classes/divine_intervention.py` | Remove turning/Divine Smite/feature AM lookups and Deity exception plumbing. | Source-owned class handlers, ordinary magical provenance, action/slot/oath costs, source resolution and all authored class effects. |

Trace the AM attack special case through `dnd/blocks/equipment.py` as well:
remove the `magical_properties_active` argument/false path if its only caller
is the deleted AM branch. Do not remove normal magical ability selection or
spell-created weapons. Include Equipment's magic-only inactive fallbacks in
`get_extra_damages` and weapon-profile handling (`equipment.py:568,1125`), plus
UsableItem's AM-era “magical properties suppressed” rejection
(`base_item.py:1397–1398`). Preserve general live-item/source validation and
Feeblemind's independent `blocks_magic_item_activation` gate. Follow actual
remaining reads before deleting any field;
an assignment alone is not a surviving use.

### 3.3 Shared protection and construction facts stay

Keep `BaseCondition.spatial_suppressions`, spell/area suppression outcomes,
`construction_suppressions`, provider geometry/positions and the corresponding
indexes/reducers in `dnd/world_facts.py`, sensory, player projection and audience
composition. Wall sections copy their owner's Globe records before footprint
clipping. Current AM-only tests for these facts do not make the facts AM-only.
Remove only the AM discriminator and AM producers/branches; retain provider
privacy, remembered hidden-cell state and actual clipping facts.

Generic contribution ownership also supports Paladin auras, item properties,
Healing Incense and shared effects. Keep it. Generic spatial/light suspension
supports Banishment and ordinary world lifecycle. Keep it. These are existing
working features, not reasons to retain an Antimagic implementation in disguise.

One existing coupling needs an explicit behavior check: SolidWallZone's stone
`antimagic_exempt` override currently bypasses both AM and Globe formation
filtering. Removing it changes that path. Use normal Globe admission/clipping
for a newly cast magical level-five wall; completed permanent stone remains
physical. The existing completion already detaches the parent and removes its
MAGICAL tag. Add formation inside/outside Globe and completed-stone versus a
later Globe/removal/destruction controls. Do not preserve this coupling with a
renamed exemption or add a future-protection manager.

### 3.4 Source contracts and generated SDKs

Remove AM-only provider-ID fields from their actual source owners:
`ConditionState` (`dnd/types/actor.py`), item/effect presentation states
(`dnd/core/item_types.py`), `VisualItem`/`FloorItem` (`dnd/player/facts.py`) and
their producers/capture/copy paths. Remove the `antimagic` discriminator from
`SpellSuppression` and its audience merge comparison. Retain ordinary
`suppressions` and `construction_suppressions` as explained above.

The live player schema is **10**, despite older README paragraphs mentioning 9.
Plan a single coordinated schema **10 → 11** change, with protocol version 1
unchanged. Use the repository's existing exporters, not hand edits:

```bash
uv run --no-sync python -m devtools.export_player_protocol
uv run --no-sync python -m devtools.generate_player_python
node sdk/player-typescript/tools/generate.mjs
```

This updates the schema, identity, OpenAPI, field ledger and current Python/TS
copies/types. The explicit handshake rejects old live peers. Keep immutable
historical packets/schemas/audit evidence; AM names inside them are historical
data, not live support. Archive the exact preceding contract using the existing
offline recording convention. Do not modify `pre-light-observations` or create
a blanket extra-field acceptance policy/runtime compatibility manager.

Determine the existing native cold-replay boundary before removing nested
fields. Preserve supported recorded facts through its existing passive/versioned
reader, or report an explicit unsupported old contract. Do not promise a new
campaign/native archive migration service. Old builds/books/preparations
explicitly containing the removed identity should receive ordinary clear
unsupported-spell validation, without silent substitutions.

## 4. Fix the independent correctness findings

### 4.1 SC-09: the 34 refused casts must not commit effects

Use the exact affected-root table in audit section “Exact SC-09 affected roots”;
each row already has an executed native regression. The source files are
`abjuration.py`, `conjuration.py`, `divination.py`, `enchantment.py`,
`evocation.py`, `illusion.py`, `necromancy.py` and `transmutation.py`.

For each authored path, resolve its native EFFECT admission **before** HP,
condition, action, concentration replacement, cure or spatial mutation. Return
the actual canceled event immediately. Move any provisional mechanics currently
performed before that admission to the existing admitted commit boundary.
For a retained condition, reuse `SpellAction.apply_owned_condition` and existing
prepared concentration/membership where appropriate; for an area/item use its
existing native preparation/commit path. Direct damage/healing remains its
spell's own effect after admission, with native factual events/provenance.

Do not add a generic dispatcher list of the 34 spell names, a global workaround
handler, or a second action executor. Do not merely overwrite the final result
or refund costs after unauthorized mutations. Preserve the current cost boundary:
declaration rejection does not pay; interruption after payment does not imply a
refund. A refusal must leave no new effect or destroyed previous sustain.

Keep the five passing controls: Bless, Charm Person, Magic Missile, Longstrider
and Antilife Shell. Extend matrix assertions where needed to retain an existing
concentration/target effect across a rejected replacement, include multi-target
children, and check real emitted facts/recording. Also inspect True Strike's
pre-EFFECT weapon attack as a finite same-boundary follow-up: add a native
reproduction before changing it, rather than declaring an unexecuted new defect.

### 4.2 SC-06: one Bestow Curse damage rider

In `necromancy.py::DamageCurseEffect`, remove `getattr` and the standalone damage
on every `ATTACK/EFFECT`. Reuse the existing owned native hit-rider path in
`spells/hit_effects.py`: one critical-aware necrotic component in the accepted
attack damage result, exact caster/target ownership, proper spell provenance,
no component on misses, and no damage before accepted damage admission.

Retain tests for normal/critical misses, hit/critical totals, native packets,
damage rejection, concentration removal and independent caster/target. Add
natural and spell-attack cases supported by the same factual packet path.
Bestow Curse's broader BG3 “attacks and spells” delivery is a real scope/detail
choice recorded in section 9; do not silently choose a per-cast versus
per-packet rule or let the bonus recursively trigger itself.

### 4.3 SC-01/SC-12: shared paralysis and healing prevention

Hold Person must retain a shared Paralyzed child using the existing
`add_shared_subcondition`/required-child ownership pattern used by Hold Monster.
Ending one parent must release only its lease. Do not restore actions or remove
another active hold's paralysis. Immunity/required-child rejection must not leave
an empty control parent or replace an admitted previous effect.

For Chill Touch, prefer a recipient-owned, source-specific ChillTouchEffect
using the existing neutral `blocks_healing` fact and `source_turn_expiry_handler`.
Remove the caster-side singleton tracker and cross-block fixed-name No Healing
replacement. Each source/recipient effect owns its deadline and undead modifier;
same-source refresh must not delete another recipient's still-valid effect.
Removing either source's effect, either order, must retain prevention until the
last source ends. Actual healing must remain blocked and resume only after the
final owner. A standalone native No Healing condition must survive unrelated
spell cleanup. This uses existing health/clock behavior, not a multi-caster
manager. Update the regression's setup to advance the real source turn or remove
the relevant actual effect; do not freeze its current caster-side storage.

### 4.4 SC-10: Hypnotic Pattern requires admitted Charmed

The owning Hypnotic Pattern effect must use required-child admission or the
existing prepare/commit composition so Charmed immunity/refusal rejects the
whole dependent incapacitation. Keep its direct transform and damage-break
handler owned by the parent. Do not add an immunity exception inside Charmed or
generic spell dispatch. Test native immunity, explicit child refusal, admitted
control, overlap with other charm and full cleanup/cost facts. Its Charmed
relationship must be source-specific: Paralyzed is shareable across casters,
but Charmed captures the charmer. Do not share a single contextual Charmed child
between different charmers.

### 4.5 SC-07/SC-08: size and bonus Dash belong to their conditions

Enlarge/Reduce must stop writing/restoring a raw prior `target.size`. Preserve
Entity's existing durable `structural_size_sources` contract. Add a small native
temporary-size source seam on Entity: exact owner UUID to signed size step,
resolved against durable/base size and clamped to the existing Size enum.
Recompute through existing durable-source mutation and temporary source
installation/removal. Same-spell replacement still follows native membership;
this is not permission to stack repeated Enlarge casts.

The Enlarge/Reduce condition installs its temporary contribution in
`_commit_application`, after admitted replacement retirement, and releases its
exact UUID idempotently in `_release_owned_runtime_state`. STR modifiers remain
ordinary owned modifiers. Rejected application/replacement never changes size;
removing the final owner restores the current durable size, not a stale snapshot.
Native state/stat publication must report the committed resolved size. Test
both modes, both replacement directions, native veto, bounds, durable size
changes, failed replacement and exact removal. The AM suppression case retires.

Expeditious Retreat grants one exact BonusDash action after committed membership,
with `contribution_owner_uuid` and an exact stored action identity. Release by
that identity through native cleanup, never by its display name. Preserve other
Dash grants and action entitlements. Use existing condition-owned granted action
patterns, not a new action-grant system. Test failed admission, accepted
replacement, actual bonus-action cost/movement, expiry/concentration and another
source's Dash surviving. The AM suppression case retires.

### 4.6 SC-02/SC-03: charm owner and harmful action admission

Generic Charmed owns a native handler preventing directly targeting its exact
charmer with harmful abilities/spells, alongside its existing attack/social
modifiers. Use native harmful-recipient intent/application facts and indexed
actor/recipient triggers; do not edit each harmful spell or use class checks.
Friendly effects and actions against another actor remain legal. Preserve
source-specific relationships and actual target rejection/cost semantics.
Use Sanctuary's actual direct-recipient distinction as a reference, without
turning incidental area contact into an invented universal damage immunity.

Charm Person gets a distinct spell sustain/condition with a source-specific
Charmed relationship, finite native duration and its own damage-break handler.
Reuse the existing Animal Friendship/Charm Monster source-key pattern. Sharing
is valid only among parents for the same charmer; different charmers need
distinct contextual children and exact cleanup, preserving native Charmed
immunity identity. No global relationship manager is needed. Recommendation under
the existing BG3 preference: **10 turns**, ending on actual positive damage
from the charmer or a current ally. Zero damage/refused damage and unrelated
enemies must not end it. Select the source from actual damage facts, not display
labels. Do not put damage-break behavior into generic Charmed.
Keep existing combat save advantage/recipient eligibility and exact upcast
recipients. Charm Monster/Animal Friendship are references for ownership,
not templates whose different authored ending/duration rules should be changed.
Test two charm sources, source cleanup, another Charmed effect, immunity,
expiration and friendly/unrelated damage. BG3's duration/early-ending reference:
[Charm Person](https://bg3.wiki/wiki/Charm_Person).

### 4.7 SC-05/SC-11: Haste and finite deadlines

Haste must explicitly allow self and accept the caster's own identity without
looking for self in its contact table. Keep nonself LOS/range and paid cast
semantics. Self Haste must spend the ordinary cast action and grant the existing
separate restricted budget. Keep Haste ending lethargy and existing Slow
interactions.

Give Hold Person, Bless, Bane, Haste, Blur and Slow their finite ten-turn native
spell deadlines; keep Hold Monster/Mirror Image as passing controls. Put the
deadline on the actual sustaining effect/root, so concentration and independent
recipients release correctly without double progression. Use the engine's
existing turn/round duration ownership, not a new timer system. Test natural
expiry through real turn progression as well as the current public duration
boundary, early concentration loss, repeat saves and multi-target releases.

Base-level Bestow Curse lasts ten turns. The verified BG3 upcasts use 20/50/100
turns at ranks 4/5/6 and retain concentration
([reference](https://bg3.wiki/wiki/Bestow_Curse)). Ranks 7–9 fall outside BG3;
the SRD 5.1 fallback gives 24 hours at 7/8 and until dispelled at 9, without
concentration from rank 5 in that fallback. Make the selected rank policy
explicit in spell data/tests rather than accidentally leaving all ranks
permanent or taking concentration away from the BG3-defined variants.

### 4.8 SC-04 after removing its AM reproductions

The three AM-specific Shield/Counterspell/Hellish Rebuke tests become obsolete;
their disappearance must not be reported as a completed reaction redesign.
Keep normal learned/innate/free-source reaction cost and targeting controls.

Hellish Rebuke independently continues after its own ActionEvent is canceled
(`infernal.py:205–221`). Add a native own-declaration/execution/effect refusal
reproduction without an AM fixture, then honor that real admission/cancellation
before save/damage. Preserve source/slot/innate costs according to the point at
which rejection occurs. Also add finite non-AM refusal probes at Shield's own
buff admission and Counterspell's actual reaction event: Shield currently
changes interception before checking buff admission, and Counterspell callers
ignore the returned reaction cancellation. Repair an independently reproduced
failure at its actual owner, not by assuming the removed AM test proves it.
Do not build another reaction framework or add a reaction prompt solely to
replace a removed spell.

## 5. Fix the three remaining performance paths

| Finding | Exact change | Meaningful qualification |
| --- | --- | --- |
| SC-P2, recipient event fanout | Add `event_source_entity_uuid=recipient` to known-recipient turn handlers and `event_target_entity_uuid=recipient` to Sleep/Hypnotic damage handlers. Keep processor safety checks. Use existing Trigger indexes at `core/events.py:2346`. | Recipient turn/damage still saves/wakes/breaks; unrelated actors produce no dispatch for that recipient's owner, observed through native passive dispatch evidence. No new dispatcher. |
| SC-P3, concentration history | Store one exact last-committed publication ref or bounded after-value on the existing Concentrating owner; use `EventQueue.get_event_by_uuid` for an exact ref. Compare current state to that publication without searching actor history. Reuse existing prepared-removal previous-state receipts. | Initial publication, unchanged/changed state, multi-target, multiple slots, device concentration, replacement/removal, JSON/replay and observer exceptions after storage. Adding 10,000 unrelated target records must not add historical predicate work. No global latest-state manager. |
| SC-P4, Antilife world scan | Remove AM lookup, query `_occupants_at(old footprint ∪ swept footprints)`, deduplicate and apply existing living/dead/construct/undead/crossing rules. Keep portal-transfer handling. Check only relevant crossing-line cells rather than rebuilding a whole live footprint for every edge. | Walking the shell into living creatures ends it; already enclosed occupants and boundary behavior stay correct; remote actors do not affect candidate work; undead/construct/dead and portal transfer controls. No new spatial index. |

For SC-P3, seed/advance publication evidence at the actual committed-store
boundary. An observer throwing after storage does not erase a committed fact;
rejected preparation must not advance the remembered publication. Keep memory
bounded by the owner, not by the number of events.

SC-P2 source sites: Hold Person/Hold Monster/Power Word Stun/Sleep in
`enchantment.py`, Fear/Hypnotic in `illusion.py`, Blindness/Deafness and both
Bestow Curse turn handlers in `necromancy.py`, Sunburst blindness in
`evocation.py`. Do not replace intentional spatial/zone subscriptions with
recipient filters or lose source-gone expiry fallbacks.

Shared area turn handlers also construct trigger-position sets. This remains
source-level follow-up rather than a measured blocker in this batch. Keep
overridable trigger subregions: Wall of Fire/wall constructions can trigger in
different cells from `affected_positions`. Do not substitute that field blindly.

## 6. Test and diagnostic migration

### 6.1 Keep the independent regressions

Keep SC-01/02/03/05/06/07/08/09/10/11/12 regressions. Remove a strict xfail only
after its desired outcome passes, and keep the regression as an ordinary test.
The 34 canceled-cast matrix cases must pass; do not weaken their expectations,
claim a fixed number of retained tests or delete a test just because it is red.

Retire exactly five new audit cases that require removed AM gameplay: the three
`test_antimagic_prevents_*` reactions, the Enlarge AM suppression test and the
Retreat AM suppression test. Keep Enlarge replacement/refusal and Retreat
refusal tests. Add Rebuke's ordinary admission test as described above.

### 6.2 Older AM suites and mixed coverage

The AM retained-contributions suite is mostly obsolete, but first move
`test_structural_item_immunity_source_is_not_mistaken_for_a_condition` to the
ordinary immunity/lifecycle suite: it uses no AM and must survive. Retire the
remaining AM-only cases in `tests/engine/test_antimagic_retained_contributions.py`
and the manual AM spell exercise `tests/manual/test_128_antimagic_field.py`.

| Existing mixed tests | Migration |
| --- | --- |
| `test_anchored_condition_inputs.py`; `test_nature_spell_delivery.py` | Remove only AM parameters/imports; keep the other anchors and Globe protection cases. |
| `test_prepared_condition_lifecycle.py`; `test_high_level_spell_fields.py`; `test_spell_handoff_necromancy.py` | Retire AM field replacement, partial-AM Antilife and Eyebite-in-AM cases; keep ordinary atomic condition replacement, Antilife contact and Eyebite admission/retirement. |
| `test_bg3_spell_hit_riders.py`; `test_bg3_spell_items_and_repeats.py` | Retire magic-arrow-through-AM/berry-return cases; retain ordinary physical+magical weapon damage, item lifetime and owner cleanup. |
| `test_high_level_spell_payloads.py`; `test_high_level_spell_review_regressions.py` | Retire suppressed-payload deadline and suppressed-Sphere shove cases; preserve ordinary payload expiry/blast and Sphere contact/removal tests. |
| `test_local_optical_inputs.py`; `test_sensory_movement_origin.py` | Keep ordinary Darkness movement/optics-before-light; replace partial-AM Fog setup with native footprint change/removal to preserve the optical invariant. No fake suppression provider. |
| `test_chain_lightning_selection.py`; `test_banishment_dimension_door.py` | Preserve actual primary-to-secondary contact/propagation and travel/return/admission tests; remove their AM-only fixture/assertions and rename accordingly. |
| `test_jaw_traps.py` | Retire AM-only cases; retain existing independent Web/Jaw and standalone-restraint lease cases. |
| `test_bg3_rank_one_two_spells.py`; `test_low_level_spell_review_regressions.py` | Retain Mockery/Dissonant and other native turn deadlines with ordinary clock input; drop field setup, not expiry assertions. |
| `tests/player/test_projection_local_world.py` | Use an actual Globe provider for provider revision/construction clipping/hidden-cell after-value coverage. Keep generic suppression records without an AM discriminator. |
| `test_high_level_spell_summons.py`; manual catalog identity exercise | Remove unused AM imports/expected AM identity; do not revive obsolete manual server imports. |

### 6.3 Performance evidence after removal

Keep the old audit/raw measurements unchanged as historical evidence. The current
manual diagnostic loses nine AM item/move operations and four AM creation-return
operations. Keep the three concentration, three unrelated-turn and three
Antilife samples, updating reported counters after fixes. The old AM-query
counts are not post-removal performance claims.

Add a normal no-AM baseline for remote object movement, movement with 4/16
Goodberries and ordinary created-item/summon lifecycle. Native passive evidence
must show no installed AM/retained-AM-return handlers. Record operation work
after setup and preserve structured profiler output. Avoid private-method
monkeypatch assertions and noisy wall-time gates. Compare matched normal
operations if reporting an elapsed-time saving; no invented total percentage.

## 7. Implementation order and checks

1. **Baseline and finite tracking.** Read the plan/test guide, preserve dirty
   work, run the new audit suites, and record the exact AM and remaining shared
   call graph. Assign a plan-adherence sub-agent for implementation as required
   by AGENTS. No implementation starts in this planning turn.
2. **One coherent AM removal slice.** Remove content, feature, dead runtime
   fields/queries/callbacks and their source-schema producers; simplify shared
   readers and rename the neutral maintenance flag. Migrate mixed tests and
   regenerate current contracts together. Cold imports/content bootstrap and
   supported SDKs must agree; no intermediate no-op shim is the delivered state.
3. **Accepted effect boundary and damage.** Fix SC-09 and Bestow Curse's
   established attack rider, plus reproduced non-AM Rebuke cancellation.
4. **Correct owners.** Repair shared paralysis/healing prevention, required
   charm admission, size receipts, bonus Dash and charm ownership.
5. **Eligibility and clocks.** Repair self Haste and finite native durations,
   including explicitly selected rank behavior. Complete the relevant new
   behavior tests rather than just removing xfails.
6. **Remaining measured costs.** Apply the exact-recipient trigger changes,
   bounded concentration publication and local Antilife candidates. Run matched
   diagnostics once the corresponding mechanics pass.
7. **Batch qualification and reviewer signoff.** Run the affected gameplay,
   progression, spatial, item/summon and player/SDK suites; lint/import checks,
   generated export verification and `git diff --check`. Update the engine
   handoff/counts/schema notes. Obtain anti-slop and anti-OOP review of actual
   implementation and plan-adherence confirmation before reporting completion.

Use `uv run --no-sync python -m pytest` in the configured Linux environment.
Target the new audit suites plus existing ownership/prepared-lifecycle,
high-level controls/fields/payloads/summons, Banishment/travel, construction,
optics, hit-riders, created items and class interaction suites. Include real
player HTTP/record/cold-replay and Python/TypeScript SDK qualification when
regenerating the contract. Run `npm test` from `sdk/player-typescript` and the
Python SDK tests with their documented environment. Reuse existing direct
build/caster fixtures; no external-service/browser/NDClient work is needed.
Existing local HTTP/SSE integration tests remain part of engine qualification.

## 8. Completion criteria

- No live AM identity, class entry, spell/zone/helper, query, exception, token,
  saved placement, dedicated callback or AM-only public field remains. Cold
  composition fails clearly on the removed identity. Runtime source search
  has no AM dependency; historical documents/archives are explicitly excluded.
- Globe formation/admission/clipping, constructions, Banishment and occupied
  returns, optical source lifecycle, magical weapons, payloads and summons keep
  their native behavior and factual evidence.
- Every retained correctness regression passes without xfail. AM retirement
  has an explicit test disposition; independent bugs are not closed by deleting
  their counterexamples. Additional cases have native behavior assertions.
- The remaining measured handler/history/spatial work is bounded by the
  relevant recipient, owner or footprint, not unrelated entities/events/items.
  Measurements distinguish profiler overhead/setup from native operation cost.
- Source contracts and both current SDKs agree on the new schema/identity;
  recordings follow their explicit old/offline contract. NDClient remains out
  of scope; the handoff states the exact wire removals and new schema.
- Anti-slop reviewer, anti-OOP reviewer and plan-adherence monitor approve the
  implemented scope. This plan itself is not evidence that fixes are delivered.

## 9. Concrete decisions and limited open points

**Chosen by the human:** remove AM, including its dedicated machinery; keep
working within this worktree; reuse native systems; no NDClient work. No second
permission question is needed for those decisions when implementation is later
authorized.

**Recommended defaults, derived from existing scope:** preserve old artifacts as
history instead of mutating them; reject removed-spell build inputs normally;
retire AM wire fields in schema 11; keep actual Globe/Banishment/ownership
mechanisms; use BG3's ten-turn Charm Person and real charmer/allied damage break.
These are explicit recommendations, not imaginary prior human agreements.

**Bestow Curse spell-damage breadth needs a concrete choice before extending
it.** BG3's [Additional Damage variant](https://bg3.wiki/wiki/Bestow_Curse:_Additional_Damage)
describes attacks and spells; the current audited path only implements attack
events. Recommend fixing the proven attack bug first, then including saved and
automatic spell damage through one existing factual packet admission seam with
one explicitly defined bonus per accepted delivery, no recursion and no duplicate
bonus when a spell attack traverses both roll-event kinds. Pin Magic Missile,
rays, a save spell and an ongoing spell in tests before widening it; do not
silently infer per-cast/per-component semantics from the wording. This is not a
reason to delay the independent removal and established regression repairs.

**Native historical replay:** implement only the already-supported passive
contract handling discovered in phase 1. If a retired-field adapter is actually
required for an existing supported recording, keep it narrow and tested at
that offline boundary; otherwise keep the old contract explicit. Do not add a
new migration service or keep live AM models for possible future compatibility.

## 10. Review record

Plan reviews completed on 2026-10-16:

- **Anti-OOP: approved.** Required source-specific Charmed relationships rather
  than one child shared across charmers, and explicit new/completed stone
  formation behavior after removing the coupled exemption. Both corrections are
  incorporated. Confirmed neutral inactive-owner maintenance, ordinary spatial
  return and actual item lifetime boundaries.
- **Anti-slop: approved.** AM work is deleted rather than replaced with another
  framework; remaining performance repairs use existing indexes/owners; baseline
  claims and retired test dispositions stay explicit.
- **Plan adherence: approved.** All 12 correctness and four performance finding
  families have an explicit repair/removal/reproduction disposition, with class,
  content, generated contracts, mixed tests, historical records and handoff
  coverage. No production implementation is claimed.

These are independent plan reviews, not human approval to begin this plan or
implementation signoff. Production code and tests were not changed in this
planning turn. Actual implementation still requires its own adherence monitor,
qualification and final reviews described above.
