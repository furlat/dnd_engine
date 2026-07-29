# Creature, Character, Roster, and Saved Encounter Hard Cut

**Date:** 2026-07-28  
**Status:** Public/runtime hard cut implemented; generated SDK, frontend
adaptation, live migration, and normal-port validation complete  
**Scope:** Replace the evaluation-shaped public game-creation ontology without
rewriting the working content, character, AI, replay, or worker foundations.

## 0. Implementation record (2026-07-29)

The implemented single path is:

```text
catalog selection
  -> POST /game-creation/compose
  -> exact EncounterRecipe + compatibility + production preview
  -> POST /game-creation/start (standalone)
     or POST /games (hosted)
  -> the same exact recipe in worker/local materialization
```

Implemented:

- dependency-neutral roster/member/controller/deployment/encounter recipes;
- lossless authored catalog for the prior 58 configurations, 141 actors, and
  38 encounters;
- one neutral compatibility checker and one assembler;
- ordered multi-character rosters with Human, native AI, and Codex controller
  defaults/overrides that never change member sources;
- plural character ownership resolution, atomic leases, exact revision-head
  pinning, runtime assignment, terminal settlement, and release;
- identical standalone and hosted recipe transport;
- owner-scoped SQLite saved-roster and saved-encounter CRUD with CAS;
- `saved_roster` as an authenticated composer selection using exact saved
  revision and recipe digest, so saved rosters are reusable rather than dead
  storage;
- isolated production projection from the exact normalized recipe;
- canonical TypeScript clients for catalog, compose, preview, exact start, and
  saved roster/encounter documents;
- deletion of the former public preflight/configuration-preview routes and
  public hero/monster/preset/composed DTO exports.

Two implementation details intentionally differ from the initial sketch:

1. There is no separate public preflight route. `compose` is the sole
   normalization boundary and returns the compatibility report and preview
   beside the exact recipe. `preview` accepts only that already-normalized
   recipe and never normalizes again.
2. The historical evaluation-shaped specifications remain only as cold
   authored-content inputs and rating/evaluation metadata. They are converted
   into canonical recipes before compatibility, preview, start, persistence,
   or SDK exposure. They are not a second runtime or public transport path.
   The former evaluation runtime assembler has been deleted; isolated rating
   and promotion workers now cross the canonical `EncounterRecipe` assembler.

Still intentionally after this freeze:

- general creature-plus-class-level champion authoring (Phase 6);
- removing the remaining cold evaluation authoring records after their useful
  rating metadata has a neutral owner;
- registered-provider AI propagation/capacity brokering across hosted workers.

None of those requires or justifies retaining a second public game-creation
path.

## 1. Decision

The product domain has five concepts:

1. **Creature definition/recipe**
   - An authored `ContentDeclaration(kind=creature)` plus an exact
     `ContentRecipe`.
   - Covers monsters, NPCs, class-neutral bodies, configured variants, and
     authored champions.
2. **Character**
   - A durable, principal-owned build with exact definition, holdings, loadout,
     appearance, advancement, and presentation-preference revisions.
3. **Champion**
   - Not a new registry or durable record type.
   - An authored creature recipe whose construction applies an exact ordered
     class/progression ledger over a permitted creature root.
   - Current Barbarian/Fighter/Sorcerer fixtures already fit the public shape:
     they are exact creature roots that delegate to the canonical character
     materializer.
4. **EncounterRoster**
   - A small ordered group of exact creature recipes and/or owned character
     references.
   - “Group,” “party,” and “cell” are display vocabulary, not different
     mechanical types.
5. **SavedEncounter**
   - Exact roster slots plus battlefield, deployment, controller/policy
     defaults, opening policy, and authored setup facts.

`SideConfigurationSpec`, `ActorBlueprint`, `hero_configuration_id`,
`monster_configuration_id`, the `preset | composed` union, and literal
`side_a | side_b` product fields are removed from public contracts. They do not
survive as aliases.

## 2. What is already canonical and must be reused

### 2.1 Creature construction

Keep:

- `ContentRecipe`;
- `ContentDeclaration(kind=creature)`;
- `materialize_creature()`;
- `CreatureBuildContext`;
- `CreatureRuntimeBinding`;
- exact `Entity.content_ref`;
- default-possession and structure-only possession modes;
- content-pack registration and startup closure.

There is no need for another creature, monster, NPC, or champion registry.

### 2.2 Characters

Keep:

- `CharacterDefinitionRevisionV2`;
- `CharacterHoldingsRevision`;
- `CharacterLoadoutRevisionV1`;
- `CharacterDeploymentSnapshot`;
- advancement awards and profile rules;
- optimistic revision heads;
- deployment leases and pinned deployment records;
- terminal holdings settlement;
- `CharacterCreationPlan` as the editable creator seed;
- `CharacterCompositionReceipt` and source-owned reversible grants.

`CharacterDefinitionRevisionV2.body_recipe` already makes the character's
creature body explicit. `class_levels` already provides the ordered additive
progression ledger.

### 2.3 Infrastructure

Keep:

- standalone SQLite and hosted directory repositories;
- replay files and artifact records;
- game history and summaries;
- worker prewarming, content-digest fencing, and terminal evidence;
- native and registered-provider AI policies;
- canonical subjective replication and objective diagnostics;
- production entity/loadout projection and isolated previews.

This hard cut is composition cleanup, not a networking or replay rewrite.

## 3. What remains duplicated or evaluation-shaped today

### 3.1 Closed actor union

`dnd/scenarios/evaluation/models.py` owns a closed `ActorBlueprint` union:

- `BarbarianActorBlueprint`;
- `FighterActorBlueprint`;
- `SorcererActorBlueprint`;
- `BestiaryActorBlueprint`;
- `SrdMonsterActorBlueprint`.

`assembler.build_actor()` then dispatches by `isinstance`, reconstructs class
builds, maps bestiary archetype strings to creature refs, and maps SRD monster
IDs through another lookup.

This is a wrapper around the canonical recipe/materializer and prevents content
packs from entering game creation through the normal creature boundary.

### 3.2 Hero/monster configuration ontology

`SideConfigurationSpec`:

- hard-codes `side_kind = hero | monster_party`;
- requires exactly one member for heroes;
- owns evaluation/rating metadata;
- mixes a reusable roster with scenario setup augmentations;
- is exported directly in `GameCreationCatalogResponse`.

`DeploymentSpec` similarly hard-codes hero and monster slots and capacities.
Compatibility reports repeat the same vocabulary.

### 3.3 Persistent character substitution

Current game creation does not place a Character in a roster. It:

1. selects one hero configuration;
2. requires that configuration to contain exactly one member;
3. substitutes a `CharacterDeploymentSnapshot` for that member;
4. permits the character only in the composed hero seat.

Standalone and hosted workers each own singular
`character_deployment`/`character_snapshot` state. Terminal settlement is also
singular even though the directory tables already allow multiple pinned
deployments per game.

### 3.4 Historical preset leakage

The public `preset | composed` request exposes `LegacyScenarioRecipe` and
historical validation-arena vocabulary. The game directory persists that old
request in `creation_manifest`.

The historical encounters are valuable content. Their legacy transport shape
is not.

### 3.5 Preview coupling

The isolated preview correctly uses production projection, but it accepts a
`SideConfigurationSpec` ID and materializes an otherwise unrelated compatible
opponent and battlefield merely to preview one group.

A roster preview should materialize the requested roster directly in the
isolated worker.

## 4. Target dependency-neutral value models

Place mechanical recipe models in a dependency-neutral content leaf. They may
import content refs/recipes, UUIDs, equipment/life/condition leaves, and pure
progression contracts. They do not import `Entity`, server repositories,
routes, or services.

### 4.1 Roster member

```text
EncounterRosterMember
  member_id
  display_name
  source:
    AuthoredCreatureSource
      recipe: ContentRecipe(kind=creature)
    OwnedCharacterSource
      character_id: UUID
  scenario_setup_effects[]
```

There is intentionally no `hero`, `monster`, `NPC`, or `champion` member kind.
An authored champion is a creature recipe. A durable character is selected by
its character identity and resolved by the directory.

`scenario_setup_effects` is a closed exact union for genuinely encounter-local
facts:

- exact item/possession grant;
- exact condition application;
- typed starting damage;
- exact reaction/behavior grant where still required;
- explicit damage affinity;
- explicit resource state.

Spell, action, condition, reaction, item, and creature identity use exact
`ContentRef`/`ContentRecipe`, never Python class names or display names.

Creature-owned ordinary wardrobe, weapons, traits, spells, and possessions do
not belong in roster setup.

### 4.2 Encounter roster recipe

```text
EncounterRosterRecipe
  roster_id
  title
  members[]
  tags[]
  required_battlefield_capabilities[]
  forbidden_battlefield_capabilities[]
  recipe_digest
```

The digest authenticates ordered membership and every exact nested recipe.
Member IDs and deployment roles are roster-local and unique.

The same value is used for:

- built-in authored rosters;
- profile-owned saved rosters;
- preflight;
- preview;
- launch;
- the pinned game creation manifest.

### 4.3 Generic deployment

Replace hero/monster fields with named zones:

```text
EncounterDeploymentSpec
  deployment_id
  battlefield_id
  zones:
    zone_id
    ordered_slots[]
    role_slots[]
    max_members
  tags[]
  digest
```

An encounter roster slot selects one zone. Portable deployments can expose
neutral names such as `west` and `east`; authored encounters may use semantic
names. No role or zone implies that one side is a player or a monster.

### 4.4 Controller assignment

```text
RosterControllerDefaults
  controller: human | ai | codex
  participant_name
  policy_id?
  member_overrides:
    member_id
    controller
    policy_id?
```

This preserves the working native group controller optimization while allowing
separate policies/assignments per member. Registered-provider assignments
remain provider-side capacity authorities.

### 4.5 Encounter recipe

```text
EncounterRecipe
  encounter_id
  title
  roster_slots:
    roster_slot_id
    roster: EncounterRosterRecipe
    faction_id
    deployment_zone_id
    controller_defaults
  battlefield_id
  deployment_id
  opening_policy: initiative | roster_slot_id
  notable_positions[]
  tags[]
  recipe_digest
```

The game-start request carries this one exact shape. A built-in encounter and a
profile-saved encounter differ only in where the client obtained the recipe.
There is no `preset | composed` runtime union.

The game record pins the submitted recipe and the fully resolved launch plan in
its creation manifest. Editing a saved roster or encounter later cannot alter
an existing game or replay.

## 5. Authored champion implementation

Do not add a public `ChampionRecord`, `HeroConfiguration`, or champion registry.

### 5.1 Immediate bounded cut

Use the existing exact class creature roots:

- `creature.player.barbarian`;
- `creature.player.fighter`;
- `creature.player.sorcerer`.

Their typed recipe parameters replace the corresponding closed actor
blueprints. They already compose schema-2 character revisions and delegate to
`materialize_character()`.

This is sufficient to convert every current class fixture and mixed class
party without changing the public roster model.

### 5.2 General creature plus class levels

Complete the already-planned internal progression extraction:

1. player-origin grants:
   - chosen base abilities;
   - flexible `+2/+1`;
   - species/background/origin;
   - first-character-level assumptions;
2. ordered progression grants:
   - class/subclass schedule and choices;
   - ASIs/feats;
   - hit dice;
   - proficiencies;
   - actions/resources/handlers;
   - Extra Attack-family resolution;
   - spellcasting sources and slots;
   - one removable receipt.

A configured champion creature applies only progression grants over its exact
base creature stat block.

Explicit authored policies cover:

- proficiency bonus: maximum of stat block and level-derived value;
- added hit dice and first added-level HP;
- multiclass-style versus explicitly authored starting proficiencies;
- spell-slot contribution alongside innate/stat-block casting;
- added possessions.

The configured champion remains a creature declaration/recipe with its own
exact creature `ContentRef`; its base creature is an authenticated dependency.
Removing progression receipts leaves the base creature intact.

This internal enhancement does not change `EncounterRosterRecipe`.

## 6. Directory persistence

Add profile-owned SQLite records:

### 6.1 Saved roster

```text
SavedRosterRecord
  roster_id: UUID
  owner_principal_id
  revision
  recipe
  recipe_digest
  created_at
  updated_at
```

### 6.2 Saved encounter

```text
SavedEncounterRecord
  encounter_id: UUID
  owner_principal_id
  revision
  recipe
  recipe_digest
  created_at
  updated_at
```

Both use strict ownership and optimistic revision CAS. Built-in authored rows
remain content/catalog data, not copied into every profile DB.

The standalone profile DB and hosted directory use the same migrations,
repository methods, service, routes, and generated SDK.

## 7. Character resolution and settlement

Resolve every `OwnedCharacterSource` before engine mutation:

1. authenticate ownership;
2. require active canonical revisions;
3. acquire all character deployment leases atomically;
4. build an exact `CharacterDeploymentSnapshot` per selected member;
5. replace character references with trusted resolved member bindings;
6. pass the complete resolved launch plan to the worker;
7. materialize each character in its roster role;
8. pin every runtime entity/deployment pair;
9. on terminal completion, project and settle all character holdings in one
   directory transaction;
10. release all leases on every failure/terminal path.

Change singular seams to tuples/maps:

- hosted worker assignment;
- event-server hosted character authority;
- local game coordinator prepared state;
- runtime entity bindings;
- terminal holdings evidence;
- settlement bundle.

The existing `character_deployments` and lease tables already support multiple
characters per game. The orchestration code, not the storage model, is the
current restriction.

## 8. Public/API hard cut

### 8.1 Catalog

`GameCreationCatalogResponse` exposes:

- authored roster recipes;
- authored encounter recipes;
- battlefield specs;
- generic deployment specs;
- controller kinds and AI policy descriptors.

Individual creature discovery remains in the content catalog. Character
creation/selection remains in the character directory.

Remove:

- `hero_configurations`;
- `monster_configurations`;
- legacy presets;
- `SideConfigurationSpec`;
- actor blueprint models;
- hero/monster deployment fields.

### 8.2 Preflight

`POST /game-creation/preflight` accepts one exact `EncounterRecipe` and returns
a neutral report keyed by roster slot, roster/member role, battlefield,
deployment zone, and typed issue.

### 8.3 Preview

Replace the configuration-ID route with an isolated roster preview accepting
an exact roster recipe. A one-member roster is the creature/champion preview;
no second endpoint or synthetic entity path is needed.

The preview worker materializes only the selected roster and projects the same
`APIEntitySummary`/`EntityVisualLoadout` used in production.

### 8.4 Start/result

`GameCreationStartRequest` contains the exact encounter recipe and no top-level
`character_id`.

Character references live in roster members.

`GameCreationStartResponse` returns ordered roster results:

- roster slot identity;
- recipe digest/title;
- resolved controller/policy facts;
- member identity to runtime entity assignment;
- takeover/session facts where applicable.

No literal `side_a` or `side_b` remains. Directory membership stores the
roster-slot identity. Terminal winner identity uses the same value.

### 8.5 Hosted wrapper

`CreateHostedGameRequest` selects the owner's roster slot/member authority,
not `owner_side`. The gateway resolves character ownership and sends the worker
only trusted snapshots/resolved recipes.

Standalone and hosted call the same launch resolver and assembler.

## 9. Existing content conversion

Convert, without losing content:

- all 20 current hero configurations;
- all 38 current monster configurations;
- all 141 currently previewed actors;
- all 38 historical scenario recipes;
- all neutral and historical deployments;
- all typed scenario augmentations;
- every AI/rating schedule entry.

Conversion rules:

- class blueprint -> exact class creature recipe;
- bestiary blueprint -> exact bestiary creature recipe;
- SRD blueprint -> exact SRD creature recipe;
- ordinary creature wardrobe/possessions -> creature definition;
- genuinely scenario-local augmentation -> exact roster setup effect;
- `SideConfigurationSpec` -> `EncounterRosterRecipe`;
- `LegacyScenarioRecipe` -> authored `EncounterRecipe`;
- hero/monster deployment slots -> generic named zones.

During development, parity tests may compare old and new materialization. Before
the SDK freeze, delete the old models, catalogs, routes, exports, generator
roots, and compatibility tests. Do not ship a converter, alias, V2 route, or
dual request parser.

Historical replay files remain readable because they contain their own frozen
game/replay data. Development SQLite reset is a separate explicit user action;
the implementation must not silently delete profile data.

## 10. Implementation sequence

### Phase 1 — Neutral recipe models and exact conversion gates

1. Add dependency-neutral roster, deployment-zone, controller-default, and
   encounter recipe models.
2. Add digest and uniqueness validation.
3. Express current class/bestiary/SRD members as exact creature recipes.
4. Express all scenario-local augmentations with exact refs.
5. Build the full roster/encounter catalog.
6. Add exhaustive 58-configuration/141-actor/38-encounter preservation gates.

No SDK generation yet.

### Phase 2 — One generic resolver/assembler

1. Materialize every authored member through `materialize_creature()`.
2. Materialize character members through `materialize_character()`.
3. Apply only exact roster setup effects after all referenced members exist.
4. Replace hero/monster compatibility with neutral roster-slot/zone checks.
5. Assign controllers with roster defaults and per-member overrides.
6. Make evaluation/rating consumers use the same resolved recipe path.
7. Prove startup/materialization performance is not materially slower.

### Phase 3 — Directory rosters, encounters, and plural characters

1. Add saved roster/encounter migrations and CAS repositories.
2. Add owner-authorized services/routes.
3. Generalize hosted and standalone character snapshot/lease/pin state.
4. Settle multiple character holdings atomically.
5. Preserve character-to-game history and subjective replay membership joins.

### Phase 4 — Public hard cut and one SDK handoff

1. Replace game-creation catalog/preflight/preview/start/result contracts.
2. Replace hosted owner-side selection with roster-slot/member authority.
3. Remove old SDK methods/models rather than deprecating them.
4. Regenerate once after Python models/routes are closed.
5. Run generator check, SDK build/tests, standalone creation, hosted creation,
   preview census, AI matchups, character settlement, replay/history, and
   frontend adaptation gates.
6. Coordinate one backend restart only after NeuroClient reports green.

### Phase 5 — Delete the old ontology

**Implementation status:** the public ontology, compatibility path, runtime
assembler, generator exports, and transport tests are deleted. The remaining
`SideConfigurationSpec`/blueprint/legacy records are cold authoring and rating
metadata only, as recorded in implementation detail 2 above. Their eventual
removal is coupled to giving that rating metadata a neutral owner; they cannot
materialize a runtime actor.

Delete:

- `SideConfigurationSpec`;
- closed actor blueprint union and `build_actor()` dispatch;
- `LegacyScenarioRecipe`;
- public preset/composed union;
- hero/monster compatibility and deployment fields;
- singular hero character substitution;
- old generator exports and tests;
- old catalog dictionaries once no internal consumer remains.

The final source contains one game-creation path.

### Phase 6 — General authored creature champions

After the public hard cut is stable:

1. extract ordered progression application/removal;
2. author one Goblin or Veteran champion creature;
3. prove base stat-block preservation;
4. prove add/remove/reapply and rollback;
5. prove Extra Attack-family uniqueness and multiclass slots;
6. expose it automatically through the ordinary creature/roster catalog.

No game-creation schema change is required.

## 11. Required regression gates

Every defect or incomplete behavior remains measured according to
`KNOWN_ISSUES.md` policy.

Required green gates before deletion:

1. exact roster/encounter digest determinism;
2. all 58 prior configurations and 141 actors preserved;
3. all 38 historical encounters preserved mechanically;
4. no closed actor-family dispatch remains;
5. no public hero/monster/side-A/side-B model remains;
6. content-pack creature recipe enters a roster without engine code changes;
7. persistent Character vs authored roster, native AI;
8. persistent Character vs authored roster, registered-provider AI;
9. authored champion vs roster, AI vs AI;
10. different external AI assignment per member;
11. multiple owned characters lease, pin, deploy, settle, and release atomically;
12. stale character/roster/encounter revision fails before engine replacement;
13. setup-effect rollback leaves no partial runtime;
14. neutral deployment checks capacity, role mapping, bounds, occupancy, and
    cross-roster traversability;
15. isolated preview equals production projection for every authored roster;
16. standalone and hosted launch manifests normalize to the same resolved
    recipe shape;
17. replay/history survive edits to saved roster/encounter records;
18. generated SDK contains no retired models/routes;
19. cold startup and encounter materialization meet existing timing budgets;
20. no late imports, `TYPE_CHECKING`, dynamic gameplay imports, or circular
    dependency exemptions are introduced.

## 12. Deliberate non-goals

- No authentication redesign.
- No replay-database rewrite; replays remain portable files.
- No arbitrary uploaded Python or runtime content installation.
- No universal monster rules interpreter.
- No new Entity subclass for Character, Champion, NPC, or Monster.
- No separate champion registry.
- No frontend name/race/class inference.
- No compatibility aliases or versioned game-creation routes.
- No silent deletion of the current SQLite profile database.
