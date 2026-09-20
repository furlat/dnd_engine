# Ad hoc visual comparison of saved gameplay

Date: 2026-09-20.
Status: deferred idea, not an implementation plan or a required cleanup step.

The user's decision is to revisit this **ad hoc when visual changes become
difficult to assess**. Do not build a framework, add a routine test gate, or
expand the graphics cleanup to implement this now.

## Purpose

When a shared rendering change is hard to review, replay selected saved event
sequences before and after it and inspect differences in the rendered images.
The approved result is what appeared on screen, including runtime transforms
and media processing, not just the JSON values used to produce it.

Keep approved clips, unreviewed captures and known defects distinguishable.
Current output is not automatically an approved baseline, and intentional visual
changes must not silently overwrite a reference.

## Reuse what exists

`devtools/animation_review/capture.py` records real gameplay inputs, including
subjective perspectives. `cli.py` can replay those saved inputs without running
the encounter again. `record.py` renders four camera views together and already
obtains raw image pixels before sending them to the video encoder. Existing
gallery selections and traces provide scenario identification and diagnostics.

A future comparison should extend that path only as needed. It must preserve
complete subjective lineages and use the ordinary presentation implementation.
Do not create a second renderer or substitute fabricated events. A graphics
comparison should keep its saved inputs fixed; gameplay changes are tested
separately and may require deliberately recording new inputs.

## A useful comparison

- Select cases relevant to the suspected regression. Keep all four camera
  corners, and both subjective participants when perception differences matter.
  Avoid a Cartesian product of every spell, observer and configuration.
- Reuse fixed framing, viewport, timing and initial presentation settings.
  The current recorder automatically fits camera bounds using scene/effect
  extents; independently fitting before and after can move the entire image.
- First establish repeatability by replaying the same input twice in the same
  environment. Deterministic events alone do not guarantee identical pixels.
- Compare raw pixels or lossless images, not compressed MP4 files. Existing
  approved videos remain human references; they are not exact raw-pixel baselines.
- For placement and colour, a few fixed timestamps may suffice. Jump loops,
  interrupted movement and opportunity attacks need consecutive frames to catch
  transient resets or snapping. Keep baseline timestamps fixed: sampling only at
  each revised animation's new contact time could conceal a timing regression.
- Show expected, actual and difference images with scenario, observer, camera
  and timestamp, linked to the existing trace. Keep review-only labels separate
  from scene comparison without hiding gameplay text or effects.

Differences are evidence to inspect. Pixel equality does not prove mechanics,
visual quality or absence of bugs. Avoid broad tolerance thresholds that can
hide a small missing projectile. Exact equality may suit controlled Pygame
refactors; a future NeuroClient port can reuse inputs and timing expectations
without requiring identical rasterization across rendering engines.

## Keep the cost proportional

Work grows with scenarios × perspectives × four cameras × sampled frames.
Rendering, reference-image I/O, trace collection and video encoding all cost
time; pixel subtraction is only one part. No performance claim has been measured
for a proposed comparison mode.

If a concrete problem warrants it, measure a small selection first and separate
setup, playback/rendering, comparison and output costs. The recorder currently
couples rendering with video encoding, so bypassing encoding would require some
plumbing. Save useful failure evidence rather than automatically generating
another full gallery. Do not jump playback directly to a timestamp if doing so
would skip required presentation progression.

No hashes, source audits, asset validation passes, normal-game overhead or
mandatory full-catalog runs. Prefer existing side-by-side clips when they answer
the question. If this later becomes an implementation proposal, apply the usual
anti-slop and anti-OOP reviews before expanding it beyond the concrete need.
