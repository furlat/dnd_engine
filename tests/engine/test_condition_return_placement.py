"""Concentration replacement cannot partially return two banished creatures."""

from uuid import uuid4

from dnd.conditions import Concentrating
from dnd.core.base_block import PreparedConditionApplication
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import BanishedCondition


def test_conflicting_banishment_displacements_preserve_the_entire_old_graph():
    reset_engine_runtime(grid_size=(8, 8))
    try:
        game = Game()
        def actor(position):
            result = Entity.create(uuid4(), "Actor", config=EntityConfig(position=position))
            result.compose_entity()
            game.deploy_entity(result, position)
            return result
        caster = actor((1, 1))
        first, second = actor((2, 3)), actor((3, 2))
        first_gone = BanishedCondition(source_entity_uuid=caster.uuid, target_entity_uuid=first.uuid)
        second_gone = BanishedCondition(source_entity_uuid=caster.uuid, target_entity_uuid=second.uuid)
        first.add_condition(first_gone)
        second.add_condition(second_gone)
        occupant_a, occupant_b = actor((2, 3)), actor((3, 2))
        actor((2, 4))  # Both displaced occupants would otherwise choose (3, 3).
        old = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                            spell_name="Banishment")
        caster.add_condition(old)
        old.add_linked_condition(first.uuid, first_gone.uuid)
        old.add_linked_condition(second.uuid, second_gone.uuid)
        incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                                 spell_name="New concentration")
        result = caster.prepare_condition_application(incoming)
        assert not isinstance(result, PreparedConditionApplication)
        assert caster.active_conditions["Concentrating"] is old
        assert first_gone.applied and second_gone.applied
        assert first.is_spatially_suspended and second.is_spatially_suspended
        assert get_map().get_entities_at((2, 3)) == {occupant_a.uuid}
        assert get_map().get_entities_at((3, 2)) == {occupant_b.uuid}
        assert not first_gone.prepared_removal_occupancies()
        assert not second_gone.prepared_removal_occupancies()
    finally:
        reset_engine_runtime()
