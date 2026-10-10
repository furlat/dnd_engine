# Detached review record

Plan SHA-256:
`72f3cccd2e90e6b991495b044147f3eed7a4863f3049ace40d79770d4ad990ac`

This revision was rejected and superseded. Its verdicts do not apply to later
plan bytes.

## Internal review

`REJECT 72f3cccd2e90e6b991495b044147f3eed7a4863f3049ace40d79770d4ad990ac`

Material findings: the shared `ActionBindingSubject` union named a
discriminator but did not freeze the discriminator field or literal wire
values; and the required zero-target non-self Spell Studio fixtures could not
enter the current mapper/CastIntent without an explicit no-frame disposition
or a renderer expansion.

## Independent external review

Reviewer task:
`019ff6ba-7b0e-7003-81ff-b815d9a9df29`

`REJECT 72f3cccd2e90e6b991495b044147f3eed7a4863f3049ace40d79770d4ad990ac`

Material findings: `ActionStudioWorkspace.ts` remained an unlisted identity
fabricator and lacked bidirectional UI-selection/fixture closure; spell target
membership did not require exact equality when both application IDs were
nullable; the worker-summary component ID did not rotate with its V3 payload;
and the handwritten SDK REST decoders plus `gameRouting.test.ts` were absent
from the inventory and acceptance/rejection matrix.
