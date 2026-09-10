"""A cast recovers after its native concentration-removal child has finished."""

from dataclasses import replace
import json
from types import MappingProxyType

import pytest

from dnd.conditions import Concentrating
from dnd.core.events import EventType, SavingThrowEvent, TakeDamageEvent
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from game.animation import CastSample, body_clip, sample_cast
from game.animation_data import load_animation_data
from game.animation_types import DamageContext, StudioSpellDraft
from game.choreography import bind_choreography, sample_choreography
from game.combat import BoundCast, bind_cast
from game.combat_demo import iter_combat_demo
from game.condition_types import ConditionRecipe
from game.presentation import CompletedLineage, PresentationTarget, capture_lineage, reduce_lineage


@pytest.fixture(scope="module")
def concentrating_hit() -> tuple[PresentationTarget, CompletedLineage]:
    script = iter_combat_demo()
    try:
        seed = next(script)
        assert isinstance(seed, PresentationTarget)
        recipient = next(actor for actor in seed.actors.values() if actor.name == "Recipient")
        actor = Entity.get(recipient.uuid)
        assert actor is not None
        applied = actor.add_condition(Concentrating(
            source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, spell_name="Existing held spell",
        ))
        assert applied is not None
        before = reduce_lineage(seed, capture_lineage(applied, observer_uuid=seed.observer_uuid))
        lineage = next(script)  # The same discovered Fire Bolt; its native save fails.
        assert isinstance(lineage, CompletedLineage)
        return before, lineage
    finally:
        script.close()
        reset_engine_runtime()


@pytest.mark.parametrize("recovery_enabled", (True, False))
def test_authored_recovery_follows_native_late_child_without_moving_delivery(
    concentrating_hit: tuple[PresentationTarget, CompletedLineage], recovery_enabled: bool,
) -> None:
    before, lineage = concentrating_hit
    data = load_animation_data()
    fact, = lineage.conditions
    assert fact.behavior_id == "condition.concentrating"
    removal = next(event for event in lineage.events if event.uuid == fact.event_uuid)
    assert removal.event_type is EventType.CONDITION_REMOVAL
    save, = (event for event in lineage.events if isinstance(event, SavingThrowEvent))
    assert save.ability_name == "constitution" and save.result is False
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    ancestors = []
    current = removal
    while current.parent_lineage is not None:
        current = by_lineage[current.parent_lineage]
        ancestors.append(current)
    damage, = (event for event in ancestors if isinstance(event, TakeDamageEvent))
    assert ancestors[-1] == lineage.root

    # Only valid original authoring values change. No fabricated on-hit handler,
    # substituted condition type, synthetic child or mechanics replay is involved.
    recipe = data.condition_recipes[fact.behavior_id].model_dump(mode="json")
    recipe["persistent"]["alphaMultiplier"] = .4
    recipe["removal"]["durationMs"] = 2500
    condition = ConditionRecipe.model_validate_json(json.dumps(recipe))
    draft = data.drafts["spell.fire_bolt"].model_dump(mode="json")
    draft["cast"]["recovery"]["enabled"] = recovery_enabled
    draft["condition"] = {"anchor": "effect", "delayMs": 100, "feedbackEnabled": True}
    spell = StudioSpellDraft.model_validate_json(json.dumps(draft))
    context = data.damage_context.model_dump(mode="json")
    context["conditionFrame"] = 3
    authored = replace(data,
        drafts=MappingProxyType({**data.drafts, "spell.fire_bolt": spell}),
        condition_recipes=MappingProxyType({**data.condition_recipes, fact.behavior_id: condition}),
        damage_context=DamageContext.model_validate_json(json.dumps(context)))
    delivery = bind_cast(before, lineage, authored).timeline
    group = bind_choreography(before, lineage, authored)
    node, = group.nodes
    assert node.event_uuid == lineage.root.uuid and isinstance(node.bound, BoundCast)
    joined = node.bound.timeline
    transition, = group.conditions
    application, = delivery.applications
    assert application.damage_start_ms is not None and application.hp_ms is not None
    target = application.source.target
    hit_clip = body_clip(authored, target, authored.damage_context.bodyClip)
    assert transition.event_uuid == removal.uuid and transition.target_uuid == damage.target_entity_uuid
    assert transition.start_ms == pytest.approx(application.damage_start_ms +
        3 * 1000 / (hit_clip.fps * authored.damage_context.bodyPlaybackSpeed) + 100)
    assert transition.complete_ms > delivery.complete_ms
    assert joined.release_ms == delivery.release_ms
    assert joined.applications == delivery.applications
    assert tuple(anchor for anchor in joined.anchors if anchor.name not in ("recover", "complete")) == tuple(
        anchor for anchor in delivery.anchors if anchor.name not in ("recover", "complete"))
    assert group.after == reduce_lineage(before, lineage)

    # At the old recovery window, the cast waits while the child fades. Actual
    # HP is already visible and membership is removed at the child anchor.
    waiting_at = transition.complete_ms - 1
    waiting = sample_choreography(group, waiting_at)
    clip, = waiting.clips
    assert isinstance(clip.sample, CastSample)
    caster = joined.source.caster.actor_uuid
    assert next(body for body in clip.sample.bodies if body.actor_uuid == caster).clip == "Idle"
    assert not waiting.complete and not waiting.displayed.actors[transition.target_uuid].conditions
    assert waiting.vitals[0].hp == application.source.resulting_hp
    assert .4 < waiting.conditions[0].appearance.alpha < 1
    assert sample_cast(joined, application.hp_ms).vitals == sample_cast(delivery, application.hp_ms).vitals
    at_join = sample_choreography(group, transition.complete_ms)
    joined_clip, = at_join.clips
    assert isinstance(joined_clip.sample, CastSample)
    body = next(body for body in joined_clip.sample.bodies if body.actor_uuid == caster)
    if recovery_enabled:
        assert body.clip == spell.cast.recovery.bodyClip and body.frame == 0
        assert not at_join.complete
    else:
        assert body.clip == "Idle" and at_join.complete
    assert joined.recovery_start_ms == transition.complete_ms
    done = sample_choreography(group, group.complete_ms)
    assert done.complete
    assert sample_choreography(group, waiting_at) == waiting
