# Telekinesis destination selection — 2026-10-04

Implementation checkpoint; independent root review required. This fixes the missing player command route for the approved native initial/repeat transfer.

EntityDestinationSelection is one cold PositionSelection variant. Both Telekinesis forms opt in. Creature discovery admits a recipient only when some legal destination exists; get_extra_position_options binds that exact recipient and returns native validated visible candidates. Command submission requires exactly one destination and binds it to existing end_position. Native admission runs again before costs; the existing transfer resolver rechecks after intervening save/reaction events.

Controls retain the selected creature, accept one landing by map click or keyboard P, support Backspace, and refuse confirmation before a destination exists. Session queries and commits use existing action APIs. No spell-name UI branch, new spell executor, or private destination list exists. The item-use adapter and AI intent validator accept the same typed one-position capability; the AI policy itself is unchanged.

The forced_movement_scenarios Telekinesis fixture now uses a paid initial cast with deterministic successful resistance, an actual subsequent caster turn, and a paid entity-plus-destination repeat. The initial cast spends its slot/action and retains no victim. Existing function signature/case identifiers and Shove branch remain. Bootstrapped telekinesis-displacement capture succeeds with one retained repeat lineage and (4,3)→(6,4) transfer. Root owns updated hostile impact/playback expectations and the old catalog prose that still described free Move.

Validation:
- New test initially reproduced empty Telekinesis recipient discovery (StopIteration), before implementation.
- 53 passed in 13.79s: native destination, existing Telekinesis/landing and existing wall point selection.
- 3 passed in 4.03s: initial/repeat mouse+keyboard selection and live session.
- 44 passed in 37.88s: existing controls/session/discovery/dependency boundaries.
- Final extended native/UI/AI/item-use/wall selection: 20 passed in 10.14s.
- Changed production, fixtures and new test typing: zero errors/warnings.

Files: dnd/core/action_types.py, dnd/core/base_actions.py, dnd/actions_functional.py, dnd/ai/runtime/execution.py, dnd/spells/transmutation.py (selection declarations only), game/controls.py, game/session.py, tests/game/forced_movement_scenarios.py, tests/engine/test_entity_destination_selection.py, tests/game/test_entity_destination_selection.py.

Concurrent shared source work remains under its respective owners. No commits, new artwork or external communication occurred.
