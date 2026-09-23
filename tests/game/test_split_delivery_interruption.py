"""A countered volley stops before its nearest projectile can arrive."""

from uuid import UUID

from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.combat import BoundCast
from game.interruption import interrupt_delivery, interrupt_sample, interruption_ms
from game.player_facts import PlayerState, PlayerWorld


def test_split_magic_missile_interrupts_before_every_target_contact() -> None:
    data = load_animation_data()
    caster = ActorContact(actor_uuid="caster", grid=(2, 2), facing="E", hp=100, visual_scale=1)
    far = ActorContact(actor_uuid="far", grid=(22, 2), facing="W", hp=100, visual_scale=1)
    near = ActorContact(actor_uuid="near", grid=(3, 2), facing="W", hp=100, visual_scale=1)
    applications = tuple(CastApplication(application_id=str(index), target=target,
        damage_applied=False, damage_total=None, resulting_hp=None)
        for index, target in enumerate((far, near, near)))
    timeline = compile_cast(data, "spell.magic_missile", CastInput("attempt", caster, applications))
    after = PlayerState(
        generation=UUID(int=1),
        observer_uuid=UUID(int=2),
        world=PlayerWorld(battlefield_id="split-volley", battlefield_name="Split volley",
                          bounds=(0, 0, 24, 4), width=25, height=5),
    )
    bound = BoundCast(timeline, after, {})
    rule = next(row for row in data.interruptions.rules
                if row.actionEconomySpent and "execution" in row.phases)
    cutoff = interruption_ms(bound, rule)
    # Declaration order is not arrival order: the second missile arrives first.
    assert timeline.applications[1].travel_end_ms < timeline.applications[0].travel_end_ms
    assert any(delivery.travel_start_ms < cutoff for delivery in timeline.applications)
    assert all(cutoff < delivery.travel_end_ms for delivery in timeline.applications)
    interrupted = interrupt_delivery(bound, rule)
    assert isinstance(interrupted, BoundCast)
    assert interrupted.timeline.complete_ms == cutoff
    for elapsed in (0., timeline.release_ms, cutoff / 2, cutoff - .001):
        sample = interrupt_sample(sample_cast(interrupted.timeline, elapsed), caster.actor_uuid)
        assert not sample.numbers and not sample.vitals
        assert all(projectile.phase != "impact" and projectile.progress < 1
                   for projectile in sample.projectiles)
