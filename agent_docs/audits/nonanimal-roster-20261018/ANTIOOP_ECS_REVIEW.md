# Independent anti-OOP / ECS plan review

2026-10-18. Reviewer: the task's separate Devil/native-owner subagent. Read-only source review, followed by this report only. No gameplay implementation, tests, asset changes or client validation were performed.

**Result: approved for the bounded plan. No required plan changes from this review.** This approves the proposed ownership and scope, not an implementation, complete character behavior, performance or rendered pixels. Implementation approval still requires the plan's actual behavioral checks and a fresh source review of the changes.

Reviewed [the saved authoring plan](../../plans/REMAINING_NONANIMAL_CHARACTER_AUTHORING_PLAN_2026-10-18.md), its [180-row inventory](roster_inventory.csv), current AGENTS.md/RECOVERY_PLAN.md and the native owners at selected base `454fae33fbacf55d7b77bf94feff250175d3dccf`. Compared relevant owners against the earlier audited base; the attack, spell, trait, health and spellcasting owners below have not changed. Existing spell/integration ancestry does not certify the proposed additions.

## Why the proposed ownership is sound

- The inventory is explicitly audit data. Runtime creatures continue through existing declarations/materialization, possessed items, intrinsic attack definitions and composed features. The plan introduces no per-sprite classes, generic signature interpreter, alternate registry or second combat executor.
- Assassinate uses the existing attack reading and critical outcome boundary. `dnd/actions.py:2281–2314` actually consumes handler-modified attack/AC readings and the final d20 critical status. `dnd/entity.py:247–292` upgrades eligible hits without making AUTOCRIT an automatic hit. Encounter ownership remains with `CombatantState` and its turn/surprise lifecycle (`dnd/encounter.py:188–219,755–802,854–855,937`). The plan explicitly forbids an Encounter import cycle, a duplicate trait clock and per-attack event replay.
- Evasion is correctly identified as a missing consumed behavior, not merely a missing registered condition. `SpellDamageRollResultEvent` has save success/fraction but lacks save ability (`dnd/core/events.py:5226–5253`); `resolve_saved_spell_damage` already provides a shared owner (`dnd/core/spell_damage.py:50–75`). Fireball and Burning Hands currently halve locally (`dnd/spells/evocation.py:993–1007,1112–1150`). The plan calls out these distinct routes and requires the selected real spell and nonspell save-damage routes to consume the minimum typed cause facts. It does not propose spell-name dispatch or a separate executor per source.
- Spell resistance belongs in the ordinary affinity resolution. `TakeDamageEvent` receives spell origin (`dnd/entity.py:3720–3737`); `Health.get_resistance` currently sees type and attack magic (`dnd/blocks/health.py:358–364,535–558`). The plan explicitly requires one resistance result, preserving immunity and preventing quarter damage from spell resistance plus matching type resistance. An early raw-damage halving handler would violate this requirement.
- Magic Resistance remains the separate existing saving-throw feature. Spell cause facts already come from current spell execution (`dnd/entity.py:4660–4671`), and `MagicResistance` consumes magical provenance through contextual save modifiers (`dnd/monsters/traits.py:1566–1591`). No redundant spell-resistance condition hierarchy is proposed.
- Help, poison, Brute, Fortitude, Parry and Leadership are bounded additions/repairs to existing action, modifier, hit/coating, health, reaction and area owners. Their named source gaps are explicit; the plan does not treat an existing class name as behavioral proof.
- Newly instantiated actions/conditions must use existing creation declarations, public discovery/selection and normal execution. Cleanup, cost policy and source ownership stay with their existing systems. Imports remain at module scope in a DAG.

## Concrete implementation gates retained by this approval

These clarify how to satisfy the written plan; they do not authorize extra subsystems.

1. **Assassinate must read actual opening-turn eligibility.** `turn_count` increments at turn completion, and the raw `surprised` flag is retained beyond the first round in current data. Neither field alone proves the required live eligibility. The neutral fact/query must reflect whether the first turn has begun/completed as appropriate and the actual surprise interval, including skipped surprised turns, joins and encounter restart. Do not add a parallel clock. Misses, including natural 1, must remain misses against a surprised target.
2. **Evasion must reach the final damage amount.** A handler on `SavingThrowEvent` or a registered Evasion trait alone is insufficient. Cover successful and failed DEX half-on-save packets across the local-halving spell route and any nonspell DEX-half route promised by the final trait. Keep CON saves, DEX effects without half-on-save and unrelated packets unchanged. Evasion's failed-save halving is separate from resistance, so a further legitimate resistance can halve that result; two resistances cannot.
3. **Fortitude needs pre-application critical provenance.** Current critical information is a `receive_damage` argument and a later `DamageAppliedEvent` fact, while Fortitude intervenes on `TakeDamageEvent` before health commitment (`dnd/entity.py:3661–3775`; `dnd/monsters/traits.py:1092–1124`). Carry the minimum critical fact to that existing interruptible boundary. Do not infer it from a later event or revive the actor after a death. Use the existing preview for damage-taken DC and temporary-HP behavior.
4. **Shared feature fixes must remain local to their real owners.** Brute must follow actual weapon die identity, Parry must honor live visibility/held weapon/reaction eligibility, and Leadership must read existing sensory/language/incapacitation facts. None needs a new generic behavior engine, actor subclass or world scan.

## Preserved scope and canonical content

The inventory contains exactly 180 source rows and 25 existing native/rig associations: 17 accepted Goblins, three accepted authored Devils, and five older mapped kits explicitly marked for reconciliation. The plan preserves the canonical Orc, Skeleton Archer, Dretch, Corrosive Demon and Dread Demon rather than replacing those recipes with earlier proposals. Reconciliation may create an explicitly selected adaptation; it cannot silently mutate a canonical creature to satisfy a source card.

The plan preserves accepted Psychic/Ember item ownership, the three existing powered backpacks and the native Shove adaptation. It explicitly excludes restored special-arrow IDs, ordinary ammunition/Loading/focus systems, Grapple, Imp Sting/Shapechanger, legendary economy, campaign redesign, new packing infrastructure and the obsolete renderer. Existing ground-to-ground flight is reused with its supported-endpoint policy; no new XYZ, hover or aerial-combat work is authorized.

The current Godot presentation work is a later phase in its own isolated checkout under its own instructions. Old rig data remains evidence only. This review does not certify that current client imports, source frame markers, sprites or shared effect memberships are already correct.

No implementation blocker was found in the saved plan. Its explicit consumer-level tests, source-gap qualifications and complete-roster exit conditions are necessary acceptance gates; passing this architecture review cannot replace them.

## Final draft recheck: A10 and conditional A11

Re-read the updated saved plan after the independent anti-slop findings. **Approval now covers the actual A01–A11 draft**, including Shield Bash, the conditional trained-unarmed kit, the explicit canonical Skeleton Archer decision, and the added Assassinate/Fortitude provenance guards. No further required plan changes from this review. The prior approval was for the earlier draft; this recheck is the evidence for the expanded final scope.

**A10 Shield Bash fits a bounded extension to the existing attack source and hit-save owners.** The proposal preserves a real equipped shield, baseline +7 / 2d4+4 Bludgeoning, and a DC15 STR Prone rider only for Medium-or-smaller targets. Larger targets still receive bash damage. It makes the selected Multiattack position/count explicit rather than adding another offhand action. This matches the recorded retained Footsoldier attack (`PACK_ROSTER_HIGHER_TIER_ENEMY_DRAFT_2026-10-01.md:148`).

Implementation must account for the actual source gap: `Shield` is an `EquippableItem`, not a `Weapon` (`dnd/blocks/equipment.py:288–315`); `get_weapon` explicitly returns no weapon for a shield (`:956–959`), so an ordinary offhand Attack currently uses unarmed behavior. Existing `HitSaveRiderFeature` also admits exact equipped weapon-source metadata (`dnd/monsters/traits.py:912–925,957–964`). Reusing these owners therefore requires the minimum explicit shield attack-source/spec admission, with the actual possessed shield identity and current equip/unequip state consumed by execution, discovery and the save rider. Do not disguise the shield as intrinsic anatomy, create a phantom weapon possession, globally turn all shields into weapons or implement a second attack executor. Size gates the rider, not admission of the damaging attack. Shared Brute must not add another shield die to the explicitly selected 2d4 baseline.

**A11 is a conditional kit decision, not authority to install competing proposals together.** The explicit P foundation removes Brute, Shield Bash and weapon Parry and supplies the authored Fist and Martial Guard; older table rows conflict in strike dice and defense. Phase0 now requires human disposition before adopting that numerical change. Existing unarmed strike dice/bonuses already have data owners (`dnd/blocks/equipment.py:699–703,848–860,1331–1355`), so no PC class/progression or new strike engine is needed.

The plan correctly identifies the remaining formula gate. `ArmorClassFormulaCandidate.requires_unarmored` filters body armor, while `allows_shield` only controls shield contribution (`dnd/blocks/equipment.py:654–672,1466–1489,1531–1536`). It does not currently exclude the formula while a shield is equipped. If P is selected, implement only that required eligibility distinction in the existing formula owner, preserving formulas that intentionally permit shields. Prove the selected AC before equipment, with armor, with a shield and after removal. Do not change an actor's fixed AC to imitate the formula or grant a Barbarian class because its ability terms happen to match.

The new rows and acceptance checks remain within existing ECS ownership. The final draft still preserves all25 current associations and does not restore ammo, Grapple, legendary economy, general transformations, a legacy renderer, a trait framework or expanded flight.

## Implementation review: abilities and mechanics, 2026-10-18

This is a fresh review of the working implementation based on `5779fecb60f0d65e5b9c70070ed190a17e0f930b`; it is separate from the planning approvals above. Reviewer: the current task's defensive-traits/poison subagent, independently reviewing the root agent's damage-defense changes. The review also records the inspected integration with the other owned mechanics. It does not certify bulk character authoring, final poison-kit supply/lifetime, A11's unresolved numerical choice, client presentation or balance.

**Result: approved for the implemented shared mechanics. No remaining ECS or ownership blocker found in this source review.**

- **Damage facts stay at the damage boundary.** `DamageSaveContext` carries the actual save ability, result and normal success fraction into `TakeDamageEvent`. Evasion reads those facts in `Health.preview_damage_event`, after the existing packet amount calculation and before ordinary affinities. It does not inspect a spell name, search earlier events or change a save result to imitate avoided damage. Native Fireball, Burning Hands, breath and trap controls exercise the consumed behavior; CON saves and effects without a half-on-success rule remain unchanged.
- **Spell resistance has one affinity owner.** `Health.get_resistance` combines explicit spell provenance with the existing type affinity once. Packet `Damage.effect_origin` takes precedence over the enclosing event origin. Ordinary magical attacks are not promoted to spells, matching resistance does not quarter damage, and immunity wins. Evasion and spell resistance use source-UUID grants owned by Health; rejected applications and exact condition removal release those grants. Repeated preview reads publish no events.
- **Fortitude intervenes before HP commitment.** `TakeDamageEvent.critical_hit` is supplied by the existing attack/spell delivery, rather than reconstructed from logs. Fortitude uses the target's existing damage preview and normal HP, skips critical/radiant damage and uses post-defense damage for its DC. It adds no revive/death executor or independent HP state.
- **Attack facts remain local.** Help and Assassinate use native contextual attack modifiers and encounter-owned opening-turn facts. Sneak Attack consumes the final attack-advantage fact carried by `DamageRollResultEvent`; it no longer looks up a parent event or uses dynamic attribute access. Brute reads the held weapon's actual damage die, including its existing override, and adds one die while preserving independent packets. Shield Bash retains a real shield identity and the ordinary attack/save-rider path; shields are not globally converted into weapons or anatomy.
- **Poison remains an item-owned coating.** One finite Assassin Poison dose uses the existing usable-item/action/condition lifecycle and the exact DC15 CON, 7d6 poison, half-on-success payload. The saved poison rolls as an ordinary hit even when the weapon critically hits; its raw roll and reduced result remain recorded separately. It creates no Poisoned condition. Explicit melee and ranged application choices coat the selected real weapon, including a tested crossbow, without an ammunition model. The existing configurable coating duration is retained pending the human's kit-lifetime decision.
- **Coated-item dispatch is bounded.** The existing Trigger index gained an optional exact source-item key restricted to damage-roll results. Coating handlers read the damage event's `source_item_uuid` directly. They do not replay the parent attack, scan actors/items, cache a wielder or install a second dispatcher. Passive dispatch evidence with two active coatings demonstrates one matching invocation for the attacking coated item, zero for an unrelated dagger, one for the same weapon after transfer and zero after removing its coating.
- **Reaction, support and admission ownership are preserved.** Parry uses the already-published post-roll attack execution, current visibility, the defender's real held weapon and the shared reaction budget; it adds no event phase. Leadership uses the existing anchored area, ten-turn duration and native short/long-rest resource. Removing its exact action releases that action's resource contribution. Hearing/language/agency checks read existing local owners; source Silence is a bounded query of the existing spatial index and an owned `blocks_sound` fact. Both Leadership and coating actions admit their own effect before installing gameplay state, so a refused effect leaves no aura/coating behind. Native interruption-cost policy is preserved.

No new event family, global rule registry, actor subclass, per-pack executor, late import or dynamic type/name-dispatch framework was introduced. The added source-item filter extends the existing trigger key; ordinary reads and applicability checks create no additional publications. These checks establish bounded work and observed dispatch behavior, not a new wall-clock performance claim.

Independent damage-defense validation: `uv run --no-sync python -m pytest tests/engine/test_roster_damage_traits.py -q` passed **35 tests in 0.74s** in the task's isolated environment. The final combined owner/integration batch passed **194 tests with 22 existing expected failures in 8.25s** across `test_assassin_poison_items.py`, `test_basic_poison_items.py`, `test_roster_defensive_traits.py`, `test_global_native_audit_regressions.py`, `test_gear_ownership_regressions.py`, `test_summon_retirement_ownership.py` and `test_roster_damage_traits.py`. The expected-failure marks were removed only for demonstrated coating/Leadership admission repairs; unrelated existing audit failures remain explicit.

## Human clarification review: unarmed damage, 2026-10-18

The plan-adherence reviewer re-read the updated plan and implementation record against the local Monk table and progression plan. **Approved as an authoring-data correction.** One die scales from d4 at reference levels 1–4 to d6 at 5–10, d8 at 11–16 and d10 at 17–20. Existing unarmed die/count fields already represent this; no Monk class, runtime level tracker, registry or additional events are needed. Each NPC's training tier, legal ability modifier and attack budget remain explicit kit choices, with no level inferred from CR.

The earlier review's P-foundation discussion records a superseded proposal. Neither the old 2d6/3d4 fists nor CON-based Martial Guard is selected by the human's damage-scaling instruction. Defenses and other Monk features require their own kit decisions. The poison clarification likewise retains one Assassin Poison definition and its existing configurable ten-round default; lifetime options do not create duplicate items. This update changes documents only, so no additional gameplay tests were required.

## Native family authoring implementation review, 2026-10-18

Reviewer: Help/Assassinate/Shield and humanoid-authoring subagent, independently
reviewing the root agent's `undead_roster.py`, `zombie_roster.py` and
`roster_casting.py`. This is a fresh source review of the authoring implementation,
not the earlier mechanics/planning approval. I authored the humanoid recipes and
do not present this as an independent review of my own forty-one-row family.

**ECS result: no architectural blocker found in the three reviewed modules.**
The two family modules use frozen authoring records and ordinary `Entity` data
composition, real possession grants, existing conditions/handlers/actions and
typed Multiattack configurations. They introduce no per-creature entity classes,
second attack executor, name-derived powers, global state/history searches,
late imports or new event families. Zombie source IDs select immutable creation
data; execution does not dispatch by vendor identity or clothing. The forty-six
fantasy zombie selections exclude the eight held and twenty-four modern rows.
The undead caster's explicit `archmage` authoring fact preserves its selected
Magic Resistance, spell damage resistance, expertise and at-will native
Invisibility; it does not rely on another module's profile-object identity.

The casting helper composes the existing exact innate-source, spell-entitlement,
resource and Cost owners. Finite daily uses remain normal long-rest resources;
at-will casts retain native action/concentration costs. Reaction source lookup
is bounded to the owning entity's existing exact spell entry. There is no
parallel source registry, hidden calendar or publication on a read. Unsupported
utility spells, controlled undead creation and silver-qualified Wight defenses
remain explicit omissions; canonical Skeleton Archer remains unchanged.

One source completeness observation was sent to the root: the undead Mage's
four source languages should be selected explicitly or the reduced Common-only
choice recorded. This is authoring data rather than a reason for another
capability/ancestry system. The source can understand-only language distinction
for the humanoid family's Elemental remains a disclosed current-owner limit.

Independent materialization/regression observation while reviewing integration:
**193 passed in 13.44s** across the humanoid authoring boundary, direct-item
runtime, Assassin Poison, existing Goblin roster and creatable-model suites.
That validates the shared constructor/possession changes and ordinary registry
closure; it does not independently certify all undead/zombie gameplay, artwork,
client playback or balance. Those remain covered by the parent's family and
broad validation evidence.
## Independent native composition review, 2026-10-18

The plan-adherence reviewer inspected native authoring after the human authorized
the remaining nonanimal NPCs. This review covers the new family modules and
their bounded shared-owner integration, independently of their implementers.
It does not replace the earlier shared-mechanics review or claim a new runtime
performance certification.

**Result: approved within the native authoring scope.** Entities remain data
structures and compositions of existing systems. No per-NPC Entity/action
subclasses, feature executor, second inventory, behavior registry or publication
stream was introduced. Passive frozen family records and factory closures
produce ordinary content declarations, recipes and configured Multiattacks.
The CSV and family evidence are offline audit data, not runtime lookups.

- Equipment owns the actual held weapons, shields, intrinsic anatomy and
  ordinary transferable possessions. Paired attacks reuse the existing
  contextual offhand-ability callback on the exact Equipment value; the
  non-light offhand permission uses its existing actor-owned grant. No weapon
  flags are changed globally and no stale attack template is removed to mimic
  a new bonus-action restriction. Shield Bash and Wight Life Drain reuse
  existing typed attack-replacement data for the actual selected weapon.
- Finite poison supplies extend the existing possession grant with a positive,
  inventory-only stack count and feed the builder's existing quantity argument.
  The poison builder uses the item's existing stack/max-stack lifecycle. It
  does not manufacture permanent coatings, ammo counters, dose entities or
  per-dose events. Silver Longsword, Regent claws and Sentinel anatomy are
  passive item definitions in the existing native builders.
- Authored innate sources identify the exact creature content reference.
  Accepting `creature.*` alongside the existing origin prefixes closes a
  demonstrated provider-validation gap without inventing a species/class or
  a source registry. Spellcasting owns source ability, rank and entitlement;
  ActionEconomy owns actual finite uses and long-rest recharge. At-will
  reactions use existing paired-none learned-cost facts and FreeSpellCastGrant.
  Ordinary Mage/Archmage slots and actual casting/reaction paths are preserved.
- Existing Protection was already a native NPC handler, but its old PC-root
  retirement filter prevented truthful new declaration dependencies. Admission
  now has one exact exception for that existing reaction in both builtin
  filters. It restores no class, class feature, PC choice or progression root,
  and adds no reaction implementation. Each selected NPC uses the same actual
  handler with a creature-owned behavior binding and ordinary reaction budget.
- Heavy Zombie gameplay exposed authored natural dice receiving an additional
  native-size d4. The existing size-damage owner now treats NaturalWeaponSpec
  like other intrinsic body attacks, using structural_base_size as its native
  anatomy baseline. Growth above native size still uses the same size rule.
  This is one owner correction shared by preview and execution; no heavy-zombie
  special executor, actor-name switch or second Enlarge modifier was added.
- New factories read passive selections and the new entity's existing owners.
  Runtime attack, defense, support and casting decisions continue through the
  shared native systems reviewed above. There are no world/history scans,
  shadow HP/resource clocks, cached wielder/source facts, late imports or
  dynamic attribute probing. Ordinary applicability reads introduce no new
  per-trait event publications.

Independent source/CSV accounting confirms all123 new definitions and all180
source dispositions, rather than a representative pilot. Existing inventory
qualification passes; the two static icon-ledger failures reproduce unchanged
on base5779. Current-client presentation, final balance and the eight visual
holds remain explicitly outside this native composition approval.

### Integration corrections after the independent family review

Root applied the fiend author's read-only Undead/Zombie observations: Parry now
declares its actual ParryFeature dependency (which owns the existing handler),
and the Berserker declares its existing Reckless Attack action. No action or
handler implementation changed. The undead Mage now has its four explicitly
selected source languages. Darkvision60 belongs only to the Wight foundations;
the Gladiator, Berserker, Mage and Archmage receive no inferred senses from
Undead type. The final family tests check that distinction. Final native
integration and base comparisons are recorded in NATIVE_AUTHORING.md.
