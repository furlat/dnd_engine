# Lightning consultation — 2026-10-02

Consultation only; no authoring, renders, production changes or handoff. Personally inspected all four retained contact sheets below. Evidence is BG3 scene-composited footage, not source materials or engine timings. These references are not cleared production assets.

## Verified evidence

Reference root: `/mnt/c/Users/tommaso/Documents/assets/bg3-spell-reference`.
Each listed sheet has its corresponding `briefs/<id>.md`, `palettes/<id>.png`, and `sequences/<id>/` screenshots. Paths are relative to that root.

| Spell / ID | Contact sheet | Source and visible instants |
|---|---|---|
| Lightning Bolt / `lightning-bolt` | `sheets/lightning-bolt.jpg` | https://www.youtube.com/watch?v=_5QdD0cuZ6I&t=1323s ; 22:04.125 discharge, 22:04.250 endpoint flare, 22:04.500 fading haze |
| Chain Lightning / `chain-lightning` | `sheets/chain-lightning.jpg` | https://www.youtube.com/watch?v=_5QdD0cuZ6I&t=1783s ; 29:44.250 hand charge, 29:47.375 main branching discharge, 29:48.000 residual arc |
| Call Lightning initial / `conjuration-call-lightning-initial-strike` | `sheets/conjuration-call-lightning-initial-strike.jpg` | https://www.youtube.com/watch?v=2fP4zmAMNiY&t=813s ; sheet shows hand preparation, overhead fork and ground flash at 13:37.250, footprint/fragments at 13:37.750 |
| Call Lightning repeat / `conjuration-call-lightning-repeat-strike` | `sheets/conjuration-call-lightning-repeat-strike.jpg` | https://www.youtube.com/watch?v=2fP4zmAMNiY&t=826s ; 13:50.875 forked descending stroke and pointed ground flash; excerpt ends immediately afterward |

Lightning Bolt: dense angular blue-white arcs span a straight corridor, anchored near the casting hand. Source and far-end brightness are stronger than the fading haze. Palette examples: core `#E4FEFF`, cyan `#88DFF3`, blue `#5081B9`, fading scene haze `#264057`. Separate cast buildup is not established reliably by this brief excerpt.

Chain Lightning: small hand spark precedes the main discharge. Connected angular forks reach separated targets; bright knots gather around contact points. Palette: `#D0F8FF`, `#A5F5FC`, `#62CFE4`, `#52A3BE`. The sampled sheet does not establish a precise sequential jump order; do not turn its UI/camera delay into authored charge duration.

Call Lightning: caster preparation is visible in the initial sheet, but the discharge originates overhead, not from the hand. Narrow branched vertical stroke meets a broad brief blue-white ground burst. Repeat strike preserves that identity. Initial sheet gives clearer fading footprint evidence than the repeat excerpt. Palette: `#CDF9FF`, `#A1D3EC`, `#5885A6`; repeat `#D2FDFF`, `#99DCF6`, `#5081A9`.

Samples are roughly 8 FPS; visible instants are not complete phase boundaries. Colors contain lighting, bloom and compression. No persistent cloud lifecycle or precise chain branching order is verified here.

## Proposed art and geometry

Reuse a seeded electrical generator and short authored source/contact banks, rather than full XYZ frame exports. Generate each main trunk between the actual world-space anchors. Use an endpoint-constrained jagged spine, tapering attached side forks and a narrow pale core with restrained blue halo. Avoid rounded tubes, sinusoidal ropes, purple and detached ornamental strands. Keep endpoints fixed across electrical redraws; change a few coherent arc shapes instead of independently randomizing every vertex each frame.

Maximum-range templates can supply reusable noise/fork motifs, but should not simply be cropped for every distance: clipping can truncate major forks, leave constant branch density at short range and remove the terminal transition. Resample motifs to actual length with world-space segment spacing and controlled amplitude. Obstruction clipping is appropriate only at an authoritative stop, followed by a contact treatment at that stop.

Lightning Bolt: hand-origin corridor spine with short lateral forks. Creature contacts punctuate the continuing discharge; do not stop the whole line at its first affected creature unless the engine explicitly supplies that stop. Preserve the authoritative line extent and obstruction endpoint.

Chain Lightning: hand-to-primary trunk, then endpoint-bound links to the actual supplied secondary targets. Build topology from authoritative application data, not nearest-neighbor invention. Smaller attached forks enrich links; contact knots belong at each affected actor. A tiny staged onset is an art option, not verified BG3 timing or new mechanics.

Call Lightning: overhead anchor to the actual strike centre, vertical jagged trunk, ground flash and short radial ground arcs. Keep caster charge, cloud/overhead context and strike independently timed. Repeated strikes reuse the same contact family with a new seed; cloud dimensions/lifecycle must come from our game specification, not these sheets.

Compact payload proposal: style/version, seed, event timing, source/target anchor references or strike centre, authoritative link topology/line extent and obstruction endpoint where relevant. Store small normalized motif/control data and authored contact media; reconstruct paths deterministically at runtime. Projection, sockets and depth sorting remain production responsibilities.

Review native results at short/long range, different elevations, overlapping actors and all four cameras. Check attached forks, fixed contact points and readable bright cores without blanket bloom. This note approves no unseen artwork.
