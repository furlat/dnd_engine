# Recovered spell batch: implementation result

Branch: `codex/recovery-design`. The user authorized integration of the frozen
seven-spell handoff and fixes to its actual implementation. Existing uncommitted
Sleep, cannon and earlier gameplay work was retained.

Sources: [frozen intake](SPELL_BATCH_RECOVERY_2026-09-20.md),
[reviewed implementation plan](SPELL_BATCH_IMPLEMENTATION_2026-09-20.md),
[portable presentation contract](../game/data/PRESENTATION_CONTRACT.md).

## What is integrated

| Spell | Presentation and native behavior exercised |
| --- | --- |
| Sacred Flame | Ground-registered golden column, Special1 invocation, release-aligned damaging contact, back/body/front layers; successful and failed saves, adjacent and 60-foot targets |
| Shocking Grasp | Moving palm charge, actual touch hit/miss, lingering registered target arcs following TakeDamage; native No Reactions condition remains a separate fact |
| Poison Spray | Compact local smoke through the existing palm-to-body projectile, then local dissipation; fixed pixel size, exact palette and unchanged native single-target save/damage clock |
| Burning Hands | Selected whole cone, existing native footprint, actual successful/failed saves and fire damage; shared physical area compositor |
| Thunderwave | Selected naturally authored purple crest in lossless packed depth parts; native axis-resolved cube, per-recipient contact, damage and complete child pushes including diagonal and blocked endpoints |
| Gust of Wind | One traveling front, then thin maintained ribbons from an observed native zone; real next-turn saves/pushes and concentration removal; axial, diagonal and blocked cases |
| Web | Frozen v11 flight/deployment/rest artwork, identical final deployment/ground pixels, exact condition-driven back/front wraps, real saves/escape/movement, mage concentration and device-owned zones/destruction |

These are shared data/execution additions, not seven Python drawing branches.
`StudioMediaTrack` attaches finite art to a registered source hand, source ground,
target body, target ground or area ground. It uses the existing cast body and
application timeline. `StudioContact` describes presentation arrival; resolved
native results remain authoritative. Recipes own release, palette and phase
values. Importers copy media and registration without rewriting those recipes.

The renderer still processes recorded player inputs without an engine. Camera
rotation never changes damage/contact/condition time. Source-specific Web
membership is preserved through native observation and public replay; generic
Restrained is not sufficient to acquire Web silk.

## Demonstrated implementation fixes

- Forced movement previously counted a diagonal grid step twice in its reported
  distance. Reporting now counts actual successful five-foot steps; endpoints,
  collision policy and movement cost rules were not redesigned.
- Gust's initial unsnapped direction and persistent snapped direction disagreed.
  Its zone now retains the actual direction used by the cast.
- A real later Gust turn could push the caster, relocate its anchored field and
  fail near the map boundary. Ongoing application now respects the initial
  cast's existing caster exclusion, while other occupants still save and move.
- The selected area spells retain their resolved native cells for replay. Gust
  exposes its existing zone through the same admitted spatial observation path;
  the disclosed geometry provides its actual origin/direction.
- Web's source-owned restraint supplies an exact status/public label while its
  mechanical source UUID remains distinct. Escape/removal of one source does
  not remove another source's wrap membership.
- `SpellFact.attack_outcome` carries admitted native hit/miss outcomes. A missed
  Shocking Grasp keeps its hand charge without painting target arcs or damage.
- Registered sparse rectangles share rounded canvas edges, fixing real one-pixel
  seams at fractional zoom without changing source RGBA or pivots.
- The initial Poison endpoint fit was rejected on visual review: it stretched
  the whole cloud to bridge the distance. The correction below restores the
  export's fixed scale and removes that unnecessary fitting schema/code.
- Exact Thunder contact maps now serialize to ordinary JSON, including nested
  immutable lookup data. Their recipe roundtrip is tested.
- Web's natural field fringe has stable authored owners. Native remembered
  interior cells retain the existing memory treatment; fringe requires visible
  receiving support. Gust uses the declared full discrete line as its stable
  owner lattice, so diagonal gaps do not cut the natural silhouette and removed
  cells cannot lend their pixels to surviving neighbors.

An initial uninitialized discovery probe suggested missing spell registrations.
Normal initialization already supplies them. The proposed duplicate owner
registrations were removed; the existing catalog remains their single owner.
Two older Fireball tests also treated every combat-log child as a spell recipient;
they now assert recipient save identities separately from legitimate Ashen tile
condition entries, preserving their damage, cost and target assertions.

## Review evidence

The [combined gallery](http://127.0.0.1:8767/runs/20260920T181212Z-57aaae/index.html)
completed **40/40 cases** without reported media gaps. This is capture validation,
not a claim of human visual approval; the user subsequently flagged slow Web
deployment, addressed below.
The catalog contains 20 native experiments / 40 subjective clips, each with four
camera views. New cantrip scenarios cover near/far, axial/diagonal and hit/save
or miss outcomes. Area scenarios contain saved and failed recipients, an outside
actor and blocked-push variants. Gust includes an actual subsequent turn and
ending concentration. Web's cannon sequence sustains two areas and then breaks
the cannon through an actual Attack Object action.

The record-only setup generated missing inputs once. The final gallery command
reuses their public bytes:

```sh
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m devtools.animation_review \
  --case 'batch-*' --case 'spell-web-*' --fps 24
```

Review framing shares the runtime registration function. Its offline envelope
keeps Sacred's column and Gust's long field under the header in all four views,
with one fixed camera setup per clip. Poison uses the existing actor framing
option: its oversized transparent source canvas should not shrink the reviewed
characters. No new visual-regression framework or pixel hashing was added.

Completed checks (overlapping batches):

- 131 native/replay cases, including the existing spell-family module and device
  concentration/destruction, selected saves/pushes and both-observer cantrips.
- 59 focused Web/Gust/persistent condition and field regressions.
- 15 direct/area media cases, plus two real capture/framing regressions.
- Selected changed Python modules and tests: Pyright clean.
- Full game suite: **1,362 passed, 6 existing expected failures**, in 647.44 s.
  The six expected failures still describe the documented terrain occlusion
  defects during jumping/forced movement; no ordinary test failures remain.
- After the last shared animation guard change: **72 passed** across cantrip,
  animation and area media contracts, in 9.44 s.
- `git diff --check`: clean.

Their counts are not an additive total.
Independent anti-slop and ECS reviewers approved the plan and final shared
anchored-media implementation. Final ECS review also approved exact-created-zone
intro suppression, retained spatial ownership and Web memory preservation.

A fresh WSL process with source on `/mnt/c` measured animation imports at 0.872 s
and selected authored-data loading at 0.369 s (23 drafts). This is a local timing
observation under concurrent test/render work, not a new startup budget. No asset
SHA/checksum/source audit runs in that path.

## Honest limits

### Web timing follow-up

The user reported a slow projectile-to-expansion transition in the combined
gallery. Source pixel inspection and replay agree: the projectile remains visible
through its last frame, and native restraint/field creation already occur exactly
at projectile contact. The deployment's tiny seed grew to 10% coverage only after
roughly 396 ms and half coverage after 660 ms. This was authored pacing, not an
event queue delay. Source frame 189 already equals final frame 287 in every pose.

The existing Web field binding now plays at 288 fps and settles at frame 189:
roughly 330 ms to half coverage, 656.25 ms to the unchanged resting field. All
source frames remain imported; the redundant static tail no longer prolongs the
action. No gameplay, event timing, shader or special executor changed. A focused
replay uses the same saved mage/cannon inputs from both perspectives and all four
cameras. The [Web pacing gallery](http://127.0.0.1:8767/runs/20260920T182407Z-9ce5be/index.html)
passes **4/4 clips**; before/after contact frames were visually inspected. Focused
deployment, field/fringe, source-owned condition and projectile checks pass
**45/45 in 23.12 s** after this data change. The review server returns HTTP 200.

### Poison scale correction after user review

The user reported that Poison Spray looked zoomed up, with pixels much larger
than the export. The runtime overrode the authored scale by dividing the real
palm-to-target distance by a reference vector measured from the one-tile preview.
The maximum-range saved cases enlarged the raster by 2.63–3.92 times, depending
on camera direction; several adjacent views were also enlarged. The export's
`preview.js` draws the full puff at fixed scale 1 and rotates it toward the body.

The bounded correction removes `targetVectorByFacing` and automatic fitting.
The existing `.5` rig-space scale now remains effective (1:1 world/source pixels
before camera zoom). The existing facing-vector helper supplies canonical row
orientation; fine aiming still includes target height and noncanonical angles.
No native action, event, timing, image filtering or spell-specific branch changed.
Anti-slop and ECS reviewers independently approved this correction and required
checking reach separately. The old endpoint-equality test encoded the incorrect
fit; its replacement checks authored scale, exact palm anchor and body aim at
near/far/raised/noncanonical placements in all cameras and two supported zooms.

The [eight-clip replay](http://127.0.0.1:8767/runs/20260920T183008Z-b2ce3d/index.html)
passes all capture checks and uses the same saved public input bytes, including
both perspectives and all four cameras. Visual inspection confirms export-sized
particles. It also exposes the separate range limitation that fitting had hidden:
at the ten-foot target, the small puff is still short when the current 400-ms
contact flashes, then reaches the target later. Adjacent contact remains aligned.
That replay was recorded as unresolved visual arrival, not a gameplay-rule change
or a successful full-range timing fix. A bounded source/contact handoff was sent to
the existing Godot task; the user subsequently prioritized it ahead of the new
support-spell batch. The task has the exact recipe, per-facing source-frame time
maps, actual five-/ten-foot placements and saved-input reproduction command.
No new VFX was authored here.

Initial scale-only checks: **102 passed in 15.73 s** across cantrip, animation, area
media and projectile contracts; selected changed modules/tests report zero
Pyright errors. `git diff --check` is clean. These checks protect scale and
registration; they do not certify the unresolved maximum-range visual arrival.

### Poison range/contact integration complete

**Superseded after human motion review.** These measurements established size and
one-frame contact, but missed excessive post-contact travel and whole-stream
rotation in close overlapping views. The [delivery correction](POISON_DELIVERY_CORRECTION_2026-09-20.md)
replaces this candidate through the existing projectile system, removes its
distance-calibration extension, and records the new 8/8 gallery and 90 passing
focused tests. The history below explains the rejected intermediate result.

The frozen `poison-range-v3` candidate is now selected from
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/poison-range-fix/delivery/`.
The artist preserved the smoke texture, particle size/count and palette, corrected
emitter orientation/forward velocity, and supplied measured source contact rows.
The logical canvas grows from 512 to 1280 only through transparent padding at the
same pixels/world-unit ratio. Runtime uses eight compact sparse atlas pages;
the 12.36-MiB replacement replaces 48 unreferenced sheets totaling 23.22 MiB.
The importer copies only media/registration, preserves other assets and recipes,
and never consumes the delivery's checksum inventory. Contact rows are explicitly
authored in the recipe, replacing the old fixed time maps.

The independently reviewed sampler interpolates the measured contact frame using
fixed-scale source distance. Start/contact/end frames follow the existing finite
timeline; all eight saved inputs and their compiled release/contact timestamps
are unchanged. A 1e-7 source-pixel tolerance handles reproduced floating-point
roundoff at a measured endpoint, without extrapolating beyond authored coverage.

The [final eight-clip gallery](http://127.0.0.1:8767/runs/20260920T191252Z-4269df/index.html)
passes **8/8** and reuses the same real event bytes. Near/far, axis/diagonal,
both participants and all four cameras are included. Root and the art task
independently inspected contact frames: maximum-range puff/body contact is now
visible at the shared hit time with the small export pixels retained. This is
agent review, not a substitute for the user's final visual approval.

Final validation: **117 focused tests passed in 10.35 s**, selected Pyright clean,
including media-only reimport preserving authored behavior and literal pixels,
fixed scale/hand anchor/aim, calibration interpolation/JSON/seek/clock, and real
rendered contact in **48 attachment probes**. Elevation -1/0/+1 variants check
registration, not newly captured native eligibility. The rendered contact test
asserts visible high-alpha pixels at the body; source-space density thresholds
cannot be copied verbatim onto the rotated screen pixel grid. Explicit authored
distance limits remain; no arbitrary unsupported geometry or other rigs are
claimed covered. This resolves the earlier gallery's demonstrated range failure.

### Other supplied-art limits

Gust's supplied export is a three-second demonstration. Its maintained interval
is frames 252–359, 144 fps: thin/faint ribbons with a visible 750-ms loop seam.
The initial traveling front is not replayed. Native observed removal ends the
field immediately. This is not claimed to be newly authored seamless art.

Web remains the user's frozen v11 candidate; its projectile-to-ground shape
change is still perceptible. The integration preserves that selection.

The existing 53-degree cone and widened discrete line policies remain native
rules. Art may organically extend beyond those occupancy shapes; the renderer
does not create extra recipients or manufacture a mathematical alpha silhouette.
Future TypeScript use needs the documented shared sampler/registration adapter,
not Python or Pygame, and is not automatically compatible with the old unextended
NeuroStudio validator.
