# Fresh packed replay: independent visual review

Run: `.runtime/animation-review/runs/20260923T235336Z-41e560`.
Reviewer: `content_ecs_review`; 2026-09-24. Read-only acceptance sampling;
no production code, data or media changed for this review.

## Result and limits

No missing media, page-edge crop, displaced object pivot or broken visual
lifecycle was found in the sampled four-camera mosaics below. This is bounded
visual evidence for the fresh installation, not a claim that every frame or
every selected asset was inspected, nor a pixel comparison against an earlier
approved run. All inspected cases report `passed`; the run uses saved inputs.

The combined portal traveler view is too distant for fine clipping assessment
(zoom 0.15). Its closer departure (0.5) and arrival (0.75) observer clips were
therefore inspected as well. They show the body passing through the apertures.
The three receipt-compatibility failures elsewhere in this run are outside this
visual sample and were being repaired separately.

## Evidence

Extracted PNG mosaics and their requested video timestamps/frame indices are in
`.runtime/cleanup-implementation-20260924/visual-acceptance-content/`, with
`samples.json` identifying their source videos. Each PNG contains cameras 0–3.
Timestamp-named extracts use ffmpeg seeking; their embedded displayed clock is
the presentation time. Frame-indexed extracts use an exact decoded frame index.

| Case | Inspected moments | Observations |
| --- | --- | --- |
| `device-break-fireball` | Requested 650, 1750, 5625, 6750 ms; exact frames 104, 144, 149 (displayed 4300, 5925, 6133 ms) | Projectile appears at cannon muzzle; explosion is centered on its recipients; first and lethal melee contacts flash the cannon; fracture becomes a stable wreck at the same ground position. All four poses are present. The large explosion exceeds a viewport edge in some views, rather than ending at a packed-page rectangle. |
| `portal-hatch-open-jump` | Requested 650, 1400, 1750, 2200, 3350 ms | Whole-route view retains the jump/departure/arrival sequence, but its distant framing is insufficient to judge fine body clipping. |
| `portal-hatch-open-jump--departure` | Requested 500, 1150, 1350, 1550 ms | Open hatch remains visible; the jumping actor enters the aperture, lower body is clipped at the opening, then the actor disappears. No sampled body segment was drawn below the opening on top of intact surrounding ground. |
| `portal-hatch-open-jump--arrival` | Requested 1050, 1400, 2700 ms | Actor emerges through the violet floor portal, rises to standing, and remains at the settled destination after the portal closes. The body/portal relationship is consistent across the four views. |
| `liquid-barrel-water-walk` | Requested 1125, 1500, 2750, 4400, 5700 ms; exact frames 69, 75, 85 (displayed 2833, 3083, 3500 ms) | Barrel damage flash, fracture and water spill are present. Water spreads around the broken barrel, persists on the floor and remains beneath the walking actor. No page seams or shifted pivots were visible. |
| `healing-batch-lesser-restoration` | Requested 1250, 1875, 3500, 4750 ms | Turquoise restoration media is attached to the recipient, Poisoned is removed, and the finite media clears afterward. HP remains 85/120, consistent with a condition removal rather than a healing spell. All four views retain the same target. |

## Observations that do not establish a new regression

- In the water clip, `Wet` is already displayed at 2833 ms while the barrel is
  still visibly intact; visible blue spill appears by 3500 ms. The sampled
  native/reduced condition is released before the authored break/spill frames.
  This is a timing observation, not evidence that packing changed it. Do not
  retune this during packaging acceptance without comparing the prior behavior.
- The portal fixture labels the actors `0/0` HP while its recorded contacts have
  `life_state: alive`. That is present in the saved input/trace; it is not a
  missing character asset or a result of the packing adapters.

The review supports proceeding with the installation and separately reported
decoder fixes. It does not authorize creative timing, scale or artwork changes.
