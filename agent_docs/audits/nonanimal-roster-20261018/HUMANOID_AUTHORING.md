# Native Orc / HD Enemy / Barbarian / Character authoring

October 18, 2026. Authoring authorized by the current human instruction. This
implements all **41 previously unmapped rows**: eleven Orcs, twelve HD Enemy,
nine Barbarian and nine Character. They are ordinary native NPC recipes in
`dnd/monsters/roster_humanoids.py`, with twenty-one typed Multiattack data
configurations, admitted through the existing builtin inventory. No PC class,
progression, new combat executor, art import or client certification is included.

## Source and selected adaptations

The individual cards and image-only gear review dated October1 supply source
identity and observations. The higher-tier Enemy draft supplies Gladiator,
Assassin, Knight, Mage, Archmage and authored E01 foundations. The complete
October2 ability dispositions, item simplification/crosswalk, October3 cleanup
and October4 acceptance supersede earlier optional signatures. Numeric source
CR is a reference only; all changed encounter CR remains **uncalibrated**.

- Source saves, skills/expertise, languages, HP, hit dice, movement and explicit
  creature types are native data. Languages otherwise chosen by the source
  blocks are authored explicitly below. Vendor Golem and DeathKnight remain
  Humanoid. Gatebreaker retains the selected Large Giant Ogre foundation.
- Gold-knuckle Breaker and Dockwall select the **level11 training tier damage
  reference: one d8 + STR4**, three ordinary punches. This is neither a Monk
  class nor CR-to-level conversion. Bruiser wears Half plate for AC17; Brawler
  wears ordinary clothes for AC12. Neither has Brute, weapon Parry or Shield
  Bash. No CON/WIS AC formula or cosmetic Force damage is inferred.
- Assassins retain Assassinate, Evasion, poison resistance and once-per-turn
  **4d6** Sneak Attack. Each owns three Assassin Poison doses, represented by
  one native finite stack; none starts coated for free. Application costs an
  action and consumes one dose. Current coating lifetime remains ten rounds;
  the actual weapon owns the DC15 CON/7d6 poison-half rider through transfer.
  Blue Quarrel and Far-Eye have actual Musket items and one ordinary gunshot
  per action. Ammunition counting, Loading and firearm proficiency stay deferred.
- Venom Sword Ritualist has the selected Silver Longsword and two finite Basic
  Poison doses. Basic Poison remains DC10 CON/1d4 on failure, no Poisoned.
  The material vocabulary represents metals collectively; silvering is an
  explicit item identity/tag, without a newly implemented silvered-hit bypass.
- Cinderplate has a real Ember Greatsword (+1d6 Fire, no enhancement bonus),
  source Brute and one innate level1 Burning Hands per long rest using CHA.
  No Cinder Sweep or passive actor-wide fire rider is added.
- Violet Oathbreaker has the later selected **Greater Psychic Longsword**
  (+3 attack/damage and +3d6 Psychic), alongside source Brute. The weapon owns
  its psychic property. Parry replaces Void Guard; no damage return is added.
- Gateplate retains selected Protection as well as Parry; they spend the same
  reaction. Gateplate and Violet Oathbreaker may replace one of their three
  melee attacks with the real held-shield Bash. The size gate applies only to
  its saved Prone rider. No fourth attack is granted by that substitution.
- Paired Multiattacks use the current equipment modifier callback for the
  source offhand ability bonus. Existing separately paid native offhand attack
  budgets remain available when ordinary two-weapon eligibility permits them;
  this is an explicit engine adaptation rather than claiming source prohibition
  of every possible separately paid third attack. No template-removal policy or
  new attack-budget subsystem is introduced.
- The accepted specialist pack choices are actual transferable possessions:
  Farshot has Wayfarer's Pack, Windmark has Ember Quiver, and Blue Quarrel has
  Warden's Pack in the observed canister position. Their item-owned native
  charges/casts are reused. Ordinary quivers elsewhere add no new ammo system.
- Arcane Sentinel uses its authored Elemental body: intrinsic nonpickable
  AC16 natural armor, poison damage immunity, Poisoned/Exhaustion immunity and
  nonmagical-attack B/P/S resistance. It makes two intrinsic Slams +6, 2d8+3
  Bludgeoning. The conflicting bolt/cone/burst is deferred. Its source
  understands Common without speech; the current language owner records
  knowledge, not a separate understanding-only or speech-capability restriction.
- Ordinary selected weapons replace the older optional +1 suggestions unless
  a later accepted Ember/Psychic property selects a specific item above.
  Driving Blow uses independently selected standard Shove; custom reaction
  denial, pinning, Brace, Riposte and Storm Arrow remain absent. Character9
  owns an ordinary Longbow, quiver and Half plate.

## Canonical Orc01 reconciliation

The existing `content.srd_5_1_cc:creature:creature.orc@1` is preserved unchanged
and receives no duplicate declaration. Its current source kit is Hide,
Greataxe and thrown Javelin, with HP15 and Aggressive. The later Orc01 image
review establishes Scimitar plus Shield and withdraws the old bow reading.
That mismatch is recorded explicitly: the preserved canonical recipe still
uses its source kit; it is not silently converted to Iron Cask or counted among
these forty-one new variants. No Disrupting Shot is authored for Orc01.

## Native spell selections and explicit omissions

Every Mage keeps all supported selected source spells and native Shield and
Counterspell reactions. Frostmane, Brassbrow and Azure Currentbinder select
Web in place of source Suggestion. Golden-orbit selects Burning Hands in
place of Detect Magic. Hex Sovereign selects Slow in place of Fly. Other
source spells are retained where registered. Utility spell omissions are
listed below, rather than represented as cast animations or invented actions.

Magister Nine keeps all supported Archmage spells: Fire Bolt, Light, Shocking
Grasp, Mage Armor, Magic Missile, Mirror Image, Misty Step, Fly, Lightning Bolt,
Banishment, Fire Shield, Stoneskin, Cone of Cold, Wall of Force, Globe of
Invulnerability and Counterspell, with 4/3/3/3/3/1/1/1/1 slots and INT casting
at level18 (DC17/+9). Native Invisibility is at will from its real innate
INT source. Magic Resistance applies only to magical saves and spell damage
resistance only to actual spell damage. Mage Armor and Stoneskin are actual
casts; neither is an initial passive defense. Source Archmage has no Shield
prepared, so no Shield reaction is granted. Arcana/History use expertise for
+13, saves INT+9/WIS+6 and six authored languages.

Mage unsupported utility spells: detect_magic, mage_hand, prestidigitation, suggestion.

Archmage unsupported spells: mage_hand, prestidigitation, detect_magic, identify, detect_thoughts, scrying, teleport, mind_blank, time_stop, disguise_self.

Sun-ring retains source Druid level4 WIS casting and 4/3 slots, with
Produce Flame, Shillelagh, Longstrider, Thunderwave and Barkskin. Druidcraft,
Speak with Animals and Animal Messenger are unsupported. Entangle has a
runtime implementation but lacks current canonical catalog admission; it is
explicitly omitted here by the bounded authoring decision rather than silently
expanding the spell catalog. No Sunburst or new Fireball is granted.

Gilded Ward keeps Knight Brave/Leadership/Parry and Protection plus Divine
Eminence: a bonus action spends its one first-level slot per long rest and
adds the existing 3d6 Radiant melee-weapon effect until turn end. No free
Dawn Strike or PC Paladin progression is added.

## Exact selected native kits

All non-intrinsic starter gear is optional under structure-and-intrinsics-only
materialization. Body attacks/armor remain. The table is the passive authoring
selection; it does not claim sprite or client acceptance.

| Source row | Native recipe ID | Foundation / HP | Exact possessions and placement | Multiattack |
| --- | --- | --- | --- | --- |
| orcs_goblins/Orc 02 | creature.orc_rededge | Orc; 15 HP | weapon.battleaxe [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 03 | creature.orc_yellowtusk | Orc; 15 HP | weapon.battleaxe [MELEE_MAIN]; apparel.common_clothes [Body]; apparel.iron_helmet [Head] | ordinary selected Attack / cast |
| orcs_goblins/Orc 09 | creature.orc_redblade | Orc; 15 HP | weapon.shortsword [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 11 | creature.orc_greenfang | Orc; 15 HP | weapon.battleaxe [MELEE_MAIN]; shield.wooden [MELEE_OFF]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 04 | creature.orc_bristlejaw | Orc; 15 HP | weapon.club [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 05 | creature.orc_longspike | Orc; 15 HP | weapon.shortbow [RANGED_MAIN]; gear.quiver [Backpack]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 06 | creature.orc_frostmane | Mage; 40 HP | weapon.quarterstaff [MELEE_MAIN]; apparel.robes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 07 | creature.orc_brassbrow | Mage; 40 HP | apparel.robes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 08 | creature.orc_blackplate | Orc; 15 HP | weapon.scimitar [MELEE_MAIN]; shield.shield [MELEE_OFF]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| orcs_goblins/Orc 10 | creature.orc_mudrunner | Orc; 15 HP | weapon.mace [MELEE_MAIN]; weapon.handaxe [MELEE_OFF]; apparel.common_clothes [Body] | MELEE_MAIN ×1, MELEE_OFF ×1 |
| orcs_goblins/Orc 12 | creature.orc_ironjaw | Orc; 15 HP | weapon.scimitar [MELEE_MAIN]; weapon.scimitar [MELEE_OFF]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| enemy/1Hammer | creature.enemy_bellringer | Gladiator; 112 HP | weapon.maul [MELEE_MAIN]; armor.half_plate [Body]; apparel.iron_helmet [Head]; apparel.gauntlets [Hands] | MELEE_MAIN ×3 |
| enemy/2Shooter | creature.enemy_blue_quarrel | Assassin; 78 HP | weapon.musket [RANGED_MAIN]; armor.half_plate [Body]; gear.warden_pack [Backpack]; apparel.iron_helmet [Head]; consumable.weapon_coat.assassin_poison ×3 [inventory] | ordinary selected Attack / cast |
| enemy/3Footsoldier | creature.enemy_gateplate | Gladiator; 112 HP | weapon.longsword [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.plate [Body]; apparel.iron_helmet [Head] | MELEE_MAIN ×3 |
| enemy/4Assassin | creature.enemy_blue_twinblade | Assassin; 78 HP | weapon.shortsword [MELEE_MAIN]; weapon.shortsword [MELEE_OFF]; armor.studded_leather [Body]; apparel.cloth_hood [Head]; consumable.weapon_coat.assassin_poison ×3 [inventory] | MELEE_MAIN ×1, MELEE_OFF ×1 |
| enemy/5Bruiser | creature.enemy_gold_knuckle | Gladiator; authored level11 martial-die reference; 112 HP | armor.half_plate [Body]; apparel.gauntlets [Hands] | MELEE_MAIN ×3 |
| enemy/6Crusader | creature.enemy_reliquary | Knight; 52 HP | weapon.greatsword [MELEE_MAIN]; armor.plate [Body]; apparel.cloak [Cloak] | MELEE_MAIN ×2 |
| enemy/7Sniper | creature.enemy_far_eye | Assassin; 78 HP | weapon.musket [RANGED_MAIN]; armor.studded_leather [Body]; apparel.cloth_hood [Head]; consumable.weapon_coat.assassin_poison ×3 [inventory] | ordinary selected Attack / cast |
| enemy/8Brawler | creature.enemy_dockwall | Gladiator; authored level11 martial-die reference; 112 HP | apparel.common_clothes [Body] | MELEE_MAIN ×3 |
| enemy/9Commander | creature.enemy_magister_nine | Archmage; 99 HP | apparel.common_clothes [Body]; apparel.cloth_hood [Head] | ordinary selected Attack / cast |
| enemy/10Caster | creature.enemy_pale_ember | Mage; 40 HP | weapon.quarterstaff [MELEE_MAIN]; apparel.robes [Body] | ordinary selected Attack / cast |
| enemy/11Arcane elemental | creature.enemy_arcane_sentinel | Authored Arcane Sentinel E01; 119 HP | weapon.creature.arcane_sentinel_slam [MELEE_MAIN, intrinsic]; armor.creature.arcane_sentinel_natural [Body, intrinsic] | MELEE_MAIN ×2 |
| enemy/12Guard | creature.enemy_bronze_watch | Gladiator; 112 HP | weapon.spear [MELEE_MAIN]; armor.half_plate [Body]; apparel.iron_helmet [Head] | MELEE_MAIN ×3 |
| barbarian/1Ogre | creature.barbarian_gatebreaker | Ogre; 59 HP | weapon.maul [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| barbarian/2Golem | creature.barbarian_cinderplate | Gladiator; 112 HP | weapon.roster.ember_greatsword [MELEE_MAIN]; armor.plate [Body]; apparel.iron_helmet [Head] | MELEE_MAIN ×3 |
| barbarian/3Nomad | creature.barbarian_saffron_ward | Bandit Captain; 65 HP | weapon.battleaxe [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.scale_mail [Body] | MELEE_MAIN ×2 |
| barbarian/4Berserker | creature.barbarian_red_rage | Veteran; 58 HP | weapon.longsword [MELEE_MAIN]; weapon.shortsword [MELEE_OFF]; apparel.common_clothes [Body] | MELEE_MAIN ×2, MELEE_OFF ×1 |
| barbarian/5BarbArcher | creature.barbarian_farshot | Veteran; 58 HP | weapon.longbow [RANGED_MAIN]; gear.wayfarer_pack [Backpack]; apparel.common_clothes [Body] | RANGED_MAIN ×2 |
| barbarian/6Barbarian | creature.barbarian_stonejaw | Berserker; 67 HP | weapon.greataxe [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| barbarian/7BowMan | creature.barbarian_windmark | Veteran; 58 HP | weapon.longbow [RANGED_MAIN]; gear.ember_quiver [Backpack]; armor.half_plate [Body]; apparel.iron_helmet [Head] | RANGED_MAIN ×2 |
| barbarian/8Witchdoctor | creature.barbarian_venom_ritualist | Bandit Captain; 65 HP | weapon.roster.silver_longsword [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.leather [Body]; apparel.cloth_hood [Head]; consumable.weapon_coat.basic_poison ×2 [inventory] | MELEE_MAIN ×2 |
| barbarian/9Shaman | creature.barbarian_sun_ring | Druid; 27 HP | weapon.quarterstaff [MELEE_MAIN]; apparel.common_clothes [Body] | ordinary selected Attack / cast |
| character/1Knight | creature.character_whiteplate | Knight; 52 HP | weapon.longsword [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.plate [Body]; apparel.iron_helmet [Head] | MELEE_MAIN ×2 |
| character/2Archer | creature.character_briarline | Veteran; 58 HP | weapon.longbow [RANGED_MAIN]; gear.quiver [Backpack]; apparel.common_clothes [Body] | RANGED_MAIN ×2 |
| character/3Wizard | creature.character_golden_orbit | Mage; 40 HP | apparel.robes [Body] | ordinary selected Attack / cast |
| character/4Paladin | creature.character_gilded_ward | Knight; 52 HP | weapon.mace [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.plate [Body] | MELEE_MAIN ×2 |
| character/5CamoArcher | creature.character_white_streak | Assassin; 78 HP | weapon.longbow [RANGED_MAIN]; gear.quiver [Backpack]; armor.studded_leather [Body]; apparel.cloth_hood [Head]; consumable.weapon_coat.assassin_poison ×3 [inventory] | RANGED_MAIN ×2 |
| character/6Mage | creature.character_azure_current | Mage; 40 HP | apparel.robes [Body] | ordinary selected Attack / cast |
| character/7DeathKnight | creature.character_violet_oathbreaker | Gladiator; 112 HP | weapon.roster.psychic_longsword_greater [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.plate [Body]; apparel.iron_helmet [Head] | MELEE_MAIN ×3 |
| character/8DarkLord | creature.character_hex_sovereign | Mage; 40 HP | apparel.robes [Body] | ordinary selected Attack / cast |
| character/9Longbow | creature.character_blue_spark | Veteran; 58 HP | weapon.longbow [RANGED_MAIN]; gear.quiver [Backpack]; armor.half_plate [Body] | RANGED_MAIN ×2 |

## Source foundation facts

Ability scores are STR/DEX/CON/INT/WIS/CHA. All listed saves and skills use the
source PB; expertise is called out explicitly. Weapon bonuses come from the
actual selected weapon and current ability owner, never the vendor name.

| Foundation | Abilities | PB / hit dice | Saves | Skills / expertise | Languages |
| --- | --- | --- | --- | --- | --- |
| Orc | 16/12/16/7/11/10 | +2; 2d8 | none | intimidation; expertise none | language.common, language.orc |
| Mage | 9/14/11/17/12/11 | +3; 9d8 | intelligence, wisdom | arcana, history; expertise none | language.common, language.elvish, language.draconic, language.orc |
| Gladiator | 18/15/16/10/12/15 | +3; 15d8 | strength, dexterity, constitution | athletics, intimidation; expertise athletics | language.common |
| Assassin | 11/16/14/13/11/10 | +3; 12d8 | dexterity, intelligence | acrobatics, deception, perception, stealth; expertise stealth | language.common, language.elvish, language.thieves_cant |
| Gladiator; authored level11 martial-die reference | 18/15/16/10/12/15 | +3; 15d8 | strength, dexterity, constitution | athletics, intimidation; expertise athletics | language.common |
| Knight | 16/11/14/11/11/15 | +2; 8d8 | constitution, wisdom | none; expertise none | language.common |
| Archmage | 10/14/12/20/15/16 | +4; 18d8 | intelligence, wisdom | arcana, history; expertise arcana, history | language.common, language.elvish, language.draconic, language.dwarvish, language.infernal, language.celestial |
| Mage | 9/14/11/17/12/11 | +3; 9d8 | intelligence, wisdom | arcana, history; expertise none | language.common, language.elvish, language.draconic, language.dwarvish |
| Authored Arcane Sentinel E01 | 16/14/18/10/12/8 | +3; 14d8 | constitution, wisdom | perception; expertise none | language.common |
| Ogre | 19/8/16/5/7/7 | +2; 7d10 | none | none; expertise none | language.common, language.giant |
| Bandit Captain | 15/16/14/14/11/14 | +2; 10d8 | strength, dexterity, wisdom | athletics, deception; expertise none | language.common, language.goblin |
| Veteran | 16/13/14/10/11/10 | +2; 9d8 | none | athletics, perception; expertise none | language.common |
| Berserker | 16/12/17/9/11/9 | +2; 9d8 | none | none; expertise none | language.common |
| Druid | 10/12/13/12/15/11 | +2; 5d8 | none | medicine, nature, perception; expertise none | language.common, language.elvish, language.druidic |

## Validation

`tests/engine/test_remaining_humanoid_roster.py` checks all forty-one recipes
through normal bootstrap/materialization, both possession modes, exact stats
and type, representative real attacks and Multiattacks, finite supply use and
transfer, caster lists/scaling, actual slot/innate costs, shared reactions,
specialist backpack ownership and omitted Storm Arrow. The constructor test
matrix passed before additional scoped regression validation; final commands
and results are recorded below.

Final scoped command (task worktree; isolated existing environment):

```sh
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/npc-mechanics-venv uv run --no-sync python -m pytest -q tests/engine/test_remaining_humanoid_roster.py tests/engine/test_direct_item_runtime.py tests/engine/test_assassin_poison_items.py tests/engine/test_goblin_roster.py tests/architecture/test_creatable_models.py
```

Result: **193 passed in 13.44s**, including 115 family authoring checks. The
real-shield substitution is exercised from both authored shield kits; three
attacks include one real Shield Bash, never an additional fourth attack.
`git diff --check` for the owned source/test changes reports no whitespace errors.
This scoped evidence does not replace the parent task's final broad regression,
source reconciliation, client checks or encounter balance work.
