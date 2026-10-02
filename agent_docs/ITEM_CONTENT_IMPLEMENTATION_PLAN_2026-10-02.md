# Item content for the complete fixed-art roster

October 2, 2026. Scope: the missing gear and deliberate appearance/mechanical
variants needed by all 150 retained characters. This is the next content lane
after the [implemented prerequisites](ITEMS_PREREQUISITES_IMPLEMENTATION_2026-10-02.md),
not another item-framework rewrite. Conditions/abilities, characters and their
animation port follow, in that order; scenario redesign and multi-Z stay deferred.
The [full-roster port plan](FIXED_ASSETS_AND_SCENARIOS_PLAN_2026-10-02.md) remains
the parent plan. This document replaces its pending item-prerequisite assumptions.

Status: independently approved by anti-slop and ECS/anti-OOP reviewers.
Actual matches remain a dependency being completed by the original bible thread;
review approval does not approve unresolved gameplay choices or begin implementation.
No new item, rule, rig or artwork is installed by this update.

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

Private intake:
`.runtime/pack-study-20260930/integration-preparation/item-first-reconciliation/handoff.json`,
SHA-256 `e0e72d51601ec1f237db5b02d74661edadf45c0d4cbce1347241949d509303d8`.
The illustrated source is `artist-review-20261002/bible.html` beside that intake.

The handoff covers 150 roster rows across eight packs, but identifies only 134
proposed weapon/shield/focus/anatomy records on 96 rows: 119 have candidate base
references and 15 do not. **Zero exact visual candidates are selected.** Its 900
body-region checks still contain unresolved clothing/accessory/anatomy choices;
its 93 VFX observations across 63 characters all have unresolved ownership.
Those observations were selected from clip descriptions; they are not proof that
other clips contain no effects. The 32 grouped requirements are 21 existing
categories and 11 missing/ambiguous labels, not 32 new mechanical item types.

Historical handoff `production_bound=false` flags predate the imports and must be
rechecked against current registration. Earlier multiplication-based contact
sheets cannot approve colors under the corrected palette-swap path. The old
110-item cold study is a subset, not the complete current builder inventory.

The original bible authoring thread, `01a0f3b4-277a-7fa0-9356-d1c9de5527b8`
(“Art-led NPC roster and rig authoring”), has been asked to finish the previously
requested actual match analysis, using current palette swaps and full region/VFX
coverage. Its last saved turn completed the candidate inventory, not those
selections. Consume its versioned completed results for steps 1–2; do not recreate
the study in parallel. Genuine unresolved gameplay/fiction choices come back to
the human with concrete illustrated recommendations.

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
| Enemy `2Shooter` and `7Sniper`: firearm-like barrels | Firearm rules remain a human decision; do not turn them into crossbows or label SRD 5.2 proposals as implemented 5.1 content |
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

Expand/confirm the existing 93-record VFX matrix against the full selected clips.
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

For every baked possession settle its actual fiction: ordinary transferable
gear, justified innate/bound/conjured equipment, or accepted loss-on-death behavior.
Missing modular art is not itself a gameplay prohibition. An ordinary removable
item also needs an honest representation of the fixed holder after loss; request
a state/agree a representation rather than leaving the weapon baked in unnoticed.
No renderer-only disarm ban, instant re-equip or silently destroyed loot.
Actual creature/spell abilities and their derived conditions are authored in the
following lane; this step records their requirements without creating duplicate
item mechanics.

**Deliverable:** a complete ownership/transfer matrix and a per-item fixed-holder
loss decision. Entries requiring unresolved fiction or effects are not visually
certified yet.

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

Both reviewers approved this corrected plan on October 2:

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
