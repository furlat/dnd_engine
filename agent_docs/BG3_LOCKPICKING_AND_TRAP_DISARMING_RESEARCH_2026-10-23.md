# Baldur's Gate 3: lockpicking, trap detection, disarming, and documented DCs

Researched: **23 October 2026**. Contains location, item, puzzle, and quest spoilers for all three acts.

This is a research reference for BG3, not an engine implementation proposal. It consolidates publicly documented mechanics, a catalogue of **24 trap families/mechanisms**, and location-specific checks. No BG3 installation, save, or extracted game files were tested during this research. “Documented” below means a source explicitly reports the value; it does not mean independently reproduced in the current game build.

## 1. Findings and where the lists exist

**Yes: there is a published trap list with disarm DCs.** BG3 Wiki's [Trap article](https://bg3.wiki/wiki/Trap#List_of_traps) is the best starting point found. Its [Traps category](https://bg3.wiki/wiki/Category:Traps) links individual mechanism pages, while location walkthroughs often supply more specific DCs. The category is not a complete index: the inspected category returned 18 pages, whereas the main article includes additional mechanisms and hazards.

The most useful conclusions are:

- Lockpicking and ordinary trap disarming both use **Dexterity (Sleight of Hand)**, but require different tools. BG3 replaces tabletop tool-proficiency checks with this skill. [Sleight of Hand](https://bg3.wiki/wiki/Sleight_of_Hand), [BG3 rule changes](https://bg3.wiki/wiki/D%26D_5e_rule_changes).
- Detection, disarming, unlocking, and resisting the triggered effect are **different checks**. A single object can have three different interaction DCs, plus a separate saving throw.
- Generic trap-family entries such as **10+** are starting values, not a promise that every instance has DC 10. The location tables below include disarm DCs **10, 14, 15, 18, 20, 21, 25, and 30**.
- Some defenses use a switch, puzzle, destruction, or another skill instead of a toolkit. Some cannot be directly disarmed. The catalogue separates these cases.
- Published coverage is substantial but incomplete. This document does **not** claim to enumerate every placed trap, every lock, or every difficulty-dependent variant in BG3.

### Reading the tables

| Label | Meaning |
| --- | --- |
| Detect | The skill/DC used to reveal a trap or relevant hidden mechanism. Usually Perception, with explicit exceptions. |
| Disarm | Dexterity (Sleight of Hand) DC unless another skill is stated. |
| Lock | A separate Dexterity (Sleight of Hand) check to unlock the object. |
| Save | A saving throw after a hazard activates; never interchangeable with Disarm. |
| **NR** | A value was not reported in the inspected source. It is unknown here, not zero. |
| **N/A** | That operation does not apply, or the source explicitly describes a different mechanism. |
| **10+ / 15+** | The source's family-level minimum; individual placements vary. |
| **Guide** | An explicit value from a walkthrough rather than a corresponding wiki DC entry. |
| **Uncertain** | The source marks the value for verification or sources disagree. |

## 2. Lockpicking mechanics

### Requirements and outcome

Select a character and use the locked object's **Lockpick** interaction. The ordinary check requires **Thieves' Tools** and uses that character's Sleight of Hand. A successful attempt preserves the tools; an unsuccessful attempt breaks one set. Tools are found as loot and sold by traders. Their consumable classification does not mean one is spent on every success. [Thieves' Tools](https://bg3.wiki/wiki/Thieves%27_Tools).

Proficiency is helpful but is not a prerequisite to attempting a skill check. Any class can therefore serve as the lockpicker when it has the necessary tool and access to the interaction. Rogue is particularly convenient because it can acquire relevant expertise early. [Proficiency](https://bg3.wiki/wiki/Proficiency#Expertise).

For a normal roll:

```text
check total = d20 + Dexterity modifier + skill contribution + other bonuses

skill contribution:
  no proficiency: 0
  proficiency:    proficiency bonus
  expertise:      2 × proficiency bonus

ordinary success: check total >= object's DC
```

The default proficiency bonus is +2 at character levels 1–4, +3 at 5–8, and +4 at 9–12. Expertise doubles that contribution; it does not add another double bonus on top of proficiency. Rogues select expertise at rogue levels 1 and 6; bards at bard levels 3 and 10. [Proficiency](https://bg3.wiki/wiki/Proficiency).

BG3 ability checks also have critical outcomes: an unmodified **1 fails** and an unmodified **20 succeeds**, subject to features that replace or reroll the die. These rules differ from ordinary tabletop 5e skill checks. [Dice rolls](https://bg3.wiki/wiki/Dice_rolls#Natural_1s_and_20s).

### Reattempts and Inspiration

A failed ordinary lockpick attempt can be tried again with another set of tools. The roll interface can also offer **Inspiration**, which rerolls the failed check with its modifiers and advantage/disadvantage. Inspiration is shared by the party, capped at four points, and is distinct from the bard's Bardic Inspiration. [Inspiration](https://bg3.wiki/wiki/Inspiration#Spending_Inspiration).

A lock that permits attempts at **DC 99** is consequently different from an object that offers no lockpicking interaction. The Counting House entrance to the High Security Vaults explicitly permits repeated attempts until a critical success. Its intended alternatives include the pressure-plate passcode and an electrical short circuit. [The Counting House](https://bg3.wiki/wiki/The_Counting_House#High_Security_Vaults).

### Alternatives to picking a lock

| Method | What it does and its limits | Source |
| --- | --- | --- |
| Matching key | Opens its corresponding lock without the lockpicking roll. Whether it also bypasses a trap is object-specific; see the evidence caution in section 9. | [Underground Passage](https://bg3.wiki/wiki/Underground_Passage) |
| **Knock** | Level-2 spell: one Action and a level-2 spell slot; listed range 18 m. Opens eligible mundane locks regardless of lockpick DC. Resistant locks have an identifying status. | [Knock](https://bg3.wiki/wiki/Knock) |
| Attack the object | Many destructible containers expose their contents after destruction. Check the actual object's defenses and any nearby trap effects. | [Thieves' Tools](https://bg3.wiki/wiki/Thieves%27_Tools) |
| Lever, code, or environmental solution | Some doors have a separate authored opening mechanism; others cannot be picked. | [Overgrown Ruins](https://bg3.wiki/wiki/Overgrown_Ruins), [Sorcerous Vault](https://bg3.wiki/wiki/Sorcerous_Vault) |

Knock is not a general-purpose trap-disarming spell. It can also attract attention: the wiki treats casting it on owned property as a crime, with possible investigation or hostility. Particular scripted exceptions exist, including Selûne's sealed chest in section 7. [Knock](https://bg3.wiki/wiki/Knock#Notes).

## 3. Finding and disarming traps

### Detection is usually an automatic roll

World detection normally uses **Wisdom (Perception)** when a character comes close enough. BG3 actually makes a skill roll automatically. Walkthroughs frequently call this “passive Perception,” but it is not generally the tabletop fixed score of `10 + modifiers`. True passive Perception has other uses in BG3, particularly NPC detection of hiding creatures. [Perception](https://bg3.wiki/wiki/Perception#World_perception).

Party members make their own detection checks, so one failure does not prevent another member from discovering the trap. Revealing a trap normally makes its disarm interaction available. [Trap: detection](https://bg3.wiki/wiki/Trap#Detection).

Exceptions documented in this research include:

| Object/location | Detection check |
| --- | --- |
| Crèche hatchery teleportation glyphs | **Investigation 15**. [Teleporting Trap](https://bg3.wiki/wiki/Teleporting_Trap) |
| Requisitioned Barn explosive toy crate | **Investigation 15**. [Requisitioned Barn](https://bg3.wiki/wiki/Requisitioned_Barn) |
| Ramazith's Tower middle-floor Cloudkill vents and Arcane Cannons | **Arcana 15**. [Ramazith's Tower](https://bg3.wiki/wiki/Ramazith%27s_Tower) |
| Counting House Alarm Machines | Visible devices; no hidden-trap detection check is required. [Alarm Machine](https://bg3.wiki/wiki/Alarm_Machine) |

Inspiration cannot reroll the ordinary background rolls used during exploration. Prepare bonuses before approaching, and use another party member after a failed detection rather than expecting an Inspiration prompt. [Inspiration](https://bg3.wiki/wiki/Inspiration#Spending_Inspiration).

### Toolkit procedure and consequences

For an ordinary disarmable trap, have a **Trap Disarm Toolkit** available to the acting character, select **Disarm**, and make the Sleight of Hand check. Success normally deactivates the trap without spending the kit. A failed attempt consumes the kit and triggers the hazard. [Trap Disarm Toolkit](https://bg3.wiki/wiki/Trap_Disarm_Toolkit).

The crucial difference from lockpicking is the consequence of failure. **Another toolkit is not a safe undo.** The wiki's Inspiration page says rerolling through Inspiration avoids triggering the trap, whereas choosing another toolkit does not prevent activation. Its Trap page summarizes this as failure not being freely retryable with another kit. Once a persistent mechanism has activated, whether it can subsequently be disabled depends on that mechanism. [Inspiration](https://bg3.wiki/wiki/Inspiration#Spending_Inspiration), [Trap: disarming](https://bg3.wiki/wiki/Trap#Disarming).

For a trapped, locked chest, keep these facts separate:

```text
detect the trap -> deal with the trap -> unlock the chest -> open/loot
```

This is a practical interaction sequence, not a claim that every chest implements the same trigger. Disarming the trap does not by itself establish that its lock is open. The Underground Passage chest, for example, has Perception 10, disarm 10, and lockpick 15. [Underground Passage](https://bg3.wiki/wiki/Underground_Passage).

### A useful exploration procedure

The following is a practical synthesis of the documented mechanics:

1. Stop the party after a detection warning; separate the disarmer from companions near a dangerous area.
2. Inspect the surroundings for linked plates, emitters, explosive barrels, gas, and drop hazards.
3. Apply the relevant bonuses before the roll. Choose a character for its actual skill total, not merely its class name.
4. Consider a switch, blocked vent, or safe route before attempting a very high DC.
5. Use turn-based mode where movement timing matters. Do not assume activation always gives a harmless grace period.
6. After success, check for other triggers and emitters before bringing the party through.

Several traps form a connected system. In the Dank Crypt, disabling the central sarcophagus prevents the linked room trap; its pillar button can stop an already activated system. Pressing that button beforehand does not prevent later activation. [Overgrown Ruins: trapped sarcophagus](https://bg3.wiki/wiki/Overgrown_Ruins#Trapped_sarcophagus).

**Success is not universally harmless:** the Incineration Caster page explicitly reports an explosion on successful disarming. That exception is retained below rather than hidden behind the general toolkit rule. [Incineration Caster](https://bg3.wiki/wiki/Incineration_Caster).

## 4. Improving success chances

### Skills and features

Sleight of Hand proficiency can come from sources other than rogue levels, including **Charlatan** or **Urchin** backgrounds, bard choices, and ranger's **Urban Tracker** option. A separate high-Perception scout can help find traps even if another character performs the disarm. [Sleight of Hand](https://bg3.wiki/wiki/Sleight_of_Hand).

**Reliable Talent**, obtained at rogue level 11, turns die results below 10 into 10 on proficient skill checks, including natural 1. Bonuses are added afterward. With sufficient modifiers, an ordinary lockpick or disarm check can therefore become guaranteed. This requires rogue class level 11, not simply total character level 11. [Reliable Talent](https://bg3.wiki/wiki/Reliable_Talent).

**Halfling Luck** rerolls an initial natural 1 and keeps the replacement. It greatly reduces critical failures but does not guarantee success. [Halfling Luck](https://bg3.wiki/wiki/Halfling_Luck).

**Advantage** means rolling two d20s and taking the higher. Multiple advantage sources do not grant more dice, and any disadvantage cancels advantage. A source of advantage on Dexterity checks helps disarming but does not necessarily help the separate saving throw against the resulting trap. [Advantage](https://bg3.wiki/wiki/Advantage), [Enhance Ability](https://bg3.wiki/wiki/Enhance_Ability).

### Practical bonuses and equipment

This is a selected, useful set rather than an exhaustive equipment build catalogue.

| Source | Relevant benefit | Acquisition/constraint |
| --- | --- | --- |
| [Guidance](https://bg3.wiki/wiki/Guidance) | +1d4 to ability checks. | Cantrip; concentration; 10 turns. The Silver Pendant grants access. |
| [Enhance Ability](https://bg3.wiki/wiki/Enhance_Ability) | Cat's Grace: advantage on Dexterity checks. Owl's Wisdom is the corresponding choice for Perception. | Level-2 spell; concentration. |
| [Gloves of Power](https://bg3.wiki/wiki/Gloves_of_Power) | +1 Sleight of Hand. | Za'krug at the Grove entrance encounter. |
| [Smuggler's Ring](https://bg3.wiki/wiki/Smuggler%27s_Ring) | +2 Sleight of Hand, +2 Stealth; −1 Charisma. | Skeleton on the Risen Road river path, approximately X:58 Y:516. |
| [Gloves of Thievery](https://bg3.wiki/wiki/Gloves_of_Thievery) | Advantage on Sleight of Hand. | Brem's expanded stock after the Missing Shipment quest. |
| [The Graceful Cloth](https://bg3.wiki/wiki/The_Graceful_Cloth) | Advantage on Dexterity checks; +2 Dexterity, capped at 20. | Lady Esther, Rosymorn Monastery Trail. Its separate saving-throw bonus is not another +1 to Sleight of Hand. |
| [Shapeshifter's Boon Ring](https://bg3.wiki/wiki/Shapeshifter%27s_Boon_Ring) | +1d4 to ability checks while disguised/shapeshifted. | Associated with the Strange Ox. Equip before transforming; the source documents application restrictions. |
| [Bliss Spores](https://bg3.wiki/wiki/Bliss_Spores_%28condition%29) | +1d6 to ability checks until long rest. | A quest reward from Spaw; temporary rather than a permanent build feature. |
| [Bardic Inspiration](https://bg3.wiki/wiki/Sleight_of_Hand#Ways_to_boost_or_penalize) | An additional die, normally d6/d8/d10 according to progression. | A limited support resource, separate from party Inspiration rerolls. |

Gloves of Power and Gloves of Thievery occupy the same slot. A way to combine the former's flat bonus with advantage is to obtain advantage elsewhere, such as the Graceful Cloth. Do not count several copies of advantage as cumulative bonuses.

### Worked modifier examples

These are arithmetic examples from the sourced bonuses, not prescribed builds:

- At levels 1–4, Dexterity 16 (+3), Sleight of Hand expertise (+4), Smuggler's Ring (+2), and Gloves of Power (+1) give **+10**, before Guidance or other bonuses.
- At rogue level 11, Dexterity 20 (+5), expertise (+8), the ring (+2), and the gloves (+1) give **+16**. Reliable Talent makes the minimum total **26**; Guidance raises that minimum to **27** while active. DC 30 is still not guaranteed by this combination alone.

### Probability examples

Calculated for ordinary independent d20 rolls, natural-1 failure/natural-20 success, a fixed bonus, and no rerolls, additional bonus dice, or Reliable Talent. “Adv.” uses the higher of two dice.

| DC | +5 | +5 Adv. | +10 | +10 Adv. | +15 | +15 Adv. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 80% | 96% | 95% | 99.75% | 95% | 99.75% |
| 15 | 55% | 79.75% | 80% | 96% | 95% | 99.75% |
| 20 | 30% | 51% | 55% | 79.75% | 80% | 96% |
| 25 | 5% | 9.75% | 30% | 51% | 55% | 79.75% |
| 30 | 5% | 9.75% | 5% | 9.75% | 30% | 51% |

For ordinary success probability `p`, advantage gives `1 - (1 - p)^2`. The 5% floors and 95% ceilings here follow from critical outcomes; Reliable Talent changes those assumptions. Even a high modifier cannot remove the ordinary natural-1 risk by itself.

The current wiki's Karmic Dice analysis says its forced-success mechanic does **not** apply to non-dialogue checks such as lockpicking or world Perception. It should not be described as a general lockpicking aid. [Dice rolls: Karmic Dice](https://bg3.wiki/wiki/Dice_rolls#Karmic_Dice).

### Dungeon Delver and difficulty settings

Dungeon Delver has two relevant passives: advantage on Perception checks involving hidden objects, and advantage on saves against traps plus resistance to trap damage. The latter applies to actions carrying the game's `IsTrap` flag. It is not expertise or a direct bonus to the disarm check. Both passive pages say their effects were missing before Patch 6, so early guides calling the feat entirely nonfunctional are outdated. [Dungeon Delver: Perception](https://bg3.wiki/wiki/Dungeon_Delver:_Perception), [Dungeon Delver: Resist Traps](https://bg3.wiki/wiki/Dungeon_Delver:_Resist_Traps).

Explorer and Custom settings can affect proficiency bonuses. Custom mode can also hide failed Perception rolls or hide DCs on lockpick/disarm prompts. Consequently, compare the actual character bonus and settings when reproducing a reported check. The sources inspected do not establish a universal “add N to every trap DC on Tactician” rule. [Difficulty](https://bg3.wiki/wiki/Difficulty).

## 5. Trap-family catalogue

These 24 rows cover the named families/mechanisms in the main wiki catalogue, with Sanguine and Stunner Vents separated into their own rows. A family row is not an exhaustive list of placements. Damage descriptions are illustrative; use the specific instance's behavior where available.

| # | Trap/mechanism | Published disarm DC | Behavior, location, and qualifications | Source |
| --- | --- | --- | --- | --- |
| 1 | Tripwire | **10+** | Crossing a cord triggers an effect or linked devices. Ordinary explosive examples deal 2d6 Fire. Local instances can be harder. | [Tripwire](https://bg3.wiki/wiki/Tripwire) |
| 2 | Blast Mine | **15+** | Includes fire, turquoise Underdark, and poison variants. Poison variants also create a cloud; its stated three-turn duration is marked for verification. | [Blast Mine](https://bg3.wiki/wiki/Blast_Mine) |
| 3 | Vent | **10+** | Triggered or continuously emitting; effects include grease, poison, toxin, and void. High-DC exceptions exist. | [Vent](https://bg3.wiki/wiki/Vent) |
| 4 | Gargoyle Head | **10+** | Wall-mounted emitter, often plate-linked; fire projectiles, with cold variants in the Sorcerous Vault. | [Gargoyle Head](https://bg3.wiki/wiki/Gargoyle_Head), [catalogue DC](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 5 | Gargoyle Statue | **10+** | Freestanding emitter; fire jets or projectiles. Grymforge variants can push or knock targets prone. | [Gargoyle Statue](https://bg3.wiki/wiki/Gargoyle_Statue), [catalogue DC](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 6 | Marble/pressure plate | **10+** | A trigger, not necessarily the damaging component. Disabling a controlling plate can prevent its linked trap from activating. | [Marble Plate](https://bg3.wiki/wiki/Marble_Plate) |
| 7 | Trapped object | **10+** in generic catalogue | Chests, doors, bookshelves, and other interactions can carry traps; the effect and actual DC belong to the placement. | [Trapped Object](https://bg3.wiki/wiki/Trapped_Object), [catalogue DC](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 8 | Peculiar Flower | **10** | Ethel's lairs, Acts I/III. Detect: Perception **15**. Fire explosion can ignite nearby noxious gas. | [Peculiar Flower](https://bg3.wiki/wiki/Peculiar_Flower) |
| 9 | Proximity Explosive | **10** | Zhentarim Hideout. Proximity/color warning followed by detonation on the environment turn; a shared button controls the system. | [Proximity Explosive](https://bg3.wiki/wiki/Proximity_Explosive) |
| 10 | Repulsion Mine | **10** | Monastery trail and crèche hatchery. Detect: Perception **15**. Push hazard; effect save: Dexterity **13**. | [Repulsion Mine](https://bg3.wiki/wiki/Repulsion_Mine) |
| 11 | Teleporting Trap | **N/A: cannot directly disarm** | Hatchery glyphs use Investigation **15** to detect. Counting House glyphs can be switched off through their control buttons. | [Teleporting Trap](https://bg3.wiki/wiki/Teleporting_Trap) |
| 12 | Gas Pit | **NR** | Hatchery hazard emitting Strange Gas beneath/among acid pools. The catalogue supplies no toolkit DC. | [Crèche Y'llek](https://bg3.wiki/wiki/Cr%C3%A8che_Y%27llek#Hatchery), [catalogue](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 13 | Dawnbreaker | **14** | Secret Chamber near the Blood of Lathander. Radiant pulse, knockdown, and displacement; nearby chasms are the major danger. | [Dawnbreaker](https://bg3.wiki/wiki/Dawnbreaker) |
| 14 | Selûnite Outpost defense | **N/A: power-source solution** | Moonstone-powered statues fire radiant artillery. Destroy the Moonstone to disable the defense. | [Selûnite Outpost](https://bg3.wiki/wiki/Sel%C3%BBnite_Outpost) |
| 15 | Arcane Turret / related Arcane Cannon | **N/A in catalogue** | Turrets are stationary constructs. Arcane Tower examples can be destroyed, suppressed with Sussur Bloom, or deactivated by restoring tower power. Do not automatically transfer that tower-specific solution to every cannon. | [Arcane Turret](https://bg3.wiki/wiki/Arcane_Turret), [catalogue](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 16 | Trapped Beacon | **15** | Grymforge gallery. Flame attacks every two turns; disarm failure can activate the entire linked gallery. | [Trapped Beacon](https://bg3.wiki/wiki/Trapped_Beacon) |
| 17 | Spike Trap | **10** | Putrid Bog deep water. Detect: Perception **15**. Causes Bleeding/Open Wound; remains dangerous after activation. | [Sunlit Wetlands: hazards](https://bg3.wiki/wiki/Sunlit_Wetlands#Hazards) |
| 18 | Boulder Trap | **NR for boulder** | Risen Road cave: two disarmable tripwires release a rolling boulder. The location page does not state their DCs. | [The Risen Road](https://bg3.wiki/wiki/The_Risen_Road#Cave) |
| 19 | Alarm Machine | **15** | Five devices in/around the Counting House. Summons nearby guards rather than directly dealing trap damage; interacting openly can draw attention. | [Alarm Machine](https://bg3.wiki/wiki/Alarm_Machine) |
| 20 | Aspect of Athkatla | **N/A: cannot directly disarm** | Ramazith's Tower. Its associated barrier uses **Arcana 20**; failure causes Disintegrate. That is not Sleight of Hand 20. | [Aspect of Athkatla](https://bg3.wiki/wiki/Aspect_of_Athkatla) |
| 21 | Grenade Impeller | **10 — uncertain** | Wyrm's Rock launcher. DC 10 is marked “verify” in the catalogue and absent from the individual page's disarm instructions. | [catalogue](https://bg3.wiki/wiki/Trap#List_of_traps), [Grenade Impeller](https://bg3.wiki/wiki/Grenade_Impeller) |
| 22 | Incineration Caster | **10 — source qualification** | Wyrm's Rock. Individual page explicitly reports DC 10 and explosion on success; overview still marks its DC for verification. | [Incineration Caster](https://bg3.wiki/wiki/Incineration_Caster), [catalogue](https://bg3.wiki/wiki/Trap#List_of_traps) |
| 23 | Sanguine Vent | **10** | Bridge toward Bhaal Temple. Detect: Perception **15**. Releases Unstable Blood, which explodes on contact with fire. | [Sanguine Vent](https://bg3.wiki/wiki/Sanguine_Vent) |
| 24 | Stunner Vent | **10** | Wyrm's Rock rooftop. Detect: Perception **15**. Fire explosion followed by a possible stun; Constitution **15** to avoid the stun. | [Stunner Vent](https://bg3.wiki/wiki/Stunner_Vent) |

## 6. Location-specific trap and DC catalogue

**Detect defaults to Perception unless named otherwise. Disarm and Lock default to Sleight of Hand.** A dash means no corresponding lock operation in this row, not a failed search for a numerical DC. Coordinates are included only where the source gives them and help identify the object.

### Act I

| Location/object | Detect | Disarm | Lock | Notes/source |
| --- | ---: | ---: | ---: | --- |
| Dank Crypt central sarcophagus | 15 | **10** | — | **Guide** values; central trigger for the room. [EIP: Overgrown Ruins Chapel](https://eip.gg/bg3/guides/overgrown-ruins-chapel/) |
| Dank Crypt floor vents | 15 | **10** | — | **Guide** values. [EIP](https://eip.gg/bg3/guides/overgrown-ruins-chapel/) |
| Dank Crypt wall gargoyle heads | 10 | **10** | — | **Guide** values. [EIP](https://eip.gg/bg3/guides/overgrown-ruins-chapel/) |
| Underground Passage heavy chest, X:-425 Y:-200 | 10 | **10** | **15** | Nature's Snare; nearby oil barrels amplify activation. [Underground Passage](https://bg3.wiki/wiki/Underground_Passage) |
| Apothecary's Cellar plate before the tome's gate | 15 | **10** | — | Gate itself is a separate **15** lock or Rusted Key. [Apothecary's Cellar](https://bg3.wiki/wiki/Apothecary%27s_Cellar) |
| Apothecary's Cellar two gargoyle statues | NR | **10 each** | — | Two of four disarmable devices around the Necromancy of Thay. [Apothecary's Cellar](https://bg3.wiki/wiki/Apothecary%27s_Cellar) |
| Apothecary's Cellar book-support pressure plate | NR | **10** | — | Removing the book changes the pressure arrangement. [Apothecary's Cellar](https://bg3.wiki/wiki/Apothecary%27s_Cellar) |
| Overgrown Tunnel Peculiar Flowers | 15 | **10** | — | Flowers and gas vents have different DCs. [Peculiar Flower](https://bg3.wiki/wiki/Peculiar_Flower) |
| Overgrown Tunnel noxious-gas vents | 15 | **30** | — | **Guide** values. Covering the aperture provides an alternative. [EIP: Teahouse](https://eip.gg/bg3/guides/teahouse/) |
| Putrid Bog submerged spike traps | 15 | **10** | — | Not consumed by triggering. [Sunlit Wetlands](https://bg3.wiki/wiki/Sunlit_Wetlands#Hazards) |
| Zhentarim Hideout proximity bombs | Visible | **10** | — | Linked arming button at X:292 Y:-181. [Proximity Explosive](https://bg3.wiki/wiki/Proximity_Explosive) |
| Monastery trail repulsion mines | 15 | **10** | — | Three listed positions around X:-71 Y:-40 to X:-63 Y:-26. [Repulsion Mine](https://bg3.wiki/wiki/Repulsion_Mine) |
| Crèche hatchery repulsion mines | 15 | **10** | — | Can throw characters into acid or glyphs. [Repulsion Mine](https://bg3.wiki/wiki/Repulsion_Mine) |
| Crèche hatchery teleporting glyphs | **Investigation 15** | N/A | — | Direct toolkit disarm unavailable. [Teleporting Trap](https://bg3.wiki/wiki/Teleporting_Trap) |
| Secret Chamber's two Dawnbreakers | NR | **14 each** | — | Adjacent blind spots offer a bypass. [Dawnbreaker](https://bg3.wiki/wiki/Dawnbreaker) |
| Grymforge gallery Trapped Beacons | NR | **15 each** | — | Each is disarmed separately; failure can activate the network. [Trapped Beacon](https://bg3.wiki/wiki/Trapped_Beacon) |
| Risen Road cave boulder-trigger tripwires | NR | **NR** | — | Two triggers documented; do not substitute the generic 10 automatically. [The Risen Road](https://bg3.wiki/wiki/The_Risen_Road#Cave) |

### Act II

| Location/object | Detect | Disarm | Lock | Notes/source |
| --- | ---: | ---: | ---: | --- |
| Grand Mausoleum northern chamber mechanisms | 10 | **NR** | — | Wiki says these have already been disarmed, though the interaction can remain available. [Grand Mausoleum](https://bg3.wiki/wiki/Grand_Mausoleum) |
| Gauntlet entrance lever-alcove pressure plates and vents | NR | **10** | — | Void Cloud system. [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar) |
| Silent Library bookshelves | 15 | **14** | — | Acid Splash traps can destroy books. [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar#Silent_Library) |
| Silent Library incorrect column buttons | NR | **NR** | — | Reported Chain Lightning triggers; not the safe gate-opening button. [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar#Silent_Library) |
| Silent Library four vents around the Riddle of the Night | NR | **21** | — | Tentacle-like surface. The library gate has a separate **21** lock. [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar#Silent_Library) |
| Mason's Guild reinforced chest, X:104 Y:-700 | 15 | **14** | **14** | Failure encloses the character and reveals three gargoyle emitters. [Mason's Guild](https://bg3.wiki/wiki/Mason%27s_Guild) |
| Mason's Guild chest behind the altar | 15 | **21** | **14** | Guiding Bolt trap; Helmet of Arcane Acuity inside. [Mason's Guild](https://bg3.wiki/wiki/Mason%27s_Guild) |
| Waning Moon laboratory storage-cage door, X:-258 Y:-96 | 15 | **14** | **5** | An especially clear example of disarm and lock DCs differing. [The Waning Moon](https://bg3.wiki/wiki/The_Waning_Moon) |
| House of Healing Morgue, Eversight Ring chest, X:9 Y:-981 | NR | **14** | **14** | Source explicitly gives two separate checks. [House of Healing](https://bg3.wiki/wiki/House_of_Healing) |

### Act III

| Location/object | Detect | Disarm | Lock | Notes/source |
| --- | ---: | ---: | ---: | --- |
| Arfur's basement metal chest | NR | **15** | **20** | Contains the quest letter. [Arfur's Mansion](https://bg3.wiki/wiki/Arfur%27s_Mansion) |
| Arfur's basement firework traps | NR | **NR** | — | Successful disarms can yield Wogglims; do not apply the chest's DC to every firework. [Arfur's Mansion](https://bg3.wiki/wiki/Arfur%27s_Mansion) |
| Abandoned sidehouse by Arfur's mansion, trapped chest | 15 | **15** | **20** | Matching key exists. [Arfur's Mansion](https://bg3.wiki/wiki/Arfur%27s_Mansion) |
| Requisitioned Barn stuffed-bear crate | **Investigation 15** | **20** | — | Explosive toys; separate from the Donations chest. [Requisitioned Barn](https://bg3.wiki/wiki/Requisitioned_Barn) |
| Western Beach shipwreck Traveller's Chest, X:-90 Y:85 | 15 | **15** | **15** | Necklace of Elemental Augmentation. [Western Beach](https://bg3.wiki/wiki/Western_Beach) |
| Western Beach tripwires by broken statue, X:-118 Y:103 | NR | **18** | — | Steam-obscured area with five blast mines. Mine DCs not specified here. [Western Beach](https://bg3.wiki/wiki/Western_Beach) |
| Bruc and Pishe's Emporium basement hidden chest | 15 | **15** | NR | Separate mechanism exposes the chest. [Bruc and Pishe's Emporium](https://bg3.wiki/wiki/Bruc_and_Pishe%27s_Emporium) |
| Highberry's Home cellar heavy chest behind curtain | 15 | **10** | **15** | Source distinguishes it from the adjacent wooden chest. [Highberry's Home](https://bg3.wiki/wiki/Highberry%27s_Home) |
| Elerrathin's Home hidden cavern, trapped loose planks | 20 | **15** | — | Glyph of Warding: Acid; key beneath opens the bookcase. [Elerrathin's Home](https://bg3.wiki/wiki/Elerrathin%27s_Home) |
| Lower City Sewers, three refugee-route tripwires near X:-42 Y:789 | 17 | **15 each** | — | Explosions can kill fleeing refugees. [Lower City Sewers](https://bg3.wiki/wiki/Lower_City_Sewers) |
| Lower City Sewers entry gas-room vents | NR | **10** | — | **Guide** DC; a lever is another solution. [EIP: City Sewers](https://eip.gg/bg3/guides/city-sewers-undercity-ruins/) |
| Bhaal Temple approach bridge Sanguine Vents | 15 | **10** | — | Flammable Unstable Blood. [Sanguine Vent](https://bg3.wiki/wiki/Sanguine_Vent) |
| Counting House Alarm Machines | Not required | **15 each** | — | Five documented devices across the building and docks. [Alarm Machine](https://bg3.wiki/wiki/Alarm_Machine) |
| Counting House transposition glyphs | NR | N/A | — | Control buttons disable them; no direct toolkit interaction. [Teleporting Trap](https://bg3.wiki/wiki/Teleporting_Trap) |
| Ramazith's Tower middle-floor Cloudkill vents/cannons | **Arcana 15** | **NR** | — | Detection check applies to these defenses; no numerical toolkit DC established here. [Ramazith's Tower](https://bg3.wiki/wiki/Ramazith%27s_Tower) |
| Ramazith's Tower trapped display case | 13 | **15** | NR | Contains High Security Vault nº1 Key. [Ramazith's Tower](https://bg3.wiki/wiki/Ramazith%27s_Tower) |
| Ramazith's Tower barrier levers | See Invisibility | **Arcana 20**, not toolkit | — | Failure activates Aspect of Athkatla and prevents that character safely retrying the lever. [Ramazith's Tower](https://bg3.wiki/wiki/Ramazith%27s_Tower) |
| Szarr Palace subterranean puzzle: gas vents | NR | **25 each** | — | Pressure-plate system. [Szarr Palace](https://bg3.wiki/wiki/Szarr_Palace#Subterranean_puzzle_area) |
| Szarr Palace subterranean puzzle: gargoyle heads | NR | **25 each** | — | Same system; doors and final chest separately have **25** locks. [Szarr Palace](https://bg3.wiki/wiki/Szarr_Palace#Subterranean_puzzle_area) |
| House of Hope trapped portrait by Raphael's safe | **18 for hidden button** | **20** | **25, separate safe** | The 18 is documented for noticing the button; do not silently relabel it as the portrait's trap-detection DC. [Soul-Sworn Contract](https://bg3.wiki/wiki/Soul-Sworn_Contract), [Free Orpheus](https://bg3.wiki/wiki/Free_Orpheus) |
| Wyrm's Rock rooftop Stunner Vents | 15 | **10** | — | Stun is resisted separately with Constitution 15. [Stunner Vent](https://bg3.wiki/wiki/Stunner_Vent) |
| Wyrm's Rock Incineration Casters | NR | **10, qualified** | — | Successful disarm reportedly causes Overheat damage. [Incineration Caster](https://bg3.wiki/wiki/Incineration_Caster) |
| Wyrm's Rock Grenade Impellers | NR | **10, uncertain** | — | Overview marks the DC for verification. [Trap catalogue](https://bg3.wiki/wiki/Trap#List_of_traps) |
| Blushing Mermaid hag-lair Peculiar Flowers | 15 | **10** | — | Values documented on the mechanism page covering both lairs. [Peculiar Flower](https://bg3.wiki/wiki/Peculiar_Flower) |

## 7. Bypasses, special defenses, and consequences

### Blocking is different from disarming

A suitably placed object can block a vent's aperture and suppress its cloud. Removing that object can let the hazard return. Burning away noxious gas also does not disable the source; more gas can appear. These are environmental interactions, not successful toolkit rolls. [Vent](https://bg3.wiki/wiki/Vent), [GamesRadar: noxious fumes](https://www.gamesradar.com/baldurs-gate-3-noxious-fumes/).

The Ethel walkthrough explicitly contrasts the **DC 10 flowers** with **DC 30 vents** and describes covering the vents. This is why a report that “the hag's traps are DC 30” is too broad: it mixes two mechanisms in the same area. [EIP: Teahouse](https://eip.gg/bg3/guides/teahouse/).

### Control mechanisms and puzzles

| Defense | Alternative resolution | Source |
| --- | --- | --- |
| Zhentarim proximity network | Its control button toggles the network; peaceful admission affects initial activity. | [Proximity Explosive](https://bg3.wiki/wiki/Proximity_Explosive) |
| Counting House teleportation glyphs | Activate the two controls in the room. Glyph visuals may remain after deactivation. | [Teleporting Trap](https://bg3.wiki/wiki/Teleporting_Trap), [The Counting House](https://bg3.wiki/wiki/The_Counting_House) |
| Sorcerous Vault puzzle-room traps | Invisible levers disable the traps in their respective rooms. See Invisibility helps locate them. | [Sorcerous Vault](https://bg3.wiki/wiki/Sorcerous_Vault) |
| Szarr Palace pressure-plate puzzle | Weight all four relevant plates to deactivate the trap and open the forward door; removing a weight can reactivate it if not permanently disarmed. | [Szarr Palace](https://bg3.wiki/wiki/Szarr_Palace#Subterranean_puzzle_area) |
| Devil's Fee landing ward | Give the imp-head mechanism water or wine; balcony access can bypass the landing. No toolkit DC established here. | [Free Orpheus](https://bg3.wiki/wiki/Free_Orpheus) |
| Owlbear Nest Selûnite chest | Use the prayer-sheet interaction or an eligible Selûnite cleric. The wiki also explicitly reports Knock removing this particular seal. | [Selûne's Seal](https://bg3.wiki/wiki/Sel%C3%BBne%27s_Seal_%28Condition%29) |

### Activation can change more than hit points

- **Linked components:** Grymforge combines pressure plates, beacons, and statues; triggering one can activate the system. Beacons and statues have different firing schedules. [Trapped Beacon](https://bg3.wiki/wiki/Trapped_Beacon).
- **Environmental displacement:** Repulsion Mines and Dawnbreakers can make a modest-looking hit lethal by pushing a character into a chasm. Their source pages disagree internally on precise push distance, so this report does not select one number as authoritative. [Repulsion Mine](https://bg3.wiki/wiki/Repulsion_Mine), [Dawnbreaker](https://bg3.wiki/wiki/Dawnbreaker).
- **Changes to passage:** The Mason's Guild chest closes off the victim and exposes emitters. Disarm failure is an encounter-state change, not merely damage. [Mason's Guild](https://bg3.wiki/wiki/Mason%27s_Guild).
- **Loss of objects:** Silent Library traps and nearby area damage can destroy the required book. Successful navigation and preservation of the object matter separately. [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar#Silent_Library).
- **Delayed effects:** Bog spikes apply wounds that can worsen into disease. There is no initial save against the application described by the location page; later Constitution saves are distinct. [Sunlit Wetlands](https://bg3.wiki/wiki/Sunlit_Wetlands#Hazards).
- **Hostility:** Counting House alarms attract guards. An alarm's disarm DC therefore says nothing about a damage roll. [Alarm Machine](https://bg3.wiki/wiki/Alarm_Machine).

### Damage and save examples kept separate from disarm DCs

| Trap/effect | Disarm check | Triggered-effect detail |
| --- | --- | --- |
| Repulsion Mine | Sleight of Hand 10 | Dexterity save **13** against the push effect. [Source](https://bg3.wiki/wiki/Repulsion_Mine) |
| Stunner Vent | Sleight of Hand 10 | 2d6 Fire, then Constitution save **15** to avoid the reported three-turn stun. [Source](https://bg3.wiki/wiki/Stunner_Vent) |
| Selûnite Outpost artillery | Power-source solution | 2d6 Radiant; Dexterity save **12** halves damage. [Source](https://bg3.wiki/wiki/Sel%C3%BBnite_Outpost) |
| Owlbear Nest Selûne's Seal | Scripted alternatives | Dexterity save **14** avoids the listed 4d6 Radiant punishment. [Source](https://bg3.wiki/wiki/Sel%C3%BBne%27s_Seal_%28Condition%29) |
| Incineration Caster Overheat | DC 10 disarm reportedly causes it | 8d8 Fire in a 4 m radius; Dexterity save for half. Numerical save DC not established here. [Source](https://bg3.wiki/wiki/Incineration_Caster) |

Grenade Impeller ammunition has its own lifecycle: the source describes delayed detonation, and **Unstable Ballistics on Tactician/Honour prevents picking up the grenades**. Advice to collect every grenade is consequently not universal across difficulties. [Grenade Impeller](https://bg3.wiki/wiki/Grenade_Impeller).

## 8. Representative lock DCs

These are **lockpicking** examples, not additional disarm DCs. They show the practical spread and distinguish locks from scripted access restrictions.

| Act | Object | Lock DC | Alternative/qualification | Source |
| --- | --- | ---: | --- | --- |
| I | Overgrown Ruins, Chapel Entrance door | **7** | Dialogue can open it. | [Overgrown Ruins](https://bg3.wiki/wiki/Overgrown_Ruins) |
| I | Overgrown Ruins, Ancient Door approached from the beach | **20** | Other entrances and a key exist. | [Overgrown Ruins](https://bg3.wiki/wiki/Overgrown_Ruins) |
| I | Overgrown Ruins, exterior hatch | **20** | Another route into the crypt. | [Overgrown Ruins](https://bg3.wiki/wiki/Overgrown_Ruins) |
| I | Underground Passage heavy chest | **15** | Charred Key. | [Underground Passage](https://bg3.wiki/wiki/Underground_Passage) |
| I | Apothecary's Cellar tome gate | **15** | Rusted Key. | [Apothecary's Cellar](https://bg3.wiki/wiki/Apothecary%27s_Cellar) |
| II | Waning Moon laboratory storage cage | **5** | Separate disarm DC 14. | [The Waning Moon](https://bg3.wiki/wiki/The_Waning_Moon) |
| II | Mason's Guild Keyholed Herald | **18** | Tower-Shaped Key. | [Mason's Guild](https://bg3.wiki/wiki/Mason%27s_Guild) |
| II | Gauntlet of Shar vault near Balthazar | **30** | Knock works. | [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar) |
| II | Silent Library portcullis | **21** | Correct button or access to its lever. | [Gauntlet of Shar](https://bg3.wiki/wiki/Gauntlet_of_Shar#Silent_Library) |
| II | Reithwin Tollhouse safe at X:-83 Y:-60 | **30** | Nearby note gives its code. | [Reithwin Tollhouse](https://bg3.wiki/wiki/Reithwin_Tollhouse) |
| II | Morgue entrance to the Ominous Crevice | **30** | Two-lever solution. | [House of Healing](https://bg3.wiki/wiki/House_of_Healing) |
| III | Arfur's basement hatch | **18** | Toymaker's Basement Key. | [Arfur's Mansion](https://bg3.wiki/wiki/Arfur%27s_Mansion) |
| III | Arfur's basement metal chest | **20** | Separate disarm DC 15. | [Arfur's Mansion](https://bg3.wiki/wiki/Arfur%27s_Mansion) |
| III | Elerrathin's Home secret bookcase | **18** | Key under trapped planks. | [Elerrathin's Home](https://bg3.wiki/wiki/Elerrathin%27s_Home) |
| III | Counting House ordinary vaults | **25** | Corresponding vault keys. | [The Counting House](https://bg3.wiki/wiki/The_Counting_House) |
| III | Counting House High Security Vaults | **30** | Corresponding keys; Enchanted Security prevents Knock. | [The Counting House](https://bg3.wiki/wiki/The_Counting_House) |
| III | Door into Counting House High Security Vaults section | **99** | Critical success, code **1-3-5-6**, or electrified water. | [The Counting House](https://bg3.wiki/wiki/The_Counting_House) |
| III | Szarr Palace puzzle doors / final opulent chest | **25** | Pressure-plate solution also operates the doors. | [Szarr Palace](https://bg3.wiki/wiki/Szarr_Palace#Subterranean_puzzle_area) |
| III | Raphael's safe | **25** | Haarlep carries its key. Trap on nearby portrait is separately DC 20. | [Free Orpheus](https://bg3.wiki/wiki/Free_Orpheus) |
| III | Sorcerous Vault Elminster/Karsus doors | **Cannot lockpick** | Puzzle levers or Knock. This is distinct from a numerical DC 99. | [Sorcerous Vault](https://bg3.wiki/wiki/Sorcerous_Vault) |

Specific successful interactions can earn background Inspiration, such as the Risen Road's **Rock Steady** for disarming both boulder-trigger tripwires. Do not infer a universal per-trap XP award from those authored rewards or from BG1/BG2 rules. A current universal lockpick/disarm XP amount was not established in the reviewed sources. [Act One Inspiration](https://bg3.wiki/wiki/Act_One/Inspiration).

## 9. Source disagreements, outdated advice, and research limits

### Issues that materially affect interpretation

| Issue | Evidence and treatment in this report |
| --- | --- |
| “Passive Perception” terminology | The mechanics page distinguishes automatic world rolls from fixed passive scores. The former is used for ordinary trap detection here. [Perception](https://bg3.wiki/wiki/Perception) |
| Toolkit allegedly adds +1 | An older [EIP disarm guide](https://eip.gg/bg3/guides/how-to-disarm-traps/) claims a +1. The wiki tool descriptions do not list it. Player explanations identify the similar thieves-tools `x1` display as inventory quantity. **No intrinsic toolkit +1 is included in the calculations.** [Discussion](https://www.reddit.com/r/BaldursGate3/comments/18ezdo1/), [Toolkit](https://bg3.wiki/wiki/Trap_Disarm_Toolkit) |
| Key automatically neutralizes every trapped chest | There are [player reports](https://www.reddit.com/r/BaldursGate3/comments/1kqqdrb/) for specific objects, while [release-period guides](https://attackofthefanboy.com/guides/baldurs-gate-3-underground-passage-chest-how-to-get-the-charred-key/) still instruct disarming before using a key. **Not established as a universal rule.** |
| Grenade Impeller disarm DC | Overview explicitly marks **10** for verification. Kept uncertain. [Trap catalogue](https://bg3.wiki/wiki/Trap#List_of_traps) |
| Incineration Caster disarm DC and consequence | Overview marks **10** for verification; the individual page explicitly supplies 10 and says success causes Overheat. Both the numerical qualification and dangerous success behavior are preserved. [Incineration Caster](https://bg3.wiki/wiki/Incineration_Caster) |
| Precise knockback distances | Dawnbreaker prose and action block differ; Repulsion Mine prose and action block also differ. No single exact displacement is asserted here. [Dawnbreaker](https://bg3.wiki/wiki/Dawnbreaker), [Repulsion Mine](https://bg3.wiki/wiki/Repulsion_Mine) |
| Generic mine durability | The Blast Mine article's prose generalizes resistances, while its variants have different stat blocks. Examine the specific variant rather than copying a universal mine resistance profile. [Blast Mine](https://bg3.wiki/wiki/Blast_Mine) |
| Highberry's adjacent wooden chest | The location article calls one lockpicking check “Perception 20,” apparently a labeling error. That uncertain row is excluded; the separately described heavy chest is retained. [Highberry's Home](https://bg3.wiki/wiki/Highberry%27s_Home) |
| Tabletop Arcane Trickster assumptions | Current Mage Hand Legerdemain text establishes invisibility and permanence. It does not establish tabletop-style remote lockpicking/disarming, so that capability is not assumed. [Mage Hand Legerdemain](https://bg3.wiki/wiki/Mage_Hand_Legerdemain) |
| Old Dungeon Delver bug reports | Both relevant passive pages say the missing effects were fixed with Patch 6. See section 4. |

### What remains unknown

- **A complete placement census:** no public, current, version-qualified table covering every placed trap and its detection/disarm/effect DC was established in this research.
- **Some instance DCs:** NR entries retain genuine gaps rather than borrowing another member of the same trap family.
- **A universal turn cost, interaction range, and detection retry/reset rule:** the inspected reference pages do not establish these precisely enough to present as engine constants. They would need direct game or game-data verification.
- **Universal key/trap coupling and exact toolkit consumption after an Inspiration rescue:** the sources establish the ordinary failure rule and the ability to reroll safely with Inspiration, but not every inventory/trigger edge case.
- **Patch/difficulty parity:** pages do not consistently attach a build number and difficulty to each DC. Current page access is not a substitute for testing every difficulty.

### Source map for further lookup

Use the linked source in each table row for the exact claim. The most productive entry points are:

1. [BG3 Wiki: Trap](https://bg3.wiki/wiki/Trap) — broad mechanism index and links to specific traps.
2. [BG3 Wiki: Category:Traps](https://bg3.wiki/wiki/Category:Traps) — individual mechanism pages; incomplete as a placement inventory.
3. [BG3 Wiki: Sleight of Hand](https://bg3.wiki/wiki/Sleight_of_Hand), [Perception](https://bg3.wiki/wiki/Perception), and [Inspiration](https://bg3.wiki/wiki/Inspiration) — core interaction rules.
4. Location pages linked throughout section 6 — usually the best source for object-specific DCs.
5. [EIP: Teahouse](https://eip.gg/bg3/guides/teahouse/), [Overgrown Ruins Chapel](https://eip.gg/bg3/guides/overgrown-ruins-chapel/), and [City Sewers](https://eip.gg/bg3/guides/city-sewers-undercity-ruins/) — explicit supplementary DCs, marked Guide in the tables.

The report is an original synthesis with short factual paraphrases and attribution, not a copied walkthrough. Wiki content and its applicable attribution/licensing terms are described on [BG3 Wiki: Copyrights](https://bg3.wiki/wiki/bg3wiki:Copyrights).
