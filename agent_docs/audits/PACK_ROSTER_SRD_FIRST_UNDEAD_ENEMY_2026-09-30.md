# SRD-first matching: Undead, Enemy and Zombie packs

Date: 30 September 2026. This replaces the earlier mechanical proposals for
these 100 fixed variants. The zombie section now excludes 30 unmistakably modern role designs from the usable fantasy roster, retains 48 adaptable undead variants, and gives each retained variant a flavor-only backstory hook. It changes study documents only.

## Authority and method

Choose from the complete [SRD 5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf),
then change equipment to fit the actual artwork. A missing local factory never
disqualifies a source creature. All 317 source creature headings and page
locators are indexed in the existing source coverage ledger. The downloaded
official PDF matches the repository's pinned SHA-256; the private page corpus
is `.runtime/pack-study-20260930/srd-first/SRD5.1-pages.json`.
The full [SRD 5.2](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf)
was also checked, particularly its creature index and equipment table. It
supplies the Musket equipment below and corroborates an unarmed Ogre Zombie;
the selected creature foundations here all remain 5.1.

Names, source keys and visual evidence come from the
[100-entry action review](PACK_ROSTER_UNDEAD_ENEMY_COMPLETION_2026-09-30.md)
and its per-entry archive/member index. That report remains evidence, rather
than the authority for earlier custom rules. This pass also reread the private
`gallery-001-005.png` and `gallery-016-020.png`: Brute's later swing frames
resolve a long blade, correcting its earlier proposed empty hands. A greatsword
is the conservative selected subtype, not a pixel-proven catalogue identity.

Fit classes describe the resulting rules: **exact** keeps the same creature
and complete source block; **cosmetic** keeps those mechanics with an appearance
or breed reskin; **loadout** keeps the foundation but changes actual possessions
and consequent attacks/AC; **adapted** makes an additional named body/action
change. These categories do not certify final CR, production support or complete
animation coverage. Naming an SRD ancestor does not make an adapted row exact.

Unless a row explicitly changes a fact, preserve the selected source's complete
ability scores, size/type, HP, speeds, saves, skills, senses, languages, defenses,
traits and action/reaction repertoire. Signature summaries below highlight
important retained rules; they are not exhaustive replacements for stat blocks.
Source CR remains a reference benchmark when a loadout or attack changes.

## Shared selected rules and adaptations

- **S — Skeleton**, 5.1 p.346: retain the Medium undead foundation, HP13,
  bludgeoning vulnerability, poison immunity and exhaustion/poisoned immunities.
  Source armor scraps give AC13. Its source shortsword and shortbow are actual
  possessions; each row explicitly removes or replaces them. No project Mark
  Target, Parry or acid flask belongs to this SRD block.
- **W — Wight**, 5.1 pp.354–355: preserve Sunlight Sensitivity, source defenses,
  Life Drain including maximum-HP reduction and controlled-zombie consequence,
  and two-attack Multiattack with the source Life Drain substitution limit.
  A skeletal appearance does not add Skeleton's bludgeoning vulnerability.
- **L — Lich**, 5.1 pp.325–326: select the complete source CR21 creature, including
  18th-level Intelligence spellcasting and its entire prepared list, phylactery
  Rejuvenation, Legendary Resistance, Turn Resistance, Paralyzing Touch and
  legendary actions. A small sprite is not a reason to silently turn it into
  a low-level custom caster. The source component requirements remain in force.
- **Z — Zombie**, 5.1 pp.356–357: select the complete Medium undead block,
  AC8, HP22, speed20, poison/poisoned immunities and Undead Fortitude with its
  radiant/critical-hit exceptions. Retain Slam +3, 1d6+1 bludgeoning. No Bite,
  aura, police command trait, firearm or elemental resistance follows from a
  costume or green palette. Low crawling poses do not automatically impose
  the native Prone condition.
- **O — Ogre Zombie**, 5.1 p.357: retain its Large body, AC8, HP85, speed30,
  source ability scores, undead defenses and Undead Fortitude. Replace the
  unpictured Morningstar with intrinsic Slam +6, 2d8+4 bludgeoning. This is a
  named natural-attack adaptation; the same Slam occurs in 5.2 p.341. Do not
  also copy 5.2's added exhaustion immunity or other edition changes. The
  three hulks use one shared adaptation, rather than arbitrary stat inflation.
- **M — converted Musket**, 5.2 p.91: select its 1d12 piercing damage,
  range40/120, bullets, Loading and Two-Handed properties. Resolve it with 5.1
  ranged Dexterity attacks, ammunition, disadvantage at long range and Loading
  (5.1 pp.64–65); omit the 5.2 Slow mastery entirely. Loading permits one shot
  per action even if the foundation offers multiple ranged attacks. Modern
  firearm pixels are a cosmetic longgun reskin of this explicitly selected
  weapon; no automatic fire, magazine or aimed-shot rule is added. Shooter
  and Sniper have +4, 1d12+2; Zombie Soldiers have +0, 1d12−2 (minimum0).
  These calculations deliberately retain source Dexterity and proficiency,
  rather than granting invisible competence boosts. New weapon proficiency is
  explicitly part of the loadout adaptation. The source weapon's range does
  not support an unchanged longbow-range sniper claim.

Replacing a listed attack requires rewriting its weapon-specific Multiattack
choices explicitly; it does not create an extra bonus action. Listed attacks
below use the selected source ability scores and proficiency. Proficiency in
each selected replacement/additional weapon, armor or shield is an explicit
loadout grant where required (SRD 5.1 monster equipment guidance, p.254).
Unarmed strikes retain the ordinary 5.1 proficiency rule. Heavy-armor Strength limits,
Stealth disadvantage and hand occupancy remain 5.1 rules. Armor baked into a
body is still real worn equipment; suppress only a duplicate rendered overlay.
Ordinary unseen component supplies may be carried inventory, while material
components with costs remain required rather than waived by an empty-hand pose.

## HD Undead — 9

| Pack | Source variant | Flavour NPC | Primary SRD base / printed page | Fit | Retained source signature | Actual equipment and explicit changes | Local readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| undead | 1Brute | The Tombbreaker | Skeleton, 5.1 p.346 | loadout | S; source HP and Medium size retained rather than assuming Large from the Brute label. | Observed long blade: chosen `weapon.greatsword`, replacing shortsword/shortbow; no shield. Select no worn armor for its bare skeletal body: AC12 from Dex14, replacing armor scraps. Greatsword +2, 2d6 slashing using Str10; one attack. Earlier empty-hand proposal is superseded. | Skeleton root exists with partial fidelity; selected equipment/action and art binding unverified. |
| undead | 2DeathLord | Lord Ashveil | Wight, 5.1 pp.354–355 | loadout | W; armed intelligent grave-lord role is a stronger fit than a new Skeleton Warrior power set. | `weapon.longsword` + `shield.shield` + `armor.plate`; replace studded leather and remove longbow. AC20; longsword +4, 1d8+2 one-handed. Keep two melee attacks and Life Drain option. Orange slash stays cosmetic; no added Parry. | Wight missing locally; armor/weapon definitions exist. |
| undead | 3DarkKnight | The Gloam Knight | Wight, 5.1 pp.354–355 | loadout | W; skeletal-looking armored undead swordsman is a reskin without new bone defenses. | `weapon.longsword` + `shield.shield` + `armor.half_plate`; replace studded leather, remove longbow. AC19 from half plate15+Dex2+shield2; sword +4, 1d8+2. Keep source Life Drain and Multiattack; omit earlier invented Parry. | Wight missing locally; selected gear exists, effective composition unverified. |
| undead | 4Berserker | Redwake the Shattered | Skeleton, 5.1 p.346 | loadout | S; skeletal raider first, rather than inventing undead Berserker traits from its folder. | Selected `weapon.greatsword` for the long two-handed blade; replace shortsword/shortbow. Retain `armor.armor_scraps`, AC13; sword +2, 2d6 slashing. No source Reckless or Multiattack. | Skeleton root partial; custom loadout/binding unverified. |
| undead | 5Archer | Gravesight | Skeleton, 5.1 p.346 | loadout | S; canonical skeletal archer rather than the bespoke Mark Target creature. | Retain `weapon.shortbow` + `armor.armor_scraps`; remove shortsword. AC13; bow +4, 1d6+2 piercing, range80/320. No daggers or Mark Target. | Skeleton root partial; fixed-art binding remains separate. |
| undead | 6Warrior | Pikeward | Skeleton, 5.1 p.346 | loadout | S; bones and polearm sentry role. | `weapon.spear` + `shield.shield`, retain armor scraps, remove shortsword/shortbow. AC15; spear +2, 1d6 piercing one-handed using Str10. Shield excludes versatile two-handed damage. | Existing source skeleton and item owners; selected composition unverified. |
| undead | 7DarkArcher | The Black Fletch | Skeleton, 5.1 p.346 | loadout | S; palette does not grant a different ability set. | Same bow-only gear as5Archer: shortbow +armor scraps, no shortsword, AC13; +4, 1d6+2, range80/320. | Skeleton root partial; no new dark-archer handler required. |
| undead | 8Necromancer | The Violet Bell | Lich, 5.1 pp.325–326 | cosmetic | L; existing full skeletal-undead spellcaster including animate dead is preferred to the earlier bespoke two-spell warlock. | No carried weapon proposed; natural AC17 and full Lich actions/spells retained. Component access and phylactery remain native content requirements; pink casting art does not identify a spell. | Lich missing locally; legendary actions and full profile require later native capability work. |
| undead | 9Wizard | Candlebone | Lich, 5.1 pp.325–326 | loadout | L; staff-bearing appearance variant of the same source undead caster. | Real `weapon.quarterstaff` added as visible gear; natural AC17 unchanged. Ordinary staff attack +7, 1d6 bludgeoning (1d8 two-handed), explicitly using Str11/PB7; preserve full source spells/Touch/legendary actions. Not a new low-level skeleton-mage block. | Lich missing; actual staff item exists; composition/presentation unverified. |

## HD Enemy — 13

The 13 mappings below supersede the prior Guard/Scout/Thug-level pass. Full source signatures, actual attacks, gear, ammunition, poison, casting tier, 12Guard no-shield check, and local readiness are stated in the controlling [higher-tier Enemy draft](PACK_ROSTER_HIGHER_TIER_ENEMY_DRAFT_2026-10-01.md). The eight provisional level 5–12 squads are browsable in the illustration gallery. They are not production implementations or playtested balance.

| Pack | Source variant | Flavour NPC | Primary SRD base / printed page | Fit | Retained source signature | Actual equipment and explicit changes | Local readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| enemy | 1Hammer | The Bellringer | Gladiator, 5.1 p.399 | loadout | G; HP112; Brave, Brute, Parry +3; source CR5 benchmark. | Visible massive two-handed hammer: choose Maul and splint, AC17. Remove Spear, shield, studded armor and Shield Bash. Multiattack three Maul attacks +7, 3d6+4 bludgeoning; no ranged branch remains. | Gladiator, Brute, Maul and complete composition/bindings require later native verification. |
| enemy | 2Shooter | Blue Quarrel | Assassin, 5.1 p.396 | loadout | A; HP78, Assassinate, Evasion, Sneak Attack4d6, poison; source CR8 benchmark. | Visible longgun and metal protection: MU plus selected half plate, AC17 (15+DEX cap2), Stealth disadvantage. Remove source blades/crossbow and their Multiattack. One shot +6, 1d12+3 plus source poison, range40/120. Half plate makes surprise less reliable; no heavy-armor Dexterity boost. | Assassin signatures, Musket conversion, poison/ammunition inventory and fixed binding unverified. |
| enemy | 3Footsoldier | Gateplate | Gladiator, 5.1 p.399 | loadout | G; HP112, Brave, Brute, Parry +3; source CR5 benchmark. | Visible sword, large shield and protection: choose Longsword, shield and half plate, AC19. Remove Spear and its throw option. Multiattack three attacks chosen from Longsword +7, 2d8+4 slashing one-handed, or source Shield Bash +7, 2d4+4 with DC15 STR prone rider. | Gladiator and selected action choices/gear bindings need later native verification. |
| enemy | 4Assassin | The Blue Knife | Assassin, 5.1 p.396 | loadout | A; HP78 and all full source ambush/evasion/poison signatures; source CR8 benchmark. | Observed short pointed blade: selected Dagger, studded leather AC15. Remove source blades/crossbow. Rewrite Multiattack as two attacks with the one Dagger +6, 1d4+3 piercing plus source poison. Supply poison as actual inventory. No Cunning Action or unseen offhand weapon. | Full Assassin capability and actual dagger/poison ownership/binding unverified. |
| enemy | 5Bruiser | The Iron Shoulder | Gladiator, 5.1 p.399; trained unarmed adaptation P | adapted | P; HP112, source saves/skills, Brave; source CR5 benchmark. | Exposed arms, protective-looking fist guards, no carried weapon: mundane gauntlets/clothing plus explicit trained Fist attack. AC15 Martial Guard; three Fists +7, 2d6+4, or two Fists and one contested Shove. Remove source weapons/armor/shield/Brute/Parry/Shield Bash. Yellow attack FX adds no fire damage. | Authored martial trait/attack and shared action composition/binding unverified. |
| enemy | 6Crusader | Reliquary | Knight, 5.1 p.400 | loadout | K; HP52, Brave, Leadership, Parry +2; source CR3 support-officer benchmark. | Confirmed sword/shield and heavy armor: Longsword, shield, plate, AC20. Remove source Greatsword/crossbow. Two sword attacks +5, 1d8+3 one-handed. Real Leadership supports stronger troops; no invented divine aura. | Full Knight fidelity and source Leadership/gear composition/binding unverified. |
| enemy | 7Sniper | Far-Eye | Assassin, 5.1 p.396 | loadout | A; HP78, Stealth +9, Evasion, once-per-turn Sneak Attack, full Assassinate/poison; source CR8 benchmark. | Visible longgun, hood and lighter protection: MU plus selected studded leather AC15. Remove blades/crossbow/Multiattack. One shot +6, 1d12+3 plus source poison, range40/120. Uses cover/stealth and allies; no scope or exceptional range. | Full Assassin and converted firearm/ammunition/poison behavior/binding unverified. |
| enemy | 8Brawler | The Dockwall | Gladiator, 5.1 p.399; trained unarmed adaptation P | adapted | P; same shared complete foundation as Bruiser, HP112, Athletics +10 and Brave; source CR5 benchmark. | Shirt, trousers and mundane fist guards, no carried weapon/body armor: AC15 Martial Guard. Three Fists +7, 2d6+4, or two Fists and one contested Shove. No Pack Tactics, free grapple, hidden Mace or weapon-gated Parry. | Shared trained-unarmed composition and actual presentation unverified; not a second entity class. |
| enemy | 9Commander | Magister Nine | Archmage, 5.1 pp.395–396 | loadout | AM; HP99, DC17/+9, full18th-level casting, spell resistance and Magic Resistance; source CR12 benchmark. | Visible empty-hand casting: remove Dagger. Clothes AC12; AC15 with actual Mage Armor. Legal supplied components/pouch, full source spells and resource-consuming preparations retained. Stoneskin resistance is conditional. No Commander Leadership or legendary actions. | Archmage/full spell repertoire/component handling and fixed casting binding unverified. |
| enemy | 10Caster | Pale Ember | Mage, 5.1 pp.400–401 | loadout | M; HP40, full9th-level source caster, DC14/+6; source CR6 benchmark. | Observed staff: Quarterstaff replaces Dagger; +2, 1d6−1 bludgeoning (1d8−1 two-handed, minimum0), STR9/PB3. Clothes AC12/15 with Mage Armor. Explicit arcane-focus staff and legal supplies; full source spells retained. | Full Mage source fidelity, spell support and staff/focus presentation unverified. |
| enemy | 11Arcane elemental | Violet Static | Authored Arcane Sentinel E01; SRD alternatives rejected | authored | E01 below; Medium Elemental, target CR6 provisional. | Walking energy body; no held item, armor, shield, flight, invisibility or Shadow Strength Drain. Authored AC16/HP119, two Slams and rechargeable Arcane Burst. Force damage and defenses are explicit design choices, not palette evidence. | Complete new content profile and shared elemental/action capabilities would require future implementation. |
| enemy | 12Guard | Bronze Warden | Gladiator, 5.1 p.399 | loadout | G; HP112, Brave, Brute, Parry +3; source CR5 benchmark. | Fresh four-facing review finds a Spear and light clothing/protection, **no shield**. Choose studded leather AC14 (12+DEX2); remove shield/Shield Bash. Three two-handed Spear melee attacks +7, 2d8+4 piercing, or two thrown Spear attacks +7, 2d6+4, range20/60 if carrying two actual spears. Default inventory contains the single visible Spear, so cannot throw it twice without retrieval; no unlimited duplicates. | Gladiator, inventory-aware throw choices and spear/two-handed binding unverified. |
| enemy | 13Shepard | Hearth-Hound | Mastiff, 5.1 p.384 | cosmetic | Full Mastiff, CR1/8 /25 XP; Keen Hearing and Smell, Bite +3, 1d6+1, DC11 STR prone rider. | Ordinary Medium dog, AC12/HP5/speed40, no equipment. Support/spotter companion, not a main encounter threat or an inflated magical boss. No Wolf Pack Tactics or enlarged attack dice. | Full Mastiff and alternate-facing bite presentation unverified. |

## Zombie variants — 78

Each following row independently selects its listed source profile and shared
adaptation. Costumes and palette siblings share mechanics unless the actual
visible equipment or bulky body calls for the named change. Source variant
names are provenance, not content IDs. No radiation discharge is selected at
base: the previous optional custom discharge remains an unselected alternative.

| Pack | Source variant | Flavour NPC | Primary SRD base / printed page | Fit | Retained source signature | Actual equipment and explicit changes | Local readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hdz | ZombieCop1 | Deputy Ash — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieCop2 | Whitecoat Vale — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieCop3 | The Last Beat — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieCop4 | Blue Shield — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieFemale1 | Marigold | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale2 | Ash-Blue June | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale3 | Copper Jane | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale4 | Fen Green | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale5 | Roseglass | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale6 | Night Shift | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieFemale7 | Deep Teal | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieGeneral1 | The Brown General — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: military general uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieGeneral2 | The Black General — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: military general uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieHulk1 | Greenbulge | Ogre Zombie, 5.1 p.357 | adapted | O; published Large heavy-undead chassis and Undead Fortitude. | No item: Morningstar replaced by intrinsic Slam +6, 2d8+4 bludgeoning, using the secondary5.2 p.341 action. No copied5.2 exhaustion immunity. AC8/HP85/source size retained; bulk is a chosen body match. | Ogre Zombie root partial; natural-Slam replacement and art/size binding unverified. |
| hdz | ZombieHulk2 | White Knuckle | Ogre Zombie, 5.1 p.357 | adapted | O; published Large heavy-undead chassis and Undead Fortitude. | No item: Morningstar replaced by intrinsic Slam +6, 2d8+4 bludgeoning, using the secondary5.2 p.341 action. No copied5.2 exhaustion immunity. AC8/HP85/source size retained; bulk is a chosen body match. | Ogre Zombie root partial; natural-Slam replacement and art/size binding unverified. |
| hdz | ZombieMale1 | Olive Trousers | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale2 | The White Shirt | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale3 | Blue Sleeve | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale4 | Poolside | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale5 | Saffron Shirt | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale6 | Nightcoat | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale7 | Green Vest | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale8 | Red Thread | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMale9 | Rust Collar | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMonster1 | The Narrow One | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMonster2 | Red Suture | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| hdz | ZombieMonster3 | Heavy Pale | Ogre Zombie, 5.1 p.357 | adapted | O; published Large heavy-undead chassis and Undead Fortitude. | No item: Morningstar replaced by intrinsic Slam +6, 2d8+4 bludgeoning, using the secondary5.2 p.341 action. No copied5.2 exhaustion immunity. AC8/HP85/source size retained; bulk is a chosen body match. | Ogre Zombie root partial; natural-Slam replacement and art/size binding unverified. |
| hdz | ZombieRadioactive1 | The Green Reactor — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieRadioactive2 | Thinlight — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieRadioactive3 | The Spill — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier1 | Last Watch — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier2 | Helm Rust — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier3 | Hooded Line — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier4 | Cinder Company — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier5 | Brass Button — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| hdz | ZombieSoldier6 | Coal Detail — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie 01 | Corner Walker | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 02 | Viridian Scour | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 03 | White Collar | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 04 | Barefoot Red | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 05 | The Lab Runner | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 06 | Gold Fringe | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 07 | The Shroud | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 08 | Acid Bloom | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 09 | Violet Stitch | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie 10 | The Iron Stranger | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Cop 01 | Night Patrol — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Cop 02 | The Pale Patrol — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Cop 03 | Amber Siren — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Cop 04 | Whitewall — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: police uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Decay 01 | Undercrypt One | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. Source crawl/low pose remains appearance, not an automatically imposed Prone condition. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Decay 02 | Funeral Suit | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Decay 03 | Wine-Stain Walker | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Decay 04 | Undercrypt Four | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. Source crawl/low pose remains appearance, not an automatically imposed Prone condition. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Decay 05 | The Mossed Coat | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Fireman 01 | Flashover — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: firefighter uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Fireman 02 | Backdraft — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: firefighter uniform is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Radioactive 01 | Reactor Hiss — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Radioactive 02 | Greenflare Two — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Radioactive 03 | Wastelight — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Radioactive 04 | Last Warning — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: hazmat/radiation suit design is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Soldier 01 | Trench Echo — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Soldier 02 | Khaki Warden — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Soldier 03 | Brass March — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Soldier 04 | Cinder March — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Soldier 05 | Green Beret — excluded from fantasy roster | No suitable fantasy-facing asset (excluded modern design) | no_fit | Excluded: modern military uniform and firearm is a recognizable modern role/design. The source key remains for provenance only. | No SRD zombie profile or gear selection; remove this variant from the usable fantasy roster. | Excluded from fantasy roster; original sprite retained only as source provenance. |
| top | Zombie Swamp 01 | Reed Stalker | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 02 | Fen Wader | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 03 | Eelgrass | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 04 | Mudroot | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 05 | The Mirelight | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 06 | Rotwater | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 07 | Black Reed | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 08 | Pale Moss | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Swamp 09 | Siltstep | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Worker 01 | Shift Bell | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Worker 02 | The Foreman | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |
| top | Zombie Worker 03 | Blue Overall | Zombie, 5.1 pp.356–357 | cosmetic | Z; complete source block retained. | No carried weapon; source AC8 and Slam retained. Costume/palette only; no extra class, armor or aura. | Zombie root partial; this appearance/action binding unverified. |

## Retained zombie identities and optional backstory hooks

These short hooks distinguish fantasy-usable commoners and themed undead. They are flavor only: no added traits, actions, equipment, or setting canon. Excluded modern-role variants are intentionally omitted.

| Pack | Source variant | Identity | Optional backstory hook |
| --- | --- | --- | --- |
| hdz | ZombieFemale1 | Marigold | A market seller who counted every copper now drifts through the empty stalls, still clutching a wilted marigold. |
| hdz | ZombieFemale2 | Ash-Blue June | Once the keeper of a riverside inn, June is remembered by the blue shawl left at her door. |
| hdz | ZombieFemale3 | Copper Jane | Jane worked the kiln-side dye vats; the copper in her hair is all the village can still recognize. |
| hdz | ZombieFemale4 | Fen Green | A fen herbalist, she knew every safe path through the reeds until the marsh claimed her own. |
| hdz | ZombieFemale5 | Roseglass | Roseglass sang at harvest feasts, and the old glass beads sewn into her dress still catch the light. |
| hdz | ZombieFemale6 | Night Shift | The night watch found her last lantern burning beside an unlocked cottage and an unfinished cup of tea. |
| hdz | ZombieFemale7 | Deep Teal | A weaver from the low town, she vanished during the flood; only the teal thread of her apron survived. |
| hdz | ZombieHulk1 | Greenbulge | A quarry porter buried in a cave-in, he returned larger than the stone that sealed the shaft. |
| hdz | ZombieHulk2 | White Knuckle | The village gate-breaker was once its gentlest mason; pale knuckles mark the wall where he came home. |
| hdz | ZombieMale1 | Olive Trousers | A field hand who never made it back from the harvest, he still wears the mud-stained trousers of the last day. |
| hdz | ZombieMale2 | The White Shirt | The village remembers a baker who gave away the unsold loaves; his white shirt is stained with flour and grave dust. |
| hdz | ZombieMale3 | Blue Sleeve | A ferry porter lost in the winter crossing, he returns whenever the river fog closes over the landing. |
| hdz | ZombieMale4 | Poolside | He drowned on the midsummer revel and still wanders in bright clothes, searching for the music. |
| hdz | ZombieMale5 | Saffron Shirt | A spice peddler who never reached the next town, his saffron tunic marks the road where the caravan broke. |
| hdz | ZombieMale6 | Nightcoat | The old manor’s coat-keeper died in the locked cellar; the dark livery is now the only clue to his name. |
| hdz | ZombieMale7 | Green Vest | A gardener laid to rest in the orchard, he returns each spring among the green rows he tended. |
| hdz | ZombieMale8 | Red Thread | A courier vanished on the hill road with an undelivered letter stitched beneath his collar. |
| hdz | ZombieMale9 | Rust Collar | The smith’s apprentice wore a rust-red collar; the forge has been cold since the night he disappeared. |
| hdz | ZombieMonster1 | The Narrow One | A narrow, misshapen grave-robber, it was sealed beneath the chapel after disturbing the old crypt. |
| hdz | ZombieMonster2 | Red Suture | Wrapped in red burial thread, this warped corpse was bound shut by a desperate village healer. |
| hdz | ZombieMonster3 | Heavy Pale | This pale brute was the last guardian of a tomb whose entrance has since vanished beneath the hill. |
| top | Zombie 01 | Corner Walker | The corner beggar knew every alley in the old quarter; now the bells ring whenever he turns one. |
| top | Zombie 02 | Viridian Scour | Green light clings to this wanderer, who appeared after the well was sealed and the village water cleared. |
| top | Zombie 03 | White Collar | Once a clerk in the reeve’s hall, he still carries himself as if waiting to be called before the council. |
| top | Zombie 04 | Barefoot Red | A barefoot pilgrim died outside the shrine gates; each dawn finds her a little closer to the threshold. |
| top | Zombie 05 | The Lab Runner | A curious scholar entered the buried observatory and returned alone, carrying a stain no washing removes. |
| top | Zombie 06 | Gold Fringe | The fair’s golden-masked dancer disappeared on the final night; the empty stage has never been used again. |
| top | Zombie 07 | The Shroud | A wandering mourner in a dark shroud, it follows funeral processions that have not yet begun. |
| top | Zombie 08 | Acid Bloom | The orchard keeper’s grave blooms with strange color, and this figure comes out whenever the fruit ripens. |
| top | Zombie 09 | Violet Stitch | Violet stitches cross the coat of a grave-tender who once mended the dead before burial. |
| top | Zombie 10 | The Iron Stranger | No one recalls the iron-clad stranger arriving; the village only remembers the locked doors after dusk. |
| top | Zombie Decay 01 | Undercrypt One | Buried beneath a collapsed crypt stair, it reaches up whenever footsteps pass over the stone. |
| top | Zombie Decay 02 | Funeral Suit | A once-respected undertaker rose in the clothes prepared for his own final ceremony. |
| top | Zombie Decay 03 | Wine-Stain Walker | The wine-cellar keeper died in a cask collapse; the dark stain on his clothes marks the old passage. |
| top | Zombie Decay 04 | Undercrypt Four | This corpse was bricked into the undercrypt wall, but the mortar has begun to crack from within. |
| top | Zombie Decay 05 | The Mossed Coat | A forester buried beneath the mossy boundary stone now wanders wherever the woods reclaim a path. |
| top | Zombie Swamp 01 | Reed Stalker | The reed-cutter vanished in the north bog; locals say the stalks bend toward his footsteps. |
| top | Zombie Swamp 02 | Fen Wader | A ferryman from the fen, she appears beside mooring posts that have long since sunk from sight. |
| top | Zombie Swamp 03 | Eelgrass | This drowned gatherer is found where eelgrass knots around the old sunken causeway. |
| top | Zombie Swamp 04 | Mudroot | A peat digger was lost in the mire; his hut remains dry, though no one has lived there for years. |
| top | Zombie Swamp 05 | The Mirelight | A lantern-bearer disappeared in the marsh lights; the faint glow still wanders beyond the safe ground. |
| top | Zombie Swamp 06 | Rotwater | The bog reclaimed this village outcast, leaving a trail of dark water through the rushes. |
| top | Zombie Swamp 07 | Black Reed | A keeper of the black-reed beds returns whenever the cutting season begins. |
| top | Zombie Swamp 08 | Pale Moss | The pale moss grew over this sleeper’s grave, and the neighboring trees all lean away from it. |
| top | Zombie Swamp 09 | Siltstep | A mud-stained guide led travelers across the fen until one night the guide never came back. |
| top | Zombie Worker 01 | Shift Bell | The bell-ringer died before the new tower was finished; at dusk, the unfinished bell answers anyway. |
| top | Zombie Worker 02 | The Foreman | A stone foreman was buried beneath his own half-built arch, whose shadow still crosses the road. |
| top | Zombie Worker 03 | Blue Overall | A millhand disappeared during the flood season; the empty mill wheel turns when this figure passes. |

## Rejected shortcuts and remaining work

Wraith/Specter were rejected for physical armored skeletons because their
incorporeal flight/life-drain bodies would require larger alterations than
Skeleton or Wight. Minotaur Skeleton's horns, Gore and Charge do not fit the
humanoid blade skeletons; their source file size does not prove Large size.
Lich is accepted for both visibly skeletal casters with its full high-CR source
rules; a lower encounter tier would require a separately named adaptation.
For `11Arcane elemental`, Shadow is explicitly rejected because it is Undead,
not Elemental. The higher-tier proposal is an authored Arcane Sentinel E01
(target CR6, provisional), with its own force burst and defenses; these are
content choices, not inferences from purple pixels. See the linked higher-tier
Enemy draft for the complete profile and rules boundaries. Zombie hulk
adaptation preserves the published Ogre Zombie chassis.

The 5.2 comparison selects no additional primary creature for these
100 rows. Its Musket and Ogre Zombie Slam are explicitly marked secondary
details; no 5.2 weapon mastery, revised statblock initiative, automatic grapple/
prone outcome, exhaustion scheme or spell version silently replaces 5.1.

Local source-ledger statuses are dated evidence rather than a runtime guarantee.
Canonical source fidelity, effective equipment/AC, proficiency, ammunition and
Loading, complete legendary/undead effects and presentation bindings all require
later authorized implementation and verification. This study does not run tests,
import artwork, change canonical stat blocks or create an NPC framework.

## Attribution

This work includes material taken from the System Reference Document 5.1
(“SRD 5.1”) by Wizards of the Coast LLC and available at
https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is
licensed under the Creative Commons Attribution 4.0 International License
available at https://creativecommons.org/licenses/by/4.0/legalcode.

This work includes material from the System Reference Document 5.2 (“SRD 5.2”)
by Wizards of the Coast LLC, available at https://www.dndbeyond.com/srd. The
SRD 5.2 is licensed under the Creative Commons Attribution 4.0 International
License, available at https://creativecommons.org/licenses/by/4.0/legalcode.
