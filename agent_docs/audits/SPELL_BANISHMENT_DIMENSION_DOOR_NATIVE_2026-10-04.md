# Banishment and Dimension Door native checkpoint — 4 October 2026

Implementation receipt, awaiting independent root review. This implements the
approved packet6 rules and native selection/replay boundary. It does not claim
the available Banishment or Dimension Door artwork is installed or visually accepted.

## Implemented behavior

- Banishment uses native multi-entity allocation, one target at level4 and one
  additional target per higher slot. Selection admits visible creatures,
  including allies/self, within the existing support-height distance of60 feet.
  CHA resistance still spends the cast. Each failed target has its own condition
  linked to the cast's exact concentration owner before membership publication.
- Authored native/current plane IDs and a committed spatial disposition are
  passive entity data. A creature native to the current plane enters the temporary
  demiplane and becomes Incapacitated; this ends its concentration. A foreign
  creature returns to its home plane without that extra condition. Early release
  returns either branch; the foreign branch remains absent after ten native ticks.
  Items, identity, initiative membership and other condition clocks remain retained.
- Prepared returns choose the original or nearest valid unoccupied support,
  reserve destinations across the existing concentration-removal transaction and
  never move the current occupant. With no legal support, the removed spell leaves
  a passive pending return obligation and one owned spatial-event handler. A later
  occupancy/support change retries it; successful return removes that handler.
  Antimagic's separately implemented exact-anchor restoration is unchanged.
- Dimension Door uses the existing typed creature-plus-destination route. Selecting
  the caster means travelling alone; an optional ally must be present, perceived,
  within5 feet and no larger than the caster. Destinations within500 feet need not
  be seen. Discovery exposes map coordinates without filtering hidden occupancy.
  Invalid companion/input rejects before cost; an admitted blocked, occupied or
  unsupported destination spends action/slot and deals the shared4d6 force mishap
  to both participants without moving either. Caster death does not cancel the
  companion's already admitted damage.
- Successful travelers commit together before arrival reactions. Existing
  PortalTransferEvents carry each real actor, the common spell parent and original
  effect attribution, with no fake portal object. Existing subjective projection
  discloses departure/arrival independently to observers. Carried items remain on
  the same owner; no inventory copy is made.

## Shared boundaries

`dnd/types/actor.py` owns the plane/disposition snapshot values and pending-return
record. `dnd/entity.py` owns physical suspension/restoration, prepared return and
atomic position commit. `dnd/core/base_block.py` exposes reservations from the
existing accepted-removal context. `dnd/core/events.py` permits the existing transfer
fact to have no persistent portal and carry its spell origin. Spell rules remain
in the Banishment/DimensionDoor sections of `abjuration.py`/`conjuration.py`; catalog
metadata declares their real selection types. No planar simulator, global pending
queue, alternate action manager or spell-specific client selection was added.

## Validation

- `/tmp/packet6-native-final-stable.log`:94 passed in49.06s. Includes all24 focused
  native cases, native transform/prepared-removal/return lifecycle regressions,
  two actual selection/encoded-replay cases and dependency-DAG checks.
- `/tmp/packet6-native-final-portal.log`:46 passed,11 deselected in7.30s. Existing
  native portals, saved portal replay and the selected legacy Banishment cases.
- `/tmp/packet6-native-final-pyright3.log`:0 errors/warnings for all seven changed
  production modules and the two new test files.
- Scoped `git diff --check` passes. Old tests that expected Banishment to displace
  occupants now assert the approved nearest-free behavior; stale-reservation cases
  invalidate the actual reserved destination instead of merely moving the old
  occupant away.

The initial combined final run included an Antimagic test file under concurrent
development and was terminated; `/tmp/packet6-native-final-regression.log` is not a
passing receipt. The stable run above deliberately excludes that changing suite.
An earlier typing command including the old prepared-lifecycle test found its
existing un-narrowed `Event.condition` access; that test file is not included in
the clean production/new-tests typing claim. No whole-suite acceptance is claimed.

New regression files: `tests/engine/test_banishment_dimension_door.py` and
`tests/game/test_dimension_door_selection_replay.py`. They cover genuine multi-target
absence, both self-target allocation orders, the tenth tick/early return, no-space
retry, atomic arrival observations, privacy, hidden mishaps and the existing UI route.

No artwork, import, native holy rule or external chat change belongs to this checkpoint.
