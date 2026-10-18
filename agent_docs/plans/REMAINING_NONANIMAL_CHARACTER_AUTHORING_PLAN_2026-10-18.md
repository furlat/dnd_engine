# Remaining nonanimal character authoring plan

2026-10-18. The human authorized the shared abilities/mechanics branch and then all remaining nonanimal NPC authoring in this worktree. A01–A10 and finite innate reaction-source qualification are implemented. Native phases0/2 are complete:123 new recipes plus25 retained/reconciled identities cover all148 admitted source designs. A11's two trained fighters use the human-selected Monk damage reference at level11 (d8+STR4 per punch, three punches), with defenses authored separately. Current-client presentation phase3 and final balance/playback qualification remain pending. See the [native authoring record and complete source ledger](../audits/nonanimal-roster-20261018/NATIVE_AUTHORING.md) and [mechanics implementation record](../audits/nonanimal-roster-20261018/MECHANICS_IMPLEMENTATION.md) for exact delivery, validation and known base failures.

Author the remaining nonanimal characters by finishing a small shared ability batch, then composing their selected kits through the existing creature, item, spell and presentation owners. Most selected behavior already exists. The additions are attack-assisting Help, Assassinate, Evasion, spell-damage resistance, the selected Assassin poison payload and Shield Bash. Brute, Undead Fortitude, Parry and Leadership need bounded qualification and repairs. The trained-unarmed kits now use the human-selected Monk level-scaling reference for damage. Their training tier, ability modifier, attack count and defenses must be explicit in the authored kits. No new standard condition is presently required.

## 1 Scope and worktree

The human selected **nonanimal characters first** and a separate worktree. Animals, dinosaurs and the HD Enemy dog stay outside this plan.

- Implementation workspace: `/home/tommaso/.codex/worktrees/remaining-npc-authoring/dnd_engine`.
- Current mechanics branch: `codex/npc-abilities-mechanics` (created from the latest selected integration tip).
- Earlier planning branch: `codex/remaining-npc-authoring`.
- Implementation integration base: `codex/event-native-deltas`, commit `5779fecb60f0d65e5b9c70070ed190a17e0f930b`. The initial planning review used `454fae33fbacf55d7b77bf94feff250175d3dccf`; the later tip was compared once before implementation, with no changes in the relevant existing mechanic owners.
- The similarly named `event-native-deltas` checkout is the older study at `55bf034cc`; it is not the selected implementation base.

The selected base includes the 36-spell and 22-spell batches, the subsequent spell repairs, and the integrated single-pass speed work. These are verified ancestry relationships, not a new performance certification. The [integration progress record](../ENGINE_SINGLE_PASS_PROGRESS_2026-10-17.md) and [publication plan](EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18.md) own their current results and remaining work. Roster authoring must preserve those owners and cannot turn their remaining integration work into this batch's prerequisite.

The current roster ability owners are unchanged between the older study and this base. Future implementation should compare any later chosen integration tip once, incorporate relevant changes, and then run the scoped checks as a batch. Do not continually chase an active upstream branch while authoring.


### Human clarification: Monk damage scaling and poison options

On2026-10-18 the human rejected the old2d6 fist proposal and clarified: use the Monk's level scaling as a reference even though the class is absent. This supersedes the old P-foundation2d6 and conflicting3d4 recommendations for the two trained unarmed fighters. The local [Monk rules reference](../to_archive/interactive_ruleset/Classes/Monk.md) and [progression ledger](SINGLE_PLAYER_PROFILE_AND_CHARACTER_PROGRESSION_PLAN_2026-07-26.md#152-monk--way-of-the-open-hand) agree with the [official legacy Monk table](https://www.dndbeyond.com/classes/11-monk):

| Chosen training level | Damage die per unarmed hit |
| --- | --- |
| 1–4 | 1d4 |
| 5–10 | 1d6 |
| 11–16 | 1d8 |
| 17–20 | 1d10 |

Add the selected legal ability modifier once per hit. Multiple punches are separate attacks with their actual action budget. Training level is an explicit authoring benchmark, not inferred from CR; no final tier is invented here. Existing `Equipment.unarmed_damage_dice` and `unarmed_dice_numbers` represent this directly. The clarification selects damage scaling; AC, attack count and other Monk features remain separate kit decisions. Historical source drafts and earlier reviews remain evidence of the superseded proposals.

The poison question offered two lifetimes for the same Assassin Poison item and payload, not two item definitions. There is one new Assassin Poison definition using the existing configurable ten-round default. Basic Poison is already a distinct weaker payload (DC10 CON/1d4, zero on success); Assassin Poison is DC15 CON/7d6, half on success. Per-character poison supply and final lifetime remain authoring data.

### Inventory and completion counts

The [180-row inventory](../audits/nonanimal-roster-20261018/roster_inventory.csv) preserves source pack and literal variant, original card, selected ability disposition, existing native/rig association, and capability work. It is planning data, not a runtime registry.

| Group | Original character cards | Current planning candidates |
| --- | ---: | ---: |
| Goblins | 17 | 17 |
| Orcs | 12 | 12 |
| Devils and existing demon bodies | 34 | 34 |
| Undead | 9 | 9 |
| HD Enemy combatants | 12 | 12 |
| Barbarians | 9 | 9 |
| Characters | 9 | 9 |
| HD Zombies | 21 | 22 |
| Top-down Zombies | 27 | 24 |
| **Total** | **150** | **148** |

The zombie reassessment is preserved in [the 78-row visual triage](../audits/nonanimal-roster-20261018/zombie_visual_triage.json). It sampled idle frame zero in three facings per source. Of the 180 nonanimal source designs, 148 are candidates for planning, eight have ambiguous clothing, and 24 are visibly modern and excluded from the fantasy authoring queue. These counts do not pretend that the historical 150-card list originally contained 148 characters or that every new visual judgment is a final human selection.

The old 48 zombies comprise 39 clear candidates, six ambiguous cases and three modern construction workers. Seven formerly excluded Radioactive variants add the remaining fantasy candidates. Those seven need actual character cards; green bodies and their source names grant no poison, radiation, acid or spell ability.

Hold these eight clothing decisions separately: HD `ZombieCop3`, `ZombieMale4`, `ZombieMale5`, `ZombieSoldier4`; Top-down `Zombie 05`, `Zombie 07`, `Zombie Swamp 03`, `Zombie Swamp 06`. Hold status does not block shared mechanics or the other candidates. Preserve every excluded source row for provenance.

Twenty-five candidates already have fixed creature/rig associations: 17 Goblins, six fiends, Orc01 and SkeletonArcher05. Twenty use the later accepted Goblin/fiend kits; five retain older mapped kits needing reconciliation. Thus **123 candidates lack an individual fixed mapping, with five additional mapped kits to reconcile**. A mapping is not proof of a complete selected kit or current-client playback.

## 2 Source decisions to preserve

Use the [individual cards](../audits/PACK_ROSTER_INDIVIDUAL_AUTHORING_DIRECTIONS_2026-10-01.md) for character intent and the [image-only gear review](../audits/PACK_ROSTER_IMAGE_ONLY_GEAR_REVIEW_2026-10-01.md) for recorded gear observations. Apply the later [78 ability dispositions covering all 150 cards](../ROSTER_ABILITY_DISPOSITIONS_2026-10-02.md), then the [item simplification](../ITEM_CONTENT_IMPLEMENTATION_PLAN_2026-10-02.md#human-correction--simplify-remaining-gear-october-2), [October 3 cleanup](../ANTISLOP_CLEANUP_PLAN_2026-10-03.md), and [October 4 acceptance](../audits/SUMMONING_FINAL_ACCEPTANCE_2026-10-04.md). Current code determines what is actually implemented.

The [full Devil profiles](../audits/PACK_ROSTER_AUTHORED_DEVILS_DRAFT_2026-10-01.md) and [stronger Enemy foundations](../audits/PACK_ROSTER_HIGHER_TIER_ENEMY_DRAFT_2026-10-01.md) supply the numeric proposals and inherited abilities. Their older prose/table contradictions are authoring decisions to resolve under the later dispositions, not cumulative grants.

These later decisions matter to the ability inventory:

- Disrupting Shot, pinning, reaction-denial cross-cuts, entry Brace, Spined Body, zombie drag/brace/lurch/hold, Tool Hook, Riposte and Void Guard were replaced or deferred. They are not required simply because an older card names them.
- Keep ordinary native Shove's accepted bonus-action, passive-defense and weight-distance adaptation. Do not replace it with the earlier contested SRD Shove proposal.
- Protection replaces custom Shield Cover. Parry remains its own selected reaction with the correct bonus and prerequisites.
- Selected Psychic and Ember weapons replace older actor-wide Infernal Weapons or necrotic-rider proposals. Do not apply both sets of damage.
- The four special-arrow IDs were deliberately retired. G78's Storm Arrow reference is stale: author Character9Longbow's ordinary bow kit and record the removal. No arrow-selection or ammunition subsystem returns under a different name.
- Ordinary ammunition counting, Loading, firearm proficiency, material/focus checks, tool simulation and mounts remain deferred. The real Musket/Pistol and ordinary carried possessions remain valid adapted equipment.
- Existing Goblin17 Pistol and the two single-combatant riders are accepted. Preserve the 17 implemented Goblins rather than rebuilding them from the older cards.
- Preserve Dretch, Corrosive Demon and Dread Demon as the current DemonBeast1–3 identities. C01–C03 were not silently adopted when those sprites entered the summon roster. Reconcile these three source rows explicitly; do not overwrite current canonical creatures to satisfy an old proposal.
- Armed Imp-derived characters omit Sting and Shapechanger. Wight adaptations omit controlled-zombie creation. Undead8Necromancer is an adapted undead Archmage and Undead9Wizard an adapted undead Mage; neither requires Lich phylacteries, Rejuvenation or Paralyzing Touch. The Wing Regent's legendary system remains deferred.
- Existing spells retain current native adaptations. For example, Produce Flame is now a direct bolt, not the old held-light contract. Unsupported or intentionally omitted source spells must be recorded as omissions in the adapted profile.

Do not invent a new monster behavior, inventory item or renderer promise to preserve an attractive name or color. Source CR and the old team XP estimates require recalculation after the final kits; they are not accepted balance results.

## 3 Abilities and conditions to finish first

Source gaps below are read from the selected base. For existing implementations, reproduce the named gameplay case before changing code. A source observation is not a claim that a failing runtime case has already been executed.

| ID | Capability | Status and consumers | Work to complete |
| --- | --- | --- | --- |
| A01 | Attack-assisting Help | Missing selected behavior. Club Mote (`Imp 2`) and Standard Mote (`Imp 3`). Existing `AllyHelp` removes conditions; it does not assist an attack. | Add the selected attack-assistance action and a short-lived owned advantage grant through existing actions, modifiers and turn expiry. Define the ally, nearby enemy, next eligible attack and consumption; keep the existing restorative Help behavior. |
| A02 | Assassinate | Missing. HD Enemy Shooter, Assassin, Sniper; Character CamoArcher. | Advantage against an opponent that has not taken a turn; a hit against an actually surprised opponent is critical. Consume real encounter opening-turn/surprise facts. Do not use an Assassin name, invisibility, every round's initiative order, or a duplicate trait clock as a substitute. |
| A03 | Evasion | Missing. The same four Assassin profiles. | Dexterity saves whose normal success halves damage instead deal zero on success and half on failure. Add the minimum typed save/damage facts needed at the existing resolution boundary; cover actual selected spell routes, not merely a registered trait. |
| A04 | Resistance to damage from spells | Missing selected source behavior. HD Enemy Commander and Undead Necromancer, both adapted Archmages. | Resolve spell-origin resistance inside ordinary damage affinity resolution. Spell resistance and matching type resistance halve once, not twice. Distinguish it from magical-save advantage and from resistance to all magical attacks. |
| A05 | Assassin poison | Exact source payload absent; final per-profile supply treatment needs explicit authoring. The four Assassin-derived profiles retain poison in the later dispositions. | Represent DC15 CON, 7d6 Poison, half on success through the existing hit/coating and item ownership path. Basic Poison's DC10/1d4 is not equivalent. Set dose/application lifetime and available uses in the actual kit; no new ammunition model, Poisoned condition, or critical doubling of separately saved poison dice. |
| A06 | Brute with the actual weapon | Present but fixed to an extra d8. Weapon-bearing Gladiator adaptations: Enemy Hammer/Footsoldier/Guard, Undead Brute, Barbarian Golem, Character DeathKnight. | Add one die of the actual held weapon: Maul/Greatsword 2d6→3d6, Longsword 1d8→2d8. Preserve other damage packets and weapon replacement. The Ogre is not automatically a Gladiator. Explicit trained unarmed profiles remain separate authored strike data. |
| A07 | Undead Fortitude | Present but missing a critical-hit bypass; DC calculation needs qualification after mitigation. All admitted zombie and hulk kits. | Prove qualifying lethal damage can leave 1 HP, radiant/critical bypasses, failure/death behavior and DC from damage taken after defenses. Use the existing damage preview and death owner once. |
| A08 | Parry | Parameterized +2/+3 exists; held-melee-weapon, attacker visibility and would-hit timing need qualification. Selected Devil blade officers, armed Gladiator descendants, Knight/Bandit Captain adaptations and explicit Undead DarkKnight. | Use one available reaction against one eligible melee hit, only with its actual prerequisites. No reaction consumption on an ineligible attack. Compete with Protection and spell reactions using the same budget. |
| A09 | Leadership | Existing aura needs qualification/repair for recharge, incapacitation, hearing/understanding and nonstacking. Enemy Crusader, Character Knight and Knight-based Paladin. | Action activation; ten-round lifetime; one eligible d4 on attacks/saves within30ft; suppression when leader cannot lead; one Leadership die across multiple leaders; short/long-rest recharge. Use existing language/proficiency and sensory facts, not a new language system. |
| A10 | Shield Bash | Missing selected attack. Enemy Footsoldier explicitly retains the Gladiator shield attack in its source proposal; check other final shield-bearing Gladiator kits in Phase0. | Actual equipped shield required; selected baseline +7, 2d4+4 Bludgeoning. Medium-or-smaller targets additionally save DC15 STR or fall Prone; larger targets still take ordinary bash damage. Reuse current attack, damage and save-rider owners; author its permitted Multiattack position/count explicitly. A shield is a real possession, not an intrinsic claw or second offhand attack. |
| A11 | Monk-scaled trained unarmed strikes | Human correction2026-10-18 supersedes the old2d6/3d4 fist proposals. Use Monk level scaling as a damage reference; the Monk class is not implemented. | SRD5.1 progression: one d4 at training levels1–4, d6 at5–10, d8 at11–16, d10 at17–20, plus the chosen legal ability modifier per hit. Record each NPC's training tier, modifier and attack count explicitly. Use existing unarmed damage data; no Brute extension supplies additional fist dice. AC is a separate kit choice; if an unarmored formula is selected, use its explicit ability terms and armor/shield eligibility in the existing formula owner. |

### Existing behavior to compose and qualify

These are character authoring dependencies, not new mechanics projects:

| Existing owner | Selected use |
| --- | --- |
| `dnd/monsters/traits.py`: Multiattack, Aggressive, Brave, Sneak Attack, contextual Magic Resistance | Correct attack sequence, native Orc advance, selected fear defenses, Assassin **4d6** rather than Spy2d6, and advantage on explicitly magical saves only. |
| The same owner: innate Invisibility, innate Flight, WightLifeDrain and LifeDrainReduction | Adapted armed Imps, existing ground-to-ground flyer policy, and cumulative maximum-HP loss until long rest. Life Drain can replace one melee Longsword, never become a ranged rider; source removal does not cure it. |
| `dnd/classes/fighter.py`: Protection | Actual shield/visibility/other-target/range prerequisites and one reaction. Preserve native Protection rather than the older melee-only Shield Cover variant. |
| `dnd/core/view.py` and existing sense-mode data | Devil's Sight and stated range, Darkness interaction, ordinary obstruction and invisibility limits. |
| `dnd/blocks/spellcasting.py` and existing spell/reaction grants | Innate Charisma sources, fixed cast ranks, per-spell daily resources, exhaustion/rest recovery, Shield and Counterspell reaction costs. |
| `dnd/content/items/roster_item_definitions.py`, canonical item builders and `dnd/items/spell_items.py` | Actual Psychic/Ember weapons, ordinary specialist gear and the three retained powered backpacks, with ownership and transfer. |
| `dnd/blocks/equipment.py`: unarmed strike data and ArmorClassFormulaCandidate | Monk-scaled trained fist damage as existing unarmed data; any separately selected unarmored AC formula retains explicit armor/shield eligibility. No Barbarian class/progression is implied by the same ability formula. |

Prone, Restrained, Poisoned, Frightened, Paralyzed, Invisible, Concentrating and NoReactions already have owners. **No new standard-condition implementations are selected.** Help may need an owned temporary advantage grant; Assassinate/Evasion and spell resistance are reusable traits. Do not create per-NPC versions of standard effects. Current source has no ordinary Grappled implementation, and this plan does not add one.

### Spell readiness

Devil spell selections already have native owners: Eldritch Blast, Command, Bless, Bane, Web, Grease, Darkness, Slow, Counterspell, Shield and upcast Thunderwave. The accepted caster families also reuse implemented Fire Bolt, Mage Armor, Magic Missile, Misty Step, Fireball, Fly, Greater Invisibility, Ice Storm, Cone of Cold, Lightning Bolt, Banishment, Fire Shield, Stoneskin, Wall of Force and Globe of Invulnerability. Produce Flame, Shillelagh, Longstrider and Barkskin are also present in their school modules.

Do not rebuild these spells from old missing-support notes. Resolve per-character caster level, known/prepared spells, ranks, slots or innate uses and omitted source spells. In particular C12/C18/C21/C31 now cast actual Eldritch Blast: caster level determines beam count. The former two bespoke 2d6/3d6 Bolts do not define that level. Slow, native flight, the Musket and utility-spell omissions remain explicit adaptations where appropriate.

## 4 Rules and ownership for the ability batch

Reuse the current execution boundary: registered action UUID and `ActionSelection` through `Entity.perform`, existing target admission, cost commitment, typed effect origin, saves, damage and condition ownership. A refused effect must not install a benefit or orphan action, modifier, handler or resource. Preserve actual established cost policy rather than inventing blanket refunds.

- **Assassinate:** current attack readings and d20 critical status consume the result. Use encounter-owned turn/surprise facts through a dependency-safe query or existing neutral facts. Current turn count increments at turn completion and the raw surprised flag survives its live interval; neither alone is the eligibility rule. Include skipped first turns, joins and encounter restart; a miss remains a miss. Do not import `Encounter` back through the creature/Entity dependency chain or scan stored events on every attack.
- **Evasion:** current `SpellDamageRollResultEvent` has success/fraction but not save ability, and some spells halve damage locally. Extend only the missing typed cause facts in the existing save/damage owner and connect selected real routes. No spell-name dispatch, per-spell Evasion copies or second effect executor.
- **Spell resistance:** `TakeDamageEvent` already carries `EffectOrigin`; health affinity currently sees type and attack magic. Carry the minimal spell-origin context into that same resolution. Do not prehalve raw rolls in a handler and then halve again for resistance.
- **Poison:** use the exact current possession/coating owner and declared finite source. Keep application/consumption and target refusal observable. The plan does not infer unlimited poison, finite bullet stacks or a separate gun action from the source statblock.
- **Shield Bash:** a Shield is not a Weapon and current ordinary offhand Attack falls back to unarmed for that slot. Admit the minimal real-shield attack source/spec through the existing Attack owner, retaining the actual shield UUID and live equip/ownership check. Connect its size-gated rider to that attack. Do not fake an intrinsic shield, classify every shield as a Weapon or implement an independent bash executor.
- **Brute and reaction fixes:** change the shared feature, not each creature's base damage or AC to imitate the result. Buffs, replacement weapons, disarm, rest, source removal and competing reactions must continue using native ownership.
- **Fortitude:** critical provenance currently reaches `receive_damage` and the later applied-damage fact, while Fortitude interrupts `TakeDamageEvent` before HP commitment. Carry the minimal critical fact to that existing boundary. Never infer it from a later event or revive the creature after death to imitate Fortitude.
- **Leadership:** retain the existing anchored area and duration lifecycle. Read hearing, shared-language and incapacitation eligibility from existing owners; no persistent cache whose invalidation is unknown.

Legitimate concrete actions and feature conditions follow the project's existing ECS adaptation. Entities remain composed data. No NPC subclasses, generic creature manager, signature DSL, per-pack executor, dynamic attribute dispatch, new registry or type-check switch is needed. Keep imports at module scope and maintain a DAG. Declare newly created models through the base's existing creation declarations.

## 5 Implementation sequence

### Phase 0 Finalize the selected kits

Reconcile the inventory with current item definitions and later decisions before adding mechanics. Produce each candidate's exact base facts, possessed/equipped item IDs, attack sequences, traits, spell source/levels/uses and named source omissions. Preserve ordinary canonical recipes; author adaptations through the existing creature declaration/materialization path.

Finish seven new fantasy-zombie cards without assigning powers from color. Resolve the five older mapped kits, the retired G78 arrow, the four Eldritch Blast caster levels, Assassin poison supply/lifetime, and the final trained-unarmed kits. For Bruiser/Brawler, the human has rejected the old2d6/3d4 proposals and selected Monk level scaling as the unarmed damage reference. Choose an explicit training tier, ability modifier and attack count for each kit; source CR is not a Monk level. Retain ordinary punch damage without Brute, Shield Bash or weapon Parry. Set defenses separately; the old CON-based Martial Guard proposal is not silently accepted by this damage-scaling instruction. Keep the eight visual holds visible. If a choice changes a previously selected ability rather than filling authoring data, present that specific proposed change for human disposition; unrelated characters can proceed.

Keep the current Skeleton Archer identity by default. Decide explicitly whether the Gravesight Wight proposal becomes a distinct variant or is omitted for that source row; it cannot silently change Skeleton Archer into a Wight. Apply the same preservation rule to canonical Orc and DemonBeast1–3 recipes.

Exit: every admitted candidate has a kit, every required ability maps to a current owner or A01–A11, and optional old signatures remain separate. No final CR is claimed before the kit is fixed.

### Phase 1 Implement the shared abilities and fixes

1. Reproduce A06–A09's named cases through existing registered actors/actions. Apply only demonstrated fixes to those owners.
2. Implement A01 attack-assisting Help and A02 Assassinate through existing action, modifier, encounter-fact and expiry owners.
3. Implement A03 Evasion and A04 spell resistance at their existing damage boundaries; qualify actual spell and nonspell save-damage routes promised by the trait.
4. Implement A05's selected poison payload and its settled possession/coating contract. Configure Assassin Sneak Attack to4d6 through its existing feature.
5. Qualify innate daily resources and learned reaction source selection on an actual authored Devil caster. Fill only a demonstrated missing grant/recharge behavior.
6. Add A10 through the existing attack and save-rider owners, including actual shield possession and allowed target size. For A11, set the chosen Monk-tier strike die through existing unarmed data when authoring the two kits. Qualify formula eligibility only for an explicitly selected defense; no full Monk class or new scaling runtime is required for this damage reference.

The representative consumers prove shared rules; they do not shrink delivery to a pilot. Finish the shared capability checks before bulk character registration so duplicated kit work does not hide mechanical defects.

### Phase 2 Author every admitted remaining character

| Family | Authoring work |
| --- | --- |
| Orcs12 | Preserve existing canonical Orc. Author the eleven unmapped source rows and reconcile Orc01's actual kit/visual selection; use Aggressive, selected normal attacks, native Shove/Protection and existing spells. |
| Fiends34 | Preserve six accepted current mappings; reconcile older DemonBeast1–3 decisions explicitly. Compose the remaining28: melee/ranged soldiers, officers, innate casters and adapted minor Devils. Use exact accepted items, spells, senses and defenses; no implicit legendary or shapechange system. |
| Undead9 | Preserve existing Skeleton Archer while reconciling its proposed Wight profile separately. Author the other eight, selected Life Drain, adapted caster kits and approved Burning Hands. Do not mutate canonical skeleton rules or advertise a Lich. |
| HD Enemy12 | Author all twelve combatants. Use the completed Assassin package, armed/trained-unarmed Gladiator distinctions, Knight support, adapted Archmage/Mage and the selected two-Slam Arcane Sentinel; the old cone/burst is deferred. |
| Barbarians9 and Characters9 | Author all18 using accepted real gear, ordinary attacks/Multiattack, existing spellcasting, selected innate Burning Hands and Divine Eminence/Protection. Preserve explicit creature type; vendor names do not create PC class progressions, Construct immunity or Undead identity. |
| Fantasy zombie candidates46 | Author normal bodies, hulks and any depicted tools/blades using chosen Zombie/Ogre Zombie adaptations and fixed ordinary attacks. Keep Fortitude and stated immunities. No on-hit drag, recharge lurch, brace reduction or implicit poison. |
| Existing Goblins17 | Retain the accepted recipes, gear, riders and pistol. Run the affected regression controls when shared traits change; do not reauthor all seventeen. |

Use bounded passive definition tables where current siblings already use them; shared functions compose real components. Add only genuinely distinct content identities and register them in the existing built-in inventory. A palette variant can share a mechanical composition. Do not force a different rules class or factory hierarchy for each sheet.

Exit: every admitted row either materializes its exact selected native kit or references an explicitly retained existing recipe. Record real source differences; an empty list of missing features is not a substitute for materializing and exercising the character.

### Phase 3 Complete character presentation authoring

Recovery update2026-10-18: [the asset search](../audits/nonanimal-roster-20261018/ASSET_RECOVERY.md)
found installed source portraits for141/148 admitted NPCs and the complete
36+22 spell-icon handoff, subsequently updated with all seven zombie portraits
and five dedicated NPC/Unarmed icons (190 icons,19 portraits total). All148
admitted NPCs now have source portraits. Reuse these deliveries; pending
integration does not imply missing artwork.
The recovery CSVs preserve exact source and native keys without changing runtime
associations or claiming visual acceptance.

Use owned original sheets and current client authoring data. `game_obsolete/data/rigs` is preserved mapping evidence, not the renderer to restore. The current Godot client has `authoring/catalog/{creature_rigs,rigs,resources}.json` and `authoring/characters/sheet-components.json`; extend the actual current owners after reading that checkout's instructions. Client changes belong in its own isolated checkout when this phase starts, not in an unrelated dirty client.

For each admitted source character select idle, locomotion, hit, death, ordinary weapon/body attacks, cast gesture and required reaction/rest poses. Author playback rates and contact clocks calibrated from inspected source frames, plus facings, pivot, contact/release markers, sockets, selected body/shadow/effect layers and appearance scale. PNG sheets do not establish an original vendor playback rate. Reuse the accepted source controls and shared spell/condition presentation. A review page's generic12FPS clock is not a gameplay timing decision.

Keep baked gear truthful as a selected appearance. Use the existing accepted limitations for gear loss and approximate modular loot donors; this plan adds no compatibility resolver or new weapon artwork. Do not duplicate an embedded effect with shared VFX or infer gameplay from a vendor Attack number, glow or particle color. Read ASSETS.md before artwork operations; preserve originals and avoid a bulk reimport or new packing/checksum system.

Exit: every admitted character has its native identity connected to its selected rig and actions through the current client path, with actual attack/cast/hit/death evidence. Library availability alone does not satisfy this phase.

### Phase 4 Validate and close the complete roster

Run the behavior checks below, then one appropriate batch of existing engine/content/player/AI regressions for the touched owners. Confirm representative registered character discoveries, actual actions, observer facts and client playback. Exercise low-tier groups, a mixed weapon/caster team, an Assassin, a Wight, a durable zombie and the strongest adapted caster/officer at their actual selected strength. These are validation fixtures, not new campaign/scenario design.

Recalculate provisional threat/CR and team XP from the final kits or leave them explicitly uncalibrated; do not reuse old legendary-boss or poison damage estimates after altering the kit. Account for every inventory row: admitted and completed, retained existing, held for a named visual decision, or excluded modern. Report native mechanics, character composition and presentation completion separately.

## 6 Behavioral acceptance

Follow [HOW_TO_TEST.MD](../../HOW_TO_TEST.MD). Use existing deterministic dice and scenario helpers, real registered actors, action discovery/selection and `Entity.perform`. Assert the observable outcome at the smallest stable native boundary; use representative wire/client checks for integration. Do not freeze handler order, private dictionaries or exact class layout as gameplay requirements.

| Capability | Required positive and negative cases |
| --- | --- |
| Help | Correct next ally attack against selected adjacent enemy gains advantage; consumed once; wrong enemy/ally and deadline do not inherit it; no cleansing behavior lost. |
| Assassinate | Advantage before target's first turn, absent afterward; critical only with actual surprise; encounter restart clears eligibility; ordinary unseen-attacker rules still compose. |
| Evasion | DEX half-on-save success0/failurehalf; actual Fireball/Burning Hands and another selected save route; unrelated CON save/full-damage effect unchanged; defenses and multi-target recipients resolve independently. |
| Spell resistance | Spell damage halves; ordinary weapon and merely magical body attacks do not qualify; matching type resistance does not quarter; immunity still wins; packet provenance survives recorded damage. |
| Assassin poison | Exact DC/dice/half-save, hit/miss and finite source behavior, resistance/immunity, critical weapon hit without doubling separately saved poison, transfer/expiry and rejected target application. No Poisoned condition appears. |
| Brute | Maul and Greatsword3d6, Longsword2d8, replacement weapon changes the extra die; existing independent buffs/critical rules remain; trained unarmed data is deliberate. |
| Fortitude | Qualifying lethal success1HP, failed save death, radiant/critical bypass, post-defense damage DC and temporaryHP interaction. |
| Parry and Leadership | Legal and ineligible reaction cases, one shared reaction budget; Leadership duration/expiry, range, hearing/language/incapacitation, nonstacking and rest recharge. |
| Shield Bash and selected trained-unarmed kit | Bash damage/save/Prone; a larger target takes damage without the rider; no shield means no bash; one selected Multiattack budget. For the trained fighters, verify the chosen Monk-tier single die and ability modifier per strike, the actual attack budget and any explicitly selected defense eligibility; no hidden Brute or weapon Parry. |
| Existing reused effects | Magic Resistance magical/mundane contrast; innate Invisibility and concentration; Devil's Sight versus Darkness/walls; existing flight endpoints; cumulative Life Drain/source removal/rest/maxHP0; daily innate spell exhaustion and reaction source costs. |
| Every admitted recipe | Actual type/size/HP/AC, senses/immunities, exact possessions, attack counts, resources and named adaptations. Reject duplicate behavior and unexpected additional damage. |

Preserve the selected base's performance work. New traits should inspect the relevant actor, attack, save or owned item; no full-world actor scan, stored-event replay or per-sprite executor on each hit. Reuse existing relevant performance/oracle fixtures for changed damage/discovery paths and report a measured regression if one appears. This plan adds no arbitrary latency target or unrelated publication rewrite.

## 7 Required reviews and implementation supervision

**Anti-slop reviewer:** independently check all180 source rows, selected versus obsolete abilities, current spell/item support, A01–A11 and the human-selected Monk damage reference with explicit per-kit choices, the five older mappings, seven new zombie cards, eight visual holds and explicit exclusions. Reject invented color powers, revived special arrows/grapple/legendary work, duplicate weapon damage, provisional CR presented as validated, and a pilot presented as the full deliverable.

**Anti-OOP and ECS reviewer:** independently check minimal typed facts at attack/save/damage boundaries, single resistance resolution, existing component/action/condition ownership, import DAGs, model creation declarations and current discovery/execution/publication paths. Reject entity subclasses, a signature framework, global scans, late imports, getattr/type dispatch and a second combat executor.

Before implementation starts, assign a separate **plan-adherence subagent** as required by AGENTS.md. It follows these phases and calls out scope drift, redundant infrastructure or polishing a small fixture while the complete roster is neglected. Review messages stay inside this task's subagent team; do not read or message other chats. Review approval does not substitute for the human's scope choices or behavioral checks.

The independent [anti-slop review](../audits/nonanimal-roster-20261018/ANTISLOP_REVIEW.md) and [anti-OOP/ECS review](../audits/nonanimal-roster-20261018/ANTIOOP_ECS_REVIEW.md) approve the bounded plan after source rechecks and the Shield Bash/unarmed-kit corrections. They qualify planning scope, source consistency and ownership; gameplay, balance and rendered behavior require the implementation checks above.
