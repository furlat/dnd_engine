# Milestone view and motion descriptions — implementation ECS review

2026-10-05. Current source review. No production edits.

**Requires one correction before acceptance: interrupted delivery anchors must not be admitted as completed/contacting effects.**

## What is sound

`presentation_timing.py` is a read-only projection of existing bound fields and visit offsets. It introduces no scheduler, game rule execution, registry or inferred dependency edges. Cast application IDs are retained separately from target identity. Ground delivery stays distinct. Motion reconciliation stays explicitly tagged. Shared narrative/trace consumers remove duplicated offset traversal. Body cue fields are normalized without adding their start twice.

MotionDescription is passive authored data on the existing RigTables/BodyClip owner; `animation_data` carries it into modular clip definitions. Fixed-rig descriptions remain absent unless specifically authored, preventing automatic application of modular gesture prose to unrelated custom art. This is the right boundary. This review does not claim fresh visual validation of the imported prose.

## Blocking interruption case

`interruption.interrupt_delivery` truncates only `body_end_ms` and `complete_ms`. It deliberately retains original release/contact/application/recovery dates for prefix sampling. `ActionNode.interrupted` identifies that situation. The new milestone collector currently publishes every original anchor unconditionally.

Consequences:

- a cast stopped during anticipation can export a release later than its actual completion;
- an interrupted projectile can export target contact and application HP/flash/number milestones although that delivery never completes;
- narrative consumes action release and application contact as admission dates, so cancellation text can disappear beyond the head's actual duration;
- exported data mislabels retained sampling parameters as witnessed/effective milestones.

Required fix: distinguish inactive diagnostic source anchors from admitted milestones, or omit inactive anchors from the semantic milestone view. An actually reached release may remain visible when before the cutoff; target contact/result anchors cannot be manufactured from unchanged original application fields. Do not blindly clamp every future date to cutoff, which would invent simultaneous impacts. `interrupt_body` similarly sets `effect_ms=stop` for prefix termination: it must not be described as the spell's successful effect merely because the scalar is named effect.

Add a cancellation/prefix case asserting no admitted release/contact/HP past actual completion and no missing cancellation narrative. Full motion description at action start also needs prefix-aware wording; full "releases/settles" prose is not evidence those stages occur. That wording concern is shared with the narrative reviewer.

## Coverage limits

Current enum includes life but the collector does not enumerate lifecycle cues; equipment exposes completion only, not its appearance commitment; retained owner anchors are not yet inputs. These are explicit remaining coverage work, not defects in the fields already projected. Do not label this complete all-family milestone coverage yet. No dependency graph has been exported or validated by this view.
