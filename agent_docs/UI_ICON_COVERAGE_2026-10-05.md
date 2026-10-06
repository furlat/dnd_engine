# UI icon coverage — second source audit, 2026-10-05

**October 6 implementation update:** the accepted CIE28 delivery resolves the
ordinary spell/action icon gaps listed in this historical study. Installed
resources now include 613 icon registrations, 56 original player portraits plus
168 native role images, and 123 role images for 41 exact creature associations.
All ordinary declared spell icons resolve, including the manifest's explicitly
shared Fly image. The eight remaining declared gaps (including one fixture)
and missing ground-consumable appearances are documented in
[the current artwork handoff](PLAYER_UI_ARTWORK_HANDOFF_2026-10-06.md).
The ignored acceptance output retains the current machine-readable coverage
scan. Counts below describe the original audit, not missing delivered artwork.

This replaces the initial string-search inventory. Study only; no runtime mappings changed. All counts are against the current configured content registry and recovered NeuroClient icon bank. Artwork existence is separate from semantic/current binding correctness.

## Coverage denominators and method

- 528 recovered WebP icons and 56 portraits; originals retained and local copies hash-receipted.
- 95 registered creature factories materialized with default possessions: 1,631 registered action-provider occurrences inspected.
- All 374 direct item builders materialized: 36 stored item-use action templates inspected.
- Zero materialization failures. Item templates use exact action-class declaration lookup because their behavior binding is attached on use, not necessarily construction.
- 89 current automatic/choice class feature occurrences across six class/subclass tables, 49 distinct feature/feat IDs. Retired IDs found only in source strings were removed from this denominator.
- Full registry scan includes developer/internal/fixture entries, listed explicitly. Default creature materialization proves their registered grants, not every parameterized combination or temporarily granted action. The full registry action/spell list separately covers such dynamic registered behavior identities.
- State-dependent world actions come from get_use_actions overrides in environment.py, environment_interactables.py and torches.py: open/close, toggle, ignite/extinguish, loot; these are included as registered behaviors in the matrix below. Environmental interactions belong to world click/context, not the action bar.

## Missing spell icon files

| Spell/content | Required key | Visibility |
|---|---|---|
| Acid Flask (`spell.acid_flask`) | `spell.acid_flask` | observed |
| Conjure Fiend (`spell.conjure_fiend`) | `spell.conjure_fiend` | public |
| Test Bless (`spell.fixture.test_bless`) | `spell.fixture.test_bless` | developer |
| Ice Knife (`spell.ice_knife`) | `spell.ice_knife` | public |
| Barkskin (`spell.barkskin`) | `spell.barkskin` | public |
| Conjure Animals (`spell.conjure_animals`) | `spell.conjure_animals` | public |
| Conjure Fey (`spell.conjure_fey`) | `spell.conjure_fey` | public |
| Fire Shield (`spell.fire_shield`) | `spell.fire_shield` | public |
| Longstrider (`spell.longstrider`) | `spell.longstrider` | public |
| Produce Flame (`spell.produce_flame`) | `spell.produce_flame` | public |
| Shillelagh (`spell.shillelagh`) | `spell.shillelagh` | public |
| Wall of Fire (`spell.wall_of_fire`) | `spell.wall_of_fire` | public |
| Wall of Force (`spell.wall_of_force`) | `spell.wall_of_force` | public |
| Wall of Ice (`spell.wall_of_ice`) | `spell.wall_of_ice` | public |
| Wall of Stone (`spell.wall_of_stone`) | `spell.wall_of_stone` | public |
| Wall of Thorns (`spell.wall_of_thorns`) | `spell.wall_of_thorns` | public |
| Wind Wall (`spell.wind_wall`) | `spell.wind_wall` | public |

`spell.fixture.test_bless` is fixture content, not a production art request. Acid Flask is item-delivered spell behavior; its action may intentionally inherit the existing acid-flask ITEM icon, but that needs an explicit current binding, not a filename guess.

## Other registered action/feature/reaction/trait gaps

| Kind | Name / ID | Status | Required key |
|---|---|---|---|
| action | Toggle Lever / `action.environment.control_lever.toggle` | missing file | `action.environment.control_lever.toggle` |
| action | Slip free of jaws / `action.environment.escape_jaw.acrobatics` | missing file | `action.environment.escape_jaw.acrobatics` |
| action | Force jaws open / `action.environment.escape_jaw.athletics` | missing file | `action.environment.escape_jaw.athletics` |
| action | Close Chest / `action.environment.storage_chest.close` | missing file | `action.environment.storage_chest.close` |
| action | Open Chest / `action.environment.storage_chest.open` | missing file | `action.environment.storage_chest.open` |
| action | Ember Quiver / `action.item.ember_quiver` | missing file | `action.item.ember_quiver` |
| action | Dismiss Summon / `action.summon.dismiss` | missing file | `action.summon.dismiss` |
| class_feature | Aegis Training / `class_feature.aegis_training` | missing file | `class_feature.aegis_training` |
| trait | Hit Save Rider / `trait.attack_hit_save_rider` | missing file | `trait.attack_hit_save_rider` |
| trait | Body Response / `trait.body_response` | no mapping | `None` |
| trait | Keen Perception / `trait.keen_perception` | missing file | `trait.keen_perception` |
| action | Innate Invisibility / `action.monster.innate_invisibility` | missing file | `action.monster.innate_invisibility` |
| action | Multiattack Runtime / `action.monster.multiattack` | missing file | `action.monster.multiattack` |
| action | Life Drain / `action.monster.wight.life_drain` | missing file | `action.monster.wight.life_drain` |
| action | Dismiss Fire Shield / `action.spell.fire_shield.dismiss` | missing file | `action.spell.fire_shield.dismiss` |
| trait | Innate Flight / `trait.innate_flight` | missing file | `trait.innate_flight` |
| trait | Magic Resistance / `trait.magic_resistance` | missing file | `trait.magic_resistance` |
| action | Attack / `action.attack` | no mapping | `None` |

Attack has an intentional provider-dependent presentation: use the selected weapon or unarmed icon; this is not a request for new Attack art. Generic runtime Multiattack likewise needs explicit creature/configured-action presentation. Structural traits such as Body Response and Hit Save Rider are internal mechanics, not automatically player buttons; disposition must follow authored visibility and surfaced mechanic, not manufacture hotbar actions.

## Every stored item-granted action

| Item provider | Native behavior | Current behavior icon status |
|---|---|---|
| `consumable.acid_flask` | `spell.acid_flask` | missing file |
| `consumable.healing_potion` | `action.item.potion_healing.drink` | available |
| `consumable.potion_greater_invisibility` | `action.item.potion_greater_invisibility.drink` | available |
| `consumable.potion_haste` | `action.item.potion_haste.drink` | available |
| `consumable.potion_true_seeing` | `action.item.potion_true_seeing.drink` | available |
| `consumable.weapon_coat.basic_poison` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.basic_poison` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.concentration_fire` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.fire` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.fire` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.lightning` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.lightning` | `action.item.weapon_coat.apply` | available |
| `consumable.weapon_coat.timed_fire` | `action.item.weapon_coat.apply` | available |
| `environment.arcane_device` | `action.environment.arcane_device.activate` | available |
| `environment.arcane_machine_gun` | `spell.sleep` | available |
| `environment.campfire` | `action.environment.campfire.rest` | available |
| `environment.campfire` | `action.environment.campfire.cook` | available |
| `environment.chest.fantasy_a1` | `action.environment.storage_chest.loot_all` | available |
| `environment.chest.fantasy_a3` | `action.environment.storage_chest.loot_all` | available |
| `environment.chest.fantasy_b1` | `action.environment.storage_chest.loot_all` | available |
| `environment.fireball_cannon` | `spell.fireball` | available |
| `gear.ember_quiver` | `action.item.ember_quiver` | missing file |
| `gear.field_kit` | `action.item.field_kit.deploy` | available |
| `gear.warden_pack` | `spell.resistance` | available |
| `gear.wayfarer_pack` | `spell.longstrider` | missing file |
| `spell_item.scroll_fire_bolt` | `spell.fire_bolt` | available |
| `spell_item.scroll_fireball` | `spell.fireball` | available |
| `spell_item.scroll_hold_person` | `spell.hold_person` | available |
| `spell_item.scroll_invisibility` | `spell.invisibility` | available |
| `spell_item.scroll_mage_armor` | `spell.mage_armor` | available |
| `spell_item.scroll_magic_missile` | `spell.magic_missile` | available |
| `spell_item.scroll_spike_growth` | `spell.spike_growth` | available |
| `spell_item.wand_fire` | `spell.burning_hands` | available |
| `spell_item.wand_fire` | `spell.fireball` | available |
| `spell_item.wand_fire` | `spell.fireball` | available |
| `spell_item.wand_magic_missiles` | `spell.magic_missile` | available |

Actual missing behavior files affecting these stored grants: Acid Flask, Ember Quiver, and Longstrider (Wayfarer Pack). Scrolls/wands retain provider badges and charges while resolving their spell icon. Two coating rows are main-/off-hand variants, not duplicate abilities. This pass does not claim item INVENTORY icons are all mapped; direct item ids need the same separate appearance lookup discussed in the UI plan.

## Creature-granted actions: missing icons and inherited Attack

| Behavior | Affected creature providers |
|---|---|
| `action.attack` | 95: `creature.acolyte`, `creature.bandit`, `creature.bandit_captain`, `creature.berserker`, `creature.bison`, `creature.blue_raptor`, `creature.boar`, `creature.brown_bear`, `creature.bugbear`, `creature.claw_mote_devil`, `creature.commoner`, `creature.configured_srd.acolyte`, `creature.configured_srd.bandit`, `creature.configured_srd.bandit_captain`, `creature.configured_srd.berserker`, `creature.configured_srd.bugbear`, `creature.configured_srd.commoner`, `creature.configured_srd.cult_fanatic`, `creature.configured_srd.cultist`, `creature.configured_srd.gnoll`, `creature.configured_srd.guard`, `creature.configured_srd.hobgoblin`, `creature.configured_srd.knight`, `creature.configured_srd.kobold`, `creature.configured_srd.mage`, `creature.configured_srd.orc`, `creature.configured_srd.priest`, `creature.configured_srd.scout`, `creature.configured_srd.spy`, `creature.configured_srd.thug`, `creature.configured_srd.tribal_warrior`, `creature.configured_srd.veteran`, `creature.corrosive_demon`, `creature.cult_fanatic`, `creature.cultist`, `creature.dire_wolf`, `creature.dread_demon`, `creature.dretch`, `creature.elephant`, `creature.fellwing_devil`, `creature.generic_caster`, `creature.ghoul`, `creature.gnoll`, `creature.goblin`, `creature.goblin_archer`, `creature.goblin_ashhide`, `creature.goblin_briarling`, `creature.goblin_buckler_hex`, `creature.goblin_buckler_rat`, `creature.goblin_caster`, `creature.goblin_gloomplate`, `creature.goblin_gutterknife`, `creature.goblin_ironhide`, `creature.goblin_longpoint`, `creature.goblin_mossbreaker`, `creature.goblin_packtrail`, `creature.goblin_quicktail`, `creature.goblin_redcap`, `creature.goblin_reedshot`, `creature.goblin_spearline`, `creature.goblin_thornrunner`, `creature.goblin_wispbinder`, `creature.guard`, `creature.hobgoblin`, `creature.hound`, `creature.huntsman_wing_devil`, `creature.jaguar`, `creature.knight`, `creature.kobold`, `creature.lion`, `creature.mage`, `creature.mammoth`, `creature.ogre`, `creature.ogre_zombie`, `creature.orc`, `creature.ostrich`, `creature.polar_bear`, `creature.priest`, `creature.raptor`, `creature.rhinoceros`, `creature.scout`, `creature.skeleton`, `creature.skeleton_archer`, `creature.skeleton_warlock`, `creature.skeleton_warrior`, `creature.spy`, `creature.stag`, `creature.stegosaurus`, `creature.thug`, `creature.tiger`, `creature.tribal_warrior`, `creature.triceratops`, `creature.veteran`, `creature.wolf`, `creature.zombie` |
| `action.monster.multiattack` | 24: `creature.bandit_captain`, `creature.brown_bear`, `creature.configured_srd.bandit_captain`, `creature.configured_srd.cult_fanatic`, `creature.configured_srd.knight`, `creature.configured_srd.scout`, `creature.configured_srd.spy`, `creature.configured_srd.thug`, `creature.configured_srd.veteran`, `creature.corrosive_demon`, `creature.cult_fanatic`, `creature.dread_demon`, `creature.dretch`, `creature.fellwing_devil`, `creature.goblin_briarling`, `creature.goblin_gloomplate`, `creature.huntsman_wing_devil`, `creature.knight`, `creature.polar_bear`, `creature.scout`, `creature.spy`, `creature.stegosaurus`, `creature.thug`, `creature.veteran` |
| `action.summon.dismiss` | 95: `creature.acolyte`, `creature.bandit`, `creature.bandit_captain`, `creature.berserker`, `creature.bison`, `creature.blue_raptor`, `creature.boar`, `creature.brown_bear`, `creature.bugbear`, `creature.claw_mote_devil`, `creature.commoner`, `creature.configured_srd.acolyte`, `creature.configured_srd.bandit`, `creature.configured_srd.bandit_captain`, `creature.configured_srd.berserker`, `creature.configured_srd.bugbear`, `creature.configured_srd.commoner`, `creature.configured_srd.cult_fanatic`, `creature.configured_srd.cultist`, `creature.configured_srd.gnoll`, `creature.configured_srd.guard`, `creature.configured_srd.hobgoblin`, `creature.configured_srd.knight`, `creature.configured_srd.kobold`, `creature.configured_srd.mage`, `creature.configured_srd.orc`, `creature.configured_srd.priest`, `creature.configured_srd.scout`, `creature.configured_srd.spy`, `creature.configured_srd.thug`, `creature.configured_srd.tribal_warrior`, `creature.configured_srd.veteran`, `creature.corrosive_demon`, `creature.cult_fanatic`, `creature.cultist`, `creature.dire_wolf`, `creature.dread_demon`, `creature.dretch`, `creature.elephant`, `creature.fellwing_devil`, `creature.generic_caster`, `creature.ghoul`, `creature.gnoll`, `creature.goblin`, `creature.goblin_archer`, `creature.goblin_ashhide`, `creature.goblin_briarling`, `creature.goblin_buckler_hex`, `creature.goblin_buckler_rat`, `creature.goblin_caster`, `creature.goblin_gloomplate`, `creature.goblin_gutterknife`, `creature.goblin_ironhide`, `creature.goblin_longpoint`, `creature.goblin_mossbreaker`, `creature.goblin_packtrail`, `creature.goblin_quicktail`, `creature.goblin_redcap`, `creature.goblin_reedshot`, `creature.goblin_spearline`, `creature.goblin_thornrunner`, `creature.goblin_wispbinder`, `creature.guard`, `creature.hobgoblin`, `creature.hound`, `creature.huntsman_wing_devil`, `creature.jaguar`, `creature.knight`, `creature.kobold`, `creature.lion`, `creature.mage`, `creature.mammoth`, `creature.ogre`, `creature.ogre_zombie`, `creature.orc`, `creature.ostrich`, `creature.polar_bear`, `creature.priest`, `creature.raptor`, `creature.rhinoceros`, `creature.scout`, `creature.skeleton`, `creature.skeleton_archer`, `creature.skeleton_warlock`, `creature.skeleton_warrior`, `creature.spy`, `creature.stag`, `creature.stegosaurus`, `creature.thug`, `creature.tiger`, `creature.tribal_warrior`, `creature.triceratops`, `creature.veteran`, `creature.wolf`, `creature.zombie` |

Dismiss Summon is registered on ordinary creature templates but is usable only with the summon relationship; registration count is not a count of creatures always displaying that button.

## Exact current class feature/choice mappings

All 49 feature/feat IDs have a legacy asset candidate physically present. Most have NO current registered descriptor because direct class progression intentionally replaced the old declarations. Thus these are binding/schema migration work, not 49 requests for new artwork. Authenticated old hashes cannot be reused as new ContentRefs. The current direct native feature ID is the source identity.

| Current feature ID | Current binding | Existing asset candidate | Current source levels |
|---|---|---|---|
| `class_feature.barbarian.brutal_critical` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-brutalcritical` (file present) | barbarian 13, barbarian 17, barbarian 9 |
| `class_feature.barbarian.danger_sense` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-dangersense` (file present) | barbarian 2 |
| `class_feature.barbarian.fast_movement` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-fastmovement` (file present) | barbarian 5 |
| `class_feature.barbarian.feral_instinct` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-feralinstinct` (file present) | barbarian 7 |
| `class_feature.barbarian.frenzy` | direct feature; no ContentRef descriptor | `condition.dnd-classes-rage-frenzyfeature` (file present) | berserker 3 |
| `class_feature.barbarian.indomitable_might` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-indomitablemight` (file present) | barbarian 18 |
| `class_feature.barbarian.intimidating_presence` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-intimidatingpresencefeature` (file present) | berserker 10 |
| `class_feature.barbarian.mindless_rage` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-mindlessrage` (file present) | berserker 6 |
| `class_feature.barbarian.persistent_rage` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-persistentrage` (file present) | barbarian 15 |
| `class_feature.barbarian.primal_champion` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-primalchampion` (file present) | barbarian 20 |
| `class_feature.barbarian.rage` | direct feature; no ContentRef descriptor | `condition.dnd-classes-rage-ragefeature` (file present) | barbarian 1, barbarian 12, barbarian 16, barbarian 17, barbarian 20, barbarian 3, barbarian 6, barbarian 9 |
| `class_feature.barbarian.reckless_attack` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-recklessattackfeature` (file present) | barbarian 2 |
| `class_feature.barbarian.relentless_rage` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-relentlessrage` (file present) | barbarian 11 |
| `class_feature.barbarian.retaliation` | direct feature; no ContentRef descriptor | `condition.dnd-classes-barbarian-retaliation` (file present) | berserker 14 |
| `class_feature.barbarian.unarmored_defense` | direct feature; no ContentRef descriptor | `item.natural-armor` (file present) | barbarian 1 |
| `class_feature.extra_attack` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-extraattackfeature` (file present) | barbarian 5, fighter 11, fighter 20, fighter 5 |
| `class_feature.fighter.action_surge` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-actionsurgefeature` (file present) | fighter 17, fighter 2 |
| `class_feature.fighter.fighting_style.archery` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-fightingstylearchery` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.fighting_style.defense` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-fightingstyledefense` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.fighting_style.dueling` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-fightingstyledueling` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.fighting_style.great_weapon_fighting` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-greatweaponfighting` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.fighting_style.protection` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-fightingstyleprotection` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.fighting_style.two_weapon_fighting` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-fightingstyletwoweaponfighting` (file present) | champion 10, fighter 1 |
| `class_feature.fighter.improved_critical` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-improvedcritical` (file present) | champion 3 |
| `class_feature.fighter.indomitable` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-indomitable` (file present) | fighter 13, fighter 17, fighter 9 |
| `class_feature.fighter.remarkable_athlete` | direct feature; no ContentRef descriptor | `action.jump` (file present) | champion 7 |
| `class_feature.fighter.second_wind` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-secondwindfeature` (file present) | fighter 1 |
| `class_feature.fighter.superior_critical` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-superiorcritical` (file present) | champion 15 |
| `class_feature.fighter.survivor` | direct feature; no ContentRef descriptor | `condition.dnd-classes-fighter-survivor` (file present) | champion 18 |
| `class_feature.sorcerer.draconic_ancestry.black` | direct feature; no ContentRef descriptor | `spell.acid-splash` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.blue` | direct feature; no ContentRef descriptor | `spell.lightning-bolt` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.brass` | direct feature; no ContentRef descriptor | `spell.fire-bolt` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.bronze` | direct feature; no ContentRef descriptor | `spell.lightning-bolt` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.copper` | direct feature; no ContentRef descriptor | `spell.acid-splash` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.gold` | direct feature; no ContentRef descriptor | `spell.fire-bolt` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.green` | direct feature; no ContentRef descriptor | `spell.poison-spray` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.red` | direct feature; no ContentRef descriptor | `spell.fire-bolt` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.silver` | direct feature; no ContentRef descriptor | `spell.ray-of-frost` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_ancestry.white` | direct feature; no ContentRef descriptor | `spell.ray-of-frost` (file present) | draconic 1 |
| `class_feature.sorcerer.draconic_presence` | direct feature; no ContentRef descriptor | `spell.fear` (file present) | draconic 18 |
| `class_feature.sorcerer.draconic_resilience` | direct feature; no ContentRef descriptor | `condition.dnd-classes-sorcerer-draconicresilience` (file present) | draconic 1 |
| `class_feature.sorcerer.dragon_wings` | direct feature; no ContentRef descriptor | `spell.haste` (file present) | draconic 14 |
| `class_feature.sorcerer.elemental_affinity` | direct feature; no ContentRef descriptor | `condition.dnd-classes-sorcerer-elementalaffinity` (file present) | draconic 6 |
| `class_feature.sorcerer.metamagic.distant_spell` | direct feature; no ContentRef descriptor | `condition.dnd-classes-sorcerer-sorcerypointsfeature` (file present) | sorcerer 10, sorcerer 3 |
| `class_feature.sorcerer.metamagic.quickened_spell` | direct feature; no ContentRef descriptor | `action.quickened-spell` (file present) | sorcerer 10, sorcerer 3 |
| `class_feature.sorcerer.metamagic.twinned_spell` | direct feature; no ContentRef descriptor | `action.twinned-spell` (file present) | sorcerer 10, sorcerer 3 |
| `class_feature.sorcerer.sorcerous_restoration` | direct feature; no ContentRef descriptor | `condition.dnd-classes-sorcerer-sorcerypointsfeature` (file present) | sorcerer 20 |
| `class_feature.sorcerer.sorcery_points` | direct feature; no ContentRef descriptor | `condition.dnd-classes-sorcerer-sorcerypointsfeature` (file present) | sorcerer 2 |
| `feat.lucky` | available | `condition.dnd-classes-feats-luckyfeature` (file present) | barbarian 12, barbarian 16, barbarian 19, barbarian 4, barbarian 8, fighter 12, fighter 14, fighter 16, fighter 19, fighter 4, fighter 6, fighter 8, sorcerer 12, sorcerer 16, sorcerer 19, sorcerer 4, sorcerer 8 |

Some old choices are broad approximations: Dragon Wings used Haste; Distant Spell/Sorcerous Restoration reuse the sorcery-points emblem; draconic ancestries reuse their element spell icon. Preserve them provisionally only as documented substitutions; no new pixels are authorized.

## Every registered spell/action/feature/reaction/trait

| Kind | ID | Display name | Icon | Status |
|---|---|---|---|---|
| action | `action.creature.skeleton_archer.mark_target` | Mark Target | `action.mark-target` | available |
| action | `action.environment.arcane_device.activate` | Activate Device | `action.activate-device` | available |
| action | `action.environment.campfire.cook` | Cook | `action.cook` | available |
| action | `action.environment.campfire.rest` | Rest | `action.rest` | available |
| action | `action.environment.control_lever.toggle` | Toggle Lever | `action.environment.control_lever.toggle` | missing file |
| action | `action.environment.directional_door.close` | Close Directional Door | `action.close-door` | available |
| action | `action.environment.directional_door.open` | Open Directional Door | `action.open-door` | available |
| action | `action.environment.door.close` | Close Door | `action.close-door` | available |
| action | `action.environment.door.open` | Open Door | `action.open-door` | available |
| action | `action.environment.escape_jaw.acrobatics` | Slip free of jaws | `action.environment.escape_jaw.acrobatics` | missing file |
| action | `action.environment.escape_jaw.athletics` | Force jaws open | `action.environment.escape_jaw.athletics` | missing file |
| action | `action.environment.storage_chest.close` | Close Chest | `action.environment.storage_chest.close` | missing file |
| action | `action.environment.storage_chest.loot_all` | Loot All | `action.loot-all` | available |
| action | `action.environment.storage_chest.open` | Open Chest | `action.environment.storage_chest.open` | missing file |
| action | `action.environment.trap_lever.pull` | Pull Lever | `action.pull-lever` | available |
| action | `action.environment.wall_torch.extinguish` | Extinguish Wall Torch | `action.extinguish-wall-torch` | available |
| action | `action.environment.wall_torch.ignite` | Ignite Wall Torch | `action.light-wall-torch` | available |
| action | `action.item.ember_quiver` | Ember Quiver | `action.item.ember_quiver` | missing file |
| action | `action.item.field_kit.deploy` | Deploy Field Focus | `item.field-kit` | available |
| action | `action.item.potion_greater_invisibility.drink` | Drink Greater Invisibility Potion | `item.potion-of-greater-invisibility` | available |
| action | `action.item.potion_haste.drink` | Drink Haste Potion | `item.potion-of-haste` | available |
| action | `action.item.potion_healing.drink` | Drink Healing Potion | `item.potion-of-healing` | available |
| action | `action.item.potion_true_seeing.drink` | Drink True Seeing Potion | `spell.true-seeing` | available |
| action | `action.item.torch.extinguish` | Extinguish Torch | `item.torch` | available |
| action | `action.item.torch.ignite` | Ignite Torch | `item.torch` | available |
| action | `action.item.weapon_coat.apply` | Coat Main Hand | `item.weapon-coat` | available |
| action | `action.monster.multiattack.brown_bear` | Brown Bear Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.fellwing_devil` | Fellwing Devil Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.goblin_briarling` | Briarling Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.goblin_gloomplate` | Gloomplate Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.huntsman_wing_devil` | Huntsman Wing Devil Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.polar_bear` | Polar Bear Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.stegosaurus` | Stegosaurus Multiattack | `ui.filter-attacks` | available |
| action | `action.summon.dismiss` | Dismiss Summon | `action.summon.dismiss` | missing file |
| class_feature | `class_feature.aegis_training` | Aegis Training | `class_feature.aegis_training` | missing file |
| spell | `spell.acid_flask` | Acid Flask | `spell.acid_flask` | missing file |
| spell | `spell.aegis_spark` | Aegis Spark | `spell.aegis-spark` | available |
| spell | `spell.conjure_fiend` | Conjure Fiend | `spell.conjure_fiend` | missing file |
| spell | `spell.fixture.test_bless` | Test Bless | `spell.fixture.test_bless` | missing file |
| spell | `spell.ice_knife` | Ice Knife | `spell.ice_knife` | missing file |
| spell | `spell.necrotic_bless` | Necrotic Bless | `spell.necrotic-bless` | available |
| trait | `trait.attack_hit_save_rider` | Hit Save Rider | `trait.attack_hit_save_rider` | missing file |
| trait | `trait.body_response` | Body Response | `None` | no mapping |
| trait | `trait.circus_dual_wielder` | Dual Wielder | `condition.dnd-monsters-circus-fighter-conditions-dualwielder` | available |
| trait | `trait.circus_elemental_affinity` | Elemental Affinity | `condition.dnd-monsters-circus-fighter-conditions-elementalaffinity` | available |
| trait | `trait.circus_elemental_weapon_mastery` | Elemental Weapon Mastery | `condition.dnd-monsters-circus-fighter-conditions-elementalweaponmastery` | available |
| trait | `trait.circus_performer` | Circus Performer | `condition.dnd-monsters-circus-fighter-conditions-circusperformer` | available |
| trait | `trait.circus_tired` | Tired | `condition.dnd-monsters-circus-fighter-conditions-tired` | available |
| trait | `trait.keen_perception` | Keen Perception | `trait.keen_perception` | missing file |
| trait | `trait.skeleton_archer_marked` | Marked | `condition.dnd-monsters-skeleton-abilities-marked` | available |
| action | `action.class.barbarian.reckless_attack` | Reckless Attack | `action.reckless-attack` | available |
| action | `action.core.drop` | Drop | `action.drop` | available |
| action | `action.core.drop_prone` | Drop Prone | `action.drop-prone` | available |
| action | `action.core.stand_up` | Stand Up | `action.stand-up` | available |
| action | `action.environment.heroes_feast.eat` | Eat from Feast | `action.eat-from-feast` | available |
| action | `action.monster.innate_invisibility` | Innate Invisibility | `action.monster.innate_invisibility` | missing file |
| action | `action.monster.multiattack.bandit_captain.melee` | Bandit Captain Multiattack: Melee | `action.bandit-captain-multiattack-melee` | available |
| action | `action.monster.multiattack.bandit_captain.ranged` | Bandit Captain Multiattack: Ranged | `action.bandit-captain-multiattack-ranged` | available |
| action | `action.monster.multiattack.cult_fanatic` | Cult Fanatic Multiattack | `action.cult-fanatic-multiattack` | available |
| action | `action.monster.multiattack.dretch` | Dretch Multiattack | `ui.filter-attacks` | available |
| action | `action.monster.multiattack.knight` | Knight Multiattack | `action.knight-multiattack` | available |
| action | `action.monster.multiattack.scout.longbow` | Scout Multiattack: Longbow | `action.scout-multiattack-longbow` | available |
| action | `action.monster.multiattack.scout.shortsword` | Scout Multiattack: Shortsword | `action.scout-multiattack-shortsword` | available |
| action | `action.monster.multiattack.spy` | Spy Multiattack | `action.spy-multiattack` | available |
| action | `action.monster.multiattack.thug` | Thug Multiattack | `action.thug-multiattack` | available |
| action | `action.monster.multiattack.veteran.melee` | Veteran Multiattack: Melee | `action.veteran-multiattack-melee` | available |
| action | `action.monster.multiattack.veteran.ranged` | Veteran Multiattack: Ranged | `action.veteran-multiattack-ranged` | available |
| action | `action.monster.multiattack` | Multiattack Runtime | `action.monster.multiattack` | missing file |
| action | `action.monster.natural_attack` | Natural Attack | `action.bite` | available |
| action | `action.monster.wight.life_drain` | Life Drain | `action.monster.wight.life_drain` | missing file |
| action | `action.spell.call_lightning.strike` | Call Lightning Strike | `action.call-lightning-strike` | available |
| action | `action.spell.expeditious_retreat.dash` | Dash (Bonus) | `action.dash-bonus` | available |
| action | `action.spell.eyebite.strike` | Eyebite Strike | `action.eyebite-strike` | available |
| action | `action.spell.fire_shield.dismiss` | Dismiss Fire Shield | `action.spell.fire_shield.dismiss` | missing file |
| action | `action.spell.freedom_of_movement.escape` | Freedom of Movement Escape | `action.freedom-of-movement-escape` | available |
| action | `action.spell.sunbeam.strike` | Sunbeam Strike | `action.sunbeam-strike` | available |
| action | `action.spell.telekinesis.move` | Telekinesis: Move | `action.telekinesis-move` | available |
| action | `action.spell.web.escape` | Escape Web | `action.escape-web` | available |
| action | `action.trait.aggressive` | Aggressive | `action.aggressive` | available |
| action | `action.trait.divine_eminence` | Divine Eminence | `action.divine-eminence` | available |
| action | `action.trait.leadership` | Leadership | `action.leadership` | available |
| class_feature | `class_feature.barbarian.reckless_attacking` | Reckless Attacking | `condition.dnd-classes-barbarian-recklessattacking` | available |
| feat | `feat.lucky` | Lucky | `condition.dnd-classes-feats-luckyfeature` | available |
| reaction | `reaction.class_feature.paladin.divine_smite` | Divine Smite | `reaction.divine-smite` | available |
| reaction | `reaction.monster.parry` | Parry | `condition.dnd-monsters-traits-parryfeature` | available |
| reaction | `reaction.spell.counterspell` | Counterspell | `reaction.counterspell` | available |
| reaction | `reaction.spell.hellish_rebuke` | Hellish Rebuke | `spell.hellish-rebuke` | available |
| reaction | `reaction.spell.shield` | Shield | `reaction.shield` | available |
| spell | `spell.acid_splash` | Acid Splash | `spell.acid-splash` | available |
| spell | `spell.aid` | Aid | `spell.aid` | available |
| spell | `spell.antimagic_field` | Antimagic Field | `spell.antimagic-field` | available |
| spell | `spell.bane` | Bane | `spell.bane` | available |
| spell | `spell.banishment` | Banishment | `spell.banishment` | available |
| spell | `spell.barkskin` | Barkskin | `spell.barkskin` | missing file |
| spell | `spell.beacon_of_hope` | Beacon of Hope | `spell.beacon-of-hope` | available |
| spell | `spell.bestow_curse` | Bestow Curse | `spell.bestow-curse` | available |
| spell | `spell.bless` | Bless | `spell.bless` | available |
| spell | `spell.blight` | Blight | `spell.blight` | available |
| spell | `spell.blindness_deafness` | Blindness/Deafness | `spell.blindness-deafness` | available |
| spell | `spell.blur` | Blur | `spell.blur` | available |
| spell | `spell.burning_hands` | Burning Hands | `spell.burning-hands` | available |
| spell | `spell.call_lightning` | Call Lightning | `spell.call-lightning` | available |
| spell | `spell.chain_lightning` | Chain Lightning | `spell.chain-lightning` | available |
| spell | `spell.charm_person` | Charm Person | `spell.charm-person` | available |
| spell | `spell.chill_touch` | Chill Touch | `spell.chill-touch` | available |
| spell | `spell.circle_of_death` | Circle of Death | `spell.circle-of-death` | available |
| spell | `spell.cloudkill` | Cloudkill | `spell.cloudkill` | available |
| spell | `spell.color_spray` | Color Spray | `spell.color-spray` | available |
| spell | `spell.command` | Command | `spell.command` | available |
| spell | `spell.cone_of_cold` | Cone of Cold | `spell.cone-of-cold` | available |
| spell | `spell.conjure_animals` | Conjure Animals | `spell.conjure_animals` | missing file |
| spell | `spell.conjure_fey` | Conjure Fey | `spell.conjure_fey` | missing file |
| spell | `spell.continual_flame` | Continual Flame | `spell.continual-flame` | available |
| spell | `spell.counterspell` | Counterspell | `reaction.counterspell` | available |
| spell | `spell.cure_wounds` | Cure Wounds | `spell.cure-wounds` | available |
| spell | `spell.darkness` | Darkness | `spell.darkness` | available |
| spell | `spell.darkvision` | Darkvision | `spell.darkvision` | available |
| spell | `spell.daylight` | Daylight | `spell.daylight` | available |
| spell | `spell.death_ward` | Death Ward | `spell.death-ward` | available |
| spell | `spell.dimension_door` | Dimension Door | `spell.dimension-door` | available |
| spell | `spell.disintegrate` | Disintegrate | `spell.disintegrate` | available |
| spell | `spell.divine_word` | Divine Word | `spell.divine-word` | available |
| spell | `spell.eldritch_blast` | Eldritch Blast | `spell.eldritch-blast` | available |
| spell | `spell.enhance_ability` | Enhance Ability | `spell.enhance-ability` | available |
| spell | `spell.enlarge_reduce` | Enlarge/Reduce | `spell.enlarge-reduce` | available |
| spell | `spell.expeditious_retreat` | Expeditious Retreat | `spell.expeditious-retreat` | available |
| spell | `spell.eyebite` | Eyebite | `spell.eyebite` | available |
| spell | `spell.false_life` | False Life | `spell.false-life` | available |
| spell | `spell.fear` | Fear | `spell.fear` | available |
| spell | `spell.finger_of_death` | Finger of Death | `spell.finger-of-death` | available |
| spell | `spell.fire_bolt` | Fire Bolt | `spell.fire-bolt` | available |
| spell | `spell.fire_shield` | Fire Shield | `spell.fire_shield` | missing file |
| spell | `spell.fireball` | Fireball | `spell.fireball` | available |
| spell | `spell.flame_strike` | Flame Strike | `spell.flame-strike` | available |
| spell | `spell.fly` | Fly | `spell.fly` | available |
| spell | `spell.fog_cloud` | Fog Cloud | `spell.fog-cloud` | available |
| spell | `spell.freedom_of_movement` | Freedom of Movement | `spell.freedom-of-movement` | available |
| spell | `spell.globe_of_invulnerability` | Globe of Invulnerability | `spell.globe-of-invulnerability` | available |
| spell | `spell.grease` | Grease | `spell.grease` | available |
| spell | `spell.greater_invisibility` | Greater Invisibility | `spell.greater-invisibility` | available |
| spell | `spell.greater_restoration` | Greater Restoration | `spell.greater-restoration` | available |
| spell | `spell.guardian_of_faith` | Guardian of Faith | `spell.guardian-of-faith` | available |
| spell | `spell.guidance` | Guidance | `spell.guidance` | available |
| spell | `spell.guiding_bolt` | Guiding Bolt | `spell.guiding-bolt` | available |
| spell | `spell.gust_of_wind` | Gust of Wind | `spell.gust-of-wind` | available |
| spell | `spell.harm` | Harm | `spell.harm` | available |
| spell | `spell.haste` | Haste | `spell.haste` | available |
| spell | `spell.heal` | Heal | `spell.heal` | available |
| spell | `spell.healing_word` | Healing Word | `spell.healing-word` | available |
| spell | `spell.hellish_rebuke` | Hellish Rebuke | `spell.hellish-rebuke` | available |
| spell | `spell.heroes_feast` | Heroes' Feast | `spell.heroes-feast` | available |
| spell | `spell.hold_monster` | Hold Monster | `spell.hold-monster` | available |
| spell | `spell.hold_person` | Hold Person | `spell.hold-person` | available |
| spell | `spell.hypnotic_pattern` | Hypnotic Pattern | `spell.hypnotic-pattern` | available |
| spell | `spell.ice_storm` | Ice Storm | `spell.ice-storm` | available |
| spell | `spell.incendiary_cloud` | Incendiary Cloud | `spell.incendiary-cloud` | available |
| spell | `spell.inflict_wounds` | Inflict Wounds | `spell.inflict-wounds` | available |
| spell | `spell.insect_plague` | Insect Plague | `spell.insect-plague` | available |
| spell | `spell.invisibility` | Invisibility | `spell.invisibility` | available |
| spell | `spell.jump` | Jump | `spell.jump` | available |
| spell | `spell.lesser_restoration` | Lesser Restoration | `spell.lesser-restoration` | available |
| spell | `spell.light` | Light | `spell.light` | available |
| spell | `spell.lightning_bolt` | Lightning Bolt | `spell.lightning-bolt` | available |
| spell | `spell.longstrider` | Longstrider | `spell.longstrider` | missing file |
| spell | `spell.mage_armor` | Mage Armor | `spell.mage-armor` | available |
| spell | `spell.magic_missile` | Magic Missile | `spell.magic-missile` | available |
| spell | `spell.mass_cure_wounds` | Mass Cure Wounds | `spell.mass-cure-wounds` | available |
| spell | `spell.mass_heal` | Mass Heal | `spell.mass-heal` | available |
| spell | `spell.mass_healing_word` | Mass Healing Word | `spell.mass-healing-word` | available |
| spell | `spell.mirror_image` | Mirror Image | `spell.mirror-image` | available |
| spell | `spell.misty_step` | Misty Step | `spell.misty-step` | available |
| spell | `spell.poison_spray` | Poison Spray | `spell.poison-spray` | available |
| spell | `spell.power_word_kill` | Power Word Kill | `spell.power-word-kill` | available |
| spell | `spell.power_word_stun` | Power Word Stun | `spell.power-word-stun` | available |
| spell | `spell.prayer_of_healing` | Prayer of Healing | `spell.prayer-of-healing` | available |
| spell | `spell.prismatic_spray` | Prismatic Spray | `spell.prismatic-spray` | available |
| spell | `spell.produce_flame` | Produce Flame | `spell.produce_flame` | missing file |
| spell | `spell.protection_from_energy` | Protection from Energy | `spell.protection-from-energy` | available |
| spell | `spell.protection_from_poison` | Protection from Poison | `spell.protection-from-poison` | available |
| spell | `spell.ray_of_frost` | Ray of Frost | `spell.ray-of-frost` | available |
| spell | `spell.regenerate` | Regenerate | `spell.regenerate` | available |
| spell | `spell.remove_curse` | Remove Curse | `spell.remove-curse` | available |
| spell | `spell.resistance` | Resistance | `spell.resistance` | available |
| spell | `spell.sacred_flame` | Sacred Flame | `spell.sacred-flame` | available |
| spell | `spell.sanctuary` | Sanctuary | `spell.sanctuary` | available |
| spell | `spell.scorching_ray` | Scorching Ray | `spell.scorching-ray` | available |
| spell | `spell.see_invisibility` | See Invisibility | `spell.see-invisibility` | available |
| spell | `spell.shatter` | Shatter | `spell.shatter` | available |
| spell | `spell.shield` | Shield | `reaction.shield` | available |
| spell | `spell.shield_of_faith` | Shield of Faith | `spell.shield-of-faith` | available |
| spell | `spell.shillelagh` | Shillelagh | `spell.shillelagh` | missing file |
| spell | `spell.shocking_grasp` | Shocking Grasp | `spell.shocking-grasp` | available |
| spell | `spell.silence` | Silence | `spell.silence` | available |
| spell | `spell.sleep` | Sleep | `spell.sleep` | available |
| spell | `spell.sleet_storm` | Sleet Storm | `spell.sleet-storm` | available |
| spell | `spell.slow` | Slow | `spell.slow` | available |
| spell | `spell.spike_growth` | Spike Growth | `spell.spike-growth` | available |
| spell | `spell.spirit_guardians` | Spirit Guardians | `spell.spirit-guardians` | available |
| spell | `spell.stinking_cloud` | Stinking Cloud | `spell.stinking-cloud` | available |
| spell | `spell.stoneskin` | Stoneskin | `spell.stoneskin` | available |
| spell | `spell.sunbeam` | Sunbeam | `spell.sunbeam` | available |
| spell | `spell.sunburst` | Sunburst | `spell.sunburst` | available |
| spell | `spell.telekinesis` | Telekinesis | `spell.telekinesis` | available |
| spell | `spell.thaumaturgy` | Thaumaturgy | `spell.thaumaturgy` | available |
| spell | `spell.thunderwave` | Thunderwave | `spell.thunderwave` | available |
| spell | `spell.true_seeing` | True Seeing | `spell.true-seeing` | available |
| spell | `spell.true_strike` | True Strike | `spell.true-strike` | available |
| spell | `spell.wall_of_fire` | Wall of Fire | `spell.wall_of_fire` | missing file |
| spell | `spell.wall_of_force` | Wall of Force | `spell.wall_of_force` | missing file |
| spell | `spell.wall_of_ice` | Wall of Ice | `spell.wall_of_ice` | missing file |
| spell | `spell.wall_of_stone` | Wall of Stone | `spell.wall_of_stone` | missing file |
| spell | `spell.wall_of_thorns` | Wall of Thorns | `spell.wall_of_thorns` | missing file |
| spell | `spell.web` | Web | `spell.web` | available |
| spell | `spell.wind_wall` | Wind Wall | `spell.wind_wall` | missing file |
| trait | `trait.brave` | Brave | `condition.dnd-monsters-traits-conditionalsaveadvantagefeature` | available |
| trait | `trait.brute` | Brute | `condition.dnd-monsters-traits-bonusdamagefeature` | available |
| trait | `trait.dark_devotion` | Dark Devotion | `condition.dnd-monsters-traits-conditionalsaveadvantagefeature` | available |
| trait | `trait.dire_wolf_bite_prone` | Bite Prone Rider | `condition.dnd-monsters-traits-hitsaveriderfeature` | available |
| trait | `trait.divine_eminence_active` | Divine Eminence Active | `condition.dnd-monsters-traits-divineeminenceactive` | available |
| trait | `trait.ghoul_claws_paralysis` | Ghoul Claws Paralysis | `condition.dnd-monsters-traits-ghoulclawsparalysisfeature` | available |
| trait | `trait.ghoul_paralysis` | Ghoul Paralysis | `condition.dnd-monsters-traits-ghoulparalysiseffect` | available |
| trait | `trait.innate_flight` | Innate Flight | `trait.innate_flight` | missing file |
| trait | `trait.keen_hearing_and_sight` | Keen Hearing and Sight | `condition.dnd-monsters-traits-keenperceptionfeature` | available |
| trait | `trait.keen_hearing_and_smell` | Keen Hearing and Smell | `condition.dnd-monsters-traits-keenperceptionfeature` | available |
| trait | `trait.leadership_aura` | Leadership Aura | `condition.dnd-monsters-traits-leadershipaura` | available |
| trait | `trait.magic_resistance` | Magic Resistance | `trait.magic_resistance` | missing file |
| trait | `trait.martial_advantage` | Martial Advantage | `condition.dnd-monsters-traits-bonusdamagefeature` | available |
| trait | `trait.pack_tactics` | Pack Tactics | `condition.dnd-monsters-traits-packtacticsfeature` | available |
| trait | `trait.parry` | Parry | `condition.dnd-monsters-traits-parryfeature` | available |
| trait | `trait.rampage` | Rampage | `condition.dnd-monsters-traits-rampagefeature` | available |
| trait | `trait.rampage_available` | Rampage Available | `condition.dnd-monsters-traits-rampageavailable` | available |
| trait | `trait.sneak_attack` | Sneak Attack | `condition.dnd-monsters-traits-bonusdamagefeature` | available |
| trait | `trait.sunlight_sensitivity` | Sunlight Sensitivity | `condition.dnd-monsters-traits-sunlightsensitivityfeature` | available |
| trait | `trait.surprise_attack` | Surprise Attack | `condition.dnd-monsters-traits-bonusdamagefeature` | available |
| trait | `trait.undead_fortitude` | Undead Fortitude | `condition.dnd-monsters-traits-undeadfortitudefeature` | available |
| trait | `trait.wolf_bite_prone` | Bite Prone Rider | `condition.dnd-monsters-traits-hitsaveriderfeature` | available |
| action | `action.attack` | Attack | `None` | no mapping |
| action | `action.dash` | Dash | `action.dash` | available |
| action | `action.disengage` | Disengage | `action.disengage` | available |
| action | `action.dodge` | Dodge | `action.dodge` | available |
| action | `action.drop_concentration` | Drop Concentration | `action.drop-concentration` | available |
| action | `action.hide` | Hide | `action.hide` | available |
| action | `action.jump` | Jump | `action.jump` | available |
| action | `action.move` | Move | `action.move` | available |
| action | `action.pick_up` | Pick Up | `action.pick-up` | available |
| action | `action.shake_awake` | Shake Awake | `action.shake-awake` | available |
| action | `action.shove` | Shove | `action.shove` | available |
| action | `action.swim` | Swim | `action.swim` | available |
| reaction | `reaction.opportunity_attack` | Opportunity Attack | `reaction.opportunity-attack-handler` | available |

## Remaining non-button conditions

| ID | Icon | Status |
|---|---|---|
| `condition.consumable.weapon_coat.basic_poison` | `condition.consumable.weapon_coat.basic_poison` | missing file |
| `condition.environment.jaw_restrained` | `condition.environment.jaw_restrained` | missing file |
| `condition.summon_control` | `condition.summon_control` | missing file |
| `condition.summoned` | `condition.summoned` | missing file |
| `condition.tile.residue` | `None` | no mapping |
| `condition.spell.barkskin` | `condition.spell.barkskin` | missing file |
| `condition.spell.eyebite.casting` | `condition.spell.eyebite.casting` | missing file |
| `condition.spell.fire_shield` | `condition.spell.fire_shield` | missing file |
| `condition.spell.fly` | `condition.spell.fly` | missing file |
| `condition.spell.harm` | `condition.spell.harm` | missing file |
| `condition.spell.longstrider` | `condition.spell.longstrider` | missing file |
| `condition.spell.shillelagh` | `condition.spell.shillelagh` | missing file |
| `condition.spell.sunbeam.blinded` | `condition.spell.sunbeam.blinded` | missing file |
| `condition.spell.sunbeam` | `condition.spell.sunbeam` | missing file |
| `condition.spell.wall_of_fire.zone` | `condition.spell.wall_of_fire.zone` | missing file |
| `condition.spell.wall_of_force.zone` | `condition.spell.wall_of_force.zone` | missing file |
| `condition.spell.wall_of_ice.frigid_air` | `condition.spell.wall_of_ice.frigid_air` | missing file |
| `condition.spell.wall_of_ice.zone` | `condition.spell.wall_of_ice.zone` | missing file |
| `condition.spell.wall_of_stone.zone` | `condition.spell.wall_of_stone.zone` | missing file |
| `condition.spell.wall_of_thorns.zone` | `condition.spell.wall_of_thorns.zone` | missing file |
| `condition.spell.wind_wall.zone` | `condition.spell.wind_wall.zone` | missing file |
| `condition.wight.life_drain` | `condition.wight.life_drain` | missing file |

These are HUD/sheet/log condition icons. They are independent from existing overhead Godot condition marker VFX; missing HUD art does not imply missing in-world markers. Do not replace or rotate existing effect layers.

## Reproduction and scope

Read-only scripts and compact results remain in `.runtime/ui-study-20261005/audit_icons.py`, `audit_grants.py`, `icon-coverage.json`, `grant-coverage.json`. Stored templates and default creature factories cover all source providers in these denominators; future authored providers must enter the same audit. External fixture definitions are reported but excluded from shipping missing-art requests. No full effective catalog or binary assets are added to public Git.
