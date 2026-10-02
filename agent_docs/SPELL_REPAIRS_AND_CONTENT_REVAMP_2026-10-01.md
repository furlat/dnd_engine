# Spell repairs first, creature and scenario content second

October 1, 2026. Task separation requested by the user after the attack refactor
and full-suite review. This is a scope and sequencing record, not a claim that
the new spells or fixed-character roster are implemented. The asset-study chat
was contacted for consultation only; no production work was dispatched to it.

## Existing scenarios: review findings

`dnd/scenarios/authored_catalog.json` contains 40 encounter recipes, 60 reusable
rosters and nine reusable deployments. Of the encounters, 38 are labelled
"AI Validation"; the other two are Blood and Bone Workshop and Storehouse Raid.
Twenty-one encounters use the same bright open-floor battlefield. The old
rosters still contain 27 member references to retired `creature.player.*`
definitions. Counts describe checked-in content, not successful runtime builds.

The catalog already separates battlefields, rosters, deployments and encounter
composition. Preserve useful mechanics checks for darkness, doors, reaction
timing, resources and hazards, while redesigning player-facing encounters.
Restoring every old lab, old identifier or exact catalog count is not the goal.
Storehouse Raid is a useful candidate to reassess because it already combines
ordinary lighting, doors, a lever, loot and furniture; it is not an approved
template for every new encounter. Saved-event rendering cases remain distinct
from playable encounter design.

## Task 1 — spell correctness and SRD walls

1. Resolve the reproduced Grease entry failure against its intended entry/turn
   trigger rules, including forced movement and once-per-turn behavior. Preserve
   working initial application, turn-end effects, movement cost and cleanup.
2. Make Darkvision/True Seeing touch admission coherent with the user's
   close-range targeting direction. Use shared targeting/discovery and physical
   contact checks, including windows; avoid individual spell-name exceptions.
   Self/adjacent contact must not accidentally reveal hidden creatures or bypass
   a physical wall. BG3 documents a ten-foot Blinded range cap and a five-foot
   Darkvision touch range; exact broader blind-targeting scope remains to be
   settled before changing all attacks or ranged spells.
3. Pick up the queued Wall of Fire VFX handoff when available and implement its
   native spell rules and retained-event presentation. No handoff readiness or
   export coverage has been certified in this consultation.
4. Cover the other SRD 5.1 wall spells in the same workstream. A current scan of
   `dnd/` found no implementations or catalog entries for Wall of Fire, Force,
   Ice, Stone, Thorns, Wind Wall or Prismatic Wall. Source rules are the
   [2014 spell descriptions](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/spells).

Reuse existing spatial conditions, boundary access channels, object damage,
concentration, action economy and event lifecycle. Share only capabilities that
the spells actually share. A damaging permeable wall, a solid destructible wall,
an invisible force barrier and Prismatic Wall's layers cannot be represented
as cosmetic variants of one blocking/damage flag. Review each spell's placement,
shape, entry and turn triggers, sight/light, attacks, destruction and expiry.
Where the current world cannot express an SRD placement or interaction, record
the limitation and discuss the rule rather than inventing a silent substitute.
Multi-Z remains deferred; this task does not authorize that migration.

Complete the Grease and touch-targeting repairs before the new wall spells.
Wall of Fire is the first new wall delivery, followed by independently verifiable
wall spells. Spell gameplay coverage must not depend on unfinished icon/UI authoring.
Validate native execution, discovery, event replay and spatially matching VFX;
retain the accepted rendering behavior and run the active engine/game checks.
Track retired-server failures separately from the supported game.

## Task 2 — fixed-character integration, NPCs and playable scenarios

Starts after Task 1. Consulted chat: **Art-led NPC roster and rig authoring**,
`01a0f3b4-277a-7fa0-9356-d1c9de5527b8`.

Authoritative preparation currently available:

- [Roster synthesis](ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md), with its later
  image-only gear corrections and Devil/HD Enemy replacement drafts.
- [Unified presentation handoff](audits/FIXED_CHARACTER_RENDERER_INTEGRATION_2026-10-01.md).
- [Inspected motion study](audits/FIXED_CHARACTER_ANIMATION_MAPPINGS_2026-10-01.md)
  and its adjacent JSON: 150 retained characters, 600 basic mappings, 422 combat
  mappings and 12 extra selections. These are preparation data; runtime approval
  flags remain false, and exact FPS/contact/release/pivots need calibration.

The broader archive inventory contains 259 variants. The 150-character mapping
set is narrower: animals and excluded modern designs must not silently become
part of this integration. Keep source inventory, curated proposals and tested
production content distinct. Equipment and balance proposals need reconciliation
with the latest inspected artwork before registration.

1. Reconcile the study's selected native/SRD foundations, actual baked equipment,
   ability proposals and unsupported visual states. Keep declared custom changes
   separate from canonical SRD creatures. Do not use source filenames as rules.
2. Extend the existing typed presentation records only where required so both
   modular and fixed families use the same semantic action selection, timeline
   and compositor. Author per-family clips, direction rows, timing, registration,
   body/shadow/FX layers and permitted appearance states from retained facts.
3. Integrate and check representative melee, ranged, natural-attack and caster
   characters before applying the same contract across the retained roster.
   Calibration must cover equipment changes/disarm, damage/death and conditions,
   not just idle and one attack. Missing states require an explicit disposition.
4. Author corresponding native NPC/loadout variants and useful faction teams;
   reuse rule systems and compositions rather than adding a class per picture.
   Mix modular and fixed sheets in the same encounter. Higher-detail fixed art
   can serve elites, bosses and important NPCs; modular bodies retain flexible
   gear, humanoid and Body2 skeleton authoring.
5. Rebuild playable encounters around meaningful choices and current environment
   content: faction roles, routes, light, cover, breakable objects and resources.
   Preserve valuable engine regression assertions from replaced labs. Review
   actual event-driven gameplay with real floor art and clear tile relationships.

Original artwork stays private and preserved under `ASSETS.md`; production
packing/import is a separate step from reading the study. Pygame UI/icon design,
retired server restoration and character save/resume are not added to these two
tasks implicitly.

## Consultation received

The study chat confirmed the current 150-character selection: 29 Orc/Goblin,
34 Devil, nine Undead, 12 Enemy, 48 Zombie, nine Barbarian and nine Character
variants. Its final response confirmed that no new rig is runtime-approved.
Keep the [individual authoring cards](audits/PACK_ROSTER_INDIVIDUAL_AUTHORING_DIRECTIONS_2026-10-01.md)
alongside the controlling motion, gear and roster evidence above.

Additional concrete holds: mounted Goblins bake rider/mount together; crawlers
need a persistent pose rather than an invented Prone condition; some movement
and death clips contain conspicuous baked effects. Source shadowless sheets can
omit major FX, not just shadows. All-facing source timing and anchors still
need calibration. Fifteen cards preserve baseline faction coverage; specials,
signatures, equipment grades and revised CR remain proposals.

The chat suggested a level-five Crusader/Footsoldier encounter and a level-seven
Caster/Guard encounter as candidates after calibration. The Guard's spear
contact remains unresolved. These suggestions do not commit us to those pilots,
their balance or a four-adventurer party size. Its advice to preserve useful
mechanics fixtures is compatible with replacing the poor player-facing scenes.

## Review

Independent anti-slop and anti-OOP/ECS reviews approved this scope separation.
The anti-slop reviewer independently confirmed scenario counts and missing-wall
search results and requested explicit repair-first sequencing; that correction
is applied above. The ECS reviewer confirmed reuse of shared spatial, action,
event and rig owners, with no blocking findings. These approvals cover the task
separation, not yet-written spell rules, schemas or production rig calibration.
Concrete implementation changes still require both reviews.
