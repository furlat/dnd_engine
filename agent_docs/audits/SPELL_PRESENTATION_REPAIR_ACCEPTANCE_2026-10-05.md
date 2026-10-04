# Spell presentation repair — October 5 implementation and evidence

The approved repair covers the 24 reported issues. It changes client presentation,
authoring data and native review fixtures. **No backend spell rules, event types,
combat mechanics, new art generation or external-chat communication were added.**
The source base is the human commit `b7e202dd36060215462c5068ea01524c66fe34fe`.
No commit was made by this task.

## Review entry points

- [24-issue guide](http://127.0.0.1:8768/spell-repair-20261005/persistent/runs/20261005-issue-review/issues.html)
- [Scroll feed](http://127.0.0.1:8768/spell-repair-20261005/persistent/runs/20261005-issue-review/feed.html)
- [Standard native gallery and traces](http://127.0.0.1:8768/spell-repair-20261005/persistent/runs/20261005-issue-review/index.html)

50 selected native recordings, 906 passing recorder checks and no reported binding
gaps. This is targeted evidence, not an assertion that 906 checks establish artistic
quality. Original failed attempts and the original 298-clip archive are preserved.
Each selected video/input hash and source run are in `provenance.json`.
The selected source runs use 24 or 32 FPS; the assembled static gallery uses each
clip's original FPS for frame stepping and original dimensions for aspect ratio.
No video was resampled for assembly.

## Exact changes

1. **Volume geometry and camera vectors.** `animation.py` treats inverse-projected
   camera displacements as vectors. `volume_media.py`, `cast_media.py` and `app.py`
   preserve stable declared-shape sample ownership at spherical fringes, then
   apply actual disclosure/physical geometry. Sleep uses an explicit raised-support
   policy instead of cutting its soft fringe against same-level ground. No tile
   screen-polygon mask or permission bypass was introduced.
2. **Reusable motion and media keypoints.** Existing `BodyClip` metadata owns named
   preparation/release/recovery anchors; existing media phases own measured formed,
   clear and contact anchors. `author_spell_casts.py` resolves these into ordinary
   concrete Studio data, preserves explicit overrides, rejects unavailable sheets
   and is idempotent. There is no second runtime animation registry or scheduler.
3. **Semantic authoring.** 126 owners and 24 derived presentations use the current
   assignment JSON and [current table](../art/SPELL_CAST_ASSIGNMENTS_CURRENT_2026-10-05.md).
   All six walls use ground strike; ground rings/pillars are conditional material
   choices, not diversity quotas. Directed beams retain proven Attack5 sockets.
   The Attack5/Effect3 skull belongs only to Blight. Magic2 remains the approved
   baseline. All selected modular accents use exact palette replacement and the
   existing noise material; Godot exports remain the main effect.
4. **Palette ownership.** Ten formerly white owners have explicit spell palettes.
   Fire Shield and Spirit Guardians derive their selected palette from this cast's
   received energy evidence. Shocking Grasp's main yellow art is palette-swapped
   to the common electric material. Existing shared yellow Lightning damage
   feedback is unchanged; it is distinct from casting/main VFX color.
5. **Attachments and condition timing.** Detached beams freeze their source at
   release; charge and retained Produce Flame use their appropriate moving/idle
   hand sockets. Curse touch delay is removed and persistent/removal rings are
   lowered16 canonical pixels around the body; head sigils keep their clearance.
   Hold connects faster; real Enlarge/Reduce recordings validate humanoid scaling.
   Eyebite Asleep shares the existing Sleep pose, and its delivery speed is8tiles/s.
   Hypnotic uses actual current native concentration ownership and maintains its
   rotating ground spiral. Existing Frightened wisps are shown in closer framing.
6. **Result timing.** Scorching Ray's HP/feedback callback joins impact rather than
   waiting until injury frame7. Repeated-hit reentry behavior stays intact. Power
   Word Kill death joins the existing flash's frame4@32FPS (125ms after release),
   replacing its late550ms join. No fake damage/blood packet is emitted. Dimension
   Door's additional concealed transit is0ms; ingress/egress still own their art.
7. **World-state transitions.** Existing bindings have independent formation and
   clearance offsets. Whole received state updates and related observations join
   exact spatial source lineages. Cause UUIDs resolve through retained version
   rows, including older split sensory packets. Pending art uses current disclosure,
   not future sight/collision/light. Destruction retains its own existing path.
   Fog/Darkness/Stinking Cloud/Cloudkill form at1000ms and clear at630ms;
   Stone/Ice form at843.75ms, Force850ms; construction clear850ms. Daylight forms
   at250ms and clears600ms. Sleet forms968.75ms and clears500ms, when its visible
   obstruction fades rather than at the empty tail's end.
8. **Resource and evidence corrections.** Two unchanged original modular sheets,
   Effect2/Attack4 and Effect3/Attack4, were installed and recorded in ASSETS.md.
   No new artwork was created. Native review additions are full-disclosure Sunburst,
   truly enlarged/reduced Hold recipients, and failed-save Grease. Fear gets closer
   actor framing using the same input. Old invalid size examples stay superseded.

## Issue-by-issue evidence

| ID | Report | Selected cases | What to check |
|---|---|---|---|
| G1 | Magic Missile camera curves | `missile-repeated` | All four views of the repeated A/B/A volley; elevated arena. |
| G2 | Fireball continuous volume | `spell-handoff-fireball-open` | Rounded edge with original subjective visibility preserved. |
| G3 | Sleep cloud fringe | `control-sleep-long--recipient` | Soft cloud bottom on same-level ground. Real higher terrain still occludes. |
| G4 | Sunburst dome | `sunburst-full-disclosure` | Entire circle disclosed in this native cast; compare sunburst-area for genuinely unseen far cells. |
| A1 | Lightning hand origins | `electric-lightning-bolt`, `electric-chain-lightning` | Charge follows preparation; released beam origin stays at the release socket. |
| A2 | Sunbeam emission | `sunbeam-lifecycle` | Proven directed Attack5 hand registration and release. |
| A3 | Produce Flame retained hand | `nature-produce-hit` | Flame remains at the current hand before hurl, then is consumed. |
| P1 | Previously white casting palettes | `nature-barkskin`, `nature-warm`, `sensory-see-invisibility`, `sensory-true-seeing`, `sensory-darkvision`, `nature-shillelagh`, `nature-produce-hit`, `queue-holy-spirit-radiant`, `queue-holy-guardian`, `queue-holy-feast` | All ten reported owners use their spell palette. |
| P2 | Energy variants | `nature-warm`, `nature-chill`, `queue-holy-spirit-radiant`, `queue-holy-spirit-necrotic` | Warm/chill and radiant/necrotic select from the cast’s own received result. |
| P3 | Electric material colors | `batch-shocking-adjacent-axis`, `electric-lightning-bolt`, `electric-chain-lightning` | Blue/cyan/white casting and main media. The established yellow Lightning damage flash remains shared damage feedback. |
| V1 | Semantic motion and effect variety | `antimagic-moving-field`, `healing-batch-mass-heal`, `nature-barkskin`, `electric-lightning-bolt`, `necrotic-circle-of-death-hit` | Invocation columns, restrained directed hands and protective accents follow the labeled motion semantics. |
| V2 | Walls strike the ground | `wall-fire-x`, `gap-wind-oblique`, `construction-force-panels-retirement`, `construction-stone-retirement`, `construction-ice-retirement`, `gap-thorns-ring`, `persistent-spike-growth` | All six wall materials use Attack4; selected ground effects differ by material and strength. |
| V3 | Blight owns the skeleton accent | `necrotic-blight-hit`, `necrotic-circle-of-death-hit` | Attack5/Effect3 skull is exclusive to Blight. Effect3 invocation/ground sheets are distinct artwork. |
| C1 | Curse timing and body rings | `bestow-curse-1-lifecycle` | Touch, owned ring application/sustain/removal; rings lowered around the body while the head mark stays above it. |
| C2 | Frightened condition wisps | `control-fear-cardinal-close` | Closer native actor framing exposes the existing dark sustained wisps; no duplicated Fear condition. |
| C3 | Hold connection and body size | `control-hold-person-clear`, `control-hold-monster-clear`, `control-hold-monster-enlarge`, `control-hold-monster-reduce` | Faster chain formation; native Enlarge/Reduce verifies actual changed body scale. |
| C4 | Hypnotic ground spiral | `control-hypnotic-clear`, `control-hypnotic-clear--recipient` | Maintained rotating ground art and concentration clearance from fresh native ownership. |
| C5 | Eyebite asleep pose | `eyebite-asleep` | Shared Sleep fall/rest behavior, rather than standing asleep. |
| T1 | Eyebite delivery speed | `eyebite-asleep` | Existing delivery accelerated to 8 tiles/s. |
| T2 | Repeated Scorching Ray injuries | `fire-scorching-repeat` | HP and feedback join actual impact; existing repeated-hit reentry retained. |
| T3 | Power Word lethal impact | `power-word-kill-applied` | Death joins the existing impact flash contact frame. No fake damage or deposited blood. |
| T4 | Formation and clearance | `persistent-fog-cloud`, `construction-force-panels-retirement`, `construction-stone-retirement`, `construction-ice-retirement`, `divine-daylight`, `divine-daylight--recipient`, `sleet-storm-lifecycle`, `sleet-storm-lifecycle--recipient` | Visible formation starts before admission; exact related world/light/sight state joins the authored formed/clear milestone. |
| T5 | Dimension Door transit | `dimension-door` | Emergence starts immediately after ingress, without an extra concealed pause. |
| Q1 | Grease still causes Prone | `persistent-grease-false`, `persistent-grease-true` | Compare actual failed and successful native saves; mechanics unchanged. |

## Verification and independent review

Logs are under `.runtime/projectile-regression-20261004/`. These overlap and must
not be added into a fictitious unique-test total:

- `final-affected-suite.log`:194 passed,488.17s; divine, silence, construction,
  curse, palettes, animation rigs and architecture.
- `final-clearance-tests.log`:36 passed,63.29s; final Daylight packet/seek and
  weather delivery after Sleet's clear-date correction.
- `power-impact-tests.log`:7 passed,7.31s; actual native kill/stun thresholds,
  prevention, prone death and no invented damage.
- Earlier repair regressions: `resumed-geometry-palette.log`140 passed;
  `resumed-conditions-delivery.log`48 passed; `fear-hypnotic-tests.log`12 passed;
  physical construction and media-keypoint logs remain preserved.
- Scoped typing: `final-types.log` initially found one optional-value narrowing
  issue; `final-types-correction.log` verifies the correction with0errors/warnings.
  The correction does not change timing behavior.
- Final offline author dry run: `author-final-idempotence.log` reports no
  changed files. The prior `author-final-check.log` also did so.
- [Independent ECS/DAG/disclosure review](SPELL_PRESENTATION_REPAIR_FINAL_ECS_2026-10-05.md).
- [Independent sampled artistic review](SPELL_PRESENTATION_REPAIR_FINAL_ANTISLOP_2026-10-05.md).

The full engine suite was not rerun for these client presentation repairs.
Scaled Hold evidence concerns the installed humanoid chain art, not an unmeasured
Ogre bank or arbitrary anatomy. Sunburst's full-disclosure clip is continuous;
its older long-range example still withholds genuinely unseen far cells. Those
are retained permission/artwork boundaries, not claimed repairs by revealing more.
