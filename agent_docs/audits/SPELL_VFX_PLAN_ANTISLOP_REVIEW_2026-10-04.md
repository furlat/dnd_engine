# Spell VFX plan — independent anti-slop review

Date: 2026-10-04. Initial verdict: **REJECT pending the two bounded corrections
below**. This history is preserved; the final approval appears at the end.

Reviewed plan: `agent_docs/SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md`.
Exact revision SHA256:
`bacbe1995c8a85e50cb6ff77727774a80c249110e9eb437a732f7f9bdea9224e`.

This is a plan review, not implementation acceptance. Read AGENTS.md,
RECOVERY_PLAN.md's current position, HOW_TO_TEST.MD, the plan, current native
and presentation source, intake audits, the master artwork handoff and the
Hold source contract. The official SRD 5.1 was consulted for the selected rules.
No production edits, imports, tests, captures or external-chat access occurred.
Only this receipt was written.

## Required corrections

1. **Hold Monster is counted but has no implementation packet.** The scope
   includes it at lines 35–36, and final acceptance promises every one of 34
   entries. Packet 1 supplies neither a Hold Monster row nor its delivered Ogre
   chain/held-pose integration. Merely selecting the shared Paralyzed cue does
   not consume the accepted chains. Current `game/data/condition-recipes.json`
   around line 7360 still selects `control.hold_human` for Hold Monster. The
   accepted source contract is
   `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/control-binding-study/production-handoff/HANDOFF.md`,
   revision `eefffc58e8c5`, with the held-frame supplement in
   `hold-sustain/media.json`. Add a concrete row covering native 90-foot visible
   non-undead targeting, WIS/repeat saves, one-minute concentration and higher
   slot targets; explicit human/Ogre attachment profiles and production pivots;
   application → held frame 96 → release, with the supplied crossfades;
   independent paralysis ownership; and cancellation, large anatomy, multiple
   sources and four-camera cases. Do not silently stretch the human chains or
   adopt the preview's Ogre scale. Native ownership remains in
   `dnd/spells/enchantment.py` (`HoldMonsterEffect`, `HoldMonster`).

2. **Telekinesis hides a missing fall resolver behind an existing-capability
   claim.** The extension table at line 152 names existing terrain/fall
   operations; lines 390–399 require elevated release but only say to use
   ordinary terrain and fall rules. The current native `TelekinesisMove` in
   `dnd/spells/transmutation.py:1652` admits ground walkable/unoccupied XY
   destinations, and a bounded source search found no native falling resolver
   or fall-damage operation. Existing `WorldObjectPlacement` supplies integer
   height bands; that is not fall resolution. Explicitly propose the necessary
   shared native forced-release/fall operation: its owning module, height unit,
   supported landing/occupancy policy, applicable fall damage and Prone outcome,
   and publication through existing movement/damage/condition facts. Include
   failed maintenance, switching, suppression/expiry and occupied-landing cases,
   with serialized replay. Keep the stated no-multi-floor/no-physics boundary.
   The correction is to plan this required native work, not to omit suspension
   or declare the selected SRD spell incomplete because the code is absent.

## Findings that do not block this plan

The plan explicitly includes necessary rules work rather than allowing the
renderer to invent outcomes. Finger of Death's narrow permanent Zombie branch
is plainly proposed as an exception to the undead deferral. Heroes' Feast
records the human's quick cast/eat and ten-beneficiary-turn adaptation; its prop
lifetime is separately proposed. Its listed benefits and serving wording match
the selected [SRD source](https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf)
apart from the disclosed timing adaptation. Grounded wall forms, transparent
Ice/120-HP whole dome, existing Fly behavior, retained event ownership and
separate class presentation scope remain explicit.

The common presentation work has real consumers, rejects name-based inference
and alternate runtimes, and requires native/replay/visual evidence plus both
independent reviews. No broader renderer, class or character rewrite is needed
to address these findings. Approval requires a fresh exact-revision check after
the two corrections; this receipt does not approve subsequent edits.

## Final bounded re-review — approved

Verdict: **APPROVE the plan** at exact SHA256
`2cf346fd78d6afd648cf97c142c39733e23089dd7c82de58d400cc852e280ce1`.
The initially supplied re-review hash `d1893a31...` was superseded by the plan
author's final composition-boundary clarification; the hash above was checked
against the actual saved file after reading the amendments.

Both original blockers are resolved:

- Packet 1 now gives Hold Monster a concrete rules, accepted Ogre/held-pose and
  independent Paralysis row, including higher-slot selection and lifecycle
  cases. The shared intake and camera gates retain the source registration and
  full lifecycle requirements.
- Packet 6 explicitly calls falling a new bounded native transaction. It names
  support lookup, vertical sweep, atomic landing, damage/Prone, retained facts,
  height-only publication and the range/LOS/occupancy/area consumers. Occupied
  landing and unsupported-void limits are disclosed game adaptations. Required
  suspension is planned, not deferred or implemented only as a visual offset.

The related amendments are consistent with this bounded plan: Force's damage
and Dispel immunity is distinguished from Antimagic suppression; Stone's
nonmagical material is distinguished from its maintained spell dependency;
Antimagic contribution gating and per-cast Harm/Feast ownership are explicit
native changes with independent validation gates. Feast now uses the existing
ten-tick recipient condition clock at native turn start, with first/tenth ticks
tested; its separate ten-round prop limit is visibly proposed rather than
attributed to the human. Finger's canonical Zombie construction stays at the
installed composition/encounter boundary without upward content imports.

No unresolved anti-slop plan blocker remains within this review's scope. This
approval does not certify implementation, authorize broader character/spatial
work, or substitute for the human's plan approval and the required ECS review.
No production code, artwork, tests or captures were changed or executed during
the re-review. Only this review receipt was updated.

## Human-directed movement/fall amendment — approved as a proposal

Date: 2026-10-04. Verdict: **APPROVE the amended plan for human review** at
exact SHA256
`e77a7ed1cc4e61c687bf8915242541488175aa6f60caa3815d006b5813d67241`.
Scope was only the Finger/Telekinesis/shared-fall amendment and the added
production-only visual-gap note in the missing-assets handoff. Earlier review
history remains above; its suspension and Zombie proposals are now superseded
by the human's explicit changes.

No anti-slop blocker found in this amendment:

- Finger's Zombie outcome, delayed birth, permanent control and content work
  are removed. Ordinary death/corpse/item handling remains the existing owner.
- Telekinesis completes one creature transfer per use. It removes its held
  victim/Restrain branch, stale free follow-ups and the previous global actor
  height extension. Concentration retains repeat permission only. Willing
  allied placement is safe, with ordinary destination hazards kept separate.
- Shared falls are now explicitly requested scope, not an unannounced spatial
  rewrite. One landing operation serves existing movement producers through
  existing movement, damage, condition and presentation records. Real support
  heights and committed drop distance drive results; cosmetic arc height does
  not. Rails, walls, occupied landings and missing tiles have bounded admission
  rules, without nearest-free side jumps, stacked maps or persistent hovering.
- The human-selected tabletop fall rule is distinguished from the proposed
  Telekinesis profile. The 3d6 hostile impact, STR movement resistance, DEX
  Prone save and larger-of-spell-or-actual-drop combination remain visibly
  subject to human approval. This review approves their explicit presentation
  as proposals; it does not record those balance choices as human decisions.
  The combination uses one linked landing impact and preserves separate real
  destination hazards, avoiding duplicate spell-plus-fall damage resolution.
- The added handoff note correctly assigns descent, shadow/occlusion and
  contact timing to production. Tumble/dust remains a conditional evidence-
  based gap, not a new artwork order. Existing art acceptance and G1–G4 remain
  intact; no character-sheet commission or external-chat contact is implied.

Acceptance names shared Shove/spell-push falls, downward Jump, safe transport,
interruption, occupied landings, damage/Prone/life results and saved replay.
These make the amendment reviewable without a new framework or per-spell
renderer. No broader re-audit, implementation, tests, artwork changes or chat
contact occurred. Only this receipt was appended.
