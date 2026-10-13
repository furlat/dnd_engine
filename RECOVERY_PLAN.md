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
