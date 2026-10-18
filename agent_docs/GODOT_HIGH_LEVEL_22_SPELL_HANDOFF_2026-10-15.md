# Godot handoff:22 high-level SRD spells

Implementation worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`, branch `codex/spells-rank-one-two`.
Previous 36-spell batch is committed as `c72980091a5`. This 22-spell batch remains a working-tree change for review.
Source preference is BG3 >SRD5.1 >SRD5.2. All new spell identities are SRD spells; BG3 monster techniques are explicit adaptations supporting those spells. No NDClient or Godot code was changed.

## Inventory and root behavior

There are188 composed public catalog roots,190 native roots including the already implemented uncatalogued Entangle/Black Tentacles.67 native SRD spells are levels4–9. The22 additions are below; existing non-SRD roots were not changed or counted as new SRD additions.

| Level | Root | Stable behavior ID | Behavior |
| --- | --- | --- | --- |
| 4 | Aura of Life | `spell.aura_of_life` | Moving 30-ft ally aura: Necrotic resistance, prevent added max-HP loss, heal living downed allies1 at START before death saves. |
| 4 | Charm Monster | `spell.charm_monster` | General creature charm; combat advantage, ally-damage break; upcast recipients save independently. |
| 4 | Phantasmal Killer | `spell.phantasmal_killer` | BG3 immobilizing fear; WIS recovery precedes4d10 Psychic at END; upcast adds dice, ten ENDs, strongest overlapping damage only. |
| 4 | Resilient Sphere | `spell.resilient_sphere` | Three recipient ENDs, half movement, invulnerability and outward/spellcasting denial; allies bypass DEX; Disintegrate ends enclosure. |
| 4 | Vitriolic Sphere | `spell.vitriolic_sphere` | 10d4 Acid DEX half; +2d4/slot; failed save leaves fixed5d4 at next END. |
| 5 | Antilife Shell | `spell.antilife_shell` | Moving10-ft living-creature crossing boundary; undead/constructs bypass; projectiles/spells/teleports pass; living swept contact ends shell. |
| 5 | Conjure Elemental | `spell.conjure_elemental` | Independent ally until long rest; four base forms at5, four Myrmidons at6+, one current body per caster family. |
| 5 | Dispel Evil and Good | `spell.dispel_evil_and_good` | Six-type defensive ward and paid touch Break Enchantment; cure source-eligible charm/fear then end ward. |
| 5 | Summon Dragon | `spell.summon_dragon` | Concentration600 rounds; slot-scaled spirit; existing Multiattack Rends then one separate free Breath; two independent element choices. |
| 6 | Blade Barrier | `spell.blade_barrier` | Up to120-ft segment, difficult ground,6d10 Slashing DEX half on formation/entry/START once per recipient turn. |
| 6 | Flesh to Stone | `spell.flesh_to_stone` | BG3 progression: initial fail plus three failed END saves petrifies persistently; any repeat success clears progression; separate Petrified state. |
| 6 | Freezing Sphere | `spell.freezing_sphere` | BG3 60-ft launch or portable item on self/ally within5;10d6 Cold CON half,20-ft burst,ten-round ice; no upcast damage. |
| 6 | Irresistible Dance | `spell.irresistible_dance` | No initial save; Action denial/speed0, DEX disadvantage, incoming advantage; WIS END recovery, bonus/reaction preserved. |
| 6 | Planar Ally | `spell.planar_ally` | Independent Deva/Djinni/Cambion ally until long rest; one per caster family, fixed approved loadout. |
| 7 | Arcane Sword | `spell.arcane_sword` | 60-ft initial visible anchor,3d10 melee spell attack within5; granted BA strike/move within20; concentration10 rounds. |
| 7 | Delayed Blast Fireball | `spell.delayed_blast_fireball` | Real bead,12d6(+upcast), grows+1d6/original-caster END up to ten; concentration ending retires then explodes; DEX half,20-ft burst. |
| 7 | Forcecage | `spell.forcecage` | Fixed maximum20-ft bars or10-ft box, independent600 rounds; pre-admitted ejection; paid CHA escape; Disintegrate breaches bars/destroys small box. |
| 8 | Feeblemind | `spell.feeblemind` | 4d6 Psychic on either INT save outcome; failure fixes INT/CHA1 and blocks casting/magic-item activation; Heal/Greater Restoration cure; native GM30-day recovery. |
| 8 | Holy Aura | `spell.holy_aura` | Fixed chosen recipients, save advantage/incoming disadvantage/light; Fiend/Undead melee hits risk CON blindness; all ward/blind leases share cast clock. |
| 9 | Foresight | `spell.foresight` | Action casting adaptation,8 hours; attack/check/save advantage, incoming disadvantage, surprise prevention; same-caster retarget cleans prior lease. |
| 9 | Power Word Heal | `spell.power_word_heal` | 60-ft verbal-only full HP and listed cures; persistent recipient preference optionally spends Reaction to stand, with no movement cost. |
| 9 | Weird | `spell.weird` | 30-ft area ordinary fear with retreat; WIS initial/recovery,4d10 Psychic after failed END save, ten ENDs; strongest overlap only. |

## Native choices and authoritative submission

Use current Choices/Preview/Command values and authored `behavior_id`, `variant_facets`, target sets and position selection. Labels are presentation only. Preview never rolls, pays, summons, advances clocks, moves anchors or detonates items.

- Charm Monster exposes normal slot variants and allocated recipients; upcast count is authoritative.
- Freezing Sphere has `form=launch` / `form=portable`. Portable targets an entity within5ft; launch selects its impact position.
- Delayed Blast Fireball selects the initial bead position. Its item exposes separate paid touch-and-pickup / touch-and-throw forms; ordinary free pickup cannot bypass the save.
- Forcecage has `form=cage` / `form=box`. These are fixed maximum forms, with no independent size selector.
- Conjure Elemental and Planar Ally expose `form` values in the creature table below.
- Summon Dragon exposes `damage_type` for Breath and a separate **`resistance`** facet for the caster's shared resistance. Both select Acid/Cold/Fire/Lightning/Poison; they may differ. The body resists all five.
- Arcane Sword and its strike use existing entity+destination selection. Choose the target, obtain legal next anchor positions, then submit one `extra_target_positions` entry. Movement without an attack is a separate native BA action.
- Recipient stand preference is the existing toggleable `reaction.stand_when_healed` handler. Register it before the offer. No click-to-accept reaction flow was added.
- A Dragon's first accepted paid Multiattack grants one native free Breath row for the remaining turn. Its normal cone preview/command is separate from the Rends. Own END, accepted use or owner cleanup removes the allowance; previews cannot unlock or consume it.

Active protocol remains version1/schema9. Generated schema identity is `63c41fd68b001186dc11660cb00d6ddb76d4df7d827765947b18e3156e4761e6`; Python and TypeScript exports agree. The approved new `resistance` facet changes the digest. No mixed-outcome API or AI evaluator redesign was introduced.

## Summon bodies

Bodies join the existing encounter controller as autonomous allies. The creator's summon origin is retained on existence/lifetime owners; each body remains the actor for its own attacks and innate spells. Natural attacks are not automatically magical because the creature was summoned. Authored magical armaments and elemental techniques carry their own classification. Bound intrinsic weapons cannot become loot.

| Form | HP | AC | Size/type | Movement | Creature ID |
| --- | --- | --- | --- | --- | --- |
| `air_elemental` | 90 | 15 | Tiny/elemental | walk30/fly60 | `creature.spell.air_elemental` |
| `earth_elemental` | 126 | 17 | Large/elemental | walk30 | `creature.spell.earth_elemental` |
| `fire_elemental` | 102 | 13 | Tiny/elemental | walk30 | `creature.spell.fire_elemental` |
| `water_elemental` | 114 | 14 | Medium/elemental | walk30/swim30 | `creature.spell.water_elemental` |
| `air_myrmidon` | 117 | 18 | Small/elemental | walk30/fly60 | `creature.spell.air_myrmidon` |
| `earth_myrmidon` | 127 | 18 | Medium/elemental | walk30 | `creature.spell.earth_myrmidon` |
| `fire_myrmidon` | 123 | 18 | Small/elemental | walk30/fly60 | `creature.spell.fire_myrmidon` |
| `water_myrmidon` | 127 | 18 | Medium/elemental | walk30/fly60/swim30 | `creature.spell.water_myrmidon` |
| `deva` | 136 | 21 | Medium/celestial | walk30/fly60 | `creature.spell.deva` |
| `djinni` | 161 | 19 | Medium/elemental | walk30 | `creature.spell.djinni` |
| `cambion` | 82 | 14 | Medium/fiend | walk30/fly60 | `creature.spell.cambion` |
| `draconic_spirit` | 50+10×(slot−5) | 14+slot | Large/dragon | walk30/fly60/swim30 | `creature.spell.draconic_spirit` |

Concrete data, scores, senses, affinities and loadouts live in `dnd/monsters/high_level_spell_summons.py`; techniques/status owners in `dnd/monsters/spell_summon_actions.py`. Support definitions belong to the SRD5.1 adaptation pack, with the Dragon creature in5.2, preserving one-way pack dependencies. Provenance labels these adaptations rather than verbatim SRD monster blocks.

| Body | Loadout |
| --- | --- |
| Air | Two native Multiattack slams, extra dice against Shocked; two saved Gushing Air jets; Primordial Gales; Warp/Fly. |
| Earth | Two slams, extra dice against Prone; Soil-Clogged Slam/Mud; Seismic Strike/push/Trembling Legs; Warp. |
| Fire | Two slams, extra dice against Burning; Smouldering Touch/Burning/fire patch; Cinderous Swipe; Warp. |
| Water | Two slams, extra dice against Chilled; Water Slam fixed5B+2d6Cold; Winter's Breath/cooling/Brittle/ice; Warp/Swim. |
| Air Myrmidon | Bound flail/Electrified Flail/stun; Tenacity on melee miss; replacing Raging Vortex/Silence; own short-rest Invisibility; Warp/Fly. |
| Earth Myrmidon | Grounded Thunder fixed9B+3d10Thunder/Prone; Sludgy Sling/Mud; BA+20movement Burrow/arrival burst;17movement Muck to Metal; Warp. |
| Fire Myrmidon | Finesse bound scimitar/Scorching Strike/Burning; cone Swipe; own3-turn Immolation concentration/Haste/lethargy; own Hellish Rebuke resource sharing Reaction with OA; Warp/Fly. |
| Water Myrmidon | Bound trident/Hiemal Strike/Chilled; three Icicle attacks per recipient plus ice; Healing Vapours heals all sides or poisons if body Poisoned, without inventing an immunity bypass; Warp/Fly/Swim. |
| Deva | Bound mace/Angelic radiant packets; short-rest Concussive Smash/Dazed; own long-rest Revivify; Help/Fly. No Wrathful Smite. |
| Djinni | Bound scimitar/Poison; actual at-will level4 Thunderwave and Misty Step; independent Sweetplum Gales fields/restraint. No Fly or Drunken Inhale. |
| Cambion | Actual at-will Charm Person/Scorching Ray; Draining Kiss consumes this body's exact Charm Person on effect. No non-SRD Fiendish Charm/Rays of Fire. |
| Dragon | Retained caster numeric accuracy/DC, slot-scaled2/3/3/4/4 Rends; one subsequent free30-ft2d6 Breath; independent caster resistance lease; Fly/Swim. |

Creature action IDs:

- `action.elemental.warp`
- `action.air_elemental.primordial_gales`
- `action.air_elemental.gushing_air`
- `action.earth_elemental.seismic_strike`
- `action.fire_elemental.cinderous_swipe`
- `action.water_elemental.winters_breath`
- `action.earth_elemental.soil_clogged_slam`
- `action.fire_elemental.smouldering_touch`
- `action.water_elemental.slam`
- `action.water_myrmidon.explosive_icicle`
- `action.air_myrmidon.electrified_flail`
- `action.earth_myrmidon.grounded_thunder`
- `action.fire_myrmidon.scorching_strike`
- `action.water_myrmidon.hiemal_strike`
- `action.deva.concussive_smash`
- `action.earth_myrmidon.sludgy_sling`
- `action.fire_myrmidon.cinderous_swipe`
- `action.earth_myrmidon.burrow`
- `action.earth_myrmidon.landing`
- `action.earth_myrmidon.muck_to_metal`
- `action.water_myrmidon.healing_vapours`
- `action.air_myrmidon.raging_vortex`
- `action.djinni.sweetplum_gales`
- `action.fire_myrmidon.immolation`
- `action.cambion.draining_kiss`
- `action.draconic_spirit.breath`

Native retained condition/area IDs (source UUIDs and parent links distinguish exact active leases):

- `condition.spell.arcane_sword`
- `condition.spell.aura_of_life.benefit`
- `condition.spell.aura_of_life.membership`
- `condition.spell.aura_of_life.owner`
- `condition.spell.charm_monster`
- `condition.spell.dispel_evil_and_good`
- `condition.spell.feeblemind`
- `condition.spell.flesh_to_stone.petrified`
- `condition.spell.flesh_to_stone.stages`
- `condition.spell.foresight`
- `condition.spell.foresight.owner`
- `condition.spell.holy_aura`
- `condition.spell.holy_aura.blindness`
- `condition.spell.independent_summon_owner`
- `condition.spell.irresistible_dance`
- `condition.spell.payload_lifetime`
- `condition.spell.phantasmal_killer`
- `condition.spell.resilient_sphere`
- `condition.spell.summon_dragon.shared_resistance`
- `condition.spell.vitriolic_sphere.residue`
- `condition.spell.weird`
- `condition.summon.brittle`
- `condition.summon.burning`
- `condition.summon.chilled`
- `condition.summon.dazed`
- `condition.summon.draconic_breath_cadence`
- `condition.summon.elemental_multiattack_bonus`
- `condition.summon.myrmidon_strike_dice`
- `condition.summon.raging_vortex_owner`
- `condition.summon.shocked`
- `condition.summon.sweetplum_field_owner`
- `condition.summon.sweetplum_membership`
- `condition.summon.sweetplum_restrained`
- `condition.summon.tenacity`
- `condition.summon.transmuted_to_steel`
- `condition.summon.trembling_legs`
- `spatial_effect.spell.antilife_shell`
- `spatial_effect.spell.aura_of_life`
- `spatial_effect.spell.blade_barrier`
- `spatial_effect.spell.forcecage`
- `spatial_effect.summon.fire`
- `spatial_effect.summon.mud`
- `spatial_effect.summon.raging_vortex`
- `spatial_effect.summon.sweetplum_gales`

## Retained effects, items and cleanup

Spell-specific control leases keep exact source ownership and native immunity aliases. Do not infer control from display names, remove every fear owner on a source-specific cure, or count overlapping periodic fear damage twice. Flesh to Stone has explicit optional `flesh_body` data; native Petrified now includes Poison damage immunity as well as poison-condition immunity.

Payloads are real `SpellPayloadItem` values with original caster/DC/power and caster-owned `SpellPayloadLifetime`. Holder/container/floor location controls the explosion point, not the original cast position. Portable throw is paid; transfer keeps power/clock. Delayed touch failure explodes in place; success permits pickup or same-action throw. An ending veto leaves the item intact; capped deadlines do not keep increasing bead power. Accepted ending retires before blasting once. Suppressed-center expiry consumes without a later catch-up blast. Caster death/rest are gameplay endings; rejected creation and administrative world close retire without gameplay detonation.

Relevant granted IDs: `action.spell.arcane_sword.strike`, `action.spell.arcane_sword.move`, `action.spell.dispel_evil_and_good.break_enchantment`, `action.spell.payload.throw`, `action.spell.delayed_blast_fireball.touch`. Temporary items have IDs `spell_payload.freezing_sphere` / `spell_payload.delayed_fireball` and ordinary item-location/lifetime capture.

Forcecage retains native WallSection geometry. Seeing invisible force is required for Disintegrate; creator knowledge alone is not sight. A barred cage supports an actual10-ft breach while other faces/upper bars persist; a small box is removed as a whole. Misty Step now emits native paid PortalTransfer events, with relocation parented beneath that transfer. Failed CHA escape pays attempted resources without moving.

## Bounded adaptations and limits

- The optional Chilled→Frozen transition is omitted; existing Wet/Chilled/Brittle affinities remain.
- Feeblemind's30-day recovery uses native GM adjudication; there is no calendar scheduler or duplicate Befuddlement root.
- Foresight uses the agreed Action cast adaptation. Summon bodies use current-floor/native flight and grid geometry; no multi-floor project was included.
- No Dispel Magic or Rogue Evasion engine was added. Those absent native capabilities are not claimed as tested interactions.
- New Sorcerer learning entries use existing exact class-owned choices for Charm Monster, Vitriolic Sphere and Delayed Blast Fireball. Wizard catalog access remains existing behavior; no new Draconic Sorcerer progression grant was invented.
- Autonomous action legality/execution is qualified separately from optimal tactical preference. Utility actions retain their current engine profiles; no general BG3 status/AI framework was ported.

## Validation

- Expanded focused acceptance: **268 passed**,89.09s (new spells plus affected existing movement/condition/summon tests).
- Broad engine: **3,112 passed**,120 documented baseline cases deselected; archived solid-walls test ignored at collection.
- Player/progression/Python SDK: **499 passed**; one archived `game.runtime_protocol` test ignored at collection.
- TypeScript player SDK: **63 passed**. Active import/DAG/discovery/catalog gates: **35 passed**,5 documented legacy cases deselected.
- Final anti-slop, anti-OOP and plan-adherence reviews: **PASS**. Whitespace check: **PASS**.

Additional finite checks cover the lower-slot Counterspell CHECK under Foresight, Misty Step/Dimension Door paid failures and successes through both cage forms, mundane/Magic Weapon resistance, public item throw/Break Enchantment/Sword repeats, and accepted Dragon-record JSON round-trip/passive replay with unchanged native entity identities and event cursor. Later focused additions do not inflate the broad-lane count.

Configured Python typing matches the committed baseline: **92 existing diagnostics, zero new diagnostics**; all new modules are checked. Focused acceptance and active architecture checks were rerun after the final typing/narrowing repairs. Broad engine and player/SDK figures above describe the preceding integration runs.

The [implementation plan](plans/SRD_LEVEL_4_9_22_SPELL_IMPLEMENTATION_PLAN_2026-10-15.md) records exact commands, retained baseline exclusions and all limitations. The full architecture attempt still has18 stale archived-server, frozen-evidence and legacy-hygiene failures; this is not a full-repository green claim. The old standalone SDK generator still imports archived server modules; the active player SDK export/generation workflow succeeded. Prior36-spell historical results are not used as evidence for this batch.


## Subsequent 58-spell anti-slop review

The [fresh audit](SPELL_58_ANTISLOP_REVIEW_2026-10-15.md) records the later repaired bugs and current qualification: **483 combined tests passed**, 36 active architecture checks passed, and zero new Python diagnostics. Low-level repairs cover canceled smite casts, mark reapplication/owner loss, canceled field/light movement and stabilization/ground creation, independent Animal Friendship sources and Phantasmal Force's post-defense type choice. High-level repairs cover Sphere's external contact/forced-movement boundary, Antilife Shell's teleport/map-edge behavior, Air Myrmidon Tenacity's miss outcomes/current Strength formula, Break Enchantment's canceled-effect behavior and cold summon-recipe imports. Self mundane items, existing suppression/expiry/cleanup and the approved body/control model remain qualified. All repairs are in the working tree; no client code changed.
