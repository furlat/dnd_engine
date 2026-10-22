"""The arena's scenario grant preserves equal creator-built summoners."""

from dnd.core.content.encounters import RosterControllerKind
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import prepare_encounter_recipe
from dnd.spells.summoning import ConjureAnimals, SpiritualWeapon
from dnd.types.character_progression import CharacterClass
from monty_sandbox.prepare_trial import summoner_duel_configuration
from server.config import ServerConfig


def test_summoner_duel_materializes_equal_paid_spellcasters_with_distinct_seats(tmp_path):
    config = summoner_duel_configuration(tmp_path, seed=7)
    config = ServerConfig.model_validate_json(config.model_dump_json())
    assert {row.seat_id for row in config.credentials} == {'amber', 'blue'}
    assert len({row.token for row in config.credentials}) == 2
    assert {row.seat_id: row.controlled for row in config.assignments} == {
        'amber': (('amber', 'unit_1'),), 'blue': (('blue', 'unit_1'),)}
    assert all(slot.controller_defaults.controller is RosterControllerKind.CODEX
        for slot in config.recipe.roster_slots)
    reset_engine_runtime()
    game = Game()
    try:
        assembled = prepare_encounter_recipe(config.recipe, game=game)
        amber, blue = assembled.entities
        assert amber.is_enemy(blue) and blue.is_enemy(amber)
        assert (amber.position, blue.position) == ((4, 7), (10, 7))
        assert amber.get_normal_hp() == blue.get_normal_hp()
        equipment = []
        for actor in (amber, blue):
            assert actor.character_body_id == 'creature.player.humanoid_body'
            assert len(actor.applied_class_levels) == 5
            assert all(row.class_id is CharacterClass.CLERIC for row in actor.applied_class_levels)
            assert actor.action_economy.get_normal_spell_slot_capacities() == {1: 4, 2: 3, 3: 2}
            assert [actor.action_economy.spell_slot_value(rank).normalized_score for rank in (1, 2, 3)] == [4, 3, 2]
            assert any(isinstance(action, ConjureAnimals) for action in actor.registered_actions)
            assert any(isinstance(action, SpiritualWeapon) for action in actor.registered_actions)
            items = (*actor.inventory.items.values(), *actor.equipment.get_all_equipped_items())
            equipment.append(sorted(item.item_id for item in items))
            assert 'weapon.shortbow' not in equipment[-1]
        assert equipment[0] == equipment[1]
    finally:
        game.close()
        reset_engine_runtime()
