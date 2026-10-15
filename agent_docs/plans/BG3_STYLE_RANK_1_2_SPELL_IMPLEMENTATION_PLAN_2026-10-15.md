# BG3-style implementation plan: 36 rank 1 and rank 2 spells

15 October 2026. Status: implementation and qualification completed for the
approved 36-spell scope. All 36 roots are authored and registered; results,
existing repository failures and forecast limitations are recorded in §10.

The human requested a new worktree and a precise plan for all 38 spells in the
latest rank 1/2 audit, reusing the current engine, with per-spell implementation
locations, test setups, difficult interactions, references and explicit doubts.
The revised scope is 36 spells after the human removed Enthrall and Heat Metal,
including their necessary shared engine changes
and player-facing discovery/submission. This document does not authorize adding
the other 61 missing low-level spells or implementing the separate multiple-floor
plan. The human decisions in §1.3 govern; recommendations used under the instruction
to implement are recorded as implementation defaults in §10. NDClient presentation
work is excluded.

## 1. Checkout, baseline and intended result

- Implementation worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
- Branch: `codex/spells-rank-one-two`, created from `feature/speedupsensory` at
  `229ce025f3f` (the current checkout when this planning request arrived).
- A matching copy of this plan is saved under `agent_docs/plans/` in the original
  `/mnt/c/users/tommaso/documents/dev/dnd_engine` checkout, as requested.
- Source audit: 130 public catalog rows; Entangle and Black Tentacles also have
  concrete native implementations outside that catalog. None of these 36 is a
  public catalog spell yet. Divine Smite already exists as a Paladin feature.
- Intended catalog result: 36 additional spell identities, not 36 new rule
  frameworks. A learned Divine Smite root can be handler-backed, like Shield.
  If all are delivered, the public catalog grows from 130 to 166.
- Existing systems are evidence, not proof that a new spell already works. This
  is a source/test-design study; no baseline suite or gameplay run is claimed.

Read `RECOVERY_PLAN.md`, `agent_docs/HISTORY_BEFORE_ME.md` and `HOW_TO_TEST.MD`.
The active application direction is the server/SDK plus NDClient. Pygame tests
can be useful legacy regression references but cannot certify the current
client. Multi-floor and free hovering are not implemented prerequisites for
this batch. Do not edit those separate plans or their code as opportunistic work.

### 1.1 Rules policy

Use the documented BG3 mechanics below, with the engine's existing levels 1–20,
5/11/17 cantrip progression, exact spellcasting source, causality, visibility and
source ownership. Do not copy BG3 bugs, newest-class-stat bugs, hidden-target
leaks, damage-rider recursion or lost item ownership.

Four selected spells have no BG3 version: Spare the Dying, Starry Wisp, Sorcerous
Burst and Dragon's Breath. The human chose SRD 5.1 Spare the Dying; proposed
defaults are SRD 5.2 for the other three. Divine Smite has a BG3 feature rather than a 5.2
spell; its BG3 automatic-handler surface is now decided in Q1. These are explicit
profiles, not a wholesale switch of the engine to 2024 rules.

BG3 gameplay references are secondary documentation of the game, not access to
Larian's engine source. Exact proposed departures and uncertain behavior are
collected in §8. SRD sources are the repository's
`content_data/sources/srd_5_1_cc.json` and `srd_5_2_cc.json` and the official
[SRD 5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf) and
[SRD 5.2](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf).

### 1.2 Scope inventory

The numbered cards in §5 are the implementation inventory. Original rank 1:
1–5. Original rank 2: 6–38. The human removed Heat Metal (card 23) and Enthrall
(card 25); retain the remaining 36 cards and their original IDs. Their exclusions
remove metal-contact tracking and facing/peripheral-vision work from this batch.
Spell summon recipes, Flame Blade and mixed riders still need their documented
mechanics. The file name retains the original scope for stable existing links.

### 1.3 Accumulated human decisions

- **Divine Smite uses BG3-style automatic on-hit behavior.** There is no
  click-to-accept reaction UI. Reuse existing per-level player toggles and
  native automatic handler ordering/payment; do not add a new reaction prompt
  or impose the 5.2 bonus-action form. Q1 is resolved on that basis.
- **Fire summons follow the existing monster-summon model.** Current source
  gives summons the caster's faction, owned summon origin/lifetime/dismissal and
  autonomous NativeAIController turns. That is the reused model for Flaming
  Sphere and the proposed common path for Spiritual Weapon. Direct player
  movement/attack selection is not inferred from caster ownership; the proposed
  seat/audience/control protocol redesign is removed. Q3 retains only remaining
  spell-specific form/stat choices.
- **Temporary items use conditions/handlers.** A source-owned condition stores
  the created item UUIDs; existing duration/rest/removal hooks retire remaining
  items through native item lifecycle. Drop/transfer does not create a separate
  timer or item service. Goodberry uses BG3 four-berry/1d4/bonus-action consumption
  and expiry at the native long-rest boundary of its owning caster condition.
  Reuse native duration/rest conventions without a new global camp/rest clock.
- **No NDClient presentation work.** No client code, art/media work, visual
  acceptance or client handoff prerequisite belongs to this batch. Native
  mechanics, necessary server/SDK contracts and their acceptance tests remain
  in scope. Q15 is resolved.

- **Enthrall and Heat Metal are excluded.** Current scope is 36 spells. Do not
  implement their cards or shared mechanisms solely for these removed spells.
- **Spare the Dying uses SRD 5.1.** Touch/action, Cleric, with existing stabilization
  and the 5.1 undead/construct exclusion.
- **Discussion answers use the enumerated list, not Q IDs.** The human explicitly
  clarified this. Damage details are delegated to sensible native conventions;
  the surface and area recommendations are accepted (Q7–Q9 record the concrete
  profiles). Do not invent bespoke exceptions/frameworks to support them.
- **Control spells have separate conditions with explicit immunity compatibility.**
  Reuse native transforms and honor relevant existing immunity rules without
  changing global fear/prone behavior. Dissonant Whispers keeps its BG3 fear.
  Heroism clears current fear; Protection from Evil and Good clears current
  eligible charm/fear. Cleared effects are removed, not retained to resume later.
- **Ensnaring Strike uses documented BG3 recovery.** Initial STR save, start-turn
  piercing damage and ally Help removal. Remove the proposed self-escape STR-check
  action; do not add automatic repeat saves.
- **No Globe/Antimagic redesign.** New spells integrate with existing native
  protection decisions. Narrow new-rider attribution/bonus selection needed for
  compatibility is in scope; new protection policies and unrelated changes are not.

## 2. Existing owners and specific reuse

| Capability | Current source/reference | Use and practical limit |
| --- | --- | --- |
| Native casts, costs, variants and saves | `dnd/actions.py`: `SpellAction`, `SpellEvent`, `resolve_spell_attack`, `get_variant_facets`, `apply_owned_condition`; `dnd/core/action_types.py`: `ActionVariantFacet` | Reuse validation, paid actions, slot variants and typed choices. A normal SpellAction does not automatically implement conditional hit-only costs or weapon Extra Attack. |
| Source-owned conditions/concentration | `dnd/core/base_conditions.py`; `dnd/conditions.py`: `Concentrating`, `ConcentrationActionMarker`; `SpellAction.prepare_concentration`, `commit_prepared_concentration`, `apply_owned_condition` | Prepare/admit/commit/publish through the existing lifecycle; own exact modifier/handler/action/item UUIDs. The convenience helper currently resolves entity recipients only. |
| Repeated spell actions | `dnd/spells/evocation.py`: `SunbeamEffect`, `SunbeamStrike`, `Sunbeam`; `dnd/spells/conjuration.py`: `CallLightningStrike` | Sunbeam is the stronger eligibility reference: owner applied, contributions active, exact source retained. Grant repeated actions before initial damage can invalidate concentration. |
| Damage components and criticals | `dnd/core/events.py`: `DamageRollResultEvent.append_damage_roll`; `dnd/classes/paladin.py`: `create_divine_smite_processor`; `dnd/items/property_composition.py`: `_unseen_strike` | Append eligible dice before damage allocation. Weapon and spell attacks do not yet share every damage-roll interception path. |
| Existing mark concept | `dnd/spells/necromancy.py`: `AbilityCurseEffect`, `DamageCurseEffect` | Relationship/state concept only. Do not copy its late direct-damage handler, `getattr`, fixed HIT dice or saving-throw penalties into Hex. |
| Areas, moving fields and exposure | `dnd/spatial/area_conditions.py`: `SpatialCondition`, `AreaCondition`; `dnd/spatial/memberships.py`: `SpatialConditionMembershipSource`, `MembershipAreaCondition`; `CloudkillZone`, `SpiritGuardiansZone` | Existing entry/start/end hooks, per-target/turn fences, source leases, movement and suppression. No new scheduler, area dispatcher or parallel map overlay. |
| Elemental surfaces | `dnd/spatial/environmental_conditions.py`: `Wet`, `WetSurface`, `IceSurface`, `ElectrifiedWater`, `SteamCloud`, `FireSurface`, `OilSurface`, replacement recipes/transitions | Water/fire/ice/electric/steam work exists. BG3 acid AC reduction and simple-toxin surface behavior are not the same as the engine's acid/poison body residues. |
| Attack values and exact weapons | `dnd/blocks/equipment.py`: `Weapon`, weapon attack/damage profiles and item values; `dnd/spells/transmutation.py`: `ShillelaghEffect`, `Shillelagh` | Add owned item modifiers, not global wielder bonuses. Temporary magical status must compose with the independent die/ability override. Current override selection is not a general priority solution. |
| Equipment/consumption/retirement | `dnd/blocks/base_item.py`, `dnd/blocks/inventory.py`, `dnd/items/consumables.py`; `HeroesFeastObject`, `EatFromFeast`, `HeroesFeastLifetime` in `conjuration.py` | Use real items and native transfer/consume/retire events. Rest expiry on a ground item is not supplied by an actor inventory scan. |
| Summon birth, death, expiry and turn joining | `dnd/summoning/system.py`, `forms.py`, `conditions.py`; `dnd/types/summoning.py`; `dnd/spells/summoning.py` | Reuse caster-owned autonomous AI summons, existing lifecycle/join/dismissal and new concrete spell recipes (§3.5); no direct-player-control subsystem. |
| Life states and healing | `dnd/entity.py`: `stabilize`, `receive_healing`, `revive`; `dnd/blocks/health.py`: temporary HP grant identity and damage resolution | DYING/STABLE/DEAD differ. Actual revive implementation requires DEAD and rejects disintegrated remains, despite its stale broader docstring. |
| Immunities and control transforms | `Entity.check_condition_immunity`, source-owned immunity contributions; `Charmed`, `Frightened`, `Prone`, `SleepEffect`; `LesserRestoration`, `ProtectionFromPoisonEffect` | Reuse exact transforms with deliberate differences. Current fear is source-in-senses contextual; ordinary Prone can stand up. Neither is the complete BG3 control spell by itself. |
| Light/reveal | `LightEffect`, `GuidingBoltMarked`, `DaylightZone`; `dnd/conditions.py`: `Invisible`; sensory contribution refresh | Light and attack advantage exist. Temporarily defeating invisibility needs an owned contribution consumed by all observer queries, not permanent removal or See Invisibility on one observer. |
| Discovery/transport | `dnd/player/{session,facts,application,reduction}.py`, `server/{worker,protocol}.py`, `sdk/python`, `sdk/player-typescript` | Current player schema is 9; preserve schema 8 compact choices/selected previews and schema 9 optical observations, subject privacy and stale-selection validation. Client name-based spell exceptions are not an implementation. |

## 3. Shared additions justified by these spells

These are bounded changes to existing owners, not a preliminary framework
project. Implement each only with the first spell that needs it and its real
observable acceptance case.

### 3.1 Attack-hit riders and attack-backed spells

Weapon hits already have typed damage-roll result interception. Several spell
attacks roll damage after `resolve_spell_attack` without that same interception.
Expose a narrow shared damage-roll finalization boundary to both paths so Hex
can append a component per successful ray/application. Preserve original
`AttackOutcome`, exact recipient/application, source ability, damage origin and
critical dice. Do not rescan historical logs or re-trigger on received damage.

For Phantasmal Force and Vampiric Touch accounting, positive damage facts alone
are not a resolved per-component ledger. `DamageAppliedEvent` carries positive
HP/tempHP consequences and raw specifications; the matching completed
`TakeDamageEvent.resolution` carries typed `DamageResolution.components` in
source order. Consume the current native completed resolution/reference, not
historical log scans or raw requested rolls. Source-specific healing also needs
to retain the identity of Vampiric Touch's own component before same-type riders
are aggregated. If the current resolver cannot preserve that mapping, add only
the typed component attribution needed here, in the existing damage owner.
Use existing post-mitigation components, including temp-HP absorption and
overkill, without allocating limited remaining HP among components. Q7 delegates
sensible native accounting; it does not introduce a new damage framework.

Keep explicit authored eligibility for weapon-only, melee-weapon-only and
any-attack-roll effects. An appended rider cannot trigger itself. Separate
damage parts remain one original attack resolution for defense/temp HP/death
saves. Standalone later DOTs are separate resolutions with retained origin.

Weapon AttackEvent is not a SpellEvent, and current individual Damage records
do not carry an EffectOrigin. Plan an explicit narrow source/level/protection
check for each spell rider before append, or add typed component attribution
where the shared damage owner needs it; merely testing caster contribution
activity does not cover target-side Globe or a path crossing Antimagic. Preserve
physical base damage when a magical rider is suppressed. Q17 is existing-rule
compatibility only: no new protection policy, whole-attack spell veto or
Globe/Antimagic redesign. The same per-component identity
supports Vampiric Touch accounting instead of a second damage system.

BG3 attack-backed Searing/Branding/Ensnaring casts charge the weapon action for
the attempt, and the bonus action/slot on a hit. Current ordinary SpellAction
cost generation is upfront. Add the smallest shared hit-cost composition for
these three actions, with native preflight/payment/publication; preserve Extra
Attack credit and existing Haste restrictions. Do not temporarily install a
global smite handler and hope to remove it after an arbitrary next attack.
Q1 fixes Divine Smite's automatic policy; Q2 settles the remaining attack-backed
spell costs and any deliberate simplification.

### 3.2 Reveal, next-attack penalties and persistent control

Provide one exact-source reveal contribution for Starry Wisp, Faerie Fire and
Branding Smite. It suppresses the benefit of currently active invisibility and
prevents an incoming invisibility benefit while active; normal darkness,
opaque walls and blindness still apply. Removing the last revealer restores
any still-valid independent invisibility source. Use the existing suppression/
perceivability contribution owners, without deleting a race/item condition.

Native light's `dim_radius_feet` is the ADDITION beyond bright. Translate each
spell's published outer radius deliberately: Starry Wisp bright0/dim10;
Flame Blade bright10/dim-extension10 for outer20; Flaming Sphere bright20/
dim-extension20 for outer40. Current GridMap light sampling forces a minimum
one-cell bright radius even when bright radius is0; pure-dim Wisp needs a narrow
zero-bright correction in that existing owner plus an observable light-level
test. This is not authorization for another light solver or renderer rewrite.

Vicious Mockery consumes its owned disadvantage on the next actual attack roll,
not on a save-only spell. Hideous Laughter needs persistent prone/agency denial
and repeat saves, not ordinary auto-standing Prone or all Stunned effects.
Dissonant Whispers needs an explicit BG3 fear profile, not a global change to
Frightened. Give the adapted control spells separate owned conditions, explicitly
honoring relevant native fear/prone/control immunities. Laughter is not Charmed;
Charmed immunity alone does not block it. Heroism and Protection remove existing
eligible fear/charm, rather than retaining it for later restoration.
Calm Emotions must block the Rage action and remove its owned
descendants as well as providing charm/fear immunity.

### 3.3 Exact items and their lifetimes

For Magic Weapon, prefer a condition on the exact item using the
existing BaseBlock concentration transaction; narrowly generalize the entity-only
`apply_owned_condition` helper if needed. A caster-owned condition tracking an
exact item is also valid where the spell owns created items. Do not duplicate
the prepare/commit/publish protocol.

Magic Weapon requires only source-owned attack/damage modifiers and an
independent magical-status contribution. Do not install a second d8 override.
Current Attack path suppression strips intrinsic magical-item base modifiers,
keyed by `weapon.is_magical`; it does not automatically strip new temporary
enchantment handles on an ordinary weapon. Extend that existing attack-path
contribution selection to omit exactly Magic Weapon's bonus/magical contribution
when suppressed along the path or at contact, leaving ordinary physical weapon
damage and unrelated contributions intact. Test owner outside Antimagic while
the attack crosses/ends inside it, not only the caster standing inside.
Flame Blade requires a real temporary weapon plus an explicit spell-attack
profile and Extra Attack exception. Goodberry requires a caster-owned batch
lifetime that can retire its still-existing items in inventory, equipment,
containers or on the floor; no new global clock or food simulation.
Use a normal source-owned condition plus the needed native handlers: store
exact UUIDs, advance its existing duration/rest hook, and call prepared item
retirement on expiry/removal. Consumed/already-retired UUIDs are harmless to
cleanup. Follow items by identity after drop/transfer; never restore a saved
inventory or weapon snapshot. HeroesFeastLifetime already demonstrates finite
condition-owned object retirement, so temporary existence is not a new global
system.

### 3.4 Small surface definitions and spatial contributions

Compose the existing area/transition machinery for acid AC reduction, selected
toxin behavior, Plant Growth's ground cost, and glyph triggers. Acid/poison
body residues have different rules; do not relabel them as BG3 surfaces.
Plant Growth contributes a per-edge ground movement cost rather than reducing
the actor's global speed/remaining budget. Existing supported-endpoint Fly
bypasses ground vegetation; no flight rewrite is needed. Q8/Q9 define surface
menus, overlaps and toxin details.

Use exactly declared trigger policies for each area. Specify whether appearing
under someone, moving an area over them, forced entry, starting inside, or ending
inside is an exposure. Tests must separate these cases. Do not apply an
unexamined universal once-per-turn rule to every effect.

### 3.5 Spell summons — reuse the existing monster-summon model

BG3-style engine adaptation: Spiritual Weapon and Flaming Sphere are real
targetable entities with their own autonomous turns, movement, actions, expiry
and defeat. Add their authored families/forms/recipes to the current summoning owners, preserving
existing animals/fey/fiend behavior. Spiritual Weapon is not concentration;
Flaming Sphere is. Their state records retain casting source, attack/DC values
and upcast level; they do not inherit the caster's Extra Attack or inventory.

The human asked for the fire summon to work like existing summoned monsters.
Reuse NativeAIController creation/start/close/rebind, caster faction, exact
SummonOrigin, the existing after-caster combatant join and ordinary dismissal.
AI chooses the spell summon's legal movement and recipe-owned attacks/actions
through the same turn machinery. Extend only the concrete action/target-effect
profiles needed for Ram, spectral attacks or aura eligibility. The caster owns
and can dismiss the summon; the player does not directly select its turn actions
under the current monster-summon model.

Remove the previous HumanController/Session/player-audience/seat-membership
proposal. Do not alter observation sharing or protocol shape just to make these
summons appear player-controlled. Qualify native autonomous turns and existing
server progression to the next human input boundary; current observer privacy
and player-control authorization must stay intact. Q3 still discusses weapon
forms/stat snapshots, not a control-system prerequisite. This keeps real
targetable summons and their gameplay while following the existing engine's
control adaptation rather than copying BG3's direct command UI.

Enthrall is removed by the human. No facing/peripheral-vision extension or
replacement Perception-debuff spell belongs to this batch.

### 3.6 Independent sources and retained casting attribution

Current BaseBlock preparation replaces a condition of the same public membership
name. A test saying 'two casters' is therefore not enough: explicitly preserve
exact caster/cast leases where independent sources must survive. Wet's shared
public manifestation with separately owned source memberships is the concrete
reference; SpatialConditionMembershipSource alone does not make its same-named
child safe. Add only the source records required by each authored effect, not a
generic stacking/priority service.

Proposed policies: reveal remains effective while any revealer is live; native
light combines through its existing MAX/cap rules; Magic Weapon and Pass without
Trace choose strongest applicable bonus without adding duplicates; each caster's
Hex/Mark relationship contributes only to that caster's attacks. DOTs and
one-roll debuffs explicitly select coexistence/replacement/strongest policy in
their own card implementation rather than relying on name overwrite. Q7/Q9/Q14
record native/delegated defaults and the remaining item-policy proposals. Removing the strongest source
must expose the surviving weaker one where appropriate.

Hex/Mark concentration links to a caster-owned sustain/retarget marker independent
of the quarry. Quarry death or public mark removal must not empty the last
concentration child and destroy Reapply. Prepare retarget admission before
changing the relationship; rejected target/LOS/cost leaves the prior marker,
concentration and legal reapply state intact.

Dragon's Breath separates acting recipient from original caster: recipient UUID
owns costs, senses, targets and activation; original caster UUID/source/ability/
DC/origin/upcast data own magical attribution and sustain. Keep the passive
source snapshot in the existing dependency-neutral types layer if it is shared
with spell summons. Do not pass a caster-local source ID into recipient spell
methods and accept fallback to recipient stats. Summon recipe/action definitions
must not import evocation/conjuration roots that depend on those recipes; preserve
the DAG through passive snapshots and existing low-level actions/spatial owners.

## 4. Integration and useful test setups

### 4.1 Registration, learning and current player contract

For every new root, update both `SPELL_CONTENT_IDENTITY_SPECS` and
`SPELL_CATALOG_METADATA_SPECS` in `dnd/spells/catalog_content.py`, including
actual school, level, components, ranges, class metadata, concentration,
target/area shape, upcasting and adaptation notes. Keep `dnd/spells/__init__.py`
inert. Add concrete conditions/actions to
`dnd/content_system/{condition_definitions,action_definitions}.py`, and granted
actions to `_SPELL_GRANTED_ACTION_TYPES_BY_CLASS` so dependency closure is real.
Use `reaction_spell_content.py` for the handler-backed Divine Smite chosen in Q1.

For 5.2-only spells, extend the existing spell declaration/provenance path to
use the already-loaded `wotc.srd_5_2_cc` source with an accurate anchor and
explicit adaptation. Do not falsely cite 5.1. A separate new pack is not a
human requirement: choose the smallest accurate composition supported by the
current content model. Existing Ice Knife/5.2 creature provenance is a reference.

Update the explicit `SORCERER_SPELL_RANKS` and grant validation in
`dnd/content/characters/{class_definitions,sorcerer_grants}.py` for newly eligible
Sorcerer spells. Verify the actual supported progression routes and catalog
grants. Other listed classes do not authorize implementing absent class systems;
their mechanics can be exercised by explicitly authored legal casters.

Use `ActionVariantFacet`, native discovery variants, exact subject/position
choices, compound continuation and server submission for element, ability,
weapon, glyph and upcast choices. Repeated/granted actions retain original
casting source and level. Add truthful AI target-effect profiles where the
existing owner consumes them; do not make AI parse descriptions or see hidden
targets. Native visible results must flow through current player facts/logs,
with no replay payment or repeated spell execution.

The current protocol identity in `sdk/protocol/protocol-identity.json` is
player schema 9, despite older schema 8 wording in RECOVERY_PLAN and server docs.
Reuse schema 9 native optical source observations for new lights: independent
source UUID/revision, actual position and radii, change/removal and private-anchor
filtering. Do not add another client illumination solver or expose a hidden
actor/item identity merely because its light is visible. The active TypeScript
SDK is `sdk/player-typescript/`; `sdk/typescript/` is the older SDK and cannot
qualify the current server. Export protocol changes through the existing
`sdk/protocol` workflow, then regenerate both active SDK contracts together.

NDClient presentation is excluded by the human. Do not inspect/change client
media as an implementation prerequisite, author visuals, import/pack artwork,
or require client visual review to finish native spell mechanics. Native light,
condition, damage and item facts still use the existing player/server/SDK
contract where relevant. Qualify these through native state and typed command/
capture/reduction tests; make no claim that this batch implements their visuals.

### 4.2 Reusable scenario setups

These are small test data setups inside the existing harness, not new product
encounters or a test framework. Each spell card names its setup and observable
cases. Use stable public actions/state/events and `fixed_dice_faces` /
`force_save_result`, not private-handler mocks or guessed sleeps.

| Setup | Concrete initial state and purpose |
| --- | --- |
| S1: paid cast and life states | Small Game with caster, ally and enemy; real source/slots/actions; configurable DYING/STABLE/DEAD/positive HP and exhausted ally. Includes one wall and an invalid destination for admission tests. |
| S2: control and two observers | Caster, allied observer, enemy observer, beast INT 3, beast INT 4, humanoid and charm-immune target. Add invisible source, darkness/opaque wall and independent Sleep/Prone only in cases that need them. |
| S3: weapons and ownership | Two casters and a wielder; quarterstaff/club, ordinary and enchanted metal weapon, bow/offhand weapon, nonmetal alternative and metal armour. Use real equip/drop/loot/transfer; vary caster versus weapon ability. |
| S4: surfaces and path | Bounded floor with two separate water patches, oil/fire, one height change, wall/door and allies/enemies. Query actual paths/spent budget, move/force targets, and affect only part of an area. |
| S5: damage and retained actions | Caster with real slots, two durable targets, resistant/immune variants, temporary HP and independently applied control. Advance native turns; use a multi-ray cast and crit only where relevant. |
| S6: autonomous summon turns | Bound encounter with human caster, AI opponent and existing summon reference; create spell summon, advance its AI movement/attack, defeat/expire/dismiss it, and verify server progression reaches the next human input boundary. |
| S7: transport and integrated play | Real server operation/discovery/preview/submit through existing player service and SDK contracts; representative single target, AoE, variant, repeated action, temporary item and autonomous summon. One integrated native/server setup combines water/light/rider/control decisions; no NDClient presentation work. |

Strong existing references: `tests/manual/spell_regression_support.py`;
`tests/engine/test_{nature_spell_delivery,roster_support_spells,prepared_condition_lifecycle,condition_transform_ownership,liquid_barrel_areas,weather_solar_spells}.py`;
`tests/player/test_{compact_compound_choices,operation_audience_reduction,session_admission_review}.py`
and `tests/engine/test_deferred_aoe_discovery.py`. SDK tests live under
`sdk/python/tests/` and `sdk/player-typescript/src/tests/`; the latter package's
`npm test` runs its build and Node tests. Do not invent `tests/server/`.

### 4.3 Common acceptance obligations, applied selectively

Every spell needs a real successful paid cast/activation, relevant invalid
admission with correct cost behavior, its specific save/miss/crit/upcast rules,
and a meaningful cleanup/end condition. At least one legal prepared/progression
caster per family must discover and submit it; `alt_skip_slot=True` fixtures are
not primary proof of casting economy. Use card-specific tests for the rest.

Test relevant interactions rather than the Cartesian product of 36 spells:
concentration replacement/cancellation, Silence/components, Sanctuary,
Counterspell on the initial cast, Globe/Antimagic, two independent sources,
death/downing, item transfer, and source expiry. Repeated actions are not fresh
slot-paid casts and should not accidentally retrigger Counterspell. Damage/save
context and effect origins must remain truthful through DOTs, riders and summons.

## 5. Per-spell implementation cards

Each card states proposed rules, code location/reuse, concrete acceptance and
awkward interactions. Q references point to explicit human decisions in §8.
Names/classes in the audit are not a substitute for these authored rules.

### 01. Spare the Dying — rank 1, level 0

**Profile/location.** No BG3 spell. Human-chosen SRD 5.1 touch/action, Cleric,
necromancy; put `SpareTheDying` in `dnd/spells/necromancy.py`. Admit a present
DYING or STABLE creature at 0 normal HP, reject DEAD, positive HP, UNDEAD and
CONSTRUCT targets under this 5.1 profile. Use
`Entity.stabilize` without healing, reviving or restoring action agency. Record
the ordinary spell and life-state lineage. Q5 is resolved on the 5.1 profile.

**Setup/tests.** S1: DYING with failures becomes STABLE at 0 HP and its saves
reset; an already STABLE target remains stable; DEAD, positive-HP, undead and
construct targets reject before payment. Range/contact through a closed wall/window obeys the
same touch rules as Cure Wounds. A stable target damaged afterward resumes the
existing death-save path; no new death-save system.

**References/interactions.** `Entity.stabilize`, `CureWounds`, death-save tests in
`test_nature_spell_delivery.py`. Preserve separately owned magical Sleep/Hold;
stabilization must not act like healing, waking or Lesser Restoration. Silence
blocks the verbal cast; Antimagic/Counterspell use ordinary cantrip rules.

### 02. Vicious Mockery — rank 1, level 0

**Profile/location.** [BG3](https://bg3.wiki/wiki/Vicious_Mockery): action,
60 feet, WIS negates 1d4 psychic plus disadvantage on the next attack roll,
short target-turn expiry. Keep native 5/11/17 damage scaling. Add spell and
`Mocked` condition to `enchantment.py`; use an owned attack-disadvantage
contribution consumed by an actual attack-roll resolution, not damage receipt.

**Setup/tests.** S2/S5: save success means no damage/rider; failure gives first
weapon or spell attack disadvantage, a second attack normal, and no consumption
by Magic Missile/Fireball. Test end-of-target-turn expiry and psychic immunity
separately from condition immunity. A failed/missed attack still consumes the
next-roll effect; an action rejected before rolling does not.

**References/interactions.** Guiding Bolt's one-roll contribution,
`AttackD20RollResultEvent`, spell attack resolution, native modifier cleanup.
Bless/Bane and advantage cancellation still resolve normally. Do not copy the
BG3 bug that consumes Mockery on non-attack spells or turn it into generic fear.

### 03. Animal Friendship — rank 1, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Animal_Friendship) beast charm:
action, 60 feet, WIS save, Beast INT at most3, no concentration; ten turns,
one extra recipient per higher slot. Add to `enchantment.py` with a spell-owned
Charmed child and a damage
listener for caster/allied harm. Do not change faction, recruit the beast or
grant a controller. Use an explicit frozen caster relation/source, not current
target state. Decide ally definition by current native faction relation, not a
new party subsystem.

**Setup/tests.** S2: INT 3 beast can fail and is Charmed; INT 4 beast and humanoid
reject; immunity prevents charm. Beast cannot attack caster but can attack a
different enemy. Caster or ally harm breaks exactly this charm, unrelated enemy
harm does not. Test expiry, upcast recipients and two charm sources.

**References/interactions.** `CharmPerson`, `Charmed`, `DamageAppliedEvent`,
source-owned child cleanup. Calm Emotions/Protection block it appropriately;
Charmed is neither Dominate nor Animal Friendship AI control. Record the INT
boundary explicitly (BG3 rejects greater than 3), not an approximate beast filter.

### 04. Divine Smite — rank 1, level 1, new 5.2 spell identity

**Profile/location.** Human decision: BG3-style automatic on-hit Smite, with
NO click-to-accept reaction prompt and no 5.2 bonus-action spell cost. Add a
learned handler-backed spell root in `reaction_spell_content.py`, sharing the
existing Paladin delivery in `dnd/classes/paladin.py`. Reuse current per-slot
player toggles and native handler priority: highest enabled affordable level
fires once on an eligible melee hit, spends that slot, and keeps existing 5/6d8
caps and fiend/undead bonus. Do not build a reaction confirmation interface or
install a competing SpellAction that charges/delivers the same hit twice.

The new learned root and existing class feature must share exact handler/source
entitlement: removing one grant cannot disable a still-granted feature. Reuse
learned reaction ownership machinery rather than global semantic-name deletion.
If import direction needs a shared calculation, move only that calculation
below its two callers and preserve the DAG. Q1 is resolved; other attack-rider
eligibility/protection questions remain Q2/Q17.

**Setup/tests.** S3/S5: pre-toggle a slot level, hit automatically spends it and
adds dice without a request/pause; miss spends none. Test crit, fiend/undead,
insufficient slot, disabled handlers, ranged rejection and enabled-level
priority. Feature plus learned root charge/append once; removing either source
preserves the other entitlement and its chosen toggle state. Use native player
toggle/attack submission, not an accept-reaction UI fixture.

**References/interactions.** `create_divine_smite_processor`,
`register_divine_smite`, Shield learned root, typed `append_damage_roll` and
`toggle_player_handler`. Other eligible riders append their own components
without recursion; critical doubling occurs once. Preserve existing automatic
feature behavior rather than using the new catalog entry to redesign reactions.

### 05. Ray of Sickness — rank 1, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Ray_of_Sickness): action,
60 feet, ranged spell attack, 2d8 poison; on hit a CON save against two-turn
Poisoned; +1d8 per slot above first. Put in `necromancy.py`, using native ranged
spell attack plus a source-owned standard Poisoned child. This deliberately
uses BG3's CON-save rider rather than 5.2's different rider.

**Setup/tests.** S5: miss deals/applies nothing; hit plus failed/successful CON
save; crit doubles damage dice only; upcast changes damage. Poison damage
immunity and Poisoned immunity are independent. Standard ranged-threat,
long-range/visibility and Sanctuary checks apply before payment.

**References/interactions.** `ChillTouch` attack/control delivery,
`PoisonSpray` poison damage, native `Poisoned`, Protection from Poison and
Lesser Restoration. Removing poison should not erase other caster effects;
the one failed cast cannot leave concentration because this spell has none.

### 06. Starry Wisp — rank 2, level 0

**Profile/location.** No BG3 version. SRD 5.2 p.165: action, 60 feet, creature
or object, ranged spell attack 1d8 radiant; 5/11/17 scaling. Until end of caster's
next turn, target emits 10-foot dim light and cannot benefit from Invisible.
Add to `evocation.py` with exact-source reveal/light condition using §3.2.

**Setup/tests.** S2/S5: hit/miss/crit and cantrip levels; initially invisible
targets cannot be directly selected unless actually known/targetable, while an
already legitimate hit reveals to a second observer. Light follows movement,
expires on the correct caster turn, and independent invisibility can return.
Test an object target and target retirement. Damage immunity does not itself
turn a valid hit into a miss or suppress its rider.

**References/interactions.** `FireBolt` entity/object attack, `LightEffect`,
`GuidingBoltMarked`, shared Invisible/senses owners. Faerie Fire and Branding
Smite share reveal contributions; Darkness/walls/blindness still occlude. Do
not delete an innate invisibility source or substitute observer See Invisibility.
LightEffect itself currently resolves only Entity: Wisp's hit object needs an
item/BaseBlock-owned light/reveal condition using native anchored-light ownership
and the same narrow recipient-helper generalization as Magic Weapon.
Retiring that object must release its light and reveal without affecting another
source; no assumption that current LightEffect already supports object targets.

### 07. Dancing Lights — rank 2, level 0

**Profile/location.** [BG3](https://bg3.wiki/wiki/Dancing_Lights): one movable
30-foot-radius bright light, action/60-foot placement, ten-turn concentration; bonus
action relocation. Put spell/light owner and `MoveDancingLights` in
`evocation.py`, using spatial light registration and the repeated-action owner.
It is not four independent tabletop lights or a physical cat-like trap trigger.

**Setup/tests.** S4: placement changes observer-visible illumination; move
removes the old source and illuminates the new region; opaque walls still block
light; invalid/stale destination preserves source and costs; concentration
replacement/expiry removes source and exact relocation action. Two casters'
lights survive independent cleanup.

**References/interactions.** `LightEffect`, `DaylightZone`, source-owned radiance
movement tests in `test_weather_solar_spells.py`, Sunbeam's retained action
eligibility. Darkness and Antimagic use current light-contribution rules; no
vent-blocking or material occupancy is inferred from a light source. Retain the
casting source and clamp movement to declared range/LOS (Q6 duration/range policy).

### 08. Sorcerous Burst — rank 2, level 0

**Profile/location.** No BG3 version. SRD 5.2 p.163: action, 120 feet, creature
or object; ranged spell attack, 1d8 chosen acid/cold/fire/lightning/poison/psychic/
thunder, scaling 5/11/17. A natural 8 can add another d8, with a per-cast extra
die cap equal to the resolved casting ability modifier (never negative).
Add to `evocation.py` with native element facets and a bounded dice loop,
preserving every rolled face and component. This is not another multi-target
projectile or an unbounded recursive damage event.

**Setup/tests.** S5: ordinary roll; 8 then non-8; repeated 8s stop at cap;
zero/negative modifier adds none; cantrip levels and criticals; chosen damage
resistance and object target. At least one real Sorcerer learning/discovery test.

**References/interactions.** `FireBolt`, `PrismaticSpray` typed element branches,
`fixed_dice_faces`, current spell-damage affinity/reroll hooks. Resolve the
critical/die-reroll order once in the native roll path and test that bonus dice
are not doubled twice; follow Q7's delegated native-convention policy.

### 09. Dissonant Whispers — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Dissonant_Whispers): action,
60 feet, WIS save for half 3d6 psychic; failed save also applies two-turn fear
with movement denial; +1d6 per higher slot. Add to `enchantment.py`. Proposed
BG3-specific owned fear profile gives the documented penalties even when the
caster leaves sight. Use a separate owned condition with explicit native fear-immunity compatibility;
do not change global contextual `Frightened`. Q10 is resolved.

**Setup/tests.** S2/S5: save success halves damage with no fear; failure blocks
movement/penalizes attacks; immunity blocks only the rider. Caster exits sight,
target uses a save-only spell, and effect expires correctly. No reaction is
consumed and no forced escape/opportunity attack occurs.

**References/interactions.** `FearEffect`/`Frightened` transforms as references,
`PoisonSpray` save damage, standard condition immunity. Heroism/Calm Emotions/
Protection block eligible fear. Psychic resistance affects damage, not the WIS
outcome. This is the BG3 adaptation, not tabletop reaction-flee semantics.

### 10. Faerie Fire — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Faerie_Fire): action,60-foot
placement/20-foot-radius circle, DEX negates, ten-turn concentration;
no upcast benefit; affected targets glow, cannot benefit
from invisibility, and attacks against them have advantage. Add to `evocation.py`
using one cast-time recipient selection and per-target reveal/advantage
conditions linked to the same concentration. Do not create a continuously
re-saving aura or silently convert BG3's circle to the SRD cube.

**Setup/tests.** S2/S4: visible and invisible enemies/allies in area make their
own saves; failed recipients remain affected after leaving initial area, later
entrants do not gain it. Two observers see correct light/reveal changes;
concentration loss removes only this caster's effects.

**References/interactions.** `HypnoticPattern` cast-time AoE recipients,
`GuidingBoltMarked` incoming attack modifier, §3.2 reveal and Light effects.
Darkness, unseen attackers, blinded attackers and advantage/disadvantage
cancellation remain native. Test overlap with Starry Wisp without permanent
invisibility removal or duplicated advantage.

### 11. Heroism — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Heroism): action/touch,
ten-turn concentration; fear immunity and refresh to 5 temporary HP each turn;
one extra recipient per higher slot. Add to `enchantment.py` with a per-recipient
condition using source-owned immunity and `Health` temporary-HP grant identity.
Use the native refresh timing once per target turn; not additive 5 HP/round.
Casting removes existing fear immediately, then prevents renewal while active.
Removed fear does not return when Heroism ends.

**Setup/tests.** S1/S2: five temporary HP are spent, then refreshed; a larger
False Life pool remains; a later unrelated grant survives Heroism removal.
Test initial grant, expiry/concentration loss, removal of existing native/BG3-profile fear,
prevention of new fear and no old-fear return after expiry,
multi-target upcast and one rejected recipient without corrupting other links.

**References/interactions.** `FalseLife`, `Health.add_temporary_hit_points`,
`temporary_hit_points_grant`, `ProtectionFromPoisonEffect`, `Aid` multi-target
links. Refresh/removal must check this grant's exact source, not clear all temp
HP. Follow native duration conventions (Q6); Q11 resolves immediate fear removal
and source-owned, nonadditive temporary HP.

### 12. Hideous Laughter — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Tasha%27s_Hideous_Laughter):
action, WIS save, INT at least 5; concentration up to ten turns. Target remains
prone and unable to act; repeat save at turn end and on damage. Proposed
damage-triggered repeat advantage retains the SRD rule; inspected BG3 pages
do not establish that advantage. Use a separate spell condition with explicit native prone/control-immunity
compatibility in `enchantment.py`, with persistent owned
prone/agency-denial transforms and exact repeat-save handlers.

**Setup/tests.** S2/S5: low-INT target rejects; initial and repeat save pass/fail;
Stand Up cannot bypass active laughter; no duplicate damage-triggered saves
from a single damage resolution; ending effect leaves independently owned
Prone/Sleep/Hold intact. Test native opportunity attacks/agency while afflicted, explicit prone/control
immunity, Charmed immunity alone, and independent native Prone removal.

**References/interactions.** `SleepEffect` damage listener, Hold's turn repeats,
Prone transforms, prepared condition lifecycle. Do not copy Stunned's automatic
STR/DEX failures or normal Prone's automatic recovery. Use the INT gate and
authored prone/control eligibility: this spell does NOT apply Charmed, so ordinary
Charmed immunity alone does not block it. Apply any additional control immunity
only when a separately supported origin/effect rule actually requires it.

### 13. Create or Destroy Water — rank 2, level 1

**Profile/location.** [BG3 create](https://bg3.wiki/wiki/Create_Water) /
[destroy](https://bg3.wiki/wiki/Destroy_Water): action, 30-foot placement,
selected rain/water-surface creation or water-bearing surface removal, no
concentration; upcast increases area. Put root/typed variants in
`transmutation.py`, using existing Wet/Water recipes, `DOUSE`, and partial
replacement/removal operations. Q8 records the accepted destroyable material menu and
direct Wet duration; do not simulate reservoirs, drinking water or flooding.

**Setup/tests.** S4: create under creatures applies Wet and extinguishes fire;
Lightning Bolt electrifies water; cold freezes it; fire vaporizes it. Destroy
part of two independent patches, preserve outside cells and unrelated Wet
leases. Rejected/occluded placement spends nothing and reveals nothing.

**References/interactions.** `WetAreaCondition`, Wet source leases,
`WET_SURFACE_TRANSITIONS`, existing liquid-barrel area tests. Avoid treating
engine acid/poison residues as ordinary water or clearing every Wet condition
on every creature in the circle. A direct rain application and standing-water
membership need distinguishable exact owners.

### 14. Protection from Evil and Good — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Protection_from_Evil_and_Good),
with documented bugs excluded: touch/action, concentration until rest;
aberration/celestial/elemental/fey/fiend/undead attacks have disadvantage against
recipient, and those sources cannot charm/frighten it. Put in `abjuration.py`.
Use contextual incoming attack and condition-immunity contributions, reading
the incoming condition's actual source entity/type. Casting removes current
charm/fear from those eligible source types; removed effects do not resume later.
Q12 is resolved; possession has no native system and remains out of scope.

**Setup/tests.** S2/S3: fiend versus humanoid attacks; eligible/other source
Charm Person/fear; indirect condition retains true source; independent immunity
survives removal. Existing qualifying charm/fear is cleared, ineligible-source
effects remain, and cleared effects do not return after protection expires. Do not read the target's transient selected target to decide
who caused an incoming condition. Verify initial touch/LOS and concentration.

**References/interactions.** `ProtectionFromPoisonEffect`, Freedom of Movement's
contextual immunity, Charmed/Frightened, creature types. Proposed faithful
source-scoped behavior does not copy BG3's missing charm immunity or global fear
immunity bugs. General possession/mind control remains outside this batch.

### 15. Goodberry — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Goodberry): action/touch,
four berries in self/selected ally inventory; bonus-action consumption heals
1d4; no concentration/upcast benefit. Add spell and caster-owned batch lifetime
in `transmutation.py`, berry item/action in `dnd/items/consumables.py` and an
ordinary item declaration/builder under `dnd/content/items/`. No camp-supply
subsystem. Human-chosen BG3 until-long-rest lifetime follows exact berry UUIDs wherever
moved. Use the existing native rest boundary on the owning caster condition; no
new global party-rest clock or transfer-specific expiry exceptions (Q6).

**Setup/tests.** S1/S3: four real items after one paid cast; consume one through
item-use discovery, heal up to max HP, expend exactly one. Transfer, drop and
container storage preserve identity; caster rest retires only this batch's
remaining berries everywhere. Chill Touch blocks healing through normal
consumable rules. Failed inventory admission leaves neither free items nor
spell expenditure; recast creates an independent batch.

**References/interactions.** Healing potions, `EatFromFeast`, Heroes' Feast
object lifetime, BaseItem prepared retirement, Beacon of Hope/healing modifiers.
Do not rely on actor rest scanning ground items or invent a second healing path.

### 16. Divine Favor — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Divine_Favour): bonus action,
self, concentration for three turns; eligible weapon hits add 1d4 radiant;
no upcast benefit. Add spell/owner in `evocation.py` using §3.1 typed riders.
Do not modify generic spell damage or every weapon's permanent base damage.
Proposed BG3 eligibility excludes unarmed/spell attacks; Q2 covers body attacks.

**Setup/tests.** S3/S5: melee/ranged/offhand/opportunity hits gain one component;
crit doubles rider dice; miss, Eldritch Blast, Magic Missile and Fireball do not.
Weapon swap, immunity, expiry and concentration cleanup retain exact ownership.
Lethal damage/death saves see one original attack, not a late separate hit.

**References/interactions.** Typed Paladin/item damage append, native attack
category and source item. This caster cannot simultaneously maintain Hex/Mark
concentration, but item coatings and other independent riders still compose.
Caster ownership permits weapon changes without permanently enchanting old gear.

### 17. Searing Smite — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Searing_Smite): melee weapon
attempt costs action; bonus action/slot on hit. Initial 1d6 fire, +1d6 per higher
slot; ten-turn concentration burn ticks 1d6 with CON repeat to end. Add spell/DOT
in `evocation.py`, using §3.1 hit-cost/weapon attack composition. Q2 confirms
conditional payment and Q13 defines burn tick/save and extinguishing rules.

**Setup/tests.** S3/S5: miss spends attempt action only; hit pays slot/bonus once
and appends critical-aware initial fire; later DOT never inherits weapon crit.
Save success ends DOT; failed save repeats at its declared turn boundary.
Failed admission preserves prior concentration. Test expiry/death/water cleanup.

**References/interactions.** Paladin rider, native periodic condition ownership,
FireSurface/dousing hooks, Sanctuary/coatings. Wet/fire resistance affect damage
normally. Do not award two attack batches or apply Divine Smite twice to one
attack. Removing this magical burn must not erase unrelated fire owners.

### 18. Ensnaring Strike — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Ensnaring_Strike): melee or
ranged weapon attempt; action initially, bonus action/slot on hit, STR save
against ensnare; ten-turn concentration. Ensnared cannot move, incoming attacks
have advantage, its attacks/DEX saves disadvantage, and turn-start damage is
1d6 piercing plus 1d6 per higher slot. Add to `conjuration.py`, composing the
attack-backed path and owned Restrained transforms. Help removes its vines.

**Setup/tests.** S3/S5: hit/save pass keeps ordinary weapon damage without vines;
failure restrains/ticks; miss applies nothing. Both weapon/range variants obey
native eligibility. Help/concentration/death/expiry remove only this ensnare;
ordinary Extra Attack credit remains. No self-escape action or automatic repeat
save is granted: Q13 resolves recovery as BG3 ally Help. Verify that Ensnared
prevents opportunity attacks while active and restores eligibility on removal.

**References/interactions.** `EntangleRestrained`/Restrained transforms,
`ShakeAwake` exact-condition removal in `dnd/actions.py`, common action admission
in `dnd/actions_functional.py`, and `ConditionRemovalTrigger`. Add the narrow
ally-assistance action/removal eligibility needed for these vines (BG3 Help uses
an action and 7-foot range); reject self-assistance and remove the exact vine
condition. Register its common action identity/discovery and native AI support
semantics where applicable. This is not a full BG3 Help/status recovery rewrite.
`EscapeEntangleAction` is a reference only: do not grant its self-escape behavior. Freedom of Movement negates
eligible restraint without deleting unrelated effects. No map-wide Entangle
zone or unsupported large-creature advantage is silently added.

### 19. Hunter's Mark — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Hunter%27s_Mark): bonus action,
60 feet, concentration until rest; caster weapon hits against quarry add 1d6
matching qualifying weapon damage, crit-aware. Add to `divination.py` with
caster sustain/retarget state, exact target relation and granted bonus-action
`ReapplyHuntersMark`, no additional slot after quarry defeat. Q2 defines
death/downing and unarmed/body eligibility. No new RP tracking queries.

**Setup/tests.** S3/S5: marked/unmarked targets, two casters, offhand/opportunity
hits, two weapon damage types, crit/miss; no spell/save-only bonus. Defeat enables
reapply while concentration continues; repeated transfer changes quarry without
duplicating handlers. Rest/concentration/caster death remove mark and action.
Rejected retarget preserves the caster-owned sustain marker and reapply state;
quarry death cannot empty the last concentration link (§3.6).

**References/interactions.** DamageCurse relationship concept, typed append
rather than its late damage code; Sunbeam/ConcentrationActionMarker granted
action ownership. Summons do not inherit Mark unless an independently authored
class feature grants it. Same-caster Hex concentration cannot coexist.

### 20. Chromatic Orb — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Chromatic_Orb): action,
60-foot ranged spell attack. Thunder 3d8/no surface; acid/cold/fire/lightning/
poison 2d8 plus chosen surface; +1d8 per higher slot. Add to `evocation.py`
with element facets and registered surface recipes. No SRD 5.2 bounce.

Cold/fire/lightning reuse Ice/Fire/ElectrifiedWater. Acid needs a thin AC-minus-2
surface shared with Acid Arrow; poison needs the selected Simple Toxin payload,
not toxic body residue. BG3 variants use approximately 7-foot-radius/two-turn
surfaces. Q8 records the accepted toxin payload, miss placement and direct
ground targeting.

**Setup/tests.** S4/S5: each element's damage/surface; thunder leaves none;
crit/upcast/miss policy, occupied/walled patch and partial expiry. Overlapping
acid does not repeatedly subtract AC. Poison damage and condition immunity
remain separate; fire/Web/water and lightning/cold use existing transitions.

**References/interactions.** Fire Bolt, Ice Knife attack-plus-area lineage,
Prismatic Spray choices, environmental replacements. Initial attack and later
surface ticks retain distinct applications and truthful casting source.

### 21. Hex — rank 2, level 1

**Profile/location.** [BG3](https://bg3.wiki/wiki/Hex): bonus action/60 feet,
concentration until rest; each caster attack-roll hit on quarry adds 1d6
necrotic. Chosen ability has CHECK disadvantage, not saves/attacks. Add to
`enchantment.py`, with six typed ability variants, exact caster/quarry link and
bonus-action reapply after defeat. §3.1 must cover weapon and spell rays.

**Setup/tests.** S3/S5: melee/ranged/offhand and each Eldritch Blast/Scorching
Ray hit with A/B/A allocation; crit applies only to its own attack. Magic
Missile, Fireball, DOT and retaliation never proc Hex. Raw ability checks and
linked skills change; saves/attacks do not. Another caster gains no damage.
Reapply/no-slot/lifetime follows Mark; Q2 settles downing/KO eligibility.

**References/interactions.** AbilityCurse shows ability-to-skill mapping but
also penalizes saves: reuse only the needed checks. DamageCurse's late direct
hit is unsuitable. Use native multi-ray affinity/critical tests, typed damage
finalization and exact condition removal. No rider-on-rider/retaliation recursion.

### 22. Calm Emotions — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Calm_Emotions): action,
60-foot placement/20-foot radius, ten-turn concentration; remove/prevent charm,
fear and rage. Put in `enchantment.py` with cast-time recipients and owned
immunity/action-eligibility contributions. Proposed humanoid-only respects the
description rather than the unrestricted-target bug. No save or arbitrary
faction pacification is added. Q10/Q12 record the accepted control/removal rules.

**Setup/tests.** S2/S3: current Charmed/Frightened/Raging roots end; Frenzy
descendants and rage damage/resistance clean up. Rage cannot restart during
Calmed, and works after expiry. Independent immunities remain. Allies/enemies
can be recipients; later area entrants do not automatically gain the spell.

**References/interactions.** Lesser Restoration, owned immunity, `rage.py` /
`barbarian.py` action prerequisites and condition graphs. Merely adding immunity
to a display-name Rage is insufficient if activation still succeeds. NPC
berserk variants need explicit tags/identities, not substring name matching.

### 24. Phantasmal Force — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Phantasmal_Force): action/
60 feet, INT save, ten-turn concentration; start-turn 1d6 psychic that follows
qualifying external damage type; end-turn INT repeat ends it. Put in
`illusion.py`, using turn hooks and typed committed-damage observation. No
arbitrary image/belief simulation.

**Setup/tests.** S5: initial/repeat save pass/fail; one start tick; external
fire then cold changes next tick; own DOT never changes its type. Resistance,
immunity, zero accepted damage, two sources and concentration cleanup. Mixed
hits use Q7's deterministic component rule, not incidental dictionary order.

**References/interactions.** Eyebite repeat saves, matching completed
TakeDamageEvent resolution plus positive DamageAppliedEvent, and retained
effect origin. Q7 selects the largest positive resolved external
component, using existing stable component order for ties and ignoring zero
damage; this deliberately avoids BG3's arbitrary status
priority. A physical-plus-elemental hit supplies actual resolved components,
without recursively changing the same effect while processing its own tick.

### 26. Spiritual Weapon — rank 2 estimate, level 2; summon integration

**Profile/location.** [BG3](https://bg3.wiki/wiki/Spiritual_Weapon): bonus action,
60-foot real summon, ten turns, NO concentration. Baseline 20 HP/AC10, 20-foot
supported flight, psychic/poison immunity and other resistance; own initiative/
control. Attack uses caster proficiency/casting modifier, damage
1d8+1+casting modifier force; +1d8/+8HP per two higher slots. Root goes in
`evocation.py`; new concrete recipes can live in a bounded
`dnd/monsters/spell_summons.py`, registered like other creature recipes; extend
existing summoning families/forms/lifecycle, not another summoning service.

Use §3.5's existing caster-owned autonomous monster-summon model: the weapon
acts through NativeAIController, with caster faction/dismissal and current
after-caster turn joining. No player-seat/audience control changes. Q3 retains
plain weapon versus three functional forms/stat snapshots; cosmetic variants
and client presentation are excluded unless separately requested. No opportunity attacks; one active weapon per
caster independently of animal summons. Do not silently substitute a caster
bonus-action tabletop marker or invent unimplemented weapon specials.

**Setup/tests.** S6/S7: valid/invalid birth, native autonomous turn/move/attack,
caster-based accuracy/damage/upcast, defeat/expiry/recast and caster dismissal.
The AI attacks enemies and preserves allies; server advances to the next human
input boundary without assigning the summon to a player seat. Another concentration spell does not delete it;
Antimagic follows native summon suppression/restoration. Snapshot casting stats
at birth unless Q3 explicitly selects dynamic values.

**References/interactions.** SummoningSystem, prepared combatant join, Conjure
Animals, autonomous summon tests and terminal/retirement tests. Reuse the
current controller lifecycle; add only the weapon recipe/actions and necessary
spell parameters, not the previously proposed player-control infrastructure.

### 27. Flame Blade — rank 2 estimate, level 2; temporary weapon profile

**Profile/location.** Normal [BG3 spell](https://bg3.wiki/wiki/Flame_Blade):
bonus action/self, ten-turn real scimitar, NO concentration; 3d6 fire, +1d6
per two higher slots; 10-foot bright/20-foot dim light. Unequip/re-equip allowed,
but weapon stays with caster. Attacks use melee SPELL accuracy/casting ability,
no ability damage, with Extra Attack exception. Root/lifetime in `evocation.py`,
item/builder in item owners, narrow item attack profile in equipment/actions;
retain original casting source, not latest multiclass stat.

**Setup/tests.** S3/S5: occupied hand safely stores prior weapon; hit/crit uses
spell accuracy, no STR damage; Extra Attack works without all weapon-only
riders. Offhand profile/cost explicit. Unequip/re-equip persists; transfer/drop
follows Q14; expiry removes blade/light only, never deletes unrelated gear or
restores a stale weapon snapshot. Test death, Antimagic and recast.

**References/interactions.** Shillelagh exact-item ownership, Weapon/BaseItem
retirement, `Attack._on_costs_committed` batch credit, LightEffect. Hex qualifies;
Hunter's Mark/Divine Favor generally do not. Spell accuracy buffs qualify;
ordinary weapon modifiers do not unless explicitly applicable. Q14 confirms
this hybrid profile versus a deliberately simpler adaptation.

### 28. Moonbeam — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Moonbeam): action/60-foot
placement, approximately 3-foot radius; ten-turn concentration, 2d10 radiant,
CON half, +1d10 per higher slot. `MoveMoonbeam` action relocates within 60 feet
without another slot, retaining source/DC/level. Root/area/repeat action in
`evocation.py`; reuse AreaCondition rather than creating an autonomous creature
solely to copy BG3 damage-attribution quirks.

**Setup/tests.** S4/S5: appearing under target, ordinary/forced entry, start
inside, beam moved over stationary target and repeated crossing. Specify each
exposure and avoid APPEAR+ENTER double ticks. Save/immune/upcast, friendly fire,
concentration loss, stale relocation and suppressed action. Retain small radius
if current geometry supports it; do not silently round to five feet.

**References/interactions.** Cloudkill movement, Spirit Guardians exposure
fences, Sunbeam retained actions and spatial duration tests. Preserve native
Sanctuary/affinity attribution rather than BG3 summon-proc bugs. Q9 records the accepted
entry/appearance/move cadence and declared grid footprint; no unimplemented
shapeshifter transformation is silently added.

### 29. Pass without Trace — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Pass_Without_Trace): action,
self, concentration until long rest; caster-following 30-foot allied aura
grants +10 Stealth including caster. Put in `abjuration.py` using
MembershipAreaCondition and exact source-owned Stealth modifiers. It does not
automatically hide actors, silence casting or remove tracked physical residue.

**Setup/tests.** S2/S4: ally enters/leaves, caster moves, enemy receives no
bonus; opaque separation follows current aura propagation. Two caster auras do
not add +20; one leaving/removing does not remove the other contribution. Rest,
death, concentration loss and Antimagic update affected occupants and discovery.
Make a real Hide/Stealth check so the bonus matters beyond a displayed number.

**References/interactions.** Spirit Guardians following membership, Wet source
leases, skill modifiers, existing hide/perception rules. Invisibility is not
required and the spell does not defeat Faerie Fire/reveal. Proposed same-spell
nonstacking is explicit strongest contribution, not accidental dictionary order.
Q6 covers until-rest conventions; no new wilderness tracking system.

### 30. Flaming Sphere — rank 2 estimate, level 2; summon integration

**Profile/location.** [BG3](https://bg3.wiki/wiki/Flaming_Sphere): action,
60-foot summon, ten-turn concentration; real elemental, 20 HP/AC16, 30-foot
movement, own turn and bonus-action Ram. Nearby/ram damage 2d6 fire, DEX half,
+1d6 per higher slot; 5-foot end-turn aura radius, moving 20-foot bright plus
20-foot further dim light and fire trail. Root goes in `conjuration.py`, recipe
and specific Ram/aura in `dnd/monsters/spell_summons.py` (new), using the same
summoning integration as Spiritual Weapon. Retain true caster save DC, excluding
BG3's hardcoded-Wisdom bug.

**Setup/tests.** S4/S6/S7: valid paid birth, autonomous AI move/Ram and end/start
exposure per Q9, damage to creatures and breakable objects, actual resistances/
immunities, light/trail update, death/expiry/concentration cleanup. Verify accepted
enemy-only creature aura damage separately from the trail, which can burn allies;
damageable objects use the existing environmental cadence.
No permanent free summon after canceled birth, no duplicate trail on replay.

**References/interactions.** SummoningSystem, FireSurface, moving membership,
light registration, native object damage and existing monster-summon controller.
Caster faction/ownership/dismissal follow the existing path, with no new player
membership or vision sharing. Q9 records accepted aura cadence, native trail duration and
water/dousing behavior. The 5-foot aura follows the actual Ablaze description;
the general spell page's 7-foot display differs. This cannot
be silently replaced by an invulnerable caster-bonus-action area marker.

### 31. Branding Smite — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Branding_Smite): attack-backed
melee OR ranged weapon; action for attempt, bonus action/slot on hit. Add 2d6
radiant, +1d6 per higher slot; ten-turn concentration mark prevents invisibility.
Root/mark in `evocation.py`, sharing §3.1 hit-cost composition and §3.2 reveal.
No STR/DEX/etc save is invented for the initial mark.

**Setup/tests.** S3/S5: melee/ranged hit and miss costs, crit/upcast, one original
attack batch, light/reveal observed by another actor, concentration cleanup and
two reveal sources. Reject illegal weapon/target before payment. Do not copy
BG3's accidental item-marking/hidden-ground-target quirks.

**References/interactions.** Paladin/item rider, Starry Wisp/Faerie Fire reveal,
native attacks/Extra Attack. Test Shillelagh/Magic Weapon and coated weapons;
reveal ends without erasing unrelated invisibility. Q2 settles conditional cost,
weapon/body eligibility and Divine Smite coexistence. Light brightness/radius
should use a documented mark profile, not a guessed full Daylight field.

### 32. Magic Weapon — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Magic_Weapon): action/touch,
concentration until rest; exact weapon gets magical status and +1 attack/damage,
+2 at slot4/5 and +3 at slot6+, stacks with inherent enchantment. Root/item
condition in `transmutation.py`; use exact weapon attack_bonus/damage_bonus
ModifiableValues, with a small independent source-owned magical contribution
recognized by `Weapon.attack_is_magical`. Do not install another d8/ability
override or snapshot/restore the weapon's entire state.

**Setup/tests.** S3: ordinary/enchanted weapon, Shillelagh quarterstaff and
offhand/ranged variants; actual hit/damage and damage-resistance bypass. Transfer,
drop/re-equip, suppression and concentration loss remove only owned modifiers;
base enchantment, later coating and independent caster contribution survive.
Reject nonweapon and unavailable target before cost. Q14 confirms target UI and
same-spell strongest-nonstacking behavior.

**References/interactions.** Shillelagh exact-item tracking, weapon profile
builders, source modifier cleanup, prepared concentration helper. Attacks from
other weapons never gain the bonus; current wielder must be used for equipped
item disclosure/accuracy, not the original caster's stale slot.

### 33. Dragon's Breath — rank 2, level 2

**Profile/location.** No BG3 version. SRD 5.2 p.126: bonus action/touch a willing
creature; choose acid/cold/fire/lightning/poison; ten-turn concentration. Recipient
gains an action for 15-foot cone, DEX half, 3d6 chosen damage plus 1d6 per higher
slot. Root/owner/granted cone action in `transmutation.py`, using Sunbeam's
retained owner/source/level and Burning Hands' cone targeting. Caster maintains
concentration even when recipient uses the action.

**Setup/tests.** S4/S5: self/ally recipient, element selection, recipient's
action spent not caster's, true caster DC despite weaker recipient stats,
upcast retained on repeat; friendly fire, wall/geometry and save/immune targets.
Concentration loss, recipient death or Antimagic disables/removes action. A
stale submitted activation fails without extra slot consumption.
Use original caster and recipient with different spellcasting classes/stats;
remove the original casting source and apply a recipient-local spell modifier
to verify no silent source-ID fallback or double application (§3.6).

**References/interactions.** Sunbeam/ConcentrationActionMarker and source
propagation, Cone shape/preview, elemental surface interactions. Multiple
recipients/metamagic need existing native target-count rules only; do not invent
Twinned Spell behavior. Q13 settles whether mouth/speech anatomy is an enforced
restriction or merely future content, without creating body-anatomy simulation.

### 34. Acid Arrow — rank 2, level 2

**Profile/location.** [BG3](https://bg3.wiki/wiki/Melf%27s_Acid_Arrow): action,
60-foot ranged spell attack; hit 4d4 acid now plus 2d4 at target's next turn end;
miss half initial damage with no DOT; +1d4 to each part per higher slot. Add
root/DOT in `evocation.py`, with the acid surface shared with Chromatic Orb.
Attack miss-half is real additional behavior compared with Fire Bolt; apply
normal defenses once, not a fabricated successful attack outcome.

**Setup/tests.** S4/S5: hit/miss/crit; crit doubles immediate hit dice only,
not next-turn DOT; delayed damage exactly once even after movement; upcast,
acid resistance/immunity and source death. Preserve actual miss in events so
Hex/Guiding Bolt do not turn miss-half into a hit. Q8 records accepted surface creation/
footprint/duration on hit and miss.

**References/interactions.** Ice Knife mixed attack/secondary lineage, native
one-turn conditions/turn hooks, damage component finalization. Two arrows from
different casters need explicit same-spell effect policy rather than overwriting
each other's unrelated state. The acid AC surface is not corrosive body residue
or another immediate acid damage packet.

### 35. Glyph of Warding — rank 2, level 3

**Profile/location.** [BG3](https://bg3.wiki/wiki/Glyph_of_Warding): action,
30-foot placement, approximately 13-foot radius, no concentration; one glyph
per caster until trigger/recast/rest. Fixed variants: acid/cold/fire/lightning/
thunder 5d8 DEX half (+1d8/slot above3), Detonation DEX-negated 20-foot push,
Sleep DEX-negated two-turn Sleep without HP pool. Root/glyph/variant action in
`abjuration.py`, using AreaCondition, native damage/sleep/forced movement.

Enemy entry triggers once; blast affects ALL factions. Existing enemy occupancy
on cast triggers immediately. Snapshot recipients, disarm the glyph before
resolving payloads, and keep native event causality. Recast/expiry cleanup cannot
remove another caster's glyph. No arbitrary stored spell, password language or
programmable trigger engine.

**Setup/tests.** S4/S5: ally crosses safely; enemy enters with allied collateral;
initial hostile occupancy; two entries in one movement; concentration of caster
is unaffected. Every payload save/upcast, push collision and Sleep waking.
Q9 records accepted trigger behavior; Q8 records the footprint. Q13 retains
the still-proposed extra waking options. Wall/closed
door and Antimagic interactions use existing propagation and suppression.

**References/interactions.** SpikeTrap/TrapPayload show trigger ownership only;
do not stuff arbitrary magical effects into the poison-only hardware payload.
Use SleepEffect rather than Sleep HP allocation, current forced displacement
from the glyph centre and once-only area retirement. Surface transitions from
elemental payloads follow their existing definitions.

### 36. Plant Growth — rank 2, level 3

**Profile/location.** [BG3](https://bg3.wiki/wiki/Plant_Growth): action,
60-foot placement/20-foot radius, ten turns, no concentration/save; ground
vegetation costs four feet per foot moved and can burn away. Root/area in
`transmutation.py`, using a source-owned ground movement-cost contribution and
partial fire removal in the current spatial interaction owner. No existing
plant prerequisite, agricultural enrichment or plant growth simulation.

**Setup/tests.** S4: enter/cross/leave with exact spent-budget accounting,
Haste/Slow, Dash and supported-endpoint Fly; partial fire removes affected cells
only, leaving remaining vegetation; two overlaps and expiry preserve unrelated
terrain. Preview/discovery and executed movement must agree. Q9 accepts the
strongest applicable terrain factor rather than repeated multiplication, and
Freedom of Movement bypass.

**References/interactions.** SpikeGrowth movement-cost composition (not its
damage), Grease terrain, Freedom of Movement and liquid partial transitions.
Do not multiply the actor's global walking speed or reset previously spent
movement when entering/leaving. User-visible terrain cannot silently claim all
forms of movement are blocked or slowed identically.

### 37. Revivify — rank 2, level 3

**Profile/location.** [BG3](https://bg3.wiki/wiki/Revivify): action, eligible
dead/downed companion within 30 feet, returns at 1 HP, optional valid relocation
within spell bounds. No corpse-age/diamond economy in this adaptation. Root in
`necromancy.py`; DEAD routes to `Entity.revive`, DYING/STABLE to ordinary
`receive_healing`. Do not trust revive's stale docstring: its body accepts DEAD
only and rejects DISINTEGRATED remains. Q16 settles companion eligibility,
downed support and destination policy.

**Setup/tests.** S1/S7: DEAD/DYING/STABLE targets, positive-HP/noncompanion
rejection, disintegrated remains, legal/blocked relocation, stale target, and
restored combat eligibility. Validate target/destination before native cost and
commit the relocation/revival coherently using existing prepared mutation
owners; do not revive then discover the destination is invalid. Existing revive
is a direct operation, not a prepared revival transaction: preflight movement
and vetoable revival together and add a narrow prepared revival operation if
that is needed to prevent partial state. Do not claim the combined atomicity
already exists. Revival cannot
accidentally reduce exhaustion or clear unrelated Sleep/Hold.

**References/interactions.** `revive`, `receive_healing`, prepared spatial return,
Dimension Door compound choices and LifeState facts. Death Ward/Chill Touch
and downed healing differ from DEAD revival; test the chosen healing-block
policy explicitly. No need to implement a full corpse-decay subsystem.

### 38. Vampiric Touch — rank 2, level 3

**Profile/location.** [BG3](https://bg3.wiki/wiki/Vampiric_Touch): action,
five-foot melee spell attack 3d6 necrotic (+1d6 per higher slot); concentration
ten turns; heal caster half qualifying damage and grant repeated action without
another slot. Root/owner/repeat in `necromancy.py`, using Sunbeam's retained
action pattern and typed damage completion. Grant before initial resolution
can break concentration; do not double-charge the initial attack.

**Setup/tests.** S5: hit/miss/crit, resistant/immune/temporary-HP target, low-HP
overkill, healing blocked/max HP, initial and repeated paid actions, retained
upcast/source/DC. Use final qualifying damage rather than raw requested damage.
Q7 uses native post-mitigation damage including temp-HP absorption/overkill,
excluding separate Hex/coating/other rider damage from healing. Test target death and control loss.

**References/interactions.** Inflict Wounds melee spell attack, Sunbeam owner,
matching completed TakeDamageEvent.resolution components, own-component
attribution and positive DamageAppliedEvent, ordinary healing and Beacon of Hope.
Hex can add necrotic attack damage without silently increasing Vampiric Touch's
own healing basis. Antimagic disables a still-retained repeat action; stale
submission cannot execute after concentration is gone.

## 6. Parameter corrections and source precision

The following table collects easy-to-miss values from source review. All are
proposed profiles for this batch, with Q references for unresolved choices.

| Spell | Precise profile / deliberate retained rule |
| --- | --- |
| Animal Friendship | 60ft, Beast INT≤3, WIS, **ten turns**, **+1 recipient per slot above1**, no concentration. |
| Vicious Mockery | Next actual attack roll, one-turn target expiry; 5/11/17 engine scaling. |
| Faerie Fire | 60ft placement, **20ft-radius circle**, ten turns concentration, no upcast; all cast-time creatures save. Not SRD cube. |
| Hideous Laughter | 60ft, INT≥5, ten turns; damage/end-turn WIS repeats. Damage-repeat advantage is an explicitly retained SRD rule proposed here; inspected BG3 page does not establish it. Persistent BG3 condition includes STR/DEX save disadvantage and within10ft incoming advantage, never automatic save failure; Help does not clear it. |
| Calm Emotions | 60ft placement,20ft-radius circle,ten-turn concentration,no save/upcast; proposed humanoid restriction, no faction pacification. |
| Create/Destroy Water | 30ft placement,13ft radius,+7ft radius/slot; direct Wet3turn. Accepted Q8 adaptation: persistent native water and direct rain Wet/reveal for3turn, with exact independent source ownership. |
| Moonbeam | 60ft placement/relocation,3ft-radius footprint,ten-turn concentration,2d10 CON half,+1d10/slot. No silent minimum5ft radius. |
| Pass without Trace | 30ft allied aura,until-rest concentration,+10 Stealth,no upcast. |
| Glyph of Warding | 30ft placement,13ft radius; damage5d8 DEX half,+1d8/slot; Sleep2turn DEX negates; Detonation20ft push DEX negates. |
| Spiritual Weapon | Baseline20HP/AC10/20ft movement; own attack uses bonus-action attack on summon as documented for Maul, not caster's recurring bonus action. Variant specials require Q3; baseline is not AC14. |
| Flame Blade | Normal spell is nonconcentration, real item with melee spell accuracy/no ability damage; Extra Attack exception. The racial version differs and is not added. |
| Divine Favor | BG3 three-turn concentration, not silently ten turns or the 2024 no-concentration form. |
| Dancing Lights |30ft bright radius; no physical trap/vent occupancy. For all spell lights, native dim radius is additional beyond bright (§3.2). |
| Flaming Sphere |20HP/AC16/30ft movement; Ram bonus action with5ft contact; immune fire/necrotic/poison/psychic, resistant physical/acid/lightning, vulnerable cold; toggled Ablaze/trail uses the selected Q9 cadence. No Explorer-mode doubled HP profile is added. |

Sources supporting the refinements include
[Hideous Laughter condition](https://bg3.wiki/wiki/Hideous_Laughter_(Condition)),
[Create Water](https://bg3.wiki/wiki/Create_Water),
[Water surface](https://bg3.wiki/wiki/Water_(surface)),
[Move Moonbeam](https://bg3.wiki/wiki/Move_Moonbeam),
[Glyph Sleep](https://bg3.wiki/wiki/Glyph_of_Warding:_Sleep),
[Glyph Detonation](https://bg3.wiki/wiki/Glyph_of_Warding:_Detonation),
[Spiritual Weapon Maul](https://bg3.wiki/wiki/Spiritual_Weapon:_Maul),
[Chromatic Orb Poison](https://bg3.wiki/wiki/Chromatic_Orb:_Poison),
[Chromatic Orb Lightning](https://bg3.wiki/wiki/Chromatic_Orb:_Lightning),
and [Acid surface](https://bg3.wiki/wiki/Acid_(surface)).

## 7. Implementation order and validation

### 7.1 Order by real dependencies

Before implementation, discuss §8's affected choices and record the human's
answers here. Those answers supersede the recommendations. Keep unaffected
work moving once implementation is authorized. No speculative framework phase
or unrelated renderer/performance overhaul precedes the spells.

| Wave | Spells/cards | Shared work delivered with the first consumer |
| --- | --- | --- |
| A: direct/control/aura,13 | 01,02,03,05,06,08,09,10,11,12,14,22,29 | Next-roll condition, exact reveal, persistent laughter/Calmed, sourced temp HP and existing membership. |
| B: attack and weapon riders,8 | 04,16,17,18,19,21,31,32 | Weapon+spell hit boundary, conditional hit costs, retarget state, independent magical weapon contribution. |
| C: moving effects/surfaces,8 | 07,13,20,24,28,34,35,36 | Small acid/toxin definitions, declared exposure cadence, repeat actions, exact partial surface changes. |
| D: items/retained actions/life,5 | 15,27,33,37,38 | Cross-location created-item lifetime, Flame Blade spell-attack profile, revival compound selection. |
| E: spell summons,2 | 26,30 | Real spell-summon recipes/actions using existing autonomous summon/control lifecycle. |

Within waves, land coherent native behavior + registration/discovery + focused
tests together; do not stockpile disconnected spell classes. Wave A reveal
supports Branding Smite; B riders support Hex/Vampiric Touch/Flame Blade tests;
C surfaces support Flaming Sphere; D item ownership informs summon payloads.
The waves cover every card once, not independent promises to ship five separate
spell-demo applications. The final product verification uses S7 integrated play.

### 7.2 Testing lanes

1. **Before edits:** prepare the documented uv environment if absent. Run one
   meaningful baseline of the active native/player/progression/import tests;
   record existing failures by observable contract. Do not repeatedly rerun the
   whole baseline or checksum files during ordinary implementation.
2. **Per family:** implement the cards' small deterministic in-memory scenarios,
   keeping real action/slot/turn/ownership calls. Extend current tests where they
   already own the behavior; a few focused new family files under
   `tests/engine/` are reasonable. Reuse a simple setup/check helper, not a new
   universal scenario DSL. Add progression and native discovery cases where
   learning/eligibility changes.
3. **Public contract:** representative S7 discover/preview/submit tests through
   `dnd/player`/server and existing SDK tests for each materially different
   action shape. For summons, qualify existing autonomous controller progression,
   ordinary birth/departure observations and the next human input boundary;
   do not add a player-membership protocol change or browser-control requirement.
4. **Final batch:** run the affected family suites, active engine/player/
   progression/architecture lane, SDK tests and type checks once changes settle.
   Broaden only for changed ownership/protocol surfaces or new failures. Test
   import DAG rules separately from gameplay. Retired server/manual legacy
   failures are not silently waived or presented as active feature proof.
5. **Integrated native/server gameplay:** exercise an encounter through the
   server/SDK with a control spell, rider, moving field, temporary item and
   autonomous summon. Check authoritative outcomes, choice costs, light facts,
   retained effects and cleanup. No NDClient code, presentation, assets, browser
   journeys or visual acceptance/handoff is required: the human excluded it.

Use README's runtime preparation and `uv run --no-sync python -m pytest` with
the intended worktree/environment. Do not introduce new dependency installation
or change the lock for planning. Exact commands should name real existing paths
at implementation time; SDK package scripts are authoritative for their checks.
Tests should assert HP, modifiers, legal choices, ownership, state and retained
facts, not private closure counts, implementation class shapes or raw log prose.

### 7.3 Required reviewers and implementation oversight

- **Anti-slop reviewer:** scope stays these 36; choices are visible; no invented
  prerequisites, phantom bindings, complete-class-system claims, asset receipts
  or checksum rituals; tests prove useful outcomes and final integrated play.
- **Anti-OOP/ECS reviewer:** existing data/composer/event/spatial/value owners
  remain authoritative; source cleanup and import DAG are correct; no late
  imports, `getattr`, type-check bypasses, generic spell service/manager or a
  separate area scheduler. Native authored subclasses are existing content
  structure, not permission to create stateful parallel orchestration.
- **Plan-adherence subagent during implementation:** continuously track the
  human-approved scope, accumulated feedback and remaining whole-batch goals;
  interrupt drift into tiny details or unrelated debt. This is required when
  implementation starts, not a substitute for source/test reviews.

Review coherent changes/final implementation rather than ceremonial sign-off
after every spell. Any rule answer or scope correction is accumulated in this
same plan. No reads/messages to other chat threads are needed or permitted.

## 8. Doubts and decisions for discussion

The human's latest answers refer to the enumerated discussion list, not the Q
identifiers retained here for stable document references. Enthrall and Heat Metal
are excluded. Spare the Dying, BG3 Goodberry, the delegated native damage defaults,
surfaces/areas, control-condition immunity handling, immediate fear/charm removal
and BG3 Ensnaring recovery are recorded below. Globe/Antimagic scope is existing
compatibility only. Unanswered choices remain proposals, not inferred approvals;
only affected undecided behavior waits, not unrelated authorized work.

| ID | Affected spells | Doubt and proposed decision |
| --- | --- | --- |
| Q1 | Divine Smite — RESOLVED | Human chose BG3 style and stated there is no accept-reaction UI. Reuse existing automatic hit handler and per-level toggles/current highest-enabled-affordable priority, hit-only slot payment, existing5/6d8 caps and shared feature/spell entitlement. No new confirmation prompt or5.2 bonus-action surface. |
| Q2 | Divine Favor, Searing/Branding/Ensnaring, Hunter's Mark, Hex — PARTLY OPEN | BG3 Ensnaring cost/recovery is now chosen by the human. For the other affected spells, **recommend documented BG3 conditional hit payment** for attack-backed smites; weapon-only riders exclude unarmed and treat natural/body attacks only when explicitly eligible. Mark transfer on death; Hex on death/KO. Engine downing is not necessarily BG3KO: decide whether either may reapply on DYING/STABLE. Preserve native Extra Attack/Haste rules. |
| Q3 | Spiritual Weapon, Flaming Sphere — CONTROL PATH RESOLVED | Human directed the fire summon to behave like existing summoned monsters. Source confirms caster-owned allied autonomous AI turns/dismissal; reuse that model and existing after-caster joining. No direct-player-control/seat/audience/vision-sharing project. Spiritual Weapon uses the same proposed common path. Remaining choice: plain weapon or functional weapon forms, with casting-stat snapshot recommended; no cosmetic/client work. |
| Q4 | Enthrall — REMOVED | Human excluded Enthrall. No spell, replacement Perception adaptation or facing/peripheral-vision extension in this batch. |
| Q5 | Spare the Dying — RESOLVED | Human chose SRD 5.1 touch/action Cleric cantrip with existing stabilization and undead/construct rejection. No 5.2 range/class-list switch. |
| Q6 | Durations and Goodberry — NATIVE CONVENTIONS / BG3 | Goodberry uses human-chosen BG3 four berries, 1d4 healing, bonus-action consumption, no upcast benefit, until long rest. Track exact UUIDs through the owning caster condition and its existing native rest event; do not add a global party-rest clock, food economy or transfer-specific duration exceptions. Use existing round/rest lifecycle for other cards and do not clear an until-rest effect just because combat ends, except where native termination/concentration rules require it. Routine lifecycle choices use native conventions, not new spell-specific frameworks. |
| Q7 | Sorcerous Burst, Phantasmal Force, Vampiric Touch — DELEGATED | Human delegated sensible implementation with no invented exceptions. Burst uses native critical/reroll handling, rolled 8s and a nonnegative casting-modifier extra-die cap, with no double-doubling. Phantasmal uses the largest positive post-mitigation external component, ties in existing stable component order; own ticks and zero damage do not change type. Vampiric heals half its own post-mitigation necrotic damage rounded down, including temp-HP absorption/overkill, excluding Hex/coatings/other riders. Keep accounting in the native damage owner; no separate HP-allocation framework. |
| Q8 | Water, Chromatic Orb, Acid Arrow, Glyph — RESOLVED | Human accepted enumerated surface recommendations: preserve declared 13/7/3ft radii; persistent native water until removed/transformed, direct rain Wet and reveal for 3 turns; destroy Water/ElectrifiedWater/Ice/Steam/new SimpleToxin only, no Blood system. Orb/Arrow create patches at the selected impact point on hit/miss, with legal ground targeting causing no invented creature-hit damage. Spell-created acid/toxin patches last 2 turns; acid is nonstacking -2 AC while inside. Toxin uses caster-DC CON admission and one delayed 1d4 poison tick at next turn end, normal poison defenses, damage-only adaptation. These explicit adaptations replace unclear BG3 lifetime/Poisoned wording. |
| Q9 | Moonbeam, Plant Growth, Flaming Sphere, Glyph — RESOLVED | Human accepted enumerated area recommendations. Moonbeam exposure on placement/relocation, entry or turn start, at most once per target per turn; no duplicate APPEAR/ENTER hit. Sphere aura is 5ft (specific Ablaze description), enemy creatures at their turn end plus damageable objects through native environmental cadence; Ram is separate. Trail uses existing FireSurface lifetime, can harm allies, and dousing removes trail without despawning the elemental; native Wet/fire defenses apply. Plant Growth ground cost x4, strongest terrain factor, Freedom of Movement/flight bypass, partial fire removal. Glyph triggers once on hostile cast-time occupancy or entry, then payload affects all factions; native Antimagic suppresses triggering without consuming it. No protection redesign. |
| Q10 | Dissonant Whispers, Hideous Laughter, Calm Emotions — RESOLVED | Human requires separate spell conditions and explicit immunity handling when composing native transforms. Keep BG3 short fear even outside caster sight without changing global Frightened. Laughter retains persistent prone/agency denial, STR/DEX save disadvantage, end-turn/damage repeat saves with damage-save advantage and no Help recovery; preserve actual native prone/control immunity, and Charmed immunity alone is not a veto. Calm is humanoid-only/no save/purges charm-fear-rage/prevents renewal, with no faction or diplomacy change. |
| Q11 | Heroism — RESOLVED | Human allows existing fear to be removed immediately. Clear current eligible fear, prevent renewal while Heroism is active, and do not restore deleted fear afterward. Refresh source-owned temp HP to 5, preserve larger independent grants, and remove only this source remaining grant on expiry. |
| Q12 | Protection Evil/Good, Calm Emotions — RESOLVED | Human allows current eligible charm/fear to be removed rather than suspended for later resumption. Protection applies source-type-scoped attack disadvantage and charm/fear prevention; clear only existing effects from eligible creature types, leaving other-source effects intact. Calm clears eligible rage families and prevents renewal using native authored identities/tags. No possession system or global arbitrary condition-name matching. |
| Q13 | Ensnaring Strike — RESOLVED; Searing/Glyph Sleep/Dragon Breath — PARTLY OPEN | Human chose documented BG3 Ensnaring: initial STR save, start-turn piercing ticks, ally Help removal, no added self-escape action or automatic repeat saves; Ensnared blocks opportunity attacks. Add only the narrow native ally-assistance/removal support required. Remaining proposals: Searing start-turn CON save before failed-save burn, Wet/dousing/assistance ends burn; Glyph Sleep wakes on positive damage/assistance/shove/Wet; Dragon Breath willingness uses current ally policy without new anatomy restrictions. These other recovery choices were not explicitly answered. |
| Q14 | Magic Weapon, Flame Blade — OPEN; Heat Metal — REMOVED | Human skipped Heat Metal: no exact heated-item contact tracking or retained reapply action. Remaining recommendations: actual weapon selection, Magic Weapon follows exact UUID across transfer/unequip and strongest same-spell bonus stacks with inherent enchantment. Flame Blade uses normal BG3 spell-attack item and Extra Attack exception; main/offhand native costs, no ability damage; drop/transfer away from caster retires it; no stale equipment restoration. These remaining choices were not explicitly answered. |
| Q15 | NDClient presentation — RESOLVED / EXCLUDED | Human explicitly excludes NDClient presentation work. No client code, art/media task, visual acceptance or presentation handoff prerequisite. Native gameplay and necessary server/SDK facts/tests remain in scope. |
| Q16 | Revivify | BG3 companion eligibility differs from same faction; current source has no universal party-companion predicate for every authored creature. **Recommend explicit controlled-party eligibility supplied by current session/game owner**, support DEAD and DYING/STABLE by different native routes, optional legal destination within30ft, no diamonds/age. Decide broader allied/NPC eligibility and downed support; reject disintegrated remains. |
| Q17 | Spell riders, Magic Weapon and spell-attack items — COMPATIBILITY ONLY | Human questioned reworking Globe/Antimagic. Scope is existing native-rule integration/tests only, with truthful component/source attribution and narrow new-rider/temporary-bonus selection where needed. Preserve physical weapon damage when a magical component is suppressed. Do not redesign protection owners, redefine what Globe/Antimagic block, add new protection exceptions or change unrelated spells. Any genuine native policy gap is raised as a concrete finding rather than used to invent a framework. |

## 9. Review record and completion of this planning task

Required source studies and reviews of the complete saved draft were performed
by the anti-slop and anti-OOP/ECS reviewers. Both reviewed the material
corrections and passed the plan for human discussion on 15 October 2026, subject
to the explicit choices in §8. Neither verdict approves unimplemented behavior
or claims gameplay validation.

| Review | Material findings incorporated | Final verdict |
| --- | --- | --- |
| Anti-slop | Actual BG3 numeric profiles and bug exclusions; original 38-card inventory and waves; then-current Enthrall/summon/item gaps; meaningful tests; Spare the Dying undead/construct rejection; Hideous Laughter not gated by Charmed immunity; Wisp object ownership and correct damage accounting. | Planning completeness passes; no remaining material planning omissions identified, subject to human rule choices. |
| Anti-OOP/ECS | Exact source leases rather than same-name overwrite; caster-owned mark sustain/retarget; actor-versus-caster source separation; typed weapon/spell rider boundary and component attribution; temporary enchantment attack-path suppression; verified existing autonomous summon ownership/lifecycle; existing ownership and import DAG. | Structural implementability passes; all material review corrections addressed, subject to human rule choices. |

Both reviewers also passed the amendment for the accumulated human decisions in
§1.3: automatic toggled Divine Smite with shared feature/spell entitlement,
existing autonomous caster-owned summons, temporary-item conditions/handlers
tracking exact UUIDs, and exclusion of direct-control infrastructure and NDClient
presentation. That amendment retained the original 38-card scope. The latest human scope
removes cards 23/25, leaving 36; its review is recorded below. These are plan reviews, not evidence
that the spells have been implemented or gameplay-tested.

Both reviewers passed the latest 36-spell scope amendment: removed Enthrall/Heat
Metal and their exclusive mechanisms, confirmed SRD 5.1 Spare the Dying and BG3
Goodberry, native damage defaults, accepted surface/area rules, separate control
conditions with explicit immunity compatibility, immediate eligible fear/charm
removal, BG3 Ensnaring ally Help without self-escape, and protection integration
without Globe/Antimagic redesign. Anti-slop's stale surface/area decision phrases
were aligned with §8 before saving the two final copies. Remaining unanswered
spell choices stay proposals; neither review authorizes their implementation.

Final document checks verify 36 unique active numbered cards (excluding original IDs 23/25), location/setup/reference
fields for every card, all 36 covered once by the waves, and declared Q references.
The identical-copy check happens when saving the original-checkout copy. No
gameplay suite is needed to claim that this document was saved; none was run or
represented as passing in this planning task.

Planning completion requires all 36 active cards, each with location/reuse/setup/
observable cases/interactions, complete inventory/dependency coverage, real
doubts separated from recommendations, both reviews, and identical saved plan
copies in the worktree and original checkout. No spell, asset, runtime schema,
test or separate NDClient source is changed during this planning task.



## 10. Implementation and qualification record

**Completed: all 36 approved spells, with native, server and SDK qualification.**
The human authorized implementation of the updated plan, reuse of current systems,
thorough spell/interaction tests and no NDClient work. Enthrall and Heat Metal
remain excluded. Changes are uncommitted on `codex/spells-rank-one-two` in
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.

The earlier 130-row public catalog now has **166 unique public spell rows**.
Cold content bootstrap and composition succeed. Entangle and Black Tentacles
remain the two existing implementations outside that public catalog, giving
168 implemented spells when those two are included. This does not claim that
those legacy implementations gained catalog/learning registration in this batch.

### 10.1 Delivered scope and owners

| Wave | Implemented spells | Native implementation and focused proof |
| --- | --- | --- |
| A,13 | Spare the Dying; Vicious Mockery; Animal Friendship; Ray of Sickness; Starry Wisp; Sorcerous Burst; Dissonant Whispers; Faerie Fire; Heroism; Hideous Laughter; Protection from Evil and Good; Calm Emotions; Pass without Trace | Existing school roots, native control transforms, sourced immunities, turn handlers and memberships. `tests/engine/test_bg3_rank_one_two_spells.py`. |
| B,8 | Divine Smite; Divine Favor; Searing Smite; Ensnaring Strike; Hunter's Mark; Hex; Branding Smite; Magic Weapon | Existing school roots and Paladin handlers; `dnd/spells/hit_effects.py` shares attack-backed costs/riders/quarry ownership. `tests/engine/test_bg3_spell_hit_riders.py`. |
| C,8 | Dancing Lights; Create or Destroy Water; Chromatic Orb; Phantasmal Force; Moonbeam; Acid Arrow; Glyph of Warding; Plant Growth | Existing school roots, native spatial conditions and transitions; `dnd/spells/surfaces.py` contains the two authored acid/toxin patches. `tests/engine/test_bg3_spell_fields.py`. |
| D,5 | Goodberry; Flame Blade; Dragon's Breath; Revivify; Vampiric Touch | Existing school roots; `dnd/items/created_items.py` owns real items and exact native retirement. Current damage resolution supplies Vampiric healing; native revival and transfer admission supply Revivify. `tests/engine/test_bg3_spell_items_and_repeats.py`. |
| E,2 | Spiritual Weapon; Flaming Sphere | Roots in existing `dnd/spells/summoning.py`; creatures in `dnd/monsters/spell_summons.py`; current summon recipes, prepared birth/join, autonomous controllers and terminal cleanup. `tests/engine/test_bg3_spell_summons.py` plus extended native summon lifecycle coverage. |

Spell-created items live below spell-school roots because existing consumables
already import those roots. Spiritual Weapon's concrete strike is a data-only
specialization of the existing `NaturalAttack` composer, with an authored action
identity and recipe dependency. It uses the retained casting bonus and force dice;
Flaming Sphere uses its own native bonus-action Ram and moving fire aura/trail.

Remaining recommendations were resolved as implementation defaults under the
human's instruction to proceed sensibly, not recorded as additional human answers:
conditional bonus/slot payment on a weapon hit; weapon riders exclude body and
Flame Blade spell attacks; native defeated-quarry retargeting; standard Spiritual
Weapon with retained casting stats; Searing save before start-turn burn; Wet/Help
recovery; allied Dragon's Breath; exact-UUID Magic Weapon with strongest same-spell
bonus; Flame Blade drop/transfer retirement; controlled-companion Revivify with
separate dead/downed native routes. No unresolved decision blocks this scope.

Narrow shared changes carry the new behavior through existing owners:

- Typed attack kind, exact item identity and pre-publication hybrid declaration
  metadata distinguish weapon hits, spell hits and the optional spell payload.
  Existing Globe base-level and Antimagic policies remain authoritative.
- Damage finalization exposes spell hits to existing handlers. Health retains
  exact component identity; Entity delivers the current accepted resolution to
  Vampiric Touch without a damage-history service.
- Native conditional cost discovery exposes hit-only bonus/slot payment. Slow
  checks the required action channels before payment; a miss preserves hit costs.
- Native reveal, spell-specific control immunities, source-owned temporary HP,
  retained casting data, exact lifetime/cleanup and spatial contribution rules
  support the approved effects. Suppression does not freeze their deadlines.
- Explicit companion membership survives death and temporary controller changes.
  Revivify uses native revival and optional transfer admission before payment;
  public discovery includes visible eligible remains without revealing hidden ones.
- Mixed creature/ground variants and the existing compound-position selection
  carry Orb/Arrow and Revivify through current player choices and previews.

### 10.2 Behavioral acceptance

The eight new spell/progression/server test files pass **155 tests** together
in33.92s. They cover normal/critical/missed attacks, saves, paid resources,
independent sources, bounded Burst explosions, actual Hex multibeam A/B/A hits,
Magic Weapon/Shillelagh/transfer/strongest-source composition, contact/crossed
Antimagic, Flame Blade spell-attack eligibility, native interruption, control
immunity/recovery, area admission/cadence/movement, elemental surface transitions,
exact item custody/rest expiry, retained ally casting DC, healing attribution,
revival/relocation vetoes and native summon departure/autonomous damage.

Two integrated sequences use real turns without resetting their costs:

- `tests/engine/test_bg3_spell_integrated_encounter.py` combines a real berry batch,
  autonomous weapon, Hex, Moonbeam and its movement, Hideous Laughter, berry
  consumption, an actual caster Fire Bolt+Hex hit, concentration cleanup,
  dismissal and long-rest retirement. Native autonomous progression reaches the
  next human input boundary.
- `tests/player/test_bg3_spell_transport.py` also drives that combination through
  real worker Choices/Preview/Command/Advance and EndTurn operations, including
  the other human seat's legal turn passes. It verifies the autonomous force
  strike, caster damage rider, effect/item cleanup and return to authorized human
  input. Separate cases qualify spell shapes and both in-place and compound
  relocation of dead companions. Previews leave authoritative events untouched.

Sorcerer tests use actual source-owned class choices for new cantrips and level1/2
spells. The five Divine Smite toggles are shared by learned/feature origins in
both registration orders, with one highest-enabled-affordable payment per hit.
The existing ordinary-item inventory contract includes Goodberry; no client-side
spell exception or presentation change was added.

### 10.3 Final validation and existing failures

Runtime: source worktree on Linux filesystem, Python3.13 in the prepared uv
environment `/home/tommaso/.cache/dnd-engine/venv`; commands use `uv run --no-sync`.
The original checkout is on `/mnt/c`; baseline reproductions use that checkout
with the same environment. Timings are validation wall times, not engine targets.

| Check | Result |
| --- | --- |
| All eight new spell/server/progression files | **155 passed**,33.92s. |
| Full engine lane after explicit existing-failure exclusions | **2,971 passed**,120 deselected,311.06s. `test_solid_walls.py` excluded at collection because it imports the archived `game` package. |
| Spell plus affected summon/fire-contact/equipment batch | **250 passed**,57.02s. |
| Player/progression/architecture broad lane | **458 passed,18 failed**,116.60s; failures classified below. Archived `test_application_review.py` and `test_presentation_schema_export.py` excluded at collection. |
| Active catalog/import/item-ownership/provenance architecture subset | **23 passed**,5 known baseline cases deselected,8.18s. Final targeted delta including the explicit provenance gate, fields, Sorcerer and all worker cases: **46 passed**,21.00s. |
| Python SDK plus protocol-schema tests | **91 passed**; also included in the245-pass combined focused run before the final server sequence was added. |
| TypeScript SDK generated contracts and tests | **63 passed**,zero failures. |
| Pyright production source | **92 diagnostics**,exactly the same file/message multiset as the original checkout; **zero new diagnostics**. |
| Native AI tests that collect against current server layout | **33 passed,2 failed**; both failures reproduce in the original checkout. Five additional files have the same retired-module collection errors in both checkouts. |
| Cold catalog, exclusions and diff hygiene |166 unique public rows; removed spells absent; `git diff --check` passes. |

Existing failures were not repaired as unrelated spell work:

- The13 engine failures reproduced on the original checkout concern door contact,
  old combat-log fixtures, old connected-area/doorway expectations and old replay
  capture calls passing UUID instead of the current audience value. Exclusions
  also cover the related parameterized real-door cases; the full exclusion list
  is below. New failures exposed by the first broader run—item merge facts,
  Lightning Bolt's existing ignition, new summon-family coverage and Glyph sleep—
  were fixed and their affected suites pass.
- In the broad architecture run,6 failures reproduce in original import/layout
  and static item-census tests;9 source-hygiene failures also reproduce there.
  Two frozen CR-0 artifact checks fail on manifest bytes/artifact hashes in this
  worktree. Those historical evidence files were not edited for this spell batch.
  The remaining failure was the new surfaces' implicit keyword provenance; it was
  corrected to explicit native EffectOrigin arguments and the gate now passes.
- The two AI failures are the existing event-knowledge replay calls with UUID
  audiences. The five collection failures import removed
  `server.external_ai_protocol`/`server.registered_ai_controller` modules.
  Current native summon AI is independently exercised by the passing spell tests.

The engine acceptance command uses `tests/engine`, ignores
`tests/engine/test_solid_walls.py`, and deselects these existing names with `-k`:
`real_door`,
`test_door_close_still_rejects_an_occupied_opening_and_retains_swing`,
`test_eb_04_005`, `test_eb_04_007`, `test_eb_04_008`,
`test_fireball_spreads_around_open_doorway_within_original_radius`,
`test_connected_reference_l_wall_and_corridor`,
`test_hand_operated_door_requires_nearby_contact`,
`test_cold_furniture_publishes_birth_then_owned_dynamics_and_replays_after_reset`.
No full-repository green claim is made.

Reproduce the new-spell qualification from the implementation worktree:

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest -q --assert=plain --tb=short tests/engine/test_bg3*.py tests/player/test_bg3_spell_transport.py tests/progression/test_bg3_sorcerer_spell_learning.py
```

### 10.4 Public contracts, review and limits

Production schema, OpenAPI, field ledger and both generated SDK contracts are
synchronized. Protocol remains schema9;321 shared definitions and1,707 fields.
Conditional hit costs, damage component identity and spell-construct manifestation
are passive values carried through existing public contracts. No NDClient code,
assets, dependency lock changes or PRs were produced.

The human subsequently requested a commit of this completed batch before the
level-4–9 work. Pre-commit qualification reran all eight batch test files plus
catalog composition: **157 passed in 36.34s**; `git diff --check` passed.
The implementation and this handoff are committed together on the worktree branch.

Anti-slop and anti-OOP/ECS reviews are complete. Their material findings were
corrected and verified: retained casting data, identity keys, suppressed deadlines,
initial area/summon publication, exact temporary-item retirement, native force
strike composition, and weapon-only versus Flame Blade eligibility. The final plan-adherence review also passes: all36 spells and the finite acceptance
list are complete, with no remaining scope blocker.

Known forecast bounds remain within the current native outcome-profile model:
Sorcerous Burst forecasts base dice rather than the branching explosion expectation;
Acid Arrow forecasts immediate hit damage rather than its half-on-miss and delayed
one-shot tick. Actual execution implements and tests those mechanics. Summons use
existing autonomous allied controllers; no manual summon-control interface was
added. BG3 adaptations and their deliberate rule choices remain documented in the
per-spell cards and§1.3.
