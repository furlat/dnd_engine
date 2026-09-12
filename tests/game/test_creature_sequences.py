"""Real creature histories keep their native identity through fixed-rig playback."""

from pathlib import Path

import pytest

from dnd.actions import AttackEvent, MovementEvent
from dnd.core.equipment_types import WeaponSlot
from dnd.core.life_types import LifeState
from game.animation_data import load_animation_data
from game.attack import BoundAttack
from game.choreography import bind_choreography
from game.player_reduction import reduce_lineage
from game.player_facts import AttackFact
from tests.game.player_helpers import player_history
from game.scene import scene_actors
from tests.game.creature_scenarios import creature_history


@pytest.mark.parametrize("identity,slot,rig", (
    ("content.srd_5_1_cc:creature:creature.dretch@1", WeaponSlot.MELEE_MAIN, "smallscale.demonbeast01"),
    ("content.neurodragon:creature:creature.skeleton_archer@1", WeaponSlot.RANGED_MAIN, "smallscale.skeletonarcher05"),
    ("content.srd_5_1_cc:creature:creature.wolf@1", WeaponSlot.MELEE_MAIN, "smallscale.greywolf"),
))
def test_native_creature_duel_uses_its_packaged_body_and_real_life_state(identity, slot, rig) -> None:
    captured = creature_history(identity, weapon_slot=slot)
    before, roots = captured.before, captured.lineages
    creature, = (actor for actor in before.actors.values() if actor.uuid != before.observer_uuid)
    assert creature.creature_content_ref == identity
    assert any(isinstance(root.root, MovementEvent) and root.root.source_entity_uuid == creature.uuid for root in roots)
    attacks = [root.root for root in roots if isinstance(root.root, AttackEvent)
               and root.root.source_entity_uuid == creature.uuid]
    assert attacks and attacks[0].weapon_slot is slot
    data = load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))
    history, roots = player_history(captured)
    for root in roots:
        actors = scene_actors(history, data, {})
        selected = next(actor for actor in actors if actor.contact.actor_uuid == str(creature.uuid))
        assert selected.contact.rig_id == rig
        if isinstance(root.root.fact, AttackFact):
            group = bind_choreography(history, root, data)
            assert group.nodes, group.gaps
            assert not [gap for _, gap in group.gaps if not gap.startswith("Missing media:")], group.gaps
            if root.root.fact.source_entity_uuid == creature.uuid:
                bound = group.nodes[0].bound
                assert isinstance(bound, BoundAttack) and bound.timeline.source.rig_id == rig
                assert not [gap for _, gap in group.gaps if gap.endswith("/body")], group.gaps
        history = reduce_lineage(history, root)
    # Native producer already checks every HP/life boundary against the live
    # engine. Replay remains detached after its teardown, including the corpse.
    assert history.actors[creature.uuid].life_state is LifeState.DEAD
    corpse = next(actor for actor in scene_actors(history, data, {})
                  if actor.contact.actor_uuid == str(creature.uuid))
    assert corpse.contact.rig_id == rig
    assert corpse.contact.hp == history.actors[creature.uuid].normal_hp
    assert corpse.contact.hp is not None and corpse.contact.hp <= 0
