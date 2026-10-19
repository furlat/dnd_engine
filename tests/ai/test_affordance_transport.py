"""Controller transport preserves position-selection rules and real epochs."""

import pytest

from dnd.ai.contracts.control import ActionAffordance, ActionSourceDefinition, AffordanceSet
from dnd.ai.runtime.decision_epoch import build_decision_epoch
from dnd.core.action_types import (
    EntityDestinationSelection, PositionPathSelection, SinglePositionSelection,
)
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe


@pytest.mark.parametrize("selection", (
    SinglePositionSelection(),
    EntityDestinationSelection(),
    PositionPathSelection(max_length_feet=60),
    PositionPathSelection(max_length_feet=100, max_segments=4, allow_origin_start=True,
                          origin_start_offset_cells=1),
))
def test_position_selection_rules_survive_affordance_transport(selection) -> None:
    source = ActionSourceDefinition(
        source_action_id="test.aim", bucket="position_actions", template_name="Aim",
        display_name="Aim", action_category="spellcasting", target_type="position",
        can_afford=True, position_selection=selection,
    )
    affordances = AffordanceSet(
        actor_uuid="00000000-0000-0000-0000-000000000001", computed_at_observation_cursor=0,
        position_actions=(ActionAffordance(row_id="aim", source=source),),
    )
    restored = AffordanceSet.model_validate_json(affordances.model_dump_json())
    assert restored.position_actions[0].position_selection == selection
    assert restored.position_actions[0].source == source


def test_authored_archmage_decision_epoch_survives_transport() -> None:
    reset_engine_runtime()
    game = Game()
    try:
        assembled = prepare_encounter_recipe(
            encounter_recipe("encounter.high_level_spell_resource_duel"), game=game,
        )
        actor = next(actor for actor in assembled.entities_by_member_address.values()
                     if "Archmage" in actor.name)
        actor.update_entity_senses(max_distance=20)
        epoch = build_decision_epoch(actor, epoch_namespace="roundtrip", round_number=1,
                                     turn_index=0, observation_cursor=0).epoch
        assert any(row.base_template_name == "Dimension Door"
                   for row in epoch.affordances.all_rows)
        restored = AffordanceSet.model_validate_json(epoch.affordances.model_dump_json())
        assert restored.model_dump(mode="python") == epoch.affordances.model_dump(mode="python")
    finally:
        game.close()
        reset_engine_runtime()
