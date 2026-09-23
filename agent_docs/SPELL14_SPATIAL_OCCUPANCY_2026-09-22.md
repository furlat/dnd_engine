# Spell14 spatial graphics versus native occupancy

## Final spell result

The delivered maintained volume families now pass production-art registration
checks in all four cameras. Insect Plague, Cloudkill, Incendiary Cloud, Fog
Cloud and Stinking Cloud use their native 20-foot radius; Darkness uses 15 feet.
Every source pixel admitted by the actual observed native cells survives, and
no rendered piece belongs to an ungranted cell. The Cloudkill wall case excludes
13 cells. Native footprint admission, rather than enlarging a screen image,
controls the rendered field.

Fog base/upcast/raised checks additionally cover both observers: 49 cells at
20 feet; 157 map-bounded cells at 40 feet; and native elevation 2 on the raised
support. Upcast scales color, pivot and raw world coordinates together.
See the [final numeric and visual evidence](../.runtime/spell14-20260922/final-volume-registration/REVIEW.md).

The barrel findings below remain a separate, queued source correction. The
user explicitly asked to finish spells and include the existing barrel clips
in the feedback handoff; no replacement barrel artwork was installed here.

## Initial ground and barrel measurements

The audit used actual serialized player event sequences after native teardown, then rendered the retained occupied cells in all four cameras. It changed no gameplay rules or production art. The temporary diagnostic and captures are in [occupancy-result.md](../.runtime/spell14-20260922/occupancy-result.md); that report contains all eleven four-camera sheets, replay inputs and per-cell measurements.

Spell Grease registers correctly over its four native cells: 90–96% whole-cell coverage, and 100% coverage of every cell-center neighborhood, across all four views. Its source ground basis is64/32;  binding scale 0.5 cancels runtime TILE_WIDTH/rig.TILE_W=2, leaving the common camera zoom. Cube origin offset(-0.5,-0.5) places the source square on the exact native cells. [Grease sheet](../.runtime/spell14-20260922/occupancy-grease.png).

Spike Growth registers one independently sorted clump in each of its 49 native cells. No duplicate, missing or out-of-footprint clump owner was found. Its upright foliage is not a filled floor material; a ground-opacity percentage would mischaracterize it. [Spike Growth sheet](../.runtime/spell14-20260922/occupancy-spike_growth.png).

Barrel water, oil and Grease all use the correct source 32/16→runtime 64/32 single 2× registration. All three authored variants reach all nine native cells, but some hazardous cell centers are visibly dry. Measuring a central 0.25×0.25-cell footprint rather than one antialiased pixel found:

| Material | Seed 0 minimum center coverage | Seed 1 minimum | Seed 2 minimum |
|---|---:|---:|---:|
| Water | 28.66% | 0% | 17.20% |
| Oil | 0% | 0% | 11.46% |
| Grease | 0% | 0% | 10.19% |

These are alpha>=32 percentages, around 157 sampled pixels per center at camera zoom 0.75. Seed 1's offset (+1,+1) center is completely dry in every camera for all three materials. Oil/Grease seed 0 also leave offset (+1,-1) almost completely dry. This is a concrete readability mismatch where a centered actor can stand on apparently dry ground and receive the native surface effect. Rounded empty outer corners alone would not establish this defect.

The approved original handoff explicitly describes irregular **partial** nine-cell coverage; production has preserved it. Request a bounded source geometry correction so the material plausibly reaches all nine occupied centers while retaining an irregular outer silhouette, palette, timing and four-camera registration. Keep the native nine-cell footprint. Do not add an arbitrary renderer multiplier or stretch cropped frames: that would move source pixels into clipped neighboring cells and disturb registration.

Source contracts: `delivery-terrain-cameras-v1/HANDOFF.md` and `delivery-liquid-depth-v1/HANDOFF.md` in the Godot worktree's `output/weapon-vfx/`. The latter preserves `delivery-liquid-spills-v1/HANDOFF.md`'s accepted appearance. Source geometry correction has been reported to the coordinating task; no replacement art is claimed in this audit.

The comparison is an ad hoc diagnostic, not a new visual testing framework. Every material variant was displayed over the same actual retained native state by selecting its explicit presentation binding. Per-cell clipping, visibility and native admission remained in the normal rendering path. The full values and saved inputs support repeating the comparison when corrected assets arrive.
