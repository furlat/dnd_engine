# Startup and the two remaining catalog/server failures

User-authorized unit, September 18. Branch: `codex/recovery-design`, starting at
`0b33c50`. Continue through implementation and validation without treating internal
checkpoints as requests for permission. Preserve the recovery architecture.

## Observable objectives

1. Reduce real game startup cost. Measure fresh-process native imports and the
   actual `python -m game --headless --frames 1` separately from gameplay. Fix
   unnecessary work at its owner, using the selected WSL uv environment. No
   runtime source/asset audits, hashes, lazy imports, schema caches or deferred
   validation obligations. Retain real content and event behavior.
2. Assemble the existing goblinoid-warband scenario using current direct character
   construction. The bounded non-damaging matchup must reach its 80-decision limit
   without inventing a replacement encounter or restoring retired player-class
   registry declarations. Preserve the same roster, ownership and complete birth.
3. Resolve the real-provider test's obsolete application boundary explicitly.
   Its tested AI feature includes actual HTTP decisions, per-character isolation,
   native/external and external/external progress, capacity and teardown. The old
   `event_server` also requires deleted application contracts. Following this
   branch's explicit recovery direction, keep that application retired and migrate
   its real-provider feature coverage to the current native boundary. This does
   not claim that the old game-hosting HTTP application has been restored.

## Findings and execution

- Fresh import samples on the current C: checkout are 3.247s, 2.942s and 2.836s;
  CPU spans are 1.857s, 1.706s and 1.610s. The diagnostic profile attributes material
  time to mounted-file access and to constructing 809 Pydantic model classes.
  Nested profiled costs are not interchangeable with ordinary elapsed samples.
- The Linux environment is already `/home/tommaso/.cache/dnd-engine/venv` with uv
  Python 3.13.12. The user narrowed startup work to a diagnostic Linux source copy:
  compare the same imports and actual game launch, then stop startup changes if
  this is adequately faster. Keep the active C: checkout in place; an eventual
  source-folder migration is separate. Current working files and tracked assets
  were copied to `/home/tommaso/Dev/dnd_engine-startup-check-20260918` without Git
  history, environments, generated captures or bytecode caches. This directory is
  a disposable diagnostic snapshot, not an automatically synchronized checkout.
- The old Barbarian recipe has a matching current direct premade. Integrate that
  source into the existing roster source union and reuse character preparation;
  assembly still applies setup and validates before committing exactly one birth.
- The server matrix's missing `dnd.core.senses` import is followed by dependencies
  on deleted character, item-binding and replication modules. A one-line shim
  would misrepresent the problem. The existing RegisteredAIController already
  supports asynchronous HTTP decisions followed by synchronous native execution.

## Review and validation

Anti-slop reviewers: `startup_design_review` for startup, `server_repair` for
catalog/startup. Anti-OOP reviewer: `catalog_repair` for startup/server; root
reviews catalog ownership independently. Review the concrete diff and behavior,
not just compliance with this plan.

Run native timings serially with source/interpreter locations recorded. Execute
focused catalog, construction and AI tests, then the repaired provider boundary
and the relevant existing gameplay/replay checks. Preserve the previous event-fed
AI and subjective-lineage contracts. Do not hide a failure by excluding its test.
Record actual improvements, remaining costs and exactly which server behavior is
supported. Raw local diagnostics are under
`.runtime/performance-recovery/startup-server-20260918/`.

## Startup result: stop this track; migrate the source folder later

The diagnostic copy is 2,722 working files (about 90 MB), including tracked game
assets. The active checkout and its Git history remain on C:. Both paths use
`/home/tommaso/.cache/dnd-engine/venv`, Python 3.13.12 and the same installed
dependencies. No extra bytecode-prefix setting was used for this comparison.

Three fresh processes per location/stage, alternating locations, after separately
recording first use:

| Measured stage | C: source through WSL | Linux source copy |
|---|---:|---:|
| Native imports, median | 2.898s | 1.595s |
| Native imports, range | 2.826–3.068s | 1.548–1.691s |
| Whole one-frame game process, median | 5.032s | 3.050s |
| Whole one-frame game process, range | 4.846–5.144s | 3.028–3.057s |

Native import timers begin inside Python, immediately before the existing engine
imports; full-game wall timers include uv, interpreter startup, imports, actual
scene/media setup, one frame and shutdown. Do not add these rows. All launches
exited successfully. Random initiative can leave the first historical animation
in progress after one frame; both locations produced the same mix of one/two
retained lineages. This is a startup measurement, not a replay-completion test.
First-use Linux imports were 1.975s and its first game process 2.98s, separately
from these repeated medians. The earlier isolated 6.24s C: launch was not reused
as the comparison baseline.

Moving the source alone cuts these import spans by about 45% and actual launch
by about 39%. Per the user's instruction, this ends startup optimization for now.
No schema redesign, late imports, content pruning or runtime validation system
was added. GC and rendering work remain outside this unit.

Reproduce an actual launch from the diagnostic snapshot:

```bash
cd /home/tommaso/Dev/dnd_engine-startup-check-20260918
export UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
/usr/bin/time -p /home/tommaso/.local/bin/uv run --no-sync python -m game --headless --frames 1
```

Raw samples, subprocess output and the temporary comparison runner are in the
original checkout's `.runtime/performance-recovery/startup-server-20260918/`:
`source-comparison.json`, `compare_source_locations.py`,
`linux-import-first.json` and `linux-game-first-*`. The runner records the imported
`dnd` source location. It performs timing only; no fingerprints or asset audits.

An earlier diagnostic placed only Python's ordinary bytecode cache on Linux:
imports improved from 2.920s to 2.379s while source stayed on C:. The subsequent
source-copy result supersedes that avenue; no cache configuration was installed
in the project's normal launch path.

## Catalog and provider results

The two previously excluded tests now pass through supported current boundaries:

- The unchanged finite-horizon test builds its original goblinoid warband and
  reaches 80 non-damaging decisions. A passive `premade_character` roster source
  selects the existing matching level-5 Barbarian build. Character preparation
  is shared with ordinary direct construction; encounter assembly still applies
  setup and validates before publishing one complete birth per actor. Failed
  preparation disposes provisional entities. The matching canonical roster and
  its 11 embedded copies use this source; the premade owns its single lit torch.
  Unmatched retired character variants were not substituted with different builds.
- The live provider matrix retains its independent HTTP policy process but now
  drives the existing native Encounter and RegisteredAIController directly.
  Native/external and external/external policies execute actual turns; the
  end-turn mode exercises all four independent assignments over two rounds.
  Assertions cover per-character policy/memory ownership, decision order and
  epochs, native authority across the await, capacity rejection, authenticated
  close/reopen, and both sides' saved complete subjective action lineages after
  native state is cleared. No production provider adapter changes were needed.
  Retired hosted-game creation/session/replacement HTTP routes remain retired.

Catalog checks: **23 passed in 8.70s**, comprising the two new direct-premade
encounter cases, original finite-horizon regression, 18 direct-character cases,
roster source contract and warband lifecycle case. Existing pure/rejected build
checks now compare the event cursor before and after the operation, preserving
the world Tile events intentionally emitted during fixture setup.

```bash
export UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
/home/tommaso/.local/bin/uv run --no-sync python -m pytest -q \
  tests/engine/test_encounter_direct_premade.py \
  tests/ai/test_finite_horizon_gameplay.py \
  tests/progression/test_direct_character_builds.py \
  tests/manual/test_71_authored_roster_catalog.py::test_every_authored_member_has_a_creature_recipe_or_direct_build \
  'tests/manual/test_73_authored_encounter_lifecycle.py::test_every_active_recipe_constructs_one_complete_encounter[encounter.srd_goblinoid_warband]'

/home/tommaso/.local/bin/uv run --no-sync python -m pytest -q \
  tests/ai/test_live_ai_matchups.py \
  tests/ai/test_registered_ai_controller.py \
  tests/ai/test_registered_ai_provider.py
```

The second command passes **16 checks in 6.53s**. Pyright reports zero errors or
warnings for the changed provider test and the three changed production Python
files. Anti-slop and anti-OOP reviewers approved the final existing-owner design;
the review preserved optional participation when a combatant dies before acting,
while the end-turn fixture still requires every assignment to participate.

Root additionally ran both `tests/game/test_session.py` cases and the warband
lifecycle parameter: all three passed. That run also deliberately tried the
older `test_typed_post_grant_behavior_ignites_the_authored_portable_torch`, which
failed on its `creature.player.sorcerer` reference. Its entire
`encounter.standard_skeleton_doors` recipe is unchanged from the starting commit;
the scenario has a different retired Sorcerer build, not the migrated Barbarian.
The new warband birth check directly verifies one lit torch with no duplicate
grant. This unit does not claim the whole historical encounter catalog passes.
Two exploratory historical census assertions also remain stale (battlefield
count 9 versus current 14, and an old SRD roster inventory excluding Dretch).
They were not changed to manufacture a clean full-suite result.

Across the completed focused selections, **41 distinct checks pass** (23 catalog,
16 provider and two session cases). The extra legacy torch scenario remains the
explicit failed exploratory check; full retired-server/SDK and catalog restoration
are outside this bounded repair. No rendering or VFX work was resumed.
