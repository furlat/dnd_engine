# Selected spell handoff

These local data and PNGs connect the September 19 delivered assets to the existing
Studio recipes. Runtime needs Python/Pygame and these files only. Frames are read
on demand through the shared bounded cache; no atlas, authoring project, source
audit or file hash is loaded at game startup.

Source task: `/home/tommaso/.codex/worktrees/1aac/dnd_engine`.
Read its `docs/SPELL_VFX_HANDOFF_2026-09-19.md` for provenance and art limitations.
Selected inputs under `output/weapon-vfx`:

- `spell-recovery/release/manifest.json` and each spell's phase/direction PNGs.
- `spell-recovery/caster/manifest.json`, including measured source-pixel sockets.
- Isolated Guiding/Eldritch `caster/*-weaponGlow.png` sheets. Body/clothes previews
  are deliberately excluded; the actual actor layers remain in use.
- `library-selection/release/shared-fireball-20ft.json` and the individual
  `fireball_b`, `fireball_smoke`, `fireball_explosion` frames. Giant combined
  strips and page duplicates are excluded.
- Acid's original `public/spritesheets/Magic3/Special1.png` from NeuroClient.

The selected copy contains 5,203 PNGs, about 147 MiB on disk. All point frames
retain 256px centered cells and scale 0.5. Their exact phase counts/FPS remain:
Acid 12/24 travel and 115/144 impact; Guiding 12/24 and 63/144; Eldritch 72/144
preparation, 144/144 travel, 116/144 impact. Eldritch travel and preparation
footprint reductions are already baked. No second scale reduction is applied.

Fireball's travel is 256px, 12 frames at 24FPS; impact is 1536px, 48 at 24FPS.
Separate asset records preserve these different cell sizes. Smoke draws with
normal alpha before additive fire at identical scale and contact. Both delivered
layers include ground shapes and need physical wall masking. They are not a
certified separate elevated-smoke pass.

Following game review, Fireball travel uses 360 Studio pixels/second (twice the
initial binding), retaining the 150ms minimum. Its phase-local `scale: 0.6` is a
20% increase over the inherited 0.5. Impact remains 0.5, preserving the authored
20ft explosion. Phase scale is an optional presentation adaptation used by both
the shared painter and canvas-anchor registration.

Fireball's optional `area.surfaceReveal` selects `residue.ashen` and spreads
recorded surface changes at 10 tiles/second from its recorded ground contact.
The center commits at impact, reaching 20ft in 400ms. This approximates the
expanding artwork; there is no measured radius curve in the delivered media.
Only actual permitted world updates are timed; repeat hits with no new condition
changes keep their previous marks. Damage, HP feedback and condition lifetimes
retain their existing ownership.

Acid retains its original Special1 recipe with the inappropriate late Effect1
disabled. Guiding and Eldritch adapt the existing FireBolt Attack5 recipe as the
handoff specifies. Fireball also uses that available gesture; this is a local
adaptation, not a claim of a distinct authored Fireball caster recipe. Its area
record reuses the original generated Studio shape defaults with geometry media
disabled. Native area facts provide the actual ground target and affected tiles.

The optional source socket, precolored sheet, volley-pose hold and overlapping
preparation fields are explicit serializable presentation adaptations to Studio.
They do not change native events. Eldritch's candidate recipe uses 160ms between
beams, release pose 7 held through the volley, and a 500ms preparation starting
at body frame 4. All phase FPS are source FPS; the detached preview's optional
0.8 impact speed and 83ms arrival hold are not baked into these assets.

The selected point spells target each rig's explicit `body_anchor`, independent
of the cast hand sockets and ground endpoint. Modular/Goblin source128 bodies
use (64,72); the fixed skeleton/demon/wolf records retain their own inspected
source-pixel torso points. Wolf uses a64px cell and a(32,34) anchor. These values
are authored attachment data, not a universal target offset derived from the
preview goblin. Fireball continues to target its native ground contact.

Point spells retain Studio's `isometricHybrid`: select the actual authored
directional row, then rotate by the residual angle to the hand-to-body path.
This applies to travel and impact; preparation stays on its authored facing.
The initial importer incorrectly disabled this by copying a canonical-direction
preview's omission. The canonical recipe preserves the original setting; media import does not edit it.
Fireball's ground effect keeps its authored flat orientation.

Reimport from the same delivered source directories with:

```sh
uv run --no-sync python -m devtools.import_spell_recovery \
  --vfx-root /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx \
  --neuroclient-app /home/tommaso/Dev/NeuroClient/app \
  --color-revision /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/color-revision
```

This offline command copies media and updates packaging metadata only. The
required color-revision input selects the accepted pixels during every import.
`spell-studio-drafts.json` is authoritative authoring: timing, sockets, scale,
colors and source-sheet choices are never reconstructed from another spell.
Resource bindings for baked sheets and the Fire Bolt override survive reimport.

## Exact spell palettes — September 20

The accepted Fireball/Eldritch color revision occupies the existing 3,520
phase-frame paths. Counts, alpha, registration and wall/area bindings stay the
same. The normal importer requires the revision directory; the standalone
`devtools.import_spell_color_revision` remains a media-only update command.

Recipes declare target treatment in `damage.hitFlash.palette`, including the
approved contact frame 0 / 150ms flash. The casting layers separately declare
`palette` (offline bake input) and `sourceSheet` (already-colored runtime output).
Chill's casting layer deliberately uses its full palette; its target treatment
uses dark colors and source noise. Body/clothes are never part of the casting
bake. These values are authored choices, not decisions made by a packaging tool.

Rebuild declared casting sheets from local source layers with:

```sh
uv run --no-sync python -m devtools.bake_spell_palettes
```

Use `--draft-file game/data/ice_spells/spell-studio-drafts.json` to select only
one bundle. The baker writes PNGs to the declared resource locations and does
not edit recipes, bindings or hit timing. Magic Missile has no casting overlay;
its target palette remains ordinary authored data. The original NeuroClient
materialized file stays a reference; selected overrides live in local bundles.

See [the presentation contract](../PRESENTATION_CONTRACT.md) for format identity,
ownership and the small shared execution rules needed by a future TS adapter.
