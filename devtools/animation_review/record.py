"""Record finite retained sequences with the game's actual frame compositor."""

import json
from dataclasses import replace
from math import ceil
from pathlib import Path
import subprocess
from typing import Any
from uuid import UUID

import pygame

from dnd.core.events import EventPhase
from game.animation import facing_for_delta
from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows, actor_screen_bounds
from game.animation_types import Facing8
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import BoundChoreography, bind_choreography
from game.choreography_draw import ChoreographyMedia, load_choreography_media, load_motion_media
from game.combat import actor_contact
from game.feedback import FeedbackTrack, choreography_feedback, motion_feedback
from game.motion import MotionTimeline, bind_motion
from game.playback_frame import PlaybackFrame, sample_playback_frame
from game.player_facts import AttackFact, ForcedMovementFact, MovementFact, PlayerState, SpellFact, StepFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.presentation_coverage import lineage_coverage, missing_observed_bindings, presentation_inventory
from game.projection import Camera, TILE_WIDTH, ZOOM_LEVELS, project_screen
from game.scene import draw_actor_labels, load_scene_media, scene_actors
from game.visual_position import VisualPosition
from devtools.animation_review.cases import ReviewCase, ReviewSequence
from devtools.animation_review.trace import LINEAGE, STATE, draw_trace, frame_trace, group_trace, motion_trace, state_summary


def record_case(case: ReviewCase, directory: Path, trace: dict[str, Any], *,
                sequence: ReviewSequence, fps: int, size: tuple[int, int], ffmpeg: str,
                coverage_inventory: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    before = sequence.before
    latest = before
    for lineage in sequence.lineages:
        latest = reduce_lineage(latest, lineage)
    trace.update({
        "mode": "decoded-recorded-input; latest reduced before historical playback",
        "initial": STATE.dump_python(before, mode="json", serialize_as_any=True, warnings="error"),
        "latest": state_summary(latest),
        "lineages": [LINEAGE.dump_python(root, mode="json", serialize_as_any=True, warnings="error")
                     for root in sequence.lineages],
        "heads": [], "frames": [], "checks": [], "gaps": [], "coverage": [],
    })
    checks, gaps = trace["checks"], trace["gaps"]

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    check("completed-events", all(
        event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
        for root in sequence.lineages for event in root.events),
        "Every received causal node is terminal before video sampling begins; an empty perceived history is valid.")
    check("complete-descendants", all(
        child in {event.lineage_uuid for event in root.events}
        for root in sequence.lineages for event in root.events for child in event.children_lineages),
        "Original child lineage identities are retained, including technical nodes.")
    pygame.init()
    video_size = size[0] * 2, size[1] * 2
    screen = pygame.display.set_mode(video_size)
    view = pygame.Surface(size)
    pygame.display.set_caption(f"Animation review · {case.id}")
    data = load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))
    if coverage_inventory is not None and not coverage_inventory:
        coverage_inventory.extend(presentation_inventory(data))
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx), bold=style.fontWeight == "bold")
                  for style in (data.number_style, data.badge_style))
    number_font, badge_font = fonts
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    facings: dict[str, Facing8] = {
        actor.contact.actor_uuid: facing_for_delta(
            (pose.toward[0] - pose.position[0], pose.toward[1] - pose.position[1]), data)
        for actor in scene_actors(before, data, {})
        for pose in case.initial_facings if actor.contact.grid == pose.position
    }
    trace["initial_facings"] = dict(facings)
    positions: dict[str, VisualPosition] = {}
    feedback_viewport = pygame.Rect(0, 44, size[0], size[1] - 44)
    actors = scene_actors(before, data, facings)
    reported_scene_bindings: set[tuple[str, str]] = set()
    if not actors:
        raise ValueError("review scenario has no visible actors")
    focus = (sum(row.contact.grid[0] for row in actors) / len(actors),
             sum(row.contact.grid[1] for row in actors) / len(actors))
    height = round(sum(row.contact.elevation_steps for row in actors) / len(actors))
    cameras = tuple(Camera(quadrant=quadrant, zoom=1.0, viewport=size).with_focus(focus, elevation_steps=height)
                    for quadrant in range(4))
    # Frame the whole history; media loads only as those heads enter playback.
    framing_contacts = [actor.contact for actor in actors]
    area_frames = []
    for root in sequence.lineages:
        fact = root.root.fact
        if (isinstance(fact, SpellFact) and fact.aoe_position is not None
                and fact.behavior_id is not None and fact.behavior_id in data.drafts):
            recipe = data.drafts[fact.behavior_id]
            projectile = recipe.projectile
            support = before.tiles.get(fact.aoe_position)
            if recipe.area is not None and projectile is not None and projectile.sprite is not None and support is not None:
                asset = data.projectile_assets[projectile.impact.assetId or projectile.sprite.assetId]
                scale = projectile.impact.scale if projectile.impact.scale is not None else projectile.scale
                area_frames.append((fact.aoe_position, support.elevation_steps,
                                    asset.frame.width * scale, asset.frame.height * scale))
        entrants = scene_actors(stage_lineage(before, root), data, facings)
        framing_contacts.extend(actor.contact for actor in entrants)
        flight = bind_motion(before, root, data)
        if flight is not None:
            # Reuse compiled geometry for a conservative flight envelope. The
            # full sprite cell at each leg endpoint and its maximum lift also
            # covers in-between frames; this preflight never advances playback.
            framing_contacts.extend(replace(flight.actor, grid=grid, elevation_steps=elevation,
                body_lift_px=leg.arc_height_px + leg.initial_lift_px)
                for leg in flight.legs for grid, elevation in (
                    (leg.start, leg.start_height), (leg.end, leg.end_height)))
        before = reduce_lineage(before, root)
        retained_actors = scene_actors(before, data, facings)
        framing_contacts.extend(actor.contact for actor in retained_actors)
    body_rows: LoadedBodyRows = {}
    body_media = load_scene_media(actors, data, body_rows=body_rows)
    if area_frames:
        # Ground casts are reviewed around their destinations. Center the
        # reserved effect canvas in the usable pane, below its fixed header.
        focus = tuple((min(row[0][axis] for row in area_frames)
                       + max(row[0][axis] for row in area_frames)) / 2 for axis in (0, 1))
        height = round(sum(row[1] for row in area_frames) / len(area_frames))
        cameras = tuple(Camera(quadrant=quadrant, zoom=1.0, viewport=size).with_focus(
            (focus[0], focus[1]), elevation_steps=height) for quadrant in range(4))
        cameras = tuple(replace(camera, pan=(camera.pan[0], camera.pan[1] + 22)) for camera in cameras)
    # Keep the old framing when it already covers the history. Longer routes
    # use one fixed focus/zoom for all four views, never a moving-camera patch.
    def fits(views: tuple[Camera, ...]) -> bool:
        for camera in views:
            factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
            for contact in framing_contacts:
                rig = data.rigs[contact.rig_id]
                x, y = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
                width = rig.cell_width * contact.visual_scale * contact.visual_scale_x * factor
                top = y + ((rig.origin_y_from_ground - rig.cell_height) * contact.visual_scale
                           - contact.body_lift_px) * factor
                bottom = y + (rig.origin_y_from_ground * contact.visual_scale - contact.body_lift_px) * factor
                if x - width / 2 < 12 or x + width / 2 > size[0] - 12 or top < 56 or bottom > size[1] - 12:
                    return False
            for position, elevation, width, height in area_frames:
                x, y = project_screen(position, camera, elevation_steps=elevation)
                if (x - width * factor / 2 < 12 or x + width * factor / 2 > size[0] - 12
                        or y - height * factor / 2 < 56 or y + height * factor / 2 > size[1] - 12):
                    return False
        return True

    if not fits(cameras):
        if not area_frames:
            focus = tuple((min(contact.grid[axis] for contact in framing_contacts)
                           + max(contact.grid[axis] for contact in framing_contacts)) / 2 for axis in (0, 1))
            height = round((min(contact.elevation_steps for contact in framing_contacts)
                            + max(contact.elevation_steps for contact in framing_contacts)) / 2)
        for zoom in reversed(ZOOM_LEVELS):
            cameras = tuple(Camera(quadrant=quadrant, zoom=zoom, viewport=size).with_focus(
                (focus[0], focus[1]), elevation_steps=height) for quadrant in range(4))
            if area_frames:
                cameras = tuple(replace(camera, pan=(camera.pan[0], camera.pan[1] + 22)) for camera in cameras)
            if fits(cameras):
                break
    trace["cameras"] = [{"quadrant": camera.quadrant, "focus": focus, "elevation_steps": height,
                         "zoom": camera.zoom, "viewport": size,
                         "video_offset": ((camera.quadrant % 2) * size[0], (camera.quadrant // 2) * size[1])}
                        for camera in cameras]
    before = sequence.before
    feedback: list[FeedbackTrack] = []
    presentation_ms = 0.0
    frame_index = 0
    interval = 1000 / fps
    poster_written = False
    paused_pixels: bytes | None = None
    paused_pixels_match = True
    camera_state_parity = True
    bodies_in_view = True
    video = directory / "clip.mp4"
    with (directory / "encoder.log").open("wb") as encoder_log:
        encoder = subprocess.Popen([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
            "-video_size", f"{video_size[0]}x{video_size[1]}", "-framerate", str(fps), "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(video),
        ], stdin=subprocess.PIPE, stderr=encoder_log)
        assert encoder.stdin is not None
        sink = encoder.stdin

        def capture(after: PlayerState | None = None, elapsed_ms: float = 0.0,
                    root_uuid: UUID | None = None, choreography: BoundChoreography | None = None,
                    choreography_media: ChoreographyMedia | None = None, motion: MotionTimeline | None = None,
                    reaction_media: dict[UUID, ChoreographyMedia] | None = None, paused: bool = False) -> PlaybackFrame:
            nonlocal frame_index, facings, positions, poster_written, camera_state_parity, bodies_in_view
            nonlocal paused_pixels, paused_pixels_match
            views = []
            samples = []
            for camera in cameras:
                sample = sample_playback_frame(
                    before, after, data, elapsed_ms, presentation_ms, camera, facings,
                    body_media, number_font, badge_font, choreography=choreography,
                    choreography_media=choreography_media, motion=motion, reaction_media=reaction_media,
                    feedback=feedback,
                    positions=positions, feedback_viewport=feedback_viewport,
                )
                samples.append(sample)
                bodies_in_view &= all(feedback_viewport.contains(bounds)
                                      for bounds in actor_screen_bounds(sample.commands).values())
                draw_frame(view, sample.displayed, catalog, cache, camera, presentation_ms / 1000,
                           show_grid=False, show_debug=False, mouse_position=None, extra_commands=sample.commands,
                           world_transitions=sample.world_transitions, residue_reveals=sample.residue_reveals)
                draw_actor_labels(view, cache.debug_font, sample.actors, sample.displayed, camera,
                                  shown_hp=sample.shown_hp, active_uuid=None,
                                  commands=sample.commands, viewport=feedback_viewport)
                view.fill((14, 20, 28), (0, 0, size[0], 44))
                mode = "PAUSED" if paused else "history" if sequence.lineages else "no perceived changes"
                label = f"{case.id}  |  {presentation_ms:.0f} ms  |  {mode}"
                view.blit(cache.debug_font.render(label, True, (230, 237, 245)), (12, 8))
                cursors = f"latest {latest.reducer_cursor}  |  displayed {sample.displayed.reducer_cursor}  |  camera {camera.quadrant}"
                view.blit(cache.debug_font.render(cursors, True, (158, 179, 197)), (12, 26))
                screen.blit(view, ((camera.quadrant % 2) * size[0], (camera.quadrant // 2) * size[1]))
                views.append({"quadrant": camera.quadrant, "draws": draw_trace(sample)})
            sample = samples[0]
            camera_state_parity &= all(row.displayed == sample.displayed and row.complete == sample.complete
                                       and row.shown_hp == sample.shown_hp and row.positions == sample.positions
                                       and row.actors == sample.actors for row in samples[1:])
            facings = dict(sample.facings)
            positions = dict(sample.positions)
            pygame.event.pump()
            pygame.display.flip()
            pixels = pygame.image.tobytes(screen, "RGB")
            if paused:
                if paused_pixels is None:
                    paused_pixels = pixels
                else:
                    paused_pixels_match &= pixels == paused_pixels
            else:
                paused_pixels = None
            sink.write(pixels)
            if not poster_written and presentation_ms >= 900:
                pygame.image.save(screen, directory / "poster.png")
                poster_written = True
            trace["frames"].append({
                "index": frame_index, "video_ms": frame_index * interval,
                "presentation_ms": presentation_ms, "elapsed_ms": elapsed_ms,
                "root_uuid": str(root_uuid) if root_uuid else None, "paused": paused,
                "latest_cursor": latest.reducer_cursor, "views": views, **frame_trace(sample),
            })
            frame_index += 1
            return sample

        try:
            for _ in range(ceil(350 / interval)):
                sampled = capture()
                presentation_ms += interval
            pause_done = False
            for lineage in sequence.lineages:
                after = reduce_lineage(before, lineage)
                admitted = stage_lineage(before, lineage)
                staged_actors = (
                    *scene_actors(admitted, data, facings, positions),
                    *scene_actors(after, data, facings, positions),
                )
                load_scene_media(staged_actors, data, body_rows=body_rows)
                for actor in staged_actors:
                    bindings = [("rig", actor.contact.rig_id)]
                    retained = after.actors.get(UUID(actor.contact.actor_uuid)) or admitted.actors.get(UUID(actor.contact.actor_uuid))
                    if retained is not None and retained.creature_content_ref is not None:
                        bindings.append(("creature", retained.creature_content_ref))
                    for family, identity in bindings:
                        if (family, identity) in reported_scene_bindings:
                            continue
                        reported_scene_bindings.add((family, identity))
                        trace["coverage"].append({"root_uuid": str(lineage.root.uuid), "event_uuid": None,
                            "owner": "body rig", "observed": "scene_loaded", "issues": [],
                            "family": family, "identity": identity})
                contacts = {actor.contact.actor_uuid: actor.contact
                            for actor in scene_actors(before, data, facings, positions)}
                motion = bind_motion(before, lineage, data, contacts=contacts)
                if isinstance(lineage.root.fact, MovementFact) and any(
                    isinstance(event.fact, AttackFact) or isinstance(event.fact, StepFact) and event.fact.committed
                    for event in lineage.events
                ):
                    check(f"movement-bound:{lineage.root.uuid}", motion is not None,
                          "A committed movement/reaction must execute its movement choreography.")
                    if motion is None:
                        gaps.append(f"{lineage.root.uuid}: Movement reaction choreography is not bound")
                group = None if motion is not None else bind_choreography(before, lineage, data,
                                                                        facings=facings, contacts=contacts)
                group_media = load_choreography_media(group, body_rows=body_rows) if group is not None else None
                reaction_media = load_motion_media(motion, data, body_rows=body_rows) if motion is not None else {}
                duration = motion.complete_ms if motion is not None else group.complete_ms if group else 0
                if motion is not None:
                    feedback.extend(motion_feedback(motion, data, presentation_ms))
                    groups = tuple(row.choreography for row in motion.reactions)
                    composition = motion_trace(motion)
                else:
                    assert group is not None
                    feedback.extend(choreography_feedback(group, data, presentation_ms, contacts=contacts))
                    groups = (group,)
                    composition = group_trace(group)
                for bound in groups:
                    gaps.extend(f"{identity}: {detail}" for identity, detail in bound.gaps)
                evidence = lineage_coverage(lineage, group=group, motion=motion)
                trace["coverage"].extend(evidence)
                if coverage_inventory is not None:
                    coverage_inventory.extend(missing_observed_bindings(coverage_inventory, evidence))
                trace["heads"].append({
                    "root_uuid": str(lineage.root.uuid), "video_start_ms": frame_index * interval,
                    "presentation_start_ms": presentation_ms, "duration_ms": duration,
                    "before": state_summary(before), "after": state_summary(after),
                    "composition": composition,
                })
                start = presentation_ms
                for tick in range(ceil(duration / interval) + 1):
                    elapsed = min(tick * interval, duration)
                    presentation_ms = start + elapsed
                    if (not pause_done and case.pause_at_ms is not None and elapsed >= case.pause_at_ms):
                        for _ in range(ceil(case.pause_duration_ms / interval)):
                            capture(after, elapsed, lineage.root.uuid, group, group_media, motion, reaction_media, paused=True)
                        pause_done = True
                    sampled = capture(after, elapsed, lineage.root.uuid, group, group_media, motion, reaction_media)
                check(f"settled-state:{lineage.root.uuid}", sampled.complete and sampled.displayed == after,
                      "At completion the frame exposes the authoritative reduced state.")
                for bound in groups:
                    for cue in bound.forced_movement:
                        node = next(event for event in lineage.events if event.uuid == cue.event_uuid)
                        assert isinstance(node.fact, ForcedMovementFact)
                        contact = next((actor.contact for actor in sampled.actors
                                        if actor.contact.actor_uuid == cue.actor.actor_uuid), None)
                        if contact is not None:
                            check(f"forced-position:{node.uuid}", contact.grid == node.fact.end_position,
                                  f"Visible {contact.grid}; received displacement committed {node.fact.end_position}.")
                steps = [event.fact for event in lineage.events if isinstance(event.fact, StepFact)]
                if steps:
                    actor_uuid = str(steps[-1].source_entity_uuid)
                    contact = next((row.contact for row in sampled.actors if row.contact.actor_uuid == actor_uuid), None)
                    expected = steps[-1].to_position if steps[-1].committed else steps[-1].from_position
                    legal = (actor_contact(after, after.actors[steps[-1].source_entity_uuid], data)
                             if contact is not None else None)
                    if legal is not None:
                        check(f"committed-position:{lineage.root.uuid}", legal.grid == expected,
                              f"Legal {legal.grid}; last received Step settled at {expected}.")
                    if motion is not None and legal is not None and contact is not None:
                        stopped = legal if steps[-1].committed else motion.reactions[-1].contact
                        check(f"visual-position:{lineage.root.uuid}",
                              (contact.grid, contact.elevation_steps, contact.body_lift_px)
                              == (stopped.grid, stopped.elevation_steps, stopped.body_lift_px),
                              f"Rendered {contact.grid} retains its motion endpoint; legal tile is {expected}.")
                before = after
                presentation_ms += interval
            tail = max(800, max((track.start_ms + track.duration_ms - presentation_ms for track in feedback), default=0))
            for _ in range(ceil(tail / interval)):
                idle_sample = capture()
                presentation_ms += interval
            check("idle-visual-position", tuple(
                (actor.contact.actor_uuid, actor.contact.grid, actor.contact.elevation_steps, actor.contact.body_lift_px)
                for actor in sampled.actors) == tuple(
                (actor.contact.actor_uuid, actor.contact.grid, actor.contact.elevation_steps, actor.contact.body_lift_px)
                for actor in idle_sample.actors),
                "Releasing the final head preserves rendered placement, including interrupted subcell poses and body lift.")
            if not poster_written:
                pygame.image.save(screen, directory / "poster.png")
            check("history-equals-latest", before == latest, "All complete roots reduce to the same final history/latest values.")
            check("four-camera-state-parity", camera_state_parity,
                  "All four views sample the same retained state and presentation time in one recording pass.")
            check("visible-bodies-in-frame", bodies_in_view,
                  "Opaque actor pixels stay below the header and inside all four camera viewports, including jump lift.")
            if case.pause_at_ms is not None:
                held = [row for row in trace["frames"] if row["paused"]]
                check("frozen-presentation", len(held) > 1 and paused_pixels_match and all(
                    row["presentation_ms"] == held[0]["presentation_ms"] and row["state"] == held[0]["state"]
                    and row["contacts"] == held[0]["contacts"] and row["views"] == held[0]["views"] for row in held),
                    "Video time advances while retained time, state, draw samples and rendered RGB pixels remain frozen.")
        finally:
            encoder.stdin.close()
            encoder.wait(timeout=60)
            pygame.quit()
        if encoder.returncode != 0:
            raise RuntimeError(f"video encoder exited {encoder.returncode}: {(directory / 'encoder.log').read_text()}")
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
        "stream=nb_read_frames,width,height,codec_name,duration", "-of", "json", str(video),
    ], check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    check("encoded-frames", int(stream["nb_read_frames"]) == frame_index,
          f"Decoded {stream['nb_read_frames']} frames; trace has {frame_index} frames at {fps} fps.")
    trace["video"] = {**stream, "fps": fps, "frame_count": frame_index}
    return {"frame_count": frame_index, "duration_ms": frame_index * interval,
            "status": "passed" if all(row["passed"] for row in checks) else "failed",
            "checks": checks, "gaps": sorted(set(gaps)), "coverage": trace["coverage"]}
