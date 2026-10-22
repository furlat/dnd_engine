We are working on NDClient.

The death/invisibility repairs are implemented in the current checkout:
per-creature zero-HP policy, terminal defeat publication, and caster reveal before
area damage. See the [repair plan](agent_docs/plans/DEATH_INVISIBILITY_INVESTIGATION_2026-10-22.md)
and [client handoff](agent_docs/DEATH_INVISIBILITY_CLIENT_HANDOFF_2026-10-22.md).
The combined selected suite passed 102 tests; separate reveal checks passed 86.
The handoff records timing limits and adoption requirements. No client files
were changed, and the separate selected-AoE implementation remains unstarted.

For the selected AoE request and agent-local stamping computation, see the
[selected AoE plan](agent_docs/plans/SELECTED_AOE_AIMS_PLAN_2026-10-22.md).
The human clarified that the stamp is filtered by existing open-space
connectivity: sealed barriers block disconnected portions; gaps let it spread.
The plan retains inverse stamping and adds a batched reachability mask whose
parity and cost still need qualification. Implementation has not started.
The earlier free-ground-aim Preview cache repair is committed as
`bedc3d92dc`; its focused tests passed. The selected plan retains actual stamping
measurements and separates them from the untimed exhaustive correctness oracle.

For the three newly authorized production publication repairs (Ice destruction,
Myrmidon Landing identity and Arcane Sword anchor), follow the
[production fact repair plan](agent_docs/plans/PRODUCTION_FACT_REPAIRS_2026-10-22.md).
All three are implemented and independently reviewed; 219 selected tests passed
with one expected failure. The plan records timings, the client handoff and a
separate pre-existing summon content-declaration failure found by a broader check.

For the human-requested change making summons follow their caster's control,
see the [summon controller ownership plan](agent_docs/plans/SUMMON_CONTROLLER_OWNERSHIP_PLAN_2026-10-22.md).
Implementation and the requested fair Monty summoner match are complete. The plan
records the pre-change summon/sensory timings, independent reviews, validation
limits and the human-requested single dragon color choice. The
[client handoff](agent_docs/SUMMON_CONTROL_CLIENT_HANDOFF_2026-10-22.md) describes
schema 18 and links the match evidence. The human then identified
missing caster-zero-HP dismissal independent of concentration. The
[caster defeat cleanup plan](agent_docs/plans/SUMMON_CASTER_DEFEAT_CLEANUP_PLAN_2026-10-22.md)
is implemented; regressions and source review passed. The fresh independent
match ended naturally and both SDKs/replay passed. Its summons had already
departed before caster defeat, so direct live dismissal is explicitly not
exercised; native and real-worker cases prove that boundary with living summons.
The earlier duel's weapon-survival
behavior is defect evidence, not acceptance of the corrected lifetime rule.

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
