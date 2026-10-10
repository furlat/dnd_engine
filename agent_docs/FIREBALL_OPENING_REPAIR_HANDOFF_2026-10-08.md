# Fireball opening: abrupt expansion and flash

8 October 2026. For the Godot artwork/export author, forwarded by the human.
No between-chat communication. Return a written handoff and a separate candidate;
preserve the existing source and delivery.

## Request and scope

The human likes the smooth interactive Pixi proof, but reports that the opening
explosion seems to have too few frames and flashes. We inspected the delivered
opening manually and found abrupt changes in the exported appearance, plus a
separate first-playback frame skip that has now been fixed in the demo.

Investigate the first approximately **0.3 seconds** and prepare a smoother opening
candidate. Retain the accepted Fireball identity, palette, scale, main plume and
smoke progression. This is a bounded artwork/export follow-up: no engine, spell
rules, other effects, wall artwork, SDK or client architecture work.

Current delivery to inspect:

`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fireball-single-view-24fps-v1/HANDOFF.md`

Its adjacent `manifest.json` is the source of frame times and channel definitions.
The [original export contract](FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md)
remains applicable to packing/registration. Its earlier broader scene proposal is
not additional work in this follow-up: the current demo is only floor, real wall
sprites, lights and the Fireball impact.

## Evidence already collected

Evidence is saved outside the temporary demo directory:

- [Opening contact sheet](../output/weapon-vfx/fireball-opening-review-2026-10-08/opening-source-contact.jpg)
- [Frame measurements](../output/weapon-vfx/fireball-opening-review-2026-10-08/opening-source-metrics.json)
- [Cold and repeated playback trace](../output/weapon-vfx/fireball-opening-review-2026-10-08/opening-playback.json)

Absolute evidence directory:

`/mnt/c/users/tommaso/documents/dev/dnd_engine/output/weapon-vfx/fireball-opening-review-2026-10-08/`

The contact sheet shows frames 0–11 at the same pivot, crop and scale, with no
wall occlusion, scene lighting or bloom. It reconstructs the supplied raw bands
using the declared linear operation:

```text
C = Cnear + (1 - Anear) * Cfar
A = Anear + (1 - Anear) * Afar
display = linear_to_sRGB(clamp(C + (1 - A) * dark_background, 0, 1))
```

The visible changes are:

| Frames | Source sample times | Observation |
|---|---|---|
| 0 → 1 | 20.8 → 62.5 ms | Small ground burst becomes a bright central sphere. |
| 1 → 2 | 62.5 → 104.2 ms | The burst expands sharply; thresholded footprint grows from 360×244 to 619×524 source pixels. |
| 4 → 5 | 187.5 → 229.2 ms | The bright central sphere and much of the spiky opening burst disappear abruptly, leaving the growing plume/ring. Summed linear radiance drops about 34%. |

Times above are the **midpoint source samples**, not browser wall-clock times.
Frames 1, 2, 4 and 5 correspond to native simulation ticks 9, 15, 27 and 33.
Each frame currently plays for 1/24 second; frame 2 begins at 83.3 ms of playback,
and frame 5 at 208.3 ms.

Measurement definition: footprint is the bounding rectangle where maximum
recomposed linear RGB exceeds 0.06; radiance is the sum of recomposed linear RGB
over the original canvas, before background and display conversion. These are
diagnostic measurements, not artistic acceptance thresholds.

**What this proves:** the jumps are present in the delivered near/far appearance
before the demo's lighting, bloom or wall-depth tests. **What it does not prove:**
whether they originate in the native effect's emitter/envelope timing, temporal
undersampling, or the export/palette/band process. We have not yet compared a
dense native capture of this opening against every delivered sample. Please
establish that distinction before selecting a fix.

## Client issue already handled

A cold first cast could skip an opening sample when initial shader/texture setup
took longer than a source-frame interval. The demo now submits frame zero before
advancing and advances by at most one 24 FPS interval per displayed frame. A stall
extends playback instead of jumping over source samples.

The saved post-fix trace contains every submitted frame 0–11 on both cold and
repeated playback, with zero added buffering in those two opening checks and no
page errors. This is bounded playback evidence, not a claim that all concurrency
or first-use performance is solved. The remaining source jump is still visible
in the contact sheet. Do not compensate for the old client skip by duplicating
frames or retiming the entire effect.

The live standalone proof, while its local server is running:

<http://127.0.0.1:8790/?review=real-walls-opening-check>

Demo source:

`/mnt/c/users/tommaso/documents/dev/dnd_engine/.runtime/ndclient-fireball-proof/`

The scene now uses complete installed stone-wall/archway sprites, with simple
approximate depth/light geometry. Those wall proxies are unrelated to the
source-only opening evidence and are not a Godot repair request here.

### Separate client issue: outer ring / wall contact — unresolved

The human supplied screenshots at 0.85 and 0.96 seconds and clarified that the
**outer ring**, from a cast on the left of a wall, appeared on the opposite side.
This was reproduced in the demo with an approximately matching cast location.

The demo initially used camera-depth occlusion without a wall-contact treatment.
An attempted fix then tested the segment from the impact origin to every effect
sample against wall geometry and discarded blocked samples. **The human rejected
that result as ugly and artificial, contrary to the stated visual requirements.**
It produced angular holes/wedges and sharp doorway cones: effectively deleting
the wall's shadow from the explosion. Using continuous geometry rather than
tiles did not make that cutout visually acceptable.

The human's additional 1.11-second screenshot specifically identifies deletion
before the apparent ring/wall contact and notes that the doorway should permit
passage. Preserve those as explicit failure cases. Do not reinterpret this as
permission to erase a larger sector, close the doorway, or add a broad fade to
conceal the same spatial error. Verify reconstructed ring positions against the
registered wall surface before selecting another contact treatment.

That attempted fix has been removed. The real wall sprites, wall lighting and
camera-depth occlusion remain. The ring-crossing/contact issue is unresolved.
The previous statement that this had been “fixed” was premature. Running without
page errors or demonstrating blocked pixels was not artistic acceptance.

Historical comparison only:
[original behavior](../output/weapon-vfx/fireball-opening-review-2026-10-08/barrier-left-before.png),
[rejected hard cutout](../output/weapon-vfx/fireball-opening-review-2026-10-08/barrier-left-fixed.png).
The filename containing `fixed` predates the rejection and is not an approval.
The saved check record likewise describes the rejected candidate.
The [current reproduction](http://127.0.0.1:8790/?review=wall-cutout-removed)
restores the prior silhouette at 0.96 seconds; it is not a completed repair.

The replacement must preserve coherent flame/smoke shapes at the wall, rather
than remove angular slices from a baked effect. A mere softened version of the
same cutout is not established as sufficient. Whether existing bands can support
the desired contact without another representation remains to be demonstrated;
do not claim either sufficiency or missing assets without a concrete comparison.
No fluid simulation, new channels or new export are requested for this issue in
this handoff. Do not bake demo walls into the Fireball. Keep the opening flash
investigation below separate from this unresolved client/representation work.

## Requested investigation and candidate

1. Inspect the unchanged native opening at its existing 144 Hz simulation rate.
   Capture a short dense **diagnostic** sequence around 0–0.3 seconds, including
   the exact existing midpoint sample times. Compare the original composite with
   the near/far reconstruction at matching times, with bloom disabled first.
2. Determine whether the bright sphere/radial burst switches off sharply in the
   source, whether 24 FPS misses an otherwise smooth transition, or whether band
   capture/palette ordering introduces or amplifies the change. Check sample
   pairing and deterministic simulation advancement; do not assume “more frames”
   is sufficient without this comparison.
3. Prefer a separate **48-frame, 24 FPS, two-second candidate** that smooths the
   offending opening transition at its source/export owner. For an actual source
   discontinuity, adjust only the relevant opening size/opacity/emission envelope
   enough to bridge it into the plume; preserve the rest of the effect. For an
   export defect, repair that defect without redesigning the source explosion.
4. If genuinely smooth source motion still needs denser opening sampling, show
   a short denser comparison and report the additional frame count/bytes. Keep
   it a separately labelled candidate. **Do not silently replace the runtime
   timing contract with a variable-rate or higher-FPS bank.** The demo currently
   indexes `floor(age * 24)`; a different schedule needs a deliberate client
   change. There is no authorization for a global spell-FPS change.

Do not smooth by crossfading mismatched depth/normal frames, by adding an opaque
flash overlay, by darkening the entire Fireball, by cropping the burst, or by
slowing down the entire two-second clip. Appearance and geometry must continue
to describe the same simulation instant and source contributions.

## Keep the compact delivery contract

- One SE view, two real near/far depth bands.
- Per band: appearance RGBA8 plus geometry RGBA8, eight bytes per layer texel;
  raw-byte transport preserves emission where opacity is zero.
- Original scale-one pixels, source canvas/pivot/matrices and fixed depth basis.
  Preserve registration while each frame crops only empty borders.
- One declared radiance scale; no frame-by-frame exposure normalization to hide
  the flash. No new runtime XYZ/ownership banks or extra directions.
- Keep bloom outside the geometry payload. Show original and repaired openings
  without bloom, then with the same reference bloom settings.
- Preserve v1; deliver into a fresh private directory with provenance and a
  concise change list. Do not install into production or alter game bindings.

## Return and review

Return a handoff identifying the cause, the exact change, and any remaining
uncertainty; one before/after opening contact sheet using fixed framing; short
normal-speed and slowed diagnostic playback; the replacement manifest/payloads
if the 24 FPS candidate succeeds; and compressed/decoded/peak-frame byte totals.
Use the existing exporter checks once after the final candidate. Do not build a
new validation framework or repeatedly regenerate unrelated media.

Artistic acceptance is that expansion remains forceful but the initial sphere
does not pop in/out like an unrelated flash, and the transition into the plume
reads continuously at actual playback speed. The human reviews the result in
Pixi after reintegration; denser diagnostic frames alone are not acceptance.

Final scoped review must cover both perspectives: **anti-slop** checks that this
is a localized cause-based repair with no extra formats/systems; **anti-OOP/ECS**
checks that changes stay in artwork/export data rather than engine behavior or
spell-specific renderer code. This handoff itself does not claim those reviews
or the artwork repair have already been completed. The human forwards all
communication.
