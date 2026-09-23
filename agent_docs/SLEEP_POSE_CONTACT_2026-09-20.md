# Sleep: fall, resting contact and wake-up

Requested behavior: Sleep plays the mapped fall once and holds the final sleeping pose. A later hit targets the resting body. Actual damage wakes a surviving creature, which rises by reversing the same mapped clip. A lethal hit must not resurrect or stand the body up.

Boundary: real saved subjective event sequences → shared presentation timelines → four-camera game frames. Mechanics, condition membership, HP and life state remain native event results. No new game condition, spell-specific renderer dispatch or alternative queue.

Observed gap: current condition bodyPose overrides Idle with the final Die frame immediately; application/removal have no body transition. Projectile and anchored-media endpoints use the standing rig body anchor regardless of retained Sleep.

Implementation:
1. Author a finite body transition on condition application/removal (clip, speed, reverse). Reuse condition timelines, mapped rig clips and absolute sampling; include finite transitions in existing lineage joins. Author Sleep only.
2. Carry the retained rest pose in the existing ActorContact. Author per-rig/per-facing final-pose body anchors beside rig data; all incoming spell and ranged-attack attachment paths share that selection. Standing contacts retain their approved numerical values.
3. On application play the fall; while asleep hold that pose even at incoming hit contact. Damage/flash retain their existing actual-contact timing. On actual removal reverse the fall if alive. Death has priority and remains down. No delay of HP until standing.
4. Extend the existing native Sleep/fire-bolt wake replay tests and paired clips: continuous fall/hold/rise, lowered target from all cameras, unchanged other sleeper, reverse seeking and lethal wake suppression. Reuse saved inputs for existing scenes; record a native lethal case only where missing.
5. Run relevant cast/attack/condition/lifecycle regressions and inspect rendered falling/rising/contact frames before delivery.

Anti-slop and Anti-OOP/ECS review: GO from graphics_antislop / graphics_ecs_review. Preserve native callback timing; use target-facing anchors; transition only when aggregate pose changes; only ALIVE rises; an already-resting lethal target holds the down pose. Standing spell/arrow coordinates remain unchanged.

User correction during study: Fire Bolt’s approved positioning was incorrectly normalized in the preceding all-spell audit. Its complete projectile record is restored from the committed authored version (the only changed Fire Bolt section). Shared-body tests must not force this separately registered art into a different pivot. Prove restored output with the same historical clips before adding any resting-pose delta.

The already-approved four-spell art handoff remains queued; its requested directional exports can finish while this user-requested pose correction is handled.

User clarified during implementation: the rise is the wake-up gesture; omit a separate standing TakeDamage flinch. Damage is received while lying down.

Fire Bolt restoration evidence: `20260920T205937Z-99d178` level/height MP4 bytes exactly equal `20260920T005836Z-d15230`. This is an ad-hoc byte comparison, not a source/asset hash or new test framework. Standing results are preserved.

## Implemented result

- Sleep application plays one mapped fall at 1.5 playback speed, then holds its final frame and Zzz label. Native removal plays that same clip backward at the same speed while ALIVE. No standing TakeDamage flinch is resumed afterward.
- All shipped body rigs now carry authored final-Die body anchors. Incoming spell and arrow endpoints add that target-facing displacement after their existing insets; target-body media uses the same displacement. Standing points stay unchanged.
- Real lethal Sleep/Fire Bolt capture added with both observer packets. Native corpse HP retains its actual negative value here; tests preserve it instead of inventing a clamp. The sleeping lethal recipient does not acquire the caster’s unseen spell fact, but its damage and life after-values remain in its complete causal sequence.
- Root inspected four-camera fall/hold/hit/mid-rise/standing montage and caught/fixed a short post-rise re-fall caused by the old hit body duration outliving the wake gesture. A post-rise frame assertion now covers that interval.
- Eight focused clips pass: ordinary Sleep/wake, cannon Sleep/wake, lethal Sleep hit from both subjective perspectives, plus flat/elevated standing Fire Bolt. Gallery: http://127.0.0.1:8767/runs/20260920T210757Z-5b8bc5/index.html .
- Entire Fire Bolt authored row equals the committed version; level and height videos remain byte-identical to 005836, even with resting-pose support enabled.
- Final animation/cast/attack/condition/lifecycle/device selection: **243 passed in 82.09 seconds**. Selected production typechecks: zero errors. Independent final anti-slop and ECS reviews: GO. Recorder lane: **8 passed in 190.05 seconds**. Full-spell-gallery result is appended after completion.

No native mechanics changed for this correction. Existing saved histories are replayed; only the new lethal scenario runs mechanics to create its permanent input.

Final complete integrated-spell gallery: **82/82 passed**, 9,919 four-camera frames, no reported gaps. All 31 integrated spells plus Ice Knife child burst; http://127.0.0.1:8767/runs/20260920T210950Z-5bbc76/index.html . This supersedes the earlier 78-clip gallery for Sleep and Fire Bolt. The eight focused clips remain useful for reviewing just this correction.
