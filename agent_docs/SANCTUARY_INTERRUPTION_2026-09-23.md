# Sanctuary and interrupted actions

User request: repair Sanctuary's handler and distinguish a blocked attempt from
a committed action that is interrupted. The user's September 23 correction is
decisive: presentation must respect whether the blocked actor spent action economy.

## Findings before this change

- Sanctuary gated ATTACK at DECLARATION, before payment. It missed
  CAST_SPELL, including Fire Bolt and targeted control spells.
- Counterspell gates CAST_SPELL at published EXECUTION, after payment. Existing
  native tests establish that the caster spends its action/slot and the reactor
  spends its reaction/slot. These rules are preserved.
- `canceled_from_phase` already exists. Phase alone is not a payment receipt:
  detached validation can reach EXECUTION before costs are attempted.
- The native cost owner commits atomically. Record payment there, not by comparing
  live resources during playback or making animation duration imply payment.
- Ordinary Fireball already breaks Sanctuary via its enemy application children.
  The earlier blanket claim that position AoE cannot break the ward was wrong.
  Preserve that behavior; do not "repair" a missing root target.
- Choreography skipped all canceled action bodies while retaining children.
  That correctly avoids invented damage, but hides actual blocked attempts.
- NeuroClient's original Counterspell body/release/feedback recipe is already
  vendored. Its mapper plays that reaction; it is not a projectile-collision engine.

## Implementation boundary

Input: real commands, native completed/canceled lineages, then serialized player
histories. Output: actual resource/HP/condition changes plus a replayable interrupted
attempt. No rule depends on rendered frames, and no canceled action creates impact,
injury, blood, or persistent effects that the native history did not produce.

1. Repair Sanctuary using native spell targeting and harmful-effect semantics.
   Cover attack, harmful selected-target spell, beneficial spell and area spell.
   Explicitly selected multi-target attempts are checked before commitment. If
   a selected ward blocks one, reject the attempted allocation; do not retarget,
   charge a partially executed spell, or check each application again.
   Area effects bypass the targeting ward. Preserve real enemy-application
   self-break, and avoid treating beneficial spells as hostile merely by faction.
2. Retain cancellation reason, phase and actual payment in public action facts.
   Keep resource amounts/private inventory and hidden reactor identities private.
   Give Sanctuary a stable native outcome identity. Plain invalid commands remain
   separate from these mechanically blocked attempts.
3. Author shared interruption settings in passive presentation data. Reuse the
   original attack/cast body, equipment and launch anchors. Unpaid attempts stop
   during anticipation. Paid interruption can reach projectile flight, then end
   before contact; non-projectile delivery stops before its effect anchor. This
   is playback of an already resolved interruption, not a new mechanics phase.
   Keep completed child facts even when their parent was canceled.
4. Preserve Counterspell's triggering lineage when projecting its reaction and
   reuse its existing authored gesture. Confirm actual ownership before choosing
   how to synchronize it; do not invent a second queue or rewrite native ancestry
   merely for animation convenience.
5. Verify with native commands, saved public replay, meaningful failure/pass
   comparisons and paired-observer four-camera clips. Keep paid and unpaid
   resource assertions alongside the visual checks.

## Reviews and acceptance

Required anti-slop/correctness reviewer: `sanctuary_rules_review`.
Required anti-OOP/presentation reviewer: `interruption_arch_review`.
Both independently reviewed the plan before implementation, then took bounded
native and grouping work. Their reviews corrected the AoE claim, distinguished
cancel phase from expenditure, and found two playback requirements: preserve
separate reaction observations and interrupt a split volley before any delivery
arrives. Those findings are addressed; neither review authorizes adjacent work.

Acceptance: failed Sanctuary attack and harmful spell cause no injury or payment;
passed save allows normal costs and consequences; beneficial/area spells are not
mistakenly blocked; enemy-targeted beneficial spells do not break the ward;
existing Fireball self-break continues. Successful Counterspell spends both sides'
native costs without incoming effects; failed Counterspell allows them. Saved
playback shows the appropriate extent of action and retains native child facts.

Outside this unit: refund/retarget UI, native projectile physics, cancellation
of already applied damage, a generic reaction scheduler, barrel coverage, Dispel
Magic, or unrelated spell-rule repairs. The user subsequently authorized Godot
Counterspell and Globe artwork; that separate source-authoring work is pending
handoff and is not an implemented visual feature here.

## Implemented boundary

- Native Sanctuary checks harmful explicitly selected recipients before costs,
  including multi-target declarations. Damage provenance and existing target
  effect profiles declare intent; mixed effects retain recipient-specific rules.
  Cure Wounds cast on an enemy no longer incorrectly removes the caster's ward.
  Web/Entangle publish their successful footprint so an actual hostile area can
  break it; an empty area does not. Existing Fireball self-break is unchanged.
- `ActionEvent.action_economy_spent` is recorded by the atomic cost owner after
  successful commitment. It also covers named action grants such as Haste; it
  does not infer payment from event phase. Public cancellation facts expose the
  receipt, cancellation phase and outcome, not private costs or inventory.
- `game/data/interruptions.json` owns the supported outcome identities and
  unpaid/paid prefix policy. Source clips, rates, sockets, equipment and spell
  media stay authored by their existing recipes. Target-local effects are
  explicitly suppressed, as cutting only their clock could still show impact.
  Real child facts survive cancellation. Declared repeated selections have
  distinct attempted tracks without inventing application events or rolls.
- Counterspell capture preserves its concrete reaction type. Public projection
  retains only the permitted trigger/result. `game/presentation_group.py` groups
  consecutive reaction roots with their actual trigger for the existing queue;
  every original root still reduces in its original order. Unmatched reactions
  remain separate. The game and clip recorder use the same grouping function.
- The original NeuroStudio Counterspell Special1 recipe, release frame and
  success/failure feedback now play with the incoming cast. A failed reaction
  leaves normal delivery intact. Successful interruption occurs before the
  earliest arriving missile, including distant-first/nearby-later allocations.

The [20-clip review](http://127.0.0.1:8767/runs/20260923T094203Z-087a55/index.html)
contains ten real experiments from both subjective participants, each with four
camera corners. It includes the original Sanctuary attack story, blocked and
allowed Fire Bolt, blocked direct Sacred Flame and repeated Magic Missile,
Counterspell projectile/direct/volley blocks, and checked Fireball success/failure.
Each capture saves native debug input and public player input; rendering consumes
the saved public bytes after native shutdown. All twenty capture checks pass with
no presentation gaps. Representative Fire Bolt frames were inspected immediately
before and after the counter: both actors remain undamaged and the projectile
ends in flight. This is a timing/gesture review, not approval of pending artwork.

## Verification and remaining limits

- 47 native tests passed: Sanctuary contract, real Haste expenditure, maintained
  behavior semantics (including Counterspell costs) and Ice Knife interruption.
- 29 focused saved replay/condition/payment tests passed, including both observer
  roles, grouped reaction release, no phantom effects, and repeated allocations.
- Reviewer ran eight grouping/payment/gameplay/review caller checks, plus the
  sixteen grouped interruption cases. Original ancestry and final cursor agree.
- One focused original-data split-volley regression passed: the first selected
  target is far away and later targets are nearby; interruption precedes every
  arrival and produces no contact/damage imagery.
- Four existing Globe tests passed: direction/level/concentration, partially
  protected AoE, stationary footprint and exclusion of low-level zone effects.
- Changed presentation, projection and review modules type-check without errors.

Counterspell currently ends the incoming media at the resolved interruption and
plays the imported body/feedback. The new suppression/dissipation effects and
Globe's barrier/ripple are **not integrated**. Unpaid/paid prefix fractions are
explicit provisional authoring choices for review. No approved normal spell
trajectory or contact was retuned. This unit publishes hostile footprint facts
for Web/Entangle; it does not claim to have migrated every zone spell.

## Godot candidate received after the timing review

The author supplied
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/abjuration-review/HANDOFF.md`,
with `manifest.json` and `media.json`. It is explicitly a review candidate, not
user-approved or integrated. [Art preview](http://127.0.0.1:8784/abjuration-review/).
The technical contract was read and compared with registered media; this is not
a visual acceptance claim or a new runtime asset-validation requirement.

It contains four-camera success/failure bursts, rear/front Globe layers, eight
horizontal contact directions per camera, incoming alpha-erosion coverage and
independent Globe-clear coverage. Exports run at 144 Hz: Globe apply is [0,96),
hold [96,672), and frame 672 is a loop-check sample, not an extra held frame.
The floor-centered sphere uses one source world unit per five-foot cell and a
two-unit radius. Native canvas is 448 square with pivot (224,224).

Integration details identified, without importing or altering media:

- Atlas offsets are **pivot-relative**; current registered-media storage uses
  native-canvas offsets. Convert that representation once in the importer.
- Incoming dissipation needs alpha coverage over the interrupted frame while
  preserving its palette, registration and frozen flight position. Current
  interruption simply ends the track; mask composition is not yet implemented.
- Clear must preserve the current Globe visual phase. Rear/front shell artwork
  is not a replacement for actor/world depth, and horizontal normals do not
  establish support for arbitrary vertical contacts.
- Native mechanics supply outcome/payment and spatial facts. Presentation owns
  millisecond interruption anchors and body recovery, using the original recipe.
  Do not add renderer coordinates or animation phases to backend events because
  the art demo calls its contact "authoritative".
- Globe may exclude part of an AoE while the rest succeeds. Do not treat every
  protected cell as whole-spell cancellation or reuse Counterspell's erase cue
  for unrelated spell consequences.

These findings were sent back to the Godot author; no new renders were requested.

## September 23 follow-up: readable preparation and Counterspell dispersal

The user reviewed the first clips and found non-projectile interruption too early,
then requested a visible magical contest rather than an abrupt disappearance.
This follow-up supersedes the timing/media status above, not the native rules.

Requested observable boundary: replay the same saved subjective lineages from
both observers and all four cameras. A blocked attempt gets more readable body
preparation; successful Counterspell fractures the already emitted carrier at
its actual flight point; a failed reaction leaves the normal spell moving.
No invented damage, installed area, or target effects may accompany a canceled
cast. A source-only spell is disrupted at the caster's existing body anchor.

Implementation sequence:

1. Retain the imported body's rate; change passive interruption fractions only.
   Unpaid anticipation rises from 0.4 to 0.8 of release. Paid moving delivery
   remains halfway through the earliest flight; a direct cast reaches 0.9 of
   its body duration. These are animation clocks, never engine event phases.
2. Import the supplied four-camera success/failure media, neutral erosion mask,
   and isolated hand sheet. Convert pivot-relative storage once; keep bytes and
   authored ownership. Do not import Globe in this unit or claim art approval.
3. Retain the current logical travel sample at interruption and reproject it per
   camera. Keep its color/frame/rotation; multiply neutral coverage in the full
   original canvas before transforms. Additive material coverage attenuates RGB.
4. Keep the 500ms visual tail independent of native child/contact timing. Extend
   group completion only. Draw the reaction body and source hand energy through
   the existing body layer primitive; burst through registered media/depth.
5. Validate saved replay, finite tail, successful/failed outcomes, all cameras,
   source immutability and mask registration. Replay the existing review inputs;
   no engine rerun is needed for this presentation revision.

Anti-OOP and anti-slop reviewers independently approved this bounded approach.
Both specifically required separating the interruption cutoff from visual tail
completion, retaining logical samples rather than screenshots, covering normal
and additive layers, and preserving the original canvas across sparse parts.
No new event protocol, queue, gameplay graphics fields, spell-name renderer
branches, source hashes, or startup media audit is introduced.

The Godot author is independently exploring formation-specific cloud suppression.
That candidate does not block this point-interception review or authorize fake
native installations of canceled fields. Dispel Magic and Globe presentation
remain outside this follow-up.

### Follow-up result

[Updated saved-input review: 20 clips, both observers, four cameras](http://127.0.0.1:8767/runs/20260923T104902Z-be3b63/index.html).
All checks pass, with zero presentation gaps across 2,138 four-view frames.
The gallery server returned HTTP 200. The inputs are the original recordings,
not recreated outcomes. Fire Bolt breakup/clear and Sacred Flame suppression were
visually inspected in all four views.

Measured Sacred Flame body preparation (12 authored body frames per second):

| Interception | Prior | Revised |
| --- | --- | --- |
| Sanctuary | 366.67ms / 4.4 frames | 733.33ms / 8.8 frames |
| Counterspell | 779.17ms / 9.35 frames | 1050ms / 12.6 frames |

The successful moving carrier retains its original palette while the neutral
mask removes it over a 500ms visual tail. Coral suppression bursts are the new
candidate artwork. Failed Counterspell uses its weaker burst while ordinary
flight continues. With no emitted carrier, the burst is centered at the casting
actor's existing body anchor; it is not a hand-contact claim. The reacting mage
uses the delivered isolated hand sheet through the existing actor-layer path.
The user has not yet approved this integrated appearance.

Validation: 27 replay/split-volley/Sanctuary/import checks and 33
animation-draw/reaction-media/neutral-coverage checks pass. The new real Blur
self-cast tests cover the body-only executor from both observers and four
cameras, including the ordinary choreography drawing caller. Changed runtime
modules type-check with zero errors. Reviewers found no additional event queue,
backend graphics state, or per-spell drawing paths.

The final review also reproduced a separate concrete cancellation defect:
Counterspelled Misty Step correctly spent its bonus action and emitted no spatial
transfer, but presentation's declared-departure fallback still played teleport
art. The bounded correction suppresses that fallback for a canceled declaration;
the earlier branch consuming actual completed descendant SpatialFacts remains
intact. This is covered with real native events and subjective replay.

Final anti-slop review passed after the relocation correction. Another 28 checks
passed across interrupted relocation, ordinary teleport playback (including
one-sided subjective visibility), and interruption replay. These overlap some
of the earlier replay tests and are not an additional distinct-test total.
No native mechanics changed in this timing/media follow-up.
