# Native undead and fantasy zombie authoring

2026-10-18. Eight new undead champions/casters and all46 admitted zombie designs
are ordinary registered creature recipes. Skeleton Archer remains its existing
canonical identity. No held or modern zombie receives a new recipe.

The October1 individual cards and image-only gear rules revision supply source
identity, equipment and foundations. The October2 dispositions and October3–4
cleanup/acceptance supersede obsolete signatures. The October18 plan and human
Monk/poison corrections govern this authoring batch. The code contains passive
kit data and native composition functions; this document is audit evidence,
not another runtime roster. Threat/CR remains uncalibrated.

## Eight undead kits

All eight explicitly use Undead type, Poison immunity and
Poisoned/Exhaustion immunity. These are authored undead adaptations of the stated
foundations, not PC class progressions. Wights also have darkvision60, Necrotic resistance,
Sunlight Sensitivity and an actual Life Drain action. Silver-qualified physical
resistance is omitted because the native attack context has no silver provenance;
it is not broadened to resistance against every nonmagical attack.

- Bone-wheel Cleaver retains Gladiator HP112, STR18, DEX15, CON16, INT10,
  WIS12, CHA15, PB3, STR/DEX/CON saves, Athletics expertise and Intimidation.
  It has AC12, Brave, Brute, Greatsword3d6+4 per hit, three hits/action and
  weapon Parry+3. Brute follows the actual equipped weapon.
- Ash-crown, Flareblade, Pikeward and Black Fletch use the Wight foundation:
  HP45, STR15, DEX14, CON16, INT10, WIS13, CHA15, PB2, Stealth/Perception.
  Ash-crown equips Ember Longsword, Shield and Plate (AC20); Flareblade equips
  Ember Longsword, Shield and Half plate (AC19) with Parry+2. Pikeward has
  Spear/Shield and no armor (AC14), with real Protection. Each makes two
  selected melee hits and can replace one with existing Life Drain. Ember's
  elemental packet stays on its weapon; Life Drain does not inherit it.
  Black Fletch has Shortbow/Quiver, no armor (AC12), two bow hits and a separate
  melee Life Drain action. Arrows never carry Life Drain.
- Red-crescent uses Berserker HP67, STR16, DEX12, CON17, INT9, WIS11, CHA9,
  PB2, AC11, Greataxe and Reckless Attack. Burning Hands is one owned CHA cast
  at rank1/day, level1; it consumes its actual daily resource and recovers
  only on long rest. No free weapon fire rider is inferred.
- Ossuary Hierophant uses the adapted Archmage: HP99, AC12, STR10, DEX14,
  CON12, INT20, WIS15, CHA16, PB4, INT/WIS saves, Arcana/History expertise
  (+13), Magic Resistance and Spell Damage Resistance. Its caster level18
  slots are4/3/3/3/3/1/1/1/1. It knows Fire Bolt, Light, Shocking Grasp,
  Mage Armor, Magic Missile, Mirror Image, Misty Step, Fly, Lightning Bolt,
  Banishment, Fire Shield, Stoneskin, Cone of Cold, Wall of Force and Globe
  of Invulnerability, with Counterspell. It also has owned at-will INT
  Invisibility. No automatic prebuff, Shield or staff is added. Its six chosen
  languages are Common, Elvish, Dwarvish, Draconic, Infernal and Celestial.
- Ember Oracle uses the adapted Mage: HP40, AC12, STR9, DEX14, CON11,
  INT17, WIS12, CHA11, PB3, INT/WIS saves and Arcana/History proficiency.
  Caster level9 slots are4/3/3/3/1. It knows Fire Bolt, Light, Mage Armor,
  Magic Missile, Misty Step, Fireball, Fly, Greater Invisibility, Ice Storm
  and Cone of Cold, with actual Shield/Counterspell reactions. It carries
  no staff. Its chosen languages are Common, Elvish, Draconic and Dwarvish.

Unsupported Mage spells omitted: Detect Magic, Mage Hand, Prestidigitation and
Suggestion. Unsupported Archmage spells omitted: Mage Hand, Prestidigitation,
Detect Magic, Identify, Detect Thoughts, Scrying, Teleport, Mind Blank,
Time Stop and Disguise Self. Controlled-zombie creation, Animate Dead, Lich
phylacteries, Rejuvenation, Paralyzing Touch, orbit powers and old custom
cross-cuts/brace/riposte are omitted. Shared spells retain current adaptations.

Undead5Archer keeps `content.neurodragon:creature:creature.skeleton_archer@1`.
The old Gravesight Wight proposal is omitted for that row. It does not replace
or duplicate the canonical skeleton. Black Fletch is the distinct new Wight.

## Forty-six zombie kits

Ordinary bodies: Medium Undead, HP22 (3d8), AC8, PB2, STR13, DEX6, CON16,
INT3, WIS6, CHA5, speed20, darkvision60, WIS save proficiency, Poison immunity,
Poisoned immunity, native Undead Fortitude and Slam+3 for1d6+1 bludgeoning.
Only HD Hulk1/Hulk2/Monster3 use Large Ogre Zombie bodies: HP85 (9d10),
STR19, DEX6, CON18, INT3, WIS6, CHA5, speed30 and Slam+6 for2d8+4.
The Slam is anatomy, not an equipped fake item. Its authored dice already
include native size; temporary Enlarge adds only growth above that size.

Top-down Decay01/04 move15. Athletics proficiency belongs only to HD Female5,
HD Male9, top-down09, Decay05 and Swamp05. Swamp01 actually holds a Longsword;
Swamp09 holds Shortsword/Dagger. These remain normal weapon attacks; neither
gains a free Multiattack. All others have no invented carried weapon.

The seven new former Radioactive candidates have explicit ordinary Zombie
kits: Fallow One/Two/Three and Marshglass One/Two/Three/Four. Green bodies
confer no radiation, Poison damage, Acid or casting. Clothing remains an
appearance choice with no hidden armor benefit. Grapple/drag, brace, recharge
lurch, aperture rules and understanding-only language simulation remain omitted.
The eight clothing holds and24 modern exclusions stay visible in the ledger.

## Exact source-to-native rows

| Source | Selected name | Native creature ID | Selected kit / exceptions |
| --- | --- | --- | --- |
| undead/1Brute | Bone-wheel Cleaver | creature.undead_bonewheel | HP112; weapon.greatsword [MELEE_MAIN]; MELEE_MAIN ×3 |
| undead/2DeathLord | Ash-crown Revenant | creature.undead_ash_crown | HP45; weapon.roster.ember_longsword [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.plate [Body]; MELEE_MAIN ×2 |
| undead/3DarkKnight | Flareblade Grave Sentinel | creature.undead_flareblade | HP45; weapon.roster.ember_longsword [MELEE_MAIN]; shield.shield [MELEE_OFF]; armor.half_plate [Body]; MELEE_MAIN ×2 |
| undead/4Berserker | Red-crescent Ravager | creature.undead_red_crescent | HP67; weapon.greataxe [MELEE_MAIN]; ordinary Attack / selected cast |
| undead/6Warrior | Pikeward | creature.undead_pikeward | HP45; weapon.spear [MELEE_MAIN]; shield.shield [MELEE_OFF]; MELEE_MAIN ×2 |
| undead/7DarkArcher | The Black Fletch | creature.undead_black_fletch | HP45; weapon.shortbow [RANGED_MAIN]; gear.quiver [Backpack]; RANGED_MAIN ×2 |
| undead/8Necromancer | Violet Ossuary Hierophant | creature.undead_ossuary_hierophant | HP99; No carried equipment; ordinary Attack / selected cast |
| undead/9Wizard | Antlered Ember Oracle | creature.undead_ember_oracle | HP40; No carried equipment; ordinary Attack / selected cast |
| hdz/ZombieFemale1 | Marigold | creature.zombie_hd_female_1 | Zombie |
| hdz/ZombieFemale2 | Ash-Blue June | creature.zombie_hd_female_2 | Zombie |
| hdz/ZombieFemale3 | Copper Jane | creature.zombie_hd_female_3 | Zombie |
| hdz/ZombieFemale4 | Fen Green | creature.zombie_hd_female_4 | Zombie |
| hdz/ZombieFemale5 | Roseglass | creature.zombie_hd_female_5 | Zombie; Athletics proficiency |
| hdz/ZombieFemale6 | Night Shift | creature.zombie_hd_female_6 | Zombie |
| hdz/ZombieFemale7 | Deep Teal | creature.zombie_hd_female_7 | Zombie |
| hdz/ZombieHulk1 | Greenbulge | creature.zombie_hd_hulk_1 | Ogre Zombie |
| hdz/ZombieHulk2 | White Knuckle | creature.zombie_hd_hulk_2 | Ogre Zombie |
| hdz/ZombieMale1 | Olive Trousers | creature.zombie_hd_male_1 | Zombie |
| hdz/ZombieMale2 | The White Shirt | creature.zombie_hd_male_2 | Zombie |
| hdz/ZombieMale3 | Blue Sleeve | creature.zombie_hd_male_3 | Zombie |
| hdz/ZombieMale6 | Nightcoat | creature.zombie_hd_male_6 | Zombie |
| hdz/ZombieMale7 | Green Vest | creature.zombie_hd_male_7 | Zombie |
| hdz/ZombieMale8 | Red Thread | creature.zombie_hd_male_8 | Zombie |
| hdz/ZombieMale9 | Rust Collar | creature.zombie_hd_male_9 | Zombie; Athletics proficiency |
| hdz/ZombieMonster1 | The Narrow One | creature.zombie_hd_monster_1 | Zombie |
| hdz/ZombieMonster2 | Red Suture | creature.zombie_hd_monster_2 | Zombie |
| hdz/ZombieMonster3 | Heavy Pale | creature.zombie_hd_monster_3 | Ogre Zombie |
| hdz/ZombieRadioactive1 | Fallow One | creature.zombie_hd_radioactive_1 | Zombie |
| hdz/ZombieRadioactive2 | Fallow Two | creature.zombie_hd_radioactive_2 | Zombie |
| hdz/ZombieRadioactive3 | Fallow Three | creature.zombie_hd_radioactive_3 | Zombie |
| top/Zombie 01 | Corner Walker | creature.zombie_top_01 | Zombie |
| top/Zombie 02 | Viridian Scour | creature.zombie_top_02 | Zombie |
| top/Zombie 03 | White Collar | creature.zombie_top_03 | Zombie |
| top/Zombie 04 | Barefoot Red | creature.zombie_top_04 | Zombie |
| top/Zombie 06 | Gold Fringe | creature.zombie_top_06 | Zombie |
| top/Zombie 08 | Acid Bloom | creature.zombie_top_08 | Zombie |
| top/Zombie 09 | Violet Stitch | creature.zombie_top_09 | Zombie; Athletics proficiency |
| top/Zombie 10 | The Iron Stranger | creature.zombie_top_10 | Zombie |
| top/Zombie Decay 01 | Undercrypt One | creature.zombie_top_decay_01 | Zombie; speed15 |
| top/Zombie Decay 02 | Funeral Suit | creature.zombie_top_decay_02 | Zombie |
| top/Zombie Decay 03 | Wine-Stain Walker | creature.zombie_top_decay_03 | Zombie |
| top/Zombie Decay 04 | Undercrypt Four | creature.zombie_top_decay_04 | Zombie; speed15 |
| top/Zombie Decay 05 | The Mossed Coat | creature.zombie_top_decay_05 | Zombie; Athletics proficiency |
| top/Zombie Radioactive 01 | Marshglass One | creature.zombie_top_radioactive_01 | Zombie |
| top/Zombie Radioactive 02 | Marshglass Two | creature.zombie_top_radioactive_02 | Zombie |
| top/Zombie Radioactive 03 | Marshglass Three | creature.zombie_top_radioactive_03 | Zombie |
| top/Zombie Radioactive 04 | Marshglass Four | creature.zombie_top_radioactive_04 | Zombie |
| top/Zombie Swamp 01 | Reed Stalker | creature.zombie_top_swamp_01 | Zombie; weapon.longsword [MELEE_MAIN] |
| top/Zombie Swamp 02 | Fen Wader | creature.zombie_top_swamp_02 | Zombie |
| top/Zombie Swamp 04 | Mudroot | creature.zombie_top_swamp_04 | Zombie |
| top/Zombie Swamp 05 | The Mirelight | creature.zombie_top_swamp_05 | Zombie; Athletics proficiency |
| top/Zombie Swamp 07 | Black Reed | creature.zombie_top_swamp_07 | Zombie |
| top/Zombie Swamp 08 | Pale Moss | creature.zombie_top_swamp_08 | Zombie |
| top/Zombie Swamp 09 | Siltstep | creature.zombie_top_swamp_09 | Zombie; weapon.shortsword [MELEE_MAIN]; weapon.dagger [MELEE_OFF] |
