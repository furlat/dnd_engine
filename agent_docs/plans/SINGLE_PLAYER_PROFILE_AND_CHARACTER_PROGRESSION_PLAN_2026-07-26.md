# Single-Player Profiles, Character Builds, Progression, Multiclassing,
# Respec, and Cleric

Date: 2026-07-26

Status: Phases 0–6 are implemented and frozen for frontend handoff as of
2026-07-27. Phases 7–9 and Follow-up F1 remain future work; this document
authorizes no compatibility implementation.

Implemented freeze checkpoint:

- one schema-2 build/revision/materialization path owns Fighter, Barbarian,
  Sorcerer, and every premade;
- the premade catalog includes the ordinary Fighter 2 / Sorcerer 3 Draconic
  Spellblade build and creates it through the same public request, SQLite
  revisions, deployment pin, and runtime materializer as a custom build;
- standalone profiles own one SQLite database, content-addressed portable
  replay files, durable local game history, exactly-once terminal settlement,
  lease release, and restart recovery;
- generated TypeScript creator, directory, progression, history, and replay
  contracts are the sole public SDK path;
- Cleric, the Druid NPC form slice, and generic action-presentation expansion
  are deliberately excluded from this freeze.

Rules baseline: SRD 5.1 class progression through character level 20, with the
explicit BG3-style character-building choices and selected SRD 5.2 half-caster
round-up policy listed below

Delivery order: foundations → Fighter → Barbarian → Sorcerer → cross-class gate
→ Cleric → cleanup; the effective-form NPC proof is the first bounded follow-up
before playable Druid

## 1. Outcome

This work produces one canonical character system shared by:

1. a local single-player profile stored in its own SQLite database;
2. the hosted/multiplayer directory, using the same repository and domain
   operations against deployment-owned SQL;
3. character creation from exact authored content definitions;
4. additive level-up, including multiclassing;
5. deterministic respec by rebuilding the structural character from level 1;
6. runtime materialization of the exact immutable character definition plus
   exact immutable holdings and loadout;
7. Fighter, Barbarian, and Sorcerer migrated away from one-shot entity
   factories;
8. Life Domain Cleric implemented as the first class authored directly in the
   new system.

The central model is:

```text
profile settings + earned level entitlement
                         |
                         v
immutable character definition revision
  - body/species/background
  - base ability allocation
  - ordered class-level ledger and choices
                         +
immutable character holdings revision
  - persistent item instances and exact recipes
                         +
immutable character loadout revision
  - prepared spells and persistent feature toggles
                         |
                         v
existing canonical character materializer
  + source-owned structural grant applier
                         |
                         v
runtime Entity + encounter-ephemeral state
```

There is one persistence and composition path. Premades become authored initial
build recipes; they do not remain an alternative character implementation.
Standalone and hosted modes use the same domain services; they differ only in
database placement, ownership authority, and deployment orchestration.

## 2. Hard constraints

### 2.1 Product constraints

- A local physical player profile owns one SQLite database.
- Replay bundles remain portable and downloadable, but storage reuses the
  existing content-addressed `GameArtifactStore` and `game_artifacts` rows.
  No second replay-specific file store or metadata table is added.
- A character's structural definition is separate from:
  - persistent holdings;
  - persistent mutable loadout such as prepared spells;
  - encounter damage, temporary hit points, conditions, spell-slot spending,
    resource spending, action economy, map position, and initiative.
- Canonical player characters use the product rule `0 HP -> DEAD`. Persistent
  player bodies do not opt into the engine's dormant death-save capability;
  AI scheduling, terminal encounter evidence, replay closure, and summary
  publication therefore share the same exact `DEAD` boundary.
- Loot settlement appends a holdings revision. It does not edit a structural
  definition revision.
- Preparing spells or changing a persistent opt-in feature appends a loadout
  revision. It does not edit class levels or holdings.
- Level-up and respec append structural definition revisions. They do not
  recreate starter equipment or overwrite holdings.
- A deployed character is pinned to exact definition, holdings, and loadout
  revisions. Production level-up/respec is rejected while an active deployment
  lease exists.
- Respec preserves identity, species, background, persistent holdings, earned
  total level, and history. It may replace the class-level ledger and the
  flexible ability/class choices described in section 6.
- The engine continues through level 20. BG3's level-12 product cap is not
  adopted.

### 2.2 Architecture constraints

- `Entity` and its component blocks remain class-feature agnostic.
- Dependency-neutral progression contracts live below `Entity`; concrete
  Fighter/Barbarian/Sorcerer/Cleric definitions live above it.
- No concrete class, condition, spell, item, or content-pack module may be
  imported by `Entity` or a low-level component.
- No function-local imports, `TYPE_CHECKING` import workarounds, or new circular
  dependencies.
- The content-pack cold-start import boundary remains the only audited dynamic
  import exception.
- We do **not** create a registry per content family or a global registry for
  numerical modifiers. Class/subclass/species/background/feature definitions
  enter the existing `FrozenContentRegistry`; typed read-only indexes and
  resolvers derive from that one authority. Grant appliers use existing
  modifier, action, resource, spell, handler, and condition APIs.
- Every class-derived contribution has a stable source/grant identity and can
  be removed without matching a display name or destroying the Entity.
- All game-state changes during play still flow through events. Build
  composition is cold/out-of-encounter structural materialization, not a
  gameplay shortcut.

### 2.3 Delivery constraints

- No `/v2`, legacy alias, old/new mode flag, or dual factory path ships.
- A phase removes its replaced path after all consumers have migrated.
- Each behavior change starts with a focused failing test.
- Every known open issue has an exact deterministic automated reproducer and,
  while intentionally open, a strict xfail tied to `KNOWN_ISSUES.md`.
- Cleric begins only after the three existing classes pass the new-system gate
  in section 13.

## 3. Current code: validated starting point

### 3.1 Persistence already worth keeping

The current directory implementation is a sound foundation:

- `server/game_directory/database.py` owns SQLite transactions using
  `BEGIN IMMEDIATE`, WAL configuration, a process lock, and query timing.
- `server/game_directory/migrations.py` currently creates principals,
  characters, immutable `character_definitions`, immutable
  `character_holdings_revisions`, deployment leases, games, memberships, and
  replay/artifact metadata.
- `server/game_directory/repository.py::create_character_with_revisions`
  atomically writes the character row, definition revision 1, holdings revision
  1, and both current heads. The new path generalizes this transaction to add
  loadout revision 1 and one additional current head.
- `append_character_holdings_revision` already demonstrates the required
  insert-plus-CAS pattern.
- update/delete triggers already protect immutable definition and holdings
  history.
- `tests/manual/test_173_character_revision_repository.py` covers migrations,
  immutability, stale heads, lease pinning, and transaction rollback.

This plan extends that implementation. It does not introduce a separate local
character repository or ORM.

### 3.1.1 Reuse boundary

The implementation extends the following existing owners instead of wrapping
or replacing them:

| Concern | Existing owner | Permitted extension |
| --- | --- | --- |
| progression tables | `dnd/core/progression.py` | add pure multiclass/rules evaluators |
| durable build DTOs | `dnd/core/content/durable_characters.py` | add schema-2 build/loadout models |
| content identity and registration | `FrozenContentRegistry`, `ContentDeclaration`, `ContentSystemRuntime` | add typed definition payloads and derived indexes |
| deployment materialization | `dnd/content_system/character_materialization.py::materialize_character` | invoke structural grant application before existing holdings hydration |
| persistence/CAS | `GameDirectoryRepository` | one generalized revision-bundle transaction |
| runtime mechanics | existing `ModifiableValue`, `BaseBlock`, `ActionEconomy`, `Health`, `Equipment`, `SpellcastingBlock` | source ownership and the smallest missing exact-ID APIs |
| game history and replay | existing games, summaries, replay builders, `GameArtifactStore`, `game_artifacts` | local execution kind and transport-neutral terminal publication |
| character HTTP operations | character methods currently embedded in `GameGatewayService` | extract one small shared service; gateway delegates to it |

The following are explicitly forbidden in this tranche: a second materializer,
class/species/background registries, a replay store, a normal spell-slot
engine, a universal contribution interpreter, a generic uninstall dispatcher,
or a standalone local game-history subsystem.

### 3.1.2 Complexity budget

Every implementation PR/chunk must answer these checks:

1. **Existing owner:** name the current object/table/service that owns the
   concern and extend it unless its invariant is demonstrably wrong.
2. **One authority:** a cache/index/read DTO may derive from authority but may
   not accept independent writes or registration.
3. **Concrete consumer:** a new runtime abstraction must have a delivered
   consumer in that phase. Future requirements stay as typed acceptance notes,
   not empty tables, SDK unions, services, or Entity fields.
4. **Narrow surface:** prefer one exact missing operation
   (`unregister_action_by_uuid`, resource contribution handle, source-aware
   casting) over a universal manager.
5. **No capability loss:** deferral names the owning future tranche and keeps
   its semantic acceptance tests in section 15; it does not discard the rule.
6. **Measured extraction:** split a file/service only to share an existing
   operation across local/hosted composition or after a measured size/import/
   performance problem—not merely to add a layer.
7. **Deletion proof:** when the canonical path lands, repository search and
   focused tests prove the replaced factory/route/CAS algorithm has no
   production consumer.

### 3.2 Structural definition gap

`dnd/core/content/durable_characters.py::CharacterDefinitionRevision` schema 1
currently authenticates:

- one whole `creature_recipe`;
- optional `premade_id`;
- one `content_set_digest`.

It cannot represent species, background, point buy, an ordered class-level
history, class choices, respec, or a separate persistent mutable loadout.
`character_materialization.py` therefore materializes a finished creature
recipe rather than composing a build.

### 3.3 One-shot class factories

`fighter_factory.py`, `barbarian_factory.py`, and `sorcerer_factory.py`
currently construct finished level-N entities. They independently set base
scores, saving throws, skills, proficiency bonus, hit dice, appearance,
equipment, resources, conditions, features, and actions.

Their feature implementations are often reusable. Their ownership model is not:

- class level is implicit in factory control flow;
- no ordered character-level ledger exists;
- first-class versus added-class proficiencies are not represented;
- grants are not uniformly source-owned or reversible;
- Sorcerer writes a single finished spell-slot table;
- a single `SpellcastingBlock.spellcasting_ability` cannot represent a
  Wisdom/Charisma multiclass;
- name-based action/resource cleanup cannot safely remove one provider while
  preserving another provider of the same feature.

### 3.4 Generic block gaps

The following generic gaps must be fixed before class migration:

- skill and saving-throw proficiency are booleans rather than source sets;
- weapon, armor, and shield proficiency are not an authoritative generic
  capability surface;
- attack math currently assumes proficiency instead of asking whether the
  selected weapon is proficient;
- unarmored defense is represented as one mode rather than source-owned AC
  formula candidates;
- hit-dice blocks can model mixed dice, but `ignore_first_level` must be driven
  by the ordered first character level so only one die is maximized;
- actions need exact-UUID removal and resources need source contribution IDs;
- spells require per-source casting ability and availability;
- skills/saves require source-aware proficiency without replacing their current
  event path;
- first-four once-per-turn usage requires a real turn execution identity;
- class feature stacking policies such as Extra Attack and Channel Divinity
  must be explicit rather than accidental name collisions.

Generic arbitrary ability/tool/instrument checks and full creature-form
replacement are real future gaps, but no first-four runtime API is added for
them. Bard/Rogue or an implemented check spell owns the former; the F1 Druid
NPC owns the first concrete body-replacement seam.

### 3.5 Local profile gap

The multi-game gateway currently owns `DirectoryDatabase`; standalone
`server.event_server` reports that the directory is unavailable. Consequently
the repository works, but local single-player mode cannot yet use it as a
profile service.

## 4. Exact rules policy

### 4.1 Sources and precedence

1. SRD 5.1 is authoritative for class and Life Domain Cleric progression
   through level 20:
   [official SRD 5.1 PDF](https://media.dndbeyond.com/compendium-images/srd/5.1/SRD_CC_v5.1.pdf).
2. The default profile deliberately adopts only SRD 5.2's more generous
   Paladin/Ranger multiclass slot rounding, with the 5.1 feature-start guard
   defined in section 4.8:
   [official SRD 5.2 PDF](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf).
   This does not import revised 2024 class tables or feature timing.
3. BG3-inspired creation, multiclass, and respec rules are explicit product
   choices, not claims that BG3 is the tabletop rules authority. Research
   references:
   [Character Creation](https://bg3.wiki/wiki/Character_Creation),
   [Point Buy](https://bg3.wiki/wiki/Point_Buy),
   [Classes and multiclassing](https://bg3.wiki/wiki/Classes),
   [multiclass spell slots](https://bg3.wiki/wiki/Spells), and
   [Withers/respec](https://bg3.wiki/wiki/Withers).
4. Where a rule requires a DM, unconstrained natural language, downtime,
   economy, travel, or a system not implemented here, the Cleric adjudication
   ledger must define a deterministic adaptation or explicitly defer it. There
   are no silent approximations.
5. Existing engine behavior is not authoritative merely because it exists. A
   parity test remains only when it protects the selected policy.

### 4.2 Profile rules setting

Schema stores a required profile setting:

```text
permissive_multiclass_prerequisites: bool = true
multiclass_slot_rounding_policy:
  "srd_5_2_round_up" | "srd_5_1_round_down"
  = "srd_5_2_round_up"
```

The first setting controls only entry/exit ability-score prerequisites. The
second controls only the half-caster contribution described in section 4.8.
Do not use a field named `bg3_multiclass_rules` for both unrelated decisions.

For this delivery the prerequisite values have exact meanings:

| Behavior | permissive `true` (default) | permissive `false` |
| --- | --- | --- |
| Multiclass ability prerequisites | ignored | SRD prerequisites enforced |
| Point buy | 27 points, 8–15 before bonuses | same |
| Flexible creation bonus | one +2 and one +1 on distinct abilities | same product rule |
| HP after level 1 | fixed class average | fixed class average |
| Character-level cap | 20 | 20 |
| Respec | allowed by profile policy | allowed by profile policy |

Both settings are pinned into every definition revision's `ruleset_digest`.
Changing profile settings affects new character creation only. An existing
character continues to level and respec under its pinned ruleset. Moving an
existing character to different settings requires a separate explicit
ruleset-migration preview/commit bound to both old and new ruleset digests; that
operation is deferred and is never an implicit side effect of level-up/respec.

If supporting strict prerequisites or round-down slots would materially delay
the first cut, the schema still stores both values but creation rejects the
unsupported value with a precise policy error until its matrix tests are
present. It must never silently behave as the default.

### 4.3 Ability scores

Creation uses:

- six base scores initialized at 8;
- 27 point-buy points;
- allowed pre-bonus range 8–15;
- costs: 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9;
- one +2 and one +1 allocated to distinct abilities;
- resulting creation maximum 17;
- species does not own fixed ability increases;
- automatic species/class modifiers are shown separately from the player's
  allocation, never baked into an unexplained total.

Level-up ASI choices are:

- +2 to one ability; or
- +1 to two distinct abilities; or
- one implemented feat;
- final normal maximum 20 unless a specific authored feature says otherwise.

Class ASI levels:

| Class | Class levels |
| --- | --- |
| Fighter | 4, 6, 8, 12, 14, 16, 19 |
| Barbarian | 4, 8, 12, 16, 19 |
| Sorcerer | 4, 8, 12, 16, 19 |
| Cleric | 4, 8, 12, 16, 19 |

### 4.4 Species and background

The SRD playable species set for the first complete catalog is Dragonborn,
Dwarf, Elf, Gnome, Half-Elf, Half-Orc, Halfling, Human, and Tiefling, with exact
species-variant/ancestry choices where the SRD defines them.

`CreatureType` remains a mechanical taxonomy (`humanoid`, `undead`, etc.); it
is not reused as character species identity.

Species definitions may grant:

- creature type and size;
- movement and senses;
- languages;
- proficiencies;
- traits, actions, reactions, resistances, and spells;
- typed choices;
- presentation/body parameters;
- level-gated grants.

Background supplies its exact skill/tool/language/equipment grants and authored
presentation. Species, species variant, background, and species-specific choices are
fixed during ordinary respec. A future full character rebuild may explicitly
allow changing them, but that is a different operation.

### 4.5 First class versus added class

The ordered class-level ledger makes the first class unambiguous.

- The first entry grants the class's initial saving throws and full initial
  proficiency package.
- The first character level receives maximum class hit die + Constitution.
- Adding a new class later grants only the exact multiclass proficiency package.
- Total character level, not class distribution, determines proficiency bonus
  and cantrip scaling.
- Class level determines that class's feature levels, ASIs, spell
  learn/prepare ceiling, and class-specific resources.

### 4.6 Hit points and hit dice

Fixed HP:

| Class | Hit die | Character level 1 when first class | Later level in class |
| --- | ---: | ---: | ---: |
| Fighter | d10 | 10 + CON | 6 + CON |
| Barbarian | d12 | 12 + CON | 7 + CON |
| Sorcerer | d6 | 6 + CON | 4 + CON |
| Cleric | d8 | 8 + CON | 5 + CON |

The character owns one hit die for each class level. Constitution modifier is
applied per total character level, so an ability change during respec or ASI
recomputes maximum HP consistently. Current HP is encounter state and is never
written into the definition.

Only class-level ledger ordinal 1 receives the maximum first die. A later
multiclass's first class level receives the fixed later-level value.

### 4.7 Proficiency and stacking

- Proficiency bonus is derived from total character level using the one SRD
  table.
- Each skill/save/equipment proficiency stores a set of source grant IDs.
  Removing one source does not remove another source.
- Ability-check proficiency is a source-owned multiplier/capability, not a
  boolean on Skill. Partial proficiency, full proficiency, and Expertise
  compete under the resolver below; they never add.
- Extra Attack is a ranked non-additive feature family: among the grants whose
  typed applicability matches the current Attack action/weapon/body tags, use
  the highest `attacks_per_attack_action`. Class values never add.
- Unarmored Defense is first-acquired/exclusive under SRD multiclassing. A
  later class does not grant a second Unarmored Defense formula to compare or
  stack. Armor, natural armor, Mage Armor, Draconic Resilience, and other AC
  calculations remain separately typed formula candidates as their own rules
  require.
- Channel Divinity is one cross-class capability family. Another class adds its
  exact effect options but does not grant another use merely because the
  feature was gained again. Total capacity is the greatest explicit per-class
  capacity entitlement, not a sum: Cleric 6/Paladin 4 has the union of both
  classes' options and two total uses. Every option preserves its provider
  source and therefore its own ability/DC.
- Duplicate action/spell availability from different providers is retained as
  exact provider evidence when its casting ability, resource, or removal
  semantics differ.

### 4.7.1 Authored feature-combination groups

Do not infer combination behavior from a display name or from “all modifiers of
this type.” Dependency-neutral rule primitives define a small closed set of
combination policies:

| Core combination group | Policy | Meaning |
| --- | --- | --- |
| `extra_attack` | `highest_applicable_rank` | one Attack action uses the greatest matching attack-count grant |
| `unarmored_defense` | `first_acquired_exclusive` | only the earliest class-level grant installs its formula |
| `channel_divinity` | `union_options_highest_capacity` | options combine; use capacity is the greatest explicit class-level capacity, never a sum |
| `fighting_style_choice` | `unique_choice_across_sources` | gaining another choice cannot select the same style twice |
| `ability_check_proficiency` | `strongest_applicable_multiplier` | partial sources compete; full beats partial; Expertise reaches 2× only over proficiency |
| `normal_spellcasting` | `aggregate_caster_level` | derive one normal slot pool, retain per-source spells/ability |
| `pact_magic` | `separate_pool_cross_castable` | future Warlock pool stays separate but legal spells may use either pool |
| `same_named_continuous_effect` | `nonstacking_strongest` | same rule effect does not add to itself unless its definition says so |

Each relevant class-feature definition carries an exact core
`combination_group_ref`, rank/capacity contribution, and acquisition ordinal.
The composer produces a typed resolution report showing active, suppressed,
and combined grants. Content packs may bind to installed core groups; they may
not invent executable policy strings in durable character data.

Mechanics that merely produce additional attacks by another action/bonus
action/reaction—Haste's restricted action, Monk Martial Arts/Flurry, Berserker
Frenzied Strike, opportunity attacks—do **not** belong to `extra_attack`.
Their own action economy and once-per-turn/resource rules remain distinct.

The grant used by the resolver is explicit:

```text
AttackMultiplicityGrant
  grant_id
  combination_group_ref
  attacks_per_attack_action
  applicability:
    ordinary_attack
    required_weapon_tags
    required_body_tags
    required_action_refs
```

Ordinary Fighter/Paladin/Ranger/Monk Extra Attack grants match ordinary Attack.
Future Thirsting Blade matches only the pact weapon. A creature's authored
Multiattack action remains a distinct action and never enters this family.

First-release proficiency resolution is one source set over exact subjects:

```text
ProficiencyApplication
  grant_id
  subject_ref                 # skill/save/weapon/armor/shield in tranche one
  mode: half_round_down | half_round_up | full | expertise
```

No applicable source yields `0×`; partial sources compete rather than add; full
proficiency defeats partial proficiency; Expertise yields `2×` only over full
proficiency; duplicate Expertise remains `2×`. Existing `SkillCheckEvent` and
`SavingThrowEvent` remain the execution paths.

When Bard/Rogue or a delivered spell first needs arbitrary checks, extend the
existing D20/SkillCheck event hierarchy with one typed `AbilityCheckEvent` and
adapt initiative/Counterspell to it. Do not create a parallel roll resolver
subsystem now.

### 4.8 Multiclass spell slots

Normal spell slots form one shared pool derived from Effective Spellcaster
Level (ESL).

Contribution categories are typed:

- full caster: class level;
- half caster: one-half class level;
- third caster: one-third class level;
- non-caster: zero;
- pact caster: separate pool and not implemented by the first four classes.

Every class definition also declares
`spellcasting_feature_class_level`. A caster contribution is zero
until that class has actually gained Spellcasting. Paladin 1 and Ranger 1
therefore grant no slots; their half-caster contribution begins at class level
2. This start gate applies before any single-class rounding rule.

First count normal `Spellcasting` sources, excluding Pact Magic. If exactly one
class has Spellcasting, use that class's own slot table regardless of whether
the character also has non-caster classes. A Paladin 3/Fighter 2 therefore
retains the Paladin 3 slot table; strict multiclass contribution rounding does
not reduce it. Only a character with Spellcasting from two or more classes uses
the combined ESL algorithm.

For two or more Spellcasting classes when
`multiclass_slot_rounding_policy="srd_5_2_round_up"`:

1. sum every full-caster class level;
2. exclude every half-caster class that has not reached its declared
   `spellcasting_feature_class_level`;
3. sum the class levels of all remaining half casters, divide that subtotal by
   two, and round that subtotal up once;
4. exclude every third-caster class that has not gained its Spellcasting
   feature, sum the remaining third-caster levels, divide that subtotal by
   three, and round that subtotal down once;
5. add those three integer contributions to obtain ESL.

This deliberately adopts the more generous SRD 5.2 Paladin/Ranger rounding
direction without silently adopting the entire revised 2024 class progression.
SRD 5.2 gives Paladin and Ranger Spellcasting at class level 1; our planned
Paladin and Ranger remain SRD 5.1-shaped and gain it at level 2. The explicit
feature-start gate prevents a one-level non-casting dip from manufacturing
slots.

The half-caster subtotal is rounded once, not once per class. Thus Paladin 3 /
Ranger 3 contributes `ceil((3 + 3) / 2) = 3`, not 4. This is our explicit
hybrid product policy; it avoids a double-rounding exploit while retaining the
SRD 5.2 odd-level generosity. Paladin 1 / Ranger 1 still contributes zero
because neither source has gained Spellcasting.

For two or more Spellcasting classes when
`multiclass_slot_rounding_policy="srd_5_1_round_down"`, use the same aggregate
algorithm but round the eligible Paladin/Ranger subtotal down. Eligible
third-caster levels form their own subtotal and also round down once. This is
the plan's normative, tested interpretation of the SRD 5.1 direction; it does
not pretend the source resolves every multiple-half-caster parenthesization.
Keep the same
feature-start gate so an implementation cannot derive slots from a source that
has no Spellcasting feature.

The rules authority for this selected difference is documented in the
adjudication ledger:

- [SRD 5.2 multiclass Spell Slots](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character#Spellcasting)
  says to count half the levels in Paladin and Ranger and round up;
- [SRD 5.1 multiclass Spell Slots](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/customization-options#Spellcasting)
  says to round those levels down.

Each casting class separately controls:

- spellcasting ability;
- cantrips known;
- spells known or prepared;
- maximum spell rank learnable/preparable from that class;
- always-prepared/domain spells;
- replacement rules;
- ritual-casting eligibility.

A shared slot of a higher rank permits upcasting; it does not allow learning or
preparing a spell above the individual class's ceiling.

Required example:

```text
Sorcerer 3 / Cleric 3
ESL = 6
slots = 4×L1, 3×L2, 3×L3
Sorcerer source ability = CHA, max known rank = 2
Cleric source ability = WIS, max prepared rank = 2
L3 slots may upcast those spells but do not unlock L3 class spells
```

Required half-caster boundary examples:

```text
Round-up, Paladin 1                         -> half subtotal 0 -> ESL 0
Round-up, Paladin 2                         -> ceil(2 / 2) = ESL 1
Round-up, Paladin 3                         -> ceil(3 / 2) = ESL 2
Round-up, Paladin 3 / Ranger 3              -> ceil(6 / 2) = ESL 3
Round-up, Sorcerer 3 / Paladin 3            -> 3 + ceil(3 / 2) = ESL 5
Round-down, Sorcerer 3 / Paladin 3          -> 3 + floor(3 / 2) = ESL 4
Round-down, Paladin 3 / Fighter 2           -> sole Paladin table (ESL-equivalent 2)
Round-down, Paladin 3 / Ranger 3            -> floor((3 + 3) / 2) = ESL 3
Round-up, Paladin 1 / Ranger 1 / Sorcerer 1 -> 0 + 0 + 1 = ESL 1
```

Cantrips scale from total character level. Spell attacks and save DCs resolve
through the exact `SpellcastingSourceId` carried by the action.

### 4.9 Respec policy

Ordinary respec:

- preserves character ID, display name, owner, species/species variant, background,
  species/background choices, appearance/body choices, holdings, earned total
  level, and all old immutable revisions;
- returns the build to one level in its selected first class;
- reallocates point buy and flexible +2/+1;
- rebuilds the entire ordered class-level ledger up to the same earned level;
- allows class, subclass, skill, spell, metamagic, fighting-style, ASI, and feat
  choices to change;
- revalidates all choices against the exact pinned content set and ruleset;
- appends one new definition revision only when the final build is valid.

No partial respec becomes visible. A canceled or invalid respec writes nothing.
Respec never sells, duplicates, deletes, or restores equipment.
Future Wizard structural spellbook choice slots are the sole planned
holdings-reconciliation exception described in section 6.5; copied entries and
unrelated items remain preserved.

## 5. Dependency-neutral contracts

Do not create a `dnd/core/progression/` package: the repository already owns
`dnd/core/progression.py`, including the full-caster slot table and proficiency
helpers. Extend that leaf with pure rules calculations only. Put immutable
Pydantic build, choice, prerequisite, class/species/background definition, and
loadout contracts beside the existing character contracts in
`dnd/core/content/durable_characters.py`, splitting that file later only if
measured size or import cost justifies it.

Add only the durable build identities that cross the persistence boundary in
the first release:

```text
ClassLevelId
GrantId
SpellcastingSourceId
```

Runtime resources, Armor Class formulas, hit dice, actions, modifiers, and
turn executions already use exact UUID identity. Keep those UUIDs in runtime
receipts/events instead of introducing parallel one-field wrapper models.
`Encounter` creates one opaque UUID per actual turn execution and every child
event inherits it.

Do not add `SpellSlotPoolId` yet. The first four classes share only the existing
normal slots. Pact pool identity enters with Warlock, when two pools exist.

These leaves may import only dependency-neutral enums/value objects and content
identity contracts. They never import Entity, concrete conditions/actions/
spells, content packs, repositories, or server code.

The prerequisite expression tree is data, not an executable callback. Its
closed leaves initially cover:

```text
all_of | any_of | not
class_level(class_ref, minimum)
total_character_level(minimum)
ability_score(ability, minimum)
has_feature(feature_ref)
knows_spell(spell_ref)
selected_boon(boon_ref)
bound_item_capability(capability)
effective_body_capability(capability)
```

This is sufficient for ordinary multiclass gates, future invocation
prerequisites, and creator availability without serializing Python paths or
teaching repositories about concrete classes. Future leaves such as
`bound_item_capability` or `effective_body_capability` enter only with the
class that executes them; they are not part of the first SDK union.

Extend `ContentDefinitionKind` with:

- `CLASS`;
- `SUBCLASS`;
- `SPECIES`;
- `SPECIES_VARIANT`;
- `BACKGROUND`.

Keep `CLASS_FEATURE` for independently identifiable level grants. Do not encode
these identities as Python module/class paths.

Definitions use one new general typed-definition mode on the existing
`ContentDeclaration`, enter the existing `FrozenContentRegistry`, and resolve
through the existing `ContentSystemRuntime`. Small cached per-kind indexes are
read-only derivatives of that registry, never new registration authorities.
Extend existing `ContentDependency` relations for class→feature→spell/action/
condition closure rather than creating a progression dependency graph.

Class-granted runtime behavior reuses the existing `BehaviorBinder` and
`AuthoredBehaviorAttribution`:

```text
definition_ref  = granted action/condition/reaction
provided_by_ref = exact class-feature ref
origin_root_ref = absent unless a real durable constructible root exists
```

Do not introduce class-specific attribution unions. Before adding the new
definition kinds, hard-cut duplicate transport copies of dependency-neutral
`ContentRef`/`ContentRecipePresetRef` to their canonical leaf types and move
`SafeContentPresentationRef` beside the content presentation descriptor that
authenticates it.

## 6. Character definition schema 2

### 6.1 Canonical shape

Add `CharacterDefinitionRevisionV2`; do not mutate the meaning of schema 1:

```text
CharacterDefinitionRevisionV2
  character_id: UUID
  schema_version: Literal[2]
  definition_revision: int >= 1
  body_recipe: ContentRecipe[CREATURE]
  species_ref: ContentRef[SPECIES]
  species_variant_ref: ContentRef[SPECIES_VARIANT] | null
  background_ref: ContentRef[BACKGROUND]
  immutable_origin_choices: tuple[BuildChoiceSelection, ...]
  appearance: CharacterAppearanceSelection
  base_ability_scores: AbilityScoreAllocation
  flexible_ability_bonuses: FlexibleAbilityBonusSelection
  class_levels: tuple[ClassLevelEntry, ...]
  premade_id: namespaced string | null
  earned_character_level: int
  content_set_digest: sha256
  ruleset_digest: sha256
  definition_digest: sha256 of every field above
```

The exact discriminated union of schema 1 and schema 2 is used at the storage
boundary. Runtime materialization rejects schema 1 after migration completion;
there is no indefinite dual behavior.

### 6.2 Ordered class-level ledger

```text
ClassLevelEntry
  character_level: int                 # 1..earned_character_level
  class_ref: ContentRef[CLASS]
  resulting_class_level: int
  subclass_ref: ContentRef[SUBCLASS] | null
  choices: tuple[BuildChoiceSelection, ...]
```

Validation proves:

- character levels are contiguous from 1;
- resulting class level equals the count of prior/current entries for that
  class;
- subclass appears exactly when required and remains stable thereafter;
- required choices occur once and only once;
- no choice is accepted before its defining level;
- a class or subclass ref belongs to the pinned content set;
- total ledger length equals `earned_character_level`;
- every selected spell/feature/feat is allowed by its exact definition;
- the digest authenticates ordered choices, not only the final derived totals.

The order is semantically important for first-class proficiencies, first-level
HP, per-level grants, and deterministic reconstruction.

### 6.3 Typed choices

Use a closed discriminated union, including at least:

- `ClassSkillChoice`;
- `StartingProficiencyChoice`;
- `FightingStyleChoice`;
- `SubclassChoice`;
- `CantripChoice`;
- `SpellKnownChoice`;
- `SpellReplacementChoice`;
- `MetamagicChoice`;
- `ElementalAncestryChoice`;
- `AbilityScoreImprovementChoice`;
- `FeatChoice`;
- `StartingEquipmentPackageChoice`.

The first SDK union contains only choices exercised by the delivered classes,
species, backgrounds, and generic feats. Future `ExpertiseChoice`,
`ToolProficiencyChoice`, `MusicalInstrumentProficiencyChoice`,
`MagicalSecretsChoice`, `SpellbookSpellChoice`, `SpellMasteryChoice`,
`SignatureSpellChoice`, invocation/boon/arcanum choices, and Druid circle/land
choices remain requirements in section 15. Add them through the deliberate
contract revision for their class tranche; do not freeze unused variants into
the first SDK.

Each choice carries exact `ContentRef` values where authored content is
selected. Display names and semantic keys are never identity.

Automatic grants are not stored as pretend choices. They are re-derived from
the pinned definitions and shown beside choices in preview responses.

Prepared-spell selection is deliberately absent from the structural union. It
belongs to `CharacterLoadoutRevision` below.

### 6.4 Persistent level authority

Do not infer earned level from the mutable build ledger alone. Store an
append-only/idempotent advancement authority, for example:

```text
character_advancement_awards
  award_id
  character_id
  level_delta
  source_kind
  source_id
  created_at
```

`earned_character_level` in the authenticated definition must equal the
authoritative award total. Creation grants level 1. Until XP/endgame rewards
exist, a developer/manual award operation may add levels, but it must be
explicit, idempotent, and separate from choosing the class level.

This prevents respec, retries, or a forged client build from minting levels.

### 6.5 Character loadout revision

Prepared spells and persistent opt-in feature preferences need their own
immutable stream:

```text
CharacterLoadoutRevisionV1
  character_id
  schema_version: Literal[1]
  loadout_revision
  based_on_definition_revision
  prepared_spells:
    tuple[PreparedSpellSourceLoadout, ...]
      spellcasting_source_id
      spell_refs
  feature_toggles:
    tuple[FeatureToggleSelection, ...]
      feature_ref
      enabled
  loadout_digest
```

Rules:

- Sorcerer known spells remain structural definition choices.
- Cleric's available spell entitlement is derived from Cleric level/content;
  the chosen prepared subset lives here.
- Domain spells are derived always-prepared grants and are not duplicated in
  the loadout.
- Cantrips are structural known choices, not prepared loadout.
- A loadout pins the definition revision against which it validated.
- Level-up/respec must atomically write a replacement loadout when the old one
  becomes invalid; valid existing selections are preserved where possible and
  every removal is shown in preview.
- Preparing spells appends only a loadout revision with CAS.
- Deployment pins definition, holdings, and loadout heads.
- Runtime spent slots and temporary feature-use state are not loadout.

Future Wizard support adds `active_spellbook_item_id` in the contract revision
that delivers Wizard and uses a physical holdings-owned spellbook:

```text
SpellbookDurableState
  character_item_id
  entries:
    tuple[SpellbookEntry, ...]
      spell_ref
      provenance_kind:
        wizard_level_choice_slot | copied_during_play | reconstructed_prepared
      source_choice_slot_id: stable ID | null
  digest
```

Level-derived entries use stable structural choice-slot IDs (six at Wizard 1,
two per later Wizard level). Copied entries are adventure-acquired holdings and
survive respec. Respec may reconcile only entries owned by removed/replaced
structural slots; unrelated holdings and copied entries remain byte-identical.
Respeccing away from Wizard leaves the physical book and copied contents owned
but unusable. Book loss prevents preparation and spellbook ritual access. The
loadout selects the active book; the structural definition never silently
recreates copied spells.

Add an independent profile setting:

```text
spell_preparation_policy: "long_rest" | "out_of_combat"
```

Default this first release to `"long_rest"` to preserve SRD behavior.
Neither multiclass profile setting silently alters it. Under `long_rest`, a
deployed adventure must possess an explicit post-long-rest preparation
entitlement.
Under `out_of_combat`, a safe non-encounter/non-threatened state may append the
loadout. Both policies use the same validator and revision stream.

### 6.6 Deferred character knowledge/unlock revision

Durable non-item knowledge is a valid future concern, but none of Fighter,
Barbarian, Sorcerer, Cleric, premade migration, or the fixed-form Druid NPC
acquires it. The first release therefore does **not** create, pin, route, or
emit an empty knowledge stream.

The first playable feature that acquires forms/lore/unlocks adds an immutable
`CharacterKnowledgeRevision` using the same revision-bundle CAS primitive. It
will carry exact content refs, acquisition provenance, and an authenticated
content-set digest; it will survive respec and remain separate from physical
Wizard spellbook entries. This preserves the capability without paying a
fourth-head tax on every current character and deployment.

### 6.7 One-time schema-1 migration

Schema 1 is migration input, not a forever runtime union:

1. an offline/audited migration command reads each canonical schema-1 head;
2. its exact `premade_id` resolves to an installed authored
   `CharacterBuildV2` seed;
3. the command proves the old creature recipe and premade mapping are the
   expected authenticated pair;
4. it appends schema-2 definition revision `current + 1`;
5. it creates loadout revision 1 from the authored initial loadout;
6. it preserves the holdings head unchanged;
7. it CAS-advances definition/loadout heads and records a migration
   receipt;
8. unknown premades, digest mismatch, missing content, or noncanonical legacy
   rows fail with a report and no partial writes.

After all profile DBs migrate:

- production materialization accepts schema 2 only;
- schema-1 models remain only in the offline migration reader until the
  supported migration window closes;
- rebuild the SQLite `characters` table to remove the stale physical
  `preset_configuration_id` legacy-backfill column;
- delete migration-only runtime branches and generator exports;
- retain immutable old definition JSON for audit/history.

## 7. Profile persistence

### 7.1 Physical local layout

Use safe server-owned UUID paths:

```text
.runtime/profiles/<profile_id>/
  profile.sqlite3
  artifacts/
    sha256/<digest-prefix>/<digest>.json
  exports/
```

- The browser never submits a filesystem path.
- `profile_id` is a launcher/storage handle and equals the selected local human
  `principal_id`; it is not a second SQL identity or a new `profiles` table.
- A small local-only `LocalProfileManager` allocates/opens validated UUID
  directories and enforces exactly one owning human principal in each local
  DB. A directory scan or non-authoritative manifest is sufficient for listing.
- SQLite contains exactly one local player identity plus its characters,
  settings, game/replay metadata, and durable transactions.
- Hosted deployments continue to use the deployment's shared SQL database and
  principal/tenant ownership checks.
- SQLite is not copied into the game worker. Workers receive pinned definition,
  holdings, and loadout revisions through the existing deployment boundary.
- The existing `GameArtifactStore` is rooted at `artifacts/`. Export/download
  may give a replay a user-facing `.ndreplay` name without changing the
  canonical digest-addressed stored object.

### 7.2 New tables

Add forward-only migrations for:

```text
profile_settings
  owner_principal_id PK/FK principals
  permissive_multiclass_prerequisites BOOLEAN NOT NULL DEFAULT 1
  multiclass_slot_rounding_policy TEXT NOT NULL DEFAULT 'srd_5_2_round_up'
  allow_respec BOOLEAN NOT NULL DEFAULT 1
  spell_preparation_policy TEXT NOT NULL DEFAULT 'long_rest'
  settings_version INTEGER NOT NULL
  ruleset_digest TEXT NOT NULL
  updated_at

character_advancement_awards
  award_id PK
  character_id FK
  level_delta CHECK > 0
  source_kind
  source_id
  created_at
  UNIQUE(character_id, source_kind, source_id)

character_loadout_revisions
  character_id
  loadout_revision
  schema_version
  based_on_definition_revision
  loadout_json
  loadout_digest
  created_at
  PRIMARY KEY(character_id, loadout_revision)

character_settlements
  settlement_id PK
  deployment_id UNIQUE FK
  game_id FK
  character_id FK
  starting_holdings_revision/digest
  resulting_holdings_revision/digest
  delta_digest
  settled_at

character_definition metadata additions if needed
  # definition JSON remains the authenticated authority
```

Do not denormalize individual class levels into mutable SQL rows. The immutable
definition document is the authoritative ordered build.

Extend the `characters` current-head invariant only with
`current_loadout_revision/current_loadout_digest`. Add pinned loadout
revision/digest columns alongside the existing pinned definition and holdings
columns; every deployment lease authenticates all three heads. Loadout rows
receive the same update/delete rejection triggers as definitions and holdings.

Generalize the existing character bootstrap and holdings CAS into one
repository-owned revision-bundle commit:

```text
commit_character_revisions(
  expected_heads,
  expected_row_version,
  new_definition?,
  new_holdings?,
  new_loadout?,
  advancement_award?,
  settlement?,
)
```

It inserts every supplied immutable row and advances all supplied heads through
one guarded `characters` update inside the existing
`DirectoryDatabase.transaction`. Single-stream holdings/loadout mutations use
the same primitive; they do not implement another CAS algorithm.

Extend the existing pinned deployment DTOs, lease validation, and pin triggers
with the loadout head. After schema-1 migration, delete the unpinned
`deploy_character`/`legacy_pending` production path. There is one deployment
path: active lease plus exact current definition/holdings/loadout pins.

### 7.3 Shared service

Extract only the cold principal-owned character methods currently embedded in
`GameGatewayService` into one transport-neutral `CharacterDirectoryService`
and one shared character router.

```text
DirectoryDatabase
      ↓
GameDirectoryRepository
      ↓
CharacterDirectoryService
      ↓
shared route handlers
      ├── standalone local-profile app
      └── hosted gateway app
```

Standalone modes become explicit:

- `ephemeral`: current transient development behavior; no profile promises;
- `local_profile`: opens one selected local profile DB and exposes the complete
  directory/character service.

The default player-facing single-player launch mode is `local_profile`.

`CharacterDirectoryService` depends directly on the existing concrete
`GameDirectoryRepository` and content/progression services. Do not add a
repository protocol, ORM, or local repository. `GameGatewayService` delegates
its extracted methods; it does not retain a competing implementation.
Authentication stays outside the domain service: hosted passes the existing
authorized principal context, while local mode supplies the selected profile
principal.

Physical profile list/create/select endpoints are local-deployment-only and
belong to `LocalProfileManager`; they are not mounted on hosted. Keep
`GET /directory/players/me` as the canonical selected-profile read and extend
its response with settings and derived character summaries. Add one settings
update route; do not add a duplicate `/directory/profiles/current`.

### 7.4 Replay relationship

- completed games publish their existing typed replay bundle through the
  existing `GameArtifactStore` and `game_artifacts` repository path;
- SQL retains the existing artifact digest/schema/contract metadata and exact
  deployment pins; the new settlement receipt owns exactly-once loot commit;
- imported replay files are validated, canonicalized, and published through
  the same artifact store/repository;
- playback never requires reconstructing current character definitions;
- replay import does not mutate the profile's character or holdings;
- settlement is exactly-once and references the completed deployment/game.

No replay-specific store, metadata table, or path column is added. If the
existing artifact `uri` is unsuitable for profile portability, change it once
to an opaque store-relative locator; digest remains authoritative.

### 7.5 Local game history

Local-profile standalone mode reuses the current durable game lifecycle even
though it does not need the hosted worker pool:

1. preparing a local game creates a game/directory record and deployment pins;
2. activation records the runtime generation;
3. completion records outcome, participants, exact revision/content/rules
   identities, replay metadata, and settlement status;
4. the replay builders and artifact store publish the canonical bundles;
5. settlement commits holdings exactly once;
6. profile history lists completed, interrupted, and recoverable games;
7. worker/process restart does not erase completed history.

Add `ExecutionKind.LOCAL` and use the existing games, memberships, assignments,
leases, pinned deployments, summaries, artifacts, and directory events with no
worker binding. A thin local lifecycle adapter owns only prepare/activate/
interrupted boundaries.

Extract the transport-neutral publication portion of hosted terminal handling
as one function in the existing summary/artifact boundary:
`publish_terminal_evidence(typed_evidence, objective_replay,
subjective_archive)`. Hosted decodes worker HTTP responses and calls it; local
mode calls it directly with in-process typed values. Do not manufacture an HTTP
response, add a service class, or create a second history subsystem.

Live event journals remain runtime state. SQLite is not used as a per-event hot
path, and objective/player replay contracts remain separate.

## 8. Generic source-owned contribution model

### 8.1 Stable grant identity

Every automatic or selected structural grant derives a deterministic ID from:

```text
character_id
character_level ordinal
class/species/background/subclass definition ref
feature definition ref
choice ordinal when applicable
```

`GrantId` is stable across preview and commit for the same exact build. A
composition receipt aggregates the exact handles already owned by engine
components; it is not a second lifecycle or ownership graph:

```text
CharacterCompositionReceipt
  grant_id
  definition_ref
  modifier_handles: (modifiable_value_uuid, modifier_uuid)
  action_uuids
  condition_handles: (block_uuid, condition_uuid)
  handler_uuids
  resource_contribution_ids
  spellcasting_source_ids
  armor_class_formula_ids
  hit_die_uuids
```

Receipts are runtime composition facts. The durable build stores choices and
definitions, not opaque runtime UUIDs. Removal calls existing exact APIs. Add
only the missing `Entity.unregister_action_by_uuid(action_uuid)`; do not add a
grant-aware action registry, generic component-token registry, or uninstall
dispatcher.

Structural class features do not become permanent `BaseCondition`s merely to
reuse cleanup. `BaseCondition.apply()` is an evented in-play lifecycle and its
name-keyed replacement is wrong for independent cold structural grants.
Structural appliers install existing modifiers/actions/handlers/resources and
return the handles above. Conditions remain for actual gameplay conditions and
feature effects whose event lifecycle is semantically real.

### 8.2 Required generic component APIs

Implement only the source-aware gaps required by the first four classes:

- ability-score and ordinary numerical grants use existing `ModifiableValue`
  modifiers and receipt `(value_uuid, modifier_uuid)` pairs;
- add one class-neutral proficiency source-set component keyed by typed subject
  and `GrantId`, resolving the strongest applicable multiplier; Entity combines
  it with item facts, while Equipment never owns creature training;
- saving throws and skills migrate from booleans to that source authority while
  preserving their existing roll/event paths;
- composed `HitDice` blocks gain stable source identity and are removed by
  exact UUID through existing Health ownership;
- Equipment replaces its single `unarmored_ac_type` with a small typed set of
  `ArmorClassFormula` candidates; this is Equipment-specific, not a general
  predicate/capability engine;
- existing action/condition/handler exact UUID cleanup is reused;
- existing `ActionEconomy.Resource` gains stable resource IDs, source capacity
  contributions, and a contribution handle; current/spent state survives
  recomposition unless a typed rule explicitly says otherwise;
- existing `RestrictedActionGrant` remains the Haste/limited-action primitive;
- `SpellcastingBlock` gains exact source registration and spell actions carry
  their source ID;
- Extra Attack, Unarmored Defense, Channel Divinity, and proficiency use four
  named typed resolvers. Stable combination refs authenticate/report them, but
  there is no runtime interpreter for arbitrary policy strings.

Every actual turn receives one opaque `TurnExecutionId` from Encounter, and
phased/child events inherit it. The first release uses a small
`UsageWindowGuard(grant_id, scope, execution_id)` for Divine Strike and similar
rules; it does not add a universal rest/day/round feature-usage service.

The following audited capabilities stay in their future class tranches:
generic tool/instrument/initiative check contexts, alternative action costs,
pending optional-feature decisions, activity-dependent recovery allocation,
auras, feature-bound creatures/objects, Pact pools, and durable form knowledge.
Their exact requirements remain in section 15, so deferral does not waive them.

Likewise, no Entity overlay field or provider API lands in the first release.
Existing partial transformations continue to use dependency-safe
`CreatureTransformTarget` plus source-owned modifiers. The F1 Wild Shape NPC is
the first consumer of full body replacement and therefore owns the smallest
concrete design:

```text
ActiveCreatureForm
  exact creature/body recipe identity
  content_set_digest
  one resolved body snapshot
  form-health routing state
  exact cleanup receipt
```

Only one full replacement is active; a new form replaces/ends the old one, so
there is no priority-stacked eight-provider framework. The permanent Entity and
its `CreatureRuntimeBinding` remain stable. The form recipe resolves through
the existing frozen registry and supplies one internally consistent resolved
view for mechanics/projection. Gaseous Form remains an ordinary partial
condition/transform rather than pretending to be a full creature body.

### 8.3 Composition transaction

`dnd.content_system.character_materialization.materialize_character` remains
the one public deployment-time materializer. Extend its schema-2 branch to
create the class-neutral body, apply structural grants/loadout, and then run
the existing holdings hydration. It uses a small pure `CharacterBuildValidator`
and structural applier:

```text
validate(build, holdings, loadout, content_snapshot) -> CharacterBuildPreview
apply(entity, build, loadout) -> CharacterCompositionReceipt
remove(entity, receipt) -> None
```

Production level-up/respec appends immutable definition/loadout revisions and
the next deployment materializes fresh; active leases reject mutation. Do not
expose a second `CharacterComposer.materialize` or parallel production
recomposition transaction.

The user-required proof that grants can be removed without destroying the
Entity is retained as a focused cold/admin helper:

1. is allowed only outside an active encounter or inside an explicit paused
   admin transaction;
2. snapshots the old composition receipt;
3. removes source-owned grants in reverse dependency order;
4. applies the new build in ledger order;
5. validates component invariants;
6. on failure removes partial new grants and reapplies the old build;
7. emits no gameplay events because this is structural composition, not play.

Tests must prove that the same Entity UUID survives recompose and that no old
action, modifier, handler, condition, resource, proficiency, hit die, spell
source, or AC candidate leaks. The helper composes the same apply/remove
operations; it is not a persisted pathway, service, or alternate materializer.

### 8.4 Definition versus applier

Definitions are pure data:

```text
ClassDefinition
  ref, name, description, hit_die
  first_class_proficiencies
  multiclass_proficiencies
  saving_throw_proficiencies
  spellcasting_progression
  level_definitions[1..20]
  presentation
```

Generic grants are data-driven. Specialized grant appliers are trusted runtime
bindings in the existing content runtime. They
translate typed grant definitions into generic component calls. A definition's
contract hash authenticates its shape; behavior binding identity authenticates
the specialized implementation. Packs contribute definitions, dependencies,
and bindings through the existing audited content system and its one registry.

Do not serialize callables, Python paths, arbitrary kwargs, or modifier lambdas
into durable character definitions.

## 9. Spellcasting redesign

### 9.1 Runtime model

Replace the single caster ability with:

```text
SpellcastingSource
  source_id
  provider_ref                 # class, item, feat, species, etc.
  ability
  caster_progression
  provider_level
  max_spell_rank
  ritual_policy
```

`SpellAction` carries `spellcasting_source_id`. Attack bonus, save DC, resource
legality, and presentation attribution resolve from that source. Known,
prepared, always-prepared, at-will, ritual, and feature-granted executable
spells remain exact registered spell actions; do not maintain a second mutable
runtime entitlement catalog over them. Build/loadout validation owns
entitlement authority. A spell granted by both Sorcerer and Cleric can therefore
have exact source-specific actions rather than whichever class last overwrote
the Entity. Future Magical Secrets registers the selected exact spell from a
Bard source using Charisma and records feature provenance.

Spell list membership and school are exact content relations:

```text
SpellSchool: closed dependency-neutral enum

SpellListDefinition
  provider_ref: ContentRef[CLASS | FEATURE | SPECIES]
  spell_refs: tuple[ContentRef[SPELL], ...]

SpellAcquisitionProvenance
  provider_source_id
  source_grant_id
  source_choice_slot_id?
```

Delete string `classes`/`subclasses` authority from validation. Catalog entries
expose typed school and exact list refs. Creator validation, preparation,
Magical Secrets, spellbook copy, and runtime attribution never infer membership
from module paths or display names.

### 9.2 Shared normal slots; deferred multiple-pool payment

The first release does not add a second `SpellSlotPool` authority.
`ActionEconomy` already owns nine normal slot `ModifiableValue`s, rank→cost
mapping, spending through exact modifiers, and rest recovery. ESL recomputes
their structural base maxima; existing spend modifiers/current state remain in
place, so recomposition cannot refill slots or make availability negative.
Sorcery Point conversion continues to mutate those exact normal slots through
events.

For Fighter, Barbarian, Sorcerer, and Cleric, a cast's exact source and cast
rank plus the existing rank-specific cost fully identify the only legal slot
payment. Do not add `SpellSlotPoolId`, a pool registry, or a general
`SpellPayment` union until Warlock creates a second real pool.

The Warlock tranche adds:

```text
SpellSlotPoolId
SpellPayment
  payment_kind: slot | feature_use | ritual_no_slot | at_will
  slot_pool_id?
  cast_rank
  feature_use_id?
```

It then implements the separate Pact pool, cross-pool payment variants,
payment-bearing affordances/events/replays/presentation, Counterspell allocation,
and Mystic Arcanum as feature uses. Bounded recovery allocation arrives with
the first delivered Arcane/Natural Recovery consumer. This future contract is
specified in section 15 but is not frozen into the first player SDK.

### 9.3 Prepared casting

Cleric preparation:

- available list = all implemented Cleric spells up to the Cleric's maximum
  spell rank;
- prepared count = Wisdom modifier + Cleric level, minimum 1;
- domain spells are always prepared and do not count against the limit;
- cantrips use the Cleric cantrip-known table and are not prepared each day;
- the normal prepared subset lives in the exact loadout revision, never the
  structural build;
- preparation is limited by the Cleric's own class progression, even if a
  multiclass shared slot pool contains higher-rank slots;
- preparation changes append a loadout revision under the profile's separate
  `spell_preparation_policy`.

Ritual policies are a closed union:

- `prepared`: Cleric/Druid require the exact spell currently prepared;
- `known`: Bard requires the exact spell known;
- `spellbook`: Wizard requires the spell in the active accessible book but
  need not prepare it.

Ritual casting is not simulated as “free in combat.” Implement a separate
out-of-combat `RitualCastAction` that validates the source's policy, consumes no
slot, enforces components/focus/book access, and advances campaign time by the
normal casting time plus ten minutes. Until campaign time and component support
exist, it returns a typed unavailable reason; it never pretends to cast for
free.

## 10. Creation, preview, level-up, and respec transactions

### 10.1 Character creation

1. Read selected profile settings and active content snapshot.
2. Return the exact creator catalog and choice graph.
3. Client submits an exact build, not derived totals.
4. Server validates point buy, origin choices, class level 1, starting package,
   spells, and every content ref.
5. Server derives automatic grants and a complete preview.
6. On commit, in one `BEGIN IMMEDIATE` transaction:
   - insert level-1 advancement award;
   - insert character row;
   - insert definition revision 1;
   - insert holdings revision 1;
   - insert loadout revision 1;
   - set all three heads through the shared revision-bundle transaction.
7. Materialize the committed revisions in a test sandbox and verify the
   projection digest before returning success.

### 10.2 Level-up

1. Read and bind the exact definition, holdings, and loadout heads, row
   version, pinned ruleset/content-set digests, and authoritative earned-level
   total.
2. Require one unspent awarded level.
3. Return only valid next-class options and their exact required choices.
4. Client selects an existing class or adds a class.
5. Server appends one `ClassLevelEntry`, validates the whole ledger, and
   computes a before/after preview.
6. Revalidate the current loadout; if necessary, include an exact replacement
   loadout in the preview.
7. Commit one new immutable definition revision and any required loadout
   revision in one transaction; CAS proves the bound holdings head and row
   version remained unchanged.
8. Holdings are untouched.

If a separate reward operation grants the level, the award and level choice may
be separate idempotent transactions. The character cannot deploy with an
unspent required level if the scenario policy demands full advancement.

### 10.3 Respec

1. Require profile `allow_respec`.
2. Reject active deployment lease.
3. Read all three current heads, row version, earned-level authority, fixed
   origin fields, and the exact content/ruleset snapshot pinned by the current
   definition.
4. Return an HMAC-authenticated expiring preview token bound to:
   - character ID;
   - current definition revision/digest;
   - current holdings revision/digest;
   - current loadout revision/digest;
   - row version;
   - pinned settings/ruleset digest;
   - content-set digest;
   - expiry.
5. Client submits a complete replacement mutable build.
6. Server validates all levels sequentially from level 1.
7. Server materializes both builds and produces an exact diff:
   abilities, HP, proficiencies, skills, saves, class distribution, resources,
   actions, features, spells, slots, AC candidates, and unresolved choices.
8. Server revalidates the old loadout against the replacement build, preserves
   still-legal selections, and returns every dropped/new required preparation
   choice.
9. Commit appends one definition revision and one loadout revision and
   CAS-advances those two heads atomically while proving the bound holdings
   head remains unchanged. If a future Wizard respec reconciles
   structurally owned spellbook choice slots, the exact holdings revision joins
   the same transaction while copied/adventure-acquired entries and unrelated
   holdings remain untouched.
10. Token reuse returns the prior result or a deterministic idempotency result;
   stale head fails without writing.

Do not add a mutable preview/respec-session table. The token contains the
normalized-build and preview digests; commit uses the shared mutation
idempotency receipt/unique domain identity rather than an operation-specific
session subsystem.

### 10.4 Deployment and settlement

- Game launch pins exact definition, holdings, and loadout revisions in a
  deployment lease.
- Runtime receives only those pinned documents and the pinned content set.
- Encounter loot mutates encounter inventory through events.
- Endgame settlement computes the holdings delta against the pinned starting
  holdings, validates instance identity and recipes, then appends exactly one
  holdings revision with CAS/idempotency.
- Death, damage, buffs, spent resources, and map state are excluded.
- A stale settlement never overwrites a later holdings revision.

### 10.5 Prepare spells / change persistent feature toggles

1. Read the exact definition and loadout heads.
2. Verify profile preparation policy and deployment/adventure authority.
3. Validate exact source/spell refs, capacity, ranks, always-prepared exclusion,
   and feature-toggle eligibility.
4. Append one immutable loadout revision and CAS-advance only its head.
5. Holdings and structural definition stay byte-for-byte unchanged.

Changing an in-encounter handler's temporary enabled state remains encounter
state. The persistent loadout preference is applied when a new runtime Entity
is materialized or at an explicitly safe out-of-combat synchronization point.

## 11. Canonical API and generated SDK

Route names below are the intended single path. Confirm no collision with the
shared directory router before implementation; once selected, do not ship
aliases.

### 11.1 Profile surface

```text
GET /directory/players/me
PUT /directory/players/me/settings
```

Hosted derives the selected player from its existing principal authority. The
local-only launcher surface may list/create/select physical profile directories
through `LocalProfileManager`; those routes are never mounted on hosted and
requests never carry arbitrary database paths.

### 11.2 Creator and progression catalog

```text
GET  /character-creation/catalog
POST /character-builds/validate
```

The catalog contains:

- exact ruleset and content-set digests;
- exact generic content-catalog digest;
- species, variants, backgrounds, classes, subclasses, feats, features,
  proficiencies, starting packages, and spells as exact content refs;
- level-by-level automatic grants;
- level-by-level choice requirements;
- prerequisites and conflict rules;
- class recommendations as non-authoritative hints;
- the point-buy cost table and flexible +2/+1 rule;
- exact implementation status for authored choices/spells.

`validate` accepts a complete draft or a next-level draft and returns:

```text
CharacterBuildValidationResponse
  valid
  errors[]                    # typed path/code/message/content refs
  unresolved_choices[]
  normalized_build           # exact canonical order, never hidden defaults
  automatic_grants[]
  derived_preview
  ruleset_digest
  content_set_digest
  preview_digest
```

Names, descriptions, icons, provenance, and presentation remain owned by
`/content/catalog`; the creator catalog references those rows instead of
copying them into a second authenticated payload. Progression spell validation
uses exact spell-list definitions from `FrozenContentRegistry`, never legacy
class/name/id spell maps.

The frontend never recomputes legality, slot tables, HP, proficiency bonus, or
feature stacking. It may optimistically render from the returned typed
progression catalog plus generic content catalog, but commit authority remains
server-side.

### 11.3 Character surface

```text
POST /directory/characters
GET  /directory/characters/{character_id}
GET  /directory/characters/{character_id}/definition
GET  /directory/characters/{character_id}/definitions
GET  /directory/characters/{character_id}/holdings
GET  /directory/characters/{character_id}/loadout

GET  /directory/characters/{character_id}/advancement
POST /directory/characters/{character_id}/level-up/validate
POST /directory/characters/{character_id}/level-up
POST /directory/characters/{character_id}/respec/validate
POST /directory/characters/{character_id}/respec
POST /directory/characters/{character_id}/loadout/validate
POST /directory/characters/{character_id}/loadout
```

Every mutation includes:

- expected definition/holdings/loadout revision and digest as
  applicable;
- expected character row version;
- expected ruleset/content-set digest;
- idempotency key.

Every response returns the exact new head(s), row version, normalized build,
derived summary, and preview/commit digest. Stale, lease-active, invalid-choice,
missing-content, unsupported-policy, and idempotency-conflict errors are typed.

### 11.4 Character read model

The player/profile list must not force the UI to deserialize full definitions
just to draw a character card. Add a server-derived exact summary:

```text
CharacterSummary
  character_id
  display_name
  total_level
  class_levels[]              # exact class/subclass refs and levels
  species_ref
  species_variant_ref
  background_ref
  portrait/presentation identity
  current_definition_revision/digest
  current_holdings_revision/digest
  current_loadout_revision/digest
  deployment state
  unspent_level_count
```

`CharacterSummary` is a derived read DTO assembled from the existing canonical
character record plus its authenticated current definition. It is never a
separate table or revision head; denormalized indexes require a measured query
need.

`premade_id` remains optional provenance. It is not used to infer the current
class build or portrait. Remove the launch-time requirement that a selected
scenario's `hero_configuration_id` equal the character premade ID. Launch
selects the character ID and pins its exact current revisions.

### 11.5 TypeScript SDK

- Generate every contract and client method from the canonical server models.
- Add no handwritten shadow DTOs and no client-side JSON parsing.
- Export exact discriminated choice and validation-error unions.
- Preserve `ContentRef` contract hashes transitively in SDK contract identity.
- Add SDK tests for all route query/body construction, error decoders, unknown
  fields, closed enums, digest mismatches, and idempotent responses.
- The character creator UI can be implemented after the catalog/validation SDK
  freezes; backend tests must not depend on a frontend implementation.

### 11.6 Creator/level-up/respec UI contract

The backend exposes an ordered typed choice graph so the frontend can use
separate panels/modals without inventing rules:

1. profile rules summary;
2. identity and appearance;
3. species and species choices;
4. background and its grants;
5. point buy and flexible +2/+1;
6. first class and starting proficiencies/skills;
7. subclass when the selected level requires it;
8. class-specific choices such as Fighting Style, ancestry, or Metamagic;
9. known cantrips/spells;
10. prepared loadout where applicable;
11. starting equipment package;
12. complete review and commit.

Every panel shows:

- exact selected and candidate `ContentRef`;
- icon, name, rules description, provenance, and implementation status;
- automatic gains at this level;
- all future gains through level 20 for transparency;
- prerequisites/conflicts and typed unavailability reason;
- live server-derived before/after abilities, HP, proficiencies, features,
  resources, slots, and spells.

Level-up uses the same components but shows one `ClassLevelEntry` delta. Respec
shows the full ordered ledger and an exact removal/addition diff. Automatic
grants are visible but not presented as selectable controls.

The client may split these steps differently for screen size, but cannot
replace exact refs with names, hide required choices behind defaults, or
calculate mechanical totals independently.

## 12. Existing class migration

The three migrations are deliberately sequential. Each class is first proven
alone at levels 1–20, then in pairwise/order-sensitive combinations.

### 12.1 Shared red-first foundation tests

Before migrating a class, add failing tests for:

1. applying and removing a generic grant receipt on one Entity;
2. two independent sources of the same proficiency;
3. removal of one source preserving the other;
4. action/resource/handler removal by grant rather than name;
5. mixed hit dice with only character level 1 maximized;
6. source-owned AC formula candidates;
7. total-level proficiency and cantrip scaling;
8. exact per-source spell ability/DC;
9. shared ESL slot derivation;
10. recompose rollback after an injected applier failure;
11. import-graph/static gate proving dependency direction;
12. deterministic digest and application order;
13. Extra Attack highest-rank resolution versus distinct bonus/reaction attack
    mechanics;
14. Fighting Style duplicate-choice rejection across delivered sources;
15. suppressed grant reporting and correct respec re-resolution when the
    formerly first/highest provider is removed.
16. unique `TurnExecutionId` propagation through child events and exact
    first-four owner-turn consumption;
17. source-owned resource maximum changes preserving spent state.

Monk/Paladin combination cases, generic partial/tool/initiative checks, Pact
cross-payment, Thirsting Blade, active forms, spellbooks, and feature-bound
item/creature teardown begin with their future tranche; they are specified in
section 15 but are not first-release runtime tests.

### 12.2 Fighter migration

Author Fighter and Champion as definitions plus bindings.

Required progression:

- d10 hit die;
- armor, shield, simple, and martial weapon proficiencies;
- Strength and Constitution saves;
- first-class skill choices;
- multiclass proficiency package;
- Fighting Style at 1;
- Second Wind at 1;
- Action Surge at 2 and second use at 17;
- Champion subclass selection at 3;
- Improved Critical at 3;
- ASIs at 4, 6, 8, 12, 14, 16, 19;
- Extra Attack at 5, 11, and 20 with max-policy semantics;
- Remarkable Athlete at 7;
- additional Fighting Style at 10;
- Superior Critical at 15;
- Survivor at 18;
- Indomitable at 9, 13, 17.

Exact level-row gate:

| Fighter level | New/advanced feature |
| ---: | --- |
| 1 | Fighting Style, Second Wind |
| 2 | Action Surge (1 use) |
| 3 | Champion, Improved Critical |
| 4 | ASI/feat |
| 5 | Extra Attack: 2 attacks |
| 6 | ASI/feat |
| 7 | Remarkable Athlete |
| 8 | ASI/feat |
| 9 | Indomitable (1 use) |
| 10 | second Fighting Style |
| 11 | Extra Attack: 3 attacks |
| 12 | ASI/feat |
| 13 | Indomitable (2 uses) |
| 14 | ASI/feat |
| 15 | Superior Critical |
| 16 | ASI/feat |
| 17 | Action Surge (2 uses), Indomitable (3 uses) |
| 18 | Survivor |
| 19 | ASI/feat |
| 20 | Extra Attack: 4 attacks |

Current-code audit: the one-shot factory already wires the major combat
features, scaling uses, critical thresholds, and Survivor, but no Remarkable
Athlete implementation was found. Several feature cleanups still unregister by
display name, and proficiencies/starting equipment remain factory facts. The
new tests must expose and close those gaps rather than canonize the omission.

Audit existing implementations rather than assuming every row exists. Each
missing feature becomes an authored class-feature entry and a measured
implementation task, or an explicit blocker; it is never silently omitted from
the level preview.

Fighter acceptance includes:

- level-by-level golden derived facts, not serialized whole-Entity goldens;
- Fighter 1 as first class versus added class;
- Fighter Extra Attack combined with Haste in both legal action orders;
- Fighter Extra Attack combined with another class source;
- Action Surge uses/recovery and cleanup;
- weapon proficiency affects attack bonus;
- every Fighting Style exact choice and reversal;
- Champion critical threshold candidates and reversal.

Delete `create_fighter`/finished `FighterConfig` consumers only after premades,
scenarios, tests, and content recipes invoke the composer.

### 12.3 Barbarian migration

Author Barbarian and Berserker as definitions plus bindings.

Required progression:

- d12 hit die;
- armor/shield/simple/martial weapon proficiencies;
- Strength and Constitution saves;
- first-class skill choices;
- multiclass proficiency package;
- Rage and uses/scaling;
- Unarmored Defense;
- Reckless Attack;
- Danger Sense;
- Berserker subclass;
- Frenzy and subclass features at their exact levels;
- ASIs;
- Extra Attack max policy;
- Fast Movement;
- Feral Instinct;
- Brutal Critical scaling;
- Relentless Rage;
- Persistent Rage;
- Indomitable Might;
- Primal Champion.

Exact level-row gate:

| Barbarian level | Rages / damage | New/advanced feature |
| ---: | --- | --- |
| 1 | 2 / +2 | Rage, Unarmored Defense |
| 2 | 2 / +2 | Reckless Attack, Danger Sense |
| 3 | 3 / +2 | Berserker, Frenzy |
| 4 | 3 / +2 | ASI/feat |
| 5 | 3 / +2 | Extra Attack, Fast Movement |
| 6 | 4 / +2 | Mindless Rage |
| 7 | 4 / +2 | Feral Instinct |
| 8 | 4 / +2 | ASI/feat |
| 9 | 4 / +3 | Brutal Critical 1 die |
| 10 | 4 / +3 | Intimidating Presence |
| 11 | 4 / +3 | Relentless Rage |
| 12 | 5 / +3 | ASI/feat |
| 13 | 5 / +3 | Brutal Critical 2 dice |
| 14 | 5 / +3 | Retaliation |
| 15 | 5 / +3 | Persistent Rage |
| 16 | 5 / +4 | ASI/feat |
| 17 | 6 / +4 | Brutal Critical 3 dice |
| 18 | 6 / +4 | Indomitable Might |
| 19 | 6 / +4 | ASI/feat |
| 20 | unlimited / +4 | Primal Champion |

Current-code audit: the factory contains bindings for every named row above,
including Berserker 3/6/10/14 and Brutal Critical scaling. The architectural
defects are ownership: finished-level condition installation, name-keyed Rage
resources/actions, factory-owned loadout, and a single unarmored-defense mode.
Migration must preserve behavior while replacing those ownership seams.

Barbarian acceptance includes:

- first-class versus multiclass proficiencies;
- Rage source/resource/condition cleanup;
- Rage damage only on legal attacks;
- Unarmored Defense applying only when legal, with any later class's
  Unarmored Defense grant suppressed by first-acquired exclusivity;
- unrelated AC formulas resolving under their exact formula policy, never
  stacking by accident;
- Constitution ASI retroactively updating HP and Barbarian AC;
- Extra Attack/Haste order matrix;
- Frenzied Strike/alternate weapon attack retaining attack presentation
  metadata on misses;
- removal/reapply leaving no stale handlers or conditions.

Delete the one-shot Barbarian factory only after parity and cross-class gates.

### 12.4 Sorcerer migration

Author Sorcerer and Draconic Bloodline as definitions plus bindings.

Required progression:

- d6 hit die;
- Constitution and Charisma saves;
- first-class skill choices;
- cantrip/spell-known progression and replacement;
- full-caster contribution;
- Sorcerous Origin at 1;
- Draconic Resilience/ancestry;
- Font of Magic and Sorcery Points;
- Flexible Casting;
- Metamagic choices and additional choices;
- ASIs;
- origin features at 6, 14, 18;
- Sorcerous Restoration at 20.

Exact level-row gate:

| Sorcerer level | Cantrips / spells known | Sorcery points | Normal slots L1→L9 | New/advanced feature |
| ---: | --- | ---: | --- | --- |
| 1 | 4 / 2 | 0 | 2 | Draconic Bloodline, Resilience |
| 2 | 4 / 3 | 2 | 3 | Font of Magic |
| 3 | 4 / 4 | 3 | 4/2 | Metamagic (2 choices) |
| 4 | 5 / 5 | 4 | 4/3 | ASI/feat |
| 5 | 5 / 6 | 5 | 4/3/2 | — |
| 6 | 5 / 7 | 6 | 4/3/3 | Elemental Affinity |
| 7 | 5 / 8 | 7 | 4/3/3/1 | — |
| 8 | 5 / 9 | 8 | 4/3/3/2 | ASI/feat |
| 9 | 5 / 10 | 9 | 4/3/3/3/1 | — |
| 10 | 6 / 11 | 10 | 4/3/3/3/2 | Metamagic (3 total) |
| 11 | 6 / 12 | 11 | 4/3/3/3/2/1 | — |
| 12 | 6 / 12 | 12 | 4/3/3/3/2/1 | ASI/feat |
| 13 | 6 / 13 | 13 | 4/3/3/3/2/1/1 | — |
| 14 | 6 / 13 | 14 | 4/3/3/3/2/1/1 | Dragon Wings |
| 15 | 6 / 14 | 15 | 4/3/3/3/2/1/1/1 | — |
| 16 | 6 / 14 | 16 | 4/3/3/3/2/1/1/1 | ASI/feat |
| 17 | 6 / 15 | 17 | 4/3/3/3/2/1/1/1/1 | Metamagic (4 total) |
| 18 | 6 / 15 | 18 | 4/3/3/3/3/1/1/1/1 | Draconic Presence |
| 19 | 6 / 15 | 19 | 4/3/3/3/3/2/1/1/1 | ASI/feat |
| 20 | 6 / 15 | 20 | 4/3/3/3/3/2/2/1/1 | Sorcerous Restoration |

Current-code audit: the factory has Resilience, Font/Sorcery Points, selected
Metamagic, Elemental Affinity, and the full-caster slot helper. It does not
implement Dragon Wings, Draconic Presence, or Sorcerous Restoration. Its
curated default spell list is not the SRD spells-known progression and stops
adding ranks after fifth-rank examples; explicit `spell_names` are not the
typed exact entitlement/choice model. These are measured migration gaps, not
acceptable parity.

Sorcerer acceptance includes:

- exact known-spell counts and rank ceiling for levels 1–20;
- shared-slot use without overwriting source ability;
- Sorcery Point conversion against the canonical slot pool;
- Quickened/Twinned legality and source cleanup;
- a Sorcerer/Cleric same-spell case with exact provider selection;
- Sorcerer first versus added class saves/proficiencies;
- total-level cantrip scaling;
- respec replacing spells/metamagic without stale actions/resources;
- Draconic AC candidate competing rather than stacking.

Delete baked spell-slot tables and the one-shot Sorcerer factory after this
phase.

### 12.5 Premade migration

Extend the existing dependency-neutral `PremadeCharacterTemplate`; do not add
a `PremadeCharacterDefinition` or premade registry. Each current
Fighter/Barbarian/Sorcerer template becomes:

```text
PremadeCharacterTemplate
  premade_id
  initial CharacterBuildV2 selections
  starter CharacterHoldingsRevision recipe
  optional authored recommendation metadata
```

The build is validated through the same creator validator. No premade-specific
class construction remains. Existing scenario character selections point to
premade build IDs only for “create a new premade”; persisted character launch
uses character ID and revision heads.

## 13. Cross-class gate before Cleric

Cleric work cannot begin until all of the following are green:

### 13.1 Single-class gate

- Fighter, Barbarian, and Sorcerer each validate/materialize at every level
  1–20.
- Every table row reports automatic grants and required choices.
- Applying then removing each level's cumulative composition leaves the base
  Entity invariant-clean.
- Existing maintained feature tests pass through the new path.
- Old factory imports have zero production call sites.

### 13.2 Pairwise/order gate

At minimum:

- Fighter 1 → Barbarian 1 and reverse order;
- Fighter 5 → Barbarian 5 and distributions with overlapping Extra Attack;
- Fighter/Sorcerer in both first-class orders;
- Barbarian/Sorcerer in both first-class orders;
- at least one three-class build;
- saving throws differ correctly by first class;
- added-class proficiencies are restricted;
- proficiency bonus uses total level;
- HP uses only the first character level maximum;
- mixed hit dice and short-rest spending remain class-separated;
- Unarmored Defense class-order exclusivity and Extra Attack highest-rank
  resolution use explicit combination policy;
- spell source remains intact when martial levels are added.

### 13.3 Respec gate

On one existing Entity and in durable SQL:

- Fighter 10 → Fighter 5/Barbarian 5;
- Barbarian 5/Sorcerer 5 → Fighter 2/Sorcerer 8;
- Sorcerer spell/metamagic replacement;
- ability reallocation changing HP/DC/AC;
- injected failure restores the exact pre-respec runtime composition;
- committed respec advances one definition revision;
- old definition remains readable and immutable;
- holdings digest/revision is byte-for-byte unchanged;
- active deployment lease rejects the mutation;
- stale CAS/idempotency races write no orphan head.

### 13.4 Architecture/performance gate

- import graph has no cycle, late import, or upward class dependency;
- build validation is pure and deterministic;
- materialization stays within an explicit baseline budget measured on the
  largest level-20 build and a representative multiclass;
- one validation request does not reconstruct the content registry;
- SQLite mutations remain bounded transactions with existing query timing;
- SDK generation/check/build is green.

Only after this gate is the foundation considered stable enough to use Cleric
as proof that a new class can be authored without editing Entity or introducing
class-specific infrastructure.

## 14. Cleric: declarative implementation after the gate

### 14.1 Scope and definition

Implement SRD 5.1 Cleric levels 1–20 with the Life Domain. Cleric is not
implemented by copying a fourth one-shot factory. It must be expressible using
the same public class-definition and grant-binding surfaces already used by the
three migrated classes.

Base Cleric definition includes:

- d8 hit die;
- first-class light/medium armor, shield, and simple weapon proficiency;
- added-class **only** light/medium armor and shields: no simple weapons,
  saves, skills, or starting equipment;
- Wisdom and Charisma saving throws;
- first-class selection of two skills from History, Insight, Medicine,
  Persuasion, and Religion;
- exact multiclass proficiency package;
- Wisdom full-caster source;
- prepared casting and ritual metadata;
- Channel Divinity pool/options;
- Destroy Undead scaling;
- Divine Intervention and improvement.

With `permissive_multiclass_prerequisites=false`, Wisdom 13 is required both to
enter Cleric and to leave Cleric for another class. With the default `true`,
that prerequisite is intentionally ignored.

Life Domain includes:

- bonus heavy armor proficiency;
- domain spells, always prepared;
- Disciple of Life;
- Preserve Life;
- Blessed Healer;
- Divine Strike;
- Supreme Healing.

Exact always-prepared Life Domain rows:

| Cleric level | Domain spells | Current audit |
| ---: | --- | --- |
| 1 | Bless, Cure Wounds | both playable |
| 3 | Lesser Restoration, Spiritual Weapon | Spiritual Weapon missing |
| 5 | Beacon of Hope, Revivify | Revivify missing |
| 7 | Death Ward, Guardian of Faith | both playable |
| 9 | Mass Cure Wounds, Raise Dead | Raise Dead missing |

The independent 2026-07-26 source-ledger audit found 45 of 105 SRD Cleric spells
currently playable and 60 missing: cantrips 4/7; ranks 1–9 respectively
9/15, 9/17, 7/19, 4/8, 4/13, 4/10, 2/8, 1/4, 1/4. Cleric can reach a bounded
MVP without implementing all missing tabletop subsystems, but “SRD Cleric spell
complete” is forbidden until the checked-in source ledger reaches 105/105.

The Cleric MVP additionally requires Spare the Dying plus the three missing Life
Domain spells above.

### 14.2 Level progression acceptance table

The authored table and tests must encode:

| Cleric level | Cantrips | Normal slots L1→L9 | Required grants/choices |
| ---: | ---: | --- | --- |
| 1 | 3 | 2 | Spellcasting, domain, Life heavy armor, Disciple, domain spells |
| 2 | 3 | 3 | Channel Divinity 1/rest, Turn Undead, Preserve Life |
| 3 | 3 | 4/2 | rank-2/domain spells |
| 4 | 4 | 4/3 | ASI/feat |
| 5 | 4 | 4/3/2 | Destroy Undead CR 1/2, rank-3/domain spells |
| 6 | 4 | 4/3/3 | Channel Divinity 2/rest, Blessed Healer |
| 7 | 4 | 4/3/3/1 | rank-4/domain spells |
| 8 | 4 | 4/3/3/2 | ASI/feat, Destroy CR 1, Divine Strike 1d8 |
| 9 | 4 | 4/3/3/3/1 | rank-5/domain spells |
| 10 | 5 | 4/3/3/3/2 | Divine Intervention |
| 11 | 5 | 4/3/3/3/2/1 | Destroy CR 2 |
| 12 | 5 | 4/3/3/3/2/1 | ASI/feat |
| 13 | 5 | 4/3/3/3/2/1/1 | rank-7 spells |
| 14 | 5 | 4/3/3/3/2/1/1 | Destroy CR 3, Divine Strike 2d8 |
| 15 | 5 | 4/3/3/3/2/1/1/1 | rank-8 spells |
| 16 | 5 | 4/3/3/3/2/1/1/1 | ASI/feat |
| 17 | 5 | 4/3/3/3/2/1/1/1/1 | Destroy CR 4, Supreme Healing |
| 18 | 5 | 4/3/3/3/3/1/1/1/1 | Channel Divinity 3/rest |
| 19 | 5 | 4/3/3/3/3/2/1/1/1 | ASI/feat |
| 20 | 5 | 4/3/3/3/3/2/2/1/1 | Improved Divine Intervention |

Cantrips known, prepared count, spell slots through full-caster ESL, proficiency
bonus, and feature numeric scaling are tested at every boundary. Domain spell
rows must be exact SRD rows and remain always prepared without consuming the
normal prepared count.

### 14.3 Channel Divinity model

Channel Divinity is:

- one Entity-owned core capability family assembled from exact class-source
  options and capacity entitlements;
- shared lawfully with a future Paladin provider: options union and the highest
  explicit capacity wins;
- fully recovered on a short or long rest;
- consumed through typed actions/events;
- shared by Turn Undead and domain Channel Divinity options;
- not represented as one resource per option;
- isolated from unrelated similarly named resources by exact combination-group
  identity, not by display name;
- removed/recomputed cleanly on respec.

Turn Undead:

- selects visible/hearing-capable undead in range according to the exact
  implemented sensory rule;
- performs one Wisdom save per target against the Cleric source DC;
- applies a typed Turned condition for ten rounds or until positive damage;
- denies reactions, forbids willing movement closer to the Cleric, requires the
  target to move as far away as possible, and restricts its action to Dash or
  escape from an effect preventing movement (Dodge only when it cannot do so);
- records all target outcomes as child events/presentation cues;
- lets AI evaluate affected target count and risk;
- never relies on a display-name check for creature type or condition.

`ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED` already exists as neutral
metadata, but the current runtime does not generically enforce it. Implement
that generic effect-origin-aware removal once before Turned; do not add a
Turned-only damage listener.

Destroy Undead:

- is a Turn Undead outcome extension at the scaling CR threshold;
- uses authoritative typed creature CR and creature type; add exact rational CR
  as a generic runtime creature fact rather than parsing authored tags;
- emits an explicit instant-destruction lifecycle child for eligible failed
  saves; do not approximate the rule as HP damage or delete the Entity;
- clearly defines treatment of PCs/nonstandard undead and immune/boss traits.

Preserve Life:

- consumes Channel Divinity;
- exposes a bounded multi-target healing-allocation request;
- total budget is `5 × Cleric level`;
- cannot heal a target above half maximum HP;
- rejects undead and constructs;
- uses exact integer allocation validation;
- AI receives a deterministic allocator;
- each heal is a child event, with unused budget reported.

### 14.4 Life Domain healing features

Disciple of Life, Blessed Healer, and Supreme Healing must integrate with typed
healing evidence rather than spell-name lists.

Required evidence includes:

- exact spell source/provider;
- base spell rank and cast rank;
- whether the effect restores HP using a spell slot;
- dice components before roll;
- target/source identity;
- parent cast lineage.

Rules:

- Disciple of Life adds `2 + cast spell level` to every qualifying healed
  creature, including a qualifying healing spell cast through another class
  source;
- Blessed Healer heals the Cleric **once per causal spell cast**, even for a
  multi-target spell, when a qualifying level-1+ spell heals at least one other
  creature, using `2 + cast spell level`;
- Supreme Healing maximizes qualifying spell healing dice;
- features neither recurse through their own derived heal nor trigger from
  potions, hit dice, Channel Divinity, or non-spell effects;
- upcast level is handled explicitly and tested;
- multi-target healing attaches each derived effect to the correct cast/target.

If current healing events lack this typed provenance, add the smallest
dependency-neutral fields/effect-origin value objects before Cleric. Do not use
spell class imports or name normalization in a generic event handler.

### 14.5 Divine Strike

Divine Strike:

- is an explicit `OWNER_TURN` usage-ledger entry owned by the Cleric grant and
  keyed to `TurnExecutionId`;
- is an optional enabled-by-default authored handler whose persistent preference
  may live in character loadout;
- applies radiant damage to a qualifying weapon attack;
- applies only during the Cleric's own turn, not on opportunity attacks;
- is 1d8 at Cleric 8 and 2d8 at Cleric 14;
- contributes damage dice to the weapon hit and therefore doubles those dice on
  a critical hit;
- resets through the turn lifecycle;
- carries exact damage components and presentation attribution;
- does not trigger on spell attacks or multiple times through Extra Attack,
  Haste or Action Surge in the same turn.

The implementation must use the canonical alternate-attack metadata snapshot
so misses still retain presentation evidence.

### 14.6 Divine Intervention decision

The tabletop feature delegates effect choice to a deity/DM and therefore needs
an explicit product interpretation.

Initial deterministic implementation:

1. expose Divine Intervention as a typed action backed by a registered
   `DivineInterventionResolver` whose possible results are exact authored
   content refs, never arbitrary callables or text;
2. Life Domain initially installs a deterministic restorative resolver assembled
   from existing Cleric spell/effect primitives;
3. levels 10–19 roll d100 and succeed when `roll <= Cleric level`;
4. level 20 succeeds automatically;
5. the intervention itself does not spend a spell slot;
6. result, selected intervention ref, roll, cooldown, and all child effects are
   evented and replayable;
7. AI selects only among the resolver's closed currently legal intervention
   refs;
8. the frontend receives exact content/presentation refs.

Do not implement “the server chooses anything reasonable” or permit arbitrary
Python/LLM effects. Additional deity/domain interventions are content
definitions added later.

On failure, the feature becomes available again after a long rest. On success,
store `available_after_campaign_day = current_day + 7`. A campaign clock is
therefore an MVP dependency. If no resolver is installed, expose typed
`requires_adjudication_provider`; if no campaign clock is installed, expose a
typed unavailable reason. Do not pretend an encounter rest is seven days.

### 14.7 Cleric spell implementation ledger

Create a checked-in Cleric spell ledger, keyed by exact `ContentRef`, with:

```text
spell ref
SRD rank/school/ritual/concentration
Cleric-list membership
Life-domain membership, if any
implementation status
engine adaptation decision
required primitive/system
focused regression test
presentation status
AI semantics status
```

Statuses are closed:

- `implemented_exact`;
- `implemented_adapted` with an adjudication ID;
- `blocked_by_named_system`;
- `deferred_non_tactical`;
- `not_srd`.

Character validation offers only implemented spells as selectable/preparable,
but the catalog shows unavailable SRD rows and their exact blocker. Missing
spells are not silently absent and not represented by another spell.

The first playable Cleric must include all domain spells and enough exact
cantrip/rank coverage to satisfy every level boundary. Cleric is not declared
SRD-complete until every SRD Cleric-list row has a ledger disposition and every
`implemented_*` row has behavior, AI, presentation, and focused tests.

### 14.8 Vague/non-tactical Cleric adjudications

Create
`agent_docs/rules/CLERIC_SRD_5_1_ADJUDICATIONS.md`. Each entry contains:

```text
adjudication_id
feature/spell ContentRef
quoted/paraphrased SRD requirement and source page
ambiguity or missing engine system
chosen deterministic behavior
explicit deviations
event/action/condition/resource representation
targeting and AI semantics
presentation/combat-log requirements
save/replay requirements
red-first tests
future replacement condition
```

Mandatory entries include:

- Divine Intervention;
- Turn Undead and “present holy symbol” sensory assumptions;
- Destroy Undead and special/boss immunity;
- Preserve Life allocation;
- prepared-spell timing;
- ritual casting;
- divination/communication spells requiring a DM answer;
- resurrection and corpse/afterlife assumptions;
- sanctuary/non-hostile intent boundaries;
- food, water, travel, downtime, planar, social, and object-creation spells;
- material components with a monetary cost;
- spells whose geometry or persistent world mutation is underspecified.

The implementation PR may not introduce a new ad hoc interpretation without a
new adjudication entry and measuring test.

### 14.9 Generic Cleric prerequisites discovered in the code audit

Land these as generic capabilities before concrete Cleric bindings:

1. per-class `SpellcastingSource`, because the current block owns only one
   Entity-wide casting ability;
2. exact casting-source identity on registered spell actions;
3. total-character-level cantrip scaling rather than factory-supplied class
   level;
4. recomputed shared slots rather than initial `ActionEconomyConfig` data;
5. source-owned skill/save/equipment proficiencies;
6. grant-owned resources instead of display-name overwrite/removal;
7. typed healing provenance: spell source, cast rank, heal dice, causal cast
   lineage, target, and origin;
8. exact rational challenge rating on runtime creatures;
9. generic enforcement of positive-damage condition removal;
10. ritual action, campaign clock, and component/focus enforcement;
11. generic spell-focus capability: a holy symbol substitutes only non-priced,
    non-consumed material components;
12. Preserve Life's typed target/allocation action payload;
13. corpse death timestamp, body integrity/presence, and transactional consumed
    material facts for Revivify/Raise Dead;
14. campaign-time/adjudication-provider surfaces for Divine Intervention.

These are reusable engine capabilities. `Entity` may own their class-neutral
execution APIs but never imports Cleric.

### 14.10 Initial dispositions for all currently missing Cleric spells

This table seeds the checked-in exact-ref ledger. Its statuses remain measured
against `content_data/ledgers/srd_5_1_source_coverage.json`; names below are
human-readable only.

| Rank | Spell | Initial decision / required system |
| ---: | --- | --- |
| 0 | Mending | deferred: typed object repair; never creature healing |
| 0 | Spare the Dying | not applicable under the selected `0 HP -> DEAD` product rule; do not expose as executable |
| 0 | Thaumaturgy | deferred: separate authored sensory/environment modes |
| 1 | Create or Destroy Water | deferred: typed create/destroy environmental water |
| 1 | Detect Evil and Good | deferred: privacy-safe typed creature/consecration sense |
| 1 | Detect Magic | deferred: authored magical aura/school and obstruction |
| 1 | Detect Poison and Disease | deferred: exact poison/disease sensory facts |
| 1 | Protection from Evil and Good | later: exact creature-type protection and source-aware charm/frighten/possession |
| 1 | Purify Food and Drink | deferred: ingestible contamination state |
| 2 | Augury | deferred: typed oracle provider and repeat uncertainty |
| 2 | Calm Emotions | deferred: branch-specific charm/fear suppression or hostility semantics |
| 2 | Find Traps | deferred: authored intentional-danger fact, no location leak |
| 2 | Gentle Repose | deferred: corpse age/decay/undead-conversion timers |
| 2 | Locate Object | deferred: privacy-safe world query and lead blocking |
| 2 | Spiritual Weapon | **MVP**: owner-bound timed summon, movement, bonus-action attack |
| 2 | Warding Bond | later: linked AC/save/resistance and nonrecursive mirrored damage |
| 2 | Zone of Truth | deferred: deliberate statement/dialogue semantics |
| 3 | Animate Dead | deferred: corpse conversion and 24-hour command entitlement |
| 3 | Clairvoyance | deferred: explicit remote subjective observer |
| 3 | Create Food and Water | later: exact persistent inventory/environment creation |
| 3 | Dispel Magic | later core primitive: exact active spell-effect target and rank check |
| 3 | Glyph of Warding | deferred: persistent trigger DSL, immobility, material cost |
| 3 | Magic Circle | later: typed creature ward/trap zone and planar restrictions |
| 3 | Meld into Stone | deferred: topology/occupancy/destruction/perception support |
| 3 | Revivify | **MVP**: dead ≤1 minute, body present, consumed diamond, 1 HP |
| 3 | Sending | deferred: campaign message/language/plane service |
| 3 | Speak with Dead | deferred: corpse-memory dialogue provider and question session |
| 3 | Tongues | deferred: language understanding/speech capabilities |
| 3 | Water Walk | later: liquid-surface movement and submerged rise |
| 4 | Control Water | deferred: environmental water volumes and four modes |
| 4 | Divination | deferred: typed deity oracle and repeat uncertainty |
| 4 | Locate Creature | deferred: privacy-safe query and polymorph identity |
| 4 | Stone Shape | deferred: persistent bounded terrain mutation |
| 5 | Commune | deferred: typed three-question deity oracle |
| 5 | Contagion | later: exact selected disease and save progression |
| 5 | Dispel Evil and Good | later: planar-origin and source-aware enchantment dismissal |
| 5 | Geas | deferred: enforceable instruction/compliance semantics |
| 5 | Hallow | deferred: persistent large zone, exclusions, material cost |
| 5 | Legend Lore | deferred: authored lore-query provider |
| 5 | Planar Binding | deferred: planar control, containment, material cost |
| 5 | Raise Dead | **MVP**: dead ≤10 days, body/material facts, penalties/recovery |
| 5 | Scrying | deferred: privacy-safe remote observer and sensor lifecycle |
| 6 | Blade Barrier | later: wall/ring geometry, opacity, entry/start effects |
| 6 | Create Undead | deferred: corpse conversion, nighttime, exact ghoul content |
| 6 | Find the Path | deferred: privacy-safe known-destination path oracle |
| 6 | Forbiddance | deferred: persistent ritual zone and planar denial |
| 6 | Planar Ally | deferred: adjudicated entity/service/payment provider |
| 6 | Word of Recall | deferred: sanctuary records and cross-map transport |
| 7 | Conjure Celestial | later: installed exact creature refs constrained by CR |
| 7 | Etherealness | deferred: planes, ethereal occupancy/perception/traversal |
| 7 | Fire Storm | later: ordered ten-cube allocation and environmental ignition |
| 7 | Plane Shift | deferred: planes, destinations, tuning forks |
| 7 | Resurrection | deferred: corpse age/body restoration and revival penalties |
| 7 | Symbol | deferred: persistent trigger DSL and selected symbol effects |
| 8 | Control Weather | deferred: campaign-scale weather transitions |
| 8 | Earthquake | deferred: fissures, structures, collapse, persistent terrain |
| 8 | Holy Aura | later: exact aura plus fiend/undead blindness rider |
| 9 | Astral Projection | deferred: planes, astral bodies, cords, suspended bodies |
| 9 | Gate | deferred: planar portals and adjudicated named-creature summoning |
| 9 | True Resurrection | deferred: 200-year death history, body reconstruction, cost |

For every `later` or `MVP` promotion:

1. add its exact adjudication if adaptation is required;
2. add the focused failing semantic test;
3. implement behavior and generic prerequisites;
4. add AI legality/utility and presentation attribution;
5. change the source ledger status;
6. prove catalog and generated SDK closure.

No deferred spell is exposed as executable merely to fill a progression count.

## 15. Forward audit of every other SRD class

These classes are not part of the first implementation delivery. Their SRD
5.1 class/subclass plans were audited now to keep the Fighter/Barbarian/
Sorcerer/Cleric foundation from freezing the wrong abstractions. Every future
class uses the same ordered class ledger and source-owned grants; none gets a
parallel character factory.

| Class | Initial SRD subclass | Added-class prerequisite when strict | Added-class proficiency package |
| --- | --- | --- | --- |
| Bard | College of Lore | CHA 13 | light armor, one skill choice, one instrument choice |
| Druid | Circle of the Land | WIS 13 | light/medium armor, shields (subject to authored material restrictions) |
| Monk | Way of the Open Hand | DEX 13, WIS 13 | simple weapons, shortswords |
| Paladin | Oath of Devotion | STR 13, CHA 13 | light/medium armor, shields, simple/martial weapons |
| Ranger | Hunter | DEX 13, WIS 13 | light/medium armor, shields, simple/martial weapons, one Ranger skill |
| Rogue | Thief | DEX 13 | light armor, one Rogue skill, thieves' tools |
| Warlock | The Fiend | CHA 13 | light armor, simple weapons |
| Wizard | School of Evocation | INT 13 | none |

Default BG3-style multiclass freedom bypasses the ability prerequisites only.
It never broadens an added-class proficiency package.

### 15.1 Cross-class foundation decisions

The audits make these decisions part of the present foundation:

1. Extra Attack resolves the strongest **applicable** grant. Monk/Paladin/
   Ranger ordinary Extra Attack does not add to Fighter Extra Attack. Monk
   Flurry, Ranger Horde Breaker/Volley/Whirlwind, Rogue extra turns, creature
   Multiattack, and Haste remain distinct. Future Thirsting Blade is scoped to
   the pact weapon.
2. Unarmored Defense remains first-acquired exclusive. Reordering Barbarian and
   Monk during respec changes which formula exists; both are never installed.
3. Channel Divinity options union and capacity is the maximum explicit
   entitlement. Each option retains its provider/DC.
4. Fighting Style selections are unique across sources.
5. Every class keeps exact spell entitlement/provider identity even when normal
   slots aggregate or a different legal pool pays.
6. Multiclass proficiency packages may contain typed choices.
7. Optional reactions/riders require explicit replayable decisions with player
   and AI authority. The first class that needs a general decision window owns
   that API; the first four do not ship an unused global service.
8. Every actual turn has a causal `TurnExecutionId`; features do not reset
   through named marker conditions.
9. Full body/form changes keep one Entity and one permanent root binding. F1
   introduces one active resolved form, not a priority-stacked provider system.
10. Spell list membership, school, acquisition provenance, and learned/copied
    knowledge use exact content identities.

### 15.2 Monk / Way of the Open Hand

Progression ledger:

| Level | Required grants/choices |
| ---: | --- |
| 1 | Martial Arts d4, Unarmored Defense |
| 2 | Ki 2, Flurry, Patient Defense, Step of the Wind, +10 movement |
| 3 | Open Hand, Deflect Missiles |
| 4 | ASI, Slow Fall |
| 5 | Extra Attack, Stunning Strike, Martial Arts d6 |
| 6 | Ki-Empowered Strikes, Wholeness of Body, +15 movement |
| 7 | Evasion, Stillness of Mind |
| 8 | ASI |
| 9 | vertical/liquid movement |
| 10 | Purity of Body, +20 movement |
| 11 | Martial Arts d8, Tranquility |
| 12 | ASI |
| 13 | Tongue of the Sun and Moon |
| 14 | Diamond Soul, +25 movement |
| 15 | Timeless Body |
| 16 | ASI |
| 17 | Martial Arts d10, Quivering Palm |
| 18 | Empty Body, +30 movement |
| 19 | ASI |
| 20 | Perfect Self |

Required later seams/tests:

- a source-owned attack-formula candidate for weapon qualification, STR/DEX
  selection, replacement Martial Arts die, and armor/shield applicability;
- typed decisions for Open Hand riders, Stunning Strike, Deflect Missiles,
  Diamond Soul, and Quivering Palm;
- rest recovery that proves at least 30 minutes of meditation;
- Unarmored Defense order/respec and Extra Attack-versus-Flurry matrices;
- deletion of the dormant incorrect DEX+STR/shield-compatible Monk AC branch
  when this class migrates.

### 15.3 Paladin / Oath of Devotion

Progression ledger:

| Level | Required grants/choices |
| ---: | --- |
| 1 | Divine Sense, Lay on Hands |
| 2 | Fighting Style, CHA half-caster source, Divine Smite |
| 3 | Divine Health, Oath of Devotion, oath spells, Channel Divinity |
| 4 | ASI |
| 5 | Extra Attack |
| 6 | Aura of Protection |
| 7 | Aura of Devotion |
| 8 | ASI |
| 9 | rank-3 spells |
| 10 | Aura of Courage |
| 11 | Improved Divine Smite |
| 12 | ASI |
| 13 | rank-4 spells |
| 14 | Cleansing Touch |
| 15 | Purity of Spirit |
| 16 | ASI |
| 17 | rank-5 spells |
| 18 | aura radius 10→30 feet |
| 19 | ASI |
| 20 | Holy Nimbus |

Required later seams/tests:

- `spellcasting_feature_class_level=2` and the section 4.8 generous boundary
  matrix;
- prepared count `max(1, CHA modifier + floor(Paladin level / 2))` and exact
  oath always-prepared levels;
- Divine Smite as a selected legal normal-slot payment, not one handler per
  rank that silently burns the highest slot;
- variable Lay on Hands allocation and typed poison/disease selection;
- source-aware Channel Divinity option/DC, exact equipped-item attachment for
  Sacred Weapon, and shared-capacity Cleric combinations;
- typed aura applicability, consciousness/radius scaling, and overlapping
  nonstacking behavior.

### 15.4 Ranger / Hunter

Progression ledger:

| Level | Required grants/choices |
| ---: | --- |
| 1 | Favored Enemy, Natural Explorer |
| 2 | Fighting Style, WIS half-caster source, two spells known |
| 3 | Hunter choice, Primeval Awareness, three known |
| 4 | ASI |
| 5 | Extra Attack, four known |
| 6 | second favored enemy/terrain |
| 7 | Defensive Tactics choice, five known |
| 8 | ASI, Land's Stride |
| 9 | rank-3 spells, six known |
| 10 | third favored terrain, Hide in Plain Sight |
| 11 | Volley or Whirlwind, seven known |
| 12 | ASI |
| 13 | rank-4 spells, eight known |
| 14 | third favored enemy, Vanish |
| 15 | Superior Hunter's Defense choice, nine known |
| 16 | ASI |
| 17 | rank-5 spells, ten known |
| 18 | Feral Senses |
| 19 | ASI, eleven known |
| 20 | Foe Slayer |

Required later seams/tests:

- `spellcasting_feature_class_level=2`, known/replacement policy, and WIS
  provider;
- Hunter choices at 3/7/11/15 as exact structural choices;
- `OWNER_TURN` for Horde Breaker/Foe Slayer and `ANY_ENCOUNTER_TURN` for
  Colossus Slayer-style riders;
- exact `CreatureType` or selected humanoid `species_ref` matching for Favored
  Enemy;
- explicit typed deferral for travel/terrain/tracking features until campaign
  systems exist;
- no companion subsystem in the SRD Hunter tranche.

### 15.5 Bard, Rogue, and Wizard

These three classes require the generic ability-check resolver and turn identity
before class work begins.

**Bard / College of Lore** later requires:

- source-owned Bardic Inspiration with Charisma-derived capacity, die scaling,
  expiry, changing recovery at Bard 5, and one exact die owner;
- Jack of All Trades as half proficiency on any otherwise-unproficient ability
  check, including initiative;
- Expertise over skill/tool subjects;
- optional Cutting Words/Peerless Skill decision windows;
- Magical Secrets as exact Bard entitlements with feature provenance;
- known-spell ritual policy and full-caster ESL.

**Rogue / Thief** later requires:

- Sneak Attack once per actual `ANY_ENCOUNTER_TURN`, including a separate
  opportunity-attack turn, with a cold typed finesse/ranged weapon-property
  snapshot on `AttackEvent`;
- Reliable Talent through the generic proficiency resolver;
- Cunning Action/Fast Hands through `AlternativeActionCostGrant`, competing for
  the ordinary bonus action;
- Expertise in skills or thieves' tools;
- optional Uncanny Dodge/Stroke of Luck decisions;
- Thief's Reflexes as a second actual turn, never Extra Attack.

**Wizard / School of Evocation** later requires:

- exact Wizard spell list/school metadata and INT full-caster source;
- physical spellbook holdings, active-book loadout, stable level-choice entries,
  copied-entry campaign transactions, loss behavior, and spellbook rituals;
- Arcane Recovery as a once-per-day end-of-short-rest bounded allocation;
- copied entries surviving respec and structural entries reconciling
  transactionally without touching unrelated holdings;
- Wizard added as a multiclass requiring an explicit book grant/ownership
  adjudication rather than silently receiving all starting equipment.

### 15.6 Warlock / The Fiend

Warlock later uses:

- a separate exact Pact slot pool with slot count/rank table and short-rest
  recovery;
- bidirectional legal payment between normal and Pact pools while preserving
  the chosen spell provider;
- invocation prerequisites/replacements through the neutral expression tree;
- Pact Boon exact choices and source-owned item/companion lifecycles;
- Mystic Arcanum at 11/13/15/17 as fixed-rank feature-use entitlements;
- Eldritch Master restoring the exact Pact pool;
- Thirsting Blade as a pact-weapon-scoped multiplicity grant.

Required future gates include two distinct payment affordances when both pools
are legal, Counterspell pool selection, provider/DC stability, Mystic Arcanum
using no slot, invocation replacement cleanup, and feature-bound object/
creature teardown.

### 15.7 Druid / Circle of the Land

Druid later uses the active-form and deferred character-knowledge seams:

- extract a pure `CreatureBodyTemplate` consumed by NPC construction and form
  resolution; this is nested creature-definition data in the existing content
  registry, not a new content kind or registry, and it never materializes a
  hidden replacement Entity;
- `ActiveCreatureForm` retains the same Entity/root identity and carries the
  exact form ref, source grant, duration, form HP/HD reservoir, equipment
  dispositions, and suppressed-feature receipt;
- retain mental scores, replace physical base scores, union proficiencies under
  exact higher-bonus rules, and retain concentration while restricting new
  casting according to component/body capability;
- damage consumes form HP, reverts, and applies overflow to base Health in one
  causal lineage; healing while transformed targets form HP;
- each item has a typed `merge | wear | drop` disposition; merged effects are
  suppressed rather than uninstalled;
- eligibility uses exact rational CR, creature type, learned creature ref, and
  typed body capabilities;
- projection/replay carries exact transform/revert identity and presentation;
- grid occupancy for Large+ forms is an explicit prerequisite, not a one-cell
  approximation.

Playable Druid is the first concrete consumer that adds
`CharacterKnowledgeRevision`: observed exact beast refs survive respec, remain
content-set authenticated, and are deployment-pinned. The earlier fixed-form
NPC needs no durable knowledge. Natural Recovery adds bounded pool allocation.
Circle of the Land is the SRD 5.1 subclass; Circle of the Moon is outside this
first Druid tranche.

Before the full playable Druid tranche, implement one authored non-player Druid
as the concrete active-form proof. It is ordinary content using a generic
`CreatureFormAction`; it is not a hidden partial player-class implementation.
Its definition selects one installed, audited Small/Medium beast body template
and exact authored use count/duration/recovery. The implementation must prove:

- the NPC keeps one Entity UUID, root creature ref, faction, controller, turn,
  conditions, concentration state, and event ancestry;
- the form provides one internally consistent resolved snapshot of physical
  scores, form HP/HD, size, movement, senses, anatomy, body attacks, and
  presentation;
- mental scores and unrelated permanent grants remain on the underlying Entity;
- damage consumes form HP, forced reversion and overflow happen in one causal
  lineage, and voluntary reversion removes the same receipt;
- healing in form affects form HP;
- every equipped item receives one explicit `merge | wear | drop` disposition
  and reversion restores only what that receipt suppressed;
- the AI can lawfully choose transform, form actions, movement, and reversion
  through the normal policy interface;
- subjective/objective projection carries exact form identity and typed
  transform/revert presentation;
- replay reproduces the same form boundary and final base state;
- repeated transform/revert cycles leak no block, handler, action, modifier,
  registry object, or stale presentation fact.

This vertical slice intentionally does not implement Druid preparation,
Circle of the Land, Natural Recovery, arbitrary learned-form selection,
Large+ occupancy, or the complete SRD Wild Shape eligibility table. Those stay
in the future class tranche and cannot be advertised by the NPC.

### 15.8 Audit regressions retained for future class work

Before any audited class is declared implementable, its focused suite owns:

- class-order proficiency packages and every class ASI level;
- Extra Attack/applicability/non-attack alternatives;
- partial/full/Expertise checks, initiative, tools, and source removal;
- once-per-turn behavior across opportunity attacks and multiple real turns;
- normal/Pact payment matrix and provider-specific maximum spell rank;
- selected optional feature timing and resource reservation;
- resource maximum/recovery changes without refill;
- spellbook copy/loss/respec/ritual behavior;
- active-form identity, HP, abilities, conditions, equipment, projection,
  replay, and cleanup;
- durable knowledge and feature-bound item/creature preservation.

## 16. Test strategy

All tests are targeted files; do not run bare `pytest`. Test names below are
planned authoritative owners, not a requirement to preserve obsolete numbered
filenames.

### 16.1 Pure rules tests

Create `tests/progression/test_character_build_rules.py`:

- every valid/invalid 27-point allocation;
- cost boundaries and distinct +2/+1;
- ability maximum at creation and ASI;
- contiguous ordered class-level entries;
- resulting per-class level;
- subclass timing/stability;
- first-class versus added-class grants;
- total-level proficiency at every transition;
- class ASI schedules;
- required/unexpected/duplicate choices;
- exact content-set and ruleset digest validation;
- permissive prerequisite bypass versus SRD prerequisite enforcement;
- deterministic validation and preview digest.

Create `tests/progression/test_multiclass_spell_slots.py`:

- full/full, full/half, full/third, half/half, third/third;
- strict 5.1 versus selected 5.2-style half-caster rounding boundaries;
- Paladin/Ranger feature-start gate and no one-level-dip slots;
- Paladin 3/Ranger 3 subtotal rounds once to ESL 3;
- Sorcerer 3/Paladin 3 yields ESL 5 under default and ESL 4 under strict;
- rank ceiling by individual class;
- upcast through higher shared slot;
- exact source ability/DC for same spell;
- total-level cantrip scaling;
- exact normal-slot cost/spend and Counterspell consuming its selected rank;
- at-will and ritual actions consume no normal slot;
- Sorcery Point conversion.

Create `tests/progression/test_mixed_hit_dice_and_hp.py`:

- all first-class dice;
- mixed dice in both orders;
- only ordinal 1 maximized;
- Constitution increase/decrease across all levels;
- short-rest spending by die type;
- remove/reapply/respec preserving invariant counts.

### 16.2 Generic contribution tests

Create `tests/progression/test_grant_receipts.py`:

- deterministic grant IDs;
- two providers of the same proficiency/action/spell;
- exact provider removal;
- resource contributions and recovery policy;
- recomposition maximum change preserving spent/current resource state;
- AC candidate competition;
- Extra Attack highest-applicable policy and scoped weapon/body grant;
- condition/handler/action cleanup;
- reverse dependency removal order;
- apply failure rollback;
- same Entity UUID recompose;
- repeated apply rejected or idempotent by contract;
- no leaked BaseObject/EventQueue registry entries.

### 16.3 Persistence tests

Extend or create focused files for:

- forward migration from current schema;
- schema-1 premade → schema-2 build/loadout migration, receipt, idempotency,
  unknown-premade failure, and unchanged holdings;
- final `characters` table rebuild with no stale `preset_configuration_id`;
- profile setting defaults and CAS;
- profile policy changes affecting new characters only while existing
  level-up/respec remains pinned to its authenticated ruleset;
- one physical SQLite DB per local profile;
- no cross-profile character reads;
- definition schema 2 digest tamper rejection;
- append definition revision CAS;
- advancement award idempotency;
- atomic creation of level award + definition + holdings + loadout;
- level-up head update with unchanged holdings;
- ordinary respec head update with unchanged holdings;
- structurally owned spellbook-entry reconciliation preserving copied entries
  and unrelated holdings;
- atomic loadout revision 1 creation and three-head invariant;
- prepared-spell loadout append with unchanged definition/holdings;
- level-up/respec loadout preservation and invalid-selection pruning;
- deployed loadout pin and stale preparation CAS;
- immutable old revisions;
- active lease rejection;
- stale race between level-up/respec/settlement;
- injected failures after each SQL write with full rollback;
- existing artifact-store replay digest/import/export integrity;
- exactly-once settlement receipt and holdings delta;
- restart and reopen persistence;
- hosted repository behavior parity with local profile mode.

### 16.4 Per-class table tests

Use data-driven level rows for each class:

```text
tests/progression/test_fighter_progression.py
tests/progression/test_barbarian_progression.py
tests/progression/test_sorcerer_progression.py
tests/progression/test_cleric_progression.py
```

Each level asserts focused derived facts:

- exact automatic grants;
- required choices;
- resource maxima;
- attack count/critical/AC policies;
- spell counts/ranks/slots where applicable;
- feature source IDs;
- apply/remove behavior.

Avoid whole serialized Entity snapshots and tests whose sole value is exact
test-count or documentation parity.

### 16.5 Cross-class matrix

Create `tests/progression/test_multiclass_composition.py` with:

- all ordered pairs of the four classes at representative boundaries;
- all three existing classes before Cleric gate;
- first-class save/proficiency differences;
- overlapping Extra Attack;
- overlapping AC candidates;
- mixed dice/HP;
- martial proficiency attack math;
- caster/martial and caster/caster source isolation;
- respec among distributions;
- total-level feature behavior;
- no order-dependent result except rules that explicitly depend on class order.

Use pairwise coverage for the full level grid and hand-authored semantic cases
at important feature boundaries; do not create an unmaintainable Cartesian
whole-Entity golden.

### 16.6 API and SDK tests

Server tests:

- catalog exact closed schema and content refs;
- validation error paths and codes;
- preview/commit digest identity;
- profile ownership and local mode;
- stale/idempotent mutation behavior;
- active deployment rejection;
- exact launch definition/holdings/loadout revision pinning;
- absence of legacy/premade-only creation and duplicate hero-configuration
  authority;
- OpenAPI exact route family and no aliases.

SDK tests:

- generated descriptor parity;
- exact request method/path/query/body;
- strict decode and unknown-field rejection;
- error union narrowing;
- all choice union cases;
- digest and bigint/integer handling;
- local-profile and hosted client use the same DTOs.

### 16.7 Runtime and replay tests

- materialize pinned definition + holdings + loadout into an Entity;
- play representative turns with each class;
- rest/resource recovery;
- AI chooses class features and spells using exact affordance semantics;
- record and replay class action/event/presentation chains;
- respec-created character starts a **new** deployment while an old replay
  remains valid against old revision/content pins;
- settlement after a completed game changes only holdings;
- imported replay never mutates character/profile state.

### 16.8 Cleric-specific rules tests

At minimum:

- prepared count with Wisdom changes and multiclassing;
- domain spells always prepared and excluded from count;
- long-rest versus out-of-combat preparation policy;
- holy-symbol focus versus priced/consumed material components;
- ritual prepared requirement, no slot, time advancement, and typed unavailable
  behavior when its prerequisites are absent;
- Channel Divinity use scaling/recovery;
- Turn Undead range/sensory checks, mixed saves, action/reaction/movement
  restrictions, ten-round duration, and positive-damage removal;
- Destroy Undead CR/type thresholds at every scaling level;
- Preserve Life allocation, range, undead/construct rejection, half-HP cap,
  unused budget, invalid allocation, and transaction rollback;
- Disciple of Life base/upcast/multi-target/nonqualifying sources;
- Disciple/Blessed cross-class healing-spell applicability;
- Blessed Healer once-per-cast deduplication, non-recursion, and other-target
  restriction;
- Supreme Healing exact dice maximization;
- Divine Strike optional toggle, once per own turn across Extra
  Attack/Haste/Action Surge, OA exclusion, level-14 scaling, and critical dice;
- Spare the Dying lifecycle lineage;
- Spiritual Weapon summon/move/repeat bonus-action attack;
- Revivify/Raise Dead time/body/material/lifecycle and atomic material rollback;
- Divine Intervention failure/long-rest retry, success/seven-day lock,
  level-20 auto-success, resolver/clock unavailable, AI, and replay;
- same Cleric spell selected from Sorcerer and Cleric source;
- every implemented Cleric spell's focused behavior;
- every adapted spell's adjudication ID;
- ledger completeness: every SRD Cleric spell has exactly one status.

### 16.9 Architecture and performance gates

Static gates fail on:

- `dnd/core/progression.py` or durable content leaves importing
  Entity/server/concrete content;
- Entity/components importing `dnd.classes`;
- local imports or `TYPE_CHECKING` in progression/class changes;
- unaudited dynamic imports;
- class appliers unregistering by display name;
- serialized Python paths/callables;
- content definitions lacking exact refs/contract hashes.

Benchmarks record:

- creator catalog cold/warm time and payload size;
- validation p50/p95 for level 1, level 20, and multiclass level 20;
- materialization time for those builds;
- SQLite level-up/respec transaction duration and query count;
- content-registry resolution count;
- memory/registry-object delta before/after repeated recompose.

Set regression thresholds only after a stable baseline is measured; never make
an unmeasured “fast enough” claim.

## 17. Implementation phases

### Phase 0 — Freeze decisions and write red tests

- approve this plan;
- add the ruleset policy model and exact citations;
- finish Cleric progression/spell/adjudication audit;
- freeze the eight-class forward-audit decisions in section 15 without
  implementing those classes;
- create `KNOWN_ISSUES.md` entries only for concrete discovered defects, each
  with its red reproducer;
- establish performance baselines;
- add dependency-direction gates.

Exit: selected policies have no unresolved semantic ambiguity needed by
foundations.

### Phase 1 — Profile and schema foundations

- local profile manager and safe physical layout;
- extract the existing cold character operations into one shared
  service/router;
- profile settings migration;
- advancement-award migration;
- CharacterDefinitionRevisionV2;
- CharacterLoadoutRevisionV1;
- one generalized three-head repository revision-bundle CAS;
- extend the existing deployment pins and delete the unpinned path after
  migration;
- reuse games/artifacts/summaries with `execution_kind=local`;
- add one exactly-once character settlement receipt;
- local/hosted repository parity tests;
- root the existing `GameArtifactStore` inside the local profile.

Exit: a profile can atomically create/read a schema-2 level-1 character and its
definition, holdings, and loadout heads, then reopen all three after
restart; no class is migrated yet.

### Phase 2 — Neutral progression and composition

- dependency-neutral contracts;
- source-owned component APIs;
- thin receipts over existing component cleanup handles;
- class/species/background typed definitions and runtime bindings in the
  existing `FrozenContentRegistry`;
- build validator and preview;
- extend the existing `materialize_character` entry point plus focused
  same-Entity apply/remove proof;
- mixed hit dice/proficiency/AC/Extra Attack policies;
- existing skill/save event paths plus causal turn identity/small usage guard;
- exact source-owned resources/recovery needed by the delivered classes;
- per-source casting and ESL-derived base maxima on existing normal slot values.

Exit: synthetic test definitions prove every runtime primitive needed by the
first four classes without concrete class imports. Future-only choice DTOs,
Pact/payment/spellbook runtimes, generic ability-check/optional-decision
transport, knowledge, and form behavior are not part of the first SDK or
falsely advertised as executable.

### Phase 3 — Fighter hard cut

- author Fighter/Champion definitions;
- migrate features and premades;
- add all table/feature tests;
- remove Fighter production factory path.

Exit: Fighter levels 1–20 and Fighter-related multiclass primitives are green.

### Phase 4 — Barbarian hard cut

- author Barbarian/Berserker definitions;
- migrate features and premades;
- prove AC/Rage/Extra Attack semantics;
- remove Barbarian production factory path.

Exit: Fighter/Barbarian both orders, level-up, and respec are green.

### Phase 5 — Sorcerer hard cut

- author Sorcerer/Draconic definitions;
- migrate known spells/metamagic/resources;
- land per-source casting and shared slots in production;
- migrate premades;
- remove Sorcerer factory and baked slot path.

Exit: all three existing classes pass section 13.

### Phase 6 — Character APIs and SDK freeze

- freeze creator, validate, creation, level-up, respec, and history routes;
- remove old premade-only request shape and duplicate scenario hero config
  authority;
- generate SDK;
- provide one exact frontend handoff.

This phase may overlap UI work only after the schema and route tests freeze.

### Phase 7 — Cleric adjudications and primitives

- finalize SRD progression and spell ledger;
- approve every required adjudication;
- implement missing generic healing/undead/allocation/divine-intervention
  primitives without putting Cleric branches in Entity;
- test primitives synthetically.

Exit: Cleric definition needs only public extension surfaces.

### Phase 8 — Cleric and Life Domain

- author definitions/bindings;
- implement all base/domain features;
- implement/land the agreed spell set;
- AI and presentation semantics;
- progression/cross-class/replay tests.

Exit: Cleric proves a new pack-authored class can be added without modifying
core ownership.

### Phase 9 — Cleanup and migration close

- migrate all persisted local development characters or provide an explicit
  one-time schema1→schema2 command;
- delete schema-1 runtime materialization after migration;
- delete all one-shot class factory production code;
- delete retired DTOs/routes/tests/generator filters;
- update architecture docs;
- run targeted final gates and record performance comparison.

Exit: repository search proves one character path.

### Follow-up Phase F1 — Active-form NPC vertical slice

This is the first bounded follow-up after the four-class release and must land
before playable Druid:

- extract one pure audited Small/Medium `CreatureBodyTemplate` from installed
  creature content;
- implement one class-neutral active resolved-form runtime from this concrete
  consumer; do not add a provider stack or a form registry;
- author one non-player Druid with the bounded `CreatureFormAction`;
- implement typed form HP/equipment/reversion event semantics;
- map exact subjective/objective transform and revert presentation;
- teach the normal AI policy to consider the authored action;
- add semantic, privacy, replay, cleanup, and repeated-cycle performance tests.

Exit: the section 15.7 NPC completes a live AI-driven transform→form
action→damage/revert sequence with one Entity identity and deterministic replay.
No playable Druid class or compatibility form path exists.

## 18. File ownership map

Expected new/changed areas:

```text
dnd/core/progression.py                      extend pure rules/tables
dnd/core/content/identities.py               new definition kinds
dnd/core/content/durable_characters.py       schema-2 build/loadout contracts
dnd/core/content/{registration,registry}.py  typed definitions in one registry
dnd/blocks/{skills,saving_throws,...}.py     source-aware generic APIs
dnd/blocks/spellcasting.py                   source-specific casting
dnd/blocks/action_economy.py                 owned resource contributions; existing slots
dnd/blocks/health.py                         mixed ordered hit-die support
dnd/blocks/equipment.py                      typed AC candidates
dnd/active_creature_form.py                  F1 only, one resolved active form
dnd/entity.py                                class-neutral owner APIs only
dnd/content_system/character_materialization.py  sole materializer
dnd/content_system/*                         existing definition/binding runtime
dnd/character_build.py                       validator + structural apply/remove
dnd/classes/{fighter,barbarian,sorcerer}.py  authored definitions/bindings
dnd/classes/cleric.py                        new declarative Cleric bindings
dnd/spells/*                                 missing exact spell behavior
server/game_directory/*                      extend existing revision transactions
server/character_directory_service.py        shared domain service
server/character_progression_routes.py        one shared router
server/local_profile_manager.py              local-only safe DB opener
server/game_summary_store.py                 shared typed terminal publication
server/event_server.py                       local in-process composition
server/game_gateway.py                       delegate extracted character operations
server/game_artifact_store.py                existing artifact owner
server/*contracts.py                         API DTOs
sdk/typescript/*                             generated client/contracts
content_data/ledgers/*                       source/completeness ledgers
agent_docs/rules/*                           exact adjudications
tests/progression/*                          authoritative focused tests
```

This map is not permission to put high-level class behavior into a low-level
file. Before any implementation phase, produce an import-direction sketch for
the touched modules and run the static gate.

## 19. Definition of done for the first release

The work is complete only when:

1. local single-player runs with one selected physical profile SQLite DB;
2. the same character repository/domain API serves hosted ownership;
3. profile settings `permissive_multiclass_prerequisites` and
   `multiclass_slot_rounding_policy` are durable and
   ruleset-authenticated;
4. character creation supports the SRD playable species catalog, background,
   point buy, flexible +2/+1, and exact level-1 class choices;
5. level-up can add a level to any implemented class up to total level 20;
6. multiclass rules, first-class grants, proficiency, HP, Extra Attack, AC, and
   spell slots—including the selected generous half-caster boundaries—follow
   the selected policy;
7. respec rebuilds an existing character without changing its ID, origin,
   holdings, earned level, or history;
8. prepared spells persist in an independent immutable loadout, and both
   preparation policies behave exactly;
9. the cold same-Entity proof can remove/reapply structural grants
   without leaks;
10. Fighter, Barbarian, and Sorcerer have no production one-shot factory path;
11. Cleric/Life Domain is authored entirely through the same extension surface;
12. every SRD Cleric spell has a ledger disposition and every implemented or
    adapted row has tests;
13. all character mutations are immutable revisions with CAS/idempotency and
    deployment fencing;
14. replay bundles remain portable through the existing artifact store and old
    deployments/replays remain pinned;
15. loot settlement updates holdings only and exactly once;
16. the generated SDK exposes one exact route/model family;
17. frontend can show every automatic grant, choice, description, icon,
    availability blocker, and before/after derived preview without inference;
18. import, targeted behavior, persistence, SDK, AI, presentation, replay, and
    performance gates are green;
19. searches find no compatibility alias, duplicate authority, late import,
    class import in Entity/components, or production reference to retired
    factories.

## 20. Explicit non-goals

- no authentication/provider selection redesign;
- no deployed Postgres/multitenant implementation in this chunk;
- no real shop, economy, XP curve, or reward-content design;
- no full character-creator frontend implementation in the backend phases;
- no arbitrary mod sandbox or untrusted Python execution;
- no runtime Bard/Druid/Monk/Paladin/Ranger/Rogue/Warlock/Wizard implementation
  in this first four-class delivery; their required contracts are reserved and
  tested without advertising executable class content;
- no silent implementation of every non-tactical Cleric spell;
- no mutation of active encounter state during profile respec;
- no embedding replay event payloads into profile SQL;
- no map-editor/isometric-asset redesign.

The contracts leave these additions possible without making the first delivery
depend on them.

## 21. Decisions that must not be reopened accidentally

- `species` is an authored identity; `CreatureType` is not repurposed.
- flexible +2/+1 belongs to the character build, not species.
- class progression is an ordered additive ledger, not a final class-level map.
- automatic grants are derived, not serialized as fake player choices.
- holdings, structural definition, and mutable persistent loadout remain
  independently revised and jointly pinned for deployment; knowledge is added
  only with its first real playable consumer.
- respec preserves origin and holdings and spends no new earned levels.
- shared normal slots derive from ESL; each class retains its casting source;
  spell entitlement/provider and selected payment pool are separate facts.
- eligible half-caster levels use the section 4.8 generous round-up subtotal
  under the default profile policy and the normative round-down subtotal under
  `srd_5_1_round_down`.
- temporary full forms use one resolved active-form seam; permanent Entity
  blocks and root content binding are never swapped or rebuilt, while partial
  transforms keep using existing modifier/transform primitives.
- source-owned contributions replace name-based cleanup.
- class features reuse generic modifiers/conditions/actions; no modifier
  megaregistry is introduced.
- existing classes migrate before Cleric.
- Cleric ambiguity is resolved in reviewed adjudications, not buried in code.
- local and hosted persistence share one repository/domain implementation.
- replay payloads remain portable through the existing content-addressed
  artifact store.
- there is one canonical API/SDK path and no compatibility aliases.
