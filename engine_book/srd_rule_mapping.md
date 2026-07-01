# SRD Rule Mapping

This is the internal source-rule map for the NeuroDragon Dev Manual. It ties
each public chapter to the local SRD markdown under `interactive_ruleset/` and
records the ruleset policy used by the engine. Public pages may teach these
relationships directly, but they should not link readers to this planning file
as the explanation.

## Mapping Policy

NeuroDragon has one videogame ruleset. The local SRD markdown is source
reference material for Dungeons & Dragons vocabulary, procedures, spell text,
monster traits, equipment, conditions, and class features. The runtime chooses
one implementation for each rule concept; parallel SRD/BG3 profiles are not a
runtime feature.

Relationship labels:

- `source-vocabulary`: The chapter teaches engine infrastructure that has no
  direct SRD object, but it exists to represent SRD concepts.
- `srd-aligned`: The engine behavior follows the local SRD source at the level
  documented by the manual.
- `engine-adaptation`: The engine deliberately adapts a tabletop procedure into
  a videogame rule.
- `product-extension`: The chapter is about the videogame built on top of the
  engine; it uses SRD concepts but is not itself an SRD rule.

Current policy points to keep visible while writing:

- Forced movement is modeled as `FORCED_MOVEMENT`. It can still move through
  terrain and spatial systems, but voluntary-movement reactions such as
  opportunity attacks must remain voluntary-movement-only.
- Standard Shove is the videogame/BG3-style bonus-action implementation:
  passive target resistance, strength-scaled forced movement, and no duplicate
  SRD special-attack runtime surface.
- Equipment uses one melee loadout and one ranged loadout. Two-handed melee
  weapons displace melee off-hand gear by `WeaponProperty.TWO_HANDED`; ranged
  loadout remains separate.
- Advantage/disadvantage is currently accumulated by modifier score, not the
  pure SRD "any advantage plus any disadvantage cancels" rule.
- Great Weapon Fighting follows the local class markdown behavior that rerolls
  1s and 2s, not the newer feat-file "treat as 3" wording.
- Encounter ending is a videogame policy based on faction survival because the
  engine owns the GM role during automated tests and playable modes.

## Chapter To Source Map

| Chapter | Public chapter | Rule touchpoints | Relationship | Local SRD sources | Engine/game policy |
| --- | --- | --- | --- | --- | --- |
| 00 | `00-neurodragon-dev-manual.mdx` | D&D vocabulary; Videogame ruleset policy; Software dungeon master loop | product-extension | `interactive_ruleset/README.md`; `interactive_ruleset/Gameplay/Combat.md` | Introduces the local SRD corpus as reference material and the engine as the software DM for one videogame ruleset. |
| 01 | `01-runtime-identity-and-registries.mdx` | Runtime identity; Object ownership; Registry lookup | source-vocabulary | `interactive_ruleset/Gamemastering/Objects.md`; `interactive_ruleset/Gameplay/Combat.md` | UUID registries are engine infrastructure used to keep SRD objects, creatures, effects, and combat procedures addressable. |
| 02 | `02-entity-anatomy.mdx` | Ability scores; Hit points; Equipment and senses | srd-aligned | `interactive_ruleset/Gameplay/Abilities.md`; `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Equipment/Armor.md`; `interactive_ruleset/Equipment/Weapons.md` | Entity composition packages SRD-style creature state into blocks owned by one runtime actor. |
| 03 | `03-values-and-modifiers.mdx` | Ability modifiers; Advantage and disadvantage; Resistance and immunity | engine-adaptation | `interactive_ruleset/Gameplay/Abilities.md`; `interactive_ruleset/Gameplay/Combat.md` | Ability modifiers and damage responses are SRD-shaped; advantage uses the engine's additive modifier ledger. |
| 04 | `04-dice-rolls.mdx` | D20 rolls; Damage dice; Critical hits | srd-aligned | `interactive_ruleset/Gameplay/Abilities.md`; `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Classes/Fighter.md`; `interactive_ruleset/feats_srd5_2.md` | Roll records model d20 checks, saves, attacks, damage, crits, and the chosen Great Weapon Fighting text. |
| 05 | `05-event-lifecycle.mdx` | Action resolution timing; Event completion; Combat narration | source-vocabulary | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Spells/# Spellcasting.md` | Events are not SRD rules themselves; they are the auditable runtime timeline for SRD combat and spell procedures. |
| 06 | `06-reactions-to-events.mdx` | Reactions; Opportunity attacks; Triggered effects | srd-aligned | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Spells/Shield.md` | Reaction handlers represent SRD reaction timing, including opportunity attacks and reaction spells. |
| 07 | `07-conditions-and-cleanup.mdx` | Conditions; Durations; Concentration-style cleanup | srd-aligned | `interactive_ruleset/Gamemastering/Conditions.md`; `interactive_ruleset/Spells/# Spellcasting.md`; `interactive_ruleset/Gameplay/Combat.md` | Condition lifecycle and cleanup make SRD condition and concentration effects removable and auditable. |
| 08 | `08-world-model-and-movement.mdx` | Movement; Difficult terrain; Forced movement | engine-adaptation | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gameplay/Adventuring.md` | Grid movement follows SRD movement concepts while separating voluntary and forced movement for videogame reaction policy. |
| 09 | `09-action-discovery-and-costs.mdx` | Actions; Bonus actions; Object interaction | srd-aligned | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gamemastering/Objects.md` | Action discovery turns SRD action economy and object interaction into legal selectable rows. |
| 10 | `10-combat-resolution.mdx` | Attacks and damage; Healing; Shove and forced movement | engine-adaptation | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Spells/Thunderwave.md`; `interactive_ruleset/Spells/Cure Wounds.md` | Attacks, damage, healing, death, and forced movement are SRD-shaped; Shove is the chosen videogame implementation. |
| 11 | `11-equipment-inventory-and-items.mdx` | Weapons and armor; Inventory; Usable items | engine-adaptation | `interactive_ruleset/Equipment/Weapons.md`; `interactive_ruleset/Equipment/Armor.md`; `interactive_ruleset/Equipment/Gear.md`; `interactive_ruleset/Gamemastering/Objects.md` | Equipment follows SRD weapon/armor concepts with videogame loadout displacement and separate melee/ranged sets. |
| 12 | `12-perception-light-stealth-and-invisibility.mdx` | Vision and light; Stealth; Invisibility | srd-aligned | `interactive_ruleset/Gameplay/Abilities.md`; `interactive_ruleset/Gameplay/Adventuring.md`; `interactive_ruleset/Gamemastering/Conditions.md`; `interactive_ruleset/Spells/Invisibility.md` | Observer-local senses represent SRD vision, passive Perception, hiding, invisibility, and special senses. |
| 13 | `13-spellcasting-core.mdx` | Spell slots; Spell attacks; Concentration | srd-aligned | `interactive_ruleset/Spells/# Spellcasting.md`; `interactive_ruleset/Gameplay/Combat.md` | Spell actions model slots, attacks, saves, concentration, and cleanup as engine-owned action/effect flows. |
| 14 | `14-spell-families-and-implemented-spells.mdx` | Spell schools; Saving throw spells; Area effects | srd-aligned | `interactive_ruleset/Spells/# Spellcasting.md`; `interactive_ruleset/Spells/## Spell Lists.md`; `interactive_ruleset/Spells/Fire Bolt.md`; `interactive_ruleset/Spells/Fireball.md`; `interactive_ruleset/Spells/Web.md`; `interactive_ruleset/Spells/Sleep.md`; `interactive_ruleset/Spells/Mirror Image.md` | Implemented spell families use local spell files as source text, with per-spell deviations documented where behavior is videogame-shaped. |
| 15 | `15-class-features-factories-and-feats.mdx` | Class features; Feats; Rest resources | engine-adaptation | `interactive_ruleset/Classes/Fighter.md`; `interactive_ruleset/Classes/Barbarian.md`; `interactive_ruleset/Classes/Sorcerer.md`; `interactive_ruleset/Classes/Paladin.md`; `interactive_ruleset/Characterizations/Feats.md`; `interactive_ruleset/feats_srd5_2.md` | Factories assemble SRD-style class features into playable actor recipes; not every tabletop option is implemented. |
| 16 | `16-monsters-and-preset-actors.mdx` | Monster stat blocks; Creature roles; Monster actions | engine-adaptation | `interactive_ruleset/Monsters/# Monster Statistics.md`; `interactive_ruleset/Monsters/Goblin.md`; `interactive_ruleset/Monsters/Skeleton.md`; `interactive_ruleset/Monsters/Scout (NPC).md` | Base monster factories map to SRD traits where implemented; preset actors may intentionally exceed literal stat blocks. |
| 17 | `17-encounters-turns-and-controllers.mdx` | Initiative; Rounds and turns; Encounter ending | engine-adaptation | `interactive_ruleset/Gameplay/Combat.md` | Initiative, rounds, turns, surprise, and reactions are SRD-shaped; encounter ending is videogame faction-survival policy. |
| 18 | `18-sessions-apis-and-client-payloads.mdx` | Turn ownership; Action legality; Combat log history | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Spells/# Spellcasting.md` | API payloads expose legal SRD-shaped choices and outcomes to clients; the endpoints are product infrastructure. |
| 19 | `19-map-editor-and-scenario-authoring.mdx` | Terrain; Objects; Scenario authoring | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gamemastering/Objects.md`; `interactive_ruleset/Gamemastering/Traps.md` | Map authoring creates entity-free spaces that later feed SRD-shaped movement, objects, hazards, and encounters. |
| 20 | `20-content-extension-basics.mdx` | Custom effects; Custom actions; Content packs | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gamemastering/Conditions.md`; `interactive_ruleset/Equipment/Gear.md` | Extensions teach how to author new game content with the same value, condition, action, and item contracts. |
| 21 | `21-spell-and-feature-extensions.mdx` | Feature-granted spells; Self and ally targeting; Spell effects | product-extension | `interactive_ruleset/Spells/# Spellcasting.md`; `interactive_ruleset/Classes/Sorcerer.md`; `interactive_ruleset/Classes/Paladin.md` | Aegis-style examples are custom authored content that reuse SRD spell and class-feature surfaces. |
| 22 | `22-playable-scenario-packages.mdx` | Scenario setup; Faction survival; Automated turns | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gamemastering/Objects.md`; `interactive_ruleset/Gamemastering/Traps.md` | Scenario packages bundle map, actors, controllers, and objectives around SRD-shaped encounter play. |
| 23 | `23-standard-arena-game-modes.mdx` | Arena mode; Hero kits; Monster factions | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Classes/Fighter.md`; `interactive_ruleset/Monsters/Skeleton.md`; `interactive_ruleset/Monsters/Goblin.md` | Standard arena is a product mode that combines SRD-shaped heroes, monsters, maps, sessions, and controllers. |
| 24 | `24-built-in-controllers-and-automated-turns.mdx` | Controllers; AI turns; Player input | product-extension | `interactive_ruleset/Gameplay/Combat.md` | Controllers decide or wait for the next legal SRD-shaped turn choice while encounters own the game clock. |
| 25 | `25-live-replication-streams.mdx` | Event history; Combat logs; Client synchronization | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Spells/# Spellcasting.md` | Replication publishes resolved SRD-shaped outcomes and product state through cursors, logs, heartbeats, and bounded queues. |
| 26 | `26-agent-tactical-interface.mdx` | Tactical state; Legal action choices; Expected damage | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gameplay/Abilities.md`; `interactive_ruleset/Spells/# Spellcasting.md` | Tactical state turns legal SRD-shaped choices into an agent-facing decision snapshot. |
| 27 | `27-agent-decision-patterns.mdx` | Behavior priorities; Composite tactics; Utility scoring | product-extension | `interactive_ruleset/Gameplay/Combat.md`; `interactive_ruleset/Gameplay/Abilities.md` | Decision patterns rank and execute legal tactical choices; behavior selection is product AI built on the engine ruleset. |

## Known Open Mapping Work

- Public chapters need a final editorial pass to ensure the SRD relationship is
  visible to readers, not just declared in frontmatter and mapped here.
- Spell-family coverage is intentionally summarized by family. A future pass
  should decide which individual implemented spells deserve per-spell public
  rows and which belong only in tests/internal notes.
- Monster factories need a final policy decision on which stat-block deviations
  are product tuning and which are bugs.
- Class and feat coverage needs a final matrix of implemented SRD features,
  intentionally omitted features, and custom videogame features.
- Product-extension chapters should stay clear that sessions, map authoring,
  controllers, streams, and agents are videogame systems built on SRD-shaped
  play, not extra tabletop rules.
