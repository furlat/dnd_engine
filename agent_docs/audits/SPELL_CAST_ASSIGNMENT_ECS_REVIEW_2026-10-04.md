# Spell cast assignment ECS review — 2026-10-04

**Outcome: approved for the bounded implementation in the implementation plan.**
This is an independent assignment/data-boundary review, not final approval of
runtime behavior, rendered timing, or the persistent gallery.

Reviewed `agent_docs/art/SPELL_CASTING_IMPLEMENTATION_PLAN_2026-10-04.md` and
`agent_docs/art/SPELL_CAST_ASSIGNMENTS_2026-10-04.{md,json}` against the production
animation loader, typed layer/socket consumers, current resource metadata, and
original modular sheets. No production files were edited for this review.

## Coverage and data boundaries

- The 126 canonical assignments plus 24 derived rows account for all 150 loaded
  identities without duplicate, missing, or extra identities. Derived rows
  distinguish 18 effect variants from six action/reaction aliases.
- Canonical source owners resolve to the stated recipe rows. Selected original
  category/clip sheets exist, and proposed combinations fit existing typed slots.
- Variants explicitly inherit pose, layers, noise, and gamma while retaining
  their own `elementColors` and effect delivery. Disabled derived casts remain
  disabled and are represented through their owner sequence.
- True Strike remains an actual child weapon attack with its existing pose,
  clock, and release. Its assignment now explicitly records gamma `0.65` and
  `/spell-palettes/source-hand-noise.png`; it does not introduce a parent cast.
- The Sunbeam action alias belongs to its canonical owner through existing
  `action_deliveries`. Distinct loaded Python objects are not evidence of an
  authored divergence; current values agree. Synchronization belongs in the
  existing owner/alias path.
- The list remains passive authoring data for a generic offline transformation.
  It requires no runtime assignment registry, per-spell behavior, gameplay
  coupling, or new presentation subsystem. Fixed rigs retain their own gestures.

## Closed release-socket finding

The initial Attack1 frame 7 selection for Shocking Grasp and Inflict Wounds had
no measured south-facing hand socket. Both assignments now select Attack1
frame 6, which has measured hand sockets in all eight directions. A repeated
check across every ordinary assignment found no unmeasured selected release
socket. This closes the assignment blocker. Preparation tracks may contain
existing gaps and must continue to use the established fallback behavior.

## Implementation checks to retain

- Preserve authored gamma/noise when the shared palette resolver replaces only
  colors with the spell palette; pass the existing decoded noise resource into
  `recolor_palette` in the shared cast-row loader. The existing full-treatment
  cache key already distinguishes these treatments.
- Register selected originals at the standard `/spritesheets/<category>/<clip>.png`
  addresses so rig clip metadata and cast-layer capability checks agree.
- Re-anchor both cast and projectile source sockets from the selected clip's
  existing hand track, with explicit release/preparation frames. Updating only
  cast sockets would leave a separate projectile consumer stale.
- Verify the resulting typed data, exact palette/alpha behavior, child-attack
  presentation, alias/variant synchronization, and retained/native gallery in
  the subsequent implementation review.

No new gameplay tests or renders were run by this reviewer for assignment
approval. The bounded correction was checked directly against the authored
JSON and existing measured socket data.
