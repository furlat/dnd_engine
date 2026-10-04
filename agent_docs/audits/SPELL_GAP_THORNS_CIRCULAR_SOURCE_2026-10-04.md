# Circular Thorns source integration — 4 October 2026

Implemented the G4 amendment in `game/thorns_surface.py` and
`game/wall_assembly_media.py`. The accepted 10ft-radius, 10ft-height ring now uses
the same original geometry/material painter as straight Thorns. No assets,
schemas, recipes, native rules or additional renderer were introduced.

Original source:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/wall-spells-study/thorns-modular-completion/ThornsModules.gd`.
SHA256: `7b9050cc3971bb28a119b22143770635757524f245169344f950ca88e6d3d6b5`.
Existing installed components SHA256:
`87675e17140bff801f808e786d80bb19d4416f1661204081091a8fe9bf6fb2d1`.
The source capture driver explicitly selects sixteen modules for `circle`.

The added branch retains the literal source changes:

- Circular slots shift each original module by `(index+.5)*CELL`, preserving
  its own interior variation, UVs, normals and slot when other modules disappear.
- After the existing living deformation, `theta=wp.x/(16*CELL)*2*pi` and
  `radius=2*CELL+wp.z`; X/Z become `sin(theta)*radius, cos(theta)*radius`.
- Normals receive the original circular world-normal transform. Straight
  heading behavior and lighting remain unchanged.
- Existing formation sampling, two-second clock, retirement, texture/dissolve
  sampling, palette pass and current-actor influence remain shared. Circular
  proximity uses distance to the ring centerline; actual dated damage retains
  its existing source-local pull and expiry.

The assembly consumer selects only received physical source sections. Each
fixed sector's endpoints define its section for the existing shell-cell
admission calculation, intersected with the actual native ring shell. This is
the same section-level disclosure policy used for straight Thorns; it does not
replace curved rendering with straight segments or clip elevated overhangs to
their ground cells. Current XYZ painter exclusions still own suppression and
occlusion. An empty received selection emits no geometry. The whole-ring RGBA
fallback retains its complete-shell guard; only the original component path
supports partial received sections.

The cache uses the actual center, optional straight tangent and source length
as immutable primitive arguments. Native geometry models and their existing
hash/equality/serialization contracts are unchanged. Exact registered radius,
width and height checks still gate this source; this does not add arbitrary
ring-size support. The visible original leaf tips are not flattened to a new
geometric height.

Validation artifacts are under `.runtime/spell-gap-20261004/thorns-circular/`:

- `parity-final.log`: six straight vertex/normal/UV/triangle/dissolve array
  comparisons are unchanged from the saved pre-change sampler; 144 circular
  vertex/normal samples match independently evaluated literal source equations
  across all sixteen modules during formation, hold and retirement.
- `typing-final.log`: zero errors and warnings for both renderer modules and
  their unchanged native geometry types.
- `tests.log`: four existing actual-damage/contact replay checks plus the
  existing native ring replay passed, 5/5 in 33.02 seconds.
- `tests-final.log`: final-signature rerun of existing actual-damage/contact
  checks passed, 4/4 in 17.48 seconds. Parent-owned expanded G4 tests cover partial shell,
  suppression, cyclic hold, retirement and retained source variants.

No missing circular source contract was found. Normal engine gallery and
independent acceptance remain with the parent/reviewer lanes.
