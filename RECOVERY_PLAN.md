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

For the human-requested multiple-floor engine addition, follow the
[complete implementation plan](agent_docs/MULTI_FLOOR_IMPLEMENTATION_PLAN_2026-10-13.md).
It covers actual-height XYZ addressing, directional physical support,
navigation, perception/light, targeting/effects, lifecycle/history, server/SDKs,
AI and the client handoff. Implementation starts with one playable building
through the real server/SDK, then completes its mechanics and production checks;
the detailed owner inventory and acceptance cases track coverage.
Section 19 also audits existing test/fixture migration and separate SDK/sandbox
checks; source counts are recorded, but an execution baseline is still needed.
The [initial study](agent_docs/MULTI_FLOOR_ENGINE_STUDY_AND_PLAN_2026-10-13.md)
retains historical source evidence; its implementation recommendations are
superseded. The human excluded flight work. Production implementation has not
started; explicit remaining rule decisions and independent review results
belong to the complete plan.
