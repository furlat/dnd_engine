# Spell presentation repair — bounded final anti-slop review

Date: 2026-10-05. Independent review of actual recorded pixels and their native traces. No production edits, new recordings, tests, or external-thread access were performed for this review.

**Verdict:** the sampled replacement clips close the identified missing-sheet, false size-coverage, raised Curse-ring, prolonged Sleet-clear, and Power Word Kill flash/death separation findings. No remaining implementation blocker was found within the sampled scope. This is not exhaustive acceptance of all 50 selected clips, all 24 issue categories, every assignment, or the archival 298 recordings.

## Evidence and provenance

Frames were decoded directly from completed `clip.mp4` files with ffmpeg by zero-based frame index and inspected in their recorded four-camera layout. The Barkskin contact sheet contains only nearest-neighbor crops of recorded pixels. No generated artwork was used.

- Earlier actual-pixel review: `.runtime/spell-repair-20261005/antislop-frames/samples.json` records 49 selections from eight recordings in `20261004T225106Z-b208f6`.
- Supplement and replacement review: `.runtime/spell-repair-20261005/antislop-frames/supplement-samples.json` records 76 selections from 14 recording versions, including explicitly superseded attempts. It preserves clip/input hashes, exact frame indices, video/presentation times, source fps and dimensions.
- The assembled gallery at `.runtime/spell-repair-20261005/persistent/runs/20261005-issue-review` contains 50 passed records, 906 passed recorder checks, no recorded gaps, and 24 issue entries. All 50 assembled video and input hashes match `provenance.json`. Frame stepping and displayed frame counts use each record's fps; replacement recordings are 24 fps while the initial/supplement recordings are 32 fps. These checks establish artifact identity and recorded coverage, not aesthetic acceptance of unviewed frames.

## Replacement findings

| Presentation | Actual evidence | Bounded conclusion |
|---|---|---|
| Hold Monster, enlarged/reduced | `20261004T231407Z-a29a07`, both cases, frames 32/44/64; video 1.3333/1.8333/2.6667 s | Native Enlarge/Reduce conditions are present. Bodies and rune/chain spans visibly differ, with connections centered on the respective bodies in all four sampled views. The earlier identically sized attempts in `230623` do not count as size evidence. This covers the scaled humanoid rig, not Ogre or other anatomy. |
| Bestow Curse | `20261004T230623Z-d99668`, `bestow-curse-1-lifecycle`, frames 32/48/96, movement frame 375, removal frames 610/622/644/670/700 | The corrected ring surrounds torso/legs; the separate sigil stays overhead. The ring follows movement at video 11.71875 s. Removal at 19.0625–21.875 s fades the ring/sigil and leaves a clean actor. No sampled attachment/material blocker remains. |
| Wall of Stone / Wall of Ice | `230623`, respective construction retirement cases, frames 26/35/39/45/52/64; video 0.8125–2 s | Original Attack4 Effect2 tall spikes and Effect3 descending/radial accent are actually present. Their broad caster accents recede as wall segments rise and do not obscure construction in the inspected frames. Successful replacements supersede the initial missing-resource failures. |
| Daylight, both observers | `230623`, `divine-daylight` and `--recipient`; exact selections in JSON | The pale-gold orb fades in through video 1.4375–1.5625 s, holds, and fades out through 5.1875–5.75 s without a sampled jump. The bright-floor fixture does not establish a dark-room illumination boundary. |
| Sleet Storm, both observers | `20261004T231520Z-82df81`, frames 99/103/106/108 for caster and 103/106/108 for recipient; video 4.125–4.5 s | The replacement fade continues toward visibility clear. Other actors return at frame 108. The earlier approximately half-second bare dark footprint after visible particles disappeared is no longer present in these samples. The superseded 1000 ms attempt remains comparison evidence only. |
| Power Word Kill | `20261004T231729Z-24a001`, frames 24/25/26/27/28/32/44; video 1–1.8333 s | The cross-shaped flash remains visible when the recipient reaches 0 HP at frame 27/video 1.125 s, followed by the fall and settled corpse. The old gap between flash and death is closed in these samples. The trace retains absent damage/flash/number application clocks; no invented damage cue was needed. |

## Motion, palette and competition limits

Earlier selected frames support Antimagic's violet orbit-to-column invocation beside its larger field, small Attack5 hand accents beside the two lightning beams, and the deliberate broad Wind/Thorns ground-strike signatures. Wind's bright foot ring recedes as its separate wall rises; Thorns' tall olive spikes share the wall's material family and leave it readable. The compact Force accent likewise does not compete with its panels. These findings come from pixels, not assignment rationales or layer quotas.

Barkskin's sampled casting energy is brown/ochre, followed by amber application. Shocking Grasp's authored casting/target media is cyan and white. Its recipient still flashes yellow at impact, as do the sampled Lightning Bolt and Chain Lightning recipients: this is the separate existing Lightning damage-feedback ramp. This receipt does not claim that every yellow screen element was removed or that damage-feedback palettes were reassigned.

The existing plan/semantic reviews remain separate from this pixel receipt. Parent review owns the remaining geometry, source/timing implementation, test reconciliation and complete issue-guide closure. No uninspected recording or unsupported anatomy is promoted to visual acceptance here.
