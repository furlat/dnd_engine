# Packing and playback audit — October 7

Status: measured source/metadata findings for G0 of the
[full migration plan](../GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md).
The human explicitly chose **keep 32 FPS; fix packing only** and separately
reported spells playing too fast. No production assets, sample rates or timelines
were changed by this audit. Packing is not declared fixed or installed.

## Fireball source footprint

Source: `game/assets/fps32/spell_recovery/shared.fireball.20ft-ground.smoke.v3/impact.zip`.
The installed archive is 1,267,137,373 bytes and has eight banks ×64 packets.
Each packet stores normal and additive components, both using the same rectangle,
with RGBA8, XYZ16×3 and owner8 planes: 11 bytes per pixel per component.

| Measurement | Four camera banks (SE/SW/NW/NE) | All eight source banks |
| --- | --- | --- |
| Packets | 256 | 512 |
| Compressed member bytes | 632,914,618 | 1,267,084,615 |
| Current decoded packet bytes | 3,567,450,592 | 7,184,150,912 |
| Exact separate-component zero-border crops | 2,880,346,242 | 5,806,203,301 |
| Decoded reduction from those crops | 19.26% | 19.18% |
| Completely empty components | 24 | 47 |
| Occupied 32×32 blocks ×11 bytes, before address/packing overhead | 2,010,207,232 | 4,025,359,360 |

The last row is a storage-layout estimate, not a built or accepted runtime
representation. Additional block draws/lookups, registration and upload behavior
must be measured. It must not be presented as an achieved memory/FPS improvement.

The audit reconstructed **every original RGBA/XYZ/owner byte** from each proposed
component crop and verified equality over all 512 packets. It used nonzero bytes
in every plane, not an alpha-only approximation. Empty components can be
represented by a single zero pixel without losing source bytes when reconstructed.
Offsets remain relative to the original pivot. All eight bank content signatures
are distinct; blanket mirrored-bank substitution would not be byte-preserving.
Overlapping normal/additive coordinates and ownership are not generally equal.

This proves a packing opportunity, not compositor parity. Current shared-depth
partitioning uses bounds; a storage crop must retain the **original logical
ordering extent**, even if its physical texture is smaller. The plan requires
that proof before installing a repair. Cropping alone leaves approximately
2.68 GiB across four views; it does not adequately solve the overall problem.

Investigate empty/sparse storage, independent data-plane access, immutable source
sharing and actual concurrent-frame residency before assigning resource budgets.
Keep the existing private-art preservation/installer flow. Do not discard samples,
rescale the artwork or call all four banks/all frames an unavoidable resident set.

Private evidence:

- `.runtime/playtest-recovery-20261006/gpu-proof/packing_audit.py`
- `.runtime/playtest-recovery-20261006/gpu-proof/packing-audit.json`

## Frame rates versus actual playback

The actual loaded metadata contains 149 spell/action drafts, including action and
reaction aliases. The audit inspected 256 directly referenced projectile/media
phases: 247 have a 32 FPS source and nine have a 24 FPS source. This is not a
complete inventory of all indirect condition/world/lifecycle media.

Fireball travel is 12 samples at 24 FPS; impact is 64 samples at 32 FPS, naturally
two seconds. These clocks are unchanged. 143 loaded cast recipes have body speed
1.0; six have 1.15 (Healing Word, Hellish Rebuke, Command, Shield, Mass Healing Word
and the Hellish Rebuke reaction alias). A global live playback speed increase
was not found: the encounter advances from elapsed seconds ×1000.

The metadata flags the following **candidates**, not confirmed timing defects:

| Selection | Source duration | Authored effect window | What needs verification |
| --- | --- | --- | --- |
| Shocking Grasp, source-hand rear/front | 1,750 ms | about 433 ms | Whether this is the intended cast-only slice and whether later media carries the remaining effect |
| Gust of Wind, source-ground effect | 2,500 ms | 1,750 ms | Whether the existing lifetime/transition retires the visual early |
| Eyebite and its repeat action, rear/front impact | 1,500 ms | 980 ms | Whether the finite window cuts the animation off or is an intentional effect selection |

These entries have no explicit time map in the inspected track and retain 32 FPS.
`media_track_frame` samples by FPS while the track's duration can retire it
earlier. A shortened window therefore need not be faster playback; it may omit
the tail. Do not automatically stretch these clips or shift damage to their end.

G0/P08 must finish the compiled/live audit: cast motion and release, actual near/
far/elevated travel durations and minimums, phase fitting/time maps, impact,
reaction/condition timing, looping/retirement, repeat actions and indirect media.
Also distinguish omitted visual samples during slow rendering from shortened
authored time. Record intentional retiming and repair demonstrated errors at
their existing owner. No global slowdown or FPS change is authorized here.

Private evidence:

- `.runtime/playtest-recovery-20261006/gpu-proof/timing_audit.py`
- `.runtime/playtest-recovery-20261006/gpu-proof/timing-audit.json`

## Conditional XYZ work

XYZ supports visual depth ordering and authored materials as well as physical
clipping; it does not drive native gameplay collision. A color-only frame should
perform none of those unused calculations. Resource requirements nevertheless
cover the admitted lifetime/all cameras/concurrent effects; a later overlap or
rotation cannot trigger a late decode. The reviewed plan now makes this
distinction explicit in its G0/G2 gates. The full renderer migration removes
per-frame CPU XYZ images; this audit does not claim that port has happened.
