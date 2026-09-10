"""Legal casts and equipment on the map, with independent intake and playback.

The finite input script owns command times. Completed lineages enter one pending
deque; the active authored sampler reads only its historical input. The old
game.app.run remains the door/light regression demonstration.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

import pygame

from dnd.actions import SpellEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.equipment import WeaponEquipEvent, WeaponUnequipEvent
from dnd.runtime_reset import reset_engine_runtime
from game.animation import (
    BodySample, CastSample, CastTimeline, EquipmentSample, EquipmentTimeline, VitalsSample,
    crossed_anchors, sample_cast, sample_equipment, sample_idle_body,
)
from game.animation_data import load_animation_data
from game.animation_draw import (
    AnimationMedia, BodyRows, actor_draw_commands, animation_draw_commands,
    load_actor_media, load_animation_media,
)
from game.animation_types import RigLayer
from game.app import BACKGROUND, WINDOW_SIZE, draw_frame
from game.assets import SurfaceCache, load_catalog
from game.combat import BoundCast, BoundEquipment, bind_cast, bind_equipment
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget, reduce_lineage
from game.projection import Camera, ZOOM_LEVELS


@dataclass(frozen=True, slots=True)
class PlaybackFrame:
    """Evidence retained after this historical sample was drawn and flipped."""

    cast_number: int
    input_ms: float
    elapsed_ms: float
    latest_vitals: tuple[VitalsSample, ...]
    reduced_casts: int
    completed_casts: int
    sample: CastSample
    appearances: Mapping[str, tuple[RigLayer, ...]]
    latest_equipment: tuple[tuple[str, UUID], ...]


@dataclass(frozen=True, slots=True)
class EquipmentPlaybackFrame:
    """The actual gear/body choice published by the equipment head."""

    root_event_uuid: str
    input_ms: float
    elapsed_ms: float
    sample: EquipmentSample
    bodies: tuple[BodySample, ...]
    appearances: Mapping[str, tuple[RigLayer, ...]]
    latest_equipment: tuple[tuple[str, UUID], ...]


@dataclass(frozen=True, slots=True)
class PlaybackSummary:
    timelines: tuple[CastTimeline, ...]
    frames: tuple[PlaybackFrame, ...]
    completed_casts: int
    latest: PresentationTarget
    historical: PresentationTarget
    equipment_timelines: tuple[EquipmentTimeline, ...]
    equipment_frames: tuple[EquipmentPlaybackFrame, ...]
    completed_lineages: int


def _draw_status(
    screen: pygame.Surface,
    font: pygame.font.Font,
    *,
    title: str,
    vitals_text: str,
    complete: bool,
    paused: bool,
    completed_log: str,
) -> None:
    state = "Complete" if complete else "Paused" if paused else "Playing"
    lines = (
        f"{title}  ·  {state}",
        vitals_text,
        re.sub(r"\{[a-z ]+:([^{}]*)\}", r"\1", completed_log),
        "Space pause · Q/E rotate · WASD pan · wheel zoom · G grid · F3 details · Esc close",
    )
    panel = pygame.Surface((screen.width, 105), pygame.SRCALPHA)
    panel.fill((10, 12, 18, 220))
    for index, text in enumerate(lines):
        panel.blit(font.render(text, True, (234, 233, 222)), (18, 9 + index * 23))
    screen.blit(panel, (0, screen.height - panel.height))


async def _run(
    *,
    frame_deltas: Sequence[float] | None,
    frame_events: Mapping[int, Sequence[pygame.event.Event]],
    max_frames: int | None,
    window_size: tuple[int, int],
    quadrant: int,
    exit_when_complete: bool,
    capture_dir: Path | None,
    miss_second: bool,
    goblin_recipient: bool,
    lethal_second: bool,
    replace_weapon: bool,
    magic_missile: bool,
) -> PlaybackSummary:
    pygame.init()
    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("D&D Engine — Authored spells on the map")
    screen.fill(BACKGROUND)
    pygame.display.flip()
    goblin_recipient = goblin_recipient or lethal_second
    script = iter_combat_demo(
        second_attack_seed=17 if lethal_second else 1 if miss_second or goblin_recipient else 0,
        goblin_recipient=goblin_recipient,
        replace_weapon=replace_weapon,
        magic_missile=magic_missile,
    )
    try:
        seed = next(script)
        if not isinstance(seed, PresentationTarget):
            raise RuntimeError("combat script must first establish its presentation baseline")
        latest = historical = seed
        catalog = load_catalog()
        rig_files = (Path(__file__).parent / "data" / "rigs" / "goblin01.json",) if goblin_recipient else ()
        data = load_animation_data(rig_files=rig_files)
        cache = SurfaceCache(catalog)
        positions = tuple(seed.senses.entities.values()) if seed.senses is not None else ()
        if seed.senses is None or not positions:
            raise RuntimeError("combat demonstration requires its retained observer/contacts")
        start = seed.senses.position
        end = (sum(contact.position[0] for contact in positions) / len(positions),
               sum(contact.position[1] for contact in positions) / len(positions))
        focus = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        camera = Camera(quadrant=quadrant, zoom=0.75, viewport=window_size).with_focus(focus)
        pending: deque[CompletedLineage] = deque()
        active: BoundCast | BoundEquipment | None = None
        shown: BoundCast | BoundEquipment | None = None
        cast_media: AnimationMedia | None = None
        equipment_media: BodyRows | None = None
        timelines: list[CastTimeline] = []
        published: list[PlaybackFrame] = []
        equipment_timelines: list[EquipmentTimeline] = []
        equipment_frames: list[EquipmentPlaybackFrame] = []
        displayed_bodies: tuple[BodySample, ...] = ()
        input_ms = elapsed_ms = 0.0
        previous_ms = -1.0
        issued = completed = frame = 0
        reduced_casts = completed_lineages = 0
        # The four middle deliveries are separate roots of one equip_item
        # command. Input times do not group them into a synthetic lineage.
        deadlines = (0, 1000, 1000, 1000, 1000, 1500) if replace_weapon else (0, 1000)
        recipient_uuids = tuple(actor for actor in seed.actors if actor != seed.observer_uuid)
        paused = show_grid = show_debug = False
        running = True
        current_log = completed_log = ""
        clock = pygame.time.Clock()
        if capture_dir is not None:
            capture_dir.mkdir(parents=True, exist_ok=True)
        while running and (max_frames is None or frame < max_frames):
            for event in frame_events.get(frame, ()):
                pygame.event.post(event)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_g:
                        show_grid = not show_grid
                    elif event.key == pygame.K_F3:
                        show_debug = not show_debug
                    elif event.key in (pygame.K_q, pygame.K_e):
                        camera = camera.quarter_turned(-1 if event.key == pygame.K_q else 1)
                elif event.type == pygame.MOUSEWHEEL:
                    zoom_index = max(0, min(len(ZOOM_LEVELS) - 1,
                                           ZOOM_LEVELS.index(camera.zoom) + event.y))
                    camera = camera.with_zoom_at(ZOOM_LEVELS[zoom_index], pygame.mouse.get_pos())
            if not running:
                break
            delta = (clock.tick(60) / 1000 if frame_deltas is None
                     else frame_deltas[min(frame, len(frame_deltas) - 1)])
            input_ms += delta * 1000
            keys = pygame.key.get_pressed()
            camera = camera.with_screen_pan((
                (keys[pygame.K_a] - keys[pygame.K_d]) * 320 * delta,
                (keys[pygame.K_w] - keys[pygame.K_s]) * 320 * delta,
            ))

            # These are input-script deadlines, independent of the active
            # timeline, pause state, queue length or display completion.
            while issued < len(deadlines) and input_ms >= deadlines[issued]:
                lineage = next(script)
                if not isinstance(lineage, CompletedLineage):
                    raise RuntimeError("combat input must produce its completed lineage")
                latest = reduce_lineage(latest, lineage)
                pending.append(lineage)
                issued += 1
                if isinstance(lineage.root, SpellEvent):
                    reduced_casts += 1
                await asyncio.sleep(0)

            started = False
            while active is None and pending:
                lineage = pending.popleft()
                match lineage.root:
                    case SpellEvent():
                        # Explicit terrace geometry; original recipe/time stays intact.
                        active = bind_cast(historical, lineage, data, travel_apex_steps=1.0)
                        timelines.append(active.timeline)
                        cast_media = load_animation_media(active.timeline, active.appearances)
                        equipment_media = None
                    case ItemLocationStateEvent():
                        active = bind_equipment(
                            historical, lineage, data,
                            {body.actor_uuid: body.facing for body in displayed_bodies},
                        )
                        if active is not None:
                            equipment_timelines.append(active.timeline)
                            actor_id = active.timeline.actor.actor_uuid
                            equipment_media = load_actor_media(data, (
                                *((contact, active.appearances[identity],
                                   ("Idle", active.timeline.recipe.bodyClip) if identity == actor_id
                                   else ("Idle", data.death_context.bodyClip))
                                  for identity, contact in active.contacts.items()),
                                (active.timeline.actor, active.replacement, ("Idle",)),
                            ))
                            cast_media = None
                    case WeaponEquipEvent() | WeaponUnequipEvent():
                        pass
                    case _:
                        raise NotImplementedError("the selected playback has no binding for this root")
                if active is None:
                    historical = reduce_lineage(historical, lineage)
                    completed_lineages += 1
                    continue
                current_log = lineage.root.combat_log.compact if lineage.root.combat_log is not None else ""
                clock.tick()
                elapsed_ms, previous_ms = 0.0, -1.0
                shown = active
                started = True
            if not started and not paused:
                elapsed_ms += delta * 1000

            match shown:
                case BoundCast():
                    assert cast_media is not None
                    sample = sample_cast(shown.timeline, elapsed_ms)
                    displayed_bodies = sample.bodies
                    appearances = shown.appearances
                    commands = animation_draw_commands(shown.timeline, sample, cast_media, camera)
                    vitals = sample.vitals
                    title = f"{'Magic Missile' if magic_missile else 'Fire Bolt'}  ·  Cast {len(timelines)}/2"
                case BoundEquipment():
                    assert equipment_media is not None
                    sample = sample_equipment(shown.timeline, elapsed_ms)
                    actor_id = shown.timeline.actor.actor_uuid
                    appearances = MappingProxyType({
                        **shown.appearances,
                        actor_id: shown.replacement if sample.complete else shown.appearances[actor_id],
                    })
                    displayed_bodies = tuple(
                        sample.body if identity == actor_id else sample_idle_body(data, contact, elapsed_ms)
                        for identity, contact in shown.contacts.items()
                    )
                    commands = tuple(command for body in displayed_bodies for command in actor_draw_commands(
                        data, body, shown.contacts[body.actor_uuid], appearances[body.actor_uuid],
                        equipment_media, camera,
                    ))
                    vitals = tuple(VitalsSample(
                        str(identity), historical.actors[identity].normal_hp,
                        historical.actors[identity].life_state, None,
                    ) for identity in recipient_uuids)
                    title = "Replace dagger with shortsword"
                case _:
                    raise RuntimeError("first combat input did not provide a drawable history")
            evidence = draw_frame(
                screen, historical, catalog, cache, camera, input_ms / 1000,
                show_grid=show_grid, show_debug=show_debug,
                mouse_position=pygame.mouse.get_pos() if show_debug else None,
                extra_commands=commands,
                revisions=(latest.reducer_cursor, latest.reducer_cursor, historical.reducer_cursor),
            )
            if not evidence.matches:
                raise RuntimeError("map draw evidence differs from the published candidates")
            _draw_status(
                screen, cache.debug_font, title=title,
                vitals_text="  ·  ".join(
                    f"{historical.actors[UUID(vital.actor_uuid)].name} HP {vital.hp} · {vital.life_state.value.capitalize()}"
                    for vital in vitals
                ),
                complete=len(timelines) == 2 and sample.complete, paused=paused,
                completed_log=current_log if sample.complete else completed_log,
            )
            pygame.display.flip()

            if active is not None:
                if capture_dir is not None and isinstance(active, BoundCast):
                    for anchor in crossed_anchors(active.timeline, previous_ms, elapsed_ms):
                        if anchor.name in {"release", "impact", "vitals", "complete"}:
                            suffix = ""
                            if len(active.timeline.applications) > 1 and anchor.application_id is not None:
                                index = next(index for index, application in enumerate(active.timeline.applications)
                                             if application.source.application_id == anchor.application_id)
                                suffix = f"-application-{index + 1}"
                            pygame.image.save(screen, capture_dir / f"cast-{len(timelines)}-{anchor.name}{suffix}.png")
                elif capture_dir is not None and (started or sample.complete):
                    pygame.image.save(screen, capture_dir / f"equipment-{'complete' if sample.complete else 'start'}.png")
                previous_ms = elapsed_ms
                if sample.complete:
                    historical = active.after
                    completed_log = current_log
                    completed_lineages += 1
                    if isinstance(active, BoundCast):
                        completed += 1
                    active = None
                latest_equipment = latest.actors[latest.observer_uuid].equipment
                match sample:
                    case CastSample():
                        published.append(PlaybackFrame(
                            len(timelines), input_ms, elapsed_ms,
                            tuple(VitalsSample(str(identity), latest.actors[identity].normal_hp,
                                               latest.actors[identity].life_state, None)
                                  for identity in recipient_uuids),
                            reduced_casts, completed, sample, appearances, latest_equipment,
                        ))
                    case EquipmentSample():
                        equipment_frames.append(EquipmentPlaybackFrame(
                            equipment_timelines[-1].root_event_uuid, input_ms, elapsed_ms,
                            sample, displayed_bodies, appearances, latest_equipment,
                        ))
            frame += 1
            if completed == 2 and exit_when_complete:
                break
            await asyncio.sleep(0)
        if running and completed < 2:
            raise RuntimeError("frame limit reached before both historical casts completed")
        return PlaybackSummary(
            tuple(timelines), tuple(published), completed, latest, historical,
            tuple(equipment_timelines), tuple(equipment_frames), completed_lineages,
        )
    finally:
        script.close()
        pygame.quit()
        reset_engine_runtime()


def run(
    *,
    frame_deltas: Sequence[float] | None = None,
    frame_events: Mapping[int, Sequence[pygame.event.Event]] | None = None,
    max_frames: int | None = None,
    window_size: tuple[int, int] = WINDOW_SIZE,
    quadrant: int = 0,
    exit_when_complete: bool = False,
    capture_dir: Path | None = None,
    miss_second: bool = False,
    goblin_recipient: bool = False,
    lethal_second: bool = False,
    replace_weapon: bool = False,
    magic_missile: bool = False,
) -> PlaybackSummary:
    """Use the same real frame loop for interactive play and deterministic proof.

    The composition entry installs the engine content system before this call.
    Tests supply frame deltas and SDL input events, keeping normal input/reduce/
    sample/draw/flip ownership intact.
    """
    if frame_deltas is not None and (not frame_deltas or any(delta <= 0 for delta in frame_deltas)):
        raise ValueError("deterministic frame deltas must be positive")
    if miss_second and lethal_second:
        raise ValueError("the second scripted cast cannot be both a miss and lethal")
    if magic_missile and (miss_second or lethal_second or goblin_recipient):
        raise ValueError("the selected Magic Missile script uses two living modular targets")
    return asyncio.run(_run(
        frame_deltas=frame_deltas, frame_events=frame_events or {},
        max_frames=max_frames, window_size=window_size, quadrant=quadrant,
        exit_when_complete=exit_when_complete, capture_dir=capture_dir,
        miss_second=miss_second,
        goblin_recipient=goblin_recipient,
        lethal_second=lethal_second,
        replace_weapon=replace_weapon,
        magic_missile=magic_missile,
    ))
