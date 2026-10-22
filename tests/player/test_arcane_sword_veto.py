"""A rejected sword lifetime never publishes or leaves an independent blade.

Input: real Arcane Sword cast with owner, concentration or blade admission vetoed.
Boundary: native admission -> captured public updates -> detached client state.
Expected: no damage, blade creation, retained anchor or granted follow-up action.
"""

import pytest

from dnd.conditions import Concentrating
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.events import EventHandler, EventPhase, EventQueue, EventType, SpatialEffectChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.spells.evocation import ArcaneSword, ArcaneSwordAnchor, ArcaneSwordEffect, ArcaneSwordStrike, MoveArcaneSword
from tests.player.test_arcane_sword_anchor import blades, capture
from tests.player.test_solid_wall_transport import clients_at_boundary, wall_world


@pytest.mark.parametrize('refused_kind,phase', [
    (ArcaneSwordEffect, EventPhase.EFFECT),
    (Concentrating, EventPhase.DECLARATION),
    (ArcaneSwordAnchor, EventPhase.EFFECT),
])
def test_rejected_sword_admission_has_no_blade_or_public_creation(refused_kind, phase):
    with wall_world(ArcaneSword, displaced=False) as (runtime, seat, publication):
        caster = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        victim = next(actor for actor in runtime.session.game.entities.values() if actor.position == (8, 7))
        clients = clients_at_boundary(runtime)

        def refuse_owner(event, _):
            if isinstance(event, ConditionApplicationEvent) and isinstance(event.condition, refused_kind):
                return event.cancel(status_message='Sword lifetime rejected')
            return None

        caster.add_event_handler(EventHandler(name='Reject sword lifetime', source_entity_uuid=caster.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=phase)],
            event_processor=refuse_owner))
        template, = (action for action in caster.registered_actions if isinstance(action, ArcaneSword))
        hp = victim.get_hp()
        cursor = EventQueue.event_cursor()
        result = template.instantiate(target_entity_uuid=victim.uuid, end_position=(9, 7)).apply()

        assert result is not None and result.canceled
        assert victim.get_hp() == hp
        assert not any(isinstance(condition, ArcaneSwordEffect) for condition in caster.active_conditions.values())
        assert 'Concentrating' not in caster.active_conditions
        assert not any(isinstance(condition, ArcaneSwordAnchor) for condition in get_map().get_spatial_conditions())
        assert not any(isinstance(action, (ArcaneSwordStrike, MoveArcaneSword)) for action in caster.registered_actions)
        assert not any(isinstance(event, SpatialEffectChangeEvent)
            for _, event in EventQueue.iter_events_since(cursor))
        capture(runtime, clients, cursor)
        assert all(not blades(client) for client in clients.values())
