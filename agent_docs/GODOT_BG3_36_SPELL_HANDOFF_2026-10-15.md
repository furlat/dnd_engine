# Godot handoff: all 36 spells from the BG 3-style implementation batch

15 October 2026. Prepared for the human to give to the Godot implementer.
This is a description of delivered backend behavior and its current public
integration surfaces. Presentation suggestions below are suggestions, not
finished artwork, Godot code or evidence of visual acceptance.

## 1. Source and scope

- Implementation checkout: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
- Branch: `codex/spells-rank-one-two`, based on `feature/speedupsensory` at
  `229ce025f3f`. **The 36-spell implementation is committed on this branch.** A checkout of the
  base commit alone will not contain these spells. Use the implementation worktree
  or integrate its actual changes, including the four new source modules and
  generated SDK/protocol files.
- This handoff covers the **36 newly implemented spells**, all listed below.
  Enthrall and Heat Metal were explicitly excluded. The public catalog now has
  166 spells; this document does not replace documentation for the other 130 catalog spells.
- The matching document in the original
  `/mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/` is a document copy;
  the implementation code remains in the new worktree.
- Governing mechanics and final test record:
  [36-spell implementation plan](plans/BG3_STYLE_RANK_1_2_SPELL_IMPLEMENTATION_PLAN_2026-10-15.md),
  especially§1.3 and§10. No NDClient/Godot code or new artwork was implemented in
  that batch. This requested handoff does not claim those clients already render it.

All paths below are relative to the implementation checkout unless absolute.
The current source, generated schema and captured player values take precedence
over older Pygame/Pixi handoffs and old endpoint examples.

## 2. Public contract to consume

Use the checked-in production contracts together:

| File | Purpose |
| --- | --- |
| `sdk/protocol/player-api-v1.schema.json` | Exact player wire types. |
| `sdk/protocol/protocol-identity.json` | Protocol 1, player schema 9, exact schema digest. |
| `sdk/protocol/openapi.json` | Actual HTTP/SSE paths and envelopes. |
| `sdk/protocol/field-ledger.json` | Public fields and their native owners. |
| `sdk/python/src/dnd_player/contracts.py` | Generated Python reference values. |
| `sdk/player-typescript/src/contracts.generated.ts` | Generated TypeScript reference values. |
| `sdk/protocol/README.md` | Current optical/privacy/replay contract. Its introductory definition/field counts predate this batch; current export is 321 definitions/1,707 fields. |

Current digest:
`b6b49d33cae8aeda7ce422677716d8ac3e4ae970c766367a10d8ec9cb8d0bb52`.
Schema 9 alone is not an exact compatibility check: consume the identity digest
from the same checkout. PlayerSequence's internal `schema_version=5` is a different
version axis from the live protocol's `player_schema_version=9`.

### 2.1 Discovery, selection and submission

1. Request Choices for the currently authorized `input_actor_uuid` and
   `state_revision`. Retain `choices.discovery_generation`.
2. Read the four action arrays (`entity_actions`, `position_actions`, `self_actions`,
   `object_actions`). Use `behavior_id`/content identity for media and semantic
   lookup. Submit the returned **discovery_index**, never an index invented by
   concatenating/filtering UI arrays. `template_name` is an execution token, not
   a stable media key; variants can share a name.
3. Resolve `row.target_set` inside that response's `target_sets`. A subject binding's
   `subject` indexes that response's `subjects`; its position and every path position
   reference index that response's `positions`. `binding.index` is the native
   selection token. UUIDs identify actors/items, not interchangeable selection tokens.
4. Render variant choices from `variant_facets` and slot rank from `cast_at_level`.
   Preserve values verbatim: weapon-slot facets are **uppercase**, e.g.
   `form=MELEE_MAIN`; element/ability/form values elsewhere are lowercase.
5. Preview the selected prefix using the current revision/generation. A Preview
   owns its own subject/position/target-set tables; its references do not index
   Choices. Follow `next_target_set`, `next_positions`, `can_confirm` and `reason`.
   Area geometry/cells/affected recipients come from the preview, not a local
   rules-radius calculation. Use the native route/cost for Plant Growth.
6. Submit `ExecuteSelectionIntent` with the same generation and an ActionSelection:
   `action_index`, native `target_indices`, `extra_target_positions`, `prefer_safe`.
   Extra positions are **actual [x, y] values**, not compact position-table indexes.
   Use normal command-number/revision/attachment handling from the production protocol.
7. Consume the recorded operation and authorized after-values. Refresh discovery
   after state changes. Old repeat actions, old selections and old item-use rows
   can become invalid; there is no client-side entitlement extension.

Coordinates here are current two-integer grid positions; native rules feet are
5 ft per grid step. Use the client's established world transform. This batch adds
no alternate grid, multi-floor protocol or free-hover placement semantics.

Classes in§4 describe current authored metadata, not permission to create action
buttons for every class spell. Actual availability/targets/costs come from Choices.
Catalog ranges are base descriptions: attack-backed spells use their current
weapon, and selected previews/target pools are authoritative.

### 2.2 Costs that differ from ordinary casts

- Searing Smite, Branding Smite and Ensnaring Strike expose upfront action cost in
  `costs` and bonus-action/slot costs in **`conditional_costs`**, whose
  `trigger` is `hit`. Display both clearly. Do not spend/refund resources locally.
  On a miss only the weapon-attempt action is spent; native affordability also
  checks that the hit costs could be paid. Slow participates in that check.
- Divine Smite is handler-backed. Read `handler_details`, show each returned
  toggle's name/enabled state, and submit ToggleHandlerIntent with its **handler
  UUID** and discovery generation. Learned spell and class feature share the
  same toggles. There is no clickable Divine Smite cast or accept-reaction prompt.
- Temporary-item actions carry `is_item_use`, `source_item_uuid`,
  `item_charge_cost` and native inventory/charge values. Eat Goodberry is an item
  action, not a second casting of Goodberry.
- Repeat/reapply actions are discovered on the actor who can actually use them.
  They spend the declared action/bonus action but no new spell slot. Do not derive
  this by looking only at the repeat action's base spell level.
- Initial cast cancellation, native committed-but-interrupted outcomes and command
  rejection are distinct. Use cancellation/action-economy and HUD after-values;
  a canceled spell does not imply resources should be restored.

### 2.3 Facts, persistent owners and replay

| Public value | Godot use |
| --- | --- |
| `PlayerNode` identity, lineage/parent links, phase, cancellation, content_attributions | Associate one action with its real consequences; avoid replaying every phase as another cast. Effective-handler attribution identifies riders such as Divine Smite. |
| `SpellFact`, `AttackFact` | Disclosed source/target/application/outcome and ordinary weapon versus spell action presentation. A hybrid smite has one physical attack with a magical accent. Flame Blade still uses ordinary AttackFact/equipment plumbing. |
| `DamageResultFact(stage=applied)`, `HealFact`, `TemporaryHitPointsFact`, `LifeFact` | Actual damage/healing/HP/temp-HP/life after-values. Formulas in§4 explain rules; they are not a request to implement a second client combat solver. |
| `ConditionChangeFact`, `ConditionFact.state` | Exact condition UUID, authored behavior/semantic key, removal, duration, suppression and agency denial. Distinct sources can share a display name. |
| `ItemEffectChangeFact`, item/equipment/world after-values | Exact item/effect membership, custody, charges, visual loadout and retirement. See Magic Weapon's cold-state limitation in§7. |
| `SensoryFact.spatial_effects_changed/removed` | Disclosed field UUID/content_ref/positions, including partial changes. Use the observation's footprint, not the global native footprint. |
| `SensoryFact.light_sources_changed/removed` and native world tile updates | Optical source UUID/revision/position/radii and aggregate native illumination. Dim radius extends beyond bright radius. No local gameplay light solver is needed. |
| Actor observations, `summon_origin`, `SpatialFact.creation`, `terminal_departure/terminal_cause` | Real summoned actor appearance/lifetime. Creation is not every reacquisition; terminal departure is not every loss of sight. |
| `PortalTransferFact(committed=true)` | Optional Revivify reposition on the same actor UUID; portal_uuid can be null. |

A source can be optically disclosed without its actor/item identity. Respect null
anchors and observer privacy. Missing or empty disclosed footprints do not reveal
hidden targets; `resolved_area_positions` is an observed subset, not a complete
physical blast mask. Use current PlayerWorld/reduction/observations to rebuild a
scene on reconnect/seek; do not consult native Python entities from Godot.

Key persistent visuals by exact condition/spatial/item/entity UUID. Suppression
retains an owner while disabling its contribution; removal ends it. A field,
its actor and its trail are different owners. Recorded absence can mean loss of
observation; only native terminal evidence should choose a death/dissolution effect.

`ConditionDurationSummary` is native data, not a client timer. Some short effects
use handler deadlines and publish `permanent`/null remaining_rounds while active
(Mockery, Wisp, Dissonant fear, Ray poison, Acid Arrow, toxin and Glyph Sleep).
Do not create a countdown from animation time or reinterpret permanent as truly
infinite. Hold the status until authoritative removal/suppression/after-state.

## 3. Reuse across the new spells

- Use the existing ordinary target picker, single-position/area picker, cone
  direction picker, ordered multi-target picker and entity+destination picker.
  Orb/Arrow have creature versus ground variants; Revivify has in-place versus
  compound relocation. Avoid separate selection implementations per spell.
- Reuse damage, healing, control poses, item equipment and summon actor lifecycle.
  Spell-specific control identities can reuse artwork while retaining their own
  status, immunity, agency and removal rules.
- Marks and damage riders add accents to their real attacks. An automatic damage
  event is not proof of an attack roll; Hex does not apply to Magic Missile.
- Native elemental surfaces own their transformations. Water can become ice,
  electrified water or steam; fire can remove Plant Growth locally. VFX illustrates
  the recorded transition and must not cause damage or mutate the footprint.
- Generic Help is `action.ally_help`, one action at 7 ft for admitted allied recovery;
  it is distinct from making up spell-specific escape buttons. Sleep also has
  existing Shake Awake and successful Shove recovery.
- Magical protection is current native policy: Globe checks base spell level;
  Antimagic suppresses contributions and allows native deadlines to continue.
  Render actual physical hits even if their magical rider was prevented.

## 4. Complete spell inventory and cards

Notation: A=action, BA=bonus action; S=one spell slot at the selected rank.
Normal leveled casts pay A+S unless a card says otherwise. Concentration is
independent of payment. Damage formulas are base mechanics plus existing native
modifiers/critical rules. Class labels and base metadata below were read from the
current composed catalog; there are 5 cantrips,16 level 1,11 level 2 and 4 level 3 spells.

### Level 0 (5 spells)

| Spell | Authored identity | Classes | Base cast / concentration |
| --- | --- | --- | --- |
| Dancing Lights | `spell.dancing_lights` | Bard, Sorcerer, Wizard | A; concentration |
| Sorcerous Burst | `spell.sorcerous_burst` | Sorcerer | A; no concentration |
| Spare the Dying | `spell.spare_the_dying` | Cleric | A; no concentration |
| Starry Wisp | `spell.starry_wisp` | Bard, Druid | A; no concentration |
| Vicious Mockery | `spell.vicious_mockery` | Bard | A; no concentration |

#### Dancing Lights

Identity: `spell.dancing_lights` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Choose one legal position within 60 ft. Action; concentration for 10 rounds. This implementation creates one movable 30 ft bright light.

Retained state and follow-ups: Caster marker `condition.spell.dancing_lights`; follow-up `action.spell.dancing_lights.move` costs a bonus action, selects a position within 60 ft, and spends no slot. Concentration loss removes the light and repeat action.

Godot: Suggested presentation: one floating light or a decorative cluster sharing the one disclosed native emitter. Track the optical source UUID and its current position; remove/rebuild from observed state. A moving-light cast is a move of the existing effect.

Integration check: Check movement, concentration cleanup, Antimagic suppression and reconnect without replaying the original cast.

#### Sorcerous Burst

Identity: `spell.sorcerous_burst` in `content.srd_5_2_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Ranged spell attack within 120 ft. Action. `damage_type` selects acid/cold/fire/lightning/poison/psychic/thunder. Base 1d8, increasing at character levels 5/11/17. Rolled 8s can add extra d8s, bounded by the positive casting modifier.

Retained state and follow-ups: Instantaneous. Additional dice belong to the same attack resolution; they do not create extra projectiles or recursive hit riders.

Godot: Suggested presentation: one elemental bolt and one outcome-dependent impact; an explosion accent can follow recorded results. The selected element is present in Choices but is not a general field on SpellFact; see§7 before implementing observer/replay element-specific media.

Integration check: Check miss, critical, bounded extra dice and an actor with a different casting ability/source. AI outcome profiles forecast base dice only.

#### Spare the Dying

Identity: `spell.spare_the_dying` in `content.srd_5_1_cc`; necromancy. Source: `dnd/spells/necromancy.py`.

Selection and result: SRD 5.1 form: touch within 5 ft, action, no slot. Eligible creature is dying or stable at 0 normal HP; undead/construct targets are excluded. Stabilizes and resets death-save progress without healing.

Retained state and follow-ups: Life state becomes STABLE while HP stays 0. There is no lingering spell condition or concentration.

Godot: Suggested presentation: brief touch/stabilization accent; refresh the life-state/death-save UI from facts. Keep the body downed until another authoritative event changes that state.

Integration check: Check that neither a healing number nor an alive/standing transition is invented.

#### Starry Wisp

Identity: `spell.starry_wisp` in `content.srd_5_2_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Ranged spell attack within 60 ft. Action. Base 1d8 radiant with 5/11/17 cantrip scaling. Supports creatures and admitted objects.

Retained state and follow-ups: `condition.spell.starry_wisp` reveals the target and supplies 10 ft dim light until the end of the caster's next turn. A miss applies no target effect. Reveal expires without destroying any underlying Invisibility condition.

Godot: Suggested presentation: a radiant mote plus a small target glow anchored to the actual target/emitter. Restore ordinary visibility and light from server observations when the effect ends.

Integration check: Check an invisible recipient, expiration while suppressed, object targeting and the source-versus-recipient turn deadline.

#### Vicious Mockery

Identity: `spell.vicious_mockery` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: One creature within 60 ft; action; WIS save. Failure takes 1d4 psychic, scaling at 5/11/17, and gains next-attack disadvantage. Success prevents both.

Retained state and follow-ups: `condition.spell.vicious_mockery` ends after the recipient's next actual attack roll or its turn end. Its native duration summary is not a countdown of that handler deadline; follow removal facts.

Godot: Suggested presentation: short psychic/mockery accent and a temporary condition icon. It does not force movement or suppress the whole turn.

Integration check: Check save success, first actual attack consumption and expiry during Antimagic.

### Level 1 (16 spells)

| Spell | Authored identity | Classes | Base cast / concentration |
| --- | --- | --- | --- |
| Animal Friendship | `spell.animal_friendship` | Bard, Druid, Ranger | A+S; no concentration |
| Chromatic Orb | `spell.chromatic_orb` | Sorcerer, Wizard | A+S; no concentration |
| Create or Destroy Water | `spell.create_or_destroy_water` | Cleric, Druid | A+S; no concentration |
| Dissonant Whispers | `spell.dissonant_whispers` | Bard | A+S; no concentration |
| Divine Favor | `spell.divine_favor` | Paladin | BA+S; concentration |
| Divine Smite | `spell.divine_smite` | Paladin | Automatic on-hit toggle; no concentration |
| Ensnaring Strike | `spell.ensnaring_strike` | Ranger | A; hit→BA+S; concentration |
| Faerie Fire | `spell.faerie_fire` | Bard, Druid | A+S; concentration |
| Goodberry | `spell.goodberry` | Druid, Ranger | A+S; no concentration |
| Heroism | `spell.heroism` | Bard, Paladin | A+S; concentration |
| Hex | `spell.hex` | Warlock | BA+S; concentration |
| Hideous Laughter | `spell.hideous_laughter` | Bard, Wizard | A+S; concentration |
| Hunter's Mark | `spell.hunters_mark` | Ranger | BA+S; concentration |
| Protection from Evil and Good | `spell.protection_from_evil_and_good` | Cleric, Paladin, Warlock, Wizard | A+S; concentration |
| Ray of Sickness | `spell.ray_of_sickness` | Sorcerer, Wizard | A+S; no concentration |
| Searing Smite | `spell.searing_smite` | Paladin | A; hit→BA+S; concentration |

#### Animal Friendship

Identity: `spell.animal_friendship` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: Choose a beast with Intelligence≤3 within 60 ft. Action+slot; WIS save. Higher slots permit more distinct selected beasts through native multi-target selection.

Retained state and follow-ups: `condition.spell.animal_friendship` is a separate charm lasting 10 rounds. Positive damage from the caster or its original allied faction ends it. It does not transfer the beast into player control.

Godot: Suggested presentation: gentle charm accent and charm status; retain the actual actor identity/faction/control. Do not offer a new party-control panel merely because the spell succeeded.

Integration check: Check native target eligibility, multiple recipients, charm immunity and allied damage removal.

#### Chromatic Orb

Identity: `spell.chromatic_orb` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Action+slot;60 ft. `damage_type`: acid/cold/fire/lightning/poison/thunder. `side`: creature or ground; thunder has creature only. Creature attack: thunder 3d8, other elements 2d8, +1d8 per higher slot.

Retained state and follow-ups: Non-thunder creature variants place the selected surface at impact on hit or miss. Ground variants place a patch without initial attack damage. Acid/toxin use the two-round 7 ft spell patches; native cold/fire/lightning transitions remain authoritative.

Godot: Suggested presentation: selected elemental orb and impact, followed by the observed patch. Read `side` and `damage_type` from the selected row; do not derive them from the display name. Observer/miss-element metadata limits are in§7.

Integration check: Check ground with zero initial damage, creature miss with a patch, thunder without a patch and each elemental transition.

#### Create or Destroy Water

Identity: `spell.create_or_destroy_water` in `content.srd_5_1_cc`; transmutation. Source: `dnd/spells/transmutation.py`.

Selection and result: Action+slot; visible point within 30 ft. `form=create|destroy`. Initial radius 13 ft, +7 ft per higher slot; use actual preview cells.

Retained state and follow-ups: Create places persistent native water plus independent 3-round `condition.spell.rain_wet` on affected creatures: Wet/reveal. Destroy removes selected water, electrified water, ice, steam and the new simple toxin. Removing water does not cancel the independent rain lease.

Godot: Suggested presentation: finite rain/destroy accent plus actual observed surface transitions and Wet status. Shared Wet can have other sources; one source ending is not permission to clear every Wet visual.

Integration check: Check water persistence, rain expiry, destroy-water with retained rain, dousing and later fire/cold/lightning interaction.

#### Dissonant Whispers

Identity: `spell.dissonant_whispers` in `content.srd_5_2_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: One creature within 60 ft; action+slot; WIS save. 3d6 psychic, +1d6 per higher slot; successful save halves damage and prevents the fear rider.

Retained state and follow-ups: `condition.spell.dissonant_whispers` is a separate two-recipient-turn fear: movement blocked, attacks and checks disadvantaged. It persists outside caster LOS. It does not order a fleeing path.

Godot: Suggested presentation: psychic impact and fear icon/pose. Do not animate forced running or create a movement command.

Integration check: Check save-half/no-fear, fear immunity, LOS loss and expiry while suppressed.

#### Divine Favor

Identity: `spell.divine_favor` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Self; bonus action+slot; concentration for 3 rounds. Qualified weapon hits add 1d4 radiant, with native critical handling.

Retained state and follow-ups: Caster owns `condition.spell.divine_favor`. The effect does not add damage to spell attacks, unarmed/body attacks or automatic non-attack damage.

Godot: Suggested presentation: restrained weapon blessing and a radiant accent on qualified recorded hits. The buff is caster-owned, unlike Magic Weapon's exact-item enchantment.

Integration check: Check miss, critical and that Fire Bolt/Flame Blade/Magic Missile do not acquire this weapon-only rider.

#### Divine Smite

Identity: `spell.divine_smite` in `content.srd_5_2_cc`; evocation. Source: `dnd/spells/reaction_spell_content.py`.

Selection and result: Automatic melee weapon on-hit behavior, not a clickable cast. Learned spell and existing Paladin feature share native per-slot toggles L1–L5. The highest enabled affordable level fires once and pays one slot; no reaction confirmation/bonus-action cost.

Retained state and follow-ups: Root `spell.divine_smite`; effective hit handler `reaction.class_feature.paladin.divine_smite`. Toggles are separate handler UUIDs, despite sharing a behavior ID. Base radiant dice are 2d8 at slot 1, increasing to the native 5d8 cap, with an extra die against undead/fiends up to 6d8; critical handling remains native.

Godot: Suggested presentation: radiant accent on the actual successful melee weapon hit when effective-handler attribution confirms Smite. Show the five discovered toggles using their labels/UUIDs. Do not create an accept-reaction popup or a second attack animation.

Integration check: Check learned-only, feature-only, both registration orders, disabled/unaffordable high slots, a miss and a spell attack.

#### Ensnaring Strike

Identity: `spell.ensnaring_strike` in `content.srd_5_1_cc`; conjuration. Source: `dnd/spells/conjuration.py`.

Selection and result: Attack-backed selection: `form=MELEE_MAIN|RANGED_MAIN`. Weapon attempt pays the action; on hit pays the conditional bonus action+slot. Initial STR save prevents ensnaring. Range comes from the equipped weapon/current choices.

Retained state and follow-ups: `condition.spell.ensnaring_strike`: restrained, blocks opportunity attacks, and deals slot-level d6 piercing at recipient turn start, up to 10 rounds while concentrated. Allied `action.ally_help` within 7 ft ends it. No self-escape action or automatic repeat save was added.

Godot: Suggested presentation: one ordinary weapon strike, then vines only on accepted condition application; tick accents follow actual damage. Use the separate spell condition even if the same restrained pose is reused.

Integration check: Check initial save, hit-only payment, spell-weapon rejection, Help removal and no autonomous escape button.

#### Faerie Fire

Identity: `spell.faerie_fire` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Action+slot; point within 60 ft; implemented sphere radius 20 ft; DEX save on initial cast. Concentration for 10 rounds.

Retained state and follow-ups: `condition.spell.faerie_fire` reveals failed-save recipients, grants incoming attack advantage and emits native light. The selection area is an initial application, not an ongoing entry-triggered damaging floor patch.

Godot: Suggested presentation: cast-area reveal pulse followed by target outlines/glows owned by each accepted condition. Existing Invisibility survives underneath reveal.

Integration check: Check saved versus failed recipients, overlapping reveal sources and removal without deleting the original Invisibility effect.

#### Goodberry

Identity: `spell.goodberry` in `content.srd_5_1_cc`; transmutation. Source: `dnd/spells/transmutation.py`.

Selection and result: Action+slot; self or ally within 5 ft. Creates exactly four separate real `consumable.goodberry` items, each with its own UUID and one charge; no upcast increase. Recipient must admit the whole batch.

Retained state and follow-ups: Caster owns `condition.spell.goodberry.batch` until that caster's long rest. Items can be transferred/dropped normally and still expire with that source batch. `action.spell.goodberry.eat` is an ordinary discovered item use: bonus action,1d4 native healing, consumes that exact berry.

Godot: Suggested presentation: inventory arrival, normal berry use/healing and normal removal. Read source_item_uuid, charge/stack values and actual inventory/world after-values. The four berries are not one four-charge synthetic item.

Integration check: Check another actor consuming one, blocked healing, dropped/transferred berries, multiple batches, capacity rejection and rest during Antimagic.

#### Heroism

Identity: `spell.heroism` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: Action+slot; ally/self within 5 ft; concentration for 10 rounds. Immediately clears existing fear and grants fear immunity while active.

Retained state and follow-ups: `condition.spell.heroism` grants 5 source-owned temporary HP immediately and refreshes that pool at recipient turn start. Refresh is non-additive. Cleared fear does not resume after Heroism ends.

Godot: Suggested presentation: support accent, fear-icon removal and temporary-HP UI from native grant facts. Do not add 5 to the displayed pool each turn.

Integration check: Check existing fear, repeated refresh, another temporary-HP source and concentration cleanup.

#### Hex

Identity: `spell.hex` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: Bonus action+slot; one creature within 60 ft; concentration until native long rest/removal. `ability` selects strength/dexterity/constitution/intelligence/wisdom/charisma.

Retained state and follow-ups: Caster sustain `condition.spell.hex`; recipient `condition.spell.hex.quarry`. Caster's attack-roll hits add 1d6 necrotic; the chosen ability checks and linked skills are disadvantaged, not saving throws. `action.spell.hex.reapply` is a bonus action with no new slot after the quarry is defeated.

Godot: Suggested presentation: source-specific quarry mark and necrotic hit accents. Multiple casters can own independent marks on the same target. Marked damage does not mean every subsequent damage event gets Hex.

Integration check: Check A/B/A multi-ray hits, miss/crit, another caster, defeated-target retargeting and that Magic Missile gains no Hex.

#### Hideous Laughter

Identity: `spell.hideous_laughter` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: Action+slot; one creature within 60 ft; initial WIS save; concentration up to 10 rounds.

Retained state and follow-ups: `condition.spell.hideous_laughter` combines prone geometry with full-turn incapacitation. WIS recovery at recipient turn end and after positive damage, with advantage on the damage-triggered save. Ordinary Stand cannot remove the spell.

Godot: Suggested presentation: laughter/downed pose and the separate spell status; use agency_denial to disable unavailable turn controls. A prone-looking actor is not necessarily dead or an ordinary standable Prone recipient.

Integration check: Check native immunity aliases, Stand rejection, save-on-damage recovery and cleanup while other prone sources exist.

#### Hunter's Mark

Identity: `spell.hunters_mark` in `content.srd_5_1_cc`; divination. Source: `dnd/spells/divination.py`.

Selection and result: Bonus action+slot; one creature within 60 ft; concentration until native long rest/removal. Qualified caster weapon hits on the quarry add 1d6 matching the base weapon damage type.

Retained state and follow-ups: Caster sustain `condition.spell.hunters_mark`; target `condition.spell.hunters_mark.quarry`. `action.spell.hunters_mark.reapply` costs a bonus action without a new slot after quarry defeat, retaining the original sustain.

Godot: Suggested presentation: exact quarry marker, independent by caster/source. Reapplying moves the active quarry; it does not restart the spell or duplicate its bonus.

Integration check: Check weapon versus spell attacks, crit, defeated quarry, independent casters and concentration cleanup.

#### Protection from Evil and Good

Identity: `spell.protection_from_evil_and_good` in `content.srd_5_1_cc`; abjuration. Source: `dnd/spells/abjuration.py`.

Selection and result: Action+slot; self/ally within 5 ft; concentration until native long rest/removal. Eligible attacker/source types: aberration, celestial, elemental, fey, fiend and undead.

Retained state and follow-ups: `condition.spell.protection_from_evil_and_good` gives those attackers disadvantage and removes/prevents eligible source-attributed charm/fear. It is not blanket immunity to every attacker or every source of control. Cleared conditions do not resume later.

Godot: Suggested presentation: ward plus actual accepted status removals; attack and condition outcomes remain server-owned.

Integration check: Check an eligible fiend source versus humanoid source, current charm/fear, and ordinary unrelated status retention.

#### Ray of Sickness

Identity: `spell.ray_of_sickness` in `content.srd_5_2_cc`; necromancy. Source: `dnd/spells/necromancy.py`.

Selection and result: Action+slot; ranged spell attack within 60 ft. 2d8 poison +1d8 per higher slot. After a hit, a separate CON save determines the Poisoned rider.

Retained state and follow-ups: `condition.spell.ray_of_sickness.poison` uses native Poisoned semantics for two actual recipient turn ends. Attack miss creates no poison/save outcome; a successful CON save does not undo the attack damage.

Godot: Suggested presentation: poison ray and accepted poison condition. Distinguish attack miss from hit/save success.

Integration check: Check poison resistance/immunity, successful CON save after damage and expiry during Antimagic.

#### Searing Smite

Identity: `spell.searing_smite` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Attack-backed melee weapon attempt: `form=MELEE_MAIN`. Action upfront; bonus action+slot only on hit. Initial extra fire damage is slot-level d6.

Retained state and follow-ups: `condition.spell.searing_smite` is a separate burn, up to 10 rounds while concentrated. At recipient START, CON save first: success ends it; failure deals 1d6 fire. Wet or allied Help ends it. Already-Wet targets do not retain the burn.

Godot: Suggested presentation: one weapon attack with fire impact, then a persistent burn only when the condition exists. A successful recovery save has no burn-damage accent.

Integration check: Check hit/miss costs, Wet/Help, start-save order, Flame Blade rejection and physical hit surviving a blocked magical payload.

### Level 2 (11 spells)

| Spell | Authored identity | Classes | Base cast / concentration |
| --- | --- | --- | --- |
| Acid Arrow | `spell.acid_arrow` | Wizard | A+S; no concentration |
| Branding Smite | `spell.branding_smite` | Paladin | A; hit→BA+S; concentration |
| Calm Emotions | `spell.calm_emotions` | Bard, Cleric | A+S; concentration |
| Dragon's Breath | `spell.dragons_breath` | Sorcerer, Wizard | BA+S; concentration |
| Flame Blade | `spell.flame_blade` | Druid | BA+S; no concentration |
| Flaming Sphere | `spell.flaming_sphere` | Druid, Wizard | A+S; concentration |
| Magic Weapon | `spell.magic_weapon` | Paladin, Wizard | A+S; concentration |
| Moonbeam | `spell.moonbeam` | Druid | A+S; concentration |
| Pass without Trace | `spell.pass_without_trace` | Druid, Ranger | A+S; concentration |
| Phantasmal Force | `spell.phantasmal_force` | Bard, Sorcerer, Wizard | A+S; concentration |
| Spiritual Weapon | `spell.spiritual_weapon` | Cleric | BA+S; no concentration |

#### Acid Arrow

Identity: `spell.acid_arrow` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Action+slot;60 ft. `side=creature|ground`. Creature attack:4d4 acid +1d4 per higher slot. Miss deals half the initial roll but does not count as a hit for riders and has no delayed tick.

Retained state and follow-ups: Hit adds `condition.spell.acid_arrow`: one delayed 2d4 (+1d4 per higher slot) acid tick at the next recipient END, then removal. Creature hit/miss and ground mode place the acid patch. Ground mode has no initial attack damage or delayed target tick.

Godot: Suggested presentation: acid projectile/miss splash, observed patch and one factual delayed tick. A miss is not necessarily zero damage.

Integration check: Check miss-half without Hex, hit+tick exactly once, ground-only patch, suppression retirement without delayed damage. Forecast models immediate hit only.

#### Branding Smite

Identity: `spell.branding_smite` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Attack-backed weapon attempt: `form=MELEE_MAIN|RANGED_MAIN`; actual weapon range. Action upfront; bonus action+slot only on hit. Extra radiant damage is slot-level d6,2d6 at base slot 2.

Retained state and follow-ups: `condition.spell.branding_smite` reveals/glows for up to 10 rounds while concentration holds. A miss has no rider; blocked magic can leave the physical hit intact.

Godot: Suggested presentation: single weapon strike with radiant impact and a retained target reveal only on actual condition application.

Integration check: Check ranged variant, miss, invisible target after reveal, concentration cleanup, Flame Blade rejection and magical protection.

#### Calm Emotions

Identity: `spell.calm_emotions` in `content.srd_5_1_cc`; enchantment. Source: `dnd/spells/enchantment.py`.

Selection and result: Action+slot; point within 60 ft; sphere radius 20 ft; concentration 10 rounds. Implemented BG 3-style humanoid application with no initial saving throw.

Retained state and follow-ups: `condition.spell.calm_emotions` clears charm, fear, Rage/Frenzy and prevents their reapplication while active. It does not change faction or pacify enemy AI. Cleared effects stay removed after Calm ends.

Godot: Suggested presentation: calming pulse/status and actual removed control/rage icons. Keep hostility and targeting as supplied by the server.

Integration check: Check humanoid filtering, Rage/Frenzy cleanup, immunity while maintained and no resumed old effect.

#### Dragon's Breath

Identity: `spell.dragons_breath` in `content.srd_5_2_cc`; transmutation. Source: `dnd/spells/transmutation.py`.

Selection and result: Bonus action+slot; self or ally within 5 ft; concentration 10 rounds. `damage_type=acid|cold|fire|lightning|poison`.

Retained state and follow-ups: `condition.spell.dragons_breath` grants the RECIPIENT `action.spell.dragons_breath.exhale`: action, no further slot,15 ft cone, DEX half,3d6 at slot 2 and +1d6 per higher slot. Original caster DC/level/element remain retained; the recipient's casting stats do not replace them.

Godot: Suggested presentation: recipient empowerment plus a directional exhale from the actual acting recipient. Populate the repeat action only when discovered for the controlled recipient. Retained element/replay limits are in§7.

Integration check: Check different caster/recipient stats, all five elements, cone preview, repeat no-slot cost and grant removal.

#### Flame Blade

Identity: `spell.flame_blade` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Bonus action+slot; self;10 rounds; implemented without concentration. Creates/equips a real `weapon.flame_blade`, moving the previous main-hand item into ordinary inventory.

Retained state and follow-ups: Caster lifetime `condition.spell.flame_blade`; exact created item UUID. Normal Attack/Extra Attack plumbing makes melee spell attacks using retained casting accuracy,3d6 fire +1d6 per two higher slots, without ability damage. Hex can apply; weapon-only Favor/Mark/Smite cannot. Unequipping into the caster's inventory keeps it; dropping/transferring out retires it.

Godot: Suggested presentation: created fire weapon through ordinary equipment/attack facts, not a second special attack button. Native light is 10 ft bright plus 10 ft dim extension. Exact retirement removes only this blade and preserves the stored ordinary weapon.

Integration check: Check equipment replacement, ordinary attacks/crit, source casting ability, incompatible smites, custody and expiry.

#### Flaming Sphere

Identity: `spell.flaming_sphere` in `content.srd_5_1_cc`; conjuration. Source: `dnd/spells/summoning.py`.

Selection and result: Action+slot; admitted ground position within 60 ft; existence concentration 10 rounds. `form=flaming_sphere` summons one native autonomous allied body.

Retained state and follow-ups: Creature `creature.spell.flaming_sphere`, manifestation `spell_construct`;20 HP, AC 16, speed 30, reactions 0. Native bonus-action `action.spell.flaming_sphere.ram` has 5 ft contact, retained caster DEX DC, slot-level d6 fire, half on save. A moving 5 ft aura damages enemies at their END; breakable objects have sphere-END contact cadence. Ram is separate from aura exposure.

Godot: Suggested presentation: fiery rolling body, observed 20 ft bright+20 ft dim-extension light, moving aura and native fire trail. Sphere/aura/trail are separate owners. Dousing a trail does not despawn the sphere. No manual summon-control UI is implied.

Integration check: Check autonomous Ram, enemy-END aura versus friendly safety, trail damage to any faction, water/cold dousing, object contacts, concentration loss and summon departure.

#### Magic Weapon

Identity: `spell.magic_weapon` in `content.srd_5_1_cc`; transmutation. Source: `dnd/spells/transmutation.py`.

Selection and result: Action+slot; self/ally within 5 ft; `form=MELEE_MAIN|MELEE_OFF|RANGED_MAIN|RANGED_OFF` chooses an actually equipped weapon. Concentration until native rest/removal.

Retained state and follow-ups: `condition.spell.magic_weapon` belongs to the exact WEAPON item, not the wielder. +1 attack/damage, +2 at slot 4,+3 at slot 6; magical attacks. Strongest same-spell bonus wins. It follows transfer, composes with Shillelagh and is suppressed on appropriate Antimagic contact/path without removing physical damage.

Godot: Suggested presentation: enchant the exact item UUID. Live item-effect membership is available, but persistent Magic Weapon visual state is not currently included in the cold item_effects snapshot; see§7. Do not decorate every weapon held by the original caster.

Integration check: Check item transfer, Shillelagh, two casters/strongest fallback and a physical arrow crossing Antimagic.

#### Moonbeam

Identity: `spell.moonbeam` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/evocation.py`.

Selection and result: Action+slot; point within 60 ft; concentration 10 rounds. Implemented radius 3 ft. CON half,2d10 at slot 2,+1d10 per higher slot.

Retained state and follow-ups: Caster marker `condition.spell.moonbeam`, spatial owner `spatial_effect.spell.moonbeam`. Initial placement, entry, target START and moving the beam can expose recipients, at most once per target per native turn. `action.spell.moonbeam.move` costs an action/no slot, selecting a point within 60 ft.

Godot: Suggested presentation: one owned vertical beam following the observed current field. Its move is not a second independently persistent beam. Damage accents follow server ticks; entering and turn start must not produce locally duplicated damage.

Integration check: Check radius, actual preview cells, initial/entry same-turn deduplication, moving exposure and concentration cleanup.

#### Pass without Trace

Identity: `spell.pass_without_trace` in `content.srd_5_1_cc`; abjuration. Source: `dnd/spells/abjuration.py`.

Selection and result: Action+slot; self; concentration until native rest/removal. Moving 30 ft friendly aura grants nonstacking+10 Stealth.

Retained state and follow-ups: Caster `condition.spell.pass_without_trace`; beneficiary `condition.spell.pass_without_trace.bonus`; shared memberships use `condition.spell.pass_without_trace.membership`. Native spatial owner is `spatial_effect.spell.pass_without_trace`, but it does not expose a visible floor footprint by default.

Godot: Suggested presentation: beneficiary status/caster accent. A decorative aura is optional; do not fabricate a sensed ground hazard or uncover private membership. Leaving one overlapping source need not remove the shared benefit.

Integration check: Check movement in/out, allied filtering, overlapping casters and independent cleanup.

#### Phantasmal Force

Identity: `spell.phantasmal_force` in `content.srd_5_1_cc`; illusion. Source: `dnd/spells/illusion.py`.

Selection and result: Action+slot; one creature within 60 ft; initial INT save; concentration up to 10 rounds.

Retained state and follow-ups: `condition.spell.phantasmal_force` deals 1d6 at recipient START, initially psychic; the largest positive external damage component updates its future damage type, with stable ties. Its own damage and zero damage do not update it. Recipient END INT save can end it. Sources coexist independently.

Godot: Suggested presentation: mental illusion status and actual typed tick impacts. Current chosen damage type is not exported as an energy_type update in ConditionState; retain a neutral loop unless a future public field supplies it.

Integration check: Check external mixed damage, two casters, own-damage exclusion, repeat save and suppression.

#### Spiritual Weapon

Identity: `spell.spiritual_weapon` in `content.srd_5_1_cc`; evocation. Source: `dnd/spells/summoning.py`.

Selection and result: Bonus action+slot; admitted position within 60 ft;10 rounds without concentration. `form=spiritual_weapon`; one native autonomous allied weapon per caster/family, replaced by recast.

Retained state and follow-ups: Creature `creature.spell.spiritual_weapon`, manifestation `spell_construct`. Base 20 HP, AC 10, supported flying speed 20, reactions 0; HP+8 and force dice+1d8 per two higher slots. `action.spell.spiritual_weapon.strike` is its native bonus-action natural attack:1d8+1+retained casting modifier at base. Native ownership supports dismissal, defeat and expiry.

Godot: Suggested presentation: independent spectral weapon body with arrival/strike/departure. Preserve actor UUID/initiative; attacks are not the caster swinging a phantom item. No manual-control panel follows from ownership.

Integration check: Check actual force die/scaling/casting bonus, autonomous turn, next human boundary, recast replacement and exact terminal cleanup.

### Level 3 (4 spells)

| Spell | Authored identity | Classes | Base cast / concentration |
| --- | --- | --- | --- |
| Glyph of Warding | `spell.glyph_of_warding` | Bard, Cleric, Wizard | A+S; no concentration |
| Plant Growth | `spell.plant_growth` | Bard, Druid, Ranger | A+S; no concentration |
| Revivify | `spell.revivify` | Cleric, Paladin | A+S; no concentration |
| Vampiric Touch | `spell.vampiric_touch` | Warlock, Wizard | A+S; concentration |

#### Glyph of Warding

Identity: `spell.glyph_of_warding` in `content.srd_5_1_cc`; abjuration. Source: `dnd/spells/abjuration.py`.

Selection and result: Action+slot; point within 30 ft; radius 13 ft; no concentration. `form=acid|cold|fire|lightning|thunder|sleep|detonation`. Held until trigger/recast/caster rest.

Retained state and follow-ups: Caster owner `condition.spell.glyph_of_warding`; spatial owner `spatial_effect.spell.glyph_of_warding`. Hostile occupancy triggers once, then payload affects all eligible occupants/factions. Elemental variants deal 5d8,+1d8 per higher slot, DEX half. Sleep applies separate `condition.spell.glyph_of_warding.sleep` for two target-ENDs, with damage/Help/Shake Awake/Wet/successful Shove recovery. Detonation uses native forced movement up to 20 ft on failed DEX.

Godot: Suggested presentation: armed glyph, one trigger burst from actual payload outcomes and exact owner retirement. Retirement by rest/recast alone is not a detonation. Do not infer payload from damage alone: Sleep/Detonation need distinct outcomes. Persistent glyph payload is not exported in generic spatial state; see§7.

Integration check: Check initial hostile occupancy, one trigger under nested movement, all-faction payload, native Antimagic suppression without consumption and Sleep recovery.

#### Plant Growth

Identity: `spell.plant_growth` in `content.srd_5_1_cc`; transmutation. Source: `dnd/spells/transmutation.py`.

Selection and result: Action+slot; point within 60 ft; implemented sphere radius 20 ft;10 rounds without concentration.

Retained state and follow-ups: `spatial_effect.spell.plant_growth` imposes strongest 4× walking cost. Overlapping difficult terrain does not multiply this into invented 8×/16× costs. Freedom of Movement and flight bypass it. Native fire removes actual affected portions.

Godot: Suggested presentation: plants on currently disclosed field cells, including partial burned-away holes. Movement/path cost and legal routes come from discovery/preview, not a Godot terrain penalty calculator.

Integration check: Check overlap, bypasses, partial fire removal, visibility clipping and no regrowth after reacquisition.

#### Revivify

Identity: `spell.revivify` in `content.srd_5_1_cc`; necromancy. Source: `dnd/spells/necromancy.py`.

Selection and result: Action+slot 3+; eligible allied player companion within 30 ft, dead/dying/stable, intact remains. Implemented BG 3 adaptation restores 1 normal HP; no death-age/diamond system. Disintegrated/noncompanion recipients are invalid.

Retained state and follow-ups: `form=in_place|relocate`. Relocate uses existing `position_selection.kind=entity_destination`: select companion, then one native-admitted position. Both revive and optional transfer must admit before payment. Same actor UUID survives; accepted life state becomes ALIVE and optional committed PortalTransfer moves it.

Godot: Suggested presentation: revival accent and authoritative life/position updates. A revival is not a summon birth. Include eligible visible corpse choices even when the ordinary living-target pool omits them. Optional transfer does not require a visible portal object.

Integration check: Check dead/downed routes, exact 1 HP, both forms through server preview/submit, blocked destination, revival veto and transfer veto without payment.

#### Vampiric Touch

Identity: `spell.vampiric_touch` in `content.srd_5_1_cc`; necromancy. Source: `dnd/spells/necromancy.py`.

Selection and result: Action+slot; melee spell attack within 5 ft; concentration 10 rounds. 3d6 necrotic at slot 3,+1d6 per higher slot. Initial miss still leaves the accepted repeat-action grant.

Retained state and follow-ups: `condition.spell.vampiric_touch` grants caster `action.spell.vampiric_touch.strike`: action/no further slot, retaining slot and casting source. Healing is floor(half its own post-mitigation necrotic component), including native temporary-HP/overkill conventions; Hex/riders do not contribute. Ordinary healing blocking applies.

Godot: Suggested presentation: melee drain impact followed by actual HealFact, not a client calculation from total target HP loss. Repeat activation has its own action identity and belongs to the retained effect.

Integration check: Check resistance, same-type Hex, flat reduction, temporary HP, overkill, blocked healing, crit and repeat cleanup.

## 5. Follow-up actions and durable presentation keys

These are concrete current identities, not proposed endpoints or names to parse.
Discover every action normally; a root spell's presence is not a permanent grant.

| Action identity | Actor / cost | Selection / lifetime |
| --- | --- | --- |
| `action.spell.dancing_lights.move` | Caster / BA | Position within 60 ft while exact light grant is active. |
| `action.spell.moonbeam.move` | Caster / A | Position within 60 ft while exact beam grant is active. |
| `action.spell.hunters_mark.reapply` | Caster / BA | New quarry after prior defeat; retains sustain, no slot. |
| `action.spell.hex.reapply` | Caster / BA | Same as Mark; retains selected ability and exact source. |
| `action.spell.dragons_breath.exhale` | Empowered recipient / A |15 ft cone; original caster's retained source/DC/element/slot. |
| `action.spell.vampiric_touch.strike` | Caster / A |5 ft spell attack, retained slot/source, actual own-component healing. |
| `action.spell.goodberry.eat` | Berry holder / BA | Native item use with exact source_item_uuid/charge consumption. |
| `action.spell.spiritual_weapon.strike` | Autonomous summoned weapon / BA | Existing native natural-attack composer; force damage. |
| `action.spell.flaming_sphere.ram` | Autonomous sphere / BA |5 ft saved fire contact; independent from aura. |
| `action.summon.dismiss` | Summoner / A | Admitted owned summon; one exact terminal departure. |
| `action.drop_concentration` | Caster / declared native costs | Standard discovered concentration removal, not a new spell endpoint. |
| `action.ally_help` | Allied helper / A | Native 7 ft recovery targets; removes only admitted recovery effects. |

Root descriptors carry authored `presentation.icon_key`, `vfx_profile`,
`visual_variant_key` and `ui_group`. For this batch the logical spell icon/VFX
keys generally equal `spell.<id>`. Resolve the actual descriptor; the presence of
a key does not prove a Godot resource/texture/audio file was delivered.
Full ContentRef includes pack/kind/content_id/version/contract hash. Do not invent
full refs from spell names or assume child conditions live in the same pack as
their root. Instances sharing a behavior ID still have different UUIDs.

## 6. Summon and temporary-item presentation

### 6.1 Spell constructs

Both new summons use `SummonManifestation=spell_construct`, not the existing
natural/fey_spirit/fiend palette branch. Branch creature appearance by disclosed
creature content identity: `creature.spell.spiritual_weapon` or
`creature.spell.flaming_sphere`. The factories do not provide authored sprite/body
resources for these new forms. A spectral weapon and fire sphere are suggested
Godot appearances; resource production/integration remains client/art work.

Use ordinary actor observations, position, stats, initiative, faction and summon
origin. Native controllers act autonomously on their own turns, joined after the
caster. Ownership gives dismissal/lifetime; it does not grant a player seat or
manual movement/attack controls. Defeat, expiry, dismissal and sustain loss remove
the body without a normal corpse. `closed` is cleanup and should remain silent.
Loss of sight and Antimagic absence are not ordinary defeat. Recast of Spiritual
Weapon retires the previous same-caster weapon and creates a distinct actor UUID.

Sphere has observed light/aura/fire-trail ownership in addition to its actor.
Destroying/suppressing/retiring one trail segment is not authority to remove the
sphere. Restore active owners from cold observed state rather than replaying
arrival effects on every snapshot.

### 6.2 Temporary items

Goodberry uses four max-stack 1, single-charge native consumables; Flame Blade uses
one exact equipped weapon per created item. Use ItemPresentationState and ordinary
inventory/equipment/world updates for identity, current custody, charges and
removal. The source-owned lifetime can retire an item held by someone else or
lying on the floor. An old item-use button becomes stale when that UUID retires.

Flame Blade's ordinary equipment attack is mechanically a spell attack. An
AttackFact remains part of ordinary attack presentation; `attack_source_kind`
(`equipped`, `unarmed`, `natural`) is not the same axis as native damage-hook
`attack_kind` (`weapon`, `spell`, etc.). The latter is not a universal public
AttackFact field. Identify the disclosed blade by source_item_uuid/item_id and
its authored presentation; eligibility remains server-owned.

Magic Weapon is an enchantment on an existing item, not a temporary replacement.
Source-owned retirement of a blade must never delete the mundane weapon stored
when the blade was equipped. See§7 before promising persistent enchantment media.

## 7. Explicit presentation/data gaps

The native spell tests prove rules and public command flow. Godot media coverage
remains to be implemented and checked. The following are concrete current limitations, not permission to
invent inferred state or instructions to redesign the protocol.

| Need | Current evidence | Consequence for integration |
| --- | --- | --- |
| Element of an observed/missed Sorcerous Burst or Chromatic Orb; chosen Dragon's Breath element | Choices expose facets to the selecting player. Generic SpellFact omits variant_facets and chosen element; actual typed damage/surface evidence may disclose an outcome later. | Local own-action previews can show the chosen variant. Full observer/replay element-specific cast media needs a deliberate public snapshot field or other explicit accepted representation. Do not assume a selector's transient UI memory is replay authority. |
| Exact ground destination in an instantaneous cast fact | Native position selections are present in Choices/Preview. Current SpellFact projection includes target_position for object contact and aoe_position for AoE; it does not generally retain a position_los/position ground destination. Follow-on disclosed fields/optical observations may carry an anchor. | Ground travel/impact for other observers or cold replay cannot universally use SpellFact alone. Use explicitly observed anchors when available; exact cast-to-ground media needs a deliberate public destination field rather than inferring a center from clipped cells. |
| Armed Glyph payload, including Sleep/Detonation | Native GlyphOfWardingZone.payload is private spell state. Generic PerceivedSpatialEffect does not populate this payload/energy choice. | A neutral observed glyph is supportable now. Exact armed variant appearance for cold/reacquired glyphs needs backend presentation data; don't identify it only from later damage. |
| Current Phantasmal Force damage mode | Native condition updates its private damage_type. Its generic ConditionState does not publish energy_type or a mode-change snapshot. | Neutral retained illusion visual plus actual typed damage impacts is supportable; a continuously recolored status requires explicit public mode state. |
| Persistent Magic Weapon enchantment on an item | Live item_effect membership has exact item/effect UUIDs and causal attribution. MagicWeaponEffect does not override snapshot_item_effect; cold ItemPresentationState.item_effects therefore does not contain its retained enchantment. | A cast accent/live membership can be associated exactly. Correct cold/reconnect/transfer glow needs an exported item effect state; do not attach the enchantment to the wielder or infer it from an item name. |
| Remaining count for handler-deadline effects | Public duration can be permanent/null while a private native handler tracks one/two actual turns. | Show the status/removal accurately; do not fabricate a numeric ticking countdown from replay or animation time. A numeric countdown would need a native remaining-deadline summary. |
| Visible Pass without Trace ground footprint | Native aura is not has_visible_presence by default. Benefits are visible as recipient conditions. | Beneficiary status works; no sensed terrain mesh/hidden membership should be invented. |
| New spell-construct bodies, temporary-item art and per-spell VFX/audio | Backend emits logical descriptors and actual lifecycle. New media was not imported or produced for this batch. | Map accepted existing resources where suitable or arrange the needed artwork separately. No resource path or completed art binding is promised here. |

The private native DamageComponentResolution/source_damage_uuid supports exact
Vampiric healing. It is not a generally exposed public per-component damage ledger
on DamageResultFact; Godot should show the already-authoritative HealFact.

Native ActionOutcomeProfile is an actor-baseline forecast, not the executed result:
Burst's extra-die expectation and Acid Arrow's miss/delayed branches are not fully
represented. Do not label its forecast as a guaranteed final HP change.

If precise media requires one of these missing fields, report the specific desired
public state against its native owner. The client should not import backend runtime
classes or reconstruct hidden source state to fill the gap. This handoff makes no
engine changes for those additional presentation fields.

## 8. Concrete integration verification

Use real production Choices/Preview/Command/Advance, authoritative after-values
and captured replay. The native setup/reference files are:

| Concern | Existing executable reference |
| --- | --- |
| Paid casts, controls/reveal/immunity/life/temp HP | `tests/engine/test_bg3_rank_one_two_spells.py` |
| Conditional costs, all hit riders, marks/reapply, exact Magic Weapon, shared Smite toggles | `tests/engine/test_bg3_spell_hit_riders.py` |
| Lights, water/patches, delayed Arrow, moving Moonbeam, Glyph and partial Plant Growth | `tests/engine/test_bg3_spell_fields.py` |
| Real berries/blade, ally Breath, Revivify vetoes/relocation, component-exact Vampiric healing | `tests/engine/test_bg3_spell_items_and_repeats.py` |
| Autonomous constructs, exact force strike, Ram/aura/trail and departure | `tests/engine/test_bg3_spell_summons.py` |
| Multi-turn native combination | `tests/engine/test_bg3_spell_integrated_encounter.py` |
| Real worker discovery/preview/submit; dead-companion compound selection; combined spell encounter | `tests/player/test_bg3_spell_transport.py` |
| Source-owned Sorcerer learning | `tests/progression/test_bg3_sorcerer_spell_learning.py` |

Useful Godot verification cases are the same observable boundaries:

- Cast and move Dancing Lights/Moonbeam, then break concentration: one active
  owner, correct disappearance, no old repeat button or repeated birth.
- Choose creature versus ground Orb/Arrow: actual target picker changes, misses
  do not invent hit riders, patches/ticks follow native results.
- Attempt each conditional-cost weapon spell on hit/miss/protected target: correct
  resource UI and one physical attack, with no duplicated caster/impact animation.
- Gain Heroism, Calm, Protection and spell-specific fear/laughter: correct removal,
  muted suppression, agency and no resumed cleared condition.
- Create, consume, transfer and expire berries; equip/unequip/drop/expire Flame
  Blade; enchant/transfer Magic Weapon and identify the cold-state gap explicitly.
- Grant Breath to another controlled actor and cast its repeat cone with retained
  source; repeat Vampiric Touch without a slot; honor actual HealFact.
- Revivify a visible companion in place and by compound destination, including a
  rejected destination/veto: same actor UUID, actual 1 HP and committed transfer only.
- Summon both constructs, allow their autonomous turns, return to human input,
  dismiss/defeat/recast/suppress/expire them and keep trail/actor owners distinct.
- Replay/seek/reconnect from after a cast and after partial field removal; use
  current observations and avoid revealing hidden actors, variants or retired items.

These are client-facing verification examples, not a request to rebuild mechanics,
write a second engine or wait on a new universal media system.

## 9. Delivered backend evidence and remaining responsibility

All 36 roots are implemented/registered. The saved final qualification reports
155 new spell/server/progression tests passing;2,971 engine tests passing after
explicit existing-failure exclusions;91 Python SDK/schema tests and 63 TypeScript
SDK tests passing; zero new Pyright diagnostics versus the original checkout.
The final implementation plan records baseline/historical failures honestly;
there is no whole-repository-green or Godot visual-acceptance claim.

For this handoff, the 36-entry inventory was checked against current composed
catalog and actual discovery rows, durable child action/condition declarations,
public facts, spatial observations and item/summon owners. Source remains
uncommitted. No other chat was read/contacted and no client code/art was changed.
The human can give this document to the Godot implementer as-is.
