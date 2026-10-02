# Item content for the complete fixed-art roster

October 2, 2026. Scope: the missing gear and deliberate appearance/mechanical
variants needed by all 150 retained characters. This is the next content lane
after the [implemented prerequisites](ITEMS_PREREQUISITES_IMPLEMENTATION_2026-10-02.md),
not another item-framework rewrite. Conditions/abilities, characters and their
animation port follow, in that order; scenario redesign and multi-Z stay deferred.
The [full-roster port plan](FIXED_ASSETS_AND_SCENARIOS_PLAN_2026-10-02.md) remains
the parent plan. This document replaces its pending item-prerequisite assumptions.

Status: the original plan and this full V2 update have both received independent
anti-slop and ECS/anti-OOP reviews for coverage/design. Exact unsettled gameplay
values still require the acceptance tables described below. Scope is **all 165 deduplicated item
requirements for all 150 characters**, including missing bases, partial garments,
accessories, lawful hand variants, effect ownership and fixed-holder loss.
A compatible-color subset is an execution step, never the definition of completion.
The settled first step is implemented: 110 new appearance recipes, complete original
action media, cloak and explicit partial-garment support. See
[the implementation checkpoint](ITEM_CONTENT_IMPLEMENTATION_2026-10-02.md).
The remaining records and unsettled gameplay proposals below stay in scope.

## Current foundation and evidence limits

| Current production capability | Use in this lane |
| --- | --- |
| One canonical direct table: 289 item builders; 47 cold weapons and 64 wearables | Reuse bases and register only deliberately new mechanical identities |
| Immutable creation transforms and shared native property composers | Create supported enchanted variants without a script/subclass per item |
| Accepted ownership/location transfers and exact item-owned coating cleanup | Preserve properties, remaining duration, native sustainer and UUID through loot |
| 77 visual categories / 205 named variants; 76 categories bind existing factories | Select existing appearances before adding any colors or geometry |
| 42 hand substitutions and 282 ground bindings | Reuse the same item identity across hands, floor, pickup and recipients |
| 645 original selected sheets; source palette replacement | Keep colors as palette swaps, original alpha/shadows and source registration |
| Two accepted complete native-event transfer recordings | Reuse the normal engine review format and meaningful duration |

## Frozen completed intake and exhaustive crosswalk

Private intake is now
`.runtime/pack-study-20260930/integration-preparation/item-first-v2-20261002/`.
`handoff-v2.json` SHA-256 is
`fb25c343932523a684e2ea03db9aa287dfd73fc311cfb685867f6b5f9e5e9b8c`.
The author froze this delivery; the original V1 remains preserved. Read
`production-consumption.json`, `deduplicated-items.html`, `media-receipts.json`
and `vfx-transfer-matrix.json` beside the illustrated bible. The portable ZIP is
`output/fixed-character-complete-bible-v2-20261002.zip` (282,377,789 bytes,
2,410 members, CRC checked by the producer).

The completed study accounts for 150 characters, 1,200 region checks, 478 depicted
possession/outfit instances, 469 selected appearance recommendations and nine
instances without selected compatible media. There are 165 deduplicated records:
159 selected and six media-gap groups. Visual outcomes are 46 reused appearances
and 113 new palette/layer recipes. The producer's separate ordinary-base readiness
classification is 45 reuse / 108 new recipes / 12 decision records. These count
different things; neither proves native eligibility or complete media admission.
Our independent category/base/slot/primary-layer check admits 101 of the 113 new
recipes structurally; seven waist-only recipes, three accessories, one offhand
longsword and one maul need the work described below. They are not discarded.

[The exhaustive crosswalk](ITEM_CONTENT_ROSTER_CROSSWALK_2026-10-02.md) lists all
165 records, exact references and every consumer. It also accounts for all 51
proposed item-owned clip components across ten holders. The full effect study
classifies 355 components over all 1,034 selected source clips: 216 cosmetic,
63 spell, 42 proposed item enchantment, 11 creature ability, 14 intrinsic anatomy
and nine proposed item coating. These are evidence-backed author recommendations,
not accepted native rules. Some component ownership still needs correction:
a green shield gesture or body ritual is not automatically sword poison because
another clip from the same character depicts a green blade. The author completed
a possession-level supplement without changing the frozen V2 snapshot. Its append-only
directory is `.runtime/pack-study-20260930/integration-preparation/item-ownership-supplement-20261002/`.
Fresh source inspection already separates the Witchdoctor's actor-centered glyph
ring from sword coating, splits sword/guard/body portions of Attack3, and finds
that the blue marksman's sparks are mainly on torso/head/limbs rather than proof
of an enchanted bow. Final component/property recommendations are still being
written. Preserve those distinctions when replacing the initial candidate matrix.

Current selection-media audit reports 328 unique sampled source resources:
210 registered/present, 204 identical to archive originals, 118 not registered.
The six differing registered Shoes2 action sheets are reported, not overwritten.
For the 101 structurally compatible recipes alone, 17 source keys have missing
action registrations (96 absent records in the sampled audit). Import required
original action sheets and verify applicable complete rig clocks/directions before
admission; Idle comparison plates are insufficient. Historical preset labels and
old `production_bound` flags still do not establish runtime readiness.

## Frozen roster reconciliation (before this implementation)

The updated author study is pinned at
`.runtime/pack-study-20260930/integration-preparation/gear-roster-current-20261002/current-review.json`,
SHA-256 `61d66023c9ba70b2f9142200c412c5d2d32956d2a16f5d91c7dd716257d38fbc`.
It retains all 150 characters / 478 possessions / 165 deduplicated records:
110 admitted appearances, 46 existing appearance reuse and nine remaining
base/slot/media requirements. This is not a claim of 156 completed item mechanics.
All 150 body choices are reviewed: 145 selected native body items and five
explicit absences. Preserve this snapshot and the original frozen V2 separately.

32 Armor Scraps holders need reconciliation of selected body item against the
old kit; 30 historical AC numbers differ from the item-plus-shield baseline.
Those comparisons exclude natural defenses/talents and are not proof of engine
AC bugs. Before character grants, select physical armor behavior per exact
possession/coverage, account separately for natural defense/talents, and recompute
final actor AC through the normal native system. Do not alter engine AC to match
an old prose number or tint every metallic scrap into plate armor. Item admission
and character stat/CR reconciliation are separate acceptance results.

The five psychic families are six physical weapons (the paired scimitars are
separate UUIDs). Each selected derived definition must be linked to the exact
possession in the later character grants. Strong new weapon damage replaces
three historical inferred-necrotic kit riders, requiring encounter/role balance
reassessment when characters are authored. No automatic level-dependent damage.

## Human decisions — October 2 follow-up

The human confirmed that purple glowing weapons deal psychic damage. They are
not merely cosmetic. Added damage must be an item-owned packet through the
existing creation transform and survive hand changes, drops and pickup. The human
delegates power design: choose added psychic dice and +1/+2/etc enhancement by
enemy role/power rather than requiring another approval for each value. Start
with deliberately strong authored tiers and tune later; these are static item
definitions, not damage recomputed from the current holder. Keep detached body
rituals separate. This confirmation supersedes cosmetic-only recommendations
in the supplement table below. Enhancement bonuses are deliberately authored
under the delegated power design, never inferred automatically from a tint.

No separate firearm proficiency is required for this roster lane. Author the
musket without adding a new proficiency category or feat requirement; retain its
ammunition/loading/two-handed restrictions and the normal attack pipeline.

The human delegates designing and implementing the depicted loadouts. Give the
specific characters explicit supporting talents/abilities instead of changing
Longsword properties globally or giving all actors special hand permissions.
Study equipment admission, attack eligibility, bonus attacks, weapon switching,
reactions and their received presentation together. The existing circus
DualWielder condition only grants AC: it does not already solve non-light
left-hand equipment or two-weapon attack eligibility. The sword/bow character uses the already supported melee/ranged loadouts and
existing switching route. Do not introduce a special bow talent or one-handed
shooting rule: select the depicted melee weapon for melee and bow for ranged,
with the correct action sheets. A bow-tip bonus attack is an optional later
authored ability, not required to solve the loadout. No silent rendered hand
substitution or bypass of two-handed weapon constraints.
Include these grants in later character authoring, with shared capabilities
implemented before their use. Independent anti-slop and ECS review are required.

Fixed-sheet equipment removal is deferred by the human. Do not force ordinary
loot into bound/conjured fiction merely to match baked sprites. A later pixel-art
lane may alter only the final dead frame; live removal states remain a separate
artwork limitation. No new art-editing chat has been requested yet.

## Next implementation slice and acceptance

Fresh independent anti-slop and ECS/anti-OOP reviews approve this revised
planning contract, including psychic definitions, ordinary Maul and the explicit
non-light offhand talent lifecycle. This is design approval, not a claim those
capabilities are already implemented. Reviewers requested remaining historical
rows point to the same contract; those corrections are applied.

Psychic gear uses existing `named_item`, `with_weapon_bonus` and `with_extra_damage`
creation transforms. Three power bands guide selection: +1 with 1d6 psychic,
+2 with 2d6 psychic, +3 with 3d6 psychic. Register only the specific selected
family/tier definitions, not every base/tier combination. Initial assignments:
paired elite violet scimitars +2/2d6 each; violet greataxe +2/2d6;
violet trident +2/2d6; violet sword tip +2/2d6; violet ritual sword +3/3d6.
Historical Infernal Weapons kit riders inferred from these violet blades are
replaced by the selected psychic packet, not stacked as extra necrotic damage.
Genuinely independent abilities retain their own explicit source.
These deliberately strong initial values are tunable cold content, not holder-level
runtime scaling. Exact possession IDs come from the complete supplement.
Detached rituals/guard crescents do not become item enchantments. Fancy control
riders may follow later when a specific creature ability justifies one; do not
introduce a new condition merely to fill this table.

The ordinary missing Maul is 2d6 bludgeoning, Heavy and Two-Handed. Its native
base can be admitted before exact art, but must not masquerade as exact modular
maul media. Musket stats above remain explicit; audit actual ammunition/loading
support before claiming the full firearm behavior implemented.

Non-light offhand capability is owned by the actor's shared equipment/attack
capabilities, granted by a specific talent, not by a special longsword subclass.
Both equipment suggestions and authoritative equip validation must use the same
eligibility. Bonus attack eligibility must preserve the project’s accepted ability to choose
either hand first, bonus action availability and existing Slow/Haste/Extra
Attack/Action Surge rules; do not add a new prior-main-hand-attack gate;
normal attacks and opportunity attacks keep their existing budgets. Talent removal
must not leave an unexplained eligible offhand action. Design its grant/removal
behavior before code; do not misuse the current AC-only circus DualWielder.

Offhand talent contract for implementation review: grant an actor-owned capability
before initial equipment installation. One equipment-owned effective slot query
combines unchanged item baseline slots with that capability; both discovery and
authoritative validation use it. Only one-handed melee weapons gain MELEE_OFF:
exclude ranged and TWO_HANDED weapons, preserve shields and footprint conflicts.
The talent itself adds no damage/ability modifier or AC; the existing AC-only
circus condition and Two-Weapon Fighting style remain separate grants.

Remove the last grant transactionally: if its removal would make an occupied
MELEE_OFF weapon illegal, ordinary unequip must return it to the holder’s
inventory, retaining UUID/properties and emitting existing equipment events.
A canceled unequip leaves both grant and equipment intact; no partial revocation
or floor drop. Remaining independent grant keeps eligibility. Revalidate the
capability and active loadout at action execution. Existing explicit reaction,
normal action, restricted-action and Multiattack costs are not overwritten;
ordinary offhand attacks keep the current bonus-action default and either-hand-first
policy. No budget reset/refund on grant/removal. This uses Equipment-owned UUID capability receipts, installed through
EquipmentConfig before initial gear or explicitly granted by Entity. Owning
talents must honor a refused final revoke; no generic condition-removal hook is
introduced. It is not a mutable sword property or actor-name
check. Test apply/remove/reapply, blocked removal, two grants, birth ordering,
suggestions and commands, and the existing action-budget matrix.

Observable checks: psychic packets and enhancement resolve through real normal
attacks, retain their same physical item/properties after drop/pickup, and do not
add damage to a different equipped weapon. Test both legal and rejected offhand
commands and replay the selected melee/ranged action with its actual equipment.
No special object-attack route, per-item event executor or runtime filename rule.
Run full engine checks after the native slice and combined renderer checks once
spells sources are stable. No new art-editing thread requested.

VFX integration/handoffs route to `01a0fd33-69ff-7321-bada-ba124e477822`
(Queued spells — production integration); original art production routes to
`01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` (Godot). Items remain in this lane.

## Completed ownership supplement and remaining native proposals

The append-only supplement is complete, SHA-256 `b67321d90be224fd7136bb6426b297850fed3f10dd00f9125ce13b34995f8524`,
under `item-ownership-supplement-20261002/` beside the V2 intake. It covers all 51
initial item-FX candidate records as 77 separated components, all ten families,
all 12 decision entries, seven partial recipes/29 consumers and all 150 fixed-holder
loss reviews. No rule below is inferred from art or silently installed by the
settled appearance step. Review/accept these exact remaining proposals in this plan.

The ownership split is 36 item-associated cosmetic parts, 29 detached cosmetics,
nine coating candidates, two creature-ability parts and one no-established-effect
part. It corrects the original holder-wide assignments, not the preserved V2 data.
Witchdoctor actor glyphs do not follow sword poison; the blue bow user's body sparks
do not establish an enchanted bow. No full ordinary fixed-holder removal media
family was found. Empty-equipment art/precise isolated media remains required.

| Visual family | Native base recommendation | Proposed property/owner | Implementation rule |
| --- | --- | --- | --- |
| Paired violet blades | weapon.scimitar, weapon.scimitar | Confirmed item-owned psychic damage plus deliberately authored enhancement tier; magical identity explicit. Detached actor accents remain separate. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Violet long axe/blade | weapon.greataxe | Confirmed item-owned psychic damage plus deliberately authored enhancement tier; magical identity explicit. Detached actor accents remain separate. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Violet trident tip | weapon.trident | Confirmed item-owned psychic damage plus deliberately authored enhancement tier; magical identity explicit. Detached actor accents remain separate. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Violet sword tip | weapon.longsword | Confirmed item-owned psychic damage plus deliberately authored enhancement tier; magical identity explicit. Detached actor accents remain separate. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Ember longsword A | weapon.longsword | Implemented magical Ember variant: composed 1d6 fire packet, no automatic +1. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Ember longsword B | weapon.longsword | Implemented magical Ember variant: composed 1d6 fire packet, no automatic +1. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Ember greatsword | weapon.greatsword | Implemented magical Ember variant: composed 1d6 fire packet, no automatic +1. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Poisoned sword and separate ritual | weapon.longsword | Implemented Basic Poison: one action application, DC10 CON on hit, failed save 1d4 poison, success zero, ten encounter rounds; no Poisoned condition. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Violet sword and separate body/guard tint | weapon.longsword | Confirmed item-owned psychic damage plus deliberately authored enhancement tier; magical identity explicit. Detached actor accents remain separate. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |
| Blue body sparks; bow association unproven | weapon.longbow | Body-owned cosmetic/ability; no bow property established. | Only accepted property/coating and object cosmetic move with item UUID. Body/ritual/guard accents stay with actor. No ground aura invented. |

Existing coat code is not exact basic poison: its unsaved 1d6 fire/lightning path
must not be relabeled poison. Reuse item UUID/lifecycle ownership while adding
only the accepted save/dice/expiry behavior through the shared native owner.
The two ember longswords share one derived definition; ember greatsword
uses the same supported packet transform on its own base. Repeated FX clips do
not create extra hits, independent damage timers or new property kinds.

| Remaining record | Concrete base/action proposal | Media / loss work |
| --- | --- | --- |
| gap.0492850d8b9c03cd / Purple banner and pole | Ordinary banner/standard tool; no aura or magical item property. Carry/display signal; no automatic Help bonus, fear save or buff. Treat staff-like improvised attack only if separately selected. | No complete banner/pole modular geometry. Fixed source shows carried standard, no no-banner variant. Request ordinary banner sprite, held/ground recipe and banner-free fixed holder. |
| gap.7e8c70e1f6af7897 / Wand | New ordinary arcane-focus wand under SRD5.1 focus rules; not charged wand or Quarterstaff. May satisfy eligible spell material focus requirements; no spell list, charges or sword/staff attack from art. Spells lane owns cast semantics. | Two short-focus consumers; original Melee19 is too long. Request short wand held/ground sheets or approved short original geometry. |
| gap.8c45e56e7e13957e / Back canister and straps | Ordinary strapped canister/container; contents unresolved, default no volatile payload. Storage only once authored capacity/contents selected; no flamethrower, blast-on-death or fire immunity. | No selected complete canister/back modular geometry; fixed back pixels cannot be removed. |
| gap.af17f53160bc0118 / Musket | Authored musket (not a claim of SRD5.1 firearm content):1d12 piercing,ammunition40/120,loading,two-handed; omit mastery Slow. Apply5.1 Loading limit; shooting/running clips do not waive ammunition/action limits. Ordinary firearm, no magic rider. | Two rifle-like source users; no compatible modular firearm selected. Need original firearm media, projectile/release/event calibration and ground media. |
| gap.c2733a274e9ddcb6 / Saddle/tack | Ordinary riding saddle on mount; do not select military saddle benefits from appearance. Tack transfer belongs to mount equipment/container; no automatic dismount-save advantage or mounted feat. | Two fixed mounted Goblins; shared rider/mount silhouette includes tack. No selected modular saddle/tack-free mounted state. |
| gap.cbf14e096242e487 / crowbar | SRD5.1 ordinary crowbar tool; optional improvised attack uses5.1 fallback1d4 with chosen bludgeoning type. Leverage-compatible Strength checks can use crowbar advantage. Improvised proficiency remains existing ordinary native rule; no Light tag copied from Club. | One worker’s hooked tool lacks matching modular media. Source no-crowbar state absent. |
| recommendation.18ec8cf1d3121b12 / Back quiver | Ordinary quiver/ammunition container,SRD5.1 capacity20 arrows; no Efficient Quiver or ranged bonuses. Arrow storage/retrieval under native inventory/ammunition; container follows UUID and contents, not creature. | Bag2 geometry exists. V2 Common Clothes/backpack placeholder is not legal current category/primary layer. Backpack render layer now exists after cloak admission; quiver still needs ordinary container attachment/storage admission. |
| recommendation.22852dc18f7bc2cd / cloak blue | Ordinary blue cloth cloak on native BodyPart.CLOAK / VisualLoadoutSlot.CLOAK; no AC/save/resistance property. Normal wearable/loot lifecycle; no hidden flight or cold resistance. | Implemented: ordinary native cloak, Bag1 geometry, backpack render layer and blue palette. No body-outfit placeholder. |
| recommendation.24e94ba86ac133ff / cloak dark | Ordinary dark cloth cloak; same base as blue cloak with alternate palette. Normal wearable lifecycle; no necrotic resistance, undead identity or invisibility. | Implemented: same ordinary cloak base and shared Bag1 source with dark palette; no duplicate mechanics. |
| recommendation.724760f143086fc2 / Longsword | Existing native Longsword in depicted left hand, paired with right Handaxe; no Light or finesse override. Can use an accepted normal attack with that sword. Implement explicit actor-owned talent permitting one-handed non-light melee weapons in offhand and existing bonus-action default and either-hand-first policy; preserve explicit reaction/composite/restricted-action costs. Do not change Longsword tags globally. | Offhand1 approximate straight silhouette exists. Non-light Longsword/offhand presentation/factory slot must be admitted explicitly; fixed hands cannot be silently swapped. |
| recommendation.801da9c994275a27 / Shortbow | Existing Shortbow carried left while Scimitar held right; source loadout remains recorded. Use existing separate melee/ranged loadouts and existing switching: blade for melee, bow for shooting. No special shooting talent required; map each actual action to its correct source sheets. | V2 panel omits left bow to avoid overlay lie. Canonical Ranged media does not recreate simultaneous carried bow plus sword; needs carry/no-sword ranged fixed/modular presentation. |
| recommendation.95d553b995244dc5 / Maul | Add SRD5.1 Maul cold definition:2d6 bludgeoning,Heavy,Two-Handed; it is an SRD rule, not a Warhammer rename. Existing generic weapon/attack pipeline can express base; no mastery,stun or giant bonus from huge head. | Melee11 Warhammer is only hammer-family approximation and undersized. No honest large rectangular maul shape selected as exact. |

Musket proposal is 1d12 piercing, 40/120 range, ammunition, loading and two-handed,
with no 5.2 mastery. The human rejected a separate firearm proficiency gate; this is
an adaptation proposal, not a claim that 5.1 already defines that source weapon.
Select armor grades from actual coverage and existing mechanical bases as part
of content authoring. Fixed-sheet removal artwork is explicitly deferred; ordinary
loot keeps its native lifecycle without invented bound/conjured fiction.

The supplement proposes a separate lower-body item at LEGS/GREAVES as an alternative
to the approved partial-body outfit. Current implementation follows the accepted
body-slot outfit with declared legs anchor and unchanged common-clothes mechanics.
Do not switch these native slots silently; approve an alternate base/slot before
character grants. The source author acknowledged this distinction.

## Organization and identity

Keep native base types and current cold definitions in
`dnd/content/items/authored_item_definitions.py`, creation transforms in
`item_composition.py`, and materialization/registration in `authored_item_builders.py`.
Put new composed named definitions in a small downstream
`dnd/content/items/derived_item_definitions.py`, importing cold bases and transforms;
the canonical builders import those entries and register their materialization.
Cold definitions never import the transforms or the derived module: transforms
already import the cold types. This preserves the import DAG and one dispatch
table; a collection of cold definitions is not another runtime registry.
Native behavior comes from the existing composers in
`dnd/items/` and blocks, with neutral property/event data in `dnd/core/`.
Definitions remain data without live UUIDs or event handlers. No second registry,
generic effect interpreter, per-weapon subclasses or renderer dependency enters
the native content layer.

For appearance-only selections, copy the frozen base definition with
`dataclasses.replace`, setting its existing `visual_item_name`/`visual_variant_id`,
and pass it through `materialize_item_definition`. A bronze handaxe with unchanged
rules keeps the handaxe item ID and mechanical values; it does not need another
weapon class or damage type. The visual ledger's `preset_id` labels are metadata,
not installed creation APIs: the built-in preset inventory is empty and
`ItemVisualVariantParameters` has no consumers. A genuinely different
enchanted item uses a named immutable definition derived from that base, explicit
native properties and registration through the same builder table. Register
required choices only; do not manufacture a Cartesian product of materials,
colors, +1/+2/+3 and damage types. Metallic color, “Holy”, “Frost” or “Poison” in
a visual catalog name grants no mechanic. Magical item identity and magical
attack provenance must be authored explicitly alongside accepted enhancement.

Public appearance data stays in the existing visual ledger,
`content_data/ledgers/neuroclient_authored_item_visuals.json`, and hand/ground/media
registrations in `game/data/`. Category-qualified variants and hand bindings are
distinct from mechanical content references. A single item can resolve different
main/off-hand media without becoming a different physical item. Received item
facts supply its identity/properties; rendering never inspects live inventory,
chooses rules from sprite filenames or overrides native equipment eligibility.

Doors, windows, props, containers, traps, levers and spell-created physical walls
keep their current environment definitions/builders/spatial profiles. They share
existing item health/destruction/location capabilities where appropriate. They
are not moved into equippable gear tables or rewritten during roster authoring.
Existing environment compatibility remains a regression gate.

## Complete gap-resolution work inside this plan

These proposals belong to this implementation, not an unowned later backlog.
Plan acceptance must settle the genuine game-rule proposals before their code is
written. Technical compatibility work does not need invented gameplay choices.
All ordinary item colors remain cosmetic, preserving the existing base mechanics.

| Requirement / exact record | Proposed resolution and implementation | Acceptance evidence |
| --- | --- | --- |
| Seven waist-only garments: recommendations `0180217b2e2a4602`, `2af518dd2cc66815`, `89678b97568fd637`, `c0f88f46f3580350`, `cfc18927c465821a`, `f07ff105e0d57f7c`, `f379e4ee6a9d3386` | Support a deliberately authored partial outfit at the existing body slot with explicit legs/belt layers and no chest. Preserve its exposed torso. Adjust the existing category presentation contract to declare supported layer alternatives and an explicit registration/primary-layer anchor; never weaken all validation or add a phantom chest just to pass it. Existing common-clothes mechanics stay unchanged. | Held and floor layers omit chest; humanoid and body-2 torso remains visible; legacy full outfits remain valid. |
| Quiver `18ec8cf1d3121b12` | Ordinary transferable accessory with back presentation. Audit existing native accessory/storage ownership first; add a supported slot only if none exists. A visible quiver does not itself add ammunition, attacks or capacity. | Equip/drop/loot with correct back layer and no combat bonus; no body-armor substitution. |
| Cloaks `22852dc18f7bc2cd`, `24e94ba86ac133ff` | Ordinary blue/dark cloaks use the existing native cloak slot. Extend the existing actor slot adapter and EquipmentRenderLayer with the rig's backpack layer; do not create another accessory subsystem or disguise a cloak as body armor. Use existing Bag1 geometry only if the annotated silhouette is accepted. | Back layer survives ownership transfer, floor binding and ordinary loss. |
| Banner/pole `gap.0492850d8b9c03cd` | Ordinary accessory/object with no aura bonus. Ask artist for reusable isolated held/floor media; author exact worn/carried disposition from source. | Valid ordinary possession and grounded rendering; no unearned ability from its color. |
| Canister/straps `gap.8c45e56e7e13957e` | Ordinary accessory until a separately accepted ability gives its contents a function. Preserve distinct container/decoration identity; request isolated media. | No automatic poison, ammunition or armor bonus; exact ownership and slot. |
| Saddle/tack `gap.c2733a274e9ddcb6` | Mount-owned ordinary gear, not a humanoid body wearable. Reuse existing mount equipment capability if present; otherwise add the smallest supported disposition/eligibility path. | Humanoid cannot equip it as armor; mount retains and releases the actual item correctly. |
| Wand/focus `gap.7e8c70e1f6af7897` | Ordinary spellcasting focus, no charges and no Quarterstaff weapon substitution. Audit current focus capability; request exact small focus hand/floor art. Its use by an innate caster is not proof of an item-granted spell. | Focus ownership/rendering with no fabricated attack or spell grant; chosen caster eligibility follows native rules. |
| Maul `95d553b995244dc5` | Add the actual SRD maul cold base with its own canonical identity and normal heavy/two-handed bludgeoning rules; select the hammer geometry with an explicit factory/presentation binding as a documented approximation rather than reuse Warhammer mechanics. Reuse normal attack/action economy. | Native base data matches the repository SRD source; two hands/attack modes and damage remain correct after loot. |
| Crowbar `gap.cbf14e096242e487` | Ordinary crowbar tool; propose existing improvised-weapon rules for attacks, with explicit proficiency treatment rather than a new martial weapon. Reuse tool interactions already supported; do not invent leverage actions. | Tool and improvised attack behavior tested through normal action route; artist confirms hooked silhouette. |
| Musket `gap.af17f53160bc0118` | Propose one explicitly authored firearm base and ammunition type matching the depicted long barrel. Use authored 1d12 piercing,40/120,ammunition,loading,two-handed,without a separate firearm proficiency gate; author ordinary weapon data plus shared ammunition/loading capability if missing. No crossbow relabeling and no silent import of SRD 5.2 rules into the 5.1 ruleset. This remains part of full-roster completion. | Normal ranged attack, ammunition consumption, loading restriction, extra attacks/Haste/Slow/Action Surge and loot retain the accepted rules. Concrete authored stats are in this plan; runtime loading/ammunition and action-budget behavior must be demonstrated, not guessed from flags. |
| Offhand longsword `724760f143086fc2` | Preserve longsword rules and current hand/feat eligibility. Implement the reviewed actor-owned talent contract above and a disclosed offhand visual binding; preserve existing bonus-action default, either-hand-first policy and explicit reaction/composite costs. | Legal equipment shows one physical sword; illegal bonus attacks remain rejected; no light-property alteration. |
| Sword plus left bow `801da9c994275a27` | Preserve melee/ranged active-set rules. Provide fixed-holder presentation states or isolated layers for the inactive equipment instead of showing the bow during a melee/unarmed attack. Do not create an attack exception for baked art. | Melee, bow and unarmed native actions each show the correct active loadout, including transition/replay. |
| Armor grades across all outfits | Compare each selected recipe against actual coverage, then approve the native base explicitly. Metal color/one pauldron does not imply plate AC. Current bases are candidates; publish the per-record selected armor base before character grants. | Item AC/max-Dex/penalties/material behavior derives from accepted definition, independent of tint and fixed sheet. |
| 51 proposed item FX components / ten source holders | Resolve the emitting possession per clip; separate sword emission from shield/body rituals. Group repeated evidence into supported item properties or cosmetic magical appearance. Prefer existing flame/coating property families where rules are actually justified; color alone adds no damage/save/duration. Complete a concrete family table before authoring native powers. | Same item UUID/effect facts drive held, floor and recipient effects; coating clock/concentration survives transfer; body/spell effects do not become loot. |
| Ordinary fixed-holder item loss | Support authored empty-equipment states or precisely separated equipment layers/masks in the existing fixed-rig presentation path. Request artist state media where needed. Fixed-sheet removal artwork is deferred by the human. Keep ordinary ownership rules; document baked art mismatch until the later final-death-frame pixel-edit lane. | Native ownership/location changes exactly once; modular holder/floor/recipient replay stays correct. Fixed-holder removal pixels explicitly deferred; no renderer-only rule ban. |

### October 2 native implementation checkpoint

Canonical psychic5/Maul definitions, actor-owned one-handed offhand receipts,
shared slot eligibility and exact attack source revalidation are implemented.
The selected longsword has main/ground palette and explicit Offhand1 binding;
111 new appearances are admitted. All authored eligible one-handed category/variant
offhand bindings reuse existing vendor sheets, with length/head/tine approximation
explicitly disclosed; they do not change mechanics. Fifteen actor-expanded native
and media checks pass, and both reviewers approve the correction. Full engine1969passed; expanded budget
suite352passed; focused checks and typing pass. Independent reviewers approve
production code and requested lifecycle/birth/cost coverage was added.

The roster author reconciled the nine historical gaps: longsword now settled;
Maul native complete/exact art absent; seven remain bounded extensions, not
cosmetic authoring alone. Musket/quiver need actual shared ammunition/Loading
semantics, focus wand needs material/held admission, banner held nonweapon
admission, canister/quiver back container eligibility/capacity, tack mount slot,
crowbar tool/leverage/selected improvised support. No firearm flags, stack-count
capacity, cloak-slot substitution or color-only effect may masquerade as these.
Exact remaining mapping and media gaps are in the implementation record.

### Implementation order and shared-file ownership

1. Pin the full intake/crosswalk and finish the possession-level effect supplement.
   Bring the exact mechanical/base/armor/effect proposals into this plan for acceptance;
   no record disappears because it needs extra work.
2. Add existing-base colors and lawful hand mappings through existing typed ledger
   and ground bindings. Label new rows as October 2 roster-derived authoring with
   the frozen hash/dedup ID; retain original July hash/date as historical provenance.
   Publish an explicit per-variant legal main/off/ranged binding matrix, including
   transfer between eligible hands and no invented equip/bonus-attack permissions.
   Complete missing original action media first. The 101 compatible selections are
   one part of this step, not a release scope reduction.
3. Implement partial garments and ordinary accessories in their existing owners,
   with explicit typed eligibility/layer alternatives and public native tests.
   Add accepted missing weapon/tool/focus bases through the one canonical builder.
4. Author accepted magical definitions through immutable transforms and shared
   item-owned properties; finish held/floor/transfer effects. Fixed-holder pixel
   removal is deferred and is not an acceptance gate for this item lane.
5. Validate the complete 165-record queue, all consumers and all effect ownership.
   Run the full engine suite at a stable combined checkpoint, affected game tests,
   typing and normal received-event in-game recordings. Then conditions/abilities
   and finally character grants can consume these finished items.

There is no new item framework, second dispatch table, per-character special item
class, palette engine or runtime dependency on the private bible. Appearance rows
are passive data; native item definitions and properties own rules. New accessory
or partial-outfit contracts receive focused reviewer checks before shared changes.
Coordinate animation loader/types, core slots/events, merged catalogs, ASSETS,
RECOVERY and private art manifest with the spells chat under the existing shared
checkout agreement. No independent git history changes or overwrite of its diff.

## Work sequence and deliverables

### 1. Complete the actual item list for every roster row

Extend the private reconciliation rather than creating another runtime inventory.
Inspect every depicted region: main/off/ranged hands, body clothing or armor,
head, gloves/bracers, feet, accessories/foci and intrinsic anatomy. Record an
explicit absence where applicable. A row without a proposed weapon still needs
its possessions checked; a broad body description is not a finished equipment set.

For every possession record: source roster key and evidence frames, physical
held hand or unresolved status, native equipment slot, proposed mechanical base,
selected category/variant/layers, original and desired palette zones, fit notes,
ownership/removal fiction, and consumers. Distinguish evidence from a proposed
gameplay choice. Do not infer main hand from list order, cloth from armor grade,
a shoulder plate from full plate, or magical properties from color.

Deduplicate by mechanical base/properties and selected appearance, preserving all
consumer rows. Each entry gets one outcome: reuse existing appearance; new palette
variant; new mechanical base using existing capability; new supported property
combination; intrinsic/ability rather than loot; or explicit decision/media gap.
No `study.item.*` identity becomes a production content ID automatically.

**Deliverable:** all-150 possession crosswalk and a deduplicated item queue with
exact reuse/new/gap counts. Unknown choices are listed, never silently approved.

### 2. Match existing art and settle missing bases

The currently requested existing groups are Battleaxe, Club, Dagger, Greataxe,
Greatsword, Handaxe, Longbow, Longsword, Mace, Quarterstaff, Scimitar, Shield,
Shortbow, Shortsword, Sickle, Spear, Trident, plus Off-hand Dagger/Handaxe/Scimitar/
Shortsword. Check all relevant existing catalog variants, including wooden shields,
armor, clothes and accessories that the incomplete region inventory omitted.

Compare the fixed source against current modular rendering on humanoid and body-2
skeleton, with actual source palette swaps. Approve silhouette compromises per
family/entry; exact pixel matching is not required. Preserve grip, cloth and metal
zones separately where the source allows it; do not recolor the whole sprite by
multiplication. Test the required idle, attack, damage, death and held-state
directions, not just one contact-sheet pose. Reuse the two accepted off-hand
geometries for six supported families when the fit is plausible.

| Missing/ambiguous source | Treatment before authoring |
| --- | --- |
| Enemy `1Hammer`: large two-handed hammer | Add Maul only after accepting its mechanical base; compare existing hammer geometry at reviewed registration, not a silent Warhammer substitution |
| Enemy `2Shooter` and `7Sniper`: firearm-like barrels | Use authored musket stats and no separate firearm proficiency gate; verify loading/ammunition support rather than relabel a crossbow or claim SRD conversion |
| Top `Zombie Worker 01`: red hooked tool | Confirm crowbar/improvised attack choice and proficiency; existing tool silhouette may be reused if accepted |
| Demon spawn 1 / Spawn 11: short wand/focus | Decide ordinary focus versus innate/conjured object; a glowing tip does not create a charged wand or Quarterstaff attack |
| Demon Spawn 13: proposed off-hand Longsword | Native eligibility and missing off-hand appearance are separate; do not make a non-light weapon light to fit an animation |
| Demon Elite 3: dark blade-like form | Inspect motion to settle held weapon versus anatomical attack |
| Demon Beasts 1–5 / Imp 5: forearm blades or claws | Use justified intrinsic/native attack data; no ordinary droppable teeth/claw loot |
| Enemy `5Bruiser` / `8Brawler`: fists/gauntlets | Decide wearable gear separately from trained/natural unarmed attack behavior |
| Armor grades, boots/headwear/accessories on all 150 | Finish independent region review; visual metal alone does not assign AC or new wearable bonuses |

THROWN/VERSATILE/ammunition/loading flags must be checked against actual current
action discovery and resolution before promising those modes. A content flag is
not proof of implemented mechanics. Any missing rule is a separately listed
decision and bounded follow-up, not an incidental expansion of a color variant.

**Deliverable:** selected modular appearances with annotated compromises and the
remaining human choices. Only entries whose rules and fit are settled proceed.
All 150 remain accounted for; unresolved entries prevent a full-port completion
claim, rather than being dropped from the roster.

### 3. Author approved bases and variants

Appearance-only entries select existing category-qualified variants or append
deliberate new palette/geometry bindings in the current ledger. Copy the frozen
base's visual fields and use the existing materializer; preserve mechanical IDs
and values. Historical visual preset labels are not a second dispatch route.
Mechanical entries use `named_item`, `with_weapon_bonus`, `with_extra_damage`,
`with_wearer_bonus` and other currently supported transforms over cold bases.
Keep replacement/duplicate semantics from the accepted implementation; use one
shared native composer for a genuinely new approved property family, never a
special handler for every item using it. Do not add new property kinds speculatively.

Record item magic, bonus, damage packets, wearable effects, intrinsic status and
removal policy explicitly. Native eligibility still controls heavy/two-handed/
off-hand/shield interactions, normal attacks, opportunity attacks and action
economy. Palette variants must preserve all unchanged mechanical values.

**Deliverable:** canonical approved content entries and appearance selections,
with each deduplicated queue record pointing to the exact resulting reference.

The later character lane must carry these appearance selections through the
existing possession grant path before initial item installation/birth. Today
`CreaturePossessionGrant` contains only item ID, disposition and equipment slot;
`build_authored_item` takes only item ID, source UUID and quantity. Neither selects
a per-grant appearance variant. That bounded integration remains explicit: extend
the existing passive grant with a validated category-qualified selection and
materialize the copied cold base through the same native owner, retaining the
selection in existing item snapshots and any durable construction recipe. Reject
incompatible base/category selections. Do not introduce a second grant catalog,
assume unused recipe parameters work, mutate visuals after birth, or create 150
mechanical IDs merely to bypass this missing selection path. This plan authors
and validates the gear selections; the character lane integrates their grants.

### 4. Account for every VFX and fixed-holder loss

Use the completed 355-component V2 matrix and possession-level supplement against all 1,034 selected clips.
Classify each effect as item enchantment/coating, creature ability/condition,
spell, intrinsic anatomy or cosmetic, with evidence and an explicit gameplay
justification where it has rules. Record trigger, lifetime, native provider and
required preparation/contact/release/removal markers. Decorative baked emissions
do not automatically become passive damage riders or a second active effect.

For item-owned effects, specify what remains on a dropped item and what the
receiving humanoid/body-2 rig draws in each relevant action. Reuse the current
item-owned effect lifecycle, disclosed phase facts and exact UUID. Static damage
bonuses remain on-hit behavior unless a separate visible ongoing effect is
accepted. Creature/spell cosmetics do not move with loot. Item tint alone cannot
certify an animated effect transfer; missing effect media/anchors stay explicit.
Independent FX/shadow sheets are preferred; avoid showing both baked and modular
copies of the same effect.

The 478 depicted records include multi-layer outfit descriptions, not proof of
478 individually lootable items. For each outfit explicitly author a single
clothing set or separate native possessions; do not infer indivisible armor/loot
from a grouped presentation recipe, or duplicate the same gear across regions.

For every baked possession settle its actual fiction: ordinary transferable
gear, justified innate/bound/conjured equipment, or accepted loss-on-death behavior.
Missing modular art is not itself a gameplay prohibition. Native item transfers still work normally. The human explicitly defers fixed
holder removal pixels, including final dead-frame cleanup; record the baked
appearance mismatch rather than block ordinary loot or invent loss fiction.
No renderer-only disarm ban, instant re-equip or silently destroyed loot.
Actual creature/spell abilities and their derived conditions are authored in the
following lane; this step records their requirements without creating duplicate
item mechanics.

**Deliverable:** a complete ownership/transfer matrix and a per-item fixed-holder
loss-art limitation record. Deferred fixed-holder pixels do not block native
item admission; incomplete item-effect transfer remains an honest visual limitation.

### 5. Finish held/floor bindings and reproducible media

Extend existing `item_appearances.json` only for approved new entries. Bind the
same disclosed item to main/off/ranged hands, apparel layers and ground sampling,
with category-qualified variants. Ground drawing preserves palette/coating,
alpha, separate shadow, camera row, support pivot and 64-pixel source-tile
registration. Drop remains at the actor's valid own/adjacent selected tile; pickup
removes the exact item, not a neighboring pile entry. A hidden recipient must not
leak through an item's release or appearance.

Use the selected original equipment-only sheets. Reuse sheets for recolors;
neither duplicated painted sprites nor loose frame exports are necessary.
Import genuinely missing originals through the existing explicit importer and
private production manifest, respecting [ASSETS.md](../ASSETS.md). Preserve the
full archive. Keep authored action clocks and shadows. Do not apply spell 32-FPS
resampling automatically to actor rig animations. Consumable ground artwork and
unsupported geometry remain named media gaps until actual assets are selected.

**Deliverable:** public passive bindings plus private reproducible media receipts;
no native imports of renderer tables, binary art commits or runtime file scans.

### 6. Verify the content through real behavior and recordings

Follow [HOW_TO_TEST.MD](../HOW_TO_TEST.MD). Validate the complete queue/reference
coverage as authoring data, and test actual gameplay through public native
composition, actions, projections and replay. Do not add one private-method test
per recolor. Parameterize authored data; use representative meaningful mechanical
and rendering paths, plus exhaustive coverage validation for admitted bindings.

Required observations: unchanged ordinary variant attack/AC values; deliberate
enchanted damage and scoped wearer bonuses; legal main/off/ranged/unarmed sets;
intrinsic removal rejection; ordinary accepted drop/pickup/equip/transfer preserving
exact item/property identity and expiry; hidden recipient privacy; original-holder
loss policy; correct palette zones, shadows, floor size and both modular bodies.
Exercise every admitted visual selection in its required directions/actions.
Existing extra attacks, Haste/Slow/Action Surge, off-hand/opportunity attacks,
object damage/destruction and containers continue to use their existing routes.

Run the complete engine suite after authoring, affected game/architecture checks,
scoped typing and a final stable-code full game suite. Preserve failure receipts;
the prerequisites' 1,955 engine passes and classified renderer failures are a
baseline, not evidence that this future batch or final full renderer suite passes.
Document and discuss unrelated backend failures with the human; do not change
expectations merely to erase them. Verify authoring ownership/reference counts
for intentional new entries without regenerating unrelated frozen evidence.

Review uses the established native-event gallery, real paving floor, all four
cameras and saved received inputs. Show complete readable equip/attack/drop/
pickup/transfer/removal sequences, including main/off and humanoid/body-2, with
coating/enchantment visible where justified. No one-second checkpoint videos,
ad-hoc replacement UI, manufactured art or reveal of a live authoritative holder.
Produce focused representative clips and a searchable exact all-entry manifest;
do not bury the review in 150 duplicate demonstrations.

**Completion:** every roster row and depicted region accounted for; every approved
deduplicated item mapped to canonical native and presentation data; every effect
owned or explicitly non-item; meaningful checks and reviewed in-game sequences
pass. A report with unresolved choices is valid progress, not a claim that the
entire roster is production-ready. The next lane then authors conditions/abilities,
followed by characters and their complete action/animation mappings.

## Independent review

The original pre-V2 plan received these reviews on October 2; they do not certify the full V2 additions below:

- `/root/renderer_failure_audit` — anti-slop: scope, evidence limits, no invented
  mechanics/fiction, existing bible assignment, actual matching dependency and
  meaningful received-event review/validation; no remaining blockers.
- `/root/item_color_ecs_review` — ECS/anti-OOP: sole canonical dispatch, downstream
  definition import DAG, real definition/materializer APIs, explicit later grant
  selection gap, exact item ownership and subjective replay; no remaining blockers.

Corrections from review: consume the existing bible assignment rather than repeat
the study; do not mistake historical visual preset IDs for installed APIs;
keep composed definitions downstream of cold types/transforms to avoid a cycle.
Current counts and pinned handoff SHA were independently checked. No production
code/art changes or gameplay test run were made for this plan-only update.

### Full V2 review

`/root/item_admission_antislop` approves full structural planning coverage:
verified 165/165 exact records and consumers, all 51 initial item-FX candidates,
all 12 producer decision records and seven partial garments. Corrections applied:
no false claim of an SRD firearm conversion; explicit lawful cross-hand matrix.
This is not final approval to implement unsettled firearm/armor/effect/loss rules.
Reconcile the ownership supplement over all 355 components: corrected body/shield
assignments may change the initial 51 proposed item-owned count.

`/root/item_admission_ecs` approves full V2 ECS/data-owner design and independently
checks all 165 dedup IDs. Corrections made concrete: explicit new maul factory/art
binding; reuse native cloak slot with the missing existing adapter/backpack layer;
partial garments retain declared registration anchors; lawful cross-hand transfers.
One canonical builder/materializer, downstream transform DAG and received item
UUID/effect facts remain the owners. No extra accessory subsystem or rule inference.
Both reviews approve complete scope/design, not unresolved numerical gameplay or
item-loss fiction. These stay inside step 1's full acceptance tables, not outside
the plan. No production code/art or gameplay tests changed during this update.

## Human correction — simplify remaining gear, October 2

The human explicitly removed ammunition/focus/tool submechanics as blockers.
Finish ordinary item content through existing native equipment and attack paths;
do not introduce material-component checks, reload/ammunition consumption,
container contents, mount rules or generic tool advantage in this lane.

- Wand, crowbar and carried banner use the existing melee weapon slot and ordinary
  one-handed1d4 bludgeoning fallback; banner occupies both melee hands. No charged
  spells, focus eligibility or universal check bonus is implied.
- Musket uses the existing ranged weapon path,1d12 piercing40/120,two-handed,
  with no separate firearm proficiency. Ammunition/Loading enforcement is deferred
  explicitly rather than advertised as implemented.
- Add native BodyPart.BACKPACK, an equipment.backpack field and the corresponding
  VisualLoadoutSlot mapping. Quiver/canister are ordinary zero-AC accessories in
  that slot; one replaces the other through normal displacement/events. Their
  contents stay ordinary actor inventory; no container capacity promise.
- Saddle/tack is an ordinary inventory possession for now, without invented
  mount movement/equipment benefits.
- Preserve native loot/drop/equip/cost/ownership publication. Separate cloak and
  backpack slots can coexist. Shared vendor backpack layer overlap must have an
  explicit appearance outcome; no silent last-layer overwrite.
- Admit available honest approximate vendor geometry through passive authored
  recipes, palette replacement, full action banks and ground bindings. Missing
  exact shapes remain disclosed; do not block native item definitions on future art.
- Validate initial disclosure, backpack displacement/veto/transfer, unchanged AC,
  held/ranged eligibility and received renderer state, then full engine tests.

Anti-slop and ECS reviewers review this bounded amendment and implementation.
This supersedes earlier statements that specialist focus/tool/ammo systems must
be added before these possessions can be authored.

## Final item-rule implementation — October 2

Human's renewed instruction is to finish item rules, without animation work. Use
the existing proposed values: two composed magical Ember definitions (Longsword
and Greatsword) with1d6 FIRE and no automatic enhancement bonus. Keep each exact
possession appearance; both ember longswords share mechanics, not appearance.

Basic Poison uses the existing usable coat action/item-owned condition lifecycle:
one action application, ten encounter rounds, DC10 Constitution on an accepted
weapon hit,1d4 POISON only on failed save, no Poisoned condition. A condition-owned
DAMAGE_ROLL_RESULT handler checks the parent attack's exact source_item_uuid.
It follows the physical weapon through transfer and is released through existing
condition cleanup; it does not install an actor-name or slot-specific bonus.
Use the current poison-tagged, nonmagical saving-throw context; poison dice are
not doubled by a weapon critical. Existing fire/lightning coating behavior stays
unchanged. No renderer or animation changes are in this slice.

Public tests exercise cost, hit/save/miss, unrelated weapon exclusion, transfer,
expiry and cleanup. Then run the complete engine suite and update the canonical
per-possession handoff. Anti-slop and ECS reviewers validate this bounded route.

Final item-only acceptance: all165 records /478 possessions mapped; all51 native
references construct. Focused50checks and complete engine1,990checks pass; native
and handoff typing is clean. Both independent anti-slop and ECS implementation
reviewers approve. Final authoring selection receipt:
`.runtime/items-roster-20261002/complete-item-rules-handoff.json`.

## Human correction — item material effects only

Existing modular silhouettes are final for this lane. No replacement art, altered
geometry, new weapon/effect sheets, or isolated source-FX extraction is authorized.
Replace the prior exact-art/isolated-FX TODO with data-driven palette and bounded
bloom on existing item pixels. Cover native additional FIRE/PSYCHIC damage facts
and existing fire/lightning/Basic Poison coating identities. Selection consumes
received item effect facts, not names, character IDs, art colors or live registries.
Use the same existing item_material function for both held hands and ground.
Retain registration, source alpha and shadows; bloom is bounded to matched item
material pixels, so it cannot introduce geometry or wall-crossing halos. Ordinary
items and unknown effects remain unchanged. Basic Poison removal/expiry removes
the treatment through existing effect state; intrinsic properties persist through
transfer. Static material glow does not claim an animated flame or spell effect.
Validate real original frames, both hands, floor/recipient replay, expiry and
property isolation. Independent anti-slop and ECS reviewers review this amendment
and actual implementation. No shared condition-rendering files need edits.

Material-only amendment implemented and double reviewed:37renderer/replay checks
and six paired engine clips pass; typing0. Existing silhouettes and palette swaps
are accepted; no remaining exact-weapon/new-FX-art tasks in this lane. Static
interior glow is the implemented treatment, not animated flames.
