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
