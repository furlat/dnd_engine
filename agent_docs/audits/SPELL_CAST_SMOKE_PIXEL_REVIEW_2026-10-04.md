# Spell casting smoke-gallery pixel review — 2026-10-04

**Verdict: no blocking visual issue found in the inspected samples.** This is
bounded evidence for the nine-clip smoke gallery, not acceptance of the complete
persistent gallery or every animation frame.

Run: `.runtime/spell-casting-20261004/wood-smoke/runs/20261004T174847Z-03847e`.
The manifest records nine passed clips, 101 passed checks and zero gaps.
Independent `ffprobe` inspection confirms each video's declared frame count,
1280×960 dimensions and 32 fps. Manifest SHA-256:
`efdbc9cf2d07806c8a82ba0f58f803cf21f6727fd0880353be3b8800f70c9030`.

## Actual pixels inspected

Frames were extracted by exact video index with ffmpeg. Caster rectangles came
from the corresponding trace draw coordinates in each of the four cameras.
Nearest-neighbor crops retain the visible pixel structure. The reviewer viewed
34 distinct sampled frames as 136 camera crops, plus four uncropped frames.
No continuous-playback or all-eight-facing inspection is claimed.

| Case | Observed motion | Video frame indices viewed in four camera crops |
|---|---|---|
| firebolt-level | Attack5 | 20, 31, 42, 44 |
| batch-shocking-adjacent-axis | Attack1 | 20, 28, 41, 42 |
| true-strike-longsword-hands--caster | Attack1, actual weapon attack | 20, 28, 41, 42 |
| healing-batch-mass-heal | Special1, then Idle | 20, 42, 55 |
| nature-shillelagh | Special1, then Run | 20, 42, 55 |
| goblin-02-web | Goblin02 Attack2 | 20, 28, 41, 42 |
| electric-lightning-bolt | Attack6 | 20, 28, 41, 42 |
| construction-stone-retirement | Attack4 | 21, 37, 43, 50 |
| gap-cone-oblique | Attack6 | 20, 28, 41, 42 |

Uncropped inspection: Mass Heal frame 55, Wall of Stone frame 50, Cone of Cold
frame 41 and Lightning Bolt frame 41, each showing all four cameras.

## Observations

- Fire Bolt's orange/yellow hand energy stays compact and follows the pointing
  hand. Shillelagh and True Strike retain similarly local pale hand accents.
  The real longsword and slash remain visible in the True Strike attack samples.
- Shocking Grasp's Attack1 downward strike and yellow body/hand accent remain
  registered across the four views. Its close target contact is much denser
  than the quiet hand-only casts, but the actor pose remains readable.
- Lightning Bolt and Cone of Cold use the low Attack6 thrust. Their main beam
  and cone dominate the scene while the caster accents remain local. Lightning
  has a visibly orange/cyan caster treatment beside its blue main bolt; this
  reflects its existing authored palette and does not obscure the delivery.
- Mass Heal's blue/white column and Wall of Stone's broad caster-centered ring
  are substantially larger than the quiet accents, as deliberately assigned.
  In the later samples they give way to readable recipient healing circles and
  the actual wall respectively. The wall ring must remain understood as a
  caster flourish, not a second affected area.
- Goblin02 retains its own Attack2 gesture, purple particles and compact bright
  charge. No modular body-shaped layer is visibly pasted over that fixed rig.
- The visible wood floor leaves the sampled casting and delivery areas open.
  Existing labels occasionally overlap nearby actors; cropped label text in the
  contact sheets is not evidence of clipping in the source video.

Material appears as discrete, mottled effect pixels without a visible overall
actor/gear/shadow recolor. Lossy video cannot establish exact palette membership
or bit-identical alpha; those remain responsibilities of source-surface tests.
Different scene zooms also preclude comparing raw screen area as a power metric.
No conclusion is made about unsampled timings, spells, skull signatures, hidden
occlusion cases or the final 298-recording gallery.

Private evidence is retained in
`.runtime/spell-casting-20261004/pixel-review-antislop/`: `samples.json` records
indices/timestamps, `evidence.json` records video hashes/probes, and the PNGs
contain exact extracted frames and camera-crop contact sheets. Only these
inspection derivatives and this receipt were written; no production edits or
external chat communication occurred.
