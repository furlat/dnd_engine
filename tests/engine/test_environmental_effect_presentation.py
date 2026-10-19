"""Visible native surfaces explain their effects through sensory observations."""

import pytest

from dnd.core.events import Event, EventPhase, EventType
from dnd.spatial.environmental_conditions import ElectrifiedWater, IceSurface, SteamCloud, WetSurface
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game


@pytest.mark.parametrize("effect_type,meaning", (
    (WetSurface, "wet"), (IceSurface, "dexterity"),
    (ElectrifiedWater, "lightning"), (SteamCloud, "obscur"),
))
def test_visible_environmental_effect_has_a_useful_public_description(game, effect_type, meaning):
    observer = combatant(game)
    effect = effect_type(source_entity_uuid=observer.uuid, position=(3, 2),
                         affected_positions={(3, 2)})
    cause = Event(name="Create surface", event_type=EventType.BASE_ACTION,
                  source_entity_uuid=observer.uuid).phase_to(EventPhase.EFFECT)
    result = effect.activate(parent_event=cause)
    assert result is not None and not result.canceled
    observer.update_entity_senses(max_distance=10)
    observation = observer.senses.spatial_effects[effect.uuid]
    assert observation.name == effect.name
    assert meaning in observation.description.lower()
