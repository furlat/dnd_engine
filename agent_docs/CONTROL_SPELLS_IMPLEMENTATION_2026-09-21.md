# Control-spell integration — 2026-09-21

## Purpose and boundary

Integrate the authored Charm Person, Blindness/Deafness, Command, Color Spray,
Silence and Sleep condition media. Real native actions generate complete saved
subjective histories; existing reduction and independent local playback consume
those histories. Preserve approved projectile endpoints, all existing Sleep
cast/impact/fall/wake behavior, and previous spell output.

Input: actual cast choices, condition membership, turn events, spatial effect
membership and lifetime. Output: authored casting hands, finite application and
clear transitions, sustained status media and Silence area. No browser demo
clock supplies game behavior. No engine renderer cues or new spell executor.

## Reviewed decisions

The anti-slop review inspected existing condition timelines, retained media
clocks, registered atlas drawing and spatial bindings. The anti-OOP review
inspected native condition parent/child ownership and turn progression.

1. Reuse paged media storage, sparse bounds, full-cell pivots and bounded caches.
   Single-orientation glyphs use one shared frame-address array rather than
   duplicating identical metadata eight times. Directional art keeps facing maps.
   Import media explicitly, separately from authoring behavior JSON. No hashes,
   source audits, dynamic fallback discovery or image rewriting.
2. Execute existing condition application/removal effects. Add frame windows,
   delayed starts and rear/front placement only where the authored material
   requires them. Frame selection is pure presentation sampling, not Pygame
   behavior. Preserve Bless/Bane/False Life paths and local clocks.
3. Retain source UUID membership while carrying the effective visual clock
   across contributors of the same recipe. Apply once and clear after the last
   contributor; no phase jump when the selected owner changes.
4. Add pose-relative head/face registration under BodyRig. Resolve it against
   the actual sampled clip, frame and camera-facing row. Source points are in
   full actor-cell coordinates. Keep torso, resting-body and projectile anchors
   unchanged. Missing pose/rig coverage must be explicit, not silently claimed.
5. Command uses an authored owner-turn-start activation track driven by retained
   TurnFact. Its execution frames include the tail. Grovel's independent Prone
   survives Command removal; Flee uses actual movement. Reacquisition does not
   invent an earlier execution edge.
6. Silence belongs to existing maintained spatial media: actual fixed origin,
   observed footprint/elevation, application, sustain and advancing clear fade.
   Effective Deafened belongs to actors. Preview ellipses do not decide members.
7. New Sleep delivery replaces only textual Zzz: seamless 576-frame/144fps loop,
   200ms fade-in, 400ms advancing fade-out, corrected face pivot [128,109.9504].
   No old +55 compensation, frame430 clamp or duplicate actor.
8. Color Spray is a stationary directional cone with hand offset already baked
   into the export. Register that measured hand point as the media pivot and
   authored release socket: the export preview's actor scale differs from the
   game's actor scale, so the original ground registration alone would offset
   emission. Preserve the cone's world size, facing rows and multicolor hands.
   Blindness/Deafness shares one spell identity; palette
   selection must follow the actual retained mode, including successful saves.

## Demonstrated native repair

Two real action sequences expose lost effective sense conditions: Silence plus
independent Deafness, and Color Spray plus independent Blindness. Removing one
parent currently removes the public condition despite the other active parent.
Repair shared ownership at the existing condition/lease seam with removal-order
coverage. Do not rewrite global replacement policy or invent simultaneous Charm
source behavior; Charm currently replaces its same-name condition.

## Implementation and review ownership

- Native agent: demonstrated sensory-condition ownership repair and native
  histories/tests; anti-OOP review of the resulting composition and event flow.
- Media agent: explicit importer, selected assets and separate authored bundle.
- Presentation reviewer: head/face pose registration and coverage, without
  modifying projectile targeting.
- Root: shared lifecycle sampling, transition and activation tracks, condition
  records, spatial integration, gallery and final validation.

## Acceptance

- Native action/state contracts pass for senses, Command phases and membership.
- Real histories serialize once and replay without native objects. Check early
  clear, overlap/removal order, moving/resting attachments, actual turn activation,
  Silence entry/exit and independent Deafness, long Sleep and damage wake.
- Review production clips from four cameras and both subjective viewpoints.
  Inspect source assets only as registration evidence, never as gameplay proof.
- Run focused presentation/native tests, native and graphics type checks, and
  import-boundary checks. Previous clean typing stays clean.
- Document actual results and remaining gaps; do not call an imported PNG a
  completed integration. Do not launch unrelated optimization or redesign work.

## User steering during implementation: lethal opportunity blood

The reviewed `walk-downed` capture lacked any body-release fact because its Hero
fixture omitted the existing blood-response composition. Enable that fixture's
existing `bloodied` option, capture both participants once, and replay the actual
damage, floor residues and downing from those saved inputs. Verify that blood
starts at the interrupted visual body position and that falling does not return
the body to its legal tile center. Do not mistake the missing fixture profile for
a renderer rule that suppresses blood on death, or invent a death multiplier.
