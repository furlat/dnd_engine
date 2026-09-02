# CR-4/CR-5 direct character recovery implementation ledger

Date: 2026-09-01 through 2026-09-02  
Status: `CR4_CR5_COMPLETE — ACCEPTED`  
Scope: Complete CR-4/CR-5 direct character recovery candidate.

## 1. Governing boundary

| Authority | Frozen identity |
|---|---|
| Branch | `codex/july-reconstruction` |
| Checkout HEAD | `ab56a24bf77fc79251e6505718119c38c4f32c8f` |
| CR-4/CR-5 implementation plan | `DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_PLAN_2026-09-01.md`, SHA-256 `b6447bf45d4bc49b5cae26de31463d538dc91d2727731f5338c03380dc58f09a` |
| Master recovery plan | `DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md`, SHA-256 `3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b` |
| CR-0 completion ledger | `DND_CONTENT_RECOVERY_CR0_COMPLETION_LEDGER_2026-08-30.md`, SHA-256 `b04eb0ed05d8e8d17a3c2136f9454aa9d08c22712c0ed63da551832eec1f09ef` |
| CR-0 current evidence | `content_data/ledgers/content_recovery_cr0_evidence.json`, SHA-256 `8693fbbeb949cf18bc9f4b7a1ba81845fac2db4bc5adc131729c5dc0d70bf5c7` |
| CR-0 historical frozen evidence | same path at CR-0 acceptance, SHA-256 `fdcd5c32e9a3771cf6f015e88fe1185f7420fb80b677af26e2db3af715350bed` |
| Primitive behavior amendment | `DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_SEQUENCE_AMENDMENT_2026-08-31.md`, SHA-256 `8300f661bfc629de52f4aa3316ab935d9129d20dae549510277c0c1a9bd5d0de` |
| Primitive behavior ledger | `DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_IMPLEMENTATION_LEDGER_2026-08-31.md`, SHA-256 `0f7e3a6271f8b7a5fe7528b48a8a85ad8af6d28fd3e9630e9d6c28c60c6b2817` |
| Direct-item ledger | `DND_CONTENT_RECOVERY_DIRECT_ITEM_CR1_CR3_IMPLEMENTATION_LEDGER_2026-08-31.md`, SHA-256 `45b2f4e1ed14cecfdbc3a1ef22994df0ed55931888e22697fdfc99783d91a2f2` |
| Direct-item manifest | `DND_CONTENT_RECOVERY_DIRECT_ITEM_CR1_CR3_IMPLEMENTATION_MANIFEST_2026-08-31.json`, SHA-256 `f54e15aaa359d33a632027c2bf3d8e1b99c6212530bba3d8a0364f213da9328a` |
| Behavioral/value evidence only | accepted checkpoint `513dd97` |
| `AGENTS.md` | SHA-256 `296ce0a99c52fab93261a15e193258b928c0b56c161b91ef8e412f5d27897668` |
| `HOW_TO_TEST.MD` | SHA-256 `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |

The worktree at preflight entry contained only the untracked accepted plan.
No production or test file was edited during Slice 0. Commit `513dd97` is used
only for authored values and externally observable cases. Its transform/Undo,
generic materialization, reflective access, and later entity split remain
rejected.

## 2. Inherited maintained proof union

The direct-item helper was executed, not trusted from prose:

| Set | Nodes | Normalized SHA-256 |
|---|---:|---|
| collected affected modules | 887 | mechanically collected by `tests/architecture/test_content_recovery_cri_direct_items.py` |
| retained predecessor union | 908 | `e05020c0f1222c7f2aad71895debe09dbf3326539d4493b82c7c488495418a44` |
| admitted direct-item successors | 25 | `f5ea8b49e99135bd432bf3bb586324c444637afdc05ae99244f18c6d996993cd` |
| inherited CR-4/CR-5 starting union | **933** | **`969416b9c090911d88eba558d532c92c6eae9614992ba758ea64aac27cbac5d8`** |

Normalization is sorted unique node IDs joined by `\n` with one terminal
newline. Exact re-collection returned the same 933 nodes.

The direct-item candidate included `dnd/core/content/durable_characters.py`
because the accepted `CharacterItemV2` value currently lives there. Exact
preflight inspection also found that the explicitly deferred
`dnd/core/content/character_deployment.py` imports three revision DTOs from the
same file. CR-4/CR-5 therefore retains both files as one quarantined deferred
persistence DTO island until CR-7. It does not move or duplicate
`CharacterItemV2`, recreate persistence, or let new direct-character gameplay
import either module. This preserves the accepted item bytes and the deferred
import DAG without an adapter, alias module, or second DTO authority.

## 3. Exact CR-0 rows and dispositions

### 3.1 Current reconciled rows

CR-0 has 70 CR-4/CR-5 implemented-content rows. Their canonical JSON-lines
SHA-256 is `33469b5ba5722e38bdd93c39466667baa34807a9e13f756e4279ac24564cd475`.

| Cut / kind | Count | Sorted semantic-ID SHA-256 | Exact IDs |
|---|---:|---|---|
| CR-4 background | 2 | `d6fd57c49fc1d766890f77785a7b228d9a3caad2e395da753b9a9c3907505904` | `background.acolyte`, `background.adventurer` |
| CR-4 class | 3 | `580b4fcd53a2e64befc2b2fa8cd148276ef3e96adfd007ff70e9f7f47ae618ef` | `class.barbarian`, `class.fighter`, `class.sorcerer` |
| CR-4 subclass | 3 | `0b09f8cc55feeec9df7831364e2855c68d57e96736c7a0431c797dcf362910de` | `subclass.barbarian.berserker`, `subclass.fighter.champion`, `subclass.sorcerer.draconic_bloodline` |
| CR-4 species | 9 | `1ed338c605e4b3e304fef7209037f2a747238f9e43fc4f24daf2df97a0cb55cf` | `species.dragonborn`, `species.dwarf`, `species.elf`, `species.gnome`, `species.half_elf`, `species.half_orc`, `species.halfling`, `species.human`, `species.tiefling` |
| CR-4 variant | 4 | `e245a4bc2565c89e5f459f9430aca8ef545a693f4e151b9b3c3a190166bf5cd4` | `species_variant.dwarf.hill`, `species_variant.elf.high`, `species_variant.gnome.rock`, `species_variant.halfling.lightfoot` |
| CR-4 trait | 42 | `a6dab4a5c98df2ba1f3270fb9e17f218c6ceed0300171efa32e0660ca5bd794a` | frozen below |
| CR-5 creature roots | 7 | `ec7d3c177ad9f0eb829d69193d635514350c1b82291d96b1522075de80e46dde` | `creature.player.barbarian`, `creature.player.fighter`, `creature.player.humanoid_body`, `creature.player.sorcerer`, and the three current `creature.premade.*` roots |

The 42 current trait IDs are:

```text
trait.origin.background.acolyte.proficiencies
trait.origin.background.acolyte.shelter_of_the_faithful
trait.origin.dragonborn.ancestry.{black,blue,brass,bronze,copper,gold,green,red,silver,white}
trait.origin.dwarf.{combat_training,dwarven_resilience,physical.medium_25,stonecunning}
trait.origin.elf.{fey_ancestry,keen_senses,trance}
trait.origin.gnome.cunning
trait.origin.half_orc.{menacing,savage_attacks}
trait.origin.halfling.{brave,nimbleness}
trait.origin.high_elf.weapon_training
trait.origin.hill_dwarf.dwarven_toughness
trait.origin.lightfoot.naturally_stealthy
trait.origin.rock_gnome.{artificers_lore,tinker}
trait.origin.shared.{darkvision_60,physical.medium_30,physical.small_25}
trait.origin.species.{dragonborn,dwarf,elf,gnome,half_elf,half_orc,halfling,human,tiefling}.languages
trait.origin.tiefling.fire_resistance
```

There are 140 legacy-authority rows: 63 CR-4 declarations, the same 63
structural definitions, 7 CR-5 declarations, and 7 CR-5 materializable roots.
Their canonical hash is
`54cd63165065168e15f1972c6df152643ca4fe95331b1c7fb5fa9c297df141d0`.
All 140 are replacement evidence, not retained runtime authority.

The 68 CR-4/CR-5 CR-0 importer rows have canonical SHA-256
`d474719789b037d287fdfdf4861594fc054df317c1c0f8cb2f0d284e4ed88e9f`.
Their 31 unique paths have sorted-path SHA-256
`30109442e48d1bd5b36b23ee2a9fae2c87a7e1f59fdb354152fe3b7b164b1767`.
The three frozen excluded modules (`manual 174`, `manual 175`, editable
character plans) have canonical SHA-256
`394167309a7be0858136f7349f161f066f76b32fea54b7fff5fbb1e6698bb281`;
their genuine cases receive direct-build successors and their old shapes do
not survive.

### 3.2 Accepted value rows

Accepted values were imported from a clean `git archive 513dd97` under an
isolated `PYTHONPATH`. Canonical rows recursively convert dataclasses, enums,
mappings, and tuples to JSON primitives, sort keys, encode one compact JSON
object per row, join with `\n`, and append one terminal newline.

| Accepted value set | Rows | Canonical SHA-256 |
|---|---:|---|
| species definitions | 9 | `1d74c320e0aebb6955f0cc07d516ac0588555faeee9eff281883a7bf56b41d65` |
| variant definitions | 4 | `75ef31db703bbb5792894cef6a08fdbb8430d914f30136908cbb730eaf1855df` |
| background definitions | 2 | `856dd25a8fd6cb4349d66ee68074dc7e507fdd81e2a3a8697b2e02e89d323cbe` |
| six 1-20 level tables | 120 | `f0891d25627ae84b39f2cf7b66766007520e5291ad9669d314e05d6124aa2b13` |
| first-class and level choice rows | 67 | `bddfedfd65c7d5d5db4cb2cf270b2ca611e72775dcd86b6c1de8831126df147c` |
| automatic grant occurrences | 62 | `b7709779adab85455cc52a0cecf566757e031b919a649b2868601cf0e9145339` |
| Sorcerer spell entitlements | 70 | `0b3c8cce54958c04c2a8023604882fa879d37189be74affc1ae5c370a3228829` |
| premade authored builds | 4 | `892c94029d8b40a881ef901f69134bd1a26ba0d2053de64599619fa578c1dba7` |

Current CR-0 rows establish provenance and complete row identity. Accepted
checkpoint rows supply the missing direct values and cases. No accepted
runtime architecture is copied.

## 4. Origins: exact definitions, choices, and mechanic mapping

### 4.1 Definition rows

| Definition | Structural values and authored choices |
|---|---|
| Dragonborn | Medium/30; Common, Draconic; ancestry 1-of-10 `{black,blue,brass,bronze,copper,gold,green,red,silver,white}` |
| Dwarf | Medium/25; Common, Dwarvish; darkvision; Stonecunning; artisan tool 1-of-3 |
| Elf | Medium/30; Common, Elvish; Perception; darkvision; Fey Ancestry; magical-sleep immunity; Trance |
| Gnome | Small/25; Common, Gnomish; darkvision; Gnome Cunning |
| Half-Elf | Medium/30; Common, Elvish; darkvision; Fey Ancestry; sleep immunity; one non-Common/non-Elvish language; two skills from all 18 |
| Half-Orc | Medium/30; Common, Orc; Intimidation; darkvision; Relentless Endurance; Savage Attacks |
| Halfling | Small/25; Common, Halfling; Brave; Lucky; Halfling Nimbleness |
| Human | Medium/30; Common; one additional non-Common language |
| Tiefling | Medium/30; Common, Infernal; darkvision; fire resistance; Infernal Legacy |
| Hill Dwarf | parent Dwarf; Dwarven Toughness |
| High Elf | parent Elf; weapon training; one additional language; exactly `spell.fire_bolt` wizard cantrip |
| Rock Gnome | parent Gnome; Artificer's Lore, Tinker, Tinker's Tools |
| Lightfoot | parent Halfling; Naturally Stealthy |
| Acolyte | Insight, Religion; two languages; Shelter of the Faithful; starting holdings |
| Adventurer | neutral background with no fixed grant |

The language vocabulary is the accepted 16 SRD language IDs. Skills are the
accepted 18 `SkillName` values. All choices preserve their accepted cardinality
and ordering; no `ContentRef` or generic choice object survives.

### 4.2 Eighteen mechanical feature families

| # | Direct family | Current row evidence / disposition |
|---:|---|---|
| 1 | `background.acolyte.starting_holdings` | accepted-only direct holdings; current acolyte proficiency/shelter rows remain separate structural facts |
| 2 | `sense.darkvision.60` | `trait.origin.shared.darkvision_60` |
| 3 | `species.dragonborn.ancestry_resistance` | selected from the ten ancestry rows |
| 4 | `species.dragonborn.breath_weapon` | same selected ancestry drives one direct action |
| 5 | `species.dwarf.combat_training` | `trait.origin.dwarf.combat_training` |
| 6 | `species.dwarf.poison_resilience` | `trait.origin.dwarf.dwarven_resilience` |
| 7 | `species.elf.fey_ancestry` | `trait.origin.elf.fey_ancestry` |
| 8 | `species.gnome.cunning` | `trait.origin.gnome.cunning` |
| 9 | `species.half_orc.relentless_endurance` | accepted-only direct handler |
| 10 | `species.half_orc.savage_attacks` | `trait.origin.half_orc.savage_attacks` |
| 11 | `species.halfling.brave` | `trait.origin.halfling.brave` |
| 12 | `species.halfling.lucky` | accepted-only direct handler |
| 13 | `species.tiefling.fire_resistance` | `trait.origin.tiefling.fire_resistance` |
| 14 | `species.tiefling.infernal_legacy` | accepted-only direct innate spells |
| 15 | `species_variant.high_elf.weapon_training` | `trait.origin.high_elf.weapon_training` |
| 16 | `species_variant.high_elf.wizard_cantrip` | accepted-only exact `spell.fire_bolt` grant |
| 17 | `species_variant.hill_dwarf.dwarven_toughness` | `trait.origin.hill_dwarf.dwarven_toughness` |
| 18 | `species_variant.rock_gnome.tinkers_tools` | `trait.origin.rock_gnome.tinker` plus structural Artificer's Lore/Tinker capability rows |

The other 21 current trait rows are not silently discarded or mislabeled as
new mechanics: two acolyte structure rows, Dwarf physical/Stonecunning, Elf
Keen Senses/Trance, Half-Orc Menacing, Halfling Nimbleness, Lightfoot Naturally
Stealthy, Rock Gnome Artificer's Lore, the two shared physical rows, and nine
species-language rows become direct cold structural values/proficiencies/
capabilities.

## 5. Class tables and choice vocabulary

### 5.1 Class headers

| Class | Hit die / casting | Multiclass prerequisite | First-class versus multiclass proficiency | Saves | Subclass |
|---|---|---|---|---|---|
| Barbarian | d12 / non-caster | Strength 13 | first: light/medium armor, shield, martial/simple weapons; multiclass omits armor | Strength, Constitution | Berserker |
| Fighter | d10 / non-caster | Strength 13 **or** Dexterity 13 | first adds heavy armor; multiclass light/medium, shield, martial/simple | Strength, Constitution | Champion |
| Sorcerer | d6 / full caster, Charisma, source `class.sorcerer.spellcasting`, no ritual preparation | Charisma 13 | first: dagger, dart, light crossbow, quarterstaff, sling; multiclass empty | Constitution, Charisma | Draconic Bloodline |

First-class choices are exact starting-equipment preset selection and two
class skills. Fighter has 8 skills and 4 equipment presets; Barbarian has 6
skills and 3 presets; Sorcerer has 6 skills and 2 presets.

### 5.2 Exact level-row skeleton

The 120 accepted rows are frozen by the hash in section 3.2. The complete
nonempty automatic grant skeleton is:

```text
Fighter: 1 second_wind; 2 action_surge; 5/11/20 extra_attack;
         9/13 indomitable; 17 action_surge + indomitable.
Champion: 3 improved_critical; 7 remarkable_athlete;
          15 superior_critical; 18 survivor.

Barbarian: 1 rage + unarmored_defense; 2 reckless_attack + danger_sense;
           3/6/9/12/16/17/20 rage; 5 extra_attack + fast_movement;
           7 feral_instinct; 9/13/17 brutal_critical;
           11 relentless_rage; 15 persistent_rage;
           18 indomitable_might; 20 primal_champion.
Berserker: 3 frenzy; 6 mindless_rage; 10 intimidating_presence;
           14 retaliation.

Sorcerer: sorcery_points at every level 2-20; level 20 also
          sorcerous_restoration.
Draconic: 1 draconic_resilience; 6 elemental_affinity;
          14 dragon_wings; 18 draconic_presence.
```

Choice timing is exact:

- Fighter fighting style at 1, Champion at 3, Champion second style at 10,
  and ASI/feat at Fighter 4/6/8/12/14/16/19.
- Barbarian Berserker at 3 and ASI/feat at 4/8/12/16/19.
- Sorcerer Draconic and initial 4 cantrips/2 spells at 1; one added known spell
  at 2-11, 13, 15, 17; optional replacement at every level 2-20; added
  cantrip at 4 and 10; metamagic 2-of-3 at 3 and one more at 10; ASI/feat at
  4/8/12/16/19; Draconic ancestry 1-of-10 at subclass level 1.
- Every ASI/feat row allows one `+2`, two `+1` selections, or `feat.lucky`,
  exactly as the accepted 13-value vocabulary specifies.
- Supported metamagic is exactly Distant, Quickened, and Twinned. The wider
  legacy structural declarations for Careful, Empowered, Extended, Heightened,
  and Subtle are not silently exposed as selectable content.

### 5.3 Sorcerer spell entitlements

All 70 IDs resolve to concrete existing spell/reaction constructors. They are
semantic entitlements, not a new catalog. `sorcerer_grants.py` may contain one
private domain-local constructor map for these exact IDs; no public
`spell_builders`, registry, service, or fallback is authorized.

```text
0: acid_splash, chill_touch, fire_bolt, light, poison_spray, ray_of_frost,
   shocking_grasp, true_strike
1: burning_hands, charm_person, color_spray, expeditious_retreat, false_life,
   fog_cloud, jump, mage_armor, magic_missile, shield, sleep, thunderwave
2: blindness_deafness, blur, darkness, darkvision, enhance_ability,
   enlarge_reduce, gust_of_wind, hold_person, invisibility, mirror_image,
   misty_step, scorching_ray, see_invisibility, shatter, web
3: counterspell, daylight, fear, fireball, haste, hypnotic_pattern,
   lightning_bolt, protection_from_energy, sleet_storm, slow, stinking_cloud
4: banishment, blight, dimension_door, greater_invisibility, ice_storm,
   stoneskin
5: cloudkill, cone_of_cold, hold_monster, insect_plague, telekinesis
6: chain_lightning, circle_of_death, disintegrate, eyebite,
   globe_of_invulnerability, sunbeam, true_seeing
7: finger_of_death, prismatic_spray
8: incendiary_cloud, power_word_stun, sunburst
9: power_word_kill
```

Disposition: all 70 roots are `EXISTING_CONCRETE_BEHAVIOR_DIRECT_ROOT_BINDING`.
Shield and Counterspell additionally install their existing exact reaction
handler factory. Their spell-domain descendants remain owned by the existing
spell mechanic and are not copied into character content. CR-4/CR-5 installs
the root `BehaviorBinding` directly and never invokes a content registry or
gateway. It does not delete the spell catalog declarations because other
unmigrated spell owners still use them; deleting the whole spell-domain
admission graph is CR-9. This is the plan's explicit semantic-entitlement
boundary, not a second character admission path.

## 6. Direct build and premade rows

The four exact accepted premade IDs are:

```text
hero.barbarian_l5_berserker_torch
hero.fighter_l5_shield_torch
hero.sorcerer_l5_standard_torch
hero.fighter_2_sorcerer_3_spellblade
```

All use Human + Adventurer, one ordered sequence of direct level selections,
the accepted point-buy/base scores and flexible bonuses, one direct item
loadout, and the public custom build path. Exact full values are frozen by the
four-row hash in section 3.2. Compact distinguishing values are:

| Premade | Levels | Body | Supplement rows |
|---|---|---|---:|
| Barbarian | Barbarian 1-5, Berserker at 3, Strength +2 at 4 | broad/tall, hair 17, warm tan, sand hair, no beard | 10 |
| Fighter | Fighter 1-5, Champion at 3, Dueling, Strength +2 at 4 | average/average, hair 10, light tan, auburn hair/beard | 11 |
| Sorcerer | Sorcerer 1-5, Red Draconic, Quickened + Twinned, Charisma +2 at 4 | slender/short, hair 22, light tan, auburn hair, no beard | 9 |
| Spellblade | Fighter 2 then Sorcerer 3, Dueling, Red Draconic, Quickened + Twinned | Fighter body; crown equipped | 11 |

The current three premade creature roots and three class-fixture creature roots
are deleted. `creature.player.humanoid_body` becomes the direct character-body
semantic ID, not a retained creature `ContentRef`. The fourth accepted
spellblade is a plain build value and never acquires a private root.

Required source-keyed prepared/toggle cases are frozen as:

```text
prepared: PreparedSpellSelection(
    source_id="class.sorcerer.spellcasting",
    spell_ids=("spell.magic_missile",),
)
supported enabled: class_feature.fighter.fighting_style.great_weapon_fighting = true
supported disabled: feat.lucky = false
unsupported rejection: class_feature.fighter.second_wind = true
```

The complete supported player-toggle vocabulary is exactly:

```text
class_feature.fighter.fighting_style.great_weapon_fighting
class_feature.fighter.fighting_style.protection
class_feature.fighter.indomitable
class_feature.barbarian.retaliation
feat.lucky
```

Disabled selections are retained as semantic state; unsupported IDs fail
before mutation. No premade is distorted merely to host these proof rows.

## 7. Appearance evidence boundary

Exactly 85 CR-8 overlay rows intersect CR-4/CR-5. Canonical JSON-lines SHA-256
is `3f778b80e2360a24fb66c4077bf284f5f09448d467599403d5165b211c1fb9f2`:

- 70 `definition_presentation` rows corresponding one-for-one to the 70 CR-0
  definition rows; and
- 15 character-specific rows, canonical SHA-256
  `985cc80f2733ca356093005e53e9b113b8446f87f33a3bbb220b7dec5e5bc143`:
  eight appearance-option vocabularies, three built-in class selections, and
  four premade appearances.

CR-5 copies only the resolved mechanical `AppearanceConfig`/body values into
plain build rows. All 85 CR-0 rows remain frozen evidence for CR-8. No asset
path, icon/portrait resolver, renderer catalog, generated binding, or Pygame
code enters this cut.

## 8. Shared owner-schema cut

### 8.1 Exact fields and consumers

| Schema | Atomic direct form | Active/shared consumers to migrate | Legacy character consumers removed |
|---|---|---|---|
| `SpellcastingSource.provider_ref` | `provider_id: str` | `dnd/blocks/spellcasting.py`, `dnd/core/feature_grants.py`, `dnd/entity.py`, world-birth/manual-125/source-propagation proofs | character validators/materializer/appliers/origin innate modules |
| `LearnedReactionSpellOwnership.spell_ref` | `spell_id: str` | `dnd/blocks/spellcasting.py`, `dnd/spells/abjuration.py`, `dnd/spells/infernal.py`, `dnd/spells/reaction_spell_content.py` and their direct reaction/source proofs | character grant schemas/materializer/origin innate modules |
| `AttackMultiplicityGrant.provider_ref` | `provider_id: str` | `dnd/blocks/action_economy.py`, `dnd/core/feature_grants.py`, manual-125 and source-owner proofs | extra-attack/fighter appliers |
| `RitualPreparationPolicy` | dependency-leaf enum | `dnd/blocks/spellcasting.py`, direct class definitions and retained source proofs | durable/validation/progression declarations |
| `OriginCapability` | dependency-leaf enum | `dnd/entity.py`, `dnd/spells/enchantment.py`, direct origin proofs | generic origin definitions/appliers |

Other occurrences of the text `spell_ref` in encounter transport/policy DTOs
are not the `LearnedReactionSpellOwnership` field and are untouched. Creature
`Entity.content_ref` remains CR-6 debt. The character identity is disjoint and
does not dual-write it.

### 8.2 Ability/skill/save names

`AbilityName`, `SkillName`, and `SavingThrowName` move to
`dnd/types/abilities.py`. Active consumers migrate atomically:

- `dnd/actions.py`;
- `dnd/entity.py`;
- `dnd/blocks/abilities.py`;
- `dnd/blocks/equipment.py`;
- `dnd/blocks/skills.py`;
- `dnd/blocks/saving_throws.py`;
- `dnd/blocks/spellcasting.py`;
- `dnd/items/environment_interactables.py`;
- `dnd/monsters/srd_roster.py`;
- `dnd/spells/abjuration.py`;
- `dnd/spells/catalog_content.py`;
- `dnd/spells/content_metadata.py`;
- `dnd/spells/evocation.py`;
- `dnd/spells/necromancy.py`; and
- `dnd/spells/transmutation.py`.

Maintained proof importers are
`tests/engine/test_spell_families.py`,
`tests/engine/test_standard_conditions.py`,
`tests/progression/test_source_owned_engine_primitives.py`, and
`tests/progression/test_spellcasting_source_action_propagation.py`.

The five manual importers
`tests/manual/spell_regression_support.py`,
`tests/manual/test_14_spell_families.py`,
`tests/manual/test_126_action_override_runtime.py`,
`tests/manual/test_131_inventory_use_actions_legacy_contract.py`, and
`tests/manual/test_142_item_equip_hooks_legacy_contract.py` receive bounded
import-only migration. Their behavior and assertions remain unchanged;
`test_131` and `test_142` are also accepted direct-item manifest members.

Legacy character importers disappear with their owning modules. Deferred
server/repository tests are not edited. Events and blocks cease being
accidental type catalogs; no compatibility alias remains.

## 9. Closed receipt families and legitimate owner cleanup

There are exactly four frozen receipt dataclasses: Origin, Fighter/Champion,
Barbarian/Berserker, and Sorcerer/Draconic. They contain only fields actually
used by that family. Shared tiny tuples are allowed only when their element
type names one concrete owner operation; there is no `kind/surface/target`
handle language and no generic receipt interpreter.

| Installed fact | Receipt data | Cleanup owner/API |
|---|---|---|
| numerical/constraint/advantage/critical/auto-hit/resistance modifier | exact semantic surface selector + modifier UUID | the known Entity component's `ModifiableValue.remove_*` method |
| skill/save/ability-check proficiency | exact subject + source UUID | `SkillSet.remove_proficiency_source`, `SavingThrowSet.remove_proficiency_source`, or `AbilityScores.remove_check_proficiency_source` |
| weapon/armor/shield/language/tool proficiency | exact source UUID | `CreatureProficiencies.remove_source` |
| hit die | hit-die UUID | `Health.remove_hit_dice_by_uuid` |
| spell source | source UUID | `SpellcastingBlock.remove_source` |
| learned reaction | spell ID + source UUID + exact handler UUID | `SpellcastingBlock.remove_learned_reaction_spell_source`; remove exact Entity-owned handler only when the last source is gone |
| spell affinity | contribution UUID | `SpellcastingBlock.remove_spell_damage_affinity_contribution` |
| normal spell slots | capacity source UUID | `ActionEconomy.remove_normal_spell_slot_capacity` |
| resource maximum/recovery | resource name + contribution UUID | exact `ActionEconomy.remove_resource_contribution` / `remove_resource_recovery_contribution` |
| attack multiplicity | grant UUID | `ActionEconomy.remove_attack_multiplicity_grant` |
| registered action | action UUID | `Entity.unregister_action_by_uuid` |
| handler | handler UUID and owning Entity block | `BaseBlock.remove_event_handler` on that owner; never queue/global lookup as the primary owner |
| AC formula | formula/source UUID | `Equipment.remove_armor_class_formula_candidate` |
| condition immunity | condition name + source UUID on the known Entity owner | `BaseBlock.remove_condition_immunity_source` |
| sense | source UUID | `Senses.remove_sense_mode_source` |
| size | source UUID | `Entity.remove_structural_size_source` |
| origin capability | capability + source UUID | `Entity.remove_origin_capability_source` |
| feature contribution | feature ID + source UUID | Entity's direct feature-source removal |
| replacement | exact replaced spell/feature semantic row plus its original contribution data | family-specific restoration in the same cleanup function |

Application returns these plain rows after each owner succeeds. Cleanup obtains
the same known owner from the same Entity and executes reverse order. It never
uses `BaseBlock.get` to discover an owned component, scans all entities or
conditions, stores a live component/action/condition, or captures an Undo/
callback/bound method.

## 10. Behavior closure and temporary import allowlist

### 10.1 Exact temporary exception

Only these four new modules may import `BehaviorBinding` from
`dnd.core.content.runtime`:

```text
dnd/content/characters/origin_grants.py
dnd/content/characters/fighter_grants.py
dnd/content/characters/barbarian_grants.py
dnd/content/characters/sorcerer_grants.py
```

They may import only the immutable `BehaviorBinding` class—never
`bind_runtime_behavior*`, a context/gateway/provider, installed runtime, or
declaration lookup. Existing engine behavior primitives remain untouched
until CR-9.

### 10.2 Origin closure

```text
action.origin.dragonborn.breath_weapon
trait.origin.half_orc.relentless_endurance
trait.origin.halfling.lucky
spell.fire_bolt
spell.thaumaturgy
spell.hellish_rebuke
spell.darkness
reaction.spell.hellish_rebuke
```

The first three are character-required CR-2C families and lose their exact
legacy declarations/admission rows in the same origin slice. The four spell
roots plus the reaction are existing spell-domain mechanics installed with
direct root bindings; their unrelated spell-domain catalog ownership remains
CR-9. `spell.darkness` is in this Slice-2 closure because Tiefling Infernal
Legacy grants it, independently of its later Sorcerer entitlement row.

### 10.3 Fighter/Champion closure

```text
action.class.fighter.action_surge
action.class.fighter.second_wind
action.feature.extra_attack
reaction.class_feature.fighter.protection
class_feature.fighter.fighting_style.{archery,defense,dueling,great_weapon_fighting,protection,two_weapon_fighting}
class_feature.fighter.{action_surge,improved_critical,indomitable,second_wind,superior_critical,survivor}
class_feature.extra_attack
```

Remarkable Athlete is direct structural modifier ownership, not a retained
behavior declaration. Every exact character class action/reaction/condition
declaration above is removed when direct construction lands.

### 10.4 Barbarian/Berserker closure

```text
action.class.barbarian.{end_rage,extend_intimidating_presence,
intimidating_presence,reckless_attack,frenzied_strike,frenzy,rage}
reaction.class_feature.barbarian.retaliation
class_feature.barbarian.{brutal_critical,danger_sense,fast_movement,
feral_instinct,frenzied,frenzy,indomitable_might,intimidating_presence,
intimidating_presence_immunity,mindless_rage,persistent_rage,
primal_champion,rage,raging,reckless_attack,reckless_attacking,
relentless_rage,retaliation}
```

### 10.5 Sorcerer/Draconic closure

```text
action.class.sorcerer.{convert_sorcery_points_to_slot,
convert_slot_to_sorcery_points,distant_spell,quickened_spell,twinned_spell,
elemental_affinity.resistance,dragon_wings.fly,dragon_wings.toggle,
draconic_presence}
class_feature.sorcerer.{draconic_resilience,draconic_presence.aura,
draconic_presence.immunity,dragon_wings.active,
elemental_affinity.resistance,metamagic_active,sorcery_points}
```

The ten ancestry choices, Elemental Affinity, Dragon Wings, Draconic Presence,
Sorcerous Restoration, and the three supported metamagic selections remain
cold/direct semantic grant IDs. Unsupported legacy metamagic declarations are
removed from the active character vocabulary; no fake runtime implementation
is invented.

`dnd/content_system/action_definitions.py`, `condition_definitions.py`,
`reaction_definitions.py`, `condition_effect_population.py`, and
`builtin_inventory.py` are mixed files: only the exact closure rows above and
their aggregation imports are removed. Unrelated spell/item/monster behavior
rows remain.

## 11. Runtime children and owner edges

| Structural owner | Runtime root retained by exact owner | Descendants / removal law |
|---|---|---|
| Rage action template | one `Raging` root UUID | `Frenzied` is its subcondition; Frenzied Strike is owned by Frenzied. Remove the root graph, never both names independently. |
| Reckless Attack template | one `RecklessAttacking` root UUID | ordinary one-root removal |
| Elemental Affinity resistance template | one `ElementalAffinityResistance` root UUID | ordinary one-root removal |
| Dragon Wings toggle template | one `DragonWingsActive` root UUID | toggle and feature cleanup share the same exact root owner |
| Draconic Presence mode template | one `Concentrating` root UUID | linked aura, target Charmed/Frightened rows, and immunity rows remain one condition graph and are removed by the existing linked/subcondition traversal |
| Distant/Quickened/Twinned template | one `MetamagicActive` root UUID | mutually exclusive active root; spell execution consumes it through its existing semantic cause |

The current `BaseBlock._remove_condition_tree` already pre-accepts the complete
linked/subcondition graph, cancels without mechanics mutation, commits child
first, and completes each child with direct parent lineage. It is retained
unchanged. No new transaction, callback chain, lifecycle manager, or condition
sweeper is authorized.

The one missing local owner edge is template-to-execution identity. Slice 1
adds one excluded `registered_template_uuid` value to `BaseAction` executable
instances. `instantiate()` and restricted variants set it to the registered
template UUID. The concrete action resolves that exact template through its
source Entity's action owner and records its one active root UUID. This is not
a registry or index: Entity already owns the template list and the lookup is
by exact UUID. Concrete cleanup consumes that root UUID before unregistering
the structural action. The executable instance never becomes durable state.

Intimidating Presence target outcomes are not structural children of the
Barbarian level. Once an action commits, its frightened/immunity outcome keeps
its normal duration even if the source later loses the action. Spell damage
and spell-applied conditions follow the same law. They are gameplay outcomes,
not flattened character receipts.

## 12. Event chronology and lawful failure boundary

Post-birth level changes use the existing Event phases and sub-event parent
field. There is no new event transport or completion callback.

```text
pure resolve + validate all owners
    -> unregistered level DECLARATION preflight (vetoable, no mutation)
    -> unregistered level EXECUTION preflight (final veto, no mutation)
    -> removal with active children only: publish accepted EXECUTION parent
    -> exact active-root condition graph, parented to that EXECUTION
       - graph veto: cancel level lineage; no mechanics changed
       - graph commit: child removal facts are committed; rollback is now unlawful
    -> apply/remove already-prevalidated concrete owner state
    -> reconcile total-level origin state
    -> store semantic row + typed receipt
    -> one unregistered terminal level COMPLETION value
    -> existing publish_completed_fact pre-completion work
    -> atomically store the terminal level fact
```

Addition uses the same declaration/execution boundary but has no child-removal
step and does not publish the preflight proposals. A natural owner failure
before committed child facts uses the same direct family cleanup; no level fact
or compensating event is published. `publish_completed_fact` runs existing
pre-completion systems before storing the terminal value, so addition or a
child-free removal can restore exact prior state if that work raises, with no
published terminal or `EFFECT` version to rewind. After an active child graph
commits, remaining owner operations are prevalidated and no-fail. A later
observation-system exception is an engine failure over already-committed child
facts, not permission to manufacture old runtime UUIDs or rewind history.

This uses the existing completed-fact seam already used for entity/world
birth. It adds no Event API, callback chain, transaction object, or special
queue storage path. The implementation proof must show no `EFFECT` version for
either level event and must exercise public pre-completion failure on addition
and on a child-free removal.

The two concrete events are `EntityLevelAddedEvent` and
`EntityLevelRemovedEvent`, with two exact `EventType` members. Their narrow
shared facts are: entity identity, previous/new total, applied/removed semantic
step, resulting per-class totals, origin/level selections, source-keyed
prepared rows, enabled/disabled toggles, and only progression-derived terminal
mechanics that changed. No full birth snapshot, operation envelope, event view,
reducer switch, clone, or callback chain is introduced.

Initial construction and hydration use the same pure resolution and owner
functions while the Entity is unpublished. They publish no level events.
Successful character construction calls `Entity.compose_entity` once and
publishes exactly one terminal birth fact.

## 13. Production caller and import disposition

### 13.1 Full-delete legacy production files

```text
dnd/classes/barbarian_progression_definitions.py
dnd/classes/content_factories.py
dnd/classes/progression_definitions.py
dnd/classes/sorcerer_progression_definitions.py
dnd/classes/sorcerer_structural_feature_definitions.py
dnd/classes/starting_equipment_refs.py
dnd/classes/structural_feature_definitions.py
dnd/content_system/acolyte_starting_holdings.py
dnd/content_system/background_starting_holdings.py
dnd/content_system/barbarian_character_grant_appliers.py
dnd/content_system/builtin_character_builds.py
dnd/content_system/builtin_character_grant_appliers.py
dnd/content_system/character_appearance.py
dnd/content_system/character_build_validation.py
dnd/content_system/character_content_migrations.py
dnd/content_system/character_grant_applier_runtime.py
dnd/content_system/character_grant_context.py
dnd/content_system/character_grant_types.py
dnd/content_system/character_materialization.py
dnd/content_system/character_origin_definitions.py
dnd/content_system/dragonborn_character_grant_appliers.py
dnd/content_system/dragonborn_origin_definitions.py
dnd/content_system/extra_attack_character_grant_appliers.py
dnd/content_system/fighter_character_grant_appliers.py
dnd/content_system/origin_character_grant_appliers.py
dnd/content_system/origin_feature_definitions.py
dnd/content_system/origin_innate_spellcasting.py
dnd/content_system/origin_runtime_character_grant_appliers.py
dnd/content_system/sorcerer_character_grant_appliers.py
dnd/content_system/starting_apparel_definitions.py
dnd/content_system/starting_equipment_definitions.py
dnd/core/content/origin_features.py
dnd/core/content/premade_characters.py
dnd/core/content/starting_equipment.py
dnd/player_character_body.py
dnd/premade_characters.py
```

The following two production files remain unchanged as the exact CR-7
deferred persistence DTO island:

```text
dnd/core/content/durable_characters.py
dnd/core/content/character_deployment.py
```

No new direct-character module or maintained gameplay caller may import them.
`CharacterItemV2` remains in its accepted direct-item location; this cut adds
no duplicate item value or compatibility re-export.

### 13.2 Mixed bounded production edits

```text
dnd/actions.py
dnd/actions_functional.py
dnd/blocks/abilities.py
dnd/blocks/action_economy.py
dnd/blocks/equipment.py
dnd/blocks/saving_throws.py
dnd/blocks/skills.py
dnd/blocks/spellcasting.py
dnd/classes/fighter.py
dnd/classes/barbarian.py
dnd/classes/feats.py
dnd/classes/fighter.py
dnd/classes/rage.py
dnd/classes/sorcerer.py
dnd/content_system/action_definitions.py
dnd/content_system/builtin_inventory.py
dnd/content_system/condition_definitions.py
dnd/content_system/condition_effect_population.py
dnd/content_system/reaction_definitions.py
dnd/core/base_actions.py
dnd/core/events.py
dnd/core/feature_grants.py
dnd/core/progression.py
dnd/entity.py
dnd/items/environment_interactables.py
dnd/monsters/srd_roster.py
dnd/origins/dragonborn.py
dnd/origins/half_orc.py
dnd/origins/halfling.py
dnd/scenarios/encounter_assembler.py
dnd/spells/abjuration.py
dnd/spells/catalog_content.py
dnd/spells/content_metadata.py
dnd/spells/enchantment.py
dnd/spells/evocation.py
dnd/spells/infernal.py
dnd/spells/necromancy.py
dnd/spells/reaction_spell_content.py
dnd/spells/transmutation.py
```

`encounter_assembler.py` receives only deletion of the obsolete
persistence-snapshot owned-character branch, its `character_deployments`
argument, and its imports of `CharacterDeploymentSnapshot` and the old
character materializer. It does not convert legacy revisions or call the new
direct build boundary. Authored-creature scenario behavior remains unchanged;
direct character deployment is restored in CR-7 through direct scenario data.

### 13.3 New production files

```text
dnd/types/abilities.py
dnd/types/character_progression.py
dnd/types/character_receipts.py
dnd/content/characters/__init__.py
dnd/content/characters/origin_definitions.py
dnd/content/characters/class_definitions.py
dnd/content/characters/origin_grants.py
dnd/content/characters/fighter_grants.py
dnd/content/characters/barbarian_grants.py
dnd/content/characters/sorcerer_grants.py
dnd/content/characters/progression.py
dnd/content/characters/builds.py
dnd/content/characters/premades.py
```

No other production path is authorized without a narrow ledger amendment.
In particular: no server, SDK, transport, generated binding, renderer, asset,
Pygame, CR-6 monster, or CR-7 scenario-definition file.

## 14. Test succession and authorized test envelope

### 14.1 Successor modules

```text
tests/architecture/test_content_recovery_cr45_direct_characters.py
tests/progression/direct_character_support.py
tests/progression/test_direct_character_origins.py
tests/progression/test_direct_fighter_progression.py
tests/progression/test_direct_barbarian_progression.py
tests/progression/test_direct_sorcerer_progression.py
tests/progression/test_direct_character_progression.py
tests/progression/test_direct_character_builds.py
```

The support file owns setup/check helpers only. Cases remain readable data and
exercise public character/progression boundaries. It is not a fixture
framework, fake materializer, or private-operation harness.

### 14.2 Obsolete maintained modules and exact successor groups

| Obsolete predecessor group | Maintained nodes | Successor proof |
|---|---:|---|
| old no-legacy-character-factory architecture | 1 | CR45 architecture gate |
| current premade character content | 8 | direct build/premade equality and one-path proofs |
| Barbarian materialization/appliers/definition | 16 | direct Barbarian 1-20/20-1, active Rage/Frenzy, feature outcomes |
| Fighter materialization/appliers/definition | 14 | direct Fighter 1-20/20-1, styles/resources/formulas/attacks |
| Sorcerer materialization/appliers/definitions/source | 34 | direct Sorcerer 1-20/20-1, sources/spells/metamagic/Draconic outcomes |
| origin definition/runtime/integration/structural modules | 46 | exact 9/4/2 rows, 42 trait dispositions, 18 mechanics, apply/remove/reconcile |
| schema-2 materialization | 8 | direct custom build and four ordinary premades |
| generic multiclass composition | 2 | direct Fighter/Sorcerer aggregate progression |
| generic character-recovery semantics | 3 | CR45 exact authority/hard-cut gate |
| manual Barbarian unarmored defense | 7 | retained module rewritten through the direct public build |

The 17 saving-throw-context nodes, 3 direct-item durable/proficiency nodes, 3
spell-affinity nodes, source propagation, normal spell-slot owner proofs, and
the general haste/action-economy cases remain behavior proofs. Only imports or
direct-ID field names change where required; they are not replaced by static
shape assertions.

### 14.3 Full-delete obsolete test/support files

```text
tests/architecture/test_no_legacy_character_factory_dependencies.py
tests/manual/test_174_premade_character_composition.py
tests/manual/test_175_character_runtime_materialization.py
tests/manual/test_premade_character_content.py
tests/progression/materialization_support.py
tests/progression/test_barbarian_berserker_materialization.py
tests/progression/test_barbarian_character_grant_appliers.py
tests/progression/test_barbarian_progression_definitions.py
tests/progression/test_builtin_character_origins.py
tests/progression/test_character_appearance.py
tests/progression/test_character_build_validation.py
tests/progression/test_character_grant_receipt_cleanup.py
tests/progression/test_character_respec_rebase.py
tests/progression/test_content_recovery_character_semantics.py
tests/progression/test_dependency_neutral_progression_foundation.py
tests/progression/test_dragonborn_origin_definitions.py
tests/progression/test_dragonborn_origin_runtime.py
tests/progression/test_dwarf_acolyte_authored_content.py
tests/progression/test_editable_character_creation_plans.py
tests/progression/test_fighter_champion_materialization.py
tests/progression/test_fighter_character_grant_appliers.py
tests/progression/test_fighter_progression_definitions.py
tests/progression/test_half_orc_origin_runtime.py
tests/progression/test_halfling_origin_runtime.py
tests/progression/test_multiclass_composition.py
tests/progression/test_origin_feature_contract.py
tests/progression/test_origin_feature_definitions.py
tests/progression/test_origin_innate_spellcasting.py
tests/progression/test_origin_integration_matrix.py
tests/progression/test_origin_structural_feature_applier.py
tests/progression/test_origin_structural_primitives.py
tests/progression/test_player_character_body.py
tests/progression/test_schema2_character_materialization.py
tests/progression/test_schema2_sorcerer_runtime_actions.py
tests/progression/test_sorcerer_character_grant_appliers.py
tests/progression/test_sorcerer_class_materialization.py
tests/progression/test_sorcerer_progression_definitions.py
tests/progression/test_sorcerer_spell_source_materialization.py
tests/progression/test_starting_apparel_packages.py
tests/progression/test_starting_equipment_packages.py
tests/progression/test_structural_class_feature_definitions.py
```

### 14.4 Bounded retained-test edits

```text
tests/engine/test_standard_conditions.py
tests/engine/test_spell_families.py
tests/engine/test_world_entity_initialization.py
tests/manual/test_125_haste_restricted_action.py
tests/manual/test_132_barbarian_unarmored_defense.py
tests/manual/spell_regression_support.py
tests/manual/test_14_spell_families.py
tests/manual/test_126_action_override_runtime.py
tests/manual/test_131_inventory_use_actions_legacy_contract.py
tests/manual/test_142_item_equip_hooks_legacy_contract.py
tests/progression/test_bg3_spell_action_economy.py
tests/progression/test_direct_item_durable_and_proficiency.py
tests/progression/test_normal_spell_slot_capacity.py
tests/progression/test_saving_throw_context.py
tests/progression/test_source_owned_engine_primitives.py
tests/progression/test_spell_damage_affinity_contributions.py
tests/progression/test_spellcasting_source_action_propagation.py
```

`test_source_owned_engine_primitives.py` is rewritten only for retained public
owner cases; its generic receipt interpreter/server projection cases are
deleted. Deferred persistence/scenario/server test modules are untouched and
remain governed exclusions. In particular, their old owned-character
deployment tests remain deferred to CR-7; they do not justify retaining an
active materializer import in the maintained assembler.

No other test path is authorized without a ledger amendment and an explicit
node disposition.

## 15. Hard-cut, DAG, locality, and stop searches

The final CR-4/CR-5 architecture gate must AST-check the active production and
maintained proof closure for:

1. no imports of deleted character modules or generic character authority from
   the maintained gameplay closure; the only durable-character/deployment DTO
   imports are inside the exact CR-7 deferred island, governed excluded
   persistence tests, or the one retained direct-item proof import of
   `CharacterItemV2` in
   `tests/progression/test_direct_item_durable_and_proficiency.py`;
2. no character `ContentRef`, `ContentRecipe`, materializer, build revision,
   ruleset digest/schema, factory string, registry/runtime/provider lookup;
3. no required owner fields `provider_ref` or `spell_ref`;
4. no character call to `bind_runtime_behavior*`, runtime context, gateway, or
   installed content system;
5. only the four exact `BehaviorBinding`-only imports in section 10.1;
6. no `EntityTransform`, `Undo`, callback/closure receipt, context-manager
   transaction, command, operation list, generic handle/interpreter;
7. no `Entity.get_all_entities`, `BaseBlock.get`, semantic condition scan, or
   global receipt lookup in character cleanup;
8. no late/local import, `TYPE_CHECKING`, `getattr`, runtime type dispatch, or
   new cycle;
9. no progression/materialization methods added to Entity;
10. no duplicate Ability/Skill/Save aliases or progression calculations;
11. no legacy and direct authority for one migrated origin/class family;
12. no premade-specific factory/post-build patch;
13. no renderer/assets/generated bindings/server/SDK/transport dependencies;
14. no edits outside the exact production/test envelope; and
15. CR-0 appearance and direct-item evidence remain hash-exact.

The import DAG is mechanically checked as:

```text
dnd/types
    -> core/blocks/Entity/concrete mechanics
    -> dnd/content/characters cold definitions
    -> dnd/content/characters procedural grants/progression/builds
    -> scenario/application caller
```

Cold definition imports must not create Entity/block/item/Event instances or
mutate a registry. Domain-local installer maps must not be imported by the
leaf definitions or receipts.

Stop conditions remain exactly those in the accepted plan. Preflight found no
required global lookup, owner-less runtime child, behavior-domain explosion,
dual identity, or premade-only path. If implementation disproves any exact
owner API or runtime-child relation recorded here, it stops for a narrow
amendment; it does not improvise infrastructure.

## 16. Slice authorization sequence

After independent Slice-0 approval, implementation proceeds exactly:

1. Slice 1: dependency leaves, direct owner schemas, Entity semantic substrate,
   narrow level facts, and action-template owner identity. The accepted
   durable-item value remains unchanged in the deferred DTO island.
2. Slice 2: complete origins plus their exact CR-2C cut.
3. Slice 3A: Fighter/Champion 1-20.
4. Slice 3B: Barbarian/Berserker 1-20.
5. Slice 3C: Sorcerer/Draconic 1-20 and 70 semantic entitlements.
6. Slice 4: aggregate add/remove, multiclass reconciliation, event chronology,
   and silent hydration.
7. Slice 5: direct custom build and four ordinary premades.
8. Slice 6: hard deletion and exact test succession.
9. Slice 7: one final maintained union, manifest, validation, and three
   independent frozen-candidate approvals.

No intermediate checkpoint is an accepted dual architecture.

## 17. Slice-0 review record

All three reviewers approved the same substantive plan/ledger candidate at
plan SHA-256
`3ace123c57bb273aa2bb1c50933f8e82bcb9390de614254359dbc9469e2aba7e`
and ledger SHA-256
`71cfedd09319f7c6e01c284005c028fef2eaa2cb34ebdfff8e1d0984eda7eaa5`.
The only later edits are this approval record, the plan's acceptance status,
and its resulting governing hash above.

| Review | Verdict | Notes |
|---|---|---|
| correctness/completeness | `APPROVE` | exact rows/hashes/importers, Darkness closure, DTO disposition, and completion-only publication boundary are complete |
| anti-slop/minimality | `APPROVE` | no adapter/duplicate item module, replacement framework, generic receipts, callback chain, or excess layer |
| anti-OOP/ECS/import-DAG | `APPROVE` | Entity ownership, stateless composition, owner cleanup, assembler cut, and quarantined DTO island preserve the DAG |

The coordinator records `SLICE_0_ACCEPTED` and authorizes Slice 1 only. All
later slices remain subject to their checkpoint reviews.

## 18. Slice-1 implementation checkpoint

Slice 1 is implemented as one unreleased direct-state substrate. Slice 2 and
all authored origin definitions/grants remain untouched.

### 18.1 Production result

The exact Slice-1 production paths are:

```text
dnd/actions.py
dnd/blocks/abilities.py
dnd/blocks/equipment.py
dnd/blocks/saving_throws.py
dnd/blocks/skills.py
dnd/blocks/spellcasting.py
dnd/content_system/builtin_character_grant_appliers.py
dnd/content_system/character_materialization.py
dnd/content_system/condition_effect_population.py
dnd/content_system/extra_attack_character_grant_appliers.py
dnd/content_system/origin_innate_spellcasting.py
dnd/core/base_actions.py
dnd/core/content/effects.py
dnd/core/content/origin_features.py
dnd/core/events.py
dnd/core/feature_grants.py
dnd/entity.py
dnd/items/environment_interactables.py
dnd/monsters/srd_roster.py
dnd/spells/abjuration.py
dnd/spells/catalog_content.py
dnd/spells/content_metadata.py
dnd/spells/enchantment.py
dnd/spells/evocation.py
dnd/spells/infernal.py
dnd/spells/necromancy.py
dnd/spells/transmutation.py
dnd/types/abilities.py
dnd/types/character_progression.py
dnd/types/character_receipts.py
```

The change provides exactly the accepted substrate:

- one dependency-leaf authority for ability, skill, and saving-throw names;
- direct spell-source, learned-reaction-spell, and attack-multiplicity owner
  identities, migrated with their current consumers;
- direct character semantic values plus four closed concrete receipt rows;
- Entity-owned character body/origin/level/preparation/toggle state, exact
  source-owned feature contributions, and private ephemeral receipt storage;
- one direct character birth projection alongside unchanged creature identity;
- narrow add-level/remove-level terminal fact classes; and
- exact Entity-owned action-template identity on executable instances.

Entity contains no public add/remove-level, materialization, hydration, or
character-validation operation. The species-variant parent rule is not placed
on Entity; it remains the responsibility of the Slice-2 cold resolver.

### 18.2 Test result

The exact changed or added Slice-1 test paths are:

```text
tests/architecture/test_content_recovery_cr45_direct_characters.py
tests/engine/test_spell_families.py
tests/engine/test_standard_conditions.py
tests/engine/test_traversal_connectors.py
tests/engine/test_world_entity_initialization.py
tests/manual/spell_regression_support.py
tests/manual/test_125_haste_restricted_action.py
tests/manual/test_126_action_override_runtime.py
tests/manual/test_131_inventory_use_actions_legacy_contract.py
tests/manual/test_142_item_equip_hooks_legacy_contract.py
tests/manual/test_14_spell_families.py
tests/progression/test_direct_character_progression.py
tests/progression/test_dragonborn_origin_runtime.py
tests/progression/test_multiclass_composition.py
tests/progression/test_origin_innate_spellcasting.py
tests/progression/test_origin_integration_matrix.py
tests/progression/test_saving_throw_context.py
tests/progression/test_sorcerer_spell_source_materialization.py
tests/progression/test_source_owned_engine_primitives.py
tests/progression/test_spellcasting_source_action_propagation.py
```

Validation completed on the candidate:

| Gate | Result |
|---|---|
| new public substrate plus CR45 architecture gate | `9 passed` |
| direct owner/action/event focused union | `121 passed in 22.73s` |
| compileall over `dnd` and new tests | exit `0` |
| `git diff --check` | clean; existing line-normalization notices only |
| old Ability/Skill/Save importer AST scan | `0` |
| retired required-owner keyword AST scan | `0` |

The focused 121-node union covers the new direct-character proof, new CR45
architecture gate, spell-source propagation, spell slots and affinities,
saving-throw context, retained extra-attack/spell-source owner cases, Entity
composition, Event lifecycle, action discovery/cost atomicity, and the complete
maintained Haste restricted-action module.

Full architecture execution reports `69 passed, 5 failed`. Three failures are
the unchanged rollback-checkpoint server/world-contract import of the absent
`dnd.core.senses`; one is the predecessor direct-item gate correctly observing
the intentional Slice-1 owner/import deltas; and one is the predecessor
content-contract allowlist not yet admitting the plan-required neutral
`dnd.types.character_progression` leaf. The new CR45 DAG gate is green. These
old gates receive their already-planned successor/update at the hard-cut
boundary; no compatibility import or unrelated server repair was added.

The unreleased old character materializer remains intentionally nonfunctional
against the removed Entity tuple/ref fields. Four world-initialization cases
that still construct classed creature roots through that legacy character
materializer therefore fail at its old `species_ref` keyword. This is the
explicitly permitted intermediate red route, not a second compatibility path.
Two retained-owner predecessor cases also retain their pre-Slice-1 stale
pre-direct-item `Weapon` fixtures without required `item_id`; they are not
caused by this slice and were not broadened here.

### 18.3 Checkpoint boundary

No server, SDK, transport, generated, renderer, asset, Pygame, CR-6 monster,
CR-7 scenario-definition, or Slice-2 origin implementation was changed. The
candidate now awaits the plan-required correctness, anti-slop, and
anti-OOP/ECS/import-DAG reviews. Any production/test repair invalidates these
checkpoint results and requires the affected gates to be rerun.

### 18.4 First-review repairs and repaired candidate

The first independent review pass rejected three bounded omissions. The
candidate was repaired without starting Slice 2 or changing the accepted
architecture:

- immutable `registered_template_uuid` now retains the first Entity-owned
  template through ordinary, Move, slot, restricted, connector, equipped-
  weapon, and final executable-copy paths; caller-supplied replacement is
  ignored;
- the remaining duplicate six-ability literal in `dnd/blocks/abilities.py`
  and the condition-effect alias were migrated to the single neutral leaf;
- the four receipt rows now name their actual ECS-owned modifier surfaces,
  origin loadout UUIDs were removed, origin resource contributions retain
  their exact resource name and contribution UUID, and Sorcerer replacement
  state is one explicit semantic ID plus its one concrete prior ownership
  form; and
- stale assertions on the three already-migrated direct owner schemas now
  read the direct IDs.

`dnd/actions_functional.py`, `dnd/classes/fighter.py`,
`dnd/content_system/condition_effect_population.py`, and
`dnd/core/content/effects.py` are narrow closure additions required to keep
those existing factories/consumers atomic. They add no new API or layer.

Repaired validation:

| Gate | Result |
|---|---|
| repaired CR45 architecture/direct proofs plus connector, structural restricted action, composed slot/restricted action, and direct innate owner | `14 passed in 3.83s` |
| broad affected direct-owner/action/spell/condition/traversal union | `170 passed, 3 expected intermediate legacy-materializer failures` |
| focused migrated owner assertions independent of the legacy materializer | `2 passed` |
| full architecture | `70 passed, 5 known predecessor failures` |
| compileall | exit `0` |
| `git diff --check` | clean; existing line-normalization notices only |
| duplicate six-ability literals outside the neutral leaf | `0` |
| stale migrated spell-source assertions | `0` |

The three broad-union failures and the materializer-dependent assertion cases
all stop at the already-recorded obsolete `species_ref` call before reaching
their later assertions. The five architecture failures remain the same
predecessor direct-item importer delta, neutral-leaf allowlist, and missing
server/world `dnd.core.senses` failures. No compatibility path was restored.

Status: `SLICE_1_REPAIRED_CANDIDATE — READY_FOR_INDEPENDENT_REVIEW`.

### 18.5 Final Slice-1 approval

All three reviewers approved the exact repaired candidate after the final
Origin resource-owner and test-quality repairs:

| Review | Verdict | Exact result |
|---|---|---|
| correctness/completeness | `APPROVE` | Origin resource contributions are exact; build-owned loadout, owner migration, and root provenance are correct; independent selection `12 passed` |
| anti-slop/minimality | `APPROVE` | no private-helper public proof, permissive receipt schema, speculative receipt field, compatibility layer, callback, or generic interpreter remains |
| anti-OOP/ECS/import-DAG | `APPROVE` | concrete ECS owners, data-only leaves, no progression methods on Entity, no late imports/reflection, production import graph `0` SCCs |

Coordinator verification on the final candidate is `14 passed in 3.83s` for
the repaired focused gate and `70 passed, 5 known predecessor failures` for
the complete architecture lane. Compileall and diff-check are clean.

Status: `SLICE_1_ACCEPTED — SLICE_2_AUTHORIZED`.

## 19. Slice 2 direct origins checkpoint

### 19.1 Implemented ownership cut

Slice 2 ports the complete 9-species, 4-variant, 2-background origin domain to
the cold `dnd.content.characters.origin_definitions` values and the one direct
procedural owner in `dnd.content.characters.origin_grants`. Resolution is pure
and exact: the accepted 16-language and 18-skill vocabularies, ordered choice
requirements, cardinality, parent-variant law, flexible +2/+1 bonuses, and
duplicate proficiency rejection are all explicit values.

`apply_origin`, `remove_origin`, and `reconcile_origin_total_level` install and
clean only concrete Entity/component source contributions recorded in the
closed `OriginGrantReceipt`. The complete eighteen-family mapping is present:
Acolyte holdings identity; darkvision; Dragonborn ancestry resistance and
breath action; Dwarf training and poison resilience; Fey Ancestry; Gnome
Cunning; Half-Orc Endurance and Savage Attacks; Halfling Brave and Lucky;
Tiefling fire resistance and innate spells; High Elf training and Fire Bolt;
Hill Dwarf toughness; and Rock Gnome tools/capabilities. Total-level
reconciliation covers Dragonborn dice, Hill Dwarf hit points, High Elf caster
level, and Tiefling level-3/5 spell thresholds. Removing or scaling below an
active Tiefling Darkness grant first drops the exact concentration slot through
the existing condition owner.

The Dragonborn action and Halfling/Half-Orc processors now carry direct
primitive `BehaviorBinding` values supplied by the origin owner. Their three
legacy behavior declarations and refs are gone. The four origin runtime/
applier modules are deleted; the generic materializer no longer installs
origin structural or innate rows; and the installed declaration inventory no
longer contains species, variant, background, passive-origin, ancestry,
origin-behavior, Acolyte-holdings, or legacy character-root rows. The old
definition sources remain temporarily importable only for unreleased legacy
class/premade data that later slices replace; they are no longer installed
content or an origin mutation path.

### 19.2 Narrow file-envelope amendment

`dnd/content_system/icon_bindings.py` is one required mixed-file addition to
the Slice-0 envelope. Removing the active origin/character declarations while
preserving their frozen CR-8 presentation evidence otherwise makes the
existing built-in icon validator treat historical evidence as live declaration
ownership. The bounded filter excludes exactly the migrated character evidence
rows from that live-owner equality check, using the same evidence-boundary
mechanism already established for direct items. It adds no runtime lookup,
resolver, binding path, or renderer authority. Reviewers must judge this exact
amendment with the candidate; no other new production path is admitted.

### 19.3 Test succession and proof results

The obsolete origin definition/runtime/integration/structural predecessor
group is deleted. Its successor is the public direct-origin suite plus the
CR45 architecture gate. The successor proves exact authored tables and
ancestries; every species/variant with both backgrounds; invalid choice and
variant failures; exact apply/remove cleanup; sibling-source preservation;
all eighteen mechanic families; actual Lucky, Relentless Endurance, Breath
Weapon, lightfoot traversal, save-context rules, scaling thresholds, and
active Darkness cleanup. The architecture proof freezes the cold import DAG,
the `BehaviorBinding`-only exception, absence of runtime devices/global scans,
retired installed behavior identities, deleted legacy runtime modules, zero
active legacy importer, and removal of the old materializer/inventory entry
points.

The first frozen Slice-2 candidate was rejected by correctness and anti-slop
review. Those rejections were valid and no approval from that candidate is
carried forward:

- the Tiefling learned-reaction handler appeared in both generic handler and
  learned-source ownership, so removing Tiefling could delete a handler still
  owned by a sibling provider;
- Tiefling Darkness cleanup selected concentration by spell name rather than
  by the exact origin action/template-to-runtime-root edge, so a later
  Sorcerer Darkness could be removed accidentally;
- a direct level jump installed threshold spells with threshold levels instead
  of the new total level;
- two unused receipt fields and one test-only private dice patch were
  speculative surface.

The first repaired candidate fixed those four issues, but correctness review
then rejected one deeper operational defect: a sibling Hellish Rebuke source
could preserve the handler structurally while that handler's processor remained
permanently bound to the removed Tiefling source/resource. Reapplication also
conflicted with the surviving handler UUID. The anti-slop and ECS approvals on
that superseded candidate are not carried forward.

The final repaired candidate keeps one owner edge for each fact. Learned
reaction ownership in `SpellcastingBlock` records each exact source together
with its source-local cost facts: either fixed innate rank plus resource, or
ordinary spell-slot use. The single handler reads those current facts; it is
not closed over one provider. Origin installation reuses an existing live
handler and only creates it when the spell has no handler. Public proof executes
the surviving Sorcerer-slot reaction after origin removal, reapplies Tiefling
over that same handler, executes the innate reaction after the class slot is
spent, and removes/reapplies without replacing or orphaning the handler.
Concrete
`Darkness` templates retain their exact active concentration slot UUID, and
origin cleanup consults only the registered Darkness action recorded by that
origin receipt. It cannot select a sibling cast by name. Direct jumps now use
the actual new total level. The unused receipt fields are removed and public
proofs use `fixed_dice_faces`. Public regressions cover sibling
Hellish-Rebuke ownership, direct 1-to-16 reconciliation, an actual active
origin Darkness cast, and a later Sorcerer-owned Darkness that survives origin
removal.

These exact owner edges require narrow production-envelope amendments in
`dnd/spells/conjuration.py` and `dnd/spells/infernal.py`. Darkness changes are
confined to concrete `Darkness`. Hellish Rebuke changes remove the fixed
provider arguments from its existing handler and read the existing
`SpellcastingBlock` ownership row. They add no generic lifecycle, registry,
callback, manager, or second event path.

Validation on the repaired candidate:

| Gate | Result |
|---|---|
| direct origins plus CR45 architecture | `59 passed in 6.00s` |
| post-repair progression/spell/condition/traversal affected lane | `162 passed, 5 known predecessor fixture failures` |
| exact shared learned-reaction schema/Counterspell lane | `3 passed in 0.80s` |
| earlier broad characterization lane | `208 passed, 7 known pre-existing direct-item fixture failures` |
| complete architecture lane | `71 passed, 10 governed predecessor/deferred failures` |
| compileall over `dnd` and successor tests | exit `0` |
| `git diff --check` | clean; existing normalization notices only |
| retired origin runtime/applier import scan | `0` active production matches |
| direct-origin forbidden runtime-device scan | `0` |

The seven broad-lane failures are old sensory/light fixtures constructing
`BaseItem`, `DirectionalWall`, or `DirectionalDoor` without the already-
required direct-item `item_id`; none reaches origin code. The ten architecture
failures are six predecessor CR-0/direct-item authority/count/node/overlay
assertions that intentionally predate this unreleased character cut, the
Slice-1 neutral-leaf allowlist predecessor, and three deferred server/world
imports of absent `dnd.core.senses`. No compatibility facade or out-of-scope
fixture repair was added.

Frozen primary bytes for independent review:

| File | SHA-256 |
|---|---|
| `dnd/content/characters/origin_definitions.py` | `9503bc12754f3653215f02483f108f373ad72a332f06a2887021e8f4164ae9e4` |
| `dnd/content/characters/origin_grants.py` | `24e8e54d40e4dfeaa241784dcd0a583a7894a32932ba44fc446b590fccb21cbd` |
| `dnd/types/character_receipts.py` | `ed139699c4d230ad662dada995a5c661a03557c1b82495cd460649bfe19465ad` |
| `dnd/blocks/spellcasting.py` | `97a5783272d4628f4d871e6e9fc27d23b4517bbd86ed72c6c1755409f0f93e77` |
| `dnd/spells/infernal.py` | `a07a1e430fb2c9d461fcc06ea46669e99e1b0d2a3b820b491b4730995c5340c4` |
| `dnd/spells/conjuration.py` | `dae0d7e417bee8c1fcb4ddb94865ca82b88fb4c563474971bcd51c07d94cf67b` |
| `dnd/content_system/icon_bindings.py` | `31d86abaa7905c338331939610bb0ff7cc2c60f654c653d9ffb22dbfec89f445` |
| `tests/progression/test_direct_character_origins.py` | `773600ab751155ec058528f92bf01b88e7831b340933786cb233615c7506e6cf` |
| `tests/architecture/test_content_recovery_cr45_direct_characters.py` | `57dc41c9978ed0b4067c7a5cf30df37b33ee0057070174475aee693c768e8b2a` |

Status: `SLICE_2_REPAIRED_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 19.4 Final Slice-2 approval

All three reviewers approved the same final repaired production/test bytes.
Every earlier approval was treated as invalid after the operational learned-
reaction repair.

| Review | Verdict | Exact result |
|---|---|---|
| correctness/completeness | `APPROVE` | surviving class-slot and reapplied innate Hellish Rebuke execute through the same handler; source selection, save DC, cost consumption, remove/reapply, last-owner retirement, rollback, Darkness ownership, and total-level scaling are correct |
| anti-slop/minimality | `APPROVE` | source-local reaction cost facts extend the existing `SpellcastingBlock` owner only; no generic cost language, lifecycle, registry, manager, callback chain, compatibility layer, private test hook, or duplicate authority |
| anti-OOP/ECS/import-DAG | `APPROVE` | frozen source facts plus concrete owner methods; no Entity growth, late import, reflection/type-dispatch cheat, or circularity; independent graph check found 249 modules, 1,659 internal edges, and 0 cyclic SCCs |

Coordinator replay on the final reviewed bytes is `59 passed in 6.00s` for the
focused successor gate, `162 passed` with the same five governed predecessor
fixture failures for the affected lane, and `71 passed` with the same ten
governed predecessor/deferred failures for the full architecture lane.
Compileall and diff-check are clean.

Status: `SLICE_2_ACCEPTED — SLICE_3A_AUTHORIZED`.

## 20. Slice 3A — Fighter / Champion

### 20.1 Narrow owner-cleanup amendment proposed

The natural Slice-3A owner-failure proof exposed one pre-existing omission in
the exact `Health` owner operation. `Health.remove_hit_dice_by_uuid` detaches
and unregisters the selected `HitDice` block, but leaves the selected hit
die's two `ModifiableValue` trees and their registered base modifiers alive.
The failing proof has no gameplay/Event residue and no sibling-state loss; its
only delta is two `NumericalModifier` registry entries named
`Hit Dice Value_base_value` and `Hit Dice Count_base_value`.

The smallest lawful correction is confined to the existing owner method:

- `Health.remove_hit_dice_by_uuid` follows the selected `HitDice` object's
  `hit_dice_value` and `hit_dice_count` fields;
- for each value it traverses only the four locally owned channels
  (`self_static`, `to_target_static`, `self_contextual`, and
  `to_target_contextual`), unregisters and clears their concrete modifier
  buckets, unregisters exactly those channels and the parent value, then
  unregisters the selected `HitDice`;
- borrowed `from_target_static` and `from_target_contextual` references are
  only dropped from the removed value; their channels and modifiers remain
  registered because they are owned by the target value;
- it performs no registry scan, Entity scan, reflection, type switch, generic
  cleanup interpretation, callback, transaction, or new public abstraction;
- a sibling hit die and every sibling registry member remain identity-exact.

This discovery narrowly amends the authorized production/test envelope with:

```text
dnd/blocks/health.py
tests/progression/test_source_owned_engine_primitives.py
```

The owner-level proof will freeze the removed hit die's exact block/value/
modifier UUIDs, prove their absence, and prove the sibling hit die's exact
block/value/modifier UUIDs remain registered. It also attaches one imported
target-owned channel/modifier to the removed value and proves that borrowed
identity remains registered after the removed value only drops its reference.
The direct Fighter natural-
failure proof will compare complete `BaseBlock`, `BaseValue`, and `BaseObject`
registry key sets before and after rollback. No other scope is authorized by
this amendment.

Status: `SLICE_3A_OWNER_CLEANUP_AMENDMENT — READY_FOR_REVIEW`.

### 20.2 Owner-cleanup amendment approval and implementation

All three reviewers approved the corrected §20.1 amendment at exact ledger
SHA-256
`cb4e1a448574d2a8e70ba7b0a238857c8782d024c10dcbc37128da9507e79f85`
before the owner code changed.

| Review | Verdict | Exact result |
|---|---|---|
| correctness/completeness | `APPROVE` | cleanup is limited to the selected hit die's two value trees and four locally owned channels; borrowed channels/modifiers and sibling identities remain owned and registered |
| anti-slop/minimality | `APPROVE` | one existing `Health` owner operation was completed; no scan, callback, transaction, lifecycle, manager, registry abstraction, or generic cleanup layer |
| anti-OOP/ECS/import-DAG | `APPROVE` | local ownership is explicit, borrowed `from_target_*` projections are only detached, and no reflection, type routing, or cycle-producing dependency was added |

`Health.remove_hit_dice_by_uuid` now performs that exact local-tree cleanup.
The public owner proof retains a foreign outgoing channel and modifier by exact
UUID while removing the selected hit die's block, values, four local channels,
and locally owned modifiers. The natural Fighter application failure also
restores complete `BaseBlock`, `BaseValue`, and `BaseObject` registry key sets.

### 20.3 Slice-3A frozen candidate

Slice 3A ports the complete Fighter/Champion level 1–20 table and choices,
applies each row through direct component owners, stores one closed typed
receipt per row, and removes levels 20–1 in exact reverse order. The direct
owner covers first-class and multiclass proficiencies, saving throws, skills,
one d10 hit die per level, all seven ASI/feat choices, all six fighting styles,
Second Wind, Action Surge, Extra Attack ranks, Indomitable, Improved/Superior
Critical, Remarkable Athlete, Survivor, and Lucky. Actions and handlers carry
direct immutable `BehaviorBinding` values. No level Event is published in this
slice; the public aggregate/Event boundary remains Slice 4.

The migrated family is hard-cut from the installed legacy inventory and
generic character-grant applier. Shared Extra Attack and Lucky declarations
remain installed only because not-yet-migrated class families still own them.
The old Fighter applier module and its three predecessor progression suites are
deleted; inactive legacy definition/build evidence remains available for the
later build cut and is not an active installed admission path.

Changed Slice-3A production paths:

```text
dnd/blocks/health.py
dnd/content/characters/class_definitions.py
dnd/content/characters/fighter_grants.py
dnd/types/character_receipts.py
dnd/content_system/builtin_character_grant_appliers.py
dnd/content_system/builtin_inventory.py
dnd/content_system/icon_bindings.py
dnd/content_system/fighter_character_grant_appliers.py (deleted)
```

Changed Slice-3A proof paths:

```text
tests/progression/test_direct_fighter_progression.py
tests/progression/test_source_owned_engine_primitives.py
tests/architecture/test_content_recovery_cr45_direct_characters.py
tests/progression/test_fighter_progression_definitions.py (deleted)
tests/progression/test_fighter_character_grant_appliers.py (deleted)
tests/progression/test_fighter_champion_materialization.py (deleted)
```

Validation on the frozen candidate:

| Gate | Result |
|---|---|
| direct Fighter/progression plus CR45 architecture successor | `30 passed in 6.34s` |
| exact hit-die local/borrowed ownership proof | `1 passed in 0.33s` |
| affected direct/owner/behavior/runtime lane excluding two known direct-item fixture cases | `74 passed, 2 deselected in 10.42s` |
| Fighter behavior characterization | `32 passed, 4 governed obsolete geometry/visibility fixture failures` |
| direct-character architecture plus complete import-cycle gate | `14 passed in 10.18s` |
| complete architecture lane | `73 passed, 10 governed predecessor/deferred failures in 92.10s` |
| compileall over changed direct/owner/proof paths | exit `0` |
| `git diff --check` | clean; existing normalization notices only |
| direct Fighter forbidden-device scan | `0` |
| retired Fighter applier importer scan | `0` |

The four behavior failures are the pre-existing Action Surge/Extra Attack
fixture cases whose `AttackEvent` is canceled before the feature mechanics by
their obsolete geometry/visibility setup. The ten architecture failures are
the same predecessor CR-0/direct-item authority/count/node/overlay assertions,
the already-governed neutral-leaf allowlist, and the deferred server/world
imports of absent `dnd.core.senses`. No compatibility layer or out-of-scope
fixture repair was added.

Frozen primary bytes:

| File | SHA-256 |
|---|---|
| `dnd/blocks/health.py` | `04031a72478b8d490dae82044f466729ba999add2f48026fb907b28adeb1ff53` |
| `dnd/content/characters/class_definitions.py` | `3bc08f55085fb890e40dfb486dbbd8dda9f256d14dbea20ccf83d012ae117803` |
| `dnd/content/characters/fighter_grants.py` | `5b101734578b180176f7dc57c1144384d0c36e70fbe4e4e1870d0f3584d9aa64` |
| `dnd/types/character_receipts.py` | `c923058ae5154d1f8569376c6bc96a6148fdf864cee12c584713ac07a8762632` |
| `dnd/content_system/builtin_character_grant_appliers.py` | `995c8efaa569d5891a79a84f7804dab8542ec9aeee67d5b6174acfdfb20b56d4` |
| `dnd/content_system/builtin_inventory.py` | `7c0334f374f7786bee021d072cdf4563c93d3545dd5365899d150fe09bce7ee8` |
| `dnd/content_system/icon_bindings.py` | `d3b74d5a94879e30c48e8937bcbb4adfd29357c7f655c318102ae2f35fe7dab5` |
| `tests/progression/test_direct_fighter_progression.py` | `388f9997e42f0c3c73a44c9246569a373e90efef85c80f422a3fe094e0dbb4e2` |
| `tests/progression/test_source_owned_engine_primitives.py` | `d05a623005c79a29ba9239440bee099c89dbd7ce8954897ef4e720f81f6a81f4` |
| `tests/architecture/test_content_recovery_cr45_direct_characters.py` | `a3fd2ee2279a8aee94807b43e57a1fb7df964b9eab7f7fef5f9e093360d1b837` |

Status: `SLICE_3A_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.4 First candidate rejection and bounded repair

The first §20.3 candidate was rejected. Its one ECS/DAG approval is invalidated
with the production changes; no verdict from that candidate carries forward.
Independent review found three concrete defects:

1. the five contextual Fighter callbacks returned registered evaluation-only
   `NumericalModifier` children, so evaluating Remarkable Athlete or a relevant
   fighting style could leave registry residue after level removal;
2. Second Wind level scaling selected the first action with a matching semantic
   behavior ID rather than the exact level-1 receipt-owned action UUID, so a
   sibling provider could be mutated; and
3. the grant owner repeated the cold feature-presence schedule through raw
   level predicates, creating a second authority that could diverge from the
   resolved authored row.

The repair remains inside the already-frozen Fighter behavior closure.
`dnd/classes/fighter.py` is added explicitly to the Slice-3A changed-path list;
it was already an authorized Slice-0 behavior-closure member. Defense, Dueling,
both Two-Weapon Fighting callbacks, and Remarkable Athlete now return ordinary
unregistered evaluation values. Second Wind resolves the exact action UUID
from `class.fighter.level_1`'s typed receipt and performs only a local Entity
action-list lookup. Feature presence now comes only from
`resolved.feature_ids`; level comparisons remain only for rank values or the
first structural action/handler installation at levels 2, 5, and 9.

The public successor proof now:

- activates Defense, Dueling, melee and ranged Two-Weapon Fighting, and
  Remarkable Athlete three times each, proving correct values and zero
  `BaseObject` registry growth;
- proves successful style and full 1–20/20–1 round trips restore exact
  `BaseBlock`, `BaseValue`, and `BaseObject` registry key sets; and
- installs a hostile sibling Second Wind with the same behavior ID, proves
  levels 1–2 update only the receipt-owned action, and proves reverse removal
  preserves the sibling's identity and level.

Validation on the repaired candidate:

| Gate | Result |
|---|---|
| direct Fighter/progression plus CR45 architecture successor | `31 passed in 6.22s` |
| exact hit-die and contextual/sibling ownership focused lane | `27 passed in 6.23s` |
| affected direct/owner/behavior/runtime lane excluding two known direct-item fixture cases | `75 passed, 2 deselected in 9.80s` |
| complete import-cycle gate | `1 passed in 4.03s` |
| complete architecture lane | `73 passed, 10 unchanged governed predecessor/deferred failures in 88.80s` |
| compileall over changed direct/behavior/owner/proof paths | exit `0` |
| `git diff --check` | clean; existing normalization notices only |
| evaluation-only `NumericalModifier.create` in direct Fighter grants | `0` |
| raw level feature-presence predicates | `0`; only first-install levels 2/5/9 remain |

The governed red-node classifications recorded in §20.3 are unchanged.

Repaired frozen primary bytes:

| File | SHA-256 |
|---|---|
| `dnd/blocks/health.py` | `04031a72478b8d490dae82044f466729ba999add2f48026fb907b28adeb1ff53` |
| `dnd/classes/fighter.py` | `1362373048c3ec839437679371f2a60730cfa746bd81ff5eebdad2ce21ff27c7` |
| `dnd/content/characters/class_definitions.py` | `3bc08f55085fb890e40dfb486dbbd8dda9f256d14dbea20ccf83d012ae117803` |
| `dnd/content/characters/fighter_grants.py` | `7dbaa45e33eb5461bc6ff4d36eb5cd669f41f83438ee6feab0662cbfad954733` |
| `dnd/types/character_receipts.py` | `c923058ae5154d1f8569376c6bc96a6148fdf864cee12c584713ac07a8762632` |
| `dnd/content_system/builtin_character_grant_appliers.py` | `995c8efaa569d5891a79a84f7804dab8542ec9aeee67d5b6174acfdfb20b56d4` |
| `dnd/content_system/builtin_inventory.py` | `7c0334f374f7786bee021d072cdf4563c93d3545dd5365899d150fe09bce7ee8` |
| `dnd/content_system/icon_bindings.py` | `d3b74d5a94879e30c48e8937bcbb4adfd29357c7f655c318102ae2f35fe7dab5` |
| `tests/progression/test_direct_fighter_progression.py` | `553f67ce1ed8b018f54e2fc1d09ed44ab9d5c071351ab998610e83d34039ed12` |
| `tests/progression/test_source_owned_engine_primitives.py` | `d05a623005c79a29ba9239440bee099c89dbd7ce8954897ef4e720f81f6a81f4` |
| `tests/architecture/test_content_recovery_cr45_direct_characters.py` | `a3fd2ee2279a8aee94807b43e57a1fb7df964b9eab7f7fef5f9e093360d1b837` |

Status: `SLICE_3A_REPAIRED_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.5 Final Slice-3A approval

All three reviewers approved the same repaired production/test bytes frozen in
§20.4 at ledger SHA-256
`d2aac998aca575721c6b69e8d3ca63bdb2d4891c79d786d407edeca9ee33f0fc`.

| Review | Verdict | Exact result |
|---|---|---|
| correctness/completeness | `APPROVE` | reproduced Defense `1`, Dueling `2`, melee/ranged TWF `(3, 3)`, Remarkable Athlete without registry growth, exact successful registry restoration, hostile sibling Second Wind preservation, complete table/grants/reverse cleanup, and unchanged governed legacy failures |
| anti-slop/minimality | `APPROVE` | exact receipt-owned Second Wind lookup, one `resolved.feature_ids` schedule authority, unregistered evaluation values, no generic cleanup/callback/transaction/compatibility path/new layer, and no scope creep |
| anti-OOP/ECS/import-DAG | `APPROVE` | data-only receipts, procedural concrete owner composition, no Entity progression methods/reflection/type routing/late imports/services/managers/commands, and independent graph `250` modules / `1,671` edges / `0` cyclic SCCs |

Independent reviewer replays include `27 passed` on the exact focused
ownership lane, the repository cycle gate green, and all frozen primary hashes
matching §20.4. No production or test bytes changed after these approvals.

Status: `SLICE_3A_ACCEPTED — SLICE_3B_AUTHORIZED`.

### 20.6 Slice 3B Barbarian/Berserker frozen candidate

Slice 3B ports the complete cold Barbarian/Berserker level table and every
direct structural owner through `dnd/content/characters/barbarian_grants.py`.
The family now applies levels 1 through 20 and removes them 20 through 1 by
typed receipt-owned UUID/source rows. Rage advancement, Unarmored Defense,
Reckless Attack, Danger Sense, Extra Attack, Fast Movement, Feral Instinct,
Brutal Critical, Relentless Rage, Persistent Rage, Indomitable Might, Primal
Champion, Frenzy, Mindless Rage, Intimidating Presence, and Retaliation all
have direct concrete owners and reverse cleanup.

Rage and Reckless Attack templates retain only their exact active root UUID.
Frenzied is a subcondition of the Raging root and owns its exact Frenzied
Strike UUID. Berserker level 3 records the displaced Rage template's exact UUID
and configuration, installs Frenzy, and restores that same Rage identity when
removed. Evaluation-only Rage damage, Danger Sense, Fast Movement, and
Reckless modifiers are unregistered values. No name/global condition sweep,
generic receipt interpreter, callback transaction, compatibility facade, or
runtime content lookup was added.

The legacy Barbarian character applier and its three obsolete progression
proof modules are deleted. The class/subclass and exclusive behavior closure
is removed from the installed declaration inventory. The SRD Berserker
monster's independently-owned Reckless Attack/Reckless Attacking behavior pair
remains admitted; bootstrap dependency validation and monster traits prove
that shared ownership explicitly. The retained seven-case Unarmored Defense
manual module now builds its level-one actor through the direct public grant.

Validation on the frozen production/test candidate:

| Gate | Result |
|---|---|
| direct Barbarian/Berserker progression | `7 passed` |
| public Unarmored Defense successor | `7 passed` |
| direct-character CR45 architecture successor | `14 passed` |
| direct origin/Fighter/Barbarian/owner lane | `86 passed, 2 unchanged governed direct-item fixture failures` |
| Barbarian action and SRD monster mechanics | `54 passed` |
| complete import-cycle gate | `1 passed` |
| cleaned class-feature docstring gate | `1 passed` |
| complete architecture lane | `74 passed, 10 unchanged governed predecessor/deferred failures in 91.82s` |
| compileall over the Slice-3B closure | exit `0` |
| `git diff --check` | clean; existing normalization notices only |
| forbidden direct-owner routing/reflection scan | `0` |

The ten already-governed CR-0/CR-I/deferred-server failures remain outside the
family cut. The temporary eleventh failure introduced by the six new exact
owner fields was repaired only by documenting those fields in their existing
Google-style model docstrings; the complete replay returned to the exact
governed ten-failure set.

Frozen primary bytes:

| File | SHA-256 |
|---|---|
| `dnd/content/characters/class_definitions.py` | `25fe20c2a25ee397b754409467292647a98ff5d5e109125befd72a9c5c925d81` |
| `dnd/content/characters/barbarian_grants.py` | `1cce284f011abdebd1bf6e3b5f086e4cd500bf79bee7c96c7677e06de7edcf09` |
| `dnd/types/character_receipts.py` | `3bc4464182359fa179724e4272b9b70103fc0df85a395feea941109328455575` |
| `dnd/classes/rage.py` | `1f909ded532d119ee1d54c740e77386a1218c3af7e78b9cddb6938845b55bfd9` |
| `dnd/classes/barbarian.py` | `25f2df816a941b44e35bf824be4f21378237bc17904f98d8070b79fce02df1fc` |
| `dnd/content_system/builtin_character_grant_appliers.py` | `469638440efc0df028bfb1a6dd78a7df1d116ce882f22087143e0dda8f976b3f` |
| `dnd/content_system/builtin_inventory.py` | `0ec994028d2642927199a9c3ff5a438b966b744288077004fa022752ae52b143` |
| `dnd/content_system/icon_bindings.py` | `a4c6ca8dfe19b9b7de458ee4dd60735e1917a3f8d6f00dac4ab4b20b9d187e4d` |
| `tests/progression/test_direct_barbarian_progression.py` | `f59972b6c78bdf3281cb4b5057c16c8d12e94de2673745241fcc4af24c0a00e6` |
| `tests/manual/test_132_barbarian_unarmored_defense.py` | `040d3aac911363db06e5af054cf1bf42f83c512595b20d78525b5ae8f096f898` |
| `tests/architecture/test_content_recovery_cr45_direct_characters.py` | `4eca7a9917698e516e7a9997c7d43ff9bb3dc7e7d7bd5d8e1a10d96a1b0ce295` |

Status: `SLICE_3B_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.7 Slice 3B reviewer repair and refreeze

The first Slice-3B candidate was rejected. The anti-slop reviewer identified
duplicate Rage feature timing and loss of registered-action ordering across
the Rage/Frenzy replacement. The ECS/import-DAG reviewer reproduced two
partial-owner failures: failed Frenzy admission could lose the displaced Rage
template, and exceptional Frenzied admission could leave an unowned committed
Raging root. The correctness review was stopped without approval once those
findings were confirmed.

The repaired candidate remains concrete and family-local:

- Rage damage rank remains level-derived, while Mindless Rage and Persistent
  Rage now derive only from Entity-owned feature sources;
- active-root teardown on reverse progression compares the current template
  configuration with the exact post-receipt configuration instead of using a
  second raw level schedule;
- the Barbarian receipt stores the displaced Rage template's exact action-list
  index alongside its UUID and configuration, and restoration returns the
  template to that exact index;
- failed Frenzy admission restores the displaced Rage UUID, configuration,
  binding, and list position before propagating the owner failure; and
- exceptional Frenzied child admission removes the exact already-committed
  Raging root through the existing evented condition-removal boundary before
  propagating the failure.

Two public-owner failure proofs cover those partial boundaries. The ordinary
Frenzy replacement proof now also freezes ordered action UUID, concrete type,
semantic key, and binding across level-3 removal. No generic replacement
facility, transaction, callback, condition sweep, registry lookup, or new
owner abstraction was added.

Validation on the repaired candidate:

| Gate | Result |
|---|---|
| direct Barbarian, public Unarmored Defense, and CR45 successor | `30 passed in 8.84s` |
| direct origin/Fighter/Barbarian/owner lane | `81 passed, 2 unchanged governed direct-item fixture failures` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.81s` |
| complete architecture lane | `74 passed, 10 unchanged governed predecessor/deferred failures in 93.56s` |
| compileall over the repaired closure | exit `0` |
| `git diff --check` | clean; existing normalization notices only |
| forbidden routing/reflection/duplicate raw Rage schedule scan | `0` |

Repaired frozen primary bytes:

| File | SHA-256 |
|---|---|
| `dnd/content/characters/class_definitions.py` | `25fe20c2a25ee397b754409467292647a98ff5d5e109125befd72a9c5c925d81` |
| `dnd/content/characters/barbarian_grants.py` | `b5c7c4037fc1a81c64b6498b351386c8503487a26a7dfaaa74a0c7077654a288` |
| `dnd/types/character_receipts.py` | `016a100b3ee0e9e84d9fd854100c30821368d61294971953308328afa71fca08` |
| `dnd/classes/rage.py` | `fc5ad84964822a1ccfb2264831fb8f71ca81d091d49192b99c5622d538291091` |
| `dnd/classes/barbarian.py` | `25f2df816a941b44e35bf824be4f21378237bc17904f98d8070b79fce02df1fc` |
| `dnd/content_system/builtin_character_grant_appliers.py` | `469638440efc0df028bfb1a6dd78a7df1d116ce882f22087143e0dda8f976b3f` |
| `dnd/content_system/builtin_inventory.py` | `0ec994028d2642927199a9c3ff5a438b966b744288077004fa022752ae52b143` |
| `dnd/content_system/icon_bindings.py` | `a4c6ca8dfe19b9b7de458ee4dd60735e1917a3f8d6f00dac4ab4b20b9d187e4d` |
| `tests/progression/test_direct_barbarian_progression.py` | `baf8edda63014a04d59dd50f75c50be5911c8805ec9796290caf1bb95537d4e6` |
| `tests/manual/test_132_barbarian_unarmored_defense.py` | `040d3aac911363db06e5af054cf1bf42f83c512595b20d78525b5ae8f096f898` |
| `tests/architecture/test_content_recovery_cr45_direct_characters.py` | `560ad9cad452aee63a6b1719a5eca5b0275f31b5641b134edbf13054f14c4b66` |

Status: `SLICE_3B_REPAIRED_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.8 Slice 3B dead Rage-column cleanup

The anti-slop review found one residual duplicate rule value: the local Rage
uses table still retained a damage column even though damage rank already has
one explicit family-local authority in `_rage_damage()`.  The table is now a
uses-only map and its sole consumer reads that value directly.  No behavior,
owner edge, receipt, or test contract changed.

Validation after the cleanup:

| Gate | Result |
|---|---|
| direct Barbarian, public Unarmored Defense, and CR45 successor | `30 passed in 8.56s` |
| compile of the changed grant owner | exit `0` |
| scoped `git diff --check` | clean |

Changed frozen byte:

| File | SHA-256 |
|---|---|
| `dnd/content/characters/barbarian_grants.py` | `e904b352f9b0092f71d290fb4ee5cfbaa071c4eacc8c0e31d8d09cc211df05ee` |

Status: `SLICE_3B_CLEANUP_FROZEN_CANDIDATE — READY_FOR_TRIPLE_RECONFIRMATION`.

### 20.9 Slice 3B exceptional child-registry cleanup

The correctness review reproduced one remaining exceptional-admission leak.
When the public Entity owner rejected `FrenziedStrike`, the already-committed
Raging root was removed from Entity/component indexes, but the six modifiers,
three handlers, and the two condition-owned durations created by that failed
Raging/Frenzied graph remained in their object registry.

The correction is confined to the concrete Frenzy child-admission exception:
it records the exact objects already named by the Raging root, removes the
exact Raging condition tree through the existing event boundary, then
unregisters only those failed graph objects and the two exact condition-owned
durations.  Normal condition removal, the action event lifecycle, and action
cost commitment were not changed.  The public failure proof now compares
BaseBlock, BaseValue, and BaseObject state and proves the only surviving new
object is the already-committed `Frenzy_cost` action-economy modifier.

Validation after the correction:

| Gate | Result |
|---|---|
| direct Barbarian, public Unarmored Defense, and CR45 successor | `30 passed in 8.52s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.33s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Changed frozen bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `cc8415f37013f21ad040ec9c905f3cb3813deec8b3d4116d994a2733a6d58b65` |
| `dnd/content/characters/barbarian_grants.py` | `e904b352f9b0092f71d290fb4ee5cfbaa071c4eacc8c0e31d8d09cc211df05ee` |
| `tests/progression/test_direct_barbarian_progression.py` | `fdefdd7fb19b451a9bc0ff0969d05eb93211803b7962368a8d49ffc17199c75e` |

Status: `SLICE_3B_FINAL_REPAIR_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.10 Slice 3B canceled child-admission closure

Both correctness and anti-slop review exercised the adjacent lawful-cancel
outcome by giving the actor static Frenzied immunity.  That path returned a
canceled child admission instead of raising, so it required the same exact
failed-graph release as exceptional admission.  The concrete
`_release_failed_frenzied_graph` function now owns that one family-specific
operation and is called by both unsuccessful outcomes.  It does not alter the
generic Entity/BaseCondition lifecycle or the already-committed action cost.

The public failure proof runs both rejection forms.  Each returns Entity,
BaseBlock, BaseValue, actions, handlers, and active-condition ownership to its
baseline, with only the exact committed `Frenzy_cost` modifier remaining in
BaseObject.

Validation:

| Gate | Result |
|---|---|
| both public failed-child outcomes | `2 passed in 0.44s` |
| direct Barbarian, public Unarmored Defense, and CR45 successor | `31 passed in 8.82s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.35s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Changed frozen bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `3f1fa07cee4e613036ded7119d7ea5454d622ad1c0d6f39b5b4c5260e9a8d697` |
| `tests/progression/test_direct_barbarian_progression.py` | `e2135cb5b0feb15e1688ceb8b1688bcb0835828e4d884168baeb37bf6c08f7f8` |

Status: `SLICE_3B_FINAL_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.11 Slice 3B complete concrete-owner closure

The ECS/import-DAG review found that the preceding failed-graph repair still
left the same concrete Raging artifacts in `BaseObject` after successful
ordinary removal.  The correctness review then exercised both public
post-registration failure boundaries: a Frenzied EFFECT cancellation and an
exception from a Frenzied EFFECT handler.  Those paths had already installed
the Frenzied Strike action before the child condition was rejected.

The final correction assigns cleanup to the two concrete owners that created
the state.  Raging unregisters only its six exact modifiers, three exact event
handlers, and owned duration after the normal base detach operations.
Frenzied unregisters only its exact Frenzied Strike action and owned duration
through its existing provisional-state hook.  Normal child-first condition
removal, declaration rejection, registration failure, EFFECT cancellation,
and EFFECT exception therefore all traverse the same existing condition-tree
lifecycle without a generic BaseCondition change, name sweep, callback,
transaction, compatibility path, or new owner abstraction.

The public proof now covers all five boundaries: ordinary teardown, static
immunity, action-registration exception, EFFECT cancellation, and EFFECT
handler exception.  It freezes the exact action, handler, condition,
BaseBlock, BaseValue, and BaseObject state.  Failed executions retain only the
already-committed `Frenzy_cost` modifier.

Validation:

| Gate | Result |
|---|---|
| ordinary teardown plus four failed-child outcomes | `5 passed in 0.66s` |
| direct Barbarian, public Unarmored Defense, and CR45 successor | `33 passed in 9.31s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.11s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Final changed bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `aac1cc5a261e9d37ac620e013421e26125c3aa03b8a220b39a46812ff4a65e40` |
| `tests/progression/test_direct_barbarian_progression.py` | `5ecaf410fe2083602391bea00b342557654751f25ae06a5d15592a8ad6146dc3` |

Status: `SLICE_3B_COMPLETE_FROZEN_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.12 Slice 3B anti-slop deduplication

The anti-slop review confirmed the concrete ownership model and identified two
dead duplications.  Frenzied Strike release existed in both `_remove()` and
`_release_owned_runtime_state()` even though the accepted lifecycle invokes
the latter for both ordinary and provisional teardown.  The redundant
`_remove()` override is deleted.  The failed-graph helper also no longer
accepts the now-unused Frenzied child argument.  There is one owner operation,
one condition-tree removal path, and no semantic change.

Validation:

| Gate | Result |
|---|---|
| ordinary teardown plus four failed-child outcomes | `5 passed in 0.65s` |
| direct Barbarian, public Unarmored Defense, and CR45 successor | `33 passed in 9.26s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.23s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Final changed byte:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `846fa4360874ec0943c7a7c26fb33bae40418d1c7ad9a32892198c1219f00636` |
| `tests/progression/test_direct_barbarian_progression.py` | `5ecaf410fe2083602391bea00b342557654751f25ae06a5d15592a8ad6146dc3` |

Status: `SLICE_3B_ACCEPTANCE_CANDIDATE — READY_FOR_TRIPLE_RECONFIRMATION`.

### 20.13 Slice 3B immediate Raging ownership

The ECS review exercised Raging failures before `_apply()` could return its
artifact UUID rows.  An exception from Raging EFFECT publication therefore
left six modifiers and three handlers without recorded owner handles; rejection
of the second handler admission left the already-admitted prefix in the same
state.

Raging now records each modifier or handler in its own existing UUID
collections immediately after that exact Entity/component owner admits it.
An object rejected during its own admission is unregistered locally.  The
successful `_apply()` return no longer repeats those UUIDs, so BaseCondition
does not duplicate them.  The existing ordinary/provisional condition cleanup
then sees the same exact owner state regardless of whether failure occurs
during modifier admission, handler admission, EFFECT cancellation, EFFECT
exception, or after successful application.  No generic lifecycle, callback,
transaction, registry lookup, or new ownership structure was added.

The public proof exercises Rage and Frenzy independently across handler
admission rejection, Raging EFFECT cancellation, and Raging EFFECT exception,
in addition to the existing child-admission and ordinary-removal matrix.

Validation:

| Gate | Result |
|---|---|
| complete direct/public/architecture Barbarian gate | `39 passed in 9.57s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.45s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Final changed bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `51ed891cd74f581e1dbe5cb2b2202e9f6225ea8f29f50db422567acd16e1d815` |
| `tests/progression/test_direct_barbarian_progression.py` | `045f66fe8548861ccd50f639492174405784f615a7fe3d4ab0cd15a2a041a471` |

Status: `SLICE_3B_FINAL_ACCEPTANCE_CANDIDATE — READY_FOR_TRIPLE_REVIEW`.

### 20.14 Slice 3B Mindless chronology and strict edge closure

The final correctness review found that Mindless Rage removed existing Charmed
and Frightened state before Raging admission was accepted.  A failed level-six
admission could therefore lose pre-existing state and its removal events had
no direct semantic parent.  The purge is removed from `Raging._apply()` and
now runs only after the exact Rage root, or complete Frenzy root plus child,
has committed.  Each exact condition removal is parented to the accepted
Raging COMPLETION fact.  Failed level-six handler admission, EFFECT
cancellation, and EFFECT exception leave the original condition identity and
indexes untouched; successful admission removes both conditions with the
required direct parent chronology.

The ECS review also proved that a missing Frenzied Strike owner edge was being
silently cleared.  The single Frenzied release hook now requires its exact
`Entity.unregister_action_by_uuid()` operation to succeed whenever the owner
UUID is present.  Provisional paths with no admitted strike remain idempotent,
while out-of-order removal fails clearly and preserves the condition indexes.

Validation:

| Gate | Result |
|---|---|
| focused chronology/edge/root-failure matrix | `11 passed in 0.91s` |
| complete direct/public/architecture Barbarian gate | `44 passed in 9.18s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.33s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Final changed bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `3e0a837096f04f3b4ddfa92871b7a84877f2010e96838940d30092dc3a57ae28` |
| `tests/progression/test_direct_barbarian_progression.py` | `8e57c70be904bd284488f3a9a591c3eaaedb0c3aa9fa4bb2ac61abd78ee4df85` |

Status: `SLICE_3B_COMPLETE — READY_FOR_FINAL_TRIPLE_ACCEPTANCE`.

### 20.15 Slice 3B atomic Mindless Rage veto closure

The final ECS review proved that a lawful removal-declaration veto could leave
one or both pre-existing Charm/Fear conditions active after Rage committed.
Mindless Rage now treats those two exact conditions as one rules operation
using the condition system's existing prepare/cancel/commit tree seam.  Both
removal graphs are prepared under the accepted Raging COMPLETION fact before
either graph mutates state.  If either declaration is vetoed, every prepared
fact is canceled and both original condition and duration identities remain;
otherwise both graphs commit normally.  The already-committed Rage/Frenzy
action remains successful and reports the blocked purge explicitly.

This is family-local orchestration over the existing condition lifecycle.  It
adds no callback, transaction wrapper, manager, compatibility path, registry
scan, or new generic removal abstraction.

Validation:

| Gate | Result |
|---|---|
| complete direct/public/architecture Barbarian gate | `46 passed in 9.64s` |
| Barbarian action and SRD monster mechanics | `54 passed in 7.30s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notice only |

Final changed bytes:

| File | SHA-256 |
|---|---|
| `dnd/classes/rage.py` | `f1d879055725637b70f6ab45a826df45c883657e005dfebac28194f4562bb5e0` |
| `tests/progression/test_direct_barbarian_progression.py` | `9961f99ba3b43e8ffb2800bc5e1af2d3005642e3f566d1dacd70d8bd994a2482` |

Status: `SLICE_3B_FINAL_CANDIDATE — READY_FOR_EXACT_TRIPLE_REVIEW`.

## 23. Triple-review repair and exact refreeze

### 23.1 Superseded candidate

The first Slice 7 candidate frozen by manifest SHA-256
`7de3e61e0aa168eb0449d60700ae8ccb833287fc298dd686f94185328c22762e`
received `CHANGES_REQUESTED` from correctness, anti-slop, and ECS/import-DAG
review.  That manifest and its 932-node execution are retained above as
historical evidence but are not acceptance authority.

The bounded repair made the following concrete corrections:

- exact 27-point point-buy validation now uses the existing progression
  authority, and the Sorcerer premade uses the accepted Deception choice;
- starting torches are lit inside the unpublished aggregate, their provisional
  light installation publishes no standalone facts, and failed composition
  discards both item and light state without post-birth patching;
- an accepted active-child removal always retains a terminal level-completion
  fact even when a pre-completion observer raises after the irreversible child
  boundary;
- each origin/Fighter/Barbarian/Sorcerer reverse path validates every concrete
  receipt-owned edge before mutation.  It unregisters only modifiers and
  resource contributions still attached to their exact local owners; imported
  `from_target_*` references remain foreign-owned and are never treated as
  cleanup authority;
- Barbarian Rage/Reckless and Tiefling Darkness cleanup uses exact root-owner
  action UUIDs stored in closed receipts, not mutable semantic tags, action
  scans, or runtime type dispatch; and
- the existing neutral dependency contract now admits the exact
  `dnd.types.abilities` leaf.  The three pre-existing absent-`dnd.core.senses`
  server diagnostics remain deferred and unchanged.

No manager, controller, service, generic receipt interpreter, callback chain,
transaction wrapper, compatibility path, late import, reflective dispatch, or
second progression authority was introduced.

### 23.2 Revalidated maintained proof union

The union was reconstructed mechanically from the same accepted sets rather
than incremented from prose:

| Component | Nodes | Normalized SHA-256 |
|---|---:|---|
| frozen CR-0 evidence | 105 | `f689e92102b7a6e25c832cdc030d88618ab2048cd174e87869d76ed59cdcab33` |
| currently collectible CR-0 intersection | 66 | `1306ae58b993beea3ebb32d02db13ffee6554546e06374318624de21858d92a0` |
| surviving direct-item affected collection | 752 | `73369bd86de6b9064bdfbe54a38565cc68fe6d599834f3919de0fcb8e3e154c2` |
| exact direct-item successors | 25 | `f5ea8b49e99135bd432bf3bb586324c444637afdc05ae99244f18c6d996993cd` |
| exact direct-item anchors | 6 | `c56e51d5fd581a70dddd8c6cf4d0b1e0e07ca28e7303fe3f909d50caa6fd3d31` |
| inherited base after accepted exclusions | 794 | `413cbfd25a6af92eb8bf1b257e3b21db38341a49fa594cd7d569def5958b718e` |
| direct-character successors | 153 | `3ebc85041bc9bbb758a265c17115b9f3a9827307b5b56bf969043b09a4672a42` |
| final sorted unique union after three CR-7 exclusions | **944** | **`465a0bba87943279d1e6c95a63b33f453af550558dec2bb3ade3cdcc3b6bde77`** |

Exact execution: **944 passed in 310.64s**.

Additional gates:

| Gate | Result |
|---|---|
| complete repaired direct-character/public/architecture lane | `154 passed in 21.81s` |
| full architecture directory | `82 passed`, 3 unchanged deferred absent-`dnd.core.senses` server diagnostics |
| compile of all 87 changed existing/new Python files | exit `0` |
| repository `git diff --check` | clean; checkout normalization notices only |

### 23.3 Refrozen exact checkout envelope

The regenerated self-excluding manifest is
`DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_MANIFEST_2026-09-02.json`.
It contains 165 unique and current members: 94 production, 70 tests, and the
accepted implementation plan.  Every member status and content hash matches
the current checkout.

| Manifest fact | Refrozen value |
|---|---|
| normalized entry SHA-256 | `ab382ad7ba379a18b1f5946fbcfe017bd7785a816c8adc688e15394ed16d81b2` |
| manifest SHA-256 | `b22954e5ecb95b22000bb1b26fc8ce29d16ccc065da13237db7ca82144c5b0cc` |
| maintained node count/hash | `944` / `465a0bba87943279d1e6c95a63b33f453af550558dec2bb3ade3cdcc3b6bde77` |

Status: `SLICE_7_REFROZEN — READY_FOR_EXACT_TRIPLE_REREVIEW`.

## 26. Second review repair and exact candidate refreeze

The manifest frozen in Section 25 and every review attached to those bytes are
historical after two exact-candidate reviewers requested changes.  The rejected
manifest SHA-256 was
`b22954e5ecb95b22000bb1b26fc8ce29d16ccc065da13237db7ca82144c5b0cc`.
The anti-slop reviewer approved those older bytes; the correctness and ECS/DAG
reviewers each found one real failure, so none of the three prior verdicts is
used as approval for the current candidate.

### 26.1 Findings and bounded repairs

1. Root-owner preflight authenticated only a root behavior ID.  A replacement
   with the same UUID and behavior but a foreign provider/root binding could
   pass preflight and orphan active Tiefling Darkness, Barbarian Rage, or
   Sorcerer metamagic children.  Each family-local owner now compares the exact
   immutable `BehaviorBinding` it authored before reading or removing any
   owned runtime graph.  No generic cleanup interpreter, manager, callback,
   reflection, late import, or ownership index was added.
2. Aggregate `remove_last_class_level` could publish an active-child removal
   execution fact before validating the complete stored receipt.  Barbarian
   and Sorcerer active-child discovery now runs the same complete family-local
   receipt preflight first.  Corrupted ownership therefore rejects with zero
   emitted facts and zero mutation.

Public regressions substitute same-UUID foreign bindings in all three families
and corrupt an aggregate-removal receipt while an active child exists.  The
rejection proofs freeze the event cursor, class level, receipt, root action,
and active child unchanged.  The earlier ECS reviewer also independently
proved that a borrowed `from_target_static` modifier reference remains present
in the foreign value and registry after Fighter cleanup; cleanup continues to
traverse only the value's four locally owned channels.

### 26.2 Validation of the repaired bytes

| Gate | Result |
|---|---|
| four new exact regressions | `4 passed in 1.09s` |
| complete direct-character focused lane | `157 passed in 23.90s` |
| exact maintained union | `947 passed in 330.95s` |
| exact union identity | 947 nodes, normalized SHA-256 `f5475640f70d62097988b90cad87db949f8c81cf8b7f0324daf36136f9d74b93` |
| full architecture lane | `82 passed, 3 known deferred failures in 138.22s` |
| compileall (`dnd`, progression tests, architecture tests) | exit `0` |
| repository `git diff --check` | clean; normalization notices only |

The three architecture failures are unchanged and outside CR-4/CR-5: two
server cold-start paths and the world-contract leaf still import the absent
`dnd.core.senses`.  No server/transport stub or out-of-scope repair was added.

### 26.3 Current exact envelope

Final manifest:
`DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_MANIFEST_2026-09-02.json`.

| Manifest fact | Current value |
|---|---|
| production members | 94 |
| test members | 70 |
| document members | 1 |
| total members | 165 unique, 165 current, zero missing paths or hash mismatches |
| normalized entry SHA-256 | `6b3a9e14c778d0fb5b7ec54dfe185861fc6fd6853bc7168197cf4615fc652933` |
| manifest SHA-256 | `22f9a8d60825144642de2c8b5847af0ccbbce19f36ffe04045574ce15358a667` |

Status: `SLICE_7_SECOND_REFROZEN — READY_FOR_EXACT_TRIPLE_REREVIEW`.

## 21. Completed direct-character candidate

### 21.1 Slice 3C — Sorcerer and Draconic Bloodline

Sorcerer levels 1 through 20 and their reverse removal path now use direct,
source-owned grants.  The implementation preserves spellcasting capacity,
known spell sources, metamagic choices, sorcery points, Draconic ancestry,
resilience, elemental affinity, wings, and the accepted level/choice tables.
Runtime actions keep exact Entity-owned template identity.  Removal traverses
only the Sorcerer receipt's concrete owned edges; imported modifier references
are dropped without unregistering their foreign owners.

No character materializer, feature registry, generic grant interpreter, or
second action/spell authority was introduced.

### 21.2 Slice 4 — aggregate progression

The public progression boundary is procedural and stateless: resolve and
validate one level, install its concrete family grant, publish one narrow
level fact, and store the resulting closed family receipt on the Entity.
Removal performs the exact reverse owner traversal and publishes the matching
removal fact.  Multiclass order, ASI ownership, prepared-spell state, feature
toggle state, and hydration from semantic selections are covered directly.

Admission, handler, child-cleanup, and publication failures preserve the
pre-operation Entity state and exact registry identities.  Normal spell-slot
capacity releases only its own unused aggregate floors; spent slots still
clamp at zero, while pristine removal returns the exact registry baseline.

### 21.3 Slice 5 — direct construction and premades

`create_character(build, ...)` is the single construction path.  It resolves
the complete plain build before mutation, creates one provisional neutral
Entity, applies body/origin/ordered levels/prepared and toggle selections plus
direct item loadout, and composes that Entity exactly once.  Failure discards
the unpublished aggregate through existing concrete owner seams.

The four accepted premades are ordinary frozen build values passed through
that same function.  Character and creature identities are disjoint.  No
draft, revision, deployment, repository, schema digest, content-set hash, or
special premade materializer was added.

### 21.4 Slice 6 — hard cut and successor proofs

The legacy generic character materialization modules and their callable paths
are deleted.  Active gameplay imports no retired character module.  Ability,
skill, and save names have one dependency-leaf authority.  Character semantic
state and the four concrete receipt types remain data-only leaves.  Entity
stores state and exact receipts but does not own progression policy.

Obsolete tests were deleted only where direct successor proofs now cover their
behavior.  Retained Fighter Action Surge, Quickened Spell, item/proficiency,
birth chronology, and icon-evidence tests were migrated to the direct public
owners rather than relaxed or routed through compatibility code.

Authored encounter catalogs that still name deleted `creature.player.*`
factories are intentionally deferred to CR-7 scenario/deployment recovery.
No adapter was installed.  The three exact nodes omitted from this candidate
union are:

```text
tests/manual/test_84_generic_roster_duels.py::test_character_style_and_creature_rosters_share_one_assembler
tests/manual/test_191_authored_encounter_catalog.py::test_every_authored_encounter_prepares_through_canonical_assembler
tests/manual/test_191_authored_encounter_catalog.py::test_every_authored_spell_matrix_preserves_requested_runtime_spells
```

## 22. Slice 7 certification freeze

### 22.1 Maintained proof union

The final union is reconstructed mechanically from the collectible remainder
of the frozen CR-0 nodes, surviving direct-item affected modules, exact
direct-item successor/anchor nodes, and all direct-character successors, then
subtracts the accepted retired/current exclusions and the three explicit CR-7
scenario nodes.

| Component | Nodes |
|---|---:|
| frozen CR-0 evidence | 105 |
| currently collectible CR-0 intersection | 66 |
| surviving direct-item affected collection | 752 |
| exact direct-item new nodes | 25 |
| exact direct-item anchors | 6 |
| inherited reconstructed base after exclusions | 794 |
| direct-character successors | 141 |
| final sorted unique union after CR-7 exclusions | **932** |

Normalized final-union SHA-256 (sorted unique node IDs joined by `\n` with
one terminal newline):
`d5729a9810232722942b5de85d15ecc91cf4166b8ad0b31fbe054eaa2f183a96`.

Exact execution: **932 passed in 312.19s**.

### 22.2 Proportional and repository diagnostics

| Gate | Result |
|---|---|
| complete direct/retained CR-4/CR-5 lane | `372 passed in 110.62s` |
| direct-character successor collection | `141 tests collected` |
| architecture | `81 passed`, 4 exact unrelated failures |
| compile of changed production/test closure | exit `0` |
| repository/scoped `git diff --check` | clean; normalization notices only |
| repository collection diagnostic | `2219 tests collected`, 78 deferred/obsolete collection errors |

The four architecture failures are outside this cut: two import the absent
`dnd.core.senses` through server/world-contract paths, one old content-neutral
allowlist does not admit `dnd.types.abilities`, and one server spell-catalog
cold start reaches the same absent senses module.  The 78 repository
collection errors are dominated by deferred server/transport/persistence and
deleted legacy content authorities such as item bindings and old character
materialization.  They are diagnostic debt, not hidden inside the green
maintained union and not repaired by out-of-scope stubs.

### 22.3 Exact checkout envelope

Against checkout HEAD `ab56a24bf77fc79251e6505718119c38c4f32c8f`,
the frozen dirty candidate contains 163 paths: 92 production, 69 tests, and
the plan plus this mutable ledger.  There are 64 modified, 77 deleted, and 22
new paths.  The final manifest self-excludes itself and this ledger and records
every other changed path with status and content hash; deleted paths carry a
null hash.

Final manifest:
`DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_MANIFEST_2026-09-02.json`.

| Manifest fact | Frozen value |
|---|---|
| production members | 92 |
| test members | 69 |
| document members | 1 (accepted implementation plan) |
| total members | 162 unique, 162 current, zero hash mismatches |
| normalized entry SHA-256 | `0bc93d3dfba70c12898d42724d6fd44af421ac93efb721e9dda9b691b10f780d` |
| manifest SHA-256 | `7de3e61e0aa168eb0449d60700ae8ccb833287fc298dd686f94185328c22762e` |

Status: `SLICE_7_FROZEN — READY_FOR_EXACT_TRIPLE_REVIEW`.

### 20.16 Slice 3B condition-owned duration closure

The ECS review of the successful Mindless Rage path found that ordinary
Charmed and Frightened conditions left their exact Duration children in the
runtime registry after the conditions themselves were removed.  Duration is
an explicit field-owned child of every BaseCondition and is stamped with its
owning condition UUID at construction.  The existing base condition owner now
validates that exact edge and releases the duration in both provisional
discard and accepted cleanup.  Subclass runtime hooks remain responsible only
for their additional local mechanics; Mindless Rage never reaches into the
foreign condition graph.  The redundant Rage-family duration removals were
deleted.

The success proof now freezes both removed condition UUIDs and both owned
duration UUIDs as absent from the registry.  Either removal veto still
preserves both complete condition-duration graphs.

Validation:

| Gate | Result |
|---|---|
| complete direct/public/architecture Barbarian gate | `46 passed in 9.97s` |
| Barbarian/SRD condition and monster mechanics | `70 passed in 19.32s` |
| compile of the changed owner/proof closure | exit `0` |
| scoped `git diff --check` | clean; existing normalization notices only |

Final changed bytes:

| File | SHA-256 |
|---|---|
| `dnd/core/base_conditions.py` | `11494441a70c892db3cefa79f1e1a728214a70c8230bc2dabb165cf2f5b1154c` |
| `dnd/classes/rage.py` | `f161abea74afe1b436b21b2c57120b68aa8c66eac4c7275bd279cc86f075b19e` |
| `tests/progression/test_direct_barbarian_progression.py` | `7188c150931dc3415da35d17baedde52dfd675b23f4b8614a52ea4bc11f93c02` |

Status: `SLICE_3B_FINAL_CANDIDATE — READY_FOR_EXACT_TRIPLE_REVIEW`.

## 25. Final physical candidate status

The rejected historical freezes above are preserved for audit.  Section 23 is
the current certification record, and its manifest SHA-256
`b22954e5ecb95b22000bb1b26fc8ce29d16ccc065da13237db7ca82144c5b0cc`
freezes 165 exact members plus the green 944-node maintained proof union.

Status: `SLICE_7_REFROZEN — READY_FOR_EXACT_TRIPLE_REREVIEW`.

## 27. Current physical candidate status

Sections 23 and 25 are rejected historical freezes.  Section 26 is the current
certification record.  Its manifest SHA-256
`22f9a8d60825144642de2c8b5847af0ccbbce19f36ffe04045574ce15358a667`
freezes 165 exact members plus the green 947-node maintained proof union.

Status: `SLICE_7_SECOND_REFROZEN — READY_FOR_EXACT_TRIPLE_REREVIEW`.

## 28. Exact authored-root repair and third refreeze

The Section 26/27 candidate and all reviews attached to manifest SHA-256
`22f9a8d60825144642de2c8b5847af0ccbbce19f36ffe04045574ce15358a667`
are historical.  The ECS/DAG reviewer proved that a valid action from the same
family could replace the exact receipt-owned row while retaining its UUID:

- level-one Rage replaced by canonically bound Frenzy;
- Quickened Spell replaced by canonically bound Twinned Spell; and
- Draconic Presence `awe` replaced by canonically bound `fear`.

Each old validator accepted the family-wide binding and could remove the level
while leaving the original active child orphaned.  Barbarian and Sorcerer
validation now derive the exact expected action kind, provider, and Presence
mode from the closed receipt step plus its deterministic action UUID.  The
candidate object no longer chooses which family row is acceptable.  This is a
family-local correction in the existing owner preflight: no receipt schema,
generic interpreter, action index, manager, callback, transaction, reflection,
or new abstraction was added.

The ECS reviewer enumerated every root-owner receipt tuple.  Barbarian raging,
Sorcerer metamagic, and Sorcerer Draconic Presence were the only ambiguous
multi-kind/configured tuples.  Darkness, Reckless Attack, Elemental Affinity,
and Dragon Wings each have one concrete kind and retain their exact full
binding checks.

### 28.1 Validation

| Gate | Result |
|---|---|
| three legitimate wrong-row regressions | `3 passed in 0.69s` |
| complete direct-character focused lane | `160 passed in 24.69s` |
| exact maintained union | `950 passed in 331.06s` |
| exact union identity | 950 nodes, normalized SHA-256 `d2c69921efeb66772c76c5e0b13e43c42f2aab94dfafd3158dea57db997a213f` |
| full architecture lane | `82 passed, 3 unchanged deferred failures in 148.86s` |
| compileall (`dnd`, progression tests, architecture tests) | exit `0` |
| repository `git diff --check` | clean; normalization notices only |

The maintained union was mechanically reconstructed from 66 current CR-0
nodes, 752 surviving direct-item affected nodes, the 794-node inherited base,
and 159 direct-character successors, then had the three explicitly deferred
CR-7 scenario nodes removed.  A diagnostic 953-node invocation that omitted
that final documented subtraction was interrupted before certification and is
not evidence.  The 950-node execution above is the accepted lane.

The architecture failures are the same out-of-scope server/world-contract
imports of absent `dnd.core.senses`; no server or transport file was changed.

### 28.2 Current exact envelope

Final manifest:
`DND_CONTENT_RECOVERY_CR4_CR5_CHARACTER_IMPLEMENTATION_MANIFEST_2026-09-02.json`.

| Manifest fact | Current value |
|---|---|
| production members | 94 |
| test members | 70 |
| document members | 1 |
| total members | 165 unique, 165 current, zero missing paths or hash mismatches |
| normalized entry SHA-256 | `afe7f46ce6843a4f1944eff9ddec649a9fefebdde0b27d474b0f6d47b15cea36` |
| manifest SHA-256 | `d3c54617c67c362078bdc7127bac497956565c81b7ab832fa94862896ba2d4b6` |

Status: `SLICE_7_THIRD_REFROZEN — READY_FOR_EXACT_TRIPLE_REREVIEW`.

## 29. Exact final triple acceptance

No production, test, plan, or manifest byte changed after the Section 28
freeze.  All three independent reviewers evaluated the same exact candidate:

- manifest SHA-256
  `d3c54617c67c362078bdc7127bac497956565c81b7ab832fa94862896ba2d4b6`;
- pre-review-metadata ledger SHA-256
  `9bb6e2505635d419a5e13b0df1e3528fcde933413405cd92460bbd17218462eb`;
- 165 manifest members; and
- 950-node maintained union SHA-256
  `d2c69921efeb66772c76c5e0b13e43c42f2aab94dfafd3158dea57db997a213f`.

| Review | Verdict | Independent evidence |
|---|---|---|
| correctness | `APPROVE` | reconstructed and executed the exact union (`950 passed in 319.42s`); reproduced corrupted active-child receipt rejection, all three legitimate wrong-row substitutions, successful reverse cleanup, torch/light birth, exact point buy, terminal chronology, premade skill, and complete family validation |
| anti-slop / anti-OOP | `APPROVE` | 165/165 members exact; receipt-step plus deterministic-UUID checks are family-local and introduce no schema, catalog, interpreter, callback chain, transaction, manager/service/controller, reflection, compatibility path, test hook, or avoidable layer |
| ECS ownership / import DAG | `APPROVE` | all six foreign/wrong-row substitutions reject before mutation; borrowed `from_target` identity survives cleanup; receipts stay closed data; Entity remains composer/state owner; 224 modules, 1,452 edges, zero cyclic SCCs, zero nested imports |

The current manifest remains hash-exact after review.  The only non-green full
architecture diagnostics are the three unchanged, governed, out-of-scope
server/world-contract imports of absent `dnd.core.senses` recorded above.

Status: `CR4_CR5_COMPLETE — ACCEPTED`.
