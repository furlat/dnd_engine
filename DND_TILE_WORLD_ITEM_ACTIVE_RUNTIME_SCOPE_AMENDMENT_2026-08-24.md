# Active-runtime scope amendment for the Tile / World-Item migration

Status: APPROVED

Substantive reviewed revision:
`95c8f32f81abf65da3d44ec6967799c41bbafcfcd60f7a181a2c5162c4459b41`

Date: 2026-08-24

## 1. Why this amendment exists

The ordered Tile-side geometry, placement ownership, movement, optical,
illumination, propagation, condition, event, and subjective-reduction design
remain unchanged. A later Phase 3 caller audit incorrectly expanded the hard
cut from active mechanics into deprecated server/editor modules, an obsolete
TypeScript SDK, generated cross-language contracts, source maps, and
transport-only tests.

That expansion is revoked. It was a scope error, not a mechanics requirement.

## 2. Current product target

The target is a flawless single-process Python engine exercised directly by a
pygame presentation. The current migration proves mechanics from first
principles inside that process:

- GridMap, Tile, placement, ordered side layers, and world-edge derivation;
- movement, pathfinding, FOV, physical optics, light, and propagation;
- entities, items, actions, conditions, concentration, anchors, and events;
- objective state followed by reducer-owned subjective perception; and
- authored Python maps/content required to exercise those capabilities.

Renderer-neutral semantic facts remain desirable, but no network or
cross-language consumer constrains this cut.

## 3. Exact included scope

An implementation member is in scope only when it is one of:

1. active Python production code under `dnd/` needed by the mechanics above;
2. active authored Python content under `dnd/` needed to construct those
   mechanics in process;
3. collecting engine/mechanics tests whose maintained subject and imports are
   active in-process Python behavior; or
4. Markdown governance and exact Python/JSON implementation manifests for
   this migration.

Core Pydantic events and replay-sufficient after-values remain in scope because
the in-process EventQueue, light settlement, spatial lifecycles, and
`SpatialSensesSystem` consume them directly.

## 4. Exact excluded scope

The following are deferred until a separately planned post-mechanics transport
refactor:

- all `deprecated/**` files;
- removed or deprecated `server/**` code and tests that import it;
- HTTP/API endpoint and MapEditor transport behavior;
- SDKs and all TypeScript/JavaScript source, output, declaration, fixture, map,
  and package artifacts;
- generated cross-language event/replay/projection contracts;
- deprecated content/icon/presentation ledgers and their generators; and
- tests whose maintained subject is server, replication, transport, SDK, or
  cross-language wire compatibility.

Excluded files may remain stale, fail collection, or retain obsolete textual
field names. They are not caller-completeness, compile, schema, deletion,
manifest, collection, or zero-reference gates. Do not restore dependencies or
invent a compatibility layer to keep them synchronized.

`dnd/core/content/icon_bindings_generated.py` is presentation packaging for
this cut. Existing unused bindings for a retired identity do not construct a
mechanic and do not block the hard cut. Do not invoke its deprecated generator
or broaden Phase 3 to clean presentation assets.

A file under `dnd/` is not automatically active merely because of its path.
`dnd/items/environment_content.py` and tests importing its legacy materializer
depend on the deleted `dnd.content_system`; they are inactive packaging for
this cut. Phase 3 uses the collecting direct builders under
`dnd/content/items/` and must not restore a content-system facade. When a
mixed blocked test contains a valuable in-process mechanic, transplant that
public behavior into a collecting active test and leave its transport or
content-system cases deferred.

## 5. Effect on approved work

- Phase 0–2 and the corrected independent-side geometry remain accepted.
- Slice 3.1 center-occupant work remains accepted.
- The core ordered-side sections of the Phase 3 guidance remain valid.
- The old Phase 3 implementation ledger is revoked as implementation
  authority because its caller and generated-artifact envelope crossed the
  boundary above.
- Luna's stopped Slice 3.3 tree is an untrusted intermediate candidate. It may
  be continued only after every changed active file is checked against the new
  active-only ledger and every newly changed excluded file is removed from the
  candidate.

Previously accepted edits already present under `deprecated/**` are frozen and
ignored. This migration neither relies on them nor spends mechanics work
rewriting them. Any new Slice 3.3 excluded-file edit must be removed before
implementation resumes.

## 6. Validation boundary

The corrected Slice 3.2 ledger freezes exact active production and test paths.
Validation consists of:

- compile/diff checks for active changed Python;
- public movement, placement, ordered-edge, FOV, light, propagation, sensory,
  condition, event, replay, and locality behavior;
- active dependency and deletion gates; and
- a final manifest containing only governed active Python/JSON files.

Repository-wide collection may still be recorded diagnostically, but
deprecated/server/SDK failures and selectors are not acceptance gates. No test
is ported merely to keep a deferred transport surface compiling.

## 7. Stop rule

If completing an active mechanic appears to require changing or generating an
excluded artifact, stop and re-check the caller classification. The default
answer is to defer that artifact, not to restore its toolchain.

## 8. Review record

| Review | Revision | Verdict | Notes |
|---|---|---|---|
| Correctness and scope | `95c8f32f81abf65da3d44ec6967799c41bbafcfcd60f7a181a2c5162c4459b41` | APPROVED | active mechanics completeness, mixed-test capability replacements, exclusion safety |
| Anti-slop and dependency | `95c8f32f81abf65da3d44ec6967799c41bbafcfcd60f7a181a2c5162c4459b41` | APPROVED + ANTI-SLOP APPROVED | no transport/content-system compatibility layer or hidden active dependency |
