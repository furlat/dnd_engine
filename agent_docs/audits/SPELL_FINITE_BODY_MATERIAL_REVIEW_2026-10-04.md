# Finite current-pose material review — 2026-10-04

Verdict: bounded correction verified. Independent review; no production edits performed in this review.

## Finding

P2 — authored palette values are ignored by the two new material operators. game/condition_draw.py:122 hardcodes fracture dark/light RGB, and :145–146 hardcode wither base/scar/pulse RGB, although game/condition_types.py declares ConditionBodyRamp.colors and the necrotic recipes author those palettes. Current recipes happen to match the duplicates; editing an authored palette cannot change the displayed result. A direct pixel probe replaced fracture colors with green/blue and obtained identical RGBA bytes. Read colors from the existing material record and validate the exact supported palette cardinalities, preserving the accepted current output. This requires no new engine or asset.

The root correction now reads fracture base/crack from the two authored colors and wither dark/light/scar/pulse from four authored colors. Schema validation enforces those cardinalities. The original wither light endpoint is explicit in the recipe, preserving the accepted operator. Independently reran the focused suite after correction: 12 passed in 7.34s, including both authored-palette pixel regressions. The finding is closed.

## Bounded positive findings

- StudioBodyMaterialTrack/BodyMaterialPoint are frozen authoring data. Ordered finite points begin and end clear. Sampling uses the existing cast release clock and the existing application outcome selector; no native mechanics or duration owner were added.
- Blight/Harm/Circle recipes use existing admitted damage and save results. Immunity does not select recipient material. Per-recipient identities are derived from disclosed CastApplication records; no live registry lookup or time/target guessing enters the material sampler.
- Both relevant cast compilation paths extend finite completion through the selected material tail. The existing choreography clock therefore retains it through restoration instead of creating a second timer framework.
- Playback attaches sampled material to the currently presented body. Explicit pose overrides retain the same finite material tuple. _actor_blit evaluates on current composed pixels before scale/placement, so it does not cache a standing actor or replace current injury/death/Prone geometry. Shared actor draw splits the shadow and excludes it from this operator; original alpha and surface immutability are preserved by the pixel function.
- Import direction remains game presentation → cold animation/condition data and dependency-leaf native facts; no late import, native Entity lookup, event synthesis or per-spell dispatcher was introduced.

## Evidence and limits

Independently ran tests/game/test_necrotic_spell_delivery.py: 10 passed in 7.85s. It proves native save/immunity outcome selection and finite lifetime sampling for paired observers, plus exact alpha preservation/restoration on two synthetic silhouettes. Source inspection confirms current-pose wiring; these tests alone are not all-rig pixel/gallery acceptance. No rendering/capture job was started by this review.

Compared the Blight operator with the preserved accepted source /home/tommaso/Dev/neurodragon_art/sources/blight-lifecycle-20261004/review.js and its NOTES.md. The native port retains donor-noise UV coverage, patch/crack math, pulse color switch and current silhouette alpha contract. The preview's Wolf-only shoulder accent is not a generic approved new creature engine; current source review does not claim all demonstration pixels were copied exactly.

Scope: game/animation_types.py, animation.py, cast_media.py, condition_animation.py, condition_types.py, condition_draw.py, animation_draw.py, playback_frame.py, animation_data.py; game/data/necrotic_media/damage-draft.json and the focused native-derived delivery tests. Other packet implementations, new artwork and complete gallery acceptance are excluded.
