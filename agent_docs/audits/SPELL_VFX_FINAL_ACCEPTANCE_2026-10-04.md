# Spell backlog implementation and final validation — 4 October 2026

The approved eight-packet implementation is complete within its recorded
available-art and installed-rig boundary. This covers 34 named spell entries,
available Wind/Thorns and surface deliveries, and 21 existing class presentation
sets. It includes substantive backend and renderer changes, not just asset bindings.

Start with the [complete feature trace](SPELL_FEATURE_CHANGE_TRACE_2026-10-04.md).
It links the before/after behavior, approval authority, owners, exact files,
event/API changes and limitations. Its native appendix covers all 59 changed
backend/AI files; the client/tool appendix covers all 209 files, including all
18 new rendering modules. Baseline: `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`.

## Final validation

| Boundary | Result and precise claim |
| --- | --- |
| Native engine, AI and progression | 3,009 passed, no failures/errors/skips. |
| Architecture and root packaging | 120 passed, no failures/errors/skips. |
| Client | All 3,522 collected cases accounted for exactly once in the full run. That run had 3,517 passes and five failures. All five were corrected and covered by complete affected-file reruns: 90 + 58 + 19 passed, no failures/errors/skips. |
| Typing | Active `dnd`, `game`, `ai` and 42 changed authoring tools: zero errors/warnings. The two final changed production modules were checked again: zero errors/warnings. |
| Standard engine recordings | 283 selected passing recordings in 34 original-clock runs; 4,681 recorder checks, 46,928 frames, zero reported presentation gaps. |

The client result is a complete run plus bounded correction reruns, **not a claim
of one uninterrupted zero-failure full run on the final revision**. Source/data
and tests were unchanged throughout the full 3,522-case run. The final delta was
limited to two production files and two fixture files; all four are pinned.
No native code changed after the native/architecture receipts.

The machine-readable receipt is
[final-acceptance.json](../../.runtime/spell-vfx-20261004/validation/final-acceptance.json).
It contains every original and rerun XML hash, exact failed node identities,
the no-missing/no-duplicate reconciliation and each selected gallery manifest.
Original failures remain available beside the passing reruns.

Final 1,622-file source/data/test snapshot:
`5ac712f84696453b388fbe899515696cecb024e0d35b8aa59dd78b3c1008ad27`.
Its hash encoding and individual file hashes are recorded in
[source-after-final-corrections.json](../../.runtime/spell-vfx-20261004/validation/source-after-final-corrections.json).

## Five final failures and their corrections

| Cases | Diagnosis | Correction |
| --- | --- | --- |
| Two Grease save outcomes | Real regression: extending contact-effect completion introduced a 500 ms decorative pause at each ground entry. | `game/choreography.py` carries those decorative ground-entry cues without extending the movement join. Applied damage, dousing, summon lifecycle, suppression and interception retain their blocking tails. Existing no-pause assertions remain unchanged. |
| Window mask selection | Real regression: dependent-target selection skipped object masks when its current options contained no declared object. A disallowed wall could fall through to a target behind it. | `game/controls.py` preserves the original object-action mask admission as well as dependent object options. The existing regression assertion remains unchanged. |
| Demonbeast rig slots | Stale fixture: the committed, accepted rig already has separate shadow/body/effect layers; the test expected two. | Update the exact per-rig slot expectation. Original source hashes, image dimensions and every body frame/facing remain checked. No artwork or rig binding changed. |
| True Seeing expiry | Stale scenario: it waited only 24 turns after the planned correction to a 600-round spell. | Advance real turns with a bounded 1,204-turn loop for the two actors, stopping on actual removal. Preserve final visibility and independent Invisibility assertions. No private clock mutation or shortened spell duration. |

These are the only post-full-run changes, recorded in
[final-correction-delta.json](../../.runtime/spell-vfx-20261004/validation/final-correction-delta.json).
The affected-file reruns exercise movement, damage/quench and summon tails,
window picking and dependent selection, original rig source and both subjective
concealment replays. Grease is the only authored decorative `ground_entry`
contact; the selected spell recordings do not need replacement for that repair.

An earlier validation attempt started before class-schema/data authoring was
finished. Its failures and the terminated third shard are retained separately;
that attempt is not counted as complete validation. The stable full run above
replaced it. The ledger records the earlier real corrections as well as fixture
migrations; they are not dismissed as universally pre-existing failures.

## Reviews and visual inspection

Independent [anti-slop](SPELL_FINAL_ANTISLOP_REVIEW_2026-10-04.md) and
[ECS/event](SPELL_FINAL_ECS_EVENT_REVIEW_2026-10-04.md) reviews are closed and
approved within their recorded authorship boundaries, with no unresolved blocker.
Both independently reconciled the five failures, final four-file correction and
current source hashes. The [root integration review](SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md)
covers independently inspected delegated work and visual evidence. No author is
treated as the independent approver of their own implementation.

The [standard engine gallery](http://127.0.0.1:8768/spell-vfx-final-acceptance-20261004/index.html)
retains original native inputs, subjective traces, camera recordings and clocks.
The [coverage matrix](SPELL_VFX_VISUAL_COVERAGE_2026-10-04.md) maps every named
spell and class set to its evidence. Recorder checks and selected frame/source
inspection do not establish that every frame was manually watched.

## Explicit remaining limits

- Later artwork: general-heading Cone of Cold, Call Lightning V5, isolated Wind
  interception gust, and the correctly dimensioned 20-foot Thorns ring.
- Ogre's unimported rig remains character-port work. Fixed rigs without measured
  sockets or separable equipment omit unsupported exact attachments.
- CPU/Pygame source ports do not promise identical whole-scene Godot lighting.
  Force ordinary weapon contacts retain the documented coarse-cell/shell
  registration approximation; exact weapon XYZ was not supplied.
- Paused server/manual lanes and retired authoring tools are outside the active
  validated boundary. They are not claimed green by these totals.

No additional roster, ammunition, grappling, cloud-rule, continuous-flight or UI
project was introduced. No external chat was read or contacted. Changes remain
uncommitted for the human's review.
