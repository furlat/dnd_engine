# Spell integration plan — independent review receipt

Date: October 4, 2026. Production baseline:
`95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`.

Reviewed document:
[Complete the available spell handoffs](../SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md).
Initial approved SHA256 (historical; subsequent human scope changes below):
`2cf346fd78d6afd648cf97c142c39733e23089dd7c82de58d400cc852e280ce1`.

## October4 human amendment — independently approved for human review

The human removed Finger of Death's zombie outcome and clarified that
Telekinesis is completed creature movement, not a maintained airborne hold.
Allied placement is safe; enemy spell impact and a save against Prone remain.
The human then asked to include actual ledge falls and animation representation,
consult BG3, and explicitly selected tabletop falling damage:1d6/full10feet,
maximum20d6. The previous suspension/global-height and zombie materialization
requirements below are therefore withdrawn, not current blockers.

Revised plan SHA256:
`e77a7ed1cc4e61c687bf8915242541488175aa6f60caa3815d006b5813d67241`.
Targeted independent anti-slop and ECS/event/DAG reviews both **approve** this
exact revision; their appended receipts preserve the initial review history.
The Telekinesis3d6/DEX-Prone and single-impact combination are clearly marked design
proposals requiring human plan approval, not previously chosen rules. No
production implementation has begun.

The ECS review records three implementation obligations: use the retained
landing result/contact identity rather than matching actor/time or inheriting
cast contact; retain the causal actor while distinguishing environmental fall
from spell-impact origin; reject obstacle clearance conservatively where the
existing 2D queries cannot establish it. These preserve the plan's shared
movement/event contract and do not authorize another executor or Z-state model.

The production-owned visual note in the missing-assets handoff was reviewed.
It requires existing-pose/media reuse first and does not commission new art.
Local documentation links were checked; no production code or tests changed.

## Initial independent decisions (historical)

- **Anti-slop — approved**, `/root/spell_plan_antislop`.
  [Detailed receipt and original rejection history](SPELL_VFX_PLAN_ANTISLOP_REVIEW_2026-10-04.md).
- **Anti-OOP/ECS/import-DAG/events — approved**, `/root/spell_plan_ecs`.
  [Detailed receipt](SPELL_VFX_PLAN_ECS_REVIEW_2026-10-04.md).
- **Walls/weather/solar/holy factual cross-check**, `/root/audit_wall_cold_solar`:
  concrete source corrections were incorporated before both final approvals.

The two final reviewers were separate local subagents from the three source
audit/design contributors. No desktop chat was read or contacted.

## Corrections in the initial revision (historical)

1. Added Hold Monster's missing implementation/validation row, including
   accepted large-body chains/hold and independently owned Paralysis.
2. Identified numeric forced height and falling as **new required native work**
   for SRD Telekinesis; specified support, occupancy, damage/Prone, height-only
   publication and range/LOS/area consumers. Removed the false implication that
   an existing fall resolver could simply be reused.
3. Made Antimagic retain source identities/clocks and gate exact owned
   contributions, including direct-state contributors. Removal/reapplication
   would replay one-time benefits and is replaced, not retained as another path.
4. Specified retained per-cast Harm/Feast sources and shared effective child:
   ordinary same-name replacement would discard still-live weaker effects.
5. Corrected Force: damage/Dispel immunity does not confer Antimagic immunity.
   Corrected Stone: nonmagical material exists from creation; permanence ends
   the maintained-spell dependency.
6. Made Guardian's Large occupancy, inside-to-inside movement trigger and
   caster-independent resolution actual backend tasks, not assumed facts.
7. Pinned the human's quick Feast/full benefits/**10 turns** decision to the
   existing native duration clock. Its separate prop lifetime is visibly a
   proposed game choice, not misattributed to the human.
8. Kept Finger's canonical Zombie materialization at the installed composition
   boundary, with no upward bootstrap/content factory import.

## Initial scope and evidence limits (historical)

The plan covers 28 first spell integrations, six named existing spell follow-ups,
available straight Thorns/Wind work, shared conditions/surface transitions and a
separate accepted class-presentation packet. Four missing art deliveries remain
explicit. All delivered art is now human accepted; dated audit acceptance gates
are superseded, not reopened.

The independent approvals certify this **plan**, not implementation or visual
quality in the running game. The plan still requires human approval. Proposed
bounded world adaptations and the narrow Finger zombie exception are stated in
the plan, not silently treated as previously approved. Implementation must have
packet reviews, public behavior/replay tests, in-engine evidence and full-suite
reconciliation as specified there.

Only documentation was changed in this planning turn. No production code,
bindings, installed art, test suite or rendering jobs were changed/run. Source
inspection, official SRD reference checks and local documentation-link checks
are the evidence for this stage. Earlier audit hashes continue to identify the
historical pre-acceptance documents; their new acceptance notices are labeled.
