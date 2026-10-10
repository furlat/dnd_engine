"""One player's recorded encounter stays visible across their heroes' turns."""

import json
from uuid import uuid4

import pytest

from dnd.conditions import Blinded
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.controller import HumanController
from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventType, SensoryUpdateEvent, EventPhase, EventQueue
from dnd.core.presentation_geometry import SpherePresentationGeometry, WallAssemblyPresentationGeometry, WallSegment
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import GREASE_ZONE_CONTENT_REF
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from tests.engine.test_senses_light_stealth import PerceptionModifierCondition, create_skeleton, reset_senses_state
from dnd.types.senses import PerceivedSpatialEffect, VolumeSurfaceSight
from dnd.types.spell_suppression import SpellSuppression
from dnd.player.audience import AudiencePerception, PlayerAudience, audience_view, observe_audience, tile_observers
from dnd.player.facts import DamageResultFact, PlayerSequence, SensoryFact
from dnd.player.projection import begin_projection, project_lineage
from dnd.player.reduction import decode_player_sequence, encode_player_sequence, reduce_initialization, reduce_lineage
from dnd.player.capture import capture_interval, capture_lineages


@pytest.mark.parametrize("split", [True, False])
def test_split_party_retains_combat_once_and_replays_without_native_owners(split: bool) -> None:
    reset_engine_runtime()
    battlefield = "battlefield.visibility_doorway_closed" if split else "battlefield.visibility_doorway_open"
    build_battlefield(battlefield)
    game = Game()
    try:
        heroes = [Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes",
                    health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")])))
                  for name, position in (("Fighter", (5, 7) if split else (8, 6)), ("Sorcerer", (8, 7)))]
        enemy = Entity.create(uuid4(), "Enemy in the other room", config=EntityConfig(position=(8, 8), faction="enemies"))
        for actor in (*heroes, enemy):
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        encounter = Encounter(name="Split party", source_entity_uuid=uuid4())
        for actor in (*heroes, enemy):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        encounter.start_encounter()
        first, second = heroes
        assert (enemy.uuid not in first.senses.entities) == split
        if not split:
            assert first.senses.entities[enemy.uuid].visual
        assert second.senses.entities[enemy.uuid].visual
        audience = PlayerAudience(tuple(actor.uuid for actor in heroes), tuple(actor.uuid for actor in heroes))
        initialization = capture_interval(name="split party", start_cursor=0, end_cursor=EventQueue.event_cursor(),
            observer_uuid=first.uuid, audience=audience, battlefield_id=battlefield)
        projection, public_initialization = begin_projection(initialization)
        before = reduce_initialization(public_initialization)
        assert before.senses is not None and before.senses.entities[enemy.uuid].visual
        assert before.senses.visible == {p for actor in heroes for p, visible in actor.senses.visible.items() if visible}
        assert set(before.perception.members) == set(audience.observers)
        assert all(before.actors[actor.uuid].controlled_items is not None for actor in heroes)
        assert before.actors[enemy.uuid].controlled_items is None

        cursor = EventQueue.event_cursor()
        first.receive_damage(1, DamageType.FORCE, source_entity_uuid=first.uuid)
        second.receive_damage(1, DamageType.FORCE, source_entity_uuid=enemy.uuid)
        native = tuple(event for _, event in EventQueue.iter_events_since(cursor)
                       if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        captured = capture_lineages(native, observer_uuid=first.uuid, audience=audience,
            known_actor_uuids=frozenset(before.actors))
        roots = tuple(value for lineage in captured if (value := project_lineage(projection, lineage)) is not None)
        damage = [node for root in roots for node in root.events if isinstance(node.fact, DamageResultFact)]
        assert len(damage) == 2 and len({node.uuid for node in damage}) == 2
        assert {node.fact.target_entity_uuid for node in damage} == set(audience.controlled)
        assert next(node.fact for node in damage if node.fact.target_entity_uuid == second.uuid).source_entity_uuid == enemy.uuid, [(node.fact.source_entity_uuid, node.fact.target_entity_uuid) for node in damage]
        expected = before
        for root in roots:
            expected = reduce_lineage(expected, root)
        cursor = EventQueue.event_cursor()
        second.add_condition(Blinded(source_entity_uuid=second.uuid, target_entity_uuid=second.uuid))
        native = tuple(event for _, event in EventQueue.iter_events_since(cursor)
                       if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
        later = tuple(value for lineage in capture_lineages(native, observer_uuid=first.uuid, audience=audience,
                      known_actor_uuids=frozenset(expected.actors))
                      if (value := project_lineage(projection, lineage)) is not None)
        roots += later
        for root in later:
            expected = reduce_lineage(expected, root)
        assert expected.senses is not None
        assert (enemy.uuid in expected.senses.entities) == (not split), (enemy.uuid in first.senses.entities, enemy.uuid in second.senses.entities, {str(k): (enemy.uuid in v.entities, len(v.visible)) for k, v in expected.perception.members.items()})
        assert before.senses.seen <= expected.senses.seen
        assert expected.actors[second.uuid].normal_hp == second.get_normal_hp()
        payload = encode_player_sequence(PlayerSequence(initialization=public_initialization, lineages=roots))
        game.close()
        reset_engine_runtime()
        replayed, restored = decode_player_sequence(payload)
        for root in restored:
            replayed = reduce_lineage(replayed, root)
        assert replayed == expected
        assert EventQueue.event_cursor() == 0
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("version", (None, 1, 2, 3, 5))
def test_unsupported_public_archive_requires_preserved_native_reprojection(version) -> None:
    reset_engine_runtime()
    battlefield = "battlefield.visibility_doorway_open"
    build_battlefield(battlefield)
    game = Game()
    try:
        actor = Entity.create(uuid4(), "Observer", config=EntityConfig(position=(5, 7)))
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        _, initial = begin_projection(capture_interval(name="singleton", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=actor.uuid, battlefield_id=battlefield))
        raw = json.loads(encode_player_sequence(PlayerSequence(initialization=initial, lineages=())))
        if version is None:
            raw.pop("schema_version")
        else:
            raw["schema_version"] = version
        raw["initialization"].pop("audience")
        cursor = EventQueue.event_cursor()
        with pytest.raises(ValueError, match="reproject the preserved native recording"):
            decode_player_sequence(json.dumps(raw).encode())
        assert EventQueue.event_cursor() == cursor
    finally:
        game.close()
        reset_engine_runtime()


def _sight(observer, cells, effects, *, light=3) -> SensoryFact:
    """A complete detached observation at the public sensory boundary."""
    return SensoryFact(observer_uuid=observer, initial=True, observer_position=(0, 0),
        observer_position_changed=True, effective_light_levels_changed={f"{x},{y}": light for x, y in cells},
        cause_event_uuid=None, visible_cells_added=tuple(cells), visible_cells_removed=(),
        seen_cells_added=tuple(cells), entity_contacts_changed={}, entity_contacts_removed=frozenset(),
        object_contacts_changed={}, object_contacts_removed=frozenset(), sense_modes_changed=True,
        sense_modes=(), passive_perception_changed=True, passive_perception=10, visual_access_changed=True,
        visual_access=1, paths_dirty=False, spatial_effects_changed=effects)


def test_party_effect_memory_respects_new_empty_cells_and_owner_versions() -> None:
    first, second, effect_id = uuid4(), uuid4(), uuid4()
    audience = PlayerAudience((first, second), (first, second))
    effect = PerceivedSpatialEffect(content_ref=GREASE_ZONE_CONTENT_REF, name="Grease", description="Slippery ground",
        owner_revision=1, apparent_presence=True, positions=((1, 0), (2, 0)))
    state = observe_audience(AudiencePerception(), audience, _sight(first, {(1, 0), (2, 0)}, {effect_id: effect}), 1)
    # First hero retains the unseen footprint. Second discovers only one now-empty cell.
    state = observe_audience(state, audience, _sight(first, {(0, 0)}, {effect_id: effect}), 2)
    state = observe_audience(state, audience, _sight(second, {(1, 0)}, {}), 3)
    view = audience_view(state, first)
    assert view is not None and view.spatial_effects[effect_id].positions == ((2, 0),)
    # A changed owner is newer even if a later refresh republishes old hidden memory.
    moved = effect.model_copy(update={"owner_revision": 2, "positions": ((4, 0),),
        "area_geometry": SpherePresentationGeometry(center=(4, 0), radius_feet=5)})
    state = observe_audience(state, audience, _sight(second, {(4, 0)}, {effect_id: moved}), 4)
    state = observe_audience(state, audience, _sight(first, {(0, 0)}, {effect_id: effect}), 5)
    view = audience_view(state, first)
    assert view is not None and view.spatial_effects[effect_id] == moved


def test_party_unions_same_owner_version_from_independent_observations() -> None:
    first, second, effect_id, protection_id = uuid4(), uuid4(), uuid4(), uuid4()
    audience = PlayerAudience((first, second), (first, second))
    effect = PerceivedSpatialEffect(content_ref=GREASE_ZONE_CONTENT_REF, name="Field", description="Field",
        owner_revision=7, positions=((1, 0),),
        upper_volume_surfaces=(VolumeSurfaceSight(position=(3, 0), lower_height_planes=((1, 0, 0),)),),
        suppressions=(SpellSuppression(provider_uuid=protection_id, positions=((1, 0),)),))
    other = effect.model_copy(update={"positions": ((2, 0),),
        "upper_volume_surfaces": (VolumeSurfaceSight(position=(3, 0), lower_height_planes=((-1, 0, 0),)),),
        "suppressions": (SpellSuppression(provider_uuid=protection_id, positions=((2, 0),)),)})
    state = observe_audience(AudiencePerception(), audience, _sight(first, {(1, 0)}, {effect_id: effect}), 1)
    state = observe_audience(state, audience, _sight(second, {(2, 0)}, {effect_id: other}), 10)
    view = audience_view(state, first)
    assert view is not None
    result = view.spatial_effects[effect_id]
    assert result.positions == ((1, 0), (2, 0))
    assert result.suppressions[0].positions == ((1, 0), (2, 0))
    assert len(result.upper_volume_surfaces) == 2
    assert {row.lower_height_planes for row in result.upper_volume_surfaces} == {((1., 0., 0.),), ((-1., 0., 0.),)}


def test_party_light_selects_one_complete_observation_with_stable_provenance() -> None:
    first, second = uuid4(), uuid4()
    audience = PlayerAudience((first, second), (first, second))
    state = observe_audience(AudiencePerception(), audience, _sight(first, {(0, 0), (1, 0)}, {}, light=2), 1)
    state = observe_audience(state, audience, _sight(second, {(1, 0), (2, 0)}, {}, light=3), 2)
    view = audience_view(state, first)
    assert view is not None
    assert view.visible == {(0, 0), (1, 0), (2, 0)}
    assert view.effective_light_levels[(0, 0)].value == 2
    assert view.effective_light_levels[(1, 0)].value == 3
    assert tile_observers(state) == {(0, 0): first, (1, 0): second, (2, 0): second}


def test_party_keeps_discovered_trap_when_companion_cannot_detect_it() -> None:
    reset_senses_state(width=6, height=2)
    try:
        scout = create_skeleton(name="Scout", position=(0, 0))
        witness = create_skeleton(name="Companion", position=(0, 1))
        scout.add_condition(PerceptionModifierCondition(source_entity_uuid=scout.uuid,
            target_entity_uuid=scout.uuid, modifier_amount=10))
        trap = materialize_spike_trap_condition({(3, 0)}, stealth_dc=15)
        assert trap.uuid in scout.senses.spatial_effects
        assert trap.uuid not in witness.senses.spatial_effects
        audience = PlayerAudience((scout.uuid, witness.uuid), (scout.uuid, witness.uuid))
        state, cursor = AudiencePerception(), 0

        def consume():
            nonlocal state, cursor
            for index, event in EventQueue.iter_events_since(cursor):
                if isinstance(event, SensoryUpdateEvent) and audience.observes(event.observer_uuid):
                    state = observe_audience(state, audience, event, index)
            cursor = EventQueue.event_cursor()
            return audience_view(state, scout.uuid)

        view = consume()
        assert view is not None and trap.uuid in view.spatial_effects
        blind = Blinded(source_entity_uuid=scout.uuid, target_entity_uuid=scout.uuid)
        scout.add_condition(blind)
        witness.update_entity_senses(max_distance=20)
        view = consume()
        assert view is not None and view.spatial_effects[trap.uuid].positions == ((3, 0),)
        trap.deactivate(parent_event=Event(source_entity_uuid=scout.uuid,
            event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT))
        scout.remove_condition_by_uuid(blind.uuid)
        view = consume()
        assert view is not None and trap.uuid not in view.spatial_effects
    finally:
        reset_engine_runtime()


def test_party_unions_disclosed_anchor_and_disjoint_construction_sections() -> None:
    first, second, effect_id = uuid4(), uuid4(), uuid4()
    audience = PlayerAudience((first, second), (first, second))
    west = WallAssemblyPresentationGeometry(path=WallSegment(start=(0, 0), end=(2, 0)),
        base_height_steps=0, width_feet=1, height_feet=10)
    east = west.model_copy(update={'path': WallSegment(start=(2, 0), end=(4, 0))})
    effect = PerceivedSpatialEffect(content_ref=GREASE_ZONE_CONTENT_REF, name="Wall", description="Panels",
        owner_revision=7, positions=((0, 0), (1, 0)), anchor_position=(0, 0),
        construction_sections=(west,))
    other = effect.model_copy(update={'positions': ((3, 0),), 'anchor_position': None,
        'construction_sections': (east,)})
    state = observe_audience(AudiencePerception(), audience, _sight(first, {(0, 0), (1, 0)}, {effect_id: effect}), 1)
    state = observe_audience(state, audience, _sight(second, {(3, 0)}, {effect_id: other}), 2)
    view = audience_view(state, first)
    assert view is not None
    observed = view.spatial_effects[effect_id]
    assert observed.positions == ((0, 0), (1, 0), (3, 0))
    assert observed.anchor_position == (0, 0)
    assert set(observed.construction_sections) == {west, east}
