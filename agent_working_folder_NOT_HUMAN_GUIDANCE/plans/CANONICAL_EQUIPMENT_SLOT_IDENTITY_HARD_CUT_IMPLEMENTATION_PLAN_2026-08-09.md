# Canonical Equipment Slot Identity Hard-Cut Implementation Plan

**Status:** DRAFT — INDEPENDENT PLAN REVIEW REQUIRED  
**Date:** 2026-08-09  
**Scope:** one bounded backend + generated SDK + NeuroClient identity migration  
**Implementation authorization:** not granted by this document

## 1. Objective

Make the engine's existing equipment-slot values the only equipment-slot
identity used by mechanics, persistence, HTTP contracts, subjective player
projection, generated SDKs, and NeuroClient.

The completed unit has no `VisualLoadoutSlot`, no `PresentationWeaponSlot`, no
server-owned lower-case slot mapping, no untyped equipment/weapon-slot fact,
and no hand-written frontend slot union. An equipped item or selected attack
weapon has the same engine enum value everywhere from the `Equipment` aggregate
to equipment UI, action discovery, combat logs, presentation cues, and actor
loadout.

This is a symbolic contract cleanup. It does **not** choose images, move images
into the backend, change sprite or portrait ownership, invent asset paths, or
redesign the renderer. Existing presentation records keep their sprite keys,
render layers, and tints. Their `equipment_slot` discriminator becomes the
canonical engine slot, so safe presentation references are deliberately
reissued from the version-2 hashes described in §6.1.

## 2. Current defect

The current engine already owns three meaningful enum families in
`dnd/core/equipment_types.py`:

- `WeaponSlot`: the four melee/ranged main/off positions;
- `BodyPart`: wearable body categories;
- `RingSlot`: the two concrete ring positions.

Persistent-character `CharacterEquipOperation.target_slot` already exposes the
engine union. In parallel, the live equipment overview and mutation routes use
lower-case strings such as `weapon_melee_main` and `body_armor`.
`VisualLoadoutSlot` copied those strings into a second enum, and NeuroClient
copied them again into `SLOT_NAMES`/`SlotName` and validation helpers.

This produces five avoidable defects:

1. the same storage position has different values depending on the route;
2. `APIEquipmentSlot.slot` and several mutation fields are merely `str`, so the
   generated SDK cannot close the domain;
3. backend projection and routes interpret slot identity through independent
   string maps;
4. `BodyPart.RING` is an item category but is currently admitted by the broad
   `EquipmentSlot = WeaponSlot | BodyPart | RingSlot` type even though a ring
   must be placed in `RingSlot.LEFT` or `RingSlot.RIGHT`;
5. `PresentationWeaponSlot` repeats `WeaponSlot` exactly, while action
   discovery, AI affordances/capabilities, and attack combat-log data degrade
   the same value back to `str` before sending it to SDK/Studio consumers.

The abandoned branch's two conversion helpers would centralize a mapping but
would preserve both identities forever. They are useful evidence, not the
target design.

## 3. Canonical domain model

`dnd/core/equipment_types.py` remains the dependency-neutral authority.

Keep the existing enum classes and values. Do not rename their serialized
values in this unit:

```python
class WeaponSlot(str, Enum):
    MELEE_MAIN = "MELEE_MAIN"
    MELEE_OFF = "MELEE_OFF"
    RANGED_MAIN = "RANGED_MAIN"
    RANGED_OFF = "RANGED_OFF"

class BodyPart(str, Enum):
    HEAD = "Head"
    BODY = "Body"
    HANDS = "Hands"
    LEGS = "Legs"
    FEET = "Feet"
    AMULET = "Amulet"
    RING = "Ring"
    CLOAK = "Cloak"

class RingSlot(str, Enum):
    LEFT = "Left Ring"
    RIGHT = "Right Ring"
```

Express the selectable non-ring body positions as a type-only subset. This is
not a fourth enum and creates no new serialized identity:

```python
ConcreteBodySlot: TypeAlias = Literal[
    BodyPart.HEAD,
    BodyPart.BODY,
    BodyPart.HANDS,
    BodyPart.LEGS,
    BodyPart.FEET,
    BodyPart.AMULET,
    BodyPart.CLOAK,
]

EquipmentSlot: TypeAlias = Union[
    WeaponSlot,
    ConcreteBodySlot,
    RingSlot,
]
```

Pydantic must accept each of the thirteen concrete enum values and reject
`"Ring"`. `BodyPart.RING` remains valid only as an item/body category used by
the `Ring` content class; it is never a storage position or command target.

Before narrowing the durable type, run a read-only audit over every configured
character repository and every `CharacterItemV1` revision, not merely current
heads. A digest-valid historical `equipped_slot="Ring"` cannot be assigned
left or right automatically. The checked local `.runtime/game-directory.sqlite3`
contained six holdings revisions and zero abstract-ring rows on 2026-08-09,
but the implementation gate must repeat the audit at its own cutoff. If any
abstract-ring row exists, stop this unit and obtain a separately reviewed,
versioned migration decision; never rewrite authenticated history or guess a
side. With a zero-row proof, all valid durable bytes and item/holdings digests
remain unchanged because the thirteen accepted enum values are unchanged.

Add one immutable `EQUIPMENT_SLOT_ORDER: tuple[EquipmentSlot, ...]` containing
the thirteen concrete positions. It owns deterministic engine/API ordering,
not a second identity. Do not add wire-name conversion tables or aliases.

Delete `VisualLoadoutSlot` after all consumers have migrated.

## 4. Engine ownership changes

### 4.1 Typed equipped state

Change `BaseItem.equipped_slot` from `str | None` to
`EquipmentSlot | None`. `EquippableItem.equip()` stores the enum member itself,
not `slot.value`. Unequip, inventory transfer, drop, and destruction continue
to clear it to `None`.

Remove worker/settlement code that reparses this engine-owned field from a
string. Persistent holdings already use `EquipmentSlot`; materialization and
terminal settlement must round-trip the same enum member without conversion.

### 4.2 Equipment is the only slot-to-item owner

Keep `_SLOT_ATTRIBUTE_BY_SLOT` private to `Equipment`. Add a small public
read-only iterator returning `(EquipmentSlot, EquippableItem | None)` in
`EQUIPMENT_SLOT_ORDER`. Server projection must consume this method instead of
redeclaring attribute names in `_EQUIPMENT_SLOT_ROWS`.

`Equipment.group_equippable_items()` must return typed slot rows internally,
not a dictionary keyed by attribute-name strings. Each displacement carries an
`EquipmentSlot` value.

Armor content continues to own `body_part: BodyPart`. The generic armor slot
path must convert a non-ring body part through one engine helper that rejects
`BodyPart.RING`; `Ring` continues to override compatible slots with the two
concrete `RingSlot` values. No class-name switching belongs in server code.

## 5. Backend contract hard cut

The following fields become `EquipmentSlot` rather than `str` or
`VisualLoadoutSlot`:

- `APIEquipmentSlot.slot`;
- `APIItemSummary.equipped_slot` when present;
- `APIEquippableDisplacement.slot`;
- `EquipRequest.slot` when present;
- `UnequipRequest.slot`;
- `VisualEquipmentLayer.slot`;
- `EquipmentSpritePresentation.equipment_slot`;
- authored item presentation/category `equipment_slot` fields.

Remove `APIEquipmentSlot.slot_type`. It is neither slot identity nor mechanics,
and the current frontend does not use it except for equality/reconciliation.
Item kind remains available on the equipped item itself.

Replace the JSON-object-keyed equippable response with typed rows:

```python
class APIEquippableSlot(BaseModel):
    slot: EquipmentSlot
    candidates: tuple[APIEquippableEntry, ...]

class APIEquippableItems(BaseModel):
    entity_uuid: str
    slots: tuple[APIEquippableSlot, ...]
```

This is necessary because JSON object keys and the current generator degrade
`dict[EquipmentSlot, ...]` back to an unclosed `Record<string, ...>`.
`slots` is always the complete thirteen-row `EQUIPMENT_SLOT_ORDER`, including
rows with `candidates=()`. The model rejects missing, duplicate, extra, or
reordered slots. This gives backend and NeuroClient one stable empty-candidate
contract instead of a sparse-map convention.

Delete `_equipment_slot_map()` from `server/event_server.py`. Pydantic request
validation supplies the enum member directly to `Entity.equip_item()` and
`Entity.unequip_item()`. Invalid old lower-case aliases fail structural request
validation; they are not translated by the route.

`_equipment_context()` and `_equipment_http_exception()` must not retain a call
to the deleted map. Type their optional slot as `EquipmentSlot | None` and, if
the correction payload keeps `valid_slots`, derive its serialized values only
from `EQUIPMENT_SLOT_ORDER`. Focused tests preserve every ordinary invalid-UUID,
not-found, not-equippable, semantic-operation, and empty-slot 400/404 response;
only structural slot parsing changes to 422 below.

This deliberately retires the legacy route-owned `400 invalid_slot` response
with `valid_slots`. A structurally invalid or retired slot now receives the
standard typed FastAPI 422 validation envelope before route execution. A valid
slot rejected by item compatibility, occupancy, lifecycle, or event mechanics
remains a structured equipment-operation 400. Update backend and NeuroClient
error tests explicitly; do not add a raw-string request wrapper merely to
preserve the old status code.

`project_equipment_overview()` iterates the `Equipment` owner and emits the
same enum member. `build_entity_visual_loadout()` copies that member directly.
No `VisualLoadoutSlot(slot.slot)` conversion remains.

### 5.1 Keep attack weapon-slot evidence typed

The following active facts represent the same `WeaponSlot` identity and become
`WeaponSlot | None` rather than `str | None`:

- `AvailableActionInfo.weapon_slot` and its `_make_action_info()` path;
- AI `ActionAffordance.weapon_slot` and `ActionCapability.weapon_slot`;
- AI semantic `CapabilitySelector.weapon_slots` as `frozenset[WeaponSlot]`;
- `AttackLogData.weapon_slot`;
- item/authored action fields that select an equipped weapon slot, including
  weapon-coat actions;
- mechanics `attack_context["weapon_slot"]`, which retains the `WeaponSlot`
  member instead of degrading it through `.value`;
- any active API/SDK model that forwards those exact fields.

Delete `PresentationWeaponSlot` and type `AttackPresentationCue.weapon_slot`
as `WeaponSlot | None`. The subjective mapper copies the enum directly and
deletes `_weapon_slot()` conversion. This is an identity correction only: it
does not change attack selection, damage, delivery, VFX, or cue timing.

## 6. Presentation metadata without image ownership

Presentation metadata may say that a sprite contribution belongs to
`WeaponSlot.MELEE_MAIN`, `BodyPart.BODY`, or `RingSlot.LEFT`. That is a symbolic
association with a mechanical storage position; it does not make the engine an
image owner.

Migrate existing `EquipmentSpritePresentation`, authored item variant
inventory, and presentation catalog rows from `VisualLoadoutSlot.*` to the
corresponding engine enum members. Do not change:

- `sprite_key`, `portrait_key`, `icon_key`, or asset paths;
- `EquipmentRenderLayer`;
- tint or visual variant semantics;
- safe-presentation privacy rules;
- the client renderer's mapping from a canonical slot to a local render layer.

Because slot values participate in canonical presentation serialization,
presentation contract hashes and generated fixtures must be regenerated in the
same atomic cut. Old hashes are not accepted as aliases.

### 6.1 Version and durable-artifact cutover

Make the incompatibility explicit instead of changing hashes under old version
numbers:

- authored item variant ledger schema `3 -> 4`;
- safe content-presentation hash contract `1 -> 2`;
- content catalog schema `7 -> 8`;
- player replication contract version `1 -> 2`;
- timeline contract version `1 -> 2` because `AttackLogData` is transitive
  through combat-log frames and `timeline_wire_schema()`;
- objective replay contract version `1 -> 2` because typed attack-log schema is
  transitive replay truth;
- subjective player replay contract version `1 -> 2` because player
  replication/loadout schema is transitive replay truth.

The content manifest schema may remain 2 because its structure is unchanged;
its content-set and built-in artifact digests change normally. Generated
event/SDK contract hashes also change under their existing build-identity
mechanism.

`CharacterItemV1` and `CharacterHoldingsRevision` remain schema 1 only when the
mandatory zero-abstract-ring audit passes. This is a correction of a type that
admitted a mechanically impossible state, not a rewrite of any accepted stored
value. If the audit fails, the hard cut is blocked as stated in §3.

Update `devtools/import_neuroclient_item_visual_inventory.py` to emit canonical
engine values and ledger schema 4 before regenerating the checked-in ledger.
Otherwise a later normal import would resurrect the retired aliases.

Do not overwrite or reinterpret immutable replay artifacts. Older objective or
subjective replay artifacts remain stored as historical metadata but are
intentionally not decoded by the new contract. `GameHistoryQueryService` must
distinguish “older retained artifact exists” from “artifact missing” and return
a typed, non-500 `artifact_contract_retired` response. NeuroClient renders that
replay/Studio entry as unavailable with an explanatory message; it does not
attempt import, reset a live follower, or silently hide the game itself.
Current-version replays remain fully usable. No legacy slot decoder or alias map
is introduced.

## 7. Generated Python/TypeScript contract

Regenerate once after Python contract changes are complete.

Required generated truth:

- `APIEquipmentSlot.slot`, `VisualEquipmentLayer.slot`, equip/unequip requests,
  item summaries, and equippable rows expose the same union of `WeaponSlot`,
  the seven concrete `BodyPart` literals, and `RingSlot`;
- action discovery, AI capability/affordance, combat-log, and attack-cue
  `weapon_slot` fields expose `WeaponSlot | null` directly;
- `BodyPart` may still contain `"Ring"` for item classification, but no
  equipment-slot field admits it;
- `VisualLoadoutSlot` and `PresentationWeaponSlot` are absent from the contract
  manifest and TypeScript;
- no equipment-slot field is emitted as plain `string`;
- generated validators reject every retired lower-case alias.

SDK render projection must not maintain another canonical slot list and must
not lexically re-sort slots. Equipment overview, derived visual loadout, patch,
replay, and render projection preserve the backend-authored canonical sequence.
Python model/tests enforce that the sequence is an ordered subset of
`EQUIPMENT_SLOT_ORDER`; actual actor layer stacking continues to use
`EquipmentRenderLayer`.

## 8. NeuroClient migration

The active frontend target is exactly
`/home/tommaso/Dev/NeuroClient/app`. It imports the frozen generated package at
`@neurodragon/dnd-engine-sdk`; implementation records the exact backend SDK
build/manifest hashes consumed by that app.

NeuroClient derives:

```typescript
type SlotName = APIEquipmentSlot["slot"];
```

Delete the hand-written `SLOT_NAMES`, `SLOT_NAME_SET`, `isSlotName()`, and
`requireSlotName()` authority. SDK decoding already validates server payloads.

The equipment panel consumes the ordered `overview.slots` and typed
equippable-slot rows. It sends the exact selected generated value in equip and
unequip requests. Display labels and screen coordinates remain legitimate
frontend presentation choices, but their maps/switches must be exhaustive over
`SlotName` and end in a `never` assertion so contract additions fail compile.

Update the renderer adapter's keys from retired aliases to engine values. This
mapping remains frontend-owned because it maps a valid game slot to a Pixi
layout/render concern; it does not validate, rename, or authorize a game slot.

No V1 compatibility adapter, alternate slot parser, or dual-payload period is
allowed.

## 9. Implementation sequence

This is one atomic unit with reviewable checkpoints, not independently shippable
partial features.

1. **Domain checkpoint:** tighten `EquipmentSlot`, type equipped state, expose
   owner iteration/grouping, and prove all thirteen slots plus ring rejection.
2. **Backend checkpoint:** hard-cut all equipment overview, item, affordance,
   mutation, persistence, action/AI weapon-slot facts, combat logs, and
   presentation fields; delete route/projection mappings.
3. **Contract checkpoint:** migrate presentation rows, regenerate manifests and
   TypeScript, apply the version matrix in §6.1, and prove no
   `VisualLoadoutSlot` or plain-string slot field.
4. **Frontend checkpoint:** consume the frozen generated SDK, remove the local
   slot authority, adapt layout keys, and restore complete equipment UI flows.
5. **Deletion checkpoint:** remove obsolete helpers, tests, fixtures, and docs
   only after their replacement behavioral gates are green.

Do not merge or hand off a backend-only intermediate wire format to the live
frontend. Freeze one generated SDK identity after checkpoint 3 and consume that
exact identity in checkpoint 4.

## 10. Required tests and acceptance gates

### 10.1 Domain and persistence

- TypeAdapter/Pydantic accepts exactly thirteen concrete slots.
- `BodyPart.RING` and all thirteen retired lower-case aliases reject as command
  slots.
- The read-only repository audit covers every holdings revision and proves zero
  persisted abstract-ring slots before type narrowing.
- Equip, conflict displacement, two-handed footprints, shield placement,
  left/right rings, unequip, inventory return, destruction, and rematerialized
  persistent holdings retain exact enum identity.
- Every item-reported compatible/default/occupied slot belongs to
  `EQUIPMENT_SLOT_ORDER`.

### 10.2 Backend vertical

- Equipment overview returns thirteen unique rows in canonical order.
- Each occupied row's slot equals `item.equipped_slot` and its visual layer
  slot.
- Equippable rows use typed slots and exact typed displacement slots.
- Equip with an omitted slot still uses item-owned default policy.
- Explicit equip/unequip accepts canonical values and rejects retired aliases
  before engine mutation.
- Persistent character equipment mutation and terminal settlement preserve the
  same enum member without reparsing.
- Action discovery, AI affordance/capability projection, attack combat logs,
  and attack presentation cues carry the originating `WeaponSlot` member with
  no string or presentation-enum conversion.
- Attack modifier/mechanics context retains the exact `WeaponSlot` runtime type;
  only generic formatting, hashing, or composite string boundaries call
  `.value`.
- Ordinary equipment 400/404 errors remain structured and source `valid_slots`
  from `EQUIPMENT_SLOT_ORDER`; retired/unknown request tokens alone use 422.

### 10.3 Presentation and privacy

- Controlled equipment overview and privacy-safe visual loadout use identical
  slot identities for the same visible equipped item.
- Existing hidden-visual policy is unchanged: occupied items remain represented
  in the canonical visual loadout with `equipped_visual_policy="hidden"`, and
  existing presentation consumers continue to suppress their actor layer.
- Authored presentation lookup finds the same sprite rows after slot migration;
  no image/path behavior is changed.
- Subjective replica bootstrap, patch, replay, and Studio import/export accept
  the new generated slot union and reject retired aliases.

### 10.4 Frontend product

- TypeScript build has no slot cast and no local slot validator.
- Login-to-encounter equipment panel renders all thirteen rows.
- Equip, swap/displacement preview, two-handed conflict, shield, both rings,
  unequip, reconnect, and resync remain usable.
- Actor visual loadout follows equipment changes without a duplicate slot
  conversion.
- `npm run check`, `npm run build`, `npm run inventory-panel:smoke`,
  `npm run equipment-transition-presentation:smoke`,
  `npm run presentation-contract:smoke`,
  `npm run studio-evidence-import:smoke`,
  `npm run studio-document-history:smoke`, and
  `npm run game-browser-history-read-model:smoke` pass in
  `/home/tommaso/Dev/NeuroClient/app` against the recorded SDK identity.
- A retained version-1 replay is shown as explicitly unavailable; a version-2
  equipment-transition replay imports and renders.

### 10.5 Deletion/static gates

Targeted source scans must prove:

- no `VisualLoadoutSlot` or `PresentationWeaponSlot` reference remains in
  production, active tests, generated contracts, or NeuroClient;
- no `_equipment_slot_map`, `SLOT_NAMES`, `requireSlotName`, or equivalent
  alias table remains;
- no equipment storage/request/projection slot or active action/log/cue
  `weapon_slot` field is typed as raw `str` or TypeScript `string`;
- retired lower-case slot spellings remain only where they are legitimate
  Python attribute names or negative rejection fixtures, never accepted
  serialized contract values or client command literals.

Run focused equipment, persistence, presentation-contract, player-replication,
SDK generation/check, and NeuroClient equipment/build gates. Do not run the
whole pytest suite or archived server batches.

## 11. Explicit non-goals

- image, portrait, icon, sprite-file, atlas, or asset-path ownership;
- replacing `EquipmentRenderLayer` or redesigning Pixi composition;
- changing item compatibility, AC, attack, damage, or action mechanics (typing
  existing `WeaponSlot` evidence is in scope; changing its behavior is not);
- shared-initiative or controller changes;
- runtime coordination, leases, replication redesign, or server topology;
- accepting old lower-case aliases for compatibility;
- creating a universal generic enum framework.

## 12. Completion rule

The unit is complete only when one canonical engine enum member crosses every
storage, projection, command, persistence, SDK, and frontend boundary without
translation, all active product flows are green, and the duplicate enum/string
authorities are deleted. Compile-green with retained alias maps, or backend
green while the equipment UI is broken, is not completion.
