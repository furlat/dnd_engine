# Reused NeuroClient presentation data

This is the source import from [the recovery plan](../../../RECOVERY_PLAN.md#113-p1--import-source-data-and-export-what-already-exists-in-ts).
It supplies local inputs for the Python timeline evaluator, its detached Pygame
reference preview, and the finite integrated spell scene in `python -m game`.

- `source/` preserves the original JSON bytes and relative paths. This includes
  the larger action/condition/media inventory; importing those records does not
  activate every recipe or copy every referenced asset.
- `catalog-input.json` captures the selected native spell records: Fire Bolt,
  Acid Splash, Magic Missile, Invisibility, Greater Invisibility, See Invisibility,
  True Seeing and Misty Step. It is an offline input to the original TypeScript
  materializer, with no old server dependency.
- `spell-studio-drafts.materialized.json` is that materializer's output, still in
  Studio's version 6 format. Fire Bolt and Acid Splash retain their saved values;
  Magic Missile exercises the existing generated baseline.
- `bindings.json` also declares the finite `relocations` selection. These actions
  release an atomic recorded relocation through the shared compositor; the list
  does not supply an endpoint or decide whether an observer can see it.
- `rig-tables.json` exports NeuroClient's existing frame, direction and layer
  constants. These are the reference units of the root modular rig.
- `bindings.json` maps current spell IDs to exact authored references and original
  media URLs to local files. The selected 62 PNGs cover six clips for ten
  modular categories, Magic2's cast glow and Fire Bolt's projectile lifecycle.
  The clips are Idle, Attack5, Special1, TakeDamage, Die and Taunt. Taunt supports the
  existing authored recovery and equipment-transition contexts; the saved Fire
  Bolt recovery stays disabled. Melee1/Melee3 supply the original dagger and
  shortsword layers used by `python -m game --replace-weapon`.
  This resource selection is not a permanent character appearance or loadout.
- `provenance.json` records the input revisions, source dependencies and output
  hashes for reproducibility. Those hashes are an import check, not a new runtime
  authentication mechanism. Engine/exporter text hashes normalize line endings
  to LF; copied source JSON and images retain their original byte hashes. Narrow
  Git attributes preserve that distinction across checkout platforms.

Use the local resource bindings when consuming selected media. Absolute paths
inside original asset metadata describe source provenance and are not runtime
paths. Neither NeuroClient, Bun nor the original asset packages will be needed
to read these artifacts in the game.

Alignment is already part of these records. Reuse it when binding a new spell
or rig; the Pygame adapter does not own another alignment catalog.

Misty Step was added on September 18 by passing its native catalog row through
NeuroClient `d274f2d62ca9c1c5ed62a77841cacf6cc0347491`'s original
`backendSpellToCatalogEntry` and `createGeneratedSpellPresentationDraft`, using
Bun 1.3.14 only for this offline step. The native input comes from
`SPELL_CATALOG_METADATA_BY_CLASS[MistyStep]` and
`SPELL_CONTENT_DECLARATIONS_BY_CLASS[MistyStep]` in
`dnd/spells/catalog_content.py`. This narrow addition preserved the previous
seven materialized rows and all imported resources. No full import, asset audit
or provenance-hash regeneration ran.

The generated draft uses the existing `Special1` cast at speed 1, releases at
frame 8, hides held weapons and leaves recovery disabled. It has no projectile,
area or authored teleport media. The original Studio sources contain no saved
Misty Step override; the older proposal for endpoint swirls is not implemented
art. Runtime loading remains pure Python.

| Authored data | Existing consumer |
| --- | --- |
| Draft `projectile.sourceAnchor` and `sourceAnchorsByFacing`: forward, side and lift | `animation._anchored_points` selects the viewed facing and transforms its local offsets. |
| Draft source `axisPx`, target `liftY`/`forwardPx` | Existing endpoint binding applies the source-axis and target offsets. NeuroClient uses the global source axis separately from per-facing local offsets. |
| Draft sprite `anchor`, `offsetX`/`offsetY`; asset `anchor` and frame dimensions | `projectile_center_offset` resolves the sprite override or asset default for projection and drawing. |
| Rig origin, dimensions, facing rows and clip mapping | Actor drawing and projectile binding use the same retained rig and appearance scale. |

The scale adaptation maps those authored attachments from Studio's unit-scale
actor canvas to the displayed actor. Effect size, world support height and the
compiled clock remain independent. The Goblin reuses its existing 128px rig;
introduce another rig adjustment only when its actual art requires one, and keep
such authored adjustments in data rather than spell-specific drawing branches.

The terrace scene also supplies an explicit `CastApplication.travel_apex_steps=1`.
This frozen world-height adaptation lifts the path above the stairs and adjusts
projected fine rotation along its vertical tangent. Its generic default is zero;
it does not alter the imported screen-space trajectory, attachments or clock.

`--magic-missile` executes the generated draft: one Special1 cast, frame-8
release, three launches 80 ms apart and Bézier darts with repeated-target spread.
The draft has no damage override, so the original global vital context and the
packet's Force palette supply its reactions. Geometry uses the existing dart
style in the generated profile; no projectile atlas or impact burst is invented.
Its eight-point trail is sampled at a fixed 60 Hz reference cadence for seeking;
NeuroClient instead retained the last eight actual rendered frames.

Point geometry honors the draft's existing `tileCenter` basis in projection.
NeuroClient's shared helper forced a sprite-art root even for this geometry,
which put the generated dart near the feet. This explicit visual correction
keeps sprite canvas registration and the source timing calculation unchanged.
Geometry depth also keeps interpolated authored `liftY` in visual height rather
than mistaking it for motion across the floor. Forward/side offsets and the
screen curve retain their planar meaning.
The original JSON remains byte-for-byte preserved. These generic anchors do not
establish a separately authored hand pose for every rig and facing.

Regenerate from the pinned NeuroClient checkout using the project environment
and a native Bun executable:

```sh
.venv/bin/python -m devtools.import_neuroclient_presentation \
  --source-app /path/to/NeuroClient/app --bun /path/to/bun
```

Add `--check` to reproduce and compare without writing. `--output-root` can
direct a candidate into a separate directory. Do not hand-edit generated files;
make a deliberate source/adaptation change and regenerate. The importer owns
only its enumerated output files.

P2 executes selected casts with controlled elapsed time and compares intermediate
states with NeuroClient's recorded runtime. Use `python -m game.animation_preview --recovery`
to inspect the existing recovery option. Resource and source parity
alone do not establish timing, event disclosure or gameplay correctness.

The runtime derives its root body-rig binding from these exact tables and media
URLs. Additional packaged rigs have separate explicit bindings under
`game/data/rigs`; they do not modify this imported authoring set. The Goblin 01
recipient proof runs with `--target-rig smallscale.goblin01`. Height and camera
controls use `--target-height-steps 1`, `--quadrant`, and Q/E.

## Body releases and selected workshop rigs — September 19

`body-release-assets.json` reuses NeuroClient's `actionMediaAssets` version 1
records (`assetId`, `source`, `frames`, `directional`). The four new selected
records refer to local `BodyRelease/*` strips through `bindings.json.resources`.
`body-release-bindings.json` is the small local mapping from permitted semantic
release IDs to the existing Studio media-track type. Its tracks use the original
assetId/attachment/tint/startFrame/fps/loop/reversed/scale/offset fields; there is
no alternate event executor or native particle specification.

The Python adapter currently selects one-shot body strips. It samples absolute
time at the containing damage/contact anchor and uses the held historical actor
contact. Drawing follows Studio's bottom-center body overlay convention, inherits
rig origin/body lift/scale and camera projection, and leaves the source white tint
unchanged. This port does not claim support for every Studio ground/loop/two-color
media variation. Persistent floor marks use `world_bindings.json.residue_ground`;
bloodied spikes use `residue_overlays` and the existing trap frame.

Selected art provenance:
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/body-residue-v2/exports/body-residue-manifest.json`.
The accompanying HANDOFF describes the source/export geometry. The runtime uses
only the selected copied PNGs, never that worktree or manifest. Four floor views
per material use variant 1 (ordinary blood small; other profiles default), pivot
(128,208), scale 1. The 128px-cell strips run at 24 fps: blood 18 frames, bone,
corrosive and dread 12 each. Terminal frames are transparent. Medium/pool blood
and other delivered variations are not bound until their native state is authored.

Demon Beast 2/3 use separate selected rig JSON under `game/data/rigs`, preserving
body/shadow separation and recording archive provenance there. The fixed skeleton
archer keeps its existing `5Archer` mapping. `bindings.json.root_creature_content_refs`
explicitly selects the modular root rig for the skeleton warrior. Its real body
and disclosed gear resolve normally: Body2, armor scraps, longsword and shield.
The selected 14 Body2 sheets and 42 Legs9/Chest15/Shield7 sheets were copied
unchanged from `/home/tommaso/Dev/NeuroClient/app/public/spritesheets`. The fixed
`6Warrior` spear artwork is deliberately not used for this longsword creature.
These are finite additions to the shipped resource selection; no startup source
scan or file-integrity audit was introduced.

### Approved independent blood particles (integration in progress)

`body-release-particles.json` is a portable media-asset extension for the existing
Studio `particles` track role. It contains the exact 96 particles from the approved
`blood-fluid/approved/a-lot-v1/particles.json`, exported by the environment artwork
task at `/home/tommaso/.codex/worktrees/23a9/dnd_engine`. The authoritative appearance
and units are documented in its `blood-fluid/APPROVED-PRODUCTION.md`. Source values
are copied once; the game reads only its local JSON. There is no runtime source
audit, random regeneration, TypeScript dependency or additional clock.

XY and Z are world-tile units, delays/lifetimes are seconds, and the palette,
tail lengths and pixel snapping preserve the approved procedural rectangles.
The finite media track uses the actual injury/contact time. Its absolute sampler
rotates world coefficients toward a disclosed attacker-to-victim direction;
an unavailable source uses the canonical art direction without a native lookup.
Individual droplets enter the ordinary world painter ordering, including the
historical actor's held position and height. Other body substances still use
their authored sprite strips.

At this earlier integration checkpoint, production blood bindings remained on the previous artwork until the persistent
floor footprint is settled. The approved field spans multiple tiles at its real
scale; it must not be squeezed into one tile. Native ordinary blood now retains
amount 1–5 on its existing condition, one unit per qualifying release. Seven-hit
saved replay confirms the cap and persistent identity from both participants.

## Current directed blood — September 20 visual correction

Production `body-release-bindings.json` now selects `particles.region.blood`.
Its material row in `body-release-regions.json` overrides the common compact
templates with four 56-droplet distributions exported from the original
`blood-fluid/approved/high-v{1,2,3,4}`. Source conversion:
`output/environment-sprites/high56-region-replacement/blood-only-high56.json`
in the environment-art task. The shared normalization basis is centered at
`(.5, 0)` with radii `(2.5, 1.7)`. Rotated kernel shapes were transformed as
quadratic forms, preserving the original full-size lobes and satellites.

Ordinary blood's native profile supplies wider receiving geometry; original
particle goals, lifetimes and delay variation then fit that recorded region.
The same existing sampler/floor painter consume it. Tails are authored at
35ms, 3–12px and 2px snapping. The media lasts 26 frames at 24fps so its slowest
critical particle can land. Bone/corrosive/dread retain the original common
28-particle templates and compact gameplay coverage; poison remains art only.

This is a moderated adaptation, not an exact replay of the original A lot96
preview. Sources remain at the historical wound attachment; existing
accumulation scales lobe offsets as well as radii. Both the templates and fully
resolved media values are JSON data usable by a future TypeScript consumer.
The loader resolves optional per-material values once; there is no additional
clock, particle entity or runtime dependency on the art task.

## Weapon motion corrections — September 20

`attack-profiles.json` is locally authored using the original `AttackVariant`
records, shared explicitly by normal, extra and opportunity attacks. Weapon
identity/outcome overrides precede physical damage-type defaults. A dagger
critical uses the overhead strike; morningstars swing despite piercing damage.
Critical and elemental modifiers no longer universally replace weapon motion.
Contact anchors and onHit/onMiss/onCrit effects remain in the same record.

The only match-format extension is optional `sourceItemIds`: direct stable item
IDs already present in player attack facts. Historical `sourceItemRefs` still
load, matching their content ID as before. Local data does not author new
contract hashes. A TypeScript consumer can add this optional array to the
existing match type and predicate; there is no Python-only weapon dispatch.

The generic offhand Attack5 remains its authored left-arm strike. This change
does not claim an offhand thrust or complete fixed-creature clip coverage.
