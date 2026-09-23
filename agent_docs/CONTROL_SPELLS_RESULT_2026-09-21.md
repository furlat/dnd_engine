# Control spells and lethal opportunity blood — implementation result

This unit connects the delivered control media to native histories and the
existing presentation pipeline. It follows
[the reviewed plan](CONTROL_SPELLS_IMPLEMENTATION_2026-09-21.md). The broader
graphics cleanup and native typing repair remain separate preceding work.

The final [34-clip review](http://127.0.0.1:8767/runs/20260921T132229Z-53ba67/index.html)
contains 3,952 synchronized four-camera frames from both subjective perspectives.
All clips and replay checks pass, with zero media gaps. The served HTML/manifest
return HTTP 200 and the video supports HTTP 206 seeking. The corrected blood
impact/floor, Charm, Blindness, Sleep and Silence frames were visually inspected;
the final Command traces also confirm zero-duration normal-expiry heads.

## What is connected

- Charm Person: finite flower/hearts application, sustained Charmed indication
  and real native removal. Successful saves do not invent a condition.
- Blindness/Deafness: the actual selected mode chooses the existing effect draft;
  application, sustained head glyph and clear follow effective membership.
- Command Grovel/Halt/Flee: a pending crest activates at the recipient's recorded
  turn start. Flee starts moving immediately while the execution media runs.
  Grovel's independently applied Prone survives Command expiry.
- Color Spray: the registered native cone now uses its selected destination;
  the directional authored art emits from the measured release hand. The media
  pivot and source socket account for source-preview actor scaling using the
  existing attachment data, with no extra rotation or runtime offset path.
- Silence: fixed observed sphere and effective Deafened belong to their existing
  spatial and condition lifecycles. Its application, loop and clear use one
  retained presentation clock and separate rear/front layers.
- Sleep: the delivered face-attached 576-frame loop replaces textual Zzz.
  Casting, projectile, impact, fall, resting-body targeting and reverse wake
  remain on their previous paths. Clearing during fade-in cannot brighten it.

All review experiments use real registered native actions and capture both
participants from the same generation. Saved player packets are sufficient for
subsequent four-camera rendering after the native runtime has been reset.

## Shared data and implementation

Condition transitions execute authored finite effects rather than acquiring
spell-specific executors. Existing condition membership dates now also cover
finite-only recipes and the optional owner-turn activation. Repeated contributors
retain the effective visual phase until the final contributor is removed.
Both playback admission callers pass already-witnessed activation identities to
the binder. A completed Command does not reserve an empty cancellation window
at normal expiry; cancellation before execution keeps its finite clear. This
uses the existing retained activation dates, not a second phase rule.

The root modular rig has authored head/face positions for its fourteen available
body clips, eight directions and each sampled frame. These points follow the
actual body pose, including forward falling and reverse waking. Incoming
projectile torso/rest endpoints are unchanged. New finite and maintained media
use existing page rectangles, pivots and bounded caches. Nondirectional frames
use one shared `parts` sequence instead of eight identical facing arrays.
The rig serializer explicitly writes the nested immutable socket maps as JSON.
A full root-rig round trip preserves every authored point, so loading successful
data is not mistaken for a complete portable-data contract.

Maintained spatial records declare layers, optional application assets, loop
window, scale and clear fade. Gust retains its existing single center layer.
Silence uses complete rear/front shell layers around its declared geometry;
the existing floor-cell slicing still serves ground-aligned linear fields.

The portable records and units are documented in
[PRESENTATION_CONTRACT.md](../game/data/PRESENTATION_CONTRACT.md). Pygame remains
the raster adapter; no native event carries an asset, socket or frame instruction.

## Native repairs demonstrated by this unit

The existing condition ownership graph can now retain multiple parents of an
effective sense condition. Removing Silence while independent Deafness remains,
or removing Color Spray while independent Blindness remains, no longer removes
the still-owned public condition. Accepted cleanup and existing removal-veto
preflight own the graph changes. Same-name Charm replacement is preserved.

Blindness/Deafness retains its chosen mode in the existing `effect_id`, including
successful saves. Color Spray uses the existing area-target resolver instead of
its template's stale default cone. Silence publishes its actual observed cells
and known center/geometry through the existing spatial observation contract.

The native spatial removal event already existed, but player projection discarded
it after its sensory child removed the field. Projection now retains a removal
only from that exact event's previously observed contact and witnessed cells.
Never-seen fields and ordinary loss of sight gain no lifecycle fact. The same
existing entry-observation mechanism already serves area delivery; no alternate
native event or public removal inference was added.

## Missing blood in the opportunity-downing clip

The earlier `walk-downed` capture had 6 Slashing damage and DYING, but its
`DamageFact.body_release` was absent. Its Hero fixture did not compose the
existing blood-response handler. Enabling the fixture's existing `bloodied`
option records the normal injury and twenty receiving floor cells in both views.
The renderer had not suppressed blood because of DYING.

A real-history regression verifies HP 4→0/DYING, spray beginning at damage
contact from the interrupted visual body position, native ground residues and
the final downed body retaining that position. Visible particles are checked
in all four cameras. The corrected gallery has also been visually inspected.
Existing critical amplification is unchanged; there is no newly invented death
or overkill multiplier.

## Validation and limits

Independent ECS/anti-OOP and presentation/anti-slop reviews covered native
ownership, real Command activation, condition overlap clocks, pose registration
and maintained spatial media. The lifecycle review's empty Command cancellation
delay was fixed and retested before this final gallery. Detailed review evidence
is in `activation-ecs-review.md`, `control-lifecycle-review.md`,
`backend-result.md` and `presentation-result.md` under the evidence directory.

Evidence is retained under `.runtime/control-spells-20260921/`. The full game
suite completed with 1,892 passes and three failures. Two exposed the missing
nested socket serializer; the third was a rig-name-isolation fixture that
discarded the Goblin's newly authored slash slot. The serializer now round-trips
all socket data. The test fixture preserves unrelated slots while exercising its
original pixel-equivalence contract; altered clip-length fixtures keep their
socket frame counts consistent. The final affected-module run passes all 66
tests, including these three repairs and the new activation/spatial tests.
The sixteen-minute full game lane was not repeated after those narrow repairs.

- Native full lane: 1,132 passed. Two subsequently added joint-owner traversal
  cases pass in the seventeen-case ownership suite; production native code did
  not change between these checks.
- Fourteen control-history cases round-trip both subjective views with no
  missing presentation bindings. Eight additional real Command cases verify
  turn activation, removal-before-execution and concurrent Flee movement.
- The final 66-test repair slice passes drawing, rig data/timing, Command,
  witnessed spatial removal and Silence lifetime. Twenty-five pose tests cover
  all eight facings across four cameras. Eleven Silence/Gust tests preserve the
  existing Gust pixels and verify application, sustain, clear and reacquisition.
- The separate real downing regression verifies native blood, floor residue,
  held subcell placement and visible particles in all four cameras.
- Color Spray registration passes all eight aim directions, four cameras and
  two actor scales; the delivered source pixels remain unchanged.
- Native plus graphics/review type checking reports zero errors and warnings.
  Twenty-six selected import-boundary/content-architecture checks pass.

The head/face socket coverage currently belongs to the measured modular root
rig. Unmeasured fixed rigs do not get an invented socket. A Silence shell needs
its received fixed origin to be currently observed; partial observation with an
unknown origin does not fabricate placement. The existing native Deafened rule
affects hearing-dependent skill checks. Color Spray's preexisting duration
advances on the recipient's turn start despite its caster-next-end description;
that rules discrepancy is recorded rather than silently changed by media work.
