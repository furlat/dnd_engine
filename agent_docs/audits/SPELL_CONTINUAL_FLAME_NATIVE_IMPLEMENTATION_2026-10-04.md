# Continual Flame native implementation — 2026-10-04

Implementation checkpoint; independent root review required. No client/art approval is claimed.

The spell selects one actual intact BaseItem through native OBJECT targeting. Its ordinary item-owned ContinualFlameCondition publishes heatless effect membership and owns bright20/dim20 light. Own inventory/equipment and hand-reachable floor items are admitted; another actor's unseen inventory is excluded. Inventory storage covers the light; equipping or floor placement exposes it. Carrier movement, drop/loot, destruction and condition removal use existing ownership and item location events. No new inventory, physical flame, ignition, dousing, or fake object exists.

The condition gates the native light through its exact contribution_owner_uuid. Suppression/resumption retains the same native light UUID. ItemEffectPresentationState now permits absent damage contribution/type and carries suppression_provider_uuids; BaseItem fills this from the condition's existing provider set without losing effect identity. Changing physical exposure/holder may retire/recreate a light while preserving the item and condition identities.

Bounded shared changes: BaseAction.include_owned_item_targets opts into own gear candidates; Entity._collect_object_actions merges those candidates with sensed floor objects. BaseItem.publish_location_state calls the existing placement hook before completion. SpellCatalogTargetType includes object. Native target and placement validation still run on execution. The obsolete ContinualFlameObject and its architecture exception were removed; old anchor tests now use real items.

Initial condition application snapshots retain their existing cursor convention: resulting_item contains the effect identity, while applied_source_event_cursor is assigned after completion and appears in later item snapshots. Client playback must use the initial application fact's cursor, as for existing item effects.

Validation:
- 49 passed in 8.52s: new item tests plus complete silent-removal, anchored-condition and Cleric legacy native files.
- 55 passed in 34.97s: inventory/equipment, action discovery and dependency boundaries.
- 9 passed in 5.61s: final item cases (including suppressed membership) and spell catalog composition.
- Production and new test typing: zero errors/warnings, including final tuple/fixture check. Bootstrapped paired native capture passes with 14 lineages.
- Historical manual test_178_spell_catalog_content_identity.py cannot collect because it imports missing dnd.content_system.item_bindings; this unrelated stale module was not changed. Current architecture spell catalog composition passes.
- Initial test authoring included incorrect Inventory.add/loot UUID calls and an overlarge light fixture; these were corrected to actual public commands and a minimal dark map. They were test setup failures, not claimed gameplay regressions.

Touched native sources: dnd/spells/evocation.py (Continual Flame section), dnd/core/item_types.py, dnd/core/base_actions.py, dnd/entity.py (object discovery only), dnd/blocks/base_item.py, dnd/spells/catalog_content.py, dnd/spells/content_metadata.py. Tests: tests/engine/test_continual_flame_items.py, test_condition_silent_removal.py, test_anchored_condition_inputs.py; tests/manual/test_134_cleric_batch1_legacy_contract.py (Continual Flame cases only); tests/architecture/test_dependency_boundaries.py (removed obsolete raw placement exception). The existing tests/game/continual_flame_scenarios.py capture now enchants two real Club items and retires them independently; its function signature and observer roles remain.

Other agents concurrently own neighboring sections in shared files. Root owns presentation bindings/tests and review of this implementation.
