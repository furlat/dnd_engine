# Final summoning/Fly phase — independent plan reviews

Date: 2026-10-03. **Both independent reviewers approve the final plan.**
This is design approval only; new Fly/lifecycle media integration and final native
visual acceptance remain pending at the human-requested planning checkpoint.

Reviewed document:
[Summoning presentation, flight and creature corrections](../SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md).
Initial combined-plan SHA256: `f9cd20d4e866eb03f3ac4fdac9a3413a36f0af22fcb90026da91355886ad952f`.

**Current approved SHA256 after the explicit human scale correction:**
`640fd5452a0a2060bdaa6d1e7ab35d1608e4a3359e0f41a3a79a2398126bf0c2`.
Both reviewers separately approved the new Scales paragraph and its two canonical
appearance assignments: all six demons at 1.00, approved animal enlargements
retained, no gameplay Size/footprint or source-pixel changes. Root subsequently
constructed all 24 recipes and verified those values and no animal shrinkage.
The detailed initial design reviews below remain valid with this policy amendment.

## Anti-slop reviewer

Independent reviewer `/root/summoning_antislop` approved the prior complete design
at SHA256 `14712e0a0c76c947ae803d841b4afefa4d1b8234035e5236acf2e7f081250ddf`,
then separately approved the final source-evidence delta at the final hash above.

Verdict: no remaining anti-slop/architecture blocker. Existing movement, appearance,
lifecycle scheduling and geometry owners remain; no additional executor. Exact
airborne poses, clipping and damage-before-departure are implementation acceptance
gates. The final delta preserves the modified body source, synchronizes existing
frames, covers legal non-winged recipients and keeps palette/material ownership.

The reviewer checked the existing source-hand/cast-sourceSockets attachment path
for S1; an unmeasured torso fallback is not necessary. No new human design decision
was identified as blocking this bounded implementation.

## Anti-OOP / ECS / import-DAG and event reviewer

Independent reviewer `/root/summoning_events_items` initially identified one
blocking ambiguity: native `CLOSED` cannot distinguish ordinary cleanup from
shutdown/reset, so the initial plan could produce false departure effects.

Resolved in the plan: all `CLOSED` releases remain silent. Departure VFX consume
only expired, dismissed, defeated and sustain_lost. No speculative native flag,
parent/timestamp heuristic, or new cleanup event was introduced.

The reviewer approved the revised full design at the prior hash above and the
final source-evidence delta at the final hash. Verdict: shared flight and source-
owned layers preserve ECS/DAG ownership; permission-filtered immutable lifecycle
facts feed the existing traversal; the proposed TAKE_DAMAGE/death completion
boundary preserves injury evidence before synchronous retirement. No remaining
event/lifecycle or import-DAG design blocker.

## Limits and execution state

- Reviewers changed no production files and ran no tests/renders during review.
- Source pose findings are candidates, not approved final animation footage.
- The human explicitly accepted the summoning artwork in this chat; the older
  artist candidate header does not revoke that acceptance.
- Previous bounded Wolf/ground/pose/blood corrections are recorded in the
  implementation ledger. No new Fly/summoning VFX integration or Git commit was
  performed in this planning pass.
- Each independent implementation packet and the combined native gallery still
  require the reviews/acceptance set out in the plan.
