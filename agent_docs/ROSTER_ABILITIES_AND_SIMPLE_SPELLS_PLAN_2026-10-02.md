# Roster abilities, simple spells and enchanted carried gear

October 2, 2026. Design and bounded native implementation approved by independent anti-slop and ECS/anti-OOP reviewers. Native checkpoint: [implementation](ROSTER_ABILITIES_IMPLEMENTATION_2026-10-02.md). Visual integration and full character registration remain separate completion steps.
Parent: [complete roster port](FIXED_ASSETS_AND_SCENARIOS_PLAN_2026-10-02.md).
The accepted item rules/materials stay complete. This is the next design lane,
not permission to rewrite attacks, condition infrastructure or accepted rendering.
Character registration follows this work; scenario redesign and multi-Z remain deferred.
The human subsequently deferred ordinary Grapple and grab-specific roster abilities.
The existing Grappled condition remains; this batch adds no grab, dragging or hand-reservation system.

## Decisions and completion boundary

The human corrected the earlier inventory: existing conditions are applied by
abilities; they are not new per-spell/per-action implementations. Inventory
**selected abilities and their missing behavior**, not standard condition names.
The bible's invented signatures are proposals, not mandatory content. Prefer
existing SRD spells, attacks, traits and equipment properties; discard gratuitous
signature duplication while accounting for every one of the 150 source rows.

Use SRD 5.1 as the single rules baseline for this batch. Do not combine a 5.2
casting time with a 5.1 effect. Original arrows/backpacks and simplified flight
are explicitly original game adaptations. Keep source attribution in existing
content provenance; public code contains no vendor art. SRD provenance is not
an assertion that artwork has the same license.
Official source: [SRD 5.1 under CC-BY-4.0](https://www.dndbeyond.com/attachments/39j2li89/SRD5.1-CCBY4.0_License_live%20links.pdf).
Retain its exact required attribution in distributed notices and native provenance.

Do not implement Mage Hand, Dispel Magic, Detect Magic, Disguise Self or Scrying
in this batch. Suggestion, Time Stop, Animate Dead and general transformations
are also deferred: they introduce substantial behavior outside simple combat
effects. Unsupported source spell lists must be named as adapted NPC profiles,
not certified as complete canonical Archmages/Druids.

## 1. Reconcile the complete roster before adding rules

Inputs: the frozen artist-review JSON, item-first V2, possession-level ownership
supplement, and complete-item-materials-handoff.json. Preserve these inputs.
An append-only authoring receipt accounts for all 150 rows and each proposal:
native base kit; exact gear IDs; selected existing spell/trait/action; selected
source clip; effect owner; baked/shared/missing media; retain/replace/defer
decision and reason. This receipt is audit data, not a second runtime rule engine.
The [complete disposition table](ROSTER_ABILITY_DISPOSITIONS_2026-10-02.md) accounts
for all 150 rows through 78 exact signature groups. The private exhaustive audit
in `.runtime/ability-plan-20261002/roster-audit.md` retains recorded clip-layer
evidence; that is not certification of pixels not freshly inspected. The
[spell audit](../.runtime/ability-plan-20261002/spell-audit.md) records exact SRD
witnesses and code owners. These are the detailed companions to this plan.

Check weapon delivery against actual evidence. Initial audit found Disrupting
Shot proposals on Goblin17, Orc01 and Orc12 without an established bow-shot
binding; Orc12's bow interpretation was withdrawn. Do not grant a bow or change
gear merely to rescue those names. Reconcile stale identity/kit descriptions with
the accepted items before binding any action.

The complete disposition table is authoritative for exact selections (including
Eldritch Blast, innate Burning Hands and Divine Eminence). Broad families below
explain the consolidation; they do not introduce alternative grants.

| Bible proposal family | Plan disposition |
| --- | --- |
| Shield Escort, Shield Cover, Sunward Cover | Reuse existing Fighting Style Protection where its exact shield/range/visibility rules fit; no three new reactions. |
| Blade Parry | Reuse existing Parry with the authored bonus and reaction budget. |
| Crossing Blades, Cross-cut, Bone Wheel, Rage Wheel | Prefer ordinary equipped attacks or authored Multiattack composition. Do not automatically add no-reaction riders or extra attacks. |
| Driving Blow, Charged Punch, Dragging Slam, Tool Hook, Hooking Chop | Prefer ordinary attack/shove or an existing supported maneuver; no five duplicate displacement executors. Any retained attack-plus-push must explicitly justify its additional rider and cost. |
| Grave Pin, Pinning Arrow, Disrupting Shot | Defer arbitrary pin/no-reaction riders unless actual selected art requires a distinct ability. Existing standard arrow attacks remain valid. |
| Ember Orbit, Red Crescent, Cinder Sweep, Flame Pillar, Sunburst, Venom Ring | Match area and damage to existing Burning Hands, Thunderwave, Shatter, Poison Spray or other supported SRD spell only when geometry/gesture actually fits. Similar colors alone are insufficient. Otherwise retain the source clip as unselected, or document a bounded custom exception before implementation. |
| Dawn Strike and other extra elemental weapon damage | Use completed item properties or existing actor traits; never duplicate the same damage as both a weapon property and an ability. |
| Arc Arrow, Flare Parry, Void Guard, Commanding Cut, Lurch | Optional custom proposals, deferred by default; these do not block a complete roster with honest adapted kits. |
| Hook Claw, Crushing Hold, Grip Training | Retain ordinary attacks and authored skills; defer Grapple and grab-on-hit behavior at the human's direction. |
| Spined Body | Retain only for a selected intrinsic spined creature with actual mechanical justification; no damage inferred from a silhouette alone. |
| Wight Life Drain, innate Invisibility, Magic Resistance, Devil's Sight | Use the exact shared-action/creature-effect contracts below. Armed Imp-derived variants omit Sting/Shapechanger; source deviations remain explicit. |
| Legendary actions/resistance | Keep an explicit boss-only backlog; not mandatory for every elaborate Devil drawing. Existing CR/name proposals remain provisional without the selected mechanics. |

These substitutions create clearly identified adapted characters, not modified
canonical SRD statblocks. Preserve a source-trait/spell disposition for omitted
abilities. If the retained art fundamentally requires a custom ability, record
that exception and its exact rule/visual contract rather than silently substituting.

## 2. Conditions and effects: reuse their actual owners

Selected actions apply existing native conditions through the normal event
queue, saves/immunities, source identity, concentration, turn clocks and removal.
No per-character Poisoned, Grappled, NoReactions or Prone clones. Keep damage
type separate from condition application: poison damage does not imply Poisoned,
and cold damage does not imply a movement debuff.

The reconciliation receipt must identify true missing behaviors, such as selected
SRD Life Drain maximum-HP reduction. Add only those effects to their existing
capability owners. No generic effect scripting
language, new inheritance hierarchy or parallel condition registry. Spell-specific
buff payloads are legitimate where the spell has genuinely distinct behavior;
they do not replace or rename standard conditions.

Before installing an effect define its public trigger, target, save, duration,
stack/reapplication policy, source cleanup, immunity and action economy. Reuse
existing semantic identities and observer projection. A color or baked aura is
never the source of a rule.

### Exact shared action and creature effect contracts

The existing Shove is a BG3-style bonus-action/passive-defence/weight-distance
adaptation. Preserve it; roster references to Shove mean this native game rule,
not the contested SRD action. Do not rewrite it in this lane.

| Selected effect | Existing owner / bounded missing implementation |
| --- | --- |
| Wight Life Drain | New selected intrinsic 5ft melee attack, baseline +4, 1d6+2 Necrotic. Hit DC13 CON: failure reduces maxHP by damage actually taken until long rest; cumulative owned reductions, death at maxHP0, survives source death. Reuse health.max_hit_points_bonus and ordinary damage/death/condition facts. May replace only one Longsword in its melee Multiattack, never add a bow rider. Defer 24-hour zombie creation/control as explicit adapted-Wight omission. |
| Armed Imp-derived rows | Choose depicted weapon attacks plus innate Invisibility/Magic Resistance/Devil's Sight. Omit Sting and Shapechanger for these adapted minor devils; no hidden tail attack or unsupported beast rig. |
| Innate Invisibility | Action, no slot, indefinite concentration; breaks on attack/concentration ending, equipment included. Reuse Invisible/Concentrating but retain this innate lifetime, not the timed spell's contract. |
| Magic Resistance | Missing reusable registration: contextual advantage on saves against spells and other explicitly magical effects, via actual effect provenance and existing save modifiers. No all-saves bonus; mundane poison does not qualify. |
| Devil's Sight | Existing dnd/blocks/sensory.py / SensesType.DEVILS_SIGHT; author the actual range. Keep obstruction and invisibility rules; no new sensory system. |
| Magical natural attacks | Existing attack-source magical status, scoped to exact intrinsic natural attack. Physical damage type stays physical; no Force conversion/inventory drop or actor-wide weapon buff. |
| Innate flight | Same ground-to-ground/no-hover policy, but retain authored innate flying speed; do not inherit the spell's 60ft or concentration. |

## 3. Simple SRD spell batch

The historical difficulty ranking is in
`to_archive/claude_docs/SORCERER_SPELL_ANALYSIS.md` and
`to_archive/claude_docs/CLERIC_SPELL_ANALYSIS.md`. Those are planning estimates,
not current correctness receipts. Fly is marked EASY; Suggestion/Time Stop are
VERY HARD. Verify the following against official SRD 5.1 before coding:

| Spell | Required behavior and ownership |
| --- | --- |
| Shillelagh | Bonus action; touch a held wooden club/quarterstaff; one minute; optional spellcasting ability instead of Strength for its melee attack/damage (retain Strength choice), d8 base damage and magical weapon status. Ends when cast again or the caster lets go. Modify the exact possession, not every weapon or another wielder's attacks. Preserve unrelated enchantments/coatings. |
| Longstrider | Action, touch, one hour, no concentration; +10 feet speed; higher slots add recipients. Owned speed modifier removes only its own contribution. |
| Barkskin | Action, touch, concentration up to one hour; effective AC cannot be below 16 under the 5.1 rule, rather than a flat +AC bonus. Preserve better armor/shield outcomes and remove only this contribution. |
| Produce Flame | Action; hand flame lasts ten minutes without concentration; bright light 10 feet plus dim light 10 feet. Create and hurl in the same action or hurl later: ranged spell attack 30 feet, d8 fire with cantrip scaling; hurling ends the flame. Casting again/dismissing ends the prior flame. Native light and its lifetime must follow the caster. |
| Fly | Action, touch, concentration up to ten minutes; 60-foot flying movement speed; higher slots add recipients. Reuse existing flying traversal rather than require Dragon Wings or instantiate an unrelated wing feature. Ground-to-ground movement only in this game adaptation: no hovering, altitude selection or aerial attack state. |
| Fire Shield | Action, self, ten minutes, no concentration. Light 10 feet bright plus 10 dim. Warm grants cold resistance and 2d8 fire retaliation; chill grants fire resistance and 2d8 cold retaliation. Qualifying melee hits by attackers within five feet trigger it even if incoming damage becomes zero. No save/reaction cost; misses/ranged hits do not trigger, retaliation cannot recursively trigger another shield. Action dismissal. |

Fly is a deliberate simplification, not exact tabletop flight. Use actual flying
traversal costs/clearance and the common movement expenditure. End every leg on
a legal support position; never end suspended in blocked/unsupported space.
Walls/closed doors remain barriers; flying does not grant sight, attack clearance
or blanket immunity to ground effects. Preserve reactions and existing native
hazard sampling. No invented height rule exempts a creature from a fire wall.
Early interruption must settle at a legal support position through existing
movement cancellation; no endpoint teleport. Concentration ending between legs
removes only the speed/traversal grant. General falling/multi-Z stays outside scope.
Flying speed is mode-specific: granting 60 feet must not raise walking speed to
60. Reuse one movement expenditure history across walking/flying/Dash, following
the SRD different-speed switching rule; no second free movement pool. Move the
minimum reusable grant/admission contract into a neutral owner if needed; the
spell must not import the Sorcerer's Dragon Wings action.

Fire Shield is included as the sixth bounded spell after source verification;
reuse existing resistance/light/post-hit packet systems. Existing spells such as Web,
Slow, Command, Bless/Bane, Shield, Fireball and invisibility are reused, not rewritten.

## 4. Stackable special arrows through normal attacks

Initial original-content selection: Ember, Frost and Storm arrows, each adding
1d6 of its named damage type to a bow/crossbow hit. No automatic burning terrain,
freezing, chain lightning, blindness or invented conditions. Do not relabel
poison damage as Poisoned.

Venom Arrows instead use the existing Basic Poison hit payload: DC10 CON,
1d4 Poison on failure, no Poisoned condition, no doubling that poison packet on
criticals. They are original sealed single-release payloads: inventory arrows
do not start a coating expiry clock. Reuse the poison resolver without changing
Basic Poison's accepted coating duration/ownership or making a coating permanent.

Arrows are selectable inventory stacks, not an equipped ammunition/quiver slot.
Ordinary shots still need no ammunition tracking. Special selection augments the
existing ranged Attack declaration: same weapon UUID, hand/loadout, range,
attack target, attack roll, damage, suggestions and attack budget. Initially
admit bow/crossbow deliveries only; a musket cannot fire an arrow.

Consume exactly one arrow at committed release, including a miss; reject invalid
targets or pre-release cancellation without spending the stack. Never spend twice
on child damage events, replay, reaction or duplicated observations. Stage the
selected payload/quantity reservation through existing action admission so a
failed action cannot eat inventory. Inventory ownership and stack changes emit
existing authoritative events; extend typed facts only for genuinely missing
selected ammunition identity/packet data. No second UseArrow combat executor.

Available uses follow the already accepted normal attack budget: Extra Attack,
Haste, Slow and Action Surge. Check ordinary/reaction/offhand routes separately;
no ranged shot is admitted merely because a melee opportunity exists. Arrow
selection must not mint extra attacks or turn NPC Multiattack into Extra Attack.
Hit dice follow existing critical rules; Basic Poison keeps its accepted rule.

Initial arrow selection is admitted only for normal main-hand bow/crossbow Attack
(including Extra Attack, Haste and Action Surge) and weapon-selected NPC ranged
Multiattack. This batch adds no offhand/reaction/Frenzy special-arrow route;
ordinary existing attacks remain unchanged. Melee opportunity attacks never
become arrow attacks. Replay does not expend native inventory again.

## 5. Three useful backpack-slot items

These are proposed original items, built through existing canonical item
composition and item-owned granted actions/resources. All use the real BACKPACK
slot and existing Bag2 palette variants; no new weapon/pack geometry.

| Item | Exact proposed power |
| --- | --- |
| Ember Quiver | Once per long rest, one action coats the user's current bow/crossbow with the existing +1d6 Fire coating for ten rounds. Use its existing stacking/ownership/transfer semantics; no ammunition supply or compartment simulation. No extra attack is granted. |
| Wayfarer's Pack | Once per long rest, cast Longstrider at level 1 on self without a spell slot. Normal one-action cost, duration and existing removal semantics. |
| Warden's Pack | Once per long rest, cast existing Resistance on self without a spell slot; normal action/concentration/duration, not permanent save advantage. |

Charges belong to the item instance, survive drop/loot/save/load, and cannot reset
by unequipping or transferring to another actor. Recharge only through
a minimal item-owned recharge hook in the existing long-rest lifecycle. Existing SpellItem charges do not yet have a demonstrated refill connection; implement that connection once, preserving UUID charges and rejecting duplicate recharge visits. Activation requires actual BACKPACK equipment, not merely inventory possession. Equipping/removing grants/revokes the action;
already resolved spells/coatings retain their own native lifetime and source
rules. Invalid use spends neither action nor charge. Only three deliberately
distinct abilities; ordinary quiver/canister remains ordinary gear.

## 6. Rendering coverage and handoff

### Selected effect coverage receipt

| Selected effect | Current source/registration evidence | Disposition, owner and reuse |
| --- | --- | --- |
| Ordinary weapon attacks, elemental/psychic held items and coatings | Accepted complete-item-materials-handoff.json; game/data/item_appearances.json and item-materials.json; fixed source companion layers in private roster audit | Existing item palettes/bloom work held and ground. Fixed body/FX bindings still require per-clip inspection during full character port; no second generic flare over baked item FX. Item-owned, transferable. |
| Eldritch Blast replacement | game/data/spell_recovery/bindings.json: spell.eldritch_blast and recovered.eldritch_blast.dense.v1 | Existing registered shared projectile candidate. Native spell is selected; source fixed caster gesture still must be calibrated. No free-beam attack alias or claim every source gesture already fits. |
| Burning Hands, Fire Bolt and other retained source spells | Existing respective native spells and passive spell bindings; per-row frozen clip records in private audit | Reuse registered spell media; resolve exact clip gesture and baked-layer suppression during body port. Spell targets/areas remain shared; source body art alone may be fixed-rig specific. No new custom cone/pillar executors. |
| Resistance / Warden's Pack | game/data/condition-media.json: support.resistance.back/front | Registered shared condition attachment. Pack grants native cast; ordinary lifetime controls the layers. No pack-specific aura. |
| Life Drain | Existing damage facts; no certified Life Drain contact bank in this audit | Ordinary compatible melee gesture allowed; reusable maxHP-reduction cue and contact treatment remain a media gap. Intrinsic Life Drain action grant does not transfer with a weapon. |
| Innate Invisibility | Existing Invisible/concentration and subjective rendering paths | Shared visibility/material response. Exact activation burst is unverified/unbound here; no need for a new per-Imp condition. Equipment follows visibility. |
| Magic Resistance / Devil's Sight / magical natural attacks | Existing save modifiers, sensory DEVILS_SIGHT and attack-source status | No mandatory new animation. Publish actual outcome/visibility through existing facts; no permanent aura inferred from these traits. |
| Shillelagh | No certified native spell-specific binding in this audit; accepted item palette/material donor is available | Shared application/held-weapon effect is pending exact recipe; no new weapon geometry. Native modifier ends on release, unlike transferable coatings. |
| Longstrider / Fly | Existing ordinary movement and historical movement-cue sources; no certified binding for these exact new cast memberships | Shared casting/movement grant cues need recipe admission. No hovering pose; innate flyers retain compatible source motion and authored speed. Do not certify historical handoff art as imported/accepted for these spells. |
| Barkskin / Fire Shield | No certified exact maintained memberships or fire/cold retaliation bindings in this audit | Reusable application/sustain/removal and post-hit impact gaps; appearance changes do not alter armor equipment. Fire Shield retaliation is actual damage, not an item enchantment. |
| Ember/Frost/Storm/Venom arrows | Existing projectile art and palette donors; no selected-ammunition VFX registration yet | New reusable arrow travel/contact recipe gap. Original arrow silhouette may be reused and palette-swapped; do not distort a spell projectile into a certified arrow without inspecting it. Ammo-owned payload; bow/fixed sheet alone does not own the extra effect. |
| Wayfarer/Ember packs | Existing Bag2 source and item materials; Longstrider and fire coating owners | Existing pack geometry only. Shared spell/coating presentation; no bespoke pack particles. Charges persist with the item. |

This is an exact planning availability/gap receipt, not completed pixel acceptance.
No fixed body signature is locked to a character solely because its target VFX
is baked in one clip. Body gesture may be rig-specific; rules and effects use
their selected native owner. Source inspection must separate baked pixels before
admitting the full clip, otherwise leave that optional clip archived.

For every selected action record separately: body gesture; contact/release timing;
projectile; recipient/area effect; sustained effect and removal. Existing source
clip effect layers are evidence: classify baked actor/item/spell/anatomy components
using the possession supplement, not the old source filename. A baked blade flare
must not spawn twice via generic VFX. Item effects follow transfer to modular
holders and floor; intrinsic anatomy/character effects do not.

Character restriction is warranted only for intrinsic anatomy or a gesture whose
art is available only on that fixed rig. A reusable spell, item or condition must
remain usable by modular and compatible custom characters. If an exact source
gesture is unavailable, choose an honest existing cast/attack gesture with shared
media, or disclose unsupported media; never change native rules to hide a gap.

Palette replacement/bloom on existing modular equipment remains allowed; no new
weapon geometry or generated weapon art. New reusable spell/arrow VFX is a
separate explicit artist handoff: hand flame + native light for Produce Flame;
Shillelagh application/held weapon material; Barkskin application/sustain/removal;
Longstrider/Fly movement cues; elemental arrow travel/contact and poison treatment.
Use registered equivalent media first. Request only gaps established by audit,
through the spells production owner, after backend specifications settle.

All playback derives from received native events/conditions/ownership and sampled
movement, never final-state masks or world reads. Preserve subjective visibility,
real floor tiles, wall/window occlusion, original shadows and accepted cloud/wall
rendering. Source clips that remain unselected stay archived privately.

## 7. Implementation order and verification

1. Finish/freeze the exhaustive 150-row selected-mechanic and VFX disposition
   receipt; reconcile stale bible signatures and item riders. Review exceptions.
2. Implement the six selected simple spells through existing native capabilities;
   verify effect application/removal and movement before new VFX production.
3. Complete selected missing canonical monster mechanics; compose existing
   attacks/traits/spells and conditions without per-NPC executors.
4. Add the bounded arrow selection/consumption contract to normal Attack and
   three item-owned backpack actions. Coordinate shared files with spells lane.
5. Write the exact reusable-media gap handoff, then integrate received assets
   through existing import/presentation paths after private preservation.
6. Verify native events and saved subjective replay, then full engine suite and
   relevant shared renderer suites. Document and discuss unrelated failures;
   do not change test expectations just to get green.
7. Only after these dependencies pass, register the complete 150-character
   roster with the honest adapted kits and selected body/media contracts.

Read HOW_TO_TEST.MD before tests. Observable cases include actual attack outcomes,
speed/AC/weapon stats, inventory quantity/charges, ownership transfer, source
expiry, concentration, long rest and replay. Re-run the existing Haste × Extra
Attack × Action Surge × Slow matrix with special arrows, plus offhand/Frenzy
regressions. Include misses, rejected actions, interrupts, empty stacks and item
transfer exploits. For media: no effect before contact, no duplicate baked FX,
multiple victims concurrent when the native cause is simultaneous, and supported
condition/body states across modular/custom rigs. Use normal engine gallery
recordings, meaningful durations and four cameras; no new preview format.

## Reviews and scope status

Both independent reviewers approved the amended plan and durable 150-row/78-group
disposition table. The reviewers' minor wording corrections are applied. Approval
is for design, not implementation or uninspected artwork.
The native batch is implemented and reviewed; final verification is recorded in
the linked checkpoint. This design is not completed media coverage, full roster
registration or a guarantee that all old SRD source spell lists are supported.
