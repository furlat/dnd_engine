# Shared portal backend — September 21

This implements the portal slice of [the reviewed trap plan](TRAPS_AND_TRIGGERS_PLAN_2026-09-20.md).
The user explicitly prioritized game behavior and authorized the Godot task to
prepare bare-portal and opening-hatch compositions independently. It does not
complete the other planned trap mechanisms or pressure-plate sensors.

## Behavior and ownership

`dnd/spatial/portals.py` installs one `Portal` spatial condition. Bare portals and
hatches use that same owner, transfer processor and ground-entry handler.
Their content identity, initial state and concealment are authored values.
The owner uses FIELD/OVERLAPPING; it does not replace floor residue or spikes.
There is no additional portal registry, fabricated caster, spell cost or
renderer-driven activation flag.

- Ready entrances activate on ground contact. Active entrances transfer later
  entrants. Disabled entrances do nothing. The existing reversible trap lever
  can enable/disable either portal content, including opening under occupants.
- Jumping over the entrance does not trigger it; landing does. Walking and
  ground pushes trigger it. An exit is an authored same-map cell outside the
  entrance footprint. This slice targets one-way portals with inert exits;
  paired portals and chains are not implemented or tested.
- The destination must currently exist, be walkable for the traveler and be
  unoccupied. Visibility of the destination is not required. A blocked exit
  leaves the creature on the entrance; no additional movement is charged.
- Entry consumes the ordinary step/jump cost. Transfer itself is free.
  Destination ground hazards run through the ordinary spatial events. Dread
  blood can request its existing paid reverse step; insufficient movement
  retains its existing fear behavior.
- Opening reveals a concealed hatch. Once known it remains known when closed.
  Observations contain its disclosed cells, state and description, not its
  private exit configuration. Closing does not recall transported creatures.

The `materialize_portal` factory accepts `positions`, `exit_position`,
`trap_state`, `content_ref`, `stealth_dc`, and an optional real parent event.
`PORTAL_CONTENT_REF` and `PORTAL_HATCH_CONTENT_REF` select the two identities.
The legacy ContentRef schema still requires static contract metadata, as do
existing spatial records. This feature performs no hashing, asset audit or
source scan at startup or during play.

## Native movement and event fixes

`PortalTransferEvent` records the exact entrance and exit under its actual
trigger. LEFT/ENTERED and arrival consequences remain native children. Its
completion occurs after a paid arrival retreat has been parented, so complete
lineage capture includes that retreat. The transfer exit stays unchanged even
when the creature subsequently retreats from it.

Walking stops its obsolete planned route after an entry relocates the actor.
Jump completion reports the actual native endpoint, while retaining the paid
jump path. Shove, Thunderwave and Gust of Wind share the small straight-push
commit loop: every admitted cell publishes real contact, and a relocation or
paid entry response stops the old route. Their existing interruption policies
remain explicit: Shove stops on incapacitation; the two externally applied
spell pushes do not require the target's ability to act. The forced leg records
its own endpoint/distance, independently of a child portal crossing.

A reproduced carried-light bug had the same nested-completion cause: the
original entrance closed after the transfer and moved the light back. Light
settlement now ignores a spatial entry superseded by newer committed membership.

## Saved and public replay

The concrete native event is registered at the existing recording boundary.
`PortalTransferFact` carries the identified traveler, independently authorized
endpoints, whether transfer committed, and portal identity only when known.
No live entity/map lookup occurs during decoding or reduction.

Movement endpoint grants use the actual committed entry evidence. Jump's
public trajectory ends at its last committed step, rather than using the
action's final position after a portal or retreat. This also prevents a witnessed
jump from revealing a hidden portal destination.

The original entrance can complete after its child arrival. Player reduction
therefore retains a small per-actor spatial commit cursor, reconstructed from
existing VersionRows. A later nested commit cannot be overwritten by its older
enclosing entry when that entry closes. The cursor survives separately timed
groups. This is reduction bookkeeping, not backend state or another wire field.
The check is limited to nested completion intervals: deliberate presentation
retiming, including playing jump takeoff after preflight reactions, remains valid.

## Evidence and review

`tests/engine/test_portals.py` exercises real Move, Jump, Shove, Thunderwave,
Gust and lever-use commands. It covers both identities and all initial states,
ground versus airborne crossings, blocked/hidden/elevated exits, destination
spikes and dread retreat, complete child lineage, pushed distance, paralysis,
and carried light.

`tests/game/test_portal_replay.py` saves a concealed-hatch crossing with a wall
between entrance and exit. After resetting the native runtime, three players
replay it: traveler, entrance witness and exit witness. Both walk and jump are
covered, with independent endpoints and whole-lineage/incremental reduction.

Anti-slop and ECS reviewers examined implementation separately. Their concrete
findings caused corrections to retreat completion order, ordering across timed
groups and preservation of the spell push policy. Both approved those changes.
The existing multiple-OA jump regression also protects intentional launch timing.

Final focused validation: **131 passed, 2 preexisting expected terrain failures
in 40.53s**. An overlapping spell-family/coverage lane passed 63 tests. Selected
explicit typechecks are clean. The final ECS follow-up approved the interval-
limited ordering correction; details and commands' scope are in the trap plan.

## Remaining presentation work

The Godot task `01a0b6af-5fa9-7ec0-9915-0ecee0a6baec` received the art request
and acknowledged it is queued behind the user's Bane correction. The request
prioritizes recovering the removed DemonPunch portal and existing portal
libraries, and composing with the trap workshop v7 hatch while preserving its
pivots and camera registrations. Approved Chill Touch remains unchanged.

Portal media bindings and a timed portal presentation primitive are still
pending. There are no new portal videos or invented fallback VFX in this slice.
Saved public facts now provide the input for that integration; ordinary movement
and transfer must remain separate temporal legs when it is added.

## Broader audit results, separate from this feature

The additional `tests/architecture/test_dependency_boundaries.py` audit found
four failures in untouched older surfaces:

1. Importing `server.event_server` fails because `server/world_contracts.py`
   imports retired `dnd.core.senses`.
2. The canonical-symbol scan treats `game.condition_types.EquipmentSlot`
   (a presentation Literal) as a duplicate of the native enum.
3. The safe-leaf allowlist omits the existing neutral presentation geometry
   dependency of `dnd/types/senses.py`.
4. The world-contract leaf audit flags that same retired senses import.

The gameplay/replay tests in that run passed; these audit failures are not
portal regressions or permission to revive the retired server. They need a
bounded follow-up decision rather than being hidden in a green-test claim.

A broad explicit typecheck also reports four older errors: the decorated
world-transition validator call in `dnd/core/events.py`, two missing-default
`anchor_uuid` overrides in `dnd/spells/evocation.py`, and ContinualFlame's
`remove_from_register` call. The same statements exist in HEAD. The selected
portal/presentation/action/lever files pass their explicit typecheck.

## Accepted artwork intake after delivered-trap completion

The Godot task delivered user-accepted `contact-trigger-v5` after the native trap
batch completed. Source handoff is
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/portal-hatch-review/PRODUCTION-HANDOFF.md`.
It includes four hatch views but **only q0 entrance/exit portal captures**.
Requested the remaining three camera exports from the actual 3D source before
claiming four-camera production readiness. No screen-space rotation substitute
or new gameplay rule is authorized by the art preview.

Preserve: closed approach; opening on actual ground contact; horizontal portal
below the whole door sweep; visible short fall; fully-open destination before
arrival; finite exit accent. Hatch pivot `(128,208)` and portal pivot `(128,160)`
attach to the same ground origin. Opening frames `0..71`, held loop `72..359`,
closing `360..432` at 144 FPS are media sections, not backend delays. The preview's
wall-clock timestamps are illustrative. Failed transfer has no fabricated exit;
independently hidden endpoints stay hidden. Actor/rim occlusion and each camera's
front pass need validation during integration. The donor warnings and front-pass
limits remain recorded in the source handoff. Runtime bindings do not load or
validate its source hashes.

Portal media integration is still pending; the existing backend and completed
trap gallery are unaffected. The clean maintained gas-field request follows the
missing portal exports in the art task's queue.
