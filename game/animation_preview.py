"""Run the detached Fire Bolt reference through Python and Pygame.

    python -m game.animation_preview
    python -m game.animation_preview --cast-speed 2 --playback-rate 0.5
    python -m game.animation_preview --recovery
    python -m game.animation_preview --target-rig smallscale.goblin01 --lethal
    python -m game.animation_preview --target-height-steps 1 --quadrant 1
    python -m game.animation_preview --headless --at-ms 1900 --capture /tmp/fire.png

Space pauses/resumes; R replays; arrows seek 100 ms and pause; Q/E rotate the
camera. Click the timeline to scrub. --near changes the target contact; --collapsed
uses distinct raised contacts whose support projections coincide in quadrant 0.
--lethal supplies an explicit dead
fact. --recovery enables the existing Taunt recipe without changing saved JSON.
Captures and headless runs render one frame and exit. No live game runs.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from math import isfinite
import os
from pathlib import Path
from types import MappingProxyType

import pygame

from dnd.core.life_types import LifeState
from game.animation import ActorContact, CastApplication, CastInput, CastTimeline, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import AnimationMedia, RigLayer, draw_animation, load_animation_media
from game.animation_types import StudioSpellDraft
from game.projection import Camera, project_screen


SIZE = (1000, 860)
TIMELINE_RECT = pygame.Rect(144, 658, 812, 120)
APPEARANCE = tuple(RigLayer(slot, category, alpha=0.5 if slot == "shadow" else 1) for slot, category in (
    ("body", "NakedBody"), ("head", "Head22"), ("helmet", "Head15"),
    ("chest", "Chest14"), ("legs", "Legs1"), ("belt", "Belt2"),
    ("shoes", "Shoes1"), ("shadow", "Shadow"), ("weapon", "Melee1"),
))
GOBLIN_APPEARANCE = (RigLayer("body", "Goblin01"), RigLayer("shadow", "Goblin01Shadow", alpha=0.5))
GOBLIN_BINDING = Path(__file__).resolve().parent / "data" / "rigs" / "goblin01.json"


def _reference(cast_speed: int, near: bool, lethal: bool, recovery: bool,
               target_height: int = 0, collapsed: bool = False,
               target_rig: str = "neuroclient.modular") -> CastTimeline:
    data = load_animation_data(rig_files=() if target_rig == "neuroclient.modular" else (GOBLIN_BINDING,))
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["cast"]["bodyPlaybackSpeed"] = cast_speed
    document["cast"]["recovery"]["enabled"] = recovery
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(data, drafts=MappingProxyType({**data.drafts, "spell.fire_bolt": draft}))
    source = CastInput(
        root_event_uuid="detached-fire-bolt-reference",
        caster=ActorContact("caster", (0, 0), "S", 0.5),
        applications=(CastApplication(
            application_id="reference-application-1",
            target=ActorContact("target", (1, 1) if collapsed else (1, -1) if near else (3, -3),
                            "W", 0.5, hp=20, elevation_steps=1 if collapsed else target_height,
                            rig_id=target_rig),
            damage_applied=True, damage_total=7, resulting_hp=0 if lethal else 13,
            resulting_life_state=LifeState.DEAD if lethal else None,
        ),),
    )
    return compile_cast(data, "spell.fire_bolt", source)


def _draw(surface: pygame.Surface, timeline: CastTimeline, media: AnimationMedia,
          camera: Camera, elapsed: float, playing: bool, rate: float,
          fonts: tuple[pygame.font.Font, ...]) -> None:
    title_font, text_font, small_font = fonts
    surface.fill((13, 17, 25))
    surface.blit(small_font.render("PYGAME  /  AUTHORING REFERENCE", True, (136, 157, 185)), (40, 26))
    surface.blit(title_font.render("Fire Bolt", True, (242, 235, 216)), (40, 49))
    surface.blit(text_font.render("Detached cast · original NeuroStudio recipe", True, (153, 164, 179)), (40, 90))
    status = "Complete" if elapsed >= timeline.complete_ms else "Playing" if playing else "Paused"
    surface.blit(text_font.render(f"{status}  ·  {elapsed:.0f} ms  ·  {rate:g}× playback", True, (234, 191, 109)), (614, 63))
    height = timeline.source.applications[0].target.elevation_steps * 5
    surface.blit(small_font.render(f"Camera {camera.quadrant}  ·  target support {height:+d} ft", True,
                                   (153, 164, 179)), (614, 99))

    stage_clip = surface.get_clip()
    surface.set_clip((24, 133, 952, 448))
    for x in range(-2, 6):
        for y in range(-5, 3):
            corners = [project_screen((x + dx, y + dy), camera)
                       for dx, dy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
            pygame.draw.polygon(surface, (24, 31, 41) if (x + y) % 2 else (27, 35, 46), corners)
            pygame.draw.polygon(surface, (39, 48, 60), corners, 1)
    for contact in (timeline.source.caster, timeline.source.applications[0].target):
        if contact.elevation_steps:
            base = project_screen(contact.grid, camera)
            support = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
            corners = [project_screen((contact.grid[0] + dx, contact.grid[1] + dy), camera,
                                       elevation_steps=contact.elevation_steps)
                       for dx, dy in ((-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5))]
            # Transparent support markers prove contact placement; this stage
            # deliberately has no opaque terrain/occlusion claim.
            pygame.draw.line(surface, (100, 144, 131), base, support, 1)
            pygame.draw.polygon(surface, (108, 180, 149), corners, 2)
    sample = sample_cast(timeline, elapsed)
    draw_animation(surface, timeline, sample, media, camera)
    surface.set_clip(stage_clip)
    caster, target = timeline.source.caster, timeline.source.applications[0].target
    labels = (f"Caster at {caster.grid}",
              f"Target · {target.rig_id} · HP {sample.vitals[0].hp} · {sample.vitals[0].life_state.value}")
    for x, label in zip((40, 500), labels):
        surface.blit(small_font.render(label, True, (182, 191, 204)), (x, 598))

    surface.blit(text_font.render("Authored timeline", True, (226, 231, 238)), (40, 624))
    end = timeline.complete_ms
    lanes = [("Cast body", 0.0, timeline.body_end_ms, (90, 133, 168))]
    lanes.extend((phase.name.capitalize(), phase.start_ms, phase.end_ms, (198, 126, 58))
                 for phase in timeline.applications[0].projectile_intervals)
    if timeline.applications[0].damage_start_ms is not None and timeline.applications[0].damage_end_ms is not None:
        lanes.append(("Target body", timeline.applications[0].damage_start_ms, timeline.applications[0].damage_end_ms, (152, 96, 106)))
    if timeline.recipe.cast.recovery.enabled:
        lanes.append(("Recovery", timeline.recovery_start_ms, timeline.complete_ms, (103, 153, 133)))
    for index, (label, start, finish, color) in enumerate(lanes):
        y = TIMELINE_RECT.y + index * 20
        surface.blit(small_font.render(label, True, (158, 173, 190)), (40, y))
        pygame.draw.rect(surface, (33, 42, 55), (TIMELINE_RECT.x, y + 2, TIMELINE_RECT.width, 12), border_radius=3)
        pygame.draw.rect(surface, color, (TIMELINE_RECT.x + start / end * TIMELINE_RECT.width, y + 2,
                                         max(2, (finish - start) / end * TIMELINE_RECT.width), 12), border_radius=3)
    cursor_x = TIMELINE_RECT.x + min(1, elapsed / end) * TIMELINE_RECT.width
    pygame.draw.line(surface, (255, 224, 151), (cursor_x, TIMELINE_RECT.y - 4), (cursor_x, TIMELINE_RECT.bottom), 2)
    anchors = "   ·   ".join(f"{anchor.name} {anchor.at_ms:.0f}" for anchor in timeline.anchors
                            if anchor.name not in {"action_start", "travel"})
    surface.blit(small_font.render(anchors + " ms", True, (173, 185, 202)), (40, 789))
    controls = "SPACE pause / play     R replay     ← → seek     Q/E rotate     Click timeline to scrub     ESC close"
    surface.blit(small_font.render(controls, True, (116, 133, 155)), (40, 826))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cast-speed", type=int, choices=(1, 2), default=1)
    parser.add_argument("--playback-rate", type=float, default=1)
    parser.add_argument("--at-ms", type=float)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--headless", action="store_true")
    layout = parser.add_mutually_exclusive_group()
    layout.add_argument("--near", action="store_true")
    layout.add_argument("--collapsed", action="store_true")
    parser.add_argument("--target-height-steps", type=int, default=0, help="Target support in 5ft steps")
    parser.add_argument("--target-rig", choices=("neuroclient.modular", "smallscale.goblin01"),
                        default="neuroclient.modular", help="Explicit recipient rig for this reference")
    parser.add_argument("--quadrant", type=int, choices=range(4), default=0)
    parser.add_argument("--lethal", action="store_true")
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args(argv)
    if not isfinite(args.playback_rate) or args.playback_rate <= 0:
        parser.error("--playback-rate must be finite and positive")
    if args.at_ms is not None and (not isfinite(args.at_ms) or args.at_ms < 0):
        parser.error("--at-ms must be finite and nonnegative")
    if args.collapsed and args.target_height_steps != 0:
        parser.error("--collapsed already selects target support +5ft")
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    timeline = _reference(args.cast_speed, args.near, args.lethal, args.recovery,
                          args.target_height_steps, args.collapsed, args.target_rig)
    pygame.init()
    try:
        surface = pygame.display.set_mode(SIZE)
        pygame.display.set_caption("Fire Bolt · Pygame reference")
        target_appearance = APPEARANCE if args.target_rig == "neuroclient.modular" else GOBLIN_APPEARANCE
        media = load_animation_media(timeline, {"caster": APPEARANCE, "target": target_appearance})
        fonts = (pygame.font.SysFont("sans", 35, bold=True), pygame.font.SysFont("sans", 18),
                 pygame.font.SysFont("sans", 14))
        focus = tuple((a + b) / 2 for a, b in zip(timeline.source.caster.grid, timeline.source.applications[0].target.grid))
        camera = Camera(quadrant=args.quadrant, zoom=1, viewport=SIZE).with_focus((focus[0], focus[1]))
        elapsed = args.at_ms if args.at_ms is not None else 0.0
        playing = args.at_ms is None
        if args.capture is not None or args.headless:
            _draw(surface, timeline, media, camera, elapsed, False, args.playback_rate, fonts)
            if args.capture is not None:
                args.capture.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(surface, args.capture)
            return
        clock = pygame.time.Clock()  # Assets/fonts are ready before the clock starts.
        pygame.key.set_repeat(250, 60)
        running = True
        while running:
            delta_ms = clock.tick(60)
            changed = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        playing, changed = not playing, True
                    elif event.key == pygame.K_r:
                        elapsed, playing, changed = 0.0, True, True
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        elapsed = max(0.0, min(timeline.complete_ms, elapsed + (-100 if event.key == pygame.K_LEFT else 100)))
                        playing, changed = False, True
                    elif event.key in (pygame.K_q, pygame.K_e):
                        camera = camera.quarter_turned(-1 if event.key == pygame.K_q else 1)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and TIMELINE_RECT.collidepoint(event.pos):
                    elapsed = (event.pos[0] - TIMELINE_RECT.x) / TIMELINE_RECT.width * timeline.complete_ms
                    playing, changed = False, True
            if playing and not changed:
                elapsed = min(timeline.complete_ms, elapsed + delta_ms * args.playback_rate)
                playing = elapsed < timeline.complete_ms
            _draw(surface, timeline, media, camera, elapsed, playing, args.playback_rate, fonts)
            pygame.display.flip()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
