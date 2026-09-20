# Misty Step: recorded atomic relocation

The user requested Misty Step after confirming forced movement. This unit connects
the existing native spell to subjective saved-event playback. The completed
environment changes remain intact; art production is a separate user-supervised
task. No new VFX production is required for this gameplay connection.

## Existing meaning and bounded changes

Native `MistyStep` already validates a visible, unoccupied, walkable landing within
30 feet, pays a bonus action and a level-2 slot, and commits position once through
`Entity.update_entity_position`. It has no intervening walking Steps. Two concrete
connections need repair: its position commit omits the existing causal parent
argument, and its discovery currently falls through the walking-path branch.
Use the existing parent argument and `PositionDiscoveryContract`, already used by
other position-targeted spells. Do not build a teleport movement/action hierarchy.

NeuroClient's checked Studio sources have no authored Misty Step/teleport draft.
Its historical reduction plans explicitly leave teleport as an atomic relocation
to connect. The original materializer's ordinary cast track is reusable:
Special1, speed 1, release frame 8, hidden equipment and disabled recovery. Generate
the spell's ordinary draft through that format; no fabricated endpoint mist asset
or claim of an original authored teleport effect.

Presentation uses that body's effect anchor and the recorded spatial/sensory
children. The ordinary body track continues at the newly observed position and
its recorded support height after release. A passive binding identifies atomic
relocations; no spell-name conditional or interpolation across intermediate cells.
Reuse the compositor's state keyframes and the existing reducer. Avoid showing
an arrival-only witness the final contact at time zero; preserve actual subjective
disclosures, including an undisclosed opposite endpoint. Native execution and
latest reduction remain independent of historical playback.

## Acceptance boundary

- Input: a real discovered cast, followed by serialized complete public lineages
  for caster and witness. Replay runs with native registries absent.
- Native result: one legal position commit under the spell lineage; bonus action
  and slot spent; no traversed Steps or opportunity attack for teleporting out of
  reach. Discovery can offer a visible landing beyond nonwalkable intervening
  terrain. Existing range/occupancy/visibility refusals remain authoritative.
- Playback result: departure until authored release, arrival at release, and
  remaining body frames at destination height. No intermediate rendered route,
  stale departure pose after completion, or future sight before the anchor.
- Examples: flat forward/reverse, over water, lower-to-upper and upper-to-lower
  support, departure-only and arrival-only doorway witness, and pause before
  release with latest already at the destination. Four cameras per viewpoint.
- Validate recorded state, concrete frame placement, private endpoint disclosure,
  repeated sampling/seeking and fresh-process saved-input replay. Retain the
  previously checked condition fades, movement, forced movement and object
  interactions; do not use this unit to revisit their unrelated limitations.

Anti-slop reviewer: `environment_native_review`, tracing native contracts and
concrete caller tests. Anti-OOP reviewer: `environment_timeline_review`, tracing
the original Studio schema and shared presentation ownership. Review the actual
implementation before completing the unit. Relevant test guidance is in
`HOW_TO_TEST.md`.

## Implemented and checked

Native discovery now uses the existing visible-landing contract and exposes the
spell's 30-foot teleport reach through `get_range()`. The position update receives
the spell effect UUID as its parent. The normal engine still pays the bonus
action/slot, publishes spatial entries and applies sensory consequences. Seven
new native cases cover parentage/no OA, a visible landing beyond an unwalkable
water strip, occupied/out-of-range/unseen refusal and both elevation directions.
Those and three related existing discovery/mobility checks pass (10 total).

The ordinary draft was generated offline using NeuroClient's original
`backendSpellToCatalogEntry` and `createGeneratedSpellPresentationDraft` functions
at `d274f2d`, using Bun 1.3.14. No runtime TypeScript dependency was introduced;
the seven existing draft records and all existing media were preserved. The
passive `relocations` binding selects the shared body cue, whose frame-8 release
is 666.667ms. Its remaining frames continue at the received destination support.
The compositor compiles already recorded state at that anchor once; frame
sampling neither reruns rules nor reduces the event stream again.

The doorway acceptance case exposed an actual projection defect: the old
located-actor fallback could disclose the earlier spell declaration position
when only its later arrival was visible. The fallback now requires the received
contact to match that coordinate, in addition to the existing location grant.
Explicit coordinate grants remain authoritative. This changes no native sight
rules. Both hidden opposite endpoints are absent from the tested public facts;
arrival observations stay undisplayed until release.

Playback checks cover all five spatial variants from both participants,
departure-only/arrival-only disclosure, deterministic seeking, actual draw
commands in four cameras and final idle placement. The broader movement,
placement, forced-movement, visibility and environment selection passes **67
checks**, with the same **two existing stair-occlusion expected failures**. A
separate body-action/player-projection selection passed 25 checks, including
seven of these teleport checks. Focused changed-source Pyright is clean; seven
existing `conjuration.py` diagnostics outside Misty Step were reproduced against
HEAD, with no unrelated edits. Both reviewers approved the final structure.

The [capture gallery](http://127.0.0.1:8767/runs/20260918T184756Z-b1f17a/index.html)
contains **eight experiments / sixteen subjective clips**, each rendered in four
corners. All capture checks pass without reported presentation gaps. The dark
vertical proving map uses actual recorded Darkvision, matching the existing
forced-movement fixture; the bright doorway uses ordinary sight. Extracted
release images are retained under `.runtime/misty-step-20260918/`.

Fresh-process replay `20260918T184933Z-8eb54a` passed all sixteen clips with native
content uninstalled, no scenario imports and an empty EventQueue throughout.
Every saved input and MP4 matched its capture byte for byte; lineages, timeline
heads, latest state and all sampled frame traces matched exactly. Six Darkvision
initial-state diagnostics differ only in the existing process-local
`sense_modes_hash`; actual recorded sense modes match. No source or asset hash
audit was added. `.runtime/misty-step-20260918/replay-comparison.json` retains the
direct comparisons. The gallery server was restarted on port 8767 and returned
HTTP 200 for the new gallery.

No dedicated silvery-mist VFX was authored or substituted: these clips show the
ordinary cast and atomic relocation. Existing terrain/wall occlusion remains
the shared renderer's responsibility. This unit covers Misty Step; it does not
claim that Dimension Door or arbitrary multi-actor teleports are connected.
