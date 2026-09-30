# SRD-first roster: crossed anti-slop review

Date: 30 September 2026. Status: **approved for the requested content-design
study**, after the corrections below. No implementation, balance or gameplay
parity is approved by this record.

## Independent review scopes

Different authors reviewed each controlling table. This is a crossed review,
not a claim that one separate reviewer authored a comprehensive fourth roster.

| Reviewed deliverable | Writer | Independent anti-slop reviewer | Result |
| --- | --- | --- | --- |
| [65 Orc/Goblin/Demon rows](PACK_ROSTER_SRD_FIRST_ORC_DEMON_2026-09-30.md) | `/root/native_composition` | `/root/animal_dinosaur_coverage` | Approved after Erinyes and Imp corrections; root also checked selected gear math and documentation |
| [100 Undead/Enemy/Zombie rows](PACK_ROSTER_SRD_FIRST_UNDEAD_ENEMY_2026-09-30.md) | `/root` | `/root/native_composition` | Approved after proficiency clarification and ZombieCop4 reinspection/loadout decision |
| [94 Animal/Dinosaur/humanoid rows](PACK_ROSTER_SRD_FIRST_ANIMAL_DINOSAUR_2026-09-30.md) | `/root/animal_dinosaur_coverage` | `/root` | Approved after direct source and conversion corrections |
| [Reconciled synthesis](../ART_LED_NPC_ROSTER_DESIGN_2026-09-30.md) | `/root` | `/root/animal_dinosaur_coverage` | Counts, source priority and secondary-source distinctions checked; no blocker |

The separate [anti-OOP/ECS review](PACK_ROSTER_SRD_FIRST_ANTI_OOP_REVIEW_2026-09-30.md)
independently covers all three tables and the synthesis. Reviewer findings and
follow-up approvals were exchanged within this task; this document records
their actual scopes and resolutions.

## Source-fidelity corrections completed

- The search boundary is the full 317-name SRD 5.1 creature index and selected
  official source blocks, rather than the implemented local subset. Missing
  factories remain readiness gaps. Selected caster profiles retain complete
  source spell lists/slots; earlier two-spell designs are superseded.
- Erinyes retains its actual 5.1 Truesight, flight, Magic Resistance, Hellish
  Weapons and three-attack Multiattack. Unsupported Devil's Sight and Parry
  claims were removed. Its chosen mace uses STR18/PB4: +8, 1d6+4 bludgeoning
  plus the retained 3d8 poison. The wingless artwork's flight gap is explicit.
- The 5.1 Ape keeps 1d6+3 for both Fist and Rock with no Rock recharge; Boar
  keeps slashing Tusk/Charge; Axe Beak keeps +4, 1d8+2 slashing; Goat remains
  Medium; Tiger Bite uses 1d10+3; Draft Horse has no Beast of Burden; Lion
  retains Running Leap. Source page spans and Mastiff's uncapped prone rider
  were corrected. These are source corrections, not newly designed powers.
- Crocodile retains its 5.1 Bite/grapple/restrain with no target-size cap.
  Ankylosaurus's converted Tail retains the Huge-or-smaller prerequisite and
  uses a DC14 Strength save for Prone. Allosaurus's converted approach/Claws
  sequence uses a DC14 Strength save and bonus-action Bite instead of the
  5.2 automatic prone/free follow-up attack. Hippopotamus explicitly maps its
  ordinary attacks, rolled initiative and proficient Strength save to 5.1.
- Replacement gear has explicit proficiency decisions and derived AC/attacks.
  Half-plate barding replaces the natural AC formula; it does not stack with
  it. ZombieCop4's reviewed protective kit selects a conservative Studded
  Leather analogue, AC10, as a real loadout rather than an unexplained costume.
  Caster component supplies/free-hand requirements remain actual 5.1 rules.
- Seven converted Musket loadouts retain 1d12, range40/120, ammunition,
  Loading and Two-Handed while dropping 5.2 mastery. Loading permits one
  shot per action. The Scout's actual generic two-melee-attack branch can
  supply two ordinary unarmed fallback strikes (+2, 1 damage each); it does
  not permit a second Musket shot. Three Ogre Zombie adaptations borrow Slam
  only and retain 5.1 defenses/Fortitude without 5.2 exhaustion immunity.
- Earlier reports and review snapshots have prominent authority notices.
  Their old custom kits are not competing current selections. The synthesis
  identifies the three revised tables and the later Brute/Cop4 reinspections.

## Coverage verification

The [revised reconciliation](../../.runtime/pack-study-20260930/srd-first/roster_coverage.json)
compares exact `(pack, literal source family)` keys with all ten inventories:
**259 rows, zero missing, extra or duplicate keys**. Each primary table has
the same number of cells as its header. All selected 5.1 creature names are
present in the complete source index, including the named ancestry and mount
components. This is a documentation check, not an execution test.

| Primary source | Variants |
| --- | ---: |
| SRD 5.1 | 240 |
| SRD 5.2 creature, explicitly adapted to 5.1 | 9 |
| No suitable source profile selected | 10 |
| Total | 259 |

The fit labels separately reconcile to 15 exact, 92 cosmetic, 64 loadout,
78 adapted and 10 no-fit entries. Thus 249 SRD-based proposals does **not**
mean 249 unchanged or exact matches. Nine primary 5.2 rows are Hippo, five
Allosaurus-based dinosaurs and three Ankylosaurus-based dinosaurs. Borrowed
Musket gear and Ogre Zombie Slam are secondary details on 5.1 primary blocks.

## Approval limits

The revised tables are complete, traceable design proposals under the corrected
source priority. No remaining study blocker was found after the follow-up
checks. Actual source-profile fidelity in the engine, new content, ammunition,
Loading, mount relations, armor wearability, intrinsic ranged delivery,
animation bindings, encounter tuning and exact presentation markers require
their later authorized work. No production content, art import or runtime test
was added by this review.
