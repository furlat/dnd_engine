# Final summoning/Fly phase — independent plan reviews

Date: 2026-10-03. **Both independent reviewers approve the expanded design.**

## Current combined approval — final phase plus all 17 Goblin sheets

The human requested the dedicated Goblin scale correction and the complete
missing-Goblin plan. Both `/root/summoning_antislop` and
`/root/summoning_events_items` independently verified and approved these exact
final bytes:

| Document | SHA256 |
| --- | --- |
| [Final-phase plan](../SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md) | `16d93fcdd9f659867b562e454b6d6e80f3d34f3dc724d34bc82bfeff96b79a6d` |
| [Goblin amendment](../GOBLIN_ROSTER_FINAL_PHASE_PLAN_2026-10-03.md) | `e7c25917da0279d2d78e50011b29cfb8c7c45308e516a99c9a49a539c2544993` |
| [Original-art/item crosswalk](GOBLIN_ART_CROSSWALK_2026-10-03.md) | `19b624be9dfff59cb31a3a03508a68f9740fd03168e6dc9e180c2b2a94549cdb` |

**Anti-slop verdict:** no remaining design blocker. Existing combat/render owners,
original proportions, bounded deduplicated native item variants and durable loot
are retained. Excluded speculative abilities remain excluded. Review removed an
unsupported exact pistol-weight promise, reconciled the appendix's overly broad
palette-variant prohibition, and made Goblin08's missing physical staff-strike
presentation an explicit acceptance gate.

**Anti-OOP/ECS/import-DAG/event verdict:** no remaining design blocker. Canonical
Goblin01 keeps one declaration/ref; its ordinary constructor and sixteen new
recipes share passive definitions without a reverse import into registration.
Items, traits, spells, Multiattack and lifecycle facts keep their existing owners.
No additional rules executor, duplicate event family or per-species renderer.
The final staff-gate amendment was separately rechecked and approved.

**Human decisions still open:** the two baked rider/wolf sheets (11/12) as one
combatant versus deferral; Goblin17's corrected pistol selection versus deferred
ranged use. Review does not decide these for the human. The proposed pistol's
modular Musket donor is an explicitly disclosed silhouette approximation. No
mount system, ammunition tracking or new weapon artwork is authorized by review.

**Applied correction:** `bestiary_content._build_goblin` now overrides only the
canonical dedicated Goblin01 scale to1.00. Direct canonical materialization
returned Goblin1.00, legacy modular archer0.82, legacy modular caster0.82. No image
bytes, gameplay Size, equipment, ability or new roster implementation changed in
this planning pass. The old videos retain their old scale until regenerated.

Reviewers performed read-only review and no tests/imports/recordings. New roster,
Fly/lifecycle integration and visual acceptance still follow the packet gates.
This is design approval, not a claim that all17 have been installed or accepted.

## Historical review — before the Goblin scope amendment

This is design approval only; new Fly/lifecycle media integration and final native
visual acceptance remain pending at the human-requested planning checkpoint.

Reviewed document:
[Summoning presentation, flight and creature corrections](../SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md).
Initial combined-plan SHA256: `f9cd20d4e866eb03f3ac4fdac9a3413a36f0af22fcb90026da91355886ad952f`.

**Previously approved SHA256 after the demon scale correction:**
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
