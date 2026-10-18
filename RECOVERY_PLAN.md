We are working on NDClient.

Follow the [NDClient implementation plan](/home/tommaso/Dev/NDClient/agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-11_v3.md).

For the human-requested server movement optimization, follow the
[server movement rework plan](agent_docs/SERVER_LOCAL_MOVEMENT_REWORK_PLAN_2026-10-12.md).
Its scope, implementation status and independent validation are recorded there.

For the human-requested available-actions computation and server/SDK redesign,
follow the [player action discovery rework plan](agent_docs/PLAYER_ACTION_DISCOVERY_REWORK_PLAN_2026-10-13.md).
It specifies shared subject/position tables, exact eligibility and on-demand
subjective AoE previews. The server and both SDKs implement schema 8; completed
qualification, remaining native costs and the client handoff are recorded in
that plan. The separate 9.5 ms movement target remains unmet.

For the human-requested XYZ addition, the current proposal is the
[minimal XYZ plan](agent_docs/XYZ_ADDITION_PLAN_2026-10-15.md), based on committed
production `229ce025f3ffbf876cbb34f63d0de26a9051d088`. It preserves existing
systems and fast paths, requires a bounded height/address proof and actual
command timing before bulk migration, and excludes the failed material/world
redesign. Antislop, antiOOP and contract review qualify the first proof only;
the algorithm and named vertical-area decisions remain unqualified.
Implementation has not started. Flight remains excluded. The older
[multifloor plan](agent_docs/MULTI_FLOOR_IMPLEMENTATION_PLAN_2026-10-13.md),
especially its section 19 fixture inventory, and the
[initial study](agent_docs/MULTI_FLOOR_ENGINE_STUDY_AND_PLAN_2026-10-13.md)
retain historical evidence; their implementation strategy is superseded.
