# Packaged creatures, native content and animation mapping

**1 October deeper asset pass:** the [reviewed animation mappings](audits/FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.md)
now supply explicit selections and source evidence for all 150 retained
nonanimal characters. The earlier geometry/filename inventory alone did not
establish action semantics. Visible timing windows are documented; exact event
markers, FPS, registration and final layer policy remain production calibration.

**1 October implementation ownership correction:** the [unified presentation
handoff](audits/FIXED_CHARACTER_RENDERER_INTEGRATION_2026-10-01.md) is the current
architecture/authoring direction. The main production thread owns runtime
integration. The art-led chat owns evidence and preparation; Luna coordination
below is historical and has been revoked. Both modular and fixed families need
one data-driven action/layout/timing projection. Fixed-character actions and
gear are deliberately constrained during native content authoring to fit the
inspected art, with explicit departures from SRD source profiles.

**Current selection correction:** match the full SRD 5.1 creature catalogue first;
SRD 5.2 is secondary and must use 5.1 rules. Adapt each selected profile to
actual visible equipment, with explicit changed attacks/AC and retained source
traits. The [reconciled synthesis](ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md) and its
three SRD-first tables supersede earlier custom-first mechanical proposals.
Local factory availability is a readiness fact, not the source-search boundary.

Status: source-study handoff completed, 30 September 2026. The expanded
[art-led roster synthesis](ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md) owns the
259-variant proposal set, focused completion evidence and independent reviews.
Use that record for final coverage and design decisions; this document retains
the initial architectural study and current-code navigation. No
production imports, NPC changes, renderer changes or new authoring framework are
authorized by this document. The human requested a general source-pack study
with Luna agents, then clarified the deliverable: **design a flavour-based NPC
for every fixed artwork variant, fitting it one to one**, with possible elite
versions/recolouring. The earlier storehouse experiment is paused.

**Ownership handoff:** at the user's request this work is now led by the full
project chat **Art-led NPC roster and rig authoring**, thread
`01a0f3b4-277a-7fa0-9356-d1c9de5527b8`, using GPT-6.1 Sol at extra-high reasoning.
Original Luna report writers finish their current deliverables; their results
are relayed to that chat, which owns subsequent Luna coordination and the final
roster/design. The original chat returns to clouds/windows. No production work
is implied by this handoff.

There are two intended content routes:

- **Art-led roster:** use the purchased fixed creatures' actual bodies, gear and
  actions to design a large corresponding NPC roster. Existing Goblin/Skeleton
  mismatches motivated the study but are not its scope or the limit on new NPCs.
- **Freely authored roster:** use the modular humanoid and `NakedBody2` skeleton
  systems for other custom characters/loadouts not covered by a fixed picture.

Each source variant needs a traceable proposal: flavour/name, role, fitting
equipment or natural attacks, native/SRD composition candidate, suggested
abilities and an optional elite treatment. Clearly distinguish reuse from new
rule proposals. Multiple visual variants can share mechanical composition;
one-to-one content design does not require a new implementation per sprite.

## Required boundary

An NPC remains a composition of native game data and existing systems: creature
identity, stats, actual possessions, natural attacks, actions, reactions,
conditions and handlers. Its rules do not depend on installed PNGs. SRD-derived
content and project-authored departures must remain distinguishable.

Presentation describes a body/outfit and the animations it actually depicts.
The renderer binds admitted, retained game facts to that presentation data.
Fixed pictures have less equipment freedom than modular bodies; that limits
which NPC/loadout combinations we can currently depict, not the engine's rules.
Do not silently remove a shortbow from canonical Goblin mechanics to fit an axe
picture, or pretend an axe swing is a bow shot.

**Human clarification: skeletons have two valid presentation routes.** Modular
`NakedBody2` skeletons deliberately support rich equipment/loadouts. Premade
Undead-pack skeletons have fixed pictures and a different available animation
set. Rich skeleton loadouts are not inherently a defect. Check each actual
content-to-rig binding; keep both routes and do not force modular skeletons to
obey limitations of the fixed pack. The study must preserve this distinction
when recommending new content variants.

The human also confirmed that shadows are required. Prefer source separated
body/shadow/effect layers. Paired shadowless/combined sheets and the previous
NeuroClient color/alpha shadow extraction are valid routes to study where an
explicit shadow sheet is absent. Preserve source pixels privately; manual
inspection and extraction probes belong to the Luna studies.

## Existing source ownership

The supplied directory is `/mnt/c/Users/tommaso/Documents/assets/smallscale/`.
Orc/Goblin and Demon archives are additionally in
`/mnt/c/Users/tommaso/Downloads/`. Duplicate download names are not distinct packs.
An archive being present does not mean its characters are installed or playable.

| Source pack present | Currently installed fixed selections | Detailed study owner |
| --- | --- | --- |
| 2D Orcs and Goblins - TopDown - V1.0 | Goblin01, Orc01 | Luna: orcs/demons |
| 2D Demons - TopDown assetpack v1.1 | DemonBeast01, 02, 03 | Luna: orcs/demons |
| 2D HD Undead pack 1 | SkeletonArcher05 | Luna: undead/enemies |
| 2D HD Enemy pack 1 | None | Luna: undead/enemies |
| 2D HD Zombie pack 1 V1.1 | None | Luna: undead/enemies |
| 2D Zombie pack 2 - Top down v1.1 | None | Luna: undead/enemies |
| 2D Animals mega Pack 1 V2 | GreyWolf | Luna: animals/humanoids |
| 2D Dinosaurs Pack 1 (.rar) | None | Luna: animals/humanoids |
| 2D HD Barbarian pack 1 | None | Luna: animals/humanoids |
| 2D HD Character pack 1 V1.2 | None | Luna: animals/humanoids |

The modular NeuroClient root is a separate installed system. Downloads also
contains `Stand-alone Character creator - 2D Fantasy V1.3.zip` and
`x256 Spritesheets.zip`; the animal/humanoid study will identify their relationship
without counting modular components as fixed creatures. Environment tilesets in
Downloads are outside this creature study. These are local holdings, not a claim
to have inventoried the vendor's complete catalogue.

Seven fixed rig JSONs currently bind 88 existing local media files; the modular
root makes eight registered rigs. These counts establish registration and file
presence, not behavioral or artistic coverage.

## What the current code actually does

### Native authorship already exists

- `dnd/monsters/srd_roster.py`: SRD creature declarations and composition through
  existing entity blocks, equipment and authored behavior.
- `dnd/monsters/bestiary.py` and `bestiary_content.py`: native Goblin, Skeleton
  and project combat-role variants. Goblin's default possessions include
  scimitar, shortbow, shield and leather armor.
- `dnd/monsters/demon_variants.py`: project variants reuse Dretch composition
  and install distinct native body-response behavior. This is an existing
  example of custom mechanics over a shared creature foundation.
- `dnd/monsters/skeleton_abilities.py`: the native Mark Target action and its
  conditions. A spell-like picture alone does not establish that ability.
- `dnd/content/items/authored_item_definitions.py` and
  `authored_item_builders.py`: passive item/weapon/wearable definitions plus
  direct materialization. `item_loadouts.py` already supplies ordered item IDs,
  quantities and actual equipment slots.
- `dnd/content/characters/builds.py`: direct character composition from species,
  background, class levels, choices, items and appearance. Do not turn every
  premade human picture into a new character class or construction path.
- `dnd/scenarios/encounter_assembler.py`: existing creature and character roster
  composition. This study does not need another encounter/NPC factory layer.

Reuse these owners where they fit. Their presence is not certification that
every older descriptor/registry convention should be expanded. There is still
legacy presentation vocabulary in native `AppearanceConfig`, content descriptors
and item visual fields. Extending those with pack-specific filenames would make
the separation worse. A global migration of those older fields is separate work.
Likewise, `creature_materialization.py` still passes through older recipe/registry
machinery. This is not a proposal to add a second registry, more content-set
digests or source audits. Existing SRD declarations also document partial fidelity
(for example Dretch's HP policy and missing traits); a source label must not be
mistaken for proof of complete SRD rules coverage.

### Disclosed identities already cross the boundary

`EntityCreatedEvent` retains `creature_content_ref`, `character_body_id`, appearance
and real game state. `game/player_projection.py` builds the permitted
`PlayerActor`/visible loadout; foreign private inventory is not part of that
public loadout. `AttackFact` retains behavior, source item, weapon slot, damage
types and outcome. Existing subjective rules remain authoritative.

`game/combat.py:actor_contact` resolves a creature's stable content identity
through the presentation-owned `AnimationData.creature_rigs` mapping.
`game/animation_data.py:resolve_actor_layers` chooses modular equipment layers
for the root rig, or fixed body/shadow categories for a packaged rig. Native
equipment changes currently do not replace a fixed sprite's baked weapon.

No new backend event containing a rig name or contact frame is needed for an
ordinary axe attack. Preserve complete causal lineages and record-once replay;
do not read live native objects to decide how a historical action looks.

### Existing mappings are useful but not sufficient for every pack

`BodyRig`/`BodyClip` in `game/animation_types.py` already own sheets, dimensions,
facing rows, body/ground/rest anchors, optional pose sockets, frame counts and
FPS. `source_clip` maps a local semantic clip to the vendor name.

`AttackVariant` already owns match criteria, a body clip, playback speed, frame
anchors and projectile/layer behavior. `select_attack_profile` uses the actual
attack's item/damage/delivery/outcome; it currently has no per-rig selector.
Thus mapping a vendor name to `Attack1` alone does not prove its contact matches
the shared recipe's contact frame. All actions that select a body clip need the
same consideration, not a one-off Goblin fix in `attack.py`.
`BodyFrame` currently permits 0–14 while `BodyClip.frames` is variable. Source
block sheets already demonstrate six- and seven-frame clips. Selected markers
must fit their actual clip; this finding does not justify retiming every existing
recipe or inventing unused long-animation support.

Current concrete examples:

- Goblin01 maps melee, movement, rolling, damage and death; the shared ranged
  recipe requests `Attack3`. The inspected vendor Attack 3/4 are airborne melee
  swings. The current missing-ranged path preserves the root timing and displays
  Idle with a reported media gap. It is a diagnostic fallback, not completed
  ranged support.
- The source study found a real bow user in Goblin03 and caster-like material
  in Goblin02. Their vendor numbering differs from the root vocabulary. These
  are candidates for separate authored NPC/rig pairings, not replacements for
  every Goblin or permission to infer spells from colored effects.
- SkeletonArcher05 maps `QuickShot` to `Attack3` and uses six body sheets; native
  Skeleton Archer also has daggers and Mark Target. Its body-only rig needs the
  source shadow study as well as action coverage. This is a specific current
  binding concern, not an argument against modular Body2 skeleton loadouts.
- DemonBeast bindings reuse one clip for multiple semantic attacks. Identical
  clip availability does not establish identical impact timing or pose semantics.

## Proposed authoring approach to review

1. **Catalogue each fixed visual family once.** Record its baked visible gear,
   body identity, layers and all clips. A family contains many directional
   animation sheets; do not duplicate the NPC definition for each sheet. Palette
   variants are appearance choices unless their game mechanics genuinely differ.
2. **Design the full matching roster, then author native content deliberately.** Choose an existing SRD
   root or a named project variant; supply real equipment IDs and reusable native
   abilities. A visible axe does not determine its damage die, CR or magical
   effects. Natural claws/bites do not become lootable weapons merely to satisfy
   a renderer selector. Preserve source/provenance in the existing content path.
3. **Keep the binding in presentation data.** Bind stable game identities to
   suitable rig/appearance choices and map action semantics to inspected clips.
   Reuse the current typed body/recipe records. Investigate the smallest shared
   per-rig action override needed for clip, contact/release timing and sockets;
   do not add one executor per pack. Numerical tuning is authored presentation.
4. **Use animation extras selectively.** Walk/backwards/strafe, block, crouch,
   taunt, alternate death, bite, cast and similar clips become a capability
   inventory. Hook them to existing events when their meaning fits. Any new
   charge, howl or special attack gets an explicit game design and native owner;
   do not generate mechanics from filenames.
5. **Check a small representative set before expanding.** Include one fixed
   melee actor, genuine archer, natural-attack creature and custom ability. Test
   their actual loadouts/action discovery, complete event playback, contact
   timing and shadows; check four cameras and relevant observer views. Keep
   modular actors as regressions. Content coverage checks belong in authoring
   tools/tests, not a startup archive scan or gameplay hash audit.

Questions to resolve from the study, not reasons to invent infrastructure:

- Which inspected variants actually provide unarmed/alternate-weapon poses?
  Disarm, dropped gear and loot stay native game facts; unsupported visual states
  must be reported, not concealed by leaving an apparently equipped baked weapon.
- A cosmetic choice among fixed variants may need a stable observed appearance
  identity when creature identity/visible gear do not distinguish it. Check the
  existing appearance contract first. Do not mint distinct mechanical creatures
  just to choose a palette, or select secretly from private inventory.
- What timing/anchor overrides do the inspected actions actually need? Retain
  approved modular recipes and causal schedules; no automatic global retiming.
- What shadow information can be recovered exactly from each source layout?
  Keep source paired images, alpha, facing and support registration together.

## Evidence and review record

The source studies and roster proposals are:

- [Orcs, Goblins and Demons](audits/PACK_STUDY_ORCS_DEMONS_2026-09-30.md):
  65 source variants, all reviewed in Idle contact sheets; selected actions
  inspected. Explicit per-variant flavour proposals remain design, not imports.
- [Undead and enemies](audits/PACK_STUDY_UNDEAD_ENEMIES_2026-09-30.md):
  9 Undead, 13 Enemy, 36 HD Zombie and 42 top-down Zombie source variants.
- [Animals and humanoids](audits/PACK_STUDY_ANIMALS_HUMANOIDS_2026-09-30.md):
  55 animals, 9 Barbarians and 9 Characters with proposed roster rows. Dinosaur
  RAR inspection remains pending. The animal contact atlas needs correction;
  source enumeration is complete but visual review of all 55 is not claimed.

Three Luna studies cover the ten fixed-pack archives. Each report must separate
directory/metadata inventory, visually inspected facts and unresolved mappings.
Independent anti-slop and anti-OOP/ECS review of the synthesis follows the factual
reports. Both reviews must assess reuse of existing native/content/animation
owners and preservation of subjective event semantics. No claim of approval
until the reviews are recorded here.
