"""Authored actions tell controllers what their selected operation will do."""

import pytest

from dnd.ai.contracts.semantics import ResourceOperation, TopologyOperation
from dnd.ai.runtime.decision_epoch import build_decision_epoch
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.jaws import materialize_jaw_trap
from dnd.types.traps import TrapState
from tests.engine.test_environment_controls import use
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game


def test_authored_sorcerer_epoch_retains_metamagic_and_conversion_meaning():
    reset_engine_runtime()
    arena_game = Game()
    try:
        assembled = prepare_encounter_recipe(
            encounter_recipe("encounter.standard_skeleton_doors"), game=arena_game,
        )
        actor = assembled.entities_by_roster_slot["roster_1"][0]
        affordances = build_decision_epoch(actor, epoch_namespace="semantics",
            round_number=1, turn_index=0, observation_cursor=0).epoch.affordances
        for name in ("Quickened Spell", "Twinned Spell"):
            row = next(row for row in affordances.all_rows if row.template_name == name)
            assert affordances.semantics_for(row).capability_transformations
        conversions = [row for row in affordances.capabilities
            if row.semantic_key.startswith("action.class.sorcerer.convert_")]
        restores = {
            (row.semantic_id, effect.resource_id, effect.amount)
            for row in conversions
            for effect in affordances.semantic_catalog[row.semantics_ref].resource_effects
            if effect.operation is ResourceOperation.RESTORE
        }
        # The level-five fixture advertises its rank-three conversion forms.
        assert ("resource.convert.slot_to_sorcery_points", "resource.sorcery_points", 3) in restores
        assert ("resource.convert.sorcery_points_to_slot", "spell_slot.3", 1) in restores
    finally:
        arena_game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("reversible,jaw", [(False, False), (True, False), (True, True)])
def test_lever_semantics_describe_selected_state_without_promising_false_deactivation(
    game, reversible, jaw,
):
    operator = combatant(game, position=(1, 1))
    trap = (materialize_jaw_trap((7, 1)) if jaw
            else materialize_spike_trap_condition({(7, 1)}))
    lever = build_trap_lever(trap.uuid, charges=3, allow_activation=reversible)
    lever.place_on_grid((2, 1))
    states = (TrapState.DEACTIVATED, TrapState.READY if jaw else TrapState.ACTIVATED)
    for index, expected in enumerate(states if reversible else states[:1]):
        operator.update_entity_senses(max_distance=10)
        affordances = build_decision_epoch(operator, epoch_namespace="lever",
            round_number=1, turn_index=index, observation_cursor=0).epoch.affordances
        row = next(row for row in affordances.all_rows if row.source_item_uuid == str(lever.uuid))
        semantics = affordances.semantics_for(row)
        disables = expected is TrapState.DEACTIVATED
        assert (semantics.semantic_id == "interaction.trap.deactivate") is disables
        assert any(effect.operation is TopologyOperation.DEACTIVATE_HAZARD
                   for effect in semantics.topology_effects) is disables
        use(operator, lever.uuid, row.template_name.split("__item_")[0])
        assert trap.trap_state is expected
