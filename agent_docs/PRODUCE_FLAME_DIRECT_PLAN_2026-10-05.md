# Produce Flame — direct damage cast

User decision: remove retained flame/light and later Hurl/Dismiss gameplay.
BG3 itself retains those choices; this is the user's explicit simplified damage
variant, not a claim of a literal BG3 port. Keep the existing30-foot ranged spell
attack,1d8 fire and shared cantrip scaling. One ordinary spell action, hit/miss,
normal targeting, defenses and action payment. No new spell systems.

Delete the now-unused retained condition/actions and their content registrations.
Fold the existing hurl damage implementation directly into ProduceFlame. Remove
its current persistent condition presentation and action alias. Retain original
finite flame projectile/impact artwork and ordinary Attack5/Magic2 casting. Update
native hit/miss/repeated-cast examples and affected condition tests. No new art.

Verification: actual cast success/miss/scaling, self/range rejection before cost,
no light/condition/granted actions, spell defenses/origin; native two-observer
animation replay and four-camera hit/miss clips. Independent anti-slop and
anti-OOP/ECS reviewers inspect the bounded final diff. No external chats.

## Frightened — deferred by user

The user will have the Godot artist provide an overhead condition symbol,
consistent with Blinded and other condition markers. The temporary violet body
outline was removed. Existing Frightened mechanics and wisps remain unchanged.
The experimental Fear recording in the bounded gallery is superseded; it is not
accepted production presentation. No communication with the artist was sent.

## Completion evidence

Produce Flame is a single targeted damage cast in backend and presentation.
Retained light/condition/Hurl/Dismiss definitions and presentation alias removed.
Native hit/miss paired-observer clips passed all six capture checks, including the
now-superseded Fear experiment. Final affected tests:112 passed; the earlier
nature/roster/lifecycle run passed90 with one overstrict new Silence assertion,
corrected to match existing execution-phase cancellation and rerun successfully.
Offline authoring dry run has no changes. Independent anti-slop and ECS reviewers
approved the bounded source changes; no new rendering framework was introduced.

Evidence: `.runtime/produce-flame-direct-20261005/` (tests and authoring logs),
`runs/20261004T233223Z-50bf7d/` (native recordings). Only the Produce Flame clips
remain relevant to this completed change.
