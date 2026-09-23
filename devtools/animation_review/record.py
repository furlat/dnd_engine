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
from dnd.core.presentation_geometry import SpherePresentationGeometry
from game.animation import facing_for_delta
from game.animation_data import load_animation_data
from game.animation_draw import LoadedBodyRows, actor_screen_bounds
from game.animation_types import Facing8
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.choreography import BoundChoreography, bind_choreography
from game.choreography_draw import ChoreographyMedia, load_choreography_media, load_motion_media
from game.combat import BoundCast, actor_contact
from game.feedback import FeedbackTrack, choreography_feedback, motion_feedback
from game.condition_media_lifetime import register_condition_lifetimes
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.deposit_media import register_deposit_starts
from game.motion_media import MotionMediaCue, bind_motion_media, choreography_motion_media
from game.motion import MotionTimeline, bind_motion
from game.playback_frame import PlaybackFrame, sample_playback_frame
from game.body_history import retain_body_head
from game.player_facts import AttackFact, ForcedMovementFact, MovementFact, PlayerState, PortalTransferFact, SpellFact, StepFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.presentation_group import presentation_groups, reduce_presentation_group, stage_presentation_group
from game.presentation_coverage import lineage_coverage, missing_observed_bindings, presentation_inventory
from game.projection import Camera, TILE_WIDTH, ZOOM_LEVELS, project_screen
from game.scene import draw_actor_labels, load_scene_media, scene_actors
from game.visual_position import VisualPosition
from devtools.animation_review.cases import ReviewCase, ReviewSequence
from devtools.animation_review.framing import cast_media_bounds, projected_bounds
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
    anchored_frames = []
    spatial_frames = set()
    for root in sequence.lineages:
        fact = root.root.fact
        if (case.framing == "scene" and isinstance(fact, SpellFact) and fact.aoe_position is not None
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
        if case.framing == "scene" and any(
                isinstance(event.fact, SpellFact)
                and (recipe := data.drafts.get(event.fact.effect_id or event.fact.behavior_id or "")) is not None
                and recipe.media for event in root.events):
            groups = (tuple(reaction.choreography for reaction in flight.reactions) if flight is not None
                      else (bind_choreography(before, root, data, facings=facings),))
            anchored_frames.extend(bounds for group in groups for node in group.nodes
                                   if isinstance(node.bound, BoundCast)
                                   if (bounds := cast_media_bounds(node.bound.timeline)))
        before = reduce_lineage(before, root)
        if case.framing == "scene" and before.senses is not None:
            for effect in before.senses.spatial_effects.values():
                binding = data.spatial_media.get(effect.content_ref.content_id)
                geometry = effect.area_geometry
                if binding is None or not isinstance(geometry, SpherePresentationGeometry):
                    continue
                support = before.tiles.get(geometry.center)
                for layer in binding.layers:
                    volume = layer.composition == "volume"
                    if not volume and geometry.center not in before.senses.visible:
                        continue
                    elevation = support.elevation_steps if support is not None else effect.anchor_elevation_steps
                    if elevation is None:
                        continue
                    radius_scale = (geometry.radius_feet / binding.referenceRadiusFeet
                        if volume and binding.referenceRadiusFeet is not None else 1.)
                    origin = tuple(geometry.center[axis] + layer.offsetCells[axis] * radius_scale
                        for axis in (0, 1))
                    asset = data.projectile_assets[layer.assetId]
                    spatial_frames.add((origin, elevation,
                        asset.frame.width * binding.scale * radius_scale, asset.frame.height * binding.scale * radius_scale,
                        asset.anchor.x, asset.anchor.y))
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
    def frame_bounds(camera: Camera):
        factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
        for contact in framing_contacts:
            rig = data.rigs[contact.rig_id]
            x, y = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
            width = rig.cell_width * contact.visual_scale * contact.visual_scale_x * factor
            top = y + ((rig.origin_y_from_ground - rig.cell_height) * contact.visual_scale
                       - contact.body_lift_px) * factor
            bottom = y + (rig.origin_y_from_ground * contact.visual_scale - contact.body_lift_px) * factor
            yield x - width / 2, top, x + width / 2, bottom
        for position, elevation, width, height in area_frames:
            x, y = project_screen(position, camera, elevation_steps=elevation)
            yield x - width * factor / 2, y - height * factor / 2, x + width * factor / 2, y + height * factor / 2
        for bounds in anchored_frames:
            yield projected_bounds(bounds[camera.quadrant], camera)
        for position, elevation, width, height, pivot_x, pivot_y in spatial_frames:
            x, y = project_screen(position, camera, elevation_steps=elevation)
            yield (x - width * pivot_x * factor, y - height * pivot_y * factor,
                   x + width * (1 - pivot_x) * factor, y + height * (1 - pivot_y) * factor)

    def fits(views: tuple[Camera, ...]) -> bool:
        return all(left >= 12 and right <= size[0] - 12 and top >= 56 and bottom <= size[1] - 12
                   for camera in views for left, top, right, bottom in frame_bounds(camera))

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
            if anchored_frames or spatial_frames:
                # One fixed pan per corner includes asymmetric authored media
                # such as a tall column or a line originating at the caster.
                centered = []
                for camera in cameras:
                    bounds = tuple(frame_bounds(camera))
                    center = ((min(row[0] for row in bounds) + max(row[2] for row in bounds)) / 2,
                              (min(row[1] for row in bounds) + max(row[3] for row in bounds)) / 2)
                    centered.append(camera.with_screen_pan((size[0] / 2 - center[0], (56 + size[1] - 12) / 2 - center[1])))
                cameras = tuple(centered)
            if fits(cameras):
                break
    trace["cameras"] = [{"quadrant": camera.quadrant, "focus": focus, "elevation_steps": height,
                         "zoom": camera.zoom, "pan": camera.pan, "viewport": size,
                         "video_offset": ((camera.quadrant % 2) * size[0], (camera.quadrant // 2) * size[1])}
                        for camera in cameras]
    before = sequence.before
    feedback: list[FeedbackTrack] = []
    motion_media: list[MotionMediaCue] = []
    presentation_ms = 0.0
    condition_lifetimes = register_condition_lifetimes({}, before, data, absolute_start_ms=0)
    spatial_lifetimes = register_spatial_lifetimes({}, before, data, absolute_start_ms=0)
    deposit_starts = register_deposit_starts({}, before, data, absolute_start_ms=0)
    body_history = retain_body_head((), before, None, start_ms=0, facings=facings, positions=positions)
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
                    feedback=feedback, condition_lifetimes=condition_lifetimes,
                    spatial_lifetimes=spatial_lifetimes, deposit_starts=deposit_starts,
                    positions=positions, feedback_viewport=feedback_viewport, motion_media=motion_media, body_history=body_history,
                )
                samples.append(sample)
                bodies_in_view &= all(feedback_viewport.contains(bounds)
                                      for bounds in actor_screen_bounds(sample.commands).values())
                draw_frame(view, sample.displayed, catalog, cache, camera, presentation_ms / 1000,
                           show_grid=False, show_debug=False, mouse_position=None, extra_commands=sample.commands,
                           world_transitions=sample.world_transitions, residue_reveals=sample.residue_reveals, deposited_materials=sample.deposited_materials)
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
            for presentation in presentation_groups(sequence.lineages):
                lineage = presentation.primary
                after = reduce_presentation_group(before, presentation)
                admitted = stage_presentation_group(before, presentation)
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
                activated_conditions = frozenset(owner for owner, lifetime in condition_lifetimes.items()
                    if lifetime.activated_ms is not None and lifetime.activated_ms <= presentation_ms)
                motion = bind_motion(before, lineage, data, contacts=contacts,
                                     activated_conditions=activated_conditions)
                if isinstance(lineage.root.fact, MovementFact) and any(
                    isinstance(event.fact, AttackFact) or isinstance(event.fact, StepFact) and event.fact.committed
                    for event in lineage.events
                ):
                    check(f"movement-bound:{lineage.root.uuid}", motion is not None,
                          "A committed movement/reaction must execute its movement choreography.")
                    if motion is None:
                        gaps.append(f"{lineage.root.uuid}: Movement reaction choreography is not bound")
                group = None if motion is not None else bind_choreography(before, lineage, data,
                    facings=facings, contacts=contacts, activated_conditions=activated_conditions,
                    reactions=presentation.reactions)
                group_media = load_choreography_media(group, body_rows=body_rows) if group is not None else None
                reaction_media = load_motion_media(motion, data, body_rows=body_rows) if motion is not None else {}
                condition_lifetimes = register_condition_lifetimes(condition_lifetimes, before, data,
                    absolute_start_ms=presentation_ms, lineage=lineage, choreography=group, motion=motion)
                spatial_lifetimes = register_spatial_lifetimes(spatial_lifetimes, before, data,
                    absolute_start_ms=presentation_ms, lineage=lineage, choreography=group, motion=motion)
                deposit_starts = register_deposit_starts(deposit_starts, before, data,
                    absolute_start_ms=presentation_ms, lineage=lineage, choreography=group, motion=motion)
                if motion is not None:
                    motion_media.extend(bind_motion_media(motion, data, presentation_ms))
                elif group is not None:
                    motion_media.extend(choreography_motion_media(group, data, presentation_ms))
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
                evidence = [entry for retained_root in presentation.lineages
                    for entry in lineage_coverage(retained_root, group=group, motion=motion)]
                trace["coverage"].extend(evidence)
                if coverage_inventory is not None:
                    coverage_inventory.extend(missing_observed_bindings(coverage_inventory, evidence))
                trace["heads"].append({
                    "root_uuid": str(lineage.root.uuid), "video_start_ms": frame_index * interval,
                    "retained_roots": [str(root.root.uuid) for root in presentation.lineages],
                    "presentation_start_ms": presentation_ms, "duration_ms": duration,
                    "before": state_summary(before), "after": state_summary(after),
                    "composition": composition,
                })
                body_history = retain_body_head(body_history, before, after, start_ms=presentation_ms,
                    facings=facings, positions=positions, choreography=group, motion=motion)
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
                step_nodes = [event for event in lineage.events if isinstance(event.fact, StepFact)]
                steps = [event.fact for event in step_nodes if isinstance(event.fact, StepFact)]
                if steps:
                    actor_uuid = str(steps[-1].source_entity_uuid)
                    contact = next((row.contact for row in sampled.actors if row.contact.actor_uuid == actor_uuid), None)
                    expected = steps[-1].to_position if steps[-1].committed else steps[-1].from_position
                    # A nested displacement can settle later than its incoming Step,
                    # while a paid Step after arrival can supersede it in turn.
                    # Declaration order retains that causality across nested completion.
                    starts = {}
                    for version in lineage.version_rows:
                        starts[version.lineage_uuid] = min(starts.get(version.lineage_uuid, version.source_index),
                                                          version.source_index)
                    relocations = [node for node in lineage.events if not node.canceled
                        and (isinstance(node.fact, PortalTransferFact) and node.fact.committed
                             and node.fact.end_position is not None
                             or isinstance(node.fact, ForcedMovementFact) and node.fact.actual_distance > 0)
                        and node.fact.target_entity_uuid == steps[-1].source_entity_uuid
                        and starts[node.lineage_uuid] > starts[step_nodes[-1].lineage_uuid]]
                    if relocations:
                        relocation = max(relocations, key=lambda node: starts[node.lineage_uuid]).fact
                        assert isinstance(relocation, (PortalTransferFact, ForcedMovementFact)) and relocation.end_position is not None
                        expected = relocation.end_position
                    legal = (actor_contact(after, after.actors[steps[-1].source_entity_uuid], data)
                             if contact is not None else None)
                    if legal is not None:
                        check(f"committed-position:{lineage.root.uuid}", legal.grid == expected,
                              f"Legal {legal.grid}; last received Step or subsequent displacement settled at {expected}.")
                    if motion is not None and legal is not None and contact is not None:
                        stopped = legal if steps[-1].committed else motion.reactions[-1].contact
                        check(f"visual-position:{lineage.root.uuid}",
                              stopped is not None and (contact.grid, contact.elevation_steps, contact.body_lift_px)
                              == (stopped.grid, stopped.elevation_steps, stopped.body_lift_px),
                              f"Rendered {contact.grid} retains its motion endpoint; legal tile is {expected}.")
                before = after
                presentation_ms += interval
            tail = max(case.tail_duration_ms, max((track.start_ms + track.duration_ms - presentation_ms for track in feedback), default=0),
                       max((cue.media.end_ms-presentation_ms for cue in motion_media), default=0))
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
