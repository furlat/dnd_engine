# Six healing/support spells — implementation and review

User scope: integrate the delivered Aid, Lesser Restoration, Greater Restoration,
Heal, Mass Cure Wounds and Mass Heal assets; request missing assets and finish
the event-driven review. The sensory batch and new spell auditions are separate.

## Existing contract and bounded work

Native classes already discover/validate targets, spend actions/slots, apply
healing or conditions, and produce complete lineages. Aid increases maximum HP and therefore derived current HP (maximum minus damage
taken), without a HealEvent; this integration preserves that native contract. Restoration
removes native conditions; mass healing affects native resolved recipients.
No presentation code decides recipients, healing amounts, or condition removal.

The delivered recipient effects are cropped 512px canvases with explicit ground
pivots and back/front layers. Import those frame addresses and original pixels
into existing sparse projectile storage. Author the six Studio recipes separately
from the importer. Keep caster glow palettes, body timing, and recipient placement
explicit in data. Four camera exports use fixed world orientation independent
of caster/recipient body facing. No XYZ volume or terrain footprint is needed
for an actor-attached effect.

Five spells use finite recipient media. Aid uses existing condition membership,
application/hold crossfade and removal fade; the Godot author supplied a
certified quiet loop instead of repeating the application burst. Reacquired
membership enters the quiet loop. Removal advances the current phase while
fading. Existing mechanisms already support this without an Aid executor.

## Implementation order

1. Study native outcomes and shared healing/condition/cast presentation. Request
   missing q1–q3 and Aid hold from the source task (requested; acknowledged).
2. Anti-slop and anti-OOP review of this bounded plan. Incorporate concrete
   findings; don't turn speculative unrelated mechanics into blockers.
3. Import delivered cameras and caster sheets offline. Add explicit Studio
   recipes and Aid condition media using existing schema and bundle registration.
4. Add native scenario recordings covering touch, ranged and multi-recipient
   effects, unselected bystanders, healing caps, actual condition cleanup, and
   Aid application → movement → removal. Preserve both subjective perspectives.
5. Cold-replay tests check public outcomes, contact timing, no damage/blood
   side-effects, recipient selection, ground registration, and four camera banks.
   Fix only demonstrated defects that block these contracts.
6. Generate paired four-camera clips from those real recordings; inspect frames
   and late tails. Run scoped regressions and typing. Record evidence and review
   gaps here and link the focused gallery in the recovery plan.

## Review and result

Both reviewers approved the shared-data approach. Anti-slop review found an actual
Aid replay mismatch: existing resulting_stats already records normal HP, but
ConditionChangeFact reduction discarded it. Reuse that fact at the condition
commit; do not fabricate healing. Native discovered-action execution additionally
exposed Aid overriding the unused get_num_projectiles method, so its discovery
incorrectly allowed only one target. Use the existing get_multi_target_count
hook, with its existing three-target value. The new scenario exercises discovery
and all three applications rather than calling the spell directly.


Implementation review also caught the shared cast drawer attaching terrain-area
clipping to any ground-targeted spell. Mass Cure has an AoE target but its media
belongs to individual actors; recipient attachments now retain ordinary actor
occlusion and never receive terrain projection. The regression exercises the
actual native Mass Cure timeline in all four cameras.

Two passive authoring additions serve explicit source requirements:
`scaleWithActor` keeps finite recipient effects at the actor's current uniform
scale; `sustain_start_ms` places Aid hold frame zero at the certified overlap
start without rotating source frames. Existing recipes keep false/zero defaults.
Aid uses the visual body's ground origin (the existing body attachment), so its
wrap follows the actual displayed actor position. All source pivots remain
unchanged. No runtime source scan, hash or per-spell executor is added.


The second ECS review reproduced Aid reapplication: the intermediate legacy
maximum records the new modifier before the old one is removed, while the final
stats snapshot is correct. Public condition commits now prefer that completed
normal HP, maximum HP and AC snapshot, retaining legacy scalar fallback. A real
second discovered Aid cast confirms no phantom stacking in either perspective.
The final validation below includes the repeated-Aid regression.

## Completed delivery and validation

All six source deliveries are imported, including the requested q1–q3 camera
banks and Aid's separate four-camera lifecycle. The importer copies native
pixels and preserves sparse full-canvas offsets and pivots. Recipient media
uses fixed world-facing camera selection, not the recipient's body facing.
Aid hold starts at source application frame 258, crossfades through frame 280,
and loops the authored 576-frame quiet hold at 144 fps. Removal fades the current
phase over 667 ms. The extra certification frame is excluded from the loop.

[Focused review: 14 paired four-camera clips](http://127.0.0.1:8767/runs/20260923T202705Z-702275/index.html).
Seven native scenarios produce caster and recipient views, each with all four
cameras in one video: the six spells plus self-cast Heal. Event inputs are saved
under `.runtime/animation-review/inputs/healing-batch*` and replayed without
rerunning mechanics for rendering. Aid shows application, two recipients moving
and explicit native condition removal; its removal is not claimed as an expiry
or concentration rule. Mass spells include unaffected bystanders. Restoration
and Heal exercise actual native condition cleanup and capped healing.

All 14 captures pass, with zero failed checks and zero presentation gaps across
1,878 video frames. Contact frames for all seven scenarios in all four cameras
were inspected, along with Aid's quiet hold during movement. These captures
await human visual review; inspection is not a claim of human approval.

Validation: 109 presentation/import/replay checks pass, plus 43 distinct native
cleric/healing regression tests (152 total). Two existing gallery-encoding tests
were deselected from the focused suite; the actual 14-clip gallery was generated
separately. Changed-file typing reports zero errors. Coverage includes public
outcomes, contact-time state, no damage reactions, selected recipients, native
Aid reapplication, condition phase continuity, exact sparse pixel/pivot import,
all four camera banks and recipient-versus-terrain layer ownership. No runtime
source validation, hashing or new per-spell rendering executor was introduced.
