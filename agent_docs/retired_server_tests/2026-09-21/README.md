# Retired server test disposition — September 21

The cleanup plan restores the active native game/engine suite without importing
or rebuilding the retired threaded HTTP/session/replication server. The `.py.txt`
files here preserve the five original source files as history, including the
mixed modules' native tests before extraction. They are not an executable test
lane and are not counted as passing tests.

The ordinary active command remains:

```sh
uv run --no-sync python -m pytest tests/game tests/engine
```

## Native assertions retained

| Former module | Active disposition |
| --- | --- |
| `test_spellcasting.py` | All 19 native tests remain at the same path. Catalog membership, display name, level, event identity, multi-target payload and Fireball save metadata now use the current native spell composition rows. The former HTTP DTO's `vfx.route_hint` is represented by its original native `metadata.delivery`; no new catalog builder was introduced. |
| `test_encounter_apis.py` | Nine native encounter/controller tests remain, covering callbacks, turns/rounds, automated/human/Codex turn boundaries, surprise, navigation, logs and death reconciliation. A tenth test preserves the native entity/encounter JSON serialization part of the old mixed catalog/API test. Setup uses real composition, Game deployment and runtime reset. The navigation fixture now places an explicitly perceived movement-only boundary instead of the removed scalar side setter. |
| `test_manual_20_encounters_turns_controllers_apis.py` | The first five native encounter/controller tests remain at the same path, preserving lifecycle, turns, automatic advance, action/log listeners and death reconciliation. Their fixture no longer resets a server singleton. |

Current retained-world initialization, actor births and spatial state are covered
by `tests/engine/test_world_entity_initialization.py` and
`tests/engine/test_recorded_world_facts.py`. Player disclosure and passive replay
are tested through the current `game` projection/reduction tests, including
`test_recorded_history.py`; this does not claim equivalence with the retired HTTP
protocol's envelopes or objective cache layout.

## Explicitly retired consumers

| Source | Retired assertions |
| --- | --- |
| `test_encounter_apis.py.txt` | The server half of `test_eb_18_006_serialization_and_spell_catalog_api_do_not_mutate_registry`, plus the HTTP/SSE/editor/session/replication tests listed below. These depend on `server.event_server`, its session singleton, stream envelopes or editor contracts; those interfaces are not the current Pygame recovery boundary. |
| `test_manual_20_encounters_turns_controllers_apis.py.txt` | `test_session_api_exposes_authoritative_turn_actions_and_results` and `test_lethal_multi_entity_command_reports_causal_death_and_primary_hp` exercise the retired `/session`, `/action` and replication endpoints. Their native turn/action/death contracts remain independently exercised by the retained native modules and gameplay replay tests. |
| `test_manual_21_arena_game_sessions_client_state.py.txt` | All six tests construct a scenario through the retired server test client and assert session/replication/API envelopes. Scenario composition, native area spells and jumping remain active features, tested at their native and saved-player-event boundaries. No `/game` or `/replication` API compatibility is claimed. |
| `test_objective_state.py.txt` | All four tests exercise `server.objective_state` builders and the old objective senses-cache dump, including removed `ItemRuntimeOrigin` recipes. These private DTOs are not current player events or initialization; copying every objective observer cache is not a current disclosure requirement. |

The complete historical source is retained, so future server work can inspect
these former protocol assertions deliberately rather than inheriting them as
silent requirements on native gameplay or restoring removed imports to collect.

The older manual server-contract wrappers (`test_147_mapeditor_legacy_contract`,
`test_149_remaining_legacy_contract` and `test_legacy_ai_server_privacy_coverage`)
still refer to some of these retired helpers or test selectors. They already
depend on the retired server and are outside the active game/engine command.
This disposition does not claim that the entire historical `tests/manual` tree
is collectible or that those HTTP contracts were migrated.

### Retired encounter HTTP/SSE assertions

- `test_eb_18_030_health_endpoint_is_state_free`
- `test_eb_18_007_objective_event_frames_preserve_directional_spatial_fields`
- `test_eb_18_008_mapeditor_api_saves_map_state_without_entities_or_encounter`
- `test_eb_18_022_mapeditor_save_load_roundtrip_restores_entity_free_state`
- `test_eb_18_024_mapeditor_tile_snapshot_preserves_grid_context`
- `test_eb_18_009_action_execute_error_payload_reports_available_corrections`
- `test_eb_18_027_available_actions_serializes_spell_slot_variant_metadata`
- `test_eb_18_010_one_action_endpoint_shares_structured_errors_across_kinds`
- `test_eb_18_023_action_target_indices_are_bound_to_current_affordances`
- `test_eb_18_011_entity_and_handler_errors_report_current_choices`
- `test_eb_18_012_equipment_errors_report_slots_inventory_and_loadout`
- `test_eb_18_013_session_and_game_errors_report_valid_sessions_and_entities`
- `test_eb_18_032_session_create_ping_and_delete_are_stateful`
- `test_eb_18_033_game_join_status_and_session_entities_are_stateful`
- `test_eb_18_014_replication_identity_errors_are_explicit`
- `test_eb_18_025_end_turn_without_active_encounter_reports_state_context`
- `test_eb_18_026_session_authority_errors_report_action_context`
- `test_eb_18_015_mapeditor_errors_report_catalog_map_and_save_context`
- `test_eb_18_016_editor_and_player_seeds_serialize_their_own_state`
- `test_eb_18_017_player_combat_log_window_has_no_cursor_duplication`
- `test_eb_18_018_combat_log_sse_follows_matching_completion_event`
- `test_eb_18_035_handler_toggle_round_trip_exposes_only_player_choices`
- `test_eb_18_036_equipment_mutations_acknowledge_and_replicate_loadout`
- `test_eb_18_037_turn_switch_updates_session_authority`

## Architecture assertions

`architecture_server_assertions.py.txt` preserves two old server-only checks.
The cold `server.event_server` import test is replaced by the active `game.app`
cold import test, asserting that no AI/server package is loaded. The cold
`server.world_contracts` DTO-import test is retired with that transport surface;
its missing old `dnd.core.senses` import is not repaired to revive the server.
Native dependency direction, unique neutral owners, passive-value edges and
full static DAG checks remain active. The Studio equipment-slot literal now has
an explicit `StudioEquipmentSlot` name distinct from native `EquipmentSlot`.
The existing passive sensing geometry edge is declared explicitly; it introduces
no runtime-owner dependency.
