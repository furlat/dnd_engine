# Native fiend authoring evidence — 2026-10-18

All 34 source variants now resolve to native public recipes: **28 new kits and six existing identities retained**. The new kits live in `dnd/monsters/remaining_fiends.py`; the builtin inventory includes all 28 roots and 16 exact Multiattack configurations. The accompanying JSON records actual materialization through `materialize_creature`, including HP, AC, ability scores, real gear, innate source providers, spell ranks and finite resources. It is evidence for this authoring batch, not a runtime registry.

Sources: the authored Devil draft (October 1), the later ability dispositions and accepted item crosswalk (October 2), the cleanup/summoning decisions (October 3–4), and the current authoring plan (October 18). Later explicit decisions take precedence. These are independent authored Fiend profiles, rather than Humanoid stat-block foundations. The two armed Imps retain their selected Imp foundation with the omissions recorded below. Source CR columns remain provisional design targets; no encounter balance certification is claimed.

## Literal source reconciliation

| Source variant | Profile | Current native identity | HP / AC | Status |
| --- | --- | --- | --- | --- |
| Demon Beast 1 | C01 | `content.srd_5_1_cc:creature:creature.dretch@1` | 22 / 11 | Existing canonical Demon preserved |
| Demon Beast 2 | C02 | `content.neurodragon:creature:creature.corrosive_demon@1` | 22 / 11 | Existing canonical Demon preserved |
| Demon Beast 3 | C03 | `content.neurodragon:creature:creature.dread_demon@1` | 22 / 11 | Existing canonical Demon preserved |
| Demon Beast 4 | C04 | `content.neurodragon:creature:creature.fellwing_devil@1` | 136 / 16 | Existing authored Devil preserved |
| Demon Beast 5 | C05 | `content.neurodragon:creature:creature.huntsman_wing_devil@1` | 93 / 16 | Existing authored Devil preserved |
| Demon Elite 1 | C06 | `content.neurodragon:creature:creature.oathblade_devil@1` | 119 / 17 | New native kit |
| Demon Elite 2 | C07 | `content.neurodragon:creature:creature.blade_marshal_devil@1` | 142 / 18 | New native kit |
| Demon Elite 3 | C08 | `content.neurodragon:creature:creature.wing_regent_devil@1` | 207 / 17 | New native kit |
| Demon Elite 4 | C09 | `content.neurodragon:creature:creature.glaive_warden_devil@1` | 110 / 17 | New native kit |
| Demon Elite 5 | C10 | `content.neurodragon:creature:creature.oath_captain_devil@1` | 152 / 20 | New native kit |
| Demon Elite 6 | C11 | `content.neurodragon:creature:creature.gate_tyrant_devil@1` | 199 / 20 | New native kit |
| Demon spawn 1 | C12 | `content.neurodragon:creature:creature.ash_scribe_devil@1` | 45 / 12 | New native kit |
| Demon Spawn 2 | C13 | `content.neurodragon:creature:creature.debt_collector_devil@1` | 39 / 14 | New native kit |
| Demon Spawn 4 | C14 | `content.neurodragon:creature:creature.wardblade_devil@1` | 52 / 17 | New native kit |
| Demon Spawn 5 | C15 | `content.neurodragon:creature:creature.contract_cutter_devil@1` | 45 / 15 | New native kit |
| Demon Spawn 6 | C16 | `content.neurodragon:creature:creature.bow_harrier_devil@1` | 27 / 14 | New native kit |
| Demon Spawn 7 | C17 | `content.neurodragon:creature:creature.night_archer_devil@1` | 52 / 16 | New native kit |
| Demon Spawn 8 | C18 | `content.neurodragon:creature:creature.night_notary_devil@1` | 90 / 12 | New native kit |
| Demon Spawn 9 | C19 | `content.neurodragon:creature:creature.gate_guard_devil@1` | 75 / 17 | New native kit |
| Demon Spawn 10 | C20 | `content.neurodragon:creature:creature.ivory_marksman_devil@1` | 90 / 17 | New native kit |
| Demon Spawn 11 | C21 | `content.neurodragon:creature:creature.bastion_magus_devil@1` | 75 / 17 | New native kit |
| Demon Spawn 12 | C22 | `content.neurodragon:creature:creature.bulwark_devil@1` | 85 / 18 | New native kit |
| Demon Spawn 13 | C23 | `content.neurodragon:creature:creature.tollbreaker_devil@1` | 90 / 14 | New native kit |
| Imp 2 | C24 | `content.neurodragon:creature:creature.club_mote_devil@1` | 7 / 12 | New native kit |
| Imp 3 | C25 | `content.neurodragon:creature:creature.standard_mote_devil@1` | 13 / 13 | New native kit |
| Imp 4 | C26 | `content.neurodragon:creature:creature.needle_mote_devil@1` | 7 / 12 | New native kit |
| Imp 5 | C27 | `content.neurodragon:creature:creature.claw_mote_devil@1` | 7 / 11 | Existing authored Devil preserved |
| Imp 6 | C28 | `content.neurodragon:creature:creature.spear_mote_devil@1` | 9 / 12 | New native kit |
| Imp 7 | C29 | `content.neurodragon:creature:creature.bow_mote_devil@1` | 18 / 13 | New native kit |
| Imp 8 | C30 | `content.neurodragon:creature:creature.buckler_mote_devil@1` | 27 / 15 | New native kit |
| Imp 9 | C31 | `content.neurodragon:creature:creature.rod_mote_devil@1` | 18 / 12 | New native kit |
| Imp 10 | C32 | `content.neurodragon:creature:creature.twinhaft_mote_devil@1` | 27 / 16 | New native kit |
| Imp 1 | I01 | `content.neurodragon:creature:creature.shieldwing_imp@1` | 10 / 15 | New native kit |
| Demon Spawn 3 | I02 | `content.neurodragon:creature:creature.reaping_imp@1` | 10 / 13 | New native kit |

The **three older mapped reconciliations** are Demon Beast 1 → Dretch, Demon Beast 2 → Corrosive Demon and Demon Beast 3 → Dread Demon. Thornback, Hookclaw and Ironhide were superseded proposals and are not created as duplicate creatures. Their old CR 3/4/5 targets do not apply to the retained Dretch-based identities. Fellwing Devil, Huntsman Wing Devil and Claw Mote Devil keep their original public recipes and definitions unchanged.

## Selected native behavior and explicit adaptations

- All 28 new profiles carry real owned Infernal/Common language sources, Fire/Poison immunity, Poisoned immunity and darkvision. Only listed profiles gain Magic Resistance, Devil's Sight, cold resistance or native flight. Ordinary Motes receive no inferred canonical Imp flight, Invisibility or poison Sting.
- The accepted psychic item mapping is literal: C06 has two physical Mindreaver Scimitars; C07 has a Mindreaver Greataxe; C09 has a Mindreaver Trident; C14 has a Mindreaver Longsword. Each has the accepted +2 item bonus and 2d6 psychic packet. C10, C11, C20, C22 and C23 use ordinary weapons without old actor-wide inferred necrotic riders. The greater psychic Longsword belongs to Character 7, outside this family.
- C08 uses its own intrinsic magical Claws: 2d8+6 slashing plus 2d6 necrotic, exactly three native attacks for one action. Its Large size grants no extra dice. Legendary actions and Legendary Resistance are deferred. Native fly 60, darkvision/Devil's Sight 120, Magic Resistance, Slow 1/day and Counterspell 3/day remain present.
- C12/C18/C21/C31 use native Eldritch Blast at explicitly chosen caster levels **5/11/5/1**, producing **2/3/2/1 beams**. One cast spends one action, and none receives a free Bolt Multiattack. Existing wand items provide ordinary 1d4 bludgeoning fallback. C31 holds its actual Quarterstaff and Dagger; casting somatic spells requires freeing a hand.
- Daily spells have exact creature-owned innate providers, Charisma, fixed selected rank, finite per-spell long-rest resources and native casting costs. Thunderwave on C11 is rank 3, 4d8 and DC16; selected Counterspell and Shield remain reaction handlers with their real finite uses. Dispel Magic on C10/C11 remains omitted by the recorded disposition. Native component, hand and concentration requirements still apply.
- Paired kits C06/C15/C23/C32 use the existing native contextual offhand ability callback on the Equipment owner. Their selected Multiattacks perform exactly 3/2/2/2 attacks. **The engine's separately paid ordinary bonus offhand attack remains available.** This is an explicit adaptation of the older C15 wording “without a third bonus attack”; no free third strike is inserted into Multiattack and no unstable template-removal policy was added.
- C23 keeps Handaxe MAIN and Longsword OFF, with the existing explicit one-handed offhand permission. C11/C23 Shove uses its independently paid native action, rather than an unimplemented free attack substitution. C09's accepted Trident has reach 5 feet despite the newer Glaive Warden name.
- I01/I02 retain Tiny Imp abilities, HP, social/Stealth proficiencies, cold resistance, Magic Resistance, Devil's Sight, fly 40 and native concentration-based Invisibility. Their actual held Handaxe/Shield or Sickle uses Strength, including the +0 attack bonus. Sting and Shapechanger are deliberately omitted by later disposition. Conditional nonsilvered physical resistance is omitted because the engine currently has no actual silver-bypass provenance; it is not broadened into unconditional physical resistance.
- C25 carries the accepted real two-handed Banner in inventory beside its selected Scimitar. It has ordinary paid Help, no extra hand, passive advantage aura or inferred flight. Dagger/Spear Motes use native item Throw; ammunition accounting remains the existing deferred mechanic. No artwork, client bindings or palettes were authored in this batch.

## ECS and work-bound review

The factory composes the existing Entity data blocks, direct possession grants, native conditions/reactions, immutable configured Multiattacks and shared native spell-source helpers. There is no per-NPC class, actor subtype, generic feature executor or second spellcasting framework. One cold intrinsic bodyweapon row was required for the Regent's exact damage packet. The Sentinel's separately requested body Slam and fixed AC16 natural armor were added to the same existing item table for the humanoid author.

Runtime decisions read their current owner: Equipment supplies actual item/hand and attack facts; Spellcasting owns exact source identity/Charisma/entitlements; ActionEconomy owns costs and finite resources; existing conditions own flight, Magic Resistance and Parry. The new authoring module installs no new event handlers beyond the selected existing reaction/trait owners, publishes no read-time events, and performs no world, history or actor-cache searches. Native action execution and creation provenance are unchanged.

## Validation

`tests/engine/test_remaining_fiend_roster.py` materializes all 28 recipes in both possession modes through the ordinary frozen builtin content registry. It exercises discovered Multiattacks for dual-weapon, natural, ranged and single-weapon families; actual accepted/removed damage packets and attack bonuses; four real Eldritch Blast casts; selected Imp Invisibility/reveal; finite Bless exhaustion and rest recharge; every innate source/rank/cost; actual Shield and rank-3 Thunderwave; real shield Protection; and all profiles' language, immunity, cold-defense and flight facts.

The 34-row JSON was generated by actual public-recipe materialization, including the six retained creatures. Its source CR targets remain provisional and the three superseded targets remain explicitly separated from current canonical identities. Encounter balance and deferred presentation are remaining work beyond this native port.
