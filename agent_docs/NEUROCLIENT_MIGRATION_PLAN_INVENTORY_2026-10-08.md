# New NeuroClient / NDClient migration — plan inventory

8 October 2026. Corrected scope after the user rejected an earlier inventory that mixed this migration with prior Pygame development.

**Implementation is stopped. The user reported deleting NDClient.** Historical “resumed work” banners predate that final stop and are not current authorization.

## Scope

This inventory starts at the user’s request to recover the NeuroClient restoration plan **after the API and new SDK had been integrated**, followed by the decision to create a fresh NDClient. It covers planning, the explicitly bounded Pixi proof, full-client implementation and foundation repair through deletion.

Earlier Pygame spell/UI/playtest/performance plans, narrative-renderer work, and server implementation plans are excluded. Existing Pygame, NeuroClient, Neuro Studio and NeuroMapEditor work matters here only as the source of capabilities and authored data the new client was supposed to recover.

The files below survive in the engine repository. No deleted NDClient path was searched. Deleted client-local documents cannot be enumerated from this inventory. This is an index, not a new implementation plan.

## Main plans

| Document | Role |
|---|---|
| [NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md>) | Earlier combined document whose client-restoration/Studio portions were the starting reference. Its server implementation is outside this retrospective; its client destination was superseded by the NDClient master. |
| [NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md>) | Full NDClient delivery plan: new repository, source recovery, complete assets, rendering, playback, Studio and playable client. |
| [NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_FOUNDATION_REPAIR_PLAN_2026-10-08.md>) | Foundation repair plan after the user rejected the migrated world/door/layer setup. Readiness was withdrawn; final work is stopped. |

## Required technical chapters and migration handoffs

These are parts of the master plan or its repair phase. They are not separate optional projects.

| Document | Role |
|---|---|
| [NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md>) | Existing authoring fields, types and owners the client must consume. |
| [NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_PIXI_NEUROCLIENT_COMPONENT_REVIEW_2026-10-08.md>) | Existing NeuroClient/Studio components and current Pixi APIs: retain, adapt or replace deliberately. |
| [NDCLIENT_INTERACTION_PARITY_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_INTERACTION_PARITY_2026-10-08.md>) | Required client interaction parity. Older implementation is a reference, not a subject of this post-mortem. |
| [NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md>) | Complete selected assets, untracked copying, modular/fixed rigs and authoring. |
| [NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_DEPTH_MATERIAL_LIGHTING_2026-10-08.md>) | Coordinates, elevation, composition, materials, lighting, picking and cutaway. |
| [NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md>) | Compact effect representations, blood/deposits and family-wide coverage. |
| [NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_OCCLUSION_MATH_AND_PIXI_2026-10-08.md>) | Occlusion versus reach, transparent composition, wall/light geometry and protection fields. |
| [FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md>) | User-authorized isolated Pixi proof, separately scoped from full NDClient production. |
| [NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md>) | Source-compatible assemblies, adjacency and authored fields missing from client consumers. |
| [PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md>) | Animated-wall author’s source instructions: owner/edge, frame/pose, committed height, contacts and source units. |

## Review and implementation receipts

These are evidence records, not additional implementation plans or certificates of complete delivery.

| Document | Role |
|---|---|
| [PLAN_REVIEWS.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-plan-20261008/PLAN_REVIEWS.md>) | Plan reviews, reduced-scaffold findings, timeline clarification and limitations of approval. |
| [FIREBALL_HANDOFF_REVIEWS.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-plan-20261008/FIREBALL_HANDOFF_REVIEWS.md>) | Reviews of the bounded prototype/export handoff. |
| [FIREBALL_PROOF.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-plan-20261008/FIREBALL_PROOF.md>) | Actual standalone proof and its limits; not complete-client acceptance. |
| [FOUNDATION_PLAN_REVIEWS.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-implementation-20261008/FOUNDATION_PLAN_REVIEWS.md>) | Foundation readiness review and withdrawal. |
| [REVIEW_AFTER_USER_STOP.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-implementation-20261008/REVIEW_AFTER_USER_STOP.md>) | Documented implementation defects after rejection. |
| [FOUNDATION_REPAIR_IMPLEMENTATION.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-implementation-20261008/FOUNDATION_REPAIR_IMPLEMENTATION.md>) | Bounded claimed repairs, unfinished work and evidence limitations. |
| [RENDER_ORDERING.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/ndclient-implementation-20261008/RENDER_ORDERING.md>) | Ordering work record. |
| [module-port-ledger.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/neuroclient-server-20261007/module-port-ledger.md>) | Earlier source/function inventory consulted for client recovery; not an instruction to port Python algorithms. |
| [PLAN_REVIEWS.md](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/audits/neuroclient-server-20261007/PLAN_REVIEWS.md>) | Review of earlier combined plan; only its client-restoration relevance is included here. |

## Relationship and status

1. The earlier combined plan supplied the client-restoration starting point.
2. The NDClient master replaced the client destination and assembled the technical chapters into one full-delivery scope.
3. The Fireball handoff/proof addressed an explicitly requested isolated experiment. It did not shrink the later client scope.
4. The foundation repair plan took precedence after the user rejected the initial source registration, assembly and rendering behavior.
5. Final stop/deletion supersedes all earlier resumption language. No source plan is authority to restart now.

**Inventory total: 3 main plan documents, 10 technical chapters/handoffs, and 9 relevant review/source-ledger receipts.** These categories are deliberately separate. The main/technical package contains 13 files; the receipts are not 9 more delivery plans.

`RECOVERY_PLAN.md` is the repository-level entry point and `ASSETS.md` the asset runbook; they govern source work but are not new client migration plans. The repository’s `USER_COMPLAINTS.md` spans earlier projects as well, so it must not be read wholesale as an NDClient failure list.

Companion: [migration-only post-mortem](</mnt/c/users/tommaso/documents/dev/dnd_engine/agent_docs/NEUROCLIENT_MIGRATION_POSTMORTEM_2026-10-08.md>).
