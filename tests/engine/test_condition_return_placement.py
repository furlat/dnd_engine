"""Concentration replacement reserves distinct nearest returns without eviction."""

from uuid import uuid4

from dnd.conditions import Concentrating
from dnd.core.base_block import PreparedConditionApplication
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import BanishedCondition


def test_two_banished_returns_reserve_destinations_without_displacing_occupants():
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
        actor((2, 4))
        old = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                            spell_name="Banishment")
        caster.add_condition(old)
        old.add_linked_condition(first.uuid, first_gone.uuid)
        old.add_linked_condition(second.uuid, second_gone.uuid)
        incoming = Concentrating(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
                                 spell_name="New concentration")
        result = caster.prepare_condition_application(incoming)
        assert isinstance(result, PreparedConditionApplication)
        reserved = incoming.prepared_removal_occupancies()
        assert len(reserved) == len(set(reserved)) == 2
        assert not set(reserved) & {(2, 3), (3, 2)}
        with caster.condition_removal_scope():
            caster.commit_condition_application(result)
            caster.publish_condition_application(result)
        assert first.is_deployed and second.is_deployed
        assert first.position != second.position
        assert get_map().get_entities_at((2, 3)) == {occupant_a.uuid}
        assert get_map().get_entities_at((3, 2)) == {occupant_b.uuid}
        assert caster.active_conditions["Concentrating"] is incoming
    finally:
        reset_engine_runtime()
