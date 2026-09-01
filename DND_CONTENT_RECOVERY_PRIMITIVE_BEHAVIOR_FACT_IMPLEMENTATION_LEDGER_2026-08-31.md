# Primitive behavior-fact implementation ledger

Date: 2026-08-31  
Status: `BF-2_COMPLETE — ACCEPTED`

## 1. Boundary

This is the mandatory documentation-only BF-0 checkpoint required by
`DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_SEQUENCE_AMENDMENT_2026-08-31.md`.
No production or test file was edited while producing it.

The implementation boundary is one existing runtime fact path:

```text
behavior_id: str
provided_by_id: str
origin_root_id: str | None
```

`BehaviorBinding` additionally retains its internal, non-serialized
`runtime_owner_uuid` solely to reject rebinding one live behavior to another
owner. `semantic_key` remains policy/grouping data and is not provenance.

This checkpoint does not authorize a new registry, resolver, service, manager,
provider object, DTO, compatibility path, event path, callback layer, live
registry lookup, reflection, late import, or circularity exception.

## 2. Governing bytes

| Authority | SHA-256 / identity |
|---|---|
| Checkout HEAD | `205fd679fde51d5319d332f12ec241d7aecd93a6` |
| Accepted sequence amendment | `8300f661bfc629de52f4aa3316ab935d9129d20dae549510277c0c1a9bd5d0de` |
| Accepted sequence amendment substantive bytes | `7a91ed5d2d7e9fbcaf914a6ca0f0b95c9b00d657dc946fc59756960d789467cd` |
| Accepted direct-item plan | `51b06ddd6c67742fe32dee8f7bb729a72134d54df1805d6b434ad68dba24ae0b` |
| Direct-item Slice 0 ledger | `c98f181888e57f2c126129ff1f97649cc0eb60bf7cbbdf3792f992b1862c781c` |
| CR-0 evidence manifest | `fdcd5c32b7ded90bb52e94fbb492181416b735eaddc4a3e0956540b613dbaa65` |
| `AGENTS.md` | `296ce0a99c52fab93261a15e193258b928c0b56c161b91ef8e412f5d27897668` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| Accepted implementation evidence only | commit `513dd97` |

## 3. Exact declaration admission inventory

The CR-0 static owner proof resolves exactly 395 current
`behavior_identity` declarations without importing live owner classes.

| Inventory | Rows | Normalized SHA-256 |
|---|---:|---|
| Sorted, newline-terminated behavior IDs | 395 | `03ab6e3d9a36a12c906dbae99557624f5dc619b279d4f39bd1b370ef4d8541a5` |
| Canonical `identity_key::runtime_kind` rows | 395 | `0974b426567769530c16c4d29f07f1a01f19a1036d7123cc18c748c38e528870` |
| Class-admitted `ID<TAB>path::symbol` rows | 393 | `32def5f9c6b71951e938e67b837cf6c5da30b3b5455713d72144ae57cf4ca2b0` |
| Provider-only function IDs | 2 | `29d815c92acb7cf72ce70d0d265628801acd10980dbe03a3b51bcc753337b00f` |

Every ID is non-empty, namespaced, unique, and maps by exact
`ContentRef.content_id`. No composite `identity_key`, display name, callable,
or Python path is a runtime behavior ID.

The two disjoint provider-only rows are exactly:

```text
trait.origin.half_orc.relentless_endurance
trait.origin.halfling.lucky
```

They enter only through explicit structural grant. Mapping generic
`EventHandler` to either function declaration is forbidden.

### 3.1 Existing and missing cold by-class views

The existing three by-class maps cover 320 rows:

| Existing view | Rows |
|---|---:|
| Action | 58 |
| Condition | 153 |
| Spell | 109 |

Their sorted, newline-terminated `ID<TAB>path::symbol` rows have SHA-256
`79a752a5d160c917c0892f98bbb7a16a35af6a2e46716366fb463bc329961e38`.

`REACTION_BEHAVIOR_DECLARATIONS` is presently only a tuple; production has no
reaction by-class map. Therefore the remaining class-admitted inventory is
exactly 73 rows, using the same normalized row format, SHA-256
`1223ba3061682d0d62284bd1169b547b9313a9fbf54be3be92cab95a173b55a1`:

```text
action.attack                                      dnd/actions.py::Attack
action.attack_object                               dnd/actions.py::AttackObject
action.dash                                        dnd/actions.py::Dash
action.disengage                                   dnd/actions.py::Disengage
action.dodge                                       dnd/actions.py::Dodge
action.drop_concentration                          dnd/actions.py::DropConcentration
action.hide                                        dnd/actions.py::Hide
action.jump                                        dnd/actions.py::Jump
action.move                                        dnd/actions.py::Move
action.origin.dragonborn.breath_weapon             dnd/origins/dragonborn.py::DragonbornBreathWeapon
action.pick_up                                     dnd/actions.py::PickUp
action.shake_awake                                 dnd/actions.py::ShakeAwake
action.shove                                       dnd/actions.py::Shove
action.swim                                        dnd/actions.py::Swim
class_feature.barbarian.unarmored_defense          dnd/classes/structural_feature_definitions.py::BarbarianUnarmoredDefenseStructuralFeature
class_feature.fighter.remarkable_athlete           dnd/classes/structural_feature_definitions.py::RemarkableAthleteStructuralFeature
class_feature.sorcerer.draconic_ancestry.black     dnd/classes/sorcerer_structural_feature_definitions.py::BlackDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.blue      dnd/classes/sorcerer_structural_feature_definitions.py::BlueDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.brass     dnd/classes/sorcerer_structural_feature_definitions.py::BrassDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.bronze    dnd/classes/sorcerer_structural_feature_definitions.py::BronzeDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.copper    dnd/classes/sorcerer_structural_feature_definitions.py::CopperDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.gold      dnd/classes/sorcerer_structural_feature_definitions.py::GoldDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.green     dnd/classes/sorcerer_structural_feature_definitions.py::GreenDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.red       dnd/classes/sorcerer_structural_feature_definitions.py::RedDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.silver    dnd/classes/sorcerer_structural_feature_definitions.py::SilverDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_ancestry.white     dnd/classes/sorcerer_structural_feature_definitions.py::WhiteDragonAncestryStructuralFeature
class_feature.sorcerer.draconic_presence           dnd/classes/sorcerer_structural_feature_definitions.py::DraconicPresenceStructuralFeature
class_feature.sorcerer.dragon_wings                dnd/classes/sorcerer_structural_feature_definitions.py::DragonWingsStructuralFeature
class_feature.sorcerer.elemental_affinity          dnd/classes/sorcerer_structural_feature_definitions.py::ElementalAffinityStructuralFeature
class_feature.sorcerer.metamagic.careful_spell     dnd/classes/sorcerer_structural_feature_definitions.py::CarefulSpellStructuralFeature
class_feature.sorcerer.metamagic.distant_spell     dnd/classes/sorcerer_structural_feature_definitions.py::DistantSpellStructuralFeature
class_feature.sorcerer.metamagic.empowered_spell   dnd/classes/sorcerer_structural_feature_definitions.py::EmpoweredSpellStructuralFeature
class_feature.sorcerer.metamagic.extended_spell    dnd/classes/sorcerer_structural_feature_definitions.py::ExtendedSpellStructuralFeature
class_feature.sorcerer.metamagic.heightened_spell  dnd/classes/sorcerer_structural_feature_definitions.py::HeightenedSpellStructuralFeature
class_feature.sorcerer.metamagic.quickened_spell   dnd/classes/sorcerer_structural_feature_definitions.py::QuickenedSpellStructuralFeature
class_feature.sorcerer.metamagic.subtle_spell      dnd/classes/sorcerer_structural_feature_definitions.py::SubtleSpellStructuralFeature
class_feature.sorcerer.metamagic.twinned_spell     dnd/classes/sorcerer_structural_feature_definitions.py::TwinnedSpellStructuralFeature
class_feature.sorcerer.sorcerous_restoration       dnd/classes/sorcerer_structural_feature_definitions.py::SorcerousRestorationStructuralFeature
condition.blinded                                  dnd/conditions.py::Blinded
condition.charmed                                  dnd/conditions.py::Charmed
condition.concentrating                            dnd/conditions.py::Concentrating
condition.dashing                                  dnd/conditions.py::Dashing
condition.deafened                                 dnd/conditions.py::Deafened
condition.disengaging                              dnd/conditions.py::Disengaging
condition.dodging                                  dnd/conditions.py::Dodging
condition.exhaustion                               dnd/conditions.py::Exhaustion
condition.frightened                               dnd/conditions.py::Frightened
condition.grappled                                 dnd/conditions.py::Grappled
condition.hidden                                   dnd/conditions.py::Hidden
condition.incapacitated                            dnd/conditions.py::Incapacitated
condition.invisible                                dnd/conditions.py::Invisible
condition.no_reactions                             dnd/conditions.py::NoReactions
condition.paralyzed                                dnd/conditions.py::Paralyzed
condition.petrified                                dnd/conditions.py::Petrified
condition.poisoned                                 dnd/conditions.py::Poisoned
condition.prone                                    dnd/conditions.py::Prone
condition.restrained                               dnd/conditions.py::Restrained
condition.stunned                                  dnd/conditions.py::Stunned
condition.unconscious                              dnd/conditions.py::Unconscious
condition.underwater                               dnd/conditions.py::Underwater
reaction.class_feature.barbarian.retaliation       dnd/classes/barbarian.py::RetaliationReactionHandler
reaction.class_feature.fighter.protection          dnd/classes/fighter.py::ProtectionReactionHandler
reaction.class_feature.paladin.divine_smite        dnd/classes/paladin.py::DivineSmiteHandler
reaction.monster.parry                             dnd/monsters/traits.py::ParryReactionHandler
reaction.opportunity_attack                        dnd/reactions.py::OpportunityAttackHandler
reaction.spell.counterspell                        dnd/spells/abjuration.py::CounterspellReactionHandler
reaction.spell.hellish_rebuke                      dnd/spells/infernal.py::HellishRebukeReactionHandler
reaction.spell.shield                              dnd/spells/abjuration.py::ShieldReactionHandler
spell.acid_flask                                   dnd/items/spell_items.py::_AcidFlaskSpell
spell.counterspell                                 dnd/spells/reaction_spell_content.py::CounterspellLearnedSpell
spell.hellish_rebuke                               dnd/spells/infernal.py::HellishRebukeLearnedSpell
spell.shield                                       dnd/spells/reaction_spell_content.py::ShieldLearnedSpell
spell.thaumaturgy                                  dnd/spells/infernal.py::Thaumaturgy
```

BF-1 adds immutable by-class views beside those owners/declarations. Cold
bootstrap merges the three existing views and these domain-local views into one
read-only 393-row constructor input for the existing `BehaviorBinder`. It is
not a runtime registry and is never rebuilt from live classes.

## 4. Runtime consumer and caller freeze

### 4.1 Runtime fact types

`BehaviorBinding` or `AuthoredBehaviorAttribution` occurs in exactly 17 files,
path-list SHA-256
`2de227884fc52e19e25c47961e3e470d2f448eac9e8b510c9acfb9b55a769a2e`:

```text
dnd/content_system/behavior_bindings.py
dnd/content_system/runtime.py
dnd/core/base_actions.py
dnd/core/base_conditions.py
dnd/core/content/runtime.py
dnd/core/events.py
dnd/entity.py
server/player_replication/mapper.py
tests/architecture/test_dependency_boundaries.py
tests/content_identity.py
tests/manual/test_121_canonical_presentation_mapper.py
tests/manual/test_139_condition_presentation_contract.py
tests/manual/test_172_behavior_runtime_binding.py
tests/manual/test_181_action_content_identity.py
tests/manual/test_181_affordance_content_identity.py
tests/manual/test_neurodragon_spell_item_content_factories.py
tests/progression/test_saving_throw_context.py
```

The server mapper is a deprecated presentation consumer. It imports the engine
binding and projects its three old refs into server DTOs. The accepted
in-process/no-server boundary forbids migrating that projection here, and the
primitive IDs cannot truthfully be converted back into `ContentRef` values
without reviving the removed catalog/transport coupling. It is therefore a
governed excluded consumer: BF-1 changes the active `dnd` runtime fact path and
does not edit server files. Server presentation recovery must consume the
primitive fact contract in its own later scope; no compatibility property or
synthetic ref is added to keep this deprecated mapper working.

### 4.2 Admission/provider callers

The exact behavior binding/context caller inventory contains 23 files,
path-list SHA-256
`ec0ff8144080001a3b9ee02a7b9a423dfabe5e1015b509c3cf9d8c3260af0ae4`.
Its production ownership groups are:

- Entity root-owned action/condition admission;
- item child admission in `dnd/blocks/base_item.py`, item runtime
  materialization, and `dnd/items/consumables.py`;
- action and condition child admission in the current core owners;
- explicit barbarian, fighter, dragonborn, extra-attack, origin, and sorcerer
  structural grants;
- origin innate spell grants;
- reaction cloning/handler binding; and
- the existing content runtime/gateway boundary.

No caller requires a new abstraction. Every call can supply the three
primitive IDs at its current binding boundary.

### 4.3 Save and spell execution callers

The narrow runtime save/spell context inventory contains 11 files, path-list
SHA-256
`64d61d776f78743f857f993eb6c5c7a4d4cce524c0827f8bed4722fb85f1e7d1`:

```text
dnd/actions.py
dnd/content_system/origin_character_grant_appliers.py
dnd/core/base_conditions.py
dnd/core/events.py
dnd/core/saving_throw_types.py
dnd/core/spell_execution.py
dnd/entity.py
dnd/spells/infernal.py
tests/progression/test_origin_structural_feature_applier.py
tests/progression/test_saving_throw_context.py
tests/progression/test_spell_damage_affinity_contributions.py
```

Configured spell/catalog declarations and character spell holders stay cold
construction data. Only runtime provenance changes from refs to IDs.

### 4.4 `semantic_key`

The lexical repository inventory is 44 files / 270 matches. It includes item,
AI, and other policy keys outside BF. In behavior owners it remains an optional
policy/grouping key. It may equal or fall back to an admitted `behavior_id`,
but it cannot create, override, or authenticate provenance.

## 5. Handler ownership freeze

The direct `EventHandler(...)` / `SpatialHandler(...)` construction inventory
is 118 sites, normalized SHA-256
`fdc036d8a0c40c7cc90d90a050e611d78aed77cc45dcab8b80eea19d55b621f1`.

| Partition | Sites | SHA-256 / exact members |
|---|---:|---|
| Ordinary provider-scoped or explicit-grant implementation arms | 112 | `5ee66b844f63fd2296c996e26dbaaf88f48c50962021d06f5b4b1c6ece8a1a2b` |
| System lifecycle helpers with no behavior attribution | 5 | `6b72332bec90ef3920f7da6c18d72afd07463f1f198bd692c7a4630fc6aa5a72` |
| Item-owned provider-scoped implementation arm | 1 | `c0d4fd400d766f06888eb3be91eb8723da04296567daefd794c4697e478e7ce0` |

The five system lifecycle helpers are exactly:

```text
dnd/actions_functional.py::_create_prone_auto_stand_handler
dnd/actions_functional.py::_setup_weapon_event_handlers (two sites)
dnd/conditions.py::create_has_attacked_handler
dnd/conditions.py::create_has_taken_damage_handler
```

BF does not invent identities for these unattributed system helpers. The one
item-owned site is `_UnseenStrikeDagger._on_equip` in `dnd/items/weapons.py`.
It is an active private implementation arm and is included in BF-1: its handler
inherits the dagger provider's primitive identity through the existing equip
binding boundary. Before the direct-item cut that primitive is derived once
from the existing item `content_ref.content_id`; the later item cut changes
only that cold source to the required `item_id`. No item-specific adapter or
second handler path is permitted.

The eight named handler subclasses are independently declared public
reactions and all occur in the 73-row missing-view inventory. All other
provider-scoped private handlers inherit their provider behavior ID.

## 6. Test lane and current dispositions

### 6.1 Frozen lanes

| Lane | Nodes | Normalized SHA-256 |
|---|---:|---|
| Existing direct-item affected union | 409 | `c4253a3f09c295f1f33e087ac3f36aecd4d455053ba70c7b1adbb6d8c525680a` |
| BF in-process selection before CR-0 union | 460 | `b7c5838ffaf5494896dd9e7ea6453140f7066f2d2ffdd6050b05702ab1e6a504` |
| BF plus maintained CR-0 union | 519 | `04e5a4bf3cd2d3ea84e88a83ae24c886d09e1a8e0a619f9dae2eb40990a0f6bb` |
| BF-specific delta over the 409 lane | 110 | `e44e8dcb7fc00b6bd75584250278c1cdac4c30e2919df1132ea3f70dc736dfea` |

The 43 BF collection arguments have normalized SHA-256
`9ea10dfb66a44b15b230216124797ab5054ef45c9e49e85564144e69db8ad06f`.

The direct-item lane remains `4 failed, 405 passed`; its failures and repairs
remain exactly:

1. WallTorch relighting inside Sleet Storm: preserve light-source truth while
   optical/weather reduction controls resolved perception.
2. Three directional-door assertions: use the human-authorized WEST side for
   the range-only fixture, with no runtime default or inference.

### 6.2 BF delta characterization

The BF-specific delta ran `7 failed, 103 passed in 38.70s`.

- Two failures are deprecated server/transport architecture assertions that
  import the removed `dnd.core.senses`; they are governed exclusions from this
  in-process cut.
- Two failures assert the removed
  `NEURODRAGON_SPELL_ITEM_RECIPES_BY_LEGACY_ID` recipe shape; they are obsolete
  after the accepted direct-item plan and are not runtime behavior proofs.
- Three progression fixtures create positioned entities with `Entity.create`
  but never compose/deploy them. The accepted occupancy contract intentionally
  excludes undeployed entities from `SpatialSensesSystem`, so their empty LOS
  and target sets are correct. Their mechanics assertions remain useful after
  mechanical migration to the existing `create_test_entity` deployment
  boundary.

The three fixture failures are:

```text
tests/progression/test_saving_throw_context.py::test_magical_sleep_immunity_excludes_target_without_charm_proxy
tests/progression/test_spell_damage_affinity_contributions.py::test_affinity_does_not_apply_to_a_different_spell_damage_type
tests/progression/test_spell_damage_affinity_contributions.py::test_matching_affinity_adds_charisma_once_per_cast_without_persisting
```

Six additional consumer tests import deprecated server modules and therefore
remain inventory-only governed exclusions until that separate recovery:

```text
tests/manual/test_121_canonical_presentation_mapper.py
tests/manual/test_139_condition_presentation_contract.py
tests/manual/test_178_spell_catalog_content_identity.py
tests/manual/test_181_action_content_identity.py
tests/manual/test_181_affordance_content_identity.py
tests/progression/test_dragonborn_origin_runtime.py
```

`server/player_replication/mapper.py` is likewise excluded from BF execution
and architecture proof lanes. Its stale field reads are recorded in section
4.1 and are not evidence of a second supported runtime contract.

## 7. BF-1 authorized edit envelope after review

After correctness, anti-slop, and anti-OOP/ECS/import-DAG approval, BF-1 may:

1. add the missing domain-local immutable by-class views and merge the exact
   393 class rows once at cold bootstrap;
2. change the existing binding/context/discovery/Event/save/spell fact fields
   to the three primitive IDs;
3. keep `runtime_owner_uuid` only as non-serialized rebinding correlation;
4. pass the two provider-only IDs only through explicit structural grant;
5. migrate the Unseen Strike equip handler through the existing item-provider
   boundary with the same primitive fact shape;
6. mechanically migrate the three undeployed test fixtures; and
7. update public behavior proofs without changing event chronology, mechanics,
   causal ownership, or the direct-item failure dispositions.

BF-1 must not edit the deprecated server mapper or add engine compatibility
fields for it.

Stop only for a conflicting semantic ID, a private handler proven to be a
public independent rule, or a consumer that genuinely cannot accept the three
primitive values through its existing boundary.

## 8. BF-0 conclusion

The preflight found no semantic collision, public/private reaction conflict,
runtime abstraction gap, or import-DAG reason to stop. The shared cut is a
value-shape replacement across existing ECS owners. The three required
reviewers approved substantive candidate SHA-256
`b9c02374cfea101918c06be1116bdf6780751ff7dfa6c86cc3ae374ec6d91a8d`;
BF-1 is authorized.

## 9. Independent review record

| Review | Result |
|---|---|
| Correctness / inventory / failure disposition | `APPROVE` — independently reproduced the 395/393/2 partitions, 320/73 map split, 17 consumers, handler partition, and fixture dispositions |
| Anti-slop | `APPROVE` — no compatibility membrane, second fact path, item adapter, synthetic ref, or unnecessary abstraction remains |
| Anti-OOP / ECS / import DAG | `APPROVE` — cold maps are constructor data for the existing binder; no provider object, reflection, late import, cycle, service, manager, or new ownership layer is authorized |

The only substantive corrections before acceptance were:

1. include Unseen Strike's equip handler in BF-1 through the existing item
   provider boundary;
2. correct the current by-class inventory from a presumed four maps/325 rows
   to the actual three maps/320 rows plus 73 missing rows; and
3. inventory the deprecated server mapper as the 17th stale reader while
   preserving the accepted no-server/no-compatibility boundary.

## 10. BF-1 implementation result

BF-1 replaced the shared live behavior-attribution value shape without adding
a second runtime path.

- `BehaviorBinding` now owns exactly `behavior_id`, `provided_by_id`,
  `origin_root_id`, and the internal encounter-local `runtime_owner_uuid`.
- action and handler discovery copy the same three primitive semantic fields;
  `AuthoredBehaviorAttribution` is deleted;
- `ActionEvent`, condition lifecycle events, handler dispatch evidence,
  saving-throw context, and spell-execution context carry primitive IDs;
- the active causal scope carries an immutable `BehaviorBinding`, never a live
  provider object;
- the authoritative runtime reset advances one internal scope generation, so
  exiting a pre-reset nested provider or cold-admission scope cannot restore
  stale encounter provenance;
- the existing binder admits exact runtime classes from one immutable cold
  393-row constructor input, while the two provider-only IDs enter only the
  explicit structural-grant path;
- private handlers inherit their provider behavior ID, while declared public
  reactions retain their own admitted behavior ID;
- item-owned use actions and Unseen Strike use the existing direct child
  boundary with the materialized item's primitive semantic ID; and
- `semantic_key` remains policy/grouping data and never supplies provenance.

No Event phase, queue chronology, completion boundary, reducer path,
condition ownership rule, or mechanics calculation changed in this cut.

## 11. BF-2 hard-cut proof

The active `dnd` runtime contains no `AuthoredBehaviorAttribution`, ref-shaped
`BehaviorBinding` field, live-provider-object binding API, decorator/class
reflection in live admission, or frozen-registry query from the binder.
Configured-action refs, authored condition-effect refs, item declarations, and
other cold catalog facts remain under their separate owning cuts.

The cold built-in bootstrap proves:

| Partition | Rows |
|---|---:|
| Exact admitted mechanics classes | 393 |
| Explicit provider-only behavior IDs | 2 |
| Complete disjoint behavior union | 395 |

The live binder receives the first partition as a `MappingProxyType`; the two
provider-only IDs are disjoint. Fresh bootstrap independently reproduced those
counts and invariants.

The CR-0 evidence manifest was reconciled mechanically after this source cut:
122 definition-owner line coordinates moved, the matching 122 presentation
coordinates moved, and six now-retired runtime `ContentRef` importer rows were
removed. The final reset/cause-validation repair added the two honest direct
imports now present in `dnd/core/spell_execution.py` and
`dnd/runtime_reset.py`; neither is hidden behind a re-export or duplicate
validator. No accepted semantic owner or maintained proof disposition changed.
The current CR-0 evidence manifest SHA-256 is
`8693fbbeb949cf18bc9f4b7a1ba81845fac2db4bc5adc131729c5dc0d70bf5c7`;
its architecture proof is
`8360061dee7a8211aa944f81fba618fe40ed8c205d031e88ba86fbf4d007f5ff`.

## 12. Frozen candidate and validation

The implementation candidate contains 69 active source/evidence paths:
37 production paths, 31 test paths, and the CR-0 evidence manifest. Their
sorted path-list SHA-256 is
`2004d59fa8df5827fe387e0f6886ad91562bae54c148855b903f544f68b8b8b7`.
The normalized `path<TAB>raw-file-sha256` row set has SHA-256
`0811086fdd3e49de95b50b4a6d17e3b9a0cd7e2c1aeaf693cb530f86d83f8ecd`.

Validation results:

| Gate | Result |
|---|---|
| Frozen direct-item affected lane | `405 passed, 4 governed pre-existing failures` over exact 409-node SHA `c4253a3f09c295f1f33e087ac3f36aecd4d455053ba70c7b1adbb6d8c525680a` |
| Active changed behavior/dependency superset | `285 passed` over exact node SHA `370e8c8f6a8ab2fec53f0f2fa66bdead92f35b4779ff7e4c66873aea78f90fff` |
| Maintained CR-0 lane | `105 passed` over exact node SHA `f689e92102b7a6e25c832cdc030d88618ab2048cd174e87869d76ed59cdcab33` |
| CR-0 architecture proof | `11 passed` |
| Active dependency/DAG gates | all green; the two deprecated server checks retain their governed missing-`dnd.core.senses` disposition |
| Fresh cold bootstrap | 393 class rows + 2 provider-only IDs; immutable, unique, and disjoint |
| `compileall` | exit `0` for `dnd` and `tests` |
| `git diff --check` | exit `0`; line-ending normalization notices only |
| Scope scan | no server, SDK, renderer, transport, or generated path edited |
| Hard-cut scan | active runtime path contains no retired attribution/ref fields, live registry lookup, reflection admission, late import, or compatibility alias |

The 409-node lane's four failures remain exactly the accepted WallTorch
relight case and three directional-door assertions. The pre-repair broader
unfiltered changed-test characterization reproduced only ten already
governed stale assertions: six native-AI fixtures using the retired
`Entity._entity_by_position` index and four legacy recipe-map assertions in
the item-family modules, less the two server failures already listed above.
The same selection with those twelve governed nodes removed is the green
285-node lane above, including both nested-reset proofs. No new regression was
found.

No production or test edit is authorized after this freeze. Any repair
invalidates these results and all following approvals.

## 13. BF-2 independent reviews

The first frozen candidate was invalidated after reviewers found three bounded
gaps: unvalidated spell `cause_id`, no public runtime-reset provider-context
proof, and one test passing a condition object instead of its binding. The
repairs added namespaced cause validation, cleared the existing behavior
contexts from the authoritative reset, added the public reset proof, and
corrected the test caller. No new runtime layer or compatibility path was
introduced.

The second frozen candidate was invalidated when correctness review reproduced
an older `ContextVar` token restoring outer provider facts after reset inside
nested scopes. The bounded repair stamps the two existing context values with
one internal reset generation. Reads reject stale generations, and stale scope
exits clear rather than restore their saved token. Public proofs cover both
nested provider facts and nested scoped cold-admission gateways. No callback,
manager, service, registry, or parallel provenance path was added. All
validation above was rerun after this repair.

The third exact candidate was independently accepted without edits:

| Review | Result | Independent evidence |
|---|---|---|
| Correctness / causal identity / failure disposition | `APPROVE` | Reproduced normal nesting, reset-crossing nesting, post-reset scopes, copied contexts, async inherited contexts, primitive propagation, malformed cause rejection, 393+2 cold admission, and CR-0 reconciliation; 76 selected tests passed |
| Anti-slop / single path | `APPROVE` | Confirmed the one generation stamp is the smallest lifecycle repair and found no manager, registry, wrapper, callback, parallel provenance path, ref compatibility, live provider, reflection admission, or synthetic identity; 5 focused proofs passed |
| Anti-OOP / ECS ownership / import DAG | `APPROVE` | Confirmed data-oriented leaf plumbing, immutable binding callers, no live component crossing, no ownership inversion, and zero cycles across 255 modules / 1,858 internal edges; 36 focused tests passed |

All reviewers verified the exact pre-approval ledger SHA
`51b33a94e0da8ad93f8c64163115bd72fde787af1c027800323f9b85df3b26ad`,
the 69-path SHA
`2004d59fa8df5827fe387e0f6886ad91562bae54c148855b903f544f68b8b8b7`,
and the path/file row SHA
`0811086fdd3e49de95b50b4a6d17e3b9a0cd7e2c1aeaf693cb530f86d83f8ecd`.
Only this approval metadata and status changed afterward; production, tests,
the CR-0 manifest, and the frozen candidate path/file rows remain unchanged.
