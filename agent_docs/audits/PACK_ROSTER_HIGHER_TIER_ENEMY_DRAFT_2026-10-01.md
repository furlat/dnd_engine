# HD Enemy: stronger SRD 5.1 proposals

Date: 1 October 2026. This draft supersedes the thirteen HD Enemy mappings in
the earlier SRD-first table. It is a design and gallery revision; it adds no
production creatures, imports, equipment or engine behavior.

The human requested enemies beyond simple Guards and Scouts while retaining
SRD 5.1 as the first source and respecting visible possessions. Plan: inspect
the fixed attacks and gear, select stronger complete 5.1 foundations, name every
equipment or mechanical change, add complementary squads, then perform
anti-slop and anti-OOP/ECS reviews. The reviews below are author self-reviews,
not independent approvals or playtest results.

## Source and art authority

Sources: [official SRD 5.1](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf),
printed pp.395–400 and 384; [official SRD 5.2](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf),
p.91 for Musket equipment only. All twelve published-creature proposals use
5.1 foundations. The elemental is one explicitly authored exception.

Source archive: `2D HD Enemy pack 1.zip`, preserved in Downloads. Fresh
[attack contact](../../.runtime/pack-study-20260930/srd-first/illustration-comparison/root-enemy-strength-evidence/enemy-attack-12.png)
samples first/middle/last Attack1 frames facing South and East for the twelve
combatant variants. A separate
[four-facing shield check](../../.runtime/pack-study-20260930/srd-first/illustration-comparison/root-enemy-strength-evidence/enemy-shield-audit.png)
confirms the Footsoldier and Crusader shields and corrects the nonexistent
shield on `12Guard`. Exact sampled members are recorded in private
`attack-members.json`. These contacts supplement the earlier archive/action
inventory; they do not certify all facing/animation bindings.

Metal or padded clothing identifies a protective silhouette, not an exact
catalogue armor item. Armor subtypes below are declared equipment choices.
Gun shapes are actual longguns represented by the selected converted Musket.
Fist and casting FX are presentation evidence; their colors do not grant damage
types, fire resistance, flight or invisibility. Literal keys, including
`11Arcane elemental` and `13Shepard`, remain unchanged.

## Complete foundations and explicit changes

Except for the changes named below, retain the selected source's entire block:
ability scores, HP, size/type, speed, saves, skills, senses, languages, defenses,
traits, actions and reactions. The following summaries are not shortened
replacement stat blocks. Source CR is a benchmark; altered profiles require
later CR calculation and playtesting. A player level is not a monster CR.

**G — Gladiator, 5.1 p.399, source CR5 / 1,800 XP.** Medium Humanoid; HP112
(15d8+45), speed30, STR18 DEX15 CON16 INT10 WIS12 CHA15, PB3. STR/DEX/CON
saves +7/+5/+6, Athletics +10, Intimidation +5, passive Perception11, Common.
Retain Brave. Brute adds **one extra weapon die** to a melee weapon's damage;
thus a Maul has 3d6+4, not 4d6+4. Source Multiattack has three melee attacks or
two ranged attacks; each row explicitly names its remaining choices. Shield
Bash is +7, 2d4+4 bludgeoning, Medium-or-smaller target DC15 STR or prone.
Parry gives +3 AC against one visible melee attack while wielding a melee
weapon. A source Shield Bash or Parry is removed when its actual requirement
is absent. There is no Pack Tactics or Leadership in this foundation.

**A — Assassin, 5.1 p.396, source CR8 / 3,900 XP.** Medium Humanoid; HP78
(12d8+24), speed30, STR11 DEX16 CON14 INT13 WIS11 CHA10, PB3. DEX/INT saves
+6/+4; Acrobatics +6, Deception +3, Perception +3, Stealth +9; passive13;
Thieves' Cant and two languages; poison resistance. Retain Assassinate,
Evasion and once-per-turn 4d6 Sneak Attack with the source eligibility rules.
Assassinate grants first-turn advantage against a creature that has not taken
a turn; the automatic critical hit requires actual surprise. Both source
Shortsword and Light Crossbow attacks carry the DC15 CON, 7d6 poison rider
(half on a successful save). The selected loadouts retain this effect through
real poison supplies, not blue clothing. Surprise is determined by ordinary
5.1 perception/stealth, not by a pack name or an automatic encounter script.

**K — Knight, 5.1 p.400, source CR3 / 700 XP.** Medium Humanoid, HP52
(8d8+16), STR16 DEX11 CON14 INT11 WIS11 CHA15, PB2, speed30. Retain the full
source defenses/saves/languages, Brave, two melee attacks, and **Parry +2**.
Leadership lasts one minute, recharges after a short/long rest, and grants a
single 1d4 to an eligible nonhostile creature's attack roll or saving throw
within30 feet when it can hear and understand the knight. It does not add to
AC, damage or grapple/shove ability checks, and multiple Leadership dice do
not stack. No divine spells or aura are added by the Crusader costume.

**M — Mage, 5.1 pp.400–401, source CR6 / 2,300 XP.** Medium Humanoid; HP40
(9d8), speed30, STR9 DEX14 CON11 INT17 WIS12 CHA11, PB3. Retain the complete
9th-level Intelligence spellcasting block, spell save DC14, spell attacks +6,
four languages, saves, skills and prepared list. Slots: 4/3/3/3/1. Cantrips:
Fire Bolt, Light, Mage Hand, Prestidigitation. Prepared spells: Detect Magic,
Mage Armor, Magic Missile, Shield; Misty Step, Suggestion; Counterspell,
Fireball, Fly; Greater Invisibility, Ice Storm; Cone of Cold. Do not replace
this with a two-spell weak caster. Concentration and component rules remain.

**AM — Archmage, 5.1 pp.395–396, source CR12 / 8,400 XP.** Medium Humanoid;
HP99 (18d8+18), speed30, STR10 DEX14 CON12 INT20 WIS15 CHA16, PB4. Retain
INT/WIS saves +9/+6, Arcana/History +13/+13, passive12, six languages, Magic
Resistance and resistance to damage from spells. Retain full 18th-level
Intelligence spellcasting, DC17, spell attacks +9, and at-will Disguise Self
and Invisibility. Slots: 4/3/3/3/3/1/1/1/1. Cantrips: Fire Bolt, Light,
Mage Hand, Prestidigitation, Shocking Grasp. Prepared spells: Detect Magic,
Identify, Mage Armor, Magic Missile; Detect Thoughts, Mirror Image, Misty
Step; Counterspell, Fly, Lightning Bolt; Banishment, Fire Shield, Stoneskin;
Cone of Cold, Scrying, Wall of Force; Globe of Invulnerability; Teleport;
Mind Blank; Time Stop. Source preparation of Mage Armor, Stoneskin and Mind
Blank consumes actual slots/components. Nonmagical B/P/S resistance belongs
to active Stoneskin, which requires concentration and its costly component;
it is not unconditional body resistance. Changing concentration to Wall of
Force ends Stoneskin. There are no source legendary actions or prepared
Shield spell. The folder Commander supplies no extra Leadership ability.

**MU — Musket conversion.** Select 5.2 p.91 damage1d12 piercing, range40/120,
Loading, Two-Handed and bullets. Use 5.1 Dexterity ranged weapon attacks,
ammunition, long-range disadvantage, nearby-enemy disadvantage and Loading;
omit the 5.2 Slow mastery. Loading permits only **one shot per action**.
Removing both Shortswords removes the source two-Shortsword Multiattack
branch; it is not permission for two gunshots or two emergency punches.
Each gunner carries one Musket, twenty bullets/powder charges, and twenty
single-use poison doses for the listed source poison effect. No automatic
fire, scope bonus, invisible sidearm, reload exemption or longbow range is
added. Each shot expends ammunition and one dose if poisoned; without a
dose it loses the poison rider. Ordinary emergency unarmed strike is +3,
1 bludgeoning, once with the Attack action. These are source-CR8 loadout
proposals, not certified final CR8 gunfighters.

**P — trained unarmed Gladiator adaptation.** Choose G first for the visible
professional arena-fighter body and role. Retain its HP112, scores, PB3,
saves, skills, movement, senses, languages and Brave. Remove all carried
source weapons, studded armor, shield, Brute, Shield Bash and weapon-gated
Parry. Add the explicitly authored **Martial Guard** trait: while not wearing
armor or using a shield, AC =10+DEX modifier+CON modifier =15. Add trained
**Fist** unarmed strike +7, reach5, 2d6+4 bludgeoning. This is an authored
martial attack definition; it is not the ordinary 1+STR unarmed rule, hidden
Mace dice, a natural claw, or a benefit granted by a mundane glove. Multiattack
allows three Fist attacks, or two Fists and one ordinary 5.1 Shove. Shove uses
the source Athletics +10 contest, has ordinary size/reach limits and knocks
prone or pushes5 feet. It does not automatically grapple or restrain. A
grapple uses the separate ordinary Attack action and occupies a hand; it is
not a free rider or a Multiattack replacement here. No reaction is added.
The two art variants share this one **adapted**, source-CR5 proposal. It
requires balance validation; it is not an exact published Gladiator block.

Replacement weapon/armor/shield proficiency is an explicit loadout grant.
Heavy-armor Strength requirements, Stealth disadvantage, shield occupancy,
weapon properties and component handling remain 5.1. Added poison/component
inventory is ordinary supplied gear; it needs content ownership before any
production use. Removing an unseen carried attack does not remove an intrinsic
source trait or spell. A missing native ability is recorded as a future gap.

## Thirteen fixed proposals

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

The twelve combatants now use source benchmarks CR3–12: one CR3 supporting
Knight, five CR5 Gladiator proposals (including the two explicitly adapted
unarmed fighters), one CR6 Mage, three CR8 Assassin loadouts, one CR12 Archmage,
and the authored target-CR6 elemental. The dog is the single companion exception.
The twelve 5.1 foundations include the dog; no Guard, Scout or Thug foundation
remains in this pack. This does not remove weak creatures from appropriate
early-level roles elsewhere in the roster.

## E01 — Arcane Sentinel, authored target CR6

Medium Elemental, unaligned. AC16 natural arcane body (authored), HP119
(14d8+56), walking speed30. STR16 DEX14 CON18 INT10 WIS12 CHA8. PB3 provisional;
CON save +7, WIS save +4, Perception +4; darkvision60, passive Perception14.
Understands Common but cannot speak. Resistance to nonmagical bludgeoning,
piercing and slashing; poison damage immunity; exhaustion and poisoned
condition immunity. These are deliberate elemental-body choices, not copied
from Shadow or inferred from magenta pixels. No other resistance, flight,
hover, incorporeal movement, invisibility, Magic Resistance or Strength Drain.

Multiattack: two Slam attacks. **Slam:** melee weapon attack +6, reach5, one
target, 2d8+3 bludgeoning; this is an intrinsic body attack, not an item.
**Arcane Burst (Recharge5–6):** as an action, emit a15-foot cone; creatures
within it make DC15 DEX saves, taking6d6 force damage on failure, half on
success. DC =8+PB3+CON4. Burst replaces Multiattack; no bonus-action version,
automatic knockback or additional turn. Friendly creatures are also affected.
No spellcasting or concentration resource is attached to this authored ability.
No reaction or legendary action is added.

The profile is a new bounded proposal because Shadow is Undead and has
incompatible drain/weakness rules; Invisible Stalker has permanent invisibility,
flight and tracking; Air Elemental has a Large flying whirlwind body; Earth
Elemental has a Large earthen body and burrow. Their complete 5.1 blocks were
considered first. Changing their type/body/signatures would discard the visual
and role match instead of preserving a fitting source. Medium walking
elemental, attack type and body defenses are explicitly owned author choices.
Target CR6 /2,300 XP is provisional, particularly because body resistance and
multi-target Burst change effective durability/damage.

## Complementary encounters for four characters

The existing [Devil teams](PACK_ROSTER_AUTHORED_DEVILS_DRAFT_2026-10-01.md)
cover player levels1–12. This stronger HD Enemy pack contributes the following
mid/high-level squads rather than being forced into weak level1 opposition.
Use the [2014 Basic Rules encounter thresholds and multipliers](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/building-combat-encounters),
consistent with 5.1-era combat, and source CR XP as a **conditional estimate**.
The encounter-building tables are additional 2014 guidance, not tables present
in the SRD 5.1 PDF. Recalculate after final CR validation.
All listed participants materially contribute; omit a support dog from the
multiplier when it contributes too little to encounter difficulty. No excluded
modern zombie enters these squads.

| Player level | Team: literal source keys and quantities | Raw / adjusted XP; provisional band | Actual cooperation | Counterplay |
| --- | --- | --- | --- | --- |
| 5 | 1×6Crusader +1×3Footsoldier | 2,500 /3,750 (×1.5); Hard | Knight Leadership improves the Gladiator's attacks/saves; sword/shield fighter uses Shield Bash before close melee attacks. | Interrupt the officer or hearing/30-foot support line; spread out and avoid fighting the shield fighter in a doorway. |
| 6 | 1×1Hammer +1×8Brawler | 3,600 /5,400 (×1.5); Hard | Brawler can win a contested Shove, leaving a prone target for the Maul fighter's nearby melee attacks. | Kite their walking bodies; win the opposed check or stand/move before the hammer closes. Neither gains a free grapple or ranged attack. |
| 7 | 1×10Caster +1×12Guard | 4,100 /6,150 (×1.5); Hard | Spear Warden screens the fragile Mage; the Mage uses Counterspell, ranged damage and one legal concentration spell. | Break concentration, flank the shieldless Warden, or pressure the Mage's HP40. Fireball includes allies; Fly and Greater Invisibility cannot both be maintained by that Mage. |
| 8 | 1×7Sniper +1×6Crusader | 4,600 /6,900 (×1.5); Hard | Officer Leadership improves the single gunshot/save; a standing Knight next to the target can satisfy source Sneak Attack positioning. | Cover, close the gunner, deny legal Sneak Attack or resist poison. Do not have the Knight knock targets prone while the gunner shoots from more than5 feet: that gives ranged disadvantage. |
| 9 | 1×4Assassin +1×3Footsoldier | 5,700 /8,550 (×1.5); Hard | The shield fighter threatens the target while the knife specialist gains eligible Sneak Attack; melee allies can benefit from a legal Shield Bash prone result. | Reveal the ambush before initiative, separate the pair, use poison defenses and stay alert to the once-per-turn Sneak Attack limit. |
| 10 | 1×11Arcane elemental +1×5Bruiser +1×6Crusader | 4,800 /9,600 (×2); Hard | Officer Leadership supports the fighters; Bruiser uses its contested 5-foot Shove **push** option to move a target into the elemental's short cone. The elemental chooses its cone to avoid allies. Prone does not penalize DEX saves. | Break the officer's support line; spread out or move beyond the15-foot cone. Magical weapons bypass the elemental's nonmagical B/P/S resistance. Leadership does not buff Shove checks or Burst DC. |
| 11 | 1×2Shooter +1×10Caster +1×6Crusader | 6,900 /13,800 (×2); Hard | Mage can concentrate on Greater Invisibility for the gunner's eligible Sneak Attack; Knight supplies Leadership and a melee screen. | Break the Mage's concentration, use cover/poison protection and push past the officer. Invisibility does not itself create surprise or automatic critical hits. Half plate still imposes Stealth disadvantage. |
| 12 | 1×9Commander +1×3Footsoldier | 10,200 /15,300 (×1.5); Hard | Archmage uses Wall of Force to partition the field while the shield fighter contests a separate lane; Counterspell and full high-level slots supply boss pressure. | Exploit the AC12/15 and HP99, disrupt preparation/components, or break the formation. Wall of Force also blocks the Archmage's attacks through it, and choosing it ends Stoneskin concentration/resistance. No legendary extra turns are available. |

These bands use four-character Hard/Deadly thresholds respectively: level5
3,000/4,400; 6 3,600/5,600; 7 4,400/6,800; 8 5,600/8,400; 9 6,400/9,600;
10 7,600/11,200; 11 9,600/14,400; 12 12,000/18,000. Poison, source surprise,
terrain and party resources can make these teams much harsher than the estimate.
Choose deliberate win conditions/telegraphing and ordinary legal initiative;
do not quietly remove source signatures to fit a level number.

## Anti-slop self-review

- All thirteen literal variants are present once; twelve combatants have actual
  stronger HP/actions/spells, not stronger names pasted onto Guard/Scout stats.
- Complete SRD 5.1 creature blocks control twelve proposals. The two trained
  unarmed profiles are marked adapted; E01 is marked authored. Edited source
  CR and encounter bands are provisional, not claims of certified balance.
- Fresh four-facing evidence removes the invented `12Guard` shield. Armor
  identities, poison supplies, fist training and elemental defenses are named
  author choices. FX hues grant no fire/force power by inference.
- The two gunners respect Loading, one-shot actions, actual poison ammunition,
  source surprise/Sneak Attack limits and 40/120 range. Shooter's half plate
  imposes Stealth disadvantage; Sniper receives no magical range increase.
- Maul Brute adds one d6; Knight Parry is +2, Gladiator Parry +3. Ordinary
  punches do not inherit Mace damage; trained Fist explicitly owns its rule.
- Teams explain real cooperation and interference: distant gunfire against
  prone targets is worse; friendly cones hurt allies; Leadership does not aid
  Shove checks; concentration and Wall of Force are enforced.
- The ordinary dog is a helper, not artificial encounter-strength padding.
  No production implementation, native fidelity, complete art binding or
  independent reviewer approval is claimed.

## Anti-OOP / ECS self-review

The proposals describe data, possessions and system-composed behavior. P is
one shared trained-unarmed composition, not Bruiser/Brawler entity subclasses.
Source NPC spell/trait/action repertoire stays with content definitions;
equipment, ammunition/doses, hand occupancy, spell slots, conditions and
concentration have explicit owners. Armor already painted on a body still
exists as real selected gear; suppress only a duplicate presentation overlay.
No new entity classes, late imports, circular dependencies, runtime type
inspection, getattr dispatch, bypass handlers or factory cloning is proposed.
Future missing capabilities are recorded without implementing them in this
design pass.

## Source attribution

This work includes material taken from the System Reference Document5.1
("SRD5.1") by Wizards of the Coast LLC and available at
https://dnd.wizards.com/resources/systems-reference-document. The SRD5.1 is
licensed under the Creative Commons Attribution4.0 International License at
https://creativecommons.org/licenses/by/4.0/legalcode. The secondary Musket
equipment is adapted from System Reference Document5.2 by Wizards of the
Coast LLC, available at the official PDF linked above, under the same license.
