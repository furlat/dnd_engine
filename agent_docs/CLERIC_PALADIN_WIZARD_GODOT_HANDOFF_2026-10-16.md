# Cleric, Paladin and Wizard: engine / Godot handoff

Worktree: `/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
Branch: `codex/spells-rank-one-two`. Implementation baseline: `a1349f52e8b`.
No NDClient files were edited. This document describes the delivered engine
contracts; validation results are recorded in implementation-plan section16.

Current update: the subsequent
[spell repair and Antimagic removal handoff](SPELL_CATALOG_REPAIR_AND_ANTIMAGIC_REMOVAL_HANDOFF_2026-10-16.md)
describes the delivered repairs and exact wire removals. Antimagic Field is no
longer installed. Current class spell counts and schema below reflect that update.

## Rules and delivered scope

Cleric/Life, Paladin/Devotion and Wizard/Evocation are playable through20 using
the existing direct creator and ordered level mutation. BG3 rules apply where
available; SRD5.1 supplies features beyond BG3's cap. Spell identities remain
restricted to SRD5.1/5.2. There are60 eligible installed Cleric roots,23 Paladin
and106 Wizard; these counts overlap and are not a distinct-spell total.

Life and Devotion selection happens at1; Evocation at2. No BG3-only Holy Rebuke
was added. Devotion's always-prepared spell pairs start at3. At17, Flame Strike
is available and Commune remains an explicit unimplemented spell gap:9/10 oath
spells, with no invented replacement. Existing multiclass ability prerequisites
and creator point buy remain. Equivalent Fighter/Paladin styles cannot be chosen
twice in either class order.

The earlier58-spell ownership repairs are part of this change. Wet owns burn
admission, Sphere owns Disintegrate interception, Feeblemind owns accepted Heal
cure, Aura of Life owns maximum-HP-reduction admission, and Forcecage consumes
the magical-transfer fact. No client approximation of those interactions is
required.

## Creation, levels and exact casting sources

Use `dnd.content.characters.builds.create_character(CharacterBuild(...))` and
`dnd.content.characters.progression.{add_class_level,remove_last_class_level}`.
Cold tables/choice requirements remain in `class_definitions.py`; each concrete
class has its own native grant receipts and exact cleanup. Do not construct
classes by adding only their level labels to an Entity.

New ordinary premade IDs:

| ID | Build |
| --- | --- |
| `hero.cleric_l5_life` | Life5, heavy armor/mace/shield, prepared healing and spirit spells |
| `hero.paladin_l5_devotion` | Devotion5, sword/shield, Dueling and prepared support |
| `hero.wizard_l5_evocation` | Evocation5, staff/robes,14 book spells and selected preparations |

An operator can supply `ServerConfig.player_builds` to the existing skirmish
launch path (`encounter_id=None`). This is private launch configuration, not a
new HTTP creator. Custom player builds cannot be combined with authored recipe
or seat assignments.

Each spell row retains `spellcasting_source_id`, `spellcasting_provider_id` and
`spellcasting_ability`. Cleric uses WIS, Paladin CHA, Wizard INT. Identical Cure
Wounds from two classes remains two choices with independently selected source
ability. Do not merge rows by spell ID or display name. Unscoped item casting
uses the supported BG3 last-new-casting-class policy; taking another level in
an earlier class does not change that fallback. Noncasting Champion does not
replace an existing casting ability.

All casters share one normal slot table. Capacity changes preserve spending and
converted extra slots. Class learning rank stays separate from shared capacity;
BG3 Wizard scroll learning/preparation can use shared slot capacity. Cantrips
scale by total character level. No client-side slot-table calculation is needed.

## Public protocol and discovery

The current player protocol is **schema11**, protocol version1. Canonical
schema/OpenAPI/field ledger are under `sdk/protocol`; both
`sdk/python/src/dnd_player` and `sdk/player-typescript/src` are regenerated.
The current player SDK is the supported surface. The historical
`sdk/typescript` generator imports removed server-directory APIs and was not
revived for this work.

Keep the existing choices -> selected prefix -> preview -> execute flow,
including state revision, discovery generation, command number, attachment and
ACK requirements. Submit exactly the chosen row/index and returned target
bindings. Variants such as Lay on Hands modes, Cleansing Touch's exact effect,
recovery ranks, ritual casts and free casts are separate native discovery rows.
Costs/display facts distinguish free and paid casts of the same base spell.

New command intents use the existing command envelope:

```json
{"kind":"prepare_spells","selection":{"source_id":"class.wizard.spellcasting","spell_ids":["spell.magic_missile","spell.shield"]}}
```

```json
{"kind":"study_spell_mastery","selection":{"rank_one_spell_id":"spell.shield","rank_two_spell_id":"spell.mirror_image","hours":8}}
```

Preparation source IDs are `class.cleric.spellcasting`,
`class.paladin.spellcasting`, and `class.wizard.spellcasting`. Preparation changes
require being outside combat. Validate/submit a complete replacement list;
domain/oath/signature spells remain always prepared outside that budget. Invalid
lists and stale/foreign commands leave authority unchanged. Temporarily reduced
INT/WIS/CHA does not discard an existing over-capacity list; further replacement
must meet current capacity.

Unpreparing the last Shield/Counterspell entitlement does not reset its disabled
automatic-reaction preference when the spell is prepared again in the same
runtime. No additional client preference store is required for that operation.

Combat end now publishes `boundary.lifecycle = "outside_encounter"` with a live
`state_revision` and `input_actor_uuid = null`. The same attached seat can query,
preview and act for its controlled players there, including Recovery and rituals.
There is no turn to end. Do not treat this boundary as terminal or close SSE.
The worker/recording remain live until explicit game end/shutdown, under existing
service limits. Terminal/closed delivery and explicit end-game behavior remain
the existing host lifecycle.

Outside-combat operations close their ordinary action/bonus/reaction/movement
debits between operations; slots and rest resources do not refresh. This is a
bounded operation policy without a new calendar or duration ticker. It does not
simulate elapsed world time. Native combat ending also releases turn debits.

## Spellbook, scrolls and rebuild inputs

Eligible existing scrolls expose their ordinary **Cast** plus **Learn Spell**
item uses. Learning costs no gold or spell slot, consumes the actual finite
scroll use, and respects Wizard membership, duplicate knowledge and shared slot
capacity. It does not auto-prepare leveled spells. Actual Fire Bolt scroll
learning grants an INT cantrip immediately. A non-Wizard scroll such as Spike
Growth stays castable without an invented Learn option.

Controlled HUD sheets carry:

- `class_levels` with exact choices, including Mastery/Signature selections;
- `scribed_spell_ids` for permanent learned knowledge;
- `prepared_spell_selections` for each class source;
- `permanent_feature_uses` for once-per-character features.

Carry these values into the corresponding `CharacterBuild` fields when rebuilding
(`prepared_spell_selections` becomes `prepared_spells`). A new untouched build
does not inherit another session's state. Class-level Wizard book choices are
reversible; scribed knowledge survives removing Wizard. Prepared-template changes
do not end cast-owned Bless, concentration, summons or retained strike actions.
Retained attack actions keep their casting ability if their source is removed.
Book/preparation/Mastery/permanent-use facts are redacted for nonowners, and HUD
sheets remain restricted to the authorized audience.

## Delivered class actions and passives

| Class | Clickable native action IDs |
| --- | --- |
| Cleric | `action.class.cleric.turn_undead`, `action.class.cleric.preserve_life` |
| Intervention | `action.class.cleric.divine_intervention.sunder_heretical`, `.opulent_revival`, `.arm_thy_servant`, `.golden_generosity` (same full prefix) |
| Paladin | `action.class.paladin.divine_sense`, `.lay_on_hands`, `.turn_unholy`, `.sacred_weapon`, `.cleansing_touch`, `.holy_nimbus` (same full prefix) |
| Wizard | `action.class.wizard.arcane_recovery` |

Discover these through normal content descriptors and action metadata. Do not
manufacture executable rows from this table or parse display names for rules.
Existing handler-toggle commands expose automatic reactions/features; Divine
Smite has no click-to-accept prompt. Its highest enabled affordable slot fires
once per melee hit. Class Smite is a magical class feature; learned5.2 Smite
retains spell restrictions. Improved Smite adds its separate native radiant
packet to every eligible melee hit, including critical doubling.

Life delivers Disciple/Blessed Healer/Supreme Healing, Divine Strike, channel
recovery and Destroy Undead's4d6 radiant damage. Healing bonuses are based on
actual spell origin and actual committed healing. Turned is a separate status,
not Frightened: three recipient turns, native flee/Dash or blocked Dodge,
no reactions, positive damage ends it after the initial Destroy damage settles.

Devotion delivers disease immunity, four existing fighting styles, Extra Attack,
Protection/Devotion/Courage auras, Sacred Weapon, Purity, Cleansing Touch and
Nimbus. Auras follow actual placement/faction/consciousness, strongest eligible
CHA bonus wins, saves include death saves, and radius grows10->30ft at18.
Devotion/Courage clear eligible existing local controls on entry and grant exact
owned immunities; Turned remains independent. Sacred Weapon follows the exact
item/current wielder, with owned light. Cleansing removes the selected local
spell root and preserves native Haste ending; removal veto spends nothing.

Evocation delivers Sculpt, Potent, Empowered and Overchannel through owning
handlers. Sculpt preview and execution exclude allies before saves/effects;
ordinary resulting fire/ice/ground environment is still ordinary environment.
Empowered INT applies per eligible damage instance, including missiles, rays,
retained fields, innate Rebuke and magical spell weapons. Potent's saved half
damage preserves the successful save and does not apply failed-save riders.
Overchannel is disabled by default, qualifies actual Wizard rank1–5 damaging
casts, counts once per accepted original cast and retains maximization for that
cast's ongoing damage. Later repeat activation/toggle changes do not select a
new cast. First use is free; subsequent recoil bypasses resistance/immunity.

Recovery restores existing rank1–5 slot debits using the daily point pool.
Mastery18 has unlimited free prepared base-rank1/rank2 choices; upcasts stay paid.
Its explicit outside-combat eight-hour study operation changes those two choices.
Signature20 has two always-prepared rank3 choices with separate short-rest uses.
Shield/Counterspell consume their actual eligible free-grant/reaction costs.

## Divine Intervention and permanent rewards

All four branches share exactly one permanent use,
`class_feature.cleric.divine_intervention`. It does not return on rests or
level removal/readdition. Actual committed costs record the permanent use even
if an earlier observer fails. Admission failures before payment spend nothing.

Sunder is enemy-only50ft,8d10 radiant, WIS half. Opulent recovers living allies'
HP/slots/rest resources and revives eligible intact dead player companions at
half their own maximum HP. It preserves actions, durations, concentration,
exhaustion, time and permanent-use resources; it does not call long rest.

Arm creates the permanent native `weapon.devotees_mace`: +3 mace,1d6 bludgeoning
+1d8 radiant and item-owned once/LR Healing Incense. The mace transfers and
survives class removal; healing is item-origin, not a Life spell. Golden creates
a permanent nearby ordinary chest: four greater-healing potions (4d4+4), Haste,
Greater Invisibility and True Seeing. Use existing storage/pickup/equip/drink
flows. No temporary-item subsystem or special client reward screen was added.

## Implementation owners and verification entry points

Cold data: `dnd/types/{character_progression,character_receipts,class_spells}.py`.
Composition: `dnd/content/characters/{cleric,paladin,wizard}_grants.py`,
`spellcasting_grants.py`, `caster_chassis.py`, `builds.py`, `progression.py`.
Rules: `dnd/classes/{cleric,paladin,wizard,divine,divine_intervention}.py`.
Knowledge: `dnd/characters/{spellbook,preparation,mastery}.py`.
Items/reactions: `dnd/items/{scroll_learning,divine_rewards}.py`,
`dnd/spells/reaction_costs.py`. Factual packet seam: `dnd/core/spell_damage.py`.

New regression suites are `tests/progression/test_{prepared_class_progression,
prepared_spellcasting,cleric_features,paladin_features,paladin_interactions,
wizard_features,wizard_owned_packets,divine_intervention}.py`, plus
`tests/player/test_{divine_and_wizard_transport,prepared_classes_http,
spell_ownership_recording}.py` and the58-spell ownership engine suite.
The HTTP test uses a real worker process and consumes/ACKs actual SSE records.
Both independent reviewer roles and the required plan-adherence monitor were
used; exact completed results and known unrelated baseline diagnostics belong
to the plan's implementation record.
