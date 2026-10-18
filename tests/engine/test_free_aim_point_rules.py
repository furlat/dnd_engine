"""A zone spell answers which points lie in its free-aim region exactly as its listed region does."""
import pytest

from dnd.entity import Entity
from dnd.spells.conjuration import CallLightning, CallLightningStrike
from dnd.spells.transmutation import CreateOrDestroyWater
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena


@pytest.mark.parametrize('spell_type', (CreateOrDestroyWater, CallLightning, CallLightningStrike))
def test_points_in_region_match_the_listed_region(spell_type):
    reset_spell_regression_arena(24, 12)
    caster = create_spell_regression_actor('Caster', (2, 5), 'heroes', spell_slots={3: 2})
    Entity.update_all_entities_senses(max_distance=120)
    spell = spell_type(source_entity_uuid=caster.uuid)
    points = [(x, y) for x in range(-2, 27) for y in range(-2, 15)]  # the map, and cells off it
    region = set(spell.get_valid_positions())
    assert spell.valid_positions_among(points) == [point for point in points if point in region]
    assert (2, 5) in region  # the caster's own cell
    assert (23, 5) not in region  # in sight, out of range
