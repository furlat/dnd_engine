> **Superseded verdict — 8 October, later user correction.** The earlier
> implementation-ready approval is withdrawn. The geometry reviewer withdrew its
> readiness claim; the human rejected arbitrary environment asset pairing and
> halted all implementation. A later narrow review of terraced-keep topology did
> not review or certify artwork compatibility. See the
> [asset recovery handoff](../../NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md).
> Historical review text below must not be used to resume production.

**Later October 8 amendment:** the human-supplied
[animated-wall positioning notes](../../PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md)
are now incorporated into foundation A0–A4, comparison coverage and work order,
and asset recovery §3.5. The historical verdicts below predate those changes.
The amendment has not received a new independent review or runtime validation.
The required implementation reviews must examine the compatible source assembly,
owner/pose/height/contacts, shared geometry and actual matched reference output;
no additional review ceremony or approval can lift the user's halt.

# Foundation repair plan — independent reviews

8 October 2026. Reviewed document:
[NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md](../../NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md).

**Historical verdict, now withdrawn: both reviewers considered the then-scoped repair plan implementation-ready.**
This is design/source review, not approval of the existing client, runtime correctness,
visual quality or performance. Implementation remains stopped until the human resumes it.
No production edits or tests were performed in these reviews.

## Anti-slop review

Independent reviewer: `/root/antislop_full_review`.

The first pass found two concrete gaps: an unspecified partial-stair fallback and
an actor-sizing promise that omitted the existing condition-scale consumer.

The amended plan closes them with the explicit stair-run observation, native
cold-fact/projection ownership and disclosure limits; and the existing
`CharacterAppearance.config()` / `AppearanceConfig` plus `persistent.bodyScale`
paths, including application/removal/suppression and seeking. No automatic
halfling multiplier is invented. The narrow condition-scale repair does not pull
in the whole condition renderer.

Final verdict: **“Scoped verdict: ready. Both findings are closed in the amended plan.”**
The reviewer reported no remaining anti-slop blocker, and specifically retained
the distinction between design readiness and implementation acceptance.

## Anti-OOP/ECS and geometry review

Independent reviewer: `/root/geometry_ecs_review`.

The first pass found four concrete gaps:

1. Atlas rectangle coordinates needed an explicit distinction from source-local trim offsets.
2. Collinear stair contacts could not independently define receiving faces; partial disclosure needed an exact decision.
3. Retaining an old frame required pinned leases and an atomic camera/picking/light replacement, not readiness checks alone.
4. Live idle required retained absolute presentation time and operation-start metadata for reload/seek.

The final plan specifies those distinctions in A2/A3 and C1–C3. Geometry remains
passive source/derived data in existing owners; the coordinate/geometry path is
shared by rendering, picking, cutaway and visual light. Native stair observations
do not introduce entities, artwork imports into the engine, a second world or
new gameplay traversal. Existing SDK types are extended at their native owner,
not copied into another protocol.

Final verdict: **“Scoped verdict: implementation-ready as a repair plan. No remaining blocker from my four findings.”**
The reviewer confirmed the existing ECS/data ownership and import DAG boundaries.

## Human decision incorporated

The human explicitly accepted seeing a stair member revealing the staircase's
direction and length for rendering (“yeah fine”). The question expressly excluded
neighboring tiles, creatures, lighting and movement permissions. A3 records that
shape disclosure and the exact minimal observation. This approval resolves that
design choice; it does not lift the implementation stop.

## Review scope and next evidence

The reviews checked the first draft, then the concrete amended findings; no
whole-plan regeneration loop or new benchmark budget was requested. The parent
also corrected the master/RECOVERY current status and withdrew earlier geometric
validation claims from the implementation documentation.

The detached door's precise runtime cause remains a diagnosis task with an explicit
source-frame/depth procedure in A1. The new plan does not claim that cause was
already proven. Independently calibrated faces, focused native/browser checks,
visual inspection and final code reviews remain implementation obligations.
