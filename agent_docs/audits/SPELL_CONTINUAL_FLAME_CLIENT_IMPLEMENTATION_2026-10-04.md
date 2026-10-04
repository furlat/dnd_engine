# Continual Flame real-item client checkpoint — 2026-10-04

Status: implemented and verified in the bounded item lane; root review remains required. No new artwork, native event, condition, queue, manager, or mechanical rule was introduced by this client change.

## Ownership and rendering

The existing `ItemEffectPresentationState` follows the real item through floor `PlayerObject`, equipped `VisualItem`/`RigLayer`, and the entitled owner's controlled inventory. `game/data/item-attachments.json` selects the existing `fire.continual_flame.apply.back/front` and `hold.back/front` registrations by the existing condition behavior ID. The obsolete spatial-effect registration was removed. There is no point object or actor condition standing in for the item.

`game/item_draw.py:compose_item_attachments` is the shared pixel consumer. It reuses `maintained_media_frame` and `registered_media_blits`. Floor drawing brackets the actual isolated item pixels; equipped drawing samples the actual current modular item layer and current camera/clip/frame, unions multiple visual parts of the same item UUID, and brackets the current body at that item anchor. The anchor is the item's occupied pixels, never the actor bounds or a guessed standing-hand offset. Item effects are composed after body material/outline processing, preserve source surfaces, and do not tint the support shadow. Cast-hidden gear and zero-pixel item frames provide no attachment. Whole-item and per-effect suppression tokens omit only magical attachment pixels.

`playback_frame`, ordinary `encounter_play`, and the standard gallery receive the same immutable start records. The ordinary map compositor consumes the resulting real-item commands once; its existing item fallback remains available. Floor targeting still uses the physical item silhouette.

## Exact event clock and disclosure

`ItemAttachmentStart` is passive data. `game/item_attachment_lifetime.py` registers it during existing head admission, keyed by the exact effect UUID and retaining the actual item UUID. It binds application to the admitted native event's `VersionRow` source cursor and existing choreography effect time. Unknown initial/first-observed effects enter their hold. Cover, suppression, movement, unequip/equip, drop and loot preserve the retained time rather than replaying the application. Rendering still requires current disclosed floor or equipped membership; retained dates alone cannot reveal anything.

A minimal `ItemEffectChangeFact` projects the existing native item condition application/removal. Reusing `ConditionChangeFact` would be misleading: its consumers index a creature's condition membership, HP and AC. The item fact instead carries only real item UUID, effect UUID and native event type; the existing PlayerNode/VersionRow carry event identity/cursor, while existing item snapshots own membership. One choreography state-node branch commits it at the existing effect clock. No native event was added.

The object-spell projection now admits the caster's own inventory/equipment and currently visible equipped items as well as observed floor objects. Foreign inventory remains undisclosed. Continual Flame already has an authored actor-only cast recipe, so the existing `bind_body_action` plays Special1 and release timing for a covered owned item without constructing a world object or an item contact in space.

## Validation

- Final focused Continual Flame plus finite body material suite: **23 passed in 18.16s** (`/tmp/continual-final-focused.log`), including all 11 Continual Flame cases.
- Shared projection, item materials, coverage, body actions and import DAG run: **72 passed; one unrelated authored-utility expectation failed** in 132.31s (`/tmp/continual-client-regression.log`). The failure is `test_original_four_utility_drafts_have_body_and_effect_without_projectile`: selected utility release frame is now 7 while the older test expects 8. This lane did not edit those utility recipes or that expectation. All dependency-boundary checks in this run passed.
- Final pyright on all changed client modules, fixture and focused tests: **0 errors/warnings** (`/tmp/continual-client-pyright-final.log`). Changed-file whitespace check passed.
- Standard saved-input gallery rerender: **2/2 paired perspectives passed**, zero gaps and zero failed checks, four cameras, 12 fps, 960×720 mosaic. Run: `.runtime/continual-item-gallery-20261004/runs/20261004T053829Z-a6d404/index.html`. Native capture includes actual floor casting, carrying, cover/uncover, exact suppression tokens and native light refresh/publication, drop/loot/equip, and independent item destruction. It does not claim an Antimagic spell-cast gallery; native suppression behavior has separate engine tests.
- Visually inspected the standard poster plus floor/transfer frames. Current-pose pixel tests cover Idle, Run, Attack5, TakeDamage and Die across all four cameras. The paired native replay verifies the same owner through both carriers, suppression, storage and destruction. Hidden-first-observation verifies that another observer receives hold rather than a private application; the caster receives the actual inventory cast and exact release clock.

## Explicit boundary

Modular equipment with a separately authored visible item layer is supported. A fixed sheet without separable held-item pixels supplies no item attachment anchor, so no hand position is fabricated there. The same real item still renders on the floor using its authored ground appearance. This limitation does not block native ownership/light mechanics or supported modular equipment. The selected bank has application/hold media; actual item removal removes its attachment with the item, without retaining a fake object for a removal tail.

The retained per-effect dates may outlive visibility because the observer is not entitled to infer offscreen removal. Actual current membership controls every frame. Root review should assess this boundary and the projection gate independently; this is an implementation receipt, not self-issued final acceptance.
