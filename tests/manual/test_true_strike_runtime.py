"""A discovered True Strike owns one real, identified weapon attack."""

import pytest

from dnd.actions import AttackEvent, SpellEvent
from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageAppliedEvent, EventQueue
from tests.game.true_strike_scenarios import true_strike_history


@pytest.mark.parametrize("ranged", (False, True))
@pytest.mark.parametrize("miss", (False, True))
def test_discovered_true_strike_retains_weapon_attack_identity_damage_and_parent(ranged, miss):
    history = true_strike_history(ranged=ranged, miss=miss)
    lineage, = [row for row in history.lineages if isinstance(row.root, SpellEvent)]
    spell = lineage.root
    assert isinstance(spell, SpellEvent) and spell.behavior_id == "spell.true_strike"
    attack, = [event for event in lineage.events if isinstance(event, AttackEvent)]
    assert attack.behavior_id == "action.attack"
    assert attack.provided_by_id == "spell.true_strike"
    assert attack.parent_lineage == spell.lineage_uuid
    assert attack.source_entity_uuid == spell.source_entity_uuid
    assert attack.target_entity_uuid == spell.target_entity_uuid
    assert attack.override_ability == "intelligence" and not attack.costs
    assert attack.weapon_slot is (WeaponSlot.RANGED_MAIN if ranged else WeaponSlot.MELEE_MAIN)
    assert attack.source_item_uuid is not None
    assert attack.source_item_presentation is not None
    assert attack.source_item_presentation.item_id == ("weapon.shortbow" if ranged else "weapon.shortsword")
    assert attack.attack_outcome is (AttackOutcome.CRIT_MISS if miss else AttackOutcome.HIT)
    assert [kind.value for kind in attack.damage_types] == ["Piercing", "Radiant"]
    damages = [event for event in lineage.events if isinstance(event, DamageAppliedEvent)]
    assert len(damages) == int(not miss)
    if not miss:
        damage, = damages
        assert damage.applied_damage == 12 and damage.resulting_normal_hp == 48
        assert damage.target_entity_uuid == attack.target_entity_uuid
        assert damage.resolution is not None
        assert [(part.damage_type.value, part.incoming_damage) for part in damage.resolution.components] == [
            ("Piercing", 8), ("Radiant", 4)]
        ancestors = {event.lineage_uuid: event for event in lineage.events}
        parent = damage.parent_lineage
        while parent is not None and parent != attack.lineage_uuid:
            parent = ancestors[parent].parent_lineage
        assert parent == attack.lineage_uuid
    # Captures remain useful after disposing of every native object/event.
    assert not BaseObject._registry and EventQueue.event_cursor() == 0
