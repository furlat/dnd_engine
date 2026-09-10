"""Retained body lift moves actual attachments without moving their support."""

from dataclasses import replace
from pathlib import Path
from typing import Iterator, Mapping

import pygame
import pytest

from dnd.actions import AttackEvent
from dnd.core.equipment_types import WeaponSlot
from game.animation import (
    ActorContact, GeometryProjectileSample, ProjectileSample, project_geometry_projectile,
    project_projectile, projectile_contact, sample_cast, sample_idle_body,
)
from game.animation_data import load_animation_data
from game.animation_draw import (
    actor_draw_commands, load_actor_media, number_draw_commands,
)
from game.animation_types import AnimationData
from game.attack import BoundAttack, attack_projectile_contact, bind_attack, project_attack_projectile, sample_attack
from game.combat import BoundCast, actor_contact, bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget
from game.projection import Camera, HEIGHT_STEP_PIXELS, TILE_WIDTH
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(authored_bundles=(), rig_files=(Path("game/data/rigs/goblin01.json"),))


@pytest.fixture(scope="module")
def histories() -> dict[str, tuple[PresentationTarget, CompletedLineage]]:
    result = {"shortbow": attack_history("weapon.shortbow", 17, weapon_slot=WeaponSlot.RANGED_MAIN,
                                        watcher_positions=((7, 3),))}
    for name, missile in (("firebolt", False), ("missile", True)):
        script = iter_combat_demo(magic_missile=missile)
        try:
            before, lineage = next(script), next(script)
            assert isinstance(before, PresentationTarget) and isinstance(lineage, CompletedLineage)
            result[name] = before, lineage
        finally:
            script.close()
    return result


def bind_history(before: PresentationTarget, lineage: CompletedLineage, data: AnimationData,
                 contacts: Mapping[str, ActorContact]) -> BoundAttack | BoundCast:
    if isinstance(lineage.root, AttackEvent):
        bound = bind_attack(before, lineage, data, contacts=contacts)
        assert bound is not None
        return bound
    return bind_cast(before, lineage, data, contacts=contacts)


def projected_travel(bound: BoundAttack | BoundCast, progress: float, quadrant: int):
    if isinstance(bound, BoundAttack):
        timeline = bound.timeline
        assert timeline.projectile is not None
        start, end = timeline.projectile.start_ms, timeline.projectile.end_ms
        effect = sample_attack(timeline, start + (end - start) * progress).projectiles[0]
        projected = project_attack_projectile(timeline, effect, quadrant)
        contact = attack_projectile_contact(timeline, projected, quadrant)
    else:
        timeline = bound.timeline
        application = timeline.applications[0]
        start, end = application.travel_start_ms, application.travel_end_ms
        effect = next(effect for effect in sample_cast(timeline, start + (end - start) * progress).projectiles
                      if effect.application_id == application.source.application_id and effect.phase == "travel")
        projected = (project_geometry_projectile(timeline, effect, quadrant)
                     if isinstance(effect, GeometryProjectileSample) else project_projectile(timeline, effect, quadrant))
        contact = projectile_contact(timeline, projected, quadrant=quadrant)
    return projected, contact, (start, end)


@pytest.mark.parametrize("kind", ("firebolt", "missile", "shortbow"))
@pytest.mark.parametrize("quadrant", range(4))
def test_real_projectiles_follow_body_height_without_planar_drift_or_double_lift(
    data: AnimationData, histories: dict[str, tuple[PresentationTarget, CompletedLineage]],
    kind: str, quadrant: int,
) -> None:
    before, lineage = histories[kind]
    contacts = {str(actor.uuid): actor_contact(before, actor, data) for actor in before.actors.values()}
    baseline = bind_history(before, lineage, data, contacts)
    for uniform in (True, False):
        lifted = {identity: replace(contact, body_lift_px=24.0 if uniform else 12.0 * (index + 1))
                  for index, (identity, contact) in enumerate(contacts.items())}
        # The existing support-height contract is an independent geometry oracle.
        equivalent = {identity: replace(contact, body_lift_px=0,
            elevation_steps=contact.elevation_steps + contact.body_lift_px * TILE_WIDTH / data.rig.TILE_W / HEIGHT_STEP_PIXELS)
            for identity, contact in lifted.items()}
        bound = bind_history(before, lineage, data, lifted)
        raised_support = bind_history(before, lineage, data, equivalent)
        assert bound.after == baseline.after == raised_support.after
        assert all(contact.elevation_steps == contacts[identity].elevation_steps for identity, contact in lifted.items())
        for progress in (0.0, .5, .999):
            effect, (ground, height), clock = projected_travel(bound, progress, quadrant)
            expected, (expected_ground, expected_height), expected_clock = projected_travel(raised_support, progress, quadrant)
            assert effect.point == pytest.approx(expected.point)
            assert ground == pytest.approx(expected_ground) and height == pytest.approx(expected_height)
            assert clock == pytest.approx(expected_clock)
            if uniform:
                original, (original_ground, original_height), original_clock = projected_travel(baseline, progress, quadrant)
                assert effect.point == pytest.approx((original.point[0], original.point[1] - 24))
                assert ground == pytest.approx(original_ground)
                assert height - original_height == pytest.approx(24 * TILE_WIDTH / data.rig.TILE_W / HEIGHT_STEP_PIXELS)
                assert clock == pytest.approx(original_clock)
            if isinstance(effect, ProjectileSample):
                assert isinstance(expected, ProjectileSample)
                assert effect.rotation_radians == pytest.approx(expected.rotation_radians)


@pytest.fixture(scope="module")
def display() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((960, 720))
        try:
            yield
        finally:
            pygame.quit()


@pytest.mark.parametrize("quadrant", range(4))
def test_body_and_number_rise_once_while_shadow_stays_on_actual_support(
    data: AnimationData, histories: dict[str, tuple[PresentationTarget, CompletedLineage]],
    display: None, quadrant: int,
) -> None:
    before, lineage = histories["shortbow"]
    bound = bind_attack(before, lineage, data)
    assert bound is not None
    contact = bound.timeline.target
    layers = bound.appearances[contact.actor_uuid]
    media = load_actor_media(data, ((contact, layers, ("Idle",)),))
    lifted = replace(contact, body_lift_px=24)
    camera = Camera(quadrant=quadrant, zoom=1, viewport=(960, 720)).with_focus(contact.grid)
    body = sample_idle_body(data, contact, 0)
    original = {command[4][6]: command for command in actor_draw_commands(data, body, contact, layers, media, camera)}
    raised = {command[4][6]: command for command in actor_draw_commands(data, body, lifted, layers, media, camera)}
    pixels = 24 * TILE_WIDTH / data.rig.TILE_W * camera.zoom
    for role in ("actor", "actor_shadow"):
        old, new = original[role], raised[role]
        assert pygame.image.tobytes(old[1], "RGBA") == pygame.image.tobytes(new[1], "RGBA")
        assert new[2] == (old[2][0], old[2][1] - (round(pixels) if role == "actor" else 0))
        assert new[4][7] == pytest.approx(contact.elevation_steps + (pixels / HEIGHT_STEP_PIXELS if role == "actor" else 0))
        if role == "actor_shadow":
            assert new[0] == old[0]
    number = sample_attack(bound.timeline, bound.timeline.contact_ms).numbers[0]
    font = pygame.font.Font(None, 16)
    old, = number_draw_commands(data, (number,), {contact.actor_uuid: contact}, font, camera)
    new, = number_draw_commands(data, (number,), {contact.actor_uuid: lifted}, font, camera)
    assert new[2] == (old[2][0], old[2][1] - round(pixels))
    assert pygame.image.tobytes(old[1], "RGBA") == pygame.image.tobytes(new[1], "RGBA")
