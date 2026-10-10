# SRD Character Origins Implementation Plan

Date: 2026-07-28

Status: Complete

## Objective

Replace the current catalog-only character-origin shell with one mechanically
implemented, persistable, reversible, previewable, and frontend-authorable
origin system.

The finished creator must support every installed SRD 5.1 playable species,
the four SRD species variants, the SRD Acolyte background, and the neutral
Neurodragon Adventurer background. An origin becomes `available` only after its
authored grants, runtime behavior, persistence, visual identity, removal, and
tests are complete.

The selected character-creation rules remain:

- SRD 5.1 mechanics and content identities.
- Profile-owned BG3-compatible flexible `+2/+1` ability bonuses.
- The `+2` and `+1` must target different abilities.
- No fixed species ability-score bonuses.
- Species, species variant, background, and immutable origin choices remain
  fixed after creation.
- Ability allocation, flexible bonuses, class progression, subclasses, and
  level choices are rebuildable through respec.

## Current State and Defect

The current catalog contains:

- 9 SRD species.
- 4 SRD species variants.
- 1 SRD background: Acolyte.
- 1 Neurodragon background: Adventurer.

Only Human and Adventurer are mechanically available. The other eight species,
all four variants, and Acolyte are deliberately marked blocked. Their catalog
descriptions are present, but their typed definitions are mechanically empty
except for Half-Elf's two-skill choice.

This is truthful transport behavior, but it is not an implemented character
creator. The existing regression that asserts these origins remain blocked
will be replaced with positive mechanical closure tests.

## Architectural Constraints

### Preserve the Existing Backbone

Origins must use the same path as class progression:

```text
exact ContentRef
  -> CharacterBuildValidator
  -> deterministic CharacterGrantScheduleEntry
  -> source-owned reversible grant applier
  -> CharacterGrantReceipt
  -> materialized Entity
```

Do not create:

- A parallel origin runtime.
- A second modifier framework.
- A name-based trait dispatcher.
- A generic untyped property bag.
- Permanent conditions standing in for structural character features.
- Function-local imports, `TYPE_CHECKING` import workarounds, or circular
  dependencies.

### Dependency Direction

Dependency-neutral contracts remain under `dnd/core/content/` or another
dependency-neutral core leaf. They may contain enums, immutable grants,
identities, and validation-only models. They must not import `Entity`, concrete
conditions, actions, server services, or runtime registries.

Runtime appliers live under `dnd/content_system/` and may import the high-level
`Entity` surface because the materializer owns the entity and its components.

Server DTOs project the installed exact contracts. Server modules must not
become the owner of origin rules.

### One Availability Authority

Runtime availability must not be inferred from provenance fidelity or duplicated
descriptor tags.

Add one explicit dependency-neutral origin implementation status to the typed
origin contract. The catalog and validator both read that same authority.
Provenance continues to describe source fidelity. Presentation tags continue to
describe discovery and layout. Neither controls executability.

## Minimal Structural Primitives

Use existing primitives where they already have a correct owner.

### Existing Primitives to Reuse

- Skill, saving throw, weapon, armor, and shield proficiency sources.
- `ModifiableValue` numerical, advantage, constraint, critical, and auto-hit
  modifiers.
- Health resistance modifiers.
- Condition immunity sources.
- Actions, handlers, resources, spellcasting sources, and known spells.
- Exact content descriptors and related/dependency refs.
- Durable holdings and exact item recipes/presets.
- Source-owned composition receipts and deterministic cleanup.

### New Primitives Required

Add only the following source-owned capabilities:

1. Fixed automatic proficiency rows in origin definitions.
2. Language knowledge contributions.
3. Tool proficiency contributions.
4. Source-owned sense-mode contributions.
5. Reversible resistance modifier receipt handles.
6. Reversible physical-profile handles where an origin changes mechanical
   size or baseline speed.
7. Exact origin identity on a materialized player entity:
   species ref, optional variant ref, and background ref.
8. Innate spell grant metadata supporting:
   - at-will spells;
   - once-per-long-rest spells;
   - unlock character level;
   - fixed cast rank;
   - exact spellcasting ability and source identity.
9. A general exact origin-trait choice for options such as Dragonborn
   ancestry. Do not reuse Sorcerer's class-specific elemental ancestry choice.

Language and tool facts are persisted and projected even before every
out-of-combat consumer exists. Their lack of an encounter consumer must be
reported honestly in presentation metadata; it must not make the exact durable
fact disappear.

## Authored Origin Feature Inventory

Each independently described trait receives an exact public `ContentRef`,
descriptor, provenance, and typed origin-feature definition. Species and
background definitions reference these features through ordered grants.

Shared traits are authored once and referenced by every applicable origin.

### Dragonborn

- Medium size, 30-foot speed.
- Draconic ancestry choice with the ten SRD ancestry options.
- Damage resistance derived from the exact selected ancestry.
- Breath Weapon action:
  - ancestry-authored damage type;
  - ancestry-authored line or cone geometry;
  - ancestry-authored Dexterity or Constitution save;
  - DC `8 + Constitution modifier + proficiency bonus`;
  - SRD character-level damage scaling;
  - one use per rest according to the SRD 5.1 baseline.
- Common and Draconic language facts.

### Dwarf

- Medium size, 25-foot speed.
- Darkvision 60 feet.
- Dwarven Resilience: poison-save advantage and poison resistance.
- Dwarven Combat Training.
- One exact tool proficiency choice.
- Stonecunning as an exact conditional History expertise fact.
- Common and Dwarvish language facts.

#### Hill Dwarf

- Dwarven Toughness: +1 maximum HP for every character level, derived from the
  additive character-level ledger and reversible under composition rebuild.

### Elf

- Medium size, 30-foot speed.
- Darkvision 60 feet.
- Keen Senses: Perception proficiency.
- Fey Ancestry: charm-save advantage and magical-sleep immunity.
- Trance as an exact rest capability fact.
- Common and Elvish language facts.

#### High Elf

- Elf Weapon Training.
- One exact Wizard cantrip choice using Intelligence.
- One additional language choice.

### Gnome

- Small size and an explicitly authored 25-foot speed, matching BG3.
  Mechanical size and walking speed remain independent facts; the engine
  must not derive one from the other.
- Darkvision 60 feet.
- Gnome Cunning: advantage on Intelligence, Wisdom, and Charisma saves against
  magic.
- Common and Gnomish language facts.

#### Rock Gnome

- Artificer's Lore as an exact conditional History expertise fact.
- Tinker tool proficiency and Tinker capability fact.

### Half-Elf

- Medium size, 30-foot speed.
- Darkvision 60 feet.
- Fey Ancestry.
- Skill Versatility: exactly two chosen skill proficiencies.
- Common, Elvish, and one additional language.

### Half-Orc

- Medium size, 30-foot speed.
- Darkvision 60 feet.
- Menacing: Intimidation proficiency.
- Relentless Endurance:
  - intercepts the causal damage/death boundary;
  - leaves the character at 1 HP;
  - once per long rest;
  - does not revive an already-dead entity.
- Savage Attacks: one additional weapon damage die on melee weapon criticals.
- Common and Orc language facts.

### Halfling

- Small size and an explicitly authored 25-foot speed, matching BG3.
  Mechanical size and walking speed remain independent facts; the engine
  must not derive one from the other.
- Lucky: reroll natural 1 on attack rolls, ability checks, and saving throws,
  using the engine's existing typed d20 reroll pipeline.
- Brave: advantage against Frightened.
- Halfling Nimbleness as an exact movement capability used by occupancy/path
  validation.
- Common and Halfling language facts.

#### Lightfoot Halfling

- Naturally Stealthy as an exact hide-targeting capability.

### Human

- Medium size, 30-foot speed.
- Common and one additional language.
- No hidden fixed ability increase; the profile-owned flexible `+2/+1` remains
  the only origin-independent creation bonus.

### Tiefling

- Medium size, 30-foot speed.
- Darkvision 60 feet.
- Fire resistance.
- Infernal Legacy using Charisma:
  - Thaumaturgy at level 1;
  - Hellish Rebuke at fixed rank 2 once per long rest at level 3;
  - Darkness once per long rest at level 5.
- Common and Infernal language facts.

Missing prerequisite spells must be implemented through the ordinary spell
system before Tiefling becomes available. No placeholder action is acceptable.

### Acolyte

- Insight and Religion proficiency.
- Two exact language choices.
- Exact starting holdings:
  - holy symbol;
  - prayer book or equivalent exact authored devotional item;
  - incense stack;
  - vestments;
  - common clothes;
  - currency/pouch fact once the durable currency owner exists.
- Shelter of the Faithful as an exact durable background feature.

The background feature and languages are useful outside encounters. They remain
durable exact facts even while dialogue/economy consumers are pending.

### Adventurer

- Intentionally neutral and mechanically complete.
- No automatic grants or hidden benefits.

## Saving-Throw and Effect Context

Conditional origin features must not infer spell or condition semantics from
display strings.

Where the current saving-throw request lacks sufficient exact evidence, extend
the dependency-neutral request with typed causal facts:

- exact effect or condition `ContentRef` where applicable;
- whether the effect is magical;
- typed condition category/semantic identity where applicable.

Spell and condition producers populate these facts. Origin modifiers consume
only the typed context.

This closes Fey Ancestry, Gnome Cunning, Dwarven Resilience, and Brave without
name matching.

## Appearance and Runtime Identity

Before a non-Human origin becomes available:

1. Appearance validation must receive the selected body and species identities.
2. The creation catalog exposes the reviewed player-body appearance values and
   constraints as exact cold presentation facts. The currently installed
   species do not add artificial backend restrictions to those shared rig
   choices; a species may add an exact constraint later only when authored
   content actually requires one.
3. The materialized player entity must retain exact species, optional variant,
   and background refs.
4. `APIEntitySummary` must project the privacy-safe exact species and variant
   identities independently of the generic player-body creature ref.
5. NeuroClient must resolve visuals from these exact refs, never the display
   name.
6. Mechanical size is authoritative backend state. Pixi palette, proportions,
   and sprite art remain frontend-authored presentation.

## Respec and Premade Semantics

Split the current broad immutable comparison.

### Immutable

- Body recipe, unless a future explicit body-change service is added.
- Species ref.
- Species variant ref.
- Background ref.
- Immutable origin choices.

### Rebuildable

- Appearance, subject to profile policy.
- Base point-buy allocation.
- Flexible `+2/+1`.
- Class-level sequence.
- Subclass and class choices.
- Prepared spell/loadout choices.

An altered premade must not continue to claim exact premade identity. Preserve
optional provenance separately if useful, but `premade_id` authenticates only
the exact premade build.

Existing durable characters use respec. They are not silently cloned.

## Canonical Editable Seed Plans

The creator's one horizontal roster must use a backend-owned editable plan:

- Blank custom seed.
- Every authenticated premade.
- Recent durable characters.

The plan returns:

- exact origin and appearance selections;
- exact level-one creation draft;
- exact ordered level-up operations required to reconstruct a premade;
- exact class and subclass choices;
- exact starting equipment and apparel choices;
- exact holdings provenance;
- target level and entitlement requirements.

Editing a level-five premade must not silently discard its choices and become an
unrelated generic level-one build. Creation still commits level one first and
uses ordinary authorized progression operations, unless an explicit
administrator clone entitlement is used.

## Testing Strategy

Every defect or incomplete origin has an automated measuring test before it is
marked available.

### Contract and Catalog Gates

- One explicit implementation authority; provenance and tags cannot change
  availability.
- Every public species, variant, and background resolves all grants and choices.
- Every available origin has complete appearance constraints.
- No available origin has an unclassified feature.
- Catalog dependency closure and generated SDK parity.

### Mechanical Unit Gates

- Fixed and selected proficiencies.
- Language/tool contributions and exact cleanup.
- Sense contribution composition and cleanup.
- Speed and size composition and cleanup.
- Resistance and condition-immunity cleanup.
- Every action/handler feature family.
- Innate spell unlock, use, rest recovery, and cleanup.

### Origin Integration Matrix

For each of the 9 species and 4 variants:

1. Validate a level-one build.
2. Materialize it.
3. Assert exact mechanical state and runtime origin refs.
4. Exercise every active feature deterministically.
5. Remove composition.
6. Assert no leaked modifiers, handlers, actions, resources, senses, or
   proficiencies.
7. Reapply and prove no duplication.

Level-based gates cover levels 1, 3, 5, and 20 where relevant.

### Persistence and Lifecycle

- SQLite create/reload preserves every origin ref and choice.
- Level-up activates the exact threshold origin grants once.
- Respec preserves immutable origin and permits the approved rebuildable fields.
- Stale CAS and idempotent retry remain correct.
- Active-deployment mutation protection remains correct.
- Premade divergence clears exact premade identity.

### Server, SDK, and Frontend

- Validation, visual preview, creation, definition read, level-up, and respec.
- Exact species identity in production world projection and player replication.
- Generated SDK check/build/tests.
- NeuroClient creator renders every available origin and its automatic/selected
  benefits with exact icons and explanations.
- Production Pixi preview for every species.
- One live create, play, level-up, reload, and respec smoke.

## Delivery Tranches

### Tranche 1: Foundation and Honest Authority

- Fail-first closure tests.
- Explicit runtime support contract.
- Fixed proficiency/language/tool/sense/resistance/physical receipt primitives.
- Respec immutable-boundary correction.

### Tranche 2: Passive Origins

- Human, Dwarf/Hill Dwarf, Elf, Gnome/Rock Gnome, Half-Elf.
- Species-aware appearance and runtime identity projection.

### Tranche 3: Active Origins

- Dragonborn.
- Half-Orc.
- Halfling/Lightfoot.
- Tiefling and prerequisite spells.

### Tranche 4: Background and Editable Seeds

- Acolyte holdings and durable facts.
- Premade editable plans.
- Existing-character respec roster seam.

### Tranche 5: Freeze and Handoff

- Exhaustive focused gates.
- One canonical generation pass.
- Frozen SDK/hash handoff.
- Coordinated backend restart only after NeuroClient adaptation.
- Normal-port live creator and gameplay validation.

## Completion Definition

This plan is complete only when:

- all installed SRD origins are available and mechanically truthful;
- the creator has no disabled SRD origin card;
- every displayed benefit is exact authored content;
- all active mechanics materialize and reverse cleanly;
- species identity survives persistence and reaches the renderer;
- premade editing no longer destroys the authored build;
- level-up and respec preserve origin invariants;
- no old compatibility path, name inference, late import, or circular dependency
  remains;
- the backend, generated SDK, and NeuroClient are green on one frozen contract.

## Implementation Progress Log

### 2026-07-28 — Foundation in progress

Completed and measured:

- Added one dependency-neutral `OriginRuntimeSupport` authority.
- Hard-cut species, variant, and background identities to content version 2.
- Removed provenance/tag-derived execution decisions and the duplicate server
  availability model.
- Added source-owned language and tool contributions to
  `CreatureProficiencies`.
- Added the built-in SRD language enum while retaining validated namespaced
  storage for trusted extension packs.
- Added composable source-owned special senses; strongest range wins and
  removal restores the remaining source.
- Added reversible resistance, structural-size, and origin-capability receipt
  handles.
- Added a typed, data-driven `OriginStructuralFeatureDefinition`.
- Added the passive-feature runtime installer for sense, resistance, physical
  size, walking speed, per-character-level HP, and durable capability facts.
- Added validation scheduling for automatic proficiencies owned by typed
  origin features.
- Added fail-first and now-green focused tests for the contracts, primitive
  source ownership, installation, and exact reversal.
- Targeted Pyright is green on the completed foundation.

Known intentional intermediate state:

- Only Human and Adventurer remain available until authored grants are wired.
- The checked icon ledger and generated SDK are stale because the origin typed
  contract is intentionally mid-hard-cut. They will be regenerated once after
  model and population closure.
- Trusted content-pack API version 1 no longer describes the final required
  origin authoring surface; bump it once at origin freeze with manifest/loader
  tests.

New exact appearance work included in this plan:

- Expose all six reviewed head rigs through authoritative appearance choices.
- Persist bounded stature and build selections.
- Project presentation-only uniform and horizontal scale separately from
  mechanical creature size.
- Keep species mechanics and Pixi presentation choices distinct.

Adjacent profile follow-up recorded, but not allowed to interrupt origin model
closure:

- Add an owner-authorized per-character deployment-history read route backed
  by `PinnedCharacterDeploymentRecord`, retaining game, membership, entity,
  pinned revision, and summary availability identities for exact replay and
  character-sheet navigation.

### 2026-07-28 — Active-origin mechanics in progress

Completed and measured:

- Dragonborn ancestry is a typed immutable origin-trait choice with all ten
  SRD ancestry rows, exact damage resistance, exact line/cone geometry, exact
  save ability, Constitution/proficiency DC, level-scaled Breath Weapon damage,
  and one source-owned short/long-rest use. Full build validation,
  materialization, use, removal, and reapplication are covered.
- Real Breath Weapon execution is also covered through the canonical
  subjective presentation mapper. Technical per-target convolution events are
  suppressed, leaving exactly one authored Action root with its ordered Damage
  child instead of a second empty Action root.
- Halfling Lucky rerolls the selected natural d20 result through the typed roll
  event and must use its replacement, including another natural 1.
- Halfling Nimbleness is consumed by authoritative traversal and path
  discovery. A larger creature's occupied cell can be crossed but is never
  exposed as a legal destination; same-size creatures and non-creature
  blockers remain blocking.
- Lightfoot Naturally Stealthy is consumed by Hide eligibility only when a
  larger living creature lies on the exact observer-to-hider grid ray.
- Half-Orc Savage Attacks contributes one reversible melee critical damage die.
- Half-Orc Relentless Endurance owns one long-rest resource and one exact
  incoming-damage handler. It preserves 1 HP once, refuses an outright
  massive-damage death, cannot activate twice before recovery, and removes
  through the composition receipt.
- The active-origin focused matrix is green and targeted Pyright reports no
  errors. The builtin declaration inventory remains duplicate-free.

Intentional freeze discipline:

- The icon ledger and generated SDK remain stale while public origin
  declarations are still being added. Ordinary collection paths that install
  the builtin catalog therefore fail closed on the measured ledger mismatch.
  Focused engine tests use an isolated registry until the authored model is
  closed; the ledger will be refreshed once, followed by the normal catalog,
  server, SDK, and frontend gates.

### 2026-07-28 — Durable legacy-origin rebase complete

- Added one owner-authorized respec-seed read path that projects a historical
  character onto the currently installed exact content contracts.
- Same-version contract refreshes use the canonical
  `(pack, kind, content id, version)` registry identity. Version changes
  require a separately authored migration row keyed by the complete historical
  `ContentRef`, including its old contract hash. Display labels, Python paths,
  aliases, and pack/content-name resemblance never participate.
- The exact durable regression for the existing `mona` character uses its real
  Human-v1 and Adventurer-v1 hashes. It rebases those two exact immutable refs,
  adds Human's exact Draconic language choice, and explicitly upgrades the
  released six-option appearance selection with average build and stature.
- Respec now distinguishes the truly immutable body/species/variant/background
  and origin-choice foundation from rebuildable appearance, ability
  allocation, flexible bonuses, and class ledger. Level-up retains the stricter
  foundation check.
- `premade_id` is server-owned provenance rather than client authority. An
  otherwise exact no-op retains it; any divergent respec or level-up clears it
  from the normalized build and committed revision.
- The response keeps old revision heads, content/rules digests, and timestamps
  as provenance and returns a closed typed change union for old/new refs,
  appearance additions, and origin-choice additions. Removed identities,
  conflicting migration choices, unsupported appearance vocabularies, or
  incompatible recipe parameters fail closed without an editable seed.
- Level-up and respec commits use current profile/content digests, remain
  three-head-CAS/idempotency/active-deployment fenced, and can atomically append
  rebased holdings while retaining immutable history.
- Focused service behavior tests are authored and static validation is green;
  their ordinary bootstrap run is waiting on the same intentional one-time
  icon-ledger refresh as the rest of this tranche.

### 2026-07-28 — Dwarf and Acolyte authored-content closure

- Dwarven Combat Training now grants the exact Battleaxe, Handaxe, Light
  Hammer, and Warhammer proficiencies; Light Hammer has one canonical SRD
  factory/ref/recipe rather than a test-only placeholder.
- The Acolyte background owns one exact starting-holdings package containing a
  holy symbol, prayer book, five incense, vestments, and common clothes.
  Directory character creation composes this through the same deterministic
  durable-holdings path as class gear and apparel, retaining class/apparel slot
  priority.
- Insight, Religion, two chosen languages, and Shelter of the Faithful remain
  exact source-owned facts and Acolyte is mechanically available.
- The SRD 15 gp is deliberately not fabricated: the engine has item-price
  metadata but no durable wallet/currency owner yet. Provenance states this
  one pending non-encounter fact explicitly.
- Focused Dwarf/Acolyte tests are green (`14 passed`), targeted Pyright is
  clean, and the complete declaration inventory freezes without duplicate
  identities. Ordinary bootstrap/service gates wait on the same final ledger
  refresh.

### 2026-07-28 — Origin runtime and lifecycle matrix complete

- All 9 SRD species, all 4 SRD variants, Acolyte, and Adventurer now use the
  same explicit `OriginRuntimeSupport.available()` authority.
- The complete passive/active inventory is implemented through source-owned
  reversible receipts: fixed/selected proficiencies, languages, tools, senses,
  resistances, save context, physical profile, per-level HP, capabilities,
  actions, handlers, resources, and innate spells.
- High Elf and Tiefling innate spellcasting use ordinary exact spell
  definitions and source-owned spellcasting grants. They do not impersonate a
  class spellcasting source.
- The 14-case integration matrix validates a level-one draft, materializes
  exact origin identity/mechanics, removes every origin-owned handle, reapplies
  the same composition, proves semantic equality, and removes it again without
  leaks or duplication.
- The complete isolated origin/appearance/context suite is green: 122 focused
  tests across 14 individually executed files. The architecture suite is 20/21
  green; its only remaining subprocess gate intentionally stops at the stale
  checked icon ledger before it can import `server.event_server`.

### 2026-07-28 — One editable creation-plan path

- The catalog schema now exposes one ordered `creation_plans` roster:
  `Blank Custom` plus the four authenticated editable built-in templates.
- Every plan authenticates its seed build, loadout, level entitlement,
  supplemental holdings, and optional source premade identity.
- The blank plan authorizes exactly level one. Each premade plan provides the
  explicit validated clone entitlement for its authored target level; arbitrary
  custom level 2–20 creation is rejected.
- Editing a premade uses the same controls. Exact `premade_id` is retained only
  when the requested build and loadout still equal the authenticated seed; any
  divergence clears it.
- Recent durable characters remain separate profile records and enter the same
  editor through the server-authored respec seed. They are never silently
  cloned.
- The retired `PremadeCharacterBuild`, premade digest, old selector helper, and
  TypeScript `catalog.premades` fixture have been removed. There is one creator
  contract and one creation service path.

### 2026-07-28 — Trusted content-pack API v2

- The trusted administrator-installed content-pack API is now version 2.
- Version 1 manifests fail before any dynamic import.
- Version 2 packs can author exact typed origin traits and species through the
  dependency-neutral public content contracts.
- Manifest, loader, and static-import gates are green (`60 passed` across the
  two currently ledger-independent focused files). The CLI/bootstrap file waits
  on the same one-time final icon-ledger refresh.

### 2026-07-28 — Origin presentation and catalog freeze

- Imported the reviewed NeuroClient icon manifest atomically at 515 assets,
  manifest SHA-256
  `94ba386f278b8da917df6cf896fba4f23d858e0abcb13b20a85a7a0bd8df244c`.
- Every new public origin feature, action, spell, reaction, item, and starting
  package has an exact reviewed binding or an explicit shared semantic binding.
- High Elf Weapon Training owns the distinct
  `trait.elf-weapon-training` asset. The briefly detected Dwarven Combat
  Training reuse was removed before freeze and is prohibited by the checked
  ledger.
- The importer rejects the old 514-asset manifest, unknown retired rows, and
  any binding drift. Its write/check cycle and the 11 binding regressions are
  green.
- The final public content catalog is schema 6 with 669 entries. Its live
  content-set digest is
  `debdb8b22dab1ee59e7c2a176532fda630910b8d8a65c22cd165ee9c6d584e92`
  and its catalog digest is
  `7295a79399f1caff03318900c3442faa4e322c894564aa121f662db5ec4d65d7`.

### 2026-07-28 — Backend and SDK freeze handed off

- Generated the canonical TypeScript SDK once after model and population
  closure, then verified generator `--check`.
- Frozen protocol hashes:
  - SDK:
    `46ca74104f5a55c40fc877a5e52e6bad3626ac631a44a47950a17252ee586b0c`
  - player replication:
    `f9156c74db78d67150dbd9c084a3ad7ad7bd120952606a786d7eaf221dcaf3f6`
  - objective event:
    `9463e028e1452b2b972a696c7b09664889676b8cc4596bfde2db8d36dc64d4a5`
- The SDK build and all 79 SDK tests are green.
- The handwritten directory client now types creation validation and visual
  preview against `CharacterCreationValidationRequest`, so both requests must
  carry the same authenticated plan ID/digest as commit. Its frozen source
  SHA-256 is
  `ee8ae14efd915184b796c2e224c569bcb8206454b8f9a0cc8e0821e8b1befff3`.
- The final dependency/import architecture suite is 21/21 green with no late
  imports or circular-import workaround.
- Character creation catalog schema 6 exposes exactly one roster of five
  authenticated plans: Blank Custom plus the four editable templates. It
  exposes 9 species, 4 variants, and 2 backgrounds.
- Historical characters use the exact respec-seed migration path. The real
  Human-v1/Adventurer-v1 durable case rebases without display-name or
  compatible-hash inference, and a changed build clears exact premade
  provenance.
- Hosted worker readiness now allows the measured current cold import. The
  character head-race, worker identity, hosted runtime, and complete
  multi-game gateway regressions are green; the semantic fencing behavior was
  not weakened.
- The final standalone backend was restarted once on PID 3949144.
- NeuroClient's schema-6 hard cut is green with no compatibility fallback:
  exact plan-authorized validation and Pixi preview return 200; edited premades
  retain their level-five plan entitlement while the backend clears divergent
  premade provenance; Blank Custom remains level one.
- Desktop and phone creator gates, all 58 configuration previews, existing
  character reload, the complete presentation/replication check, and the
  production build pass against normal ports. Backend `:8000`, UI `:5173`,
  and the Vite proxy remain healthy.
