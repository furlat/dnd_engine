# Reused NeuroClient presentation data

This is the source import from [the recovery plan](../../../RECOVERY_PLAN.md#113-p1--import-source-data-and-export-what-already-exists-in-ts).
It supplies local inputs for the Python timeline evaluator, its detached Pygame
reference preview, and the finite integrated spell scene in `python -m game`.

- `source/` preserves the original JSON bytes and relative paths. This includes
  the larger action/condition/media inventory; importing those records does not
  activate every recipe or copy every referenced asset.
- `catalog-input.json` captures three records from the current D&D content owner:
  Fire Bolt, Acid Splash and Magic Missile. It is an offline input to the original
  TypeScript materializer, with no old server dependency.
- `spell-studio-drafts.materialized.json` is that materializer's output, still in
  Studio's version 6 format. Fire Bolt and Acid Splash retain their saved values;
  Magic Missile exercises the existing generated baseline.
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
