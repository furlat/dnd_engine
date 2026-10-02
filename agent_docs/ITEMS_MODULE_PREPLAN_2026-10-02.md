# Items module prerequisites

October 2, 2026. Scope: native item authoring/composition, equipment appearance,
world objects, loot transfer and event-driven presentation. The human approved
implementation of these prerequisites on October 2. See the
[implementation record](ITEMS_PREREQUISITES_IMPLEMENTATION_2026-10-02.md).
The next content lane is the [updated item content plan](ITEM_CONTENT_IMPLEMENTATION_PLAN_2026-10-02.md).
The all-150 artist handoff contains candidates; exact gear/palette/VFX ownership
choices remain pending. Findings below describe the study baseline, not current
implementation or unfinished prerequisite work.

## Evidence and current ownership

- `dnd/content/items/authored_item_builders.py` owns the canonical direct builder
  table. Cold weapon/wearable definitions are separate from behavioral builders.
- `dnd/blocks/base_item.py` already supports inventory, equipment, floor placement,
  optional health, conditions, physical support and destruction/remnants.
- `dnd/items/environment.py`, environment builders and spatial profiles supply
  fixed-object collision/material behavior. Spell wall constructions use ordinary
  section items where physical, with spell ownership in spatial conditions.
- `content_data/ledgers/neuroclient_authored_item_visuals.json` owns presentation
  provenance. Its factory/preset labels are historical visual joins, not another
  installed native recipe registry.
- `game/player_projection.py` and reduction retain subjective item/location facts;
  `game/animation_data.py` binds equipped layers. Rendering must never query live
  inventories to reconstruct a historical frame.

Private visual evidence: `.runtime/item-hand-audit-20261002/index.html` and
`mapping.json`. There are **39 weapon/shield categories and 129 base/named
presentations**, including the unsupported Rusty Blade comparison. Seventeen
contact pages and the six-family paired sheet were visually inspected. Each shows
raw/tinted Idle in S/NW and a tinted Attack1 composite in those directions.
Nearest-pixel inspection zoom is at most 4x, not gameplay scale. These samples
do not certify every animation/direction/body. The generator reads original vendor
pixels without installing or modifying them; binding existence is not pixel acceptance.

## Main/off-hand findings

| Native family | Main-hand source | Existing off-hand source | Observed compromise |
| --- | --- | --- | --- |
| Dagger | Melee1 | Offhand2 | Different short-blade shape |
| Shortsword | Melee3 | Offhand1 | Existing straight-blade substitution |
| Scimitar | Melee4; curved variant Melee7 | Offhand1 | Off-hand remains straight, despite curved main-hand |
| Handaxe | Melee15; variants Melee17/18 | Offhand2 | Short blade substitutes for axe head |
| Club | Melee10, wooden tint | Offhand2, wooden tint | Main hammer and off-hand short blade approximate bludgeons |
| Sickle | Melee13 | Offhand2 | Short blade lacks main-hand hooked silhouette |

The vendor archive contains only two Offhand weapon categories. Recoloring/reused
geometry is a valid candidate compromise; record it rather than demand exact new
art for every native family. It does not alter weapon mechanics. The current
paired contacts reveal where color cannot reproduce a distinct axe/sickle head.
Gold variants also differ by hand (`CCAA44` vs `D8B808` in dagger/shortsword rows).
Keep those existing choices as evidence; decide whether matching appearance needs
a shared palette or a hand-specific override. Do not silently recolor everything.

Main/off-hand variant IDs belong to separate namespaces. Copying a main-hand ID
into its off-hand category fails; Assassin's Dagger in MELEE_OFF is a reproduced
resolver failure. Several extra main-hand geometries have no authored off-hand
counterpart. The contacts also expose existing crossbow categories reusing bow
sources; this is an explicit approximation to review, not proof of crossbow art.
Fixed sheets bypass equipment layers: dropping their native sword does not remove
baked pixels. Receiving modular gear and the original holder after loss both need
accepted representations. Native binding/conjuration/anatomy restrictions require
actual item fiction, never an automatic restriction caused by missing pixels.

## Ground loot findings

PickUp and Drop actions exist in `dnd/actions.py`; pickup uses physical hand
contact and pickability/capacity validation. They currently have no authored actor
gesture. Pickup participates in native object action discovery; Drop is available
through explicit execution but needs the ordinary inventory action affordance.

Floor placement/location events preserve identity and visual category/variant.
The draw paths in `game/app.py` select registered environment/legacy/device art;
ordinary dropped weapons, wearables and consumables have no general ground binding.
Native snapshots contain stack quantity and pickability, but subjective FloorItem
does not retain those fields. Keyboard selection and tile fallback exist; several
items sharing a cell require unambiguous selection.

Weapon-only sheets are feasible ground-art candidates. A held sprite is not
automatically a grounded pose. Author an explicit sampled frame, alpha crop,
camera mapping, scale, optional small rotation, floor contact/pivot and shadow
binding; review it on the existing real paving floor. Do not infer 3D geometry
from alpha or stretch equipment across tiles. Missing floor art stays explicit.
This review did not find dedicated ground/item/icon PNGs in the modular archive.

Two native transfer boundaries also need repair:

- `Inventory._detach_item_from_previous_location` ignores a rejected map removal;
  `Entity.loot_item` changes source ownership before admission and ignores another
  removal result. An item can remain spatially placed after inventory insertion.
- `Entity.drop_item` removes inventory membership and clears ownership before
  floor placement is accepted. Canceled placement can leave the item detached.

These are code-path findings, not newly executed veto regressions. The repair must
use the existing spatial preparation/admission contract and publish accepted
post-commit facts once. PickUp must propagate transfer failure rather than report
success. Include inventory transfers, equipment displacement and container spills
where the same membership changes occur; do not invent a separate loot system.

## Target module organization

Retain one item identity/lifecycle authority. Equipment versus environment is a
capability distinction, not two incompatible object universes. Pickability,
equipment slots, use actions, damageability, physical support and world blocking
compose independently: a small movable prop can be damageable without equippable;
a fixed wall can be damageable without pickable; equipment can become a floor item.

Use the existing module boundaries:

| Owner | Responsibility |
| --- | --- |
| `dnd/core/item_types.py` and neutral contracts | Typed identities, ownership/state and event snapshots |
| `dnd/content/items/` | Cold bases, stable derived recipes and family authoring |
| `dnd/items/` and existing native composers | Applying accepted item capabilities/properties |
| Existing inventory/equipment/spatial systems | Admission, membership, actions, physical effects |
| Existing spell conditions | Spell lifetime, concentration and wall/field ownership |
| `game/data/` and typed presentation schemas | Hand/body/action/ground media and effect bindings |
| Projection/reduction and shared rendering | Received facts, sampling, selection and drawing |

Do not move all files merely to achieve a directory named items. Write and verify
the dependency DAG first. Native contracts must not import rendering or high-level
content builders; recipes use typed native composers. No per-item subclass growth,
ID-switch expansion, arbitrary dictionary patches, late imports or generic effect
interpreter. Existing family-specific composition remains appropriate.

## Proposed work order and acceptance gates

### Creation-time composition clarification

The user's proposed solution to duplicated per-item scripts is functional content
authoring: start with an existing immutable definition and apply reusable functions
that return a new definition. This concerns item creation, not enchanting a live
weapon. The proposal is the following shape; function names are illustrative:

```python
definition = with_weapon_bonus(longsword, bonus=1)
definition = with_extra_damage(definition, dice="1d6", damage_type=FIRE)
definition = named_item(definition, item_id="weapon.flame_longsword", name="Flame Longsword")
```

One implementation of `with_weapon_bonus` handles the supported bonus values for
compatible weapons. One extra-damage function authors the corresponding typed
property. Several named items can reuse those functions in short content entries;
they do not each need a factory function, custom class or copied runtime handler.
Register only deliberately authored items, not every possible combination.

Composition produces ordinary immutable definition data consumed by the existing
canonical builder. Intermediate definitions have no physical UUID, owner, map
placement or live event subscriptions. The final authored ID identifies the content;
materializing a physical copy creates its native identity and contributions. Base
provenance may remain data, but creation functions do not require another registry
or a runtime recipe-language interpreter.

Simple properties can set existing typed fields. Conditional properties require
one shared native behavior implementation for that property, then parameters in
the definition; wrapping per-item scripts in functions would not solve duplication.
Existing dagger/staff/crown/armor behavior must retain its native outcomes.

Recommend an explicit final-value contract for `with_weapon_bonus`: applying +2
after +1 sets that authored enhancement to +2, rather than accidentally adding to +3.
Distinct additional damage properties need explicit coexistence/duplicate rules.
These function contracts were accepted and implemented; the implementation record
contains their exact public API.
Authoring validation rejects incompatible bases/properties and duplicate content IDs.
Appearance and VFX bindings remain independently authored over the resulting item.

1. **Finish evidence.** Receive all-150 deduplicated gear/material/color data and
   classify every VFX as item property/coating, creature ability, condition/spell,
   anatomy or cosmetic. Separate observed facts, proposed mechanics and decisions.
   Link existing native IDs and exact main/off/ground media candidates. Keep
   missing geometry, missing bindings and missing mechanics distinct.
2. **Secure native transfers.** Prepare removal/placement and capacity/stack
   admission before changing memberships/owners. Respect vetoes without partial
   state or success facts. Preserve exact UUID/effects on nonmerged transfers and
   publish surviving stack identities/counts on merges. State-bearing items must
   not merge merely because stack_id matches; validate an explicit compatibility
   policy for recipes and live effects. Preserve original concentration sustainers.
3. **Add functional item-definition composition.** Keep DIRECT_ITEM_BUILDERS as
   the sole canonical dispatch authority. Reusable creation functions return typed
   immutable definitions; deliberate named variants get stable namespaced IDs and
   use the same native materializer. Validate compatibility, stacking and inherited
   slots/quantity/ownership, physical placement/capabilities and lifetime unless an
   override is explicitly accepted. Every contribution retains exact provider/item
   identity and its removal handles; explicit stacking rules prevent one property
   from removing another's contribution. Compose existing bonus/additional damage/wearer/conditional
   effect families first, migrating dagger/staff/crown/armor behavior unchanged.
   Colors and material appearance grant no rules by themselves. Native magical
   identity and magical attack provenance remain distinct. Reuse charges/coatings.
4. **Complete appearance contracts.** A stable item appearance resolves explicit
   hand/body/action bindings, retained tint and any accepted geometry substitution.
   Author legal hand transitions without copying vendor variant IDs. Include modular
   humanoid/body2 and fixed-holder loss behavior. Preserve layering, pivot and separate
   shadows where available. No implicit wrong-category/palette fallback.
5. **Add ground presentation through the same item identity.** Author reviewed
   equipment-only frame reuse or existing prop media as ground bindings. Retain only
   disclosed quantity/pickability/effect facts needed by presentation. Give multiple
   floor items distinct pick regions/target choice; expose Drop through existing
   affordances. Ground appearance does not invent collision or removal rules.
6. **Connect owned VFX.** Item-owned effects follow item UUID and native lifecycle
   through transfer, equipment changes, destruction and expiry. Use existing attack/
   condition events and source attribution; add typed attachment/phase facts only
   where required. On-hit effects cannot become passive glows accidentally. Creature
   cosmetics do not follow loot. Show item enchantment on a receiving modular holder;
   a tint/Flaming label cannot invent a damage rider.
7. **Validate environment compatibility.** Exercise equipment, loose props, containers,
   doors/windows and construction wall sections through the common native contract.
   Preserve footprints, light/vision/attack channels, support, destruction/remnants,
   container spills and spell-owned wall cleanup. Floor loot must not accidentally
   inherit standing-object obstruction. No new wall rules or rendering rewrite.
8. **Verify before roster expansion.** Public cases: pickup/drop veto and execution
   result; full/partial stack merge and effect incompatibility; inventory capacity;
   legal off-hand/swap/unarmed and fixed-holder loss; item property transfer/expiry;
   container spill; destroyed physical wall vs retired spell owner; disclosed ground
   stacks, selection and independent event replay. Review representative real game
   clips on accepted paving, in all camera corners, then run the full engine suite
   and affected replay/architecture suites. Document unrelated failures for human
   discussion, never alter expected results to hide them.

## Review status

Anti-slop and ECS/anti-OOP reviewers approve the expanded written pre-plan and
have separately approved the creation-time functional composition amendment.
The anti-slop review's explicit canonical-dispatch, exact-contribution ownership
and inherited physical/lifetime contract clarifications are incorporated in step 3.
The human approved implementation, and both independent reviewers subsequently
approved the corrected prerequisites diff. This is not the complete roster
implementation or an assertion that all media is available.
