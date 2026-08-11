# How to Test This Project

## Purpose

Tests should give us confidence that a player-visible or client-visible feature
works while leaving the implementation free to change.

The main question is not “which function did we execute?” It is:

> Given this input and starting state, what observable result must the system
> produce?

A useful test suite makes refactoring cheaper. A harmful test suite freezes
private function signatures, mock call sequences, DOM structure, or incidental
serialization details that are not part of a real contract.

This guide distills the main ideas from the supplied *How to Test* essay and
applies them to the Python/FastAPI backend and TypeScript/Playwright frontend.

## Scope Comes Before Tests

Before changing code, write down four things:

1. **Requested behavior** — the one feature or regression being changed.
2. **Boundary** — where a real caller can observe that behavior.
3. **Input** — command, request, event stream, saved state, or user action.
4. **Expected output** — response, projected state, emitted event, or visible UI.

The implementation and tests must stay inside that boundary.

- Do not redesign neighboring systems because a test exposed unrelated debt.
- Do not rewrite unrelated tests “for consistency.”
- Do not add speculative cases for features not requested.
- Do not change expected output merely to make a failure green. Understand the
  difference first.
- If the requested behavior requires a new product decision, public contract,
  or architecture change, stop and ask for guidance.

For a bug, first add the smallest case that reproduces the externally visible
failure. For a feature, define its observable acceptance cases before choosing
which internal code to edit.

## Core Principles

### 1. Test features, not implementation

Prefer public or stable boundaries:

- Backend domain command in, authoritative state and events out.
- HTTP request in, typed status and response body out.
- Replication data in, player-visible projection out.
- Browser action in, visible UI state out.

Avoid making private helpers, class layout, call order, or module topology part
of a feature test.

Use the **replacement test**:

> Would this test still describe the same requirement if the implementation
> were completely replaced but produced the same observable result?

If yes, it probably tests a feature. If no, it probably tests code structure.

Architecture tests are a deliberate exception. A test such as “the domain
layer must not import the server layer” protects an explicit repository policy.
It should be named and located as an architecture test, and must not be used as
evidence that gameplay works.

### 2. Put repeated mechanics in one `check` helper

A feature test should mostly be data: initial state, input, and expected output.
One helper should own setup, public API calls, normalization, and useful diffs.

This reduces two kinds of friction:

- adding a regression case becomes cheap;
- a public test harness change is fixed in one place instead of dozens.

Do not hide the meaning of a case behind a large generic framework. A reader
should still be able to see the scenario and expected behavior at a glance.

### 3. Prefer value-in, value-out tests

Keep the computation-heavy path in memory where possible. Let thin boundaries
perform disk, network, process, clock, and browser work.

An integrated test may exercise a large part of the engine and still be fast if
its state is explicit and it performs no real I/O. “Integrated” does not have to
mean “slow.”

### 4. Test every useful layer through that layer's contract

Higher-level feature tests are valuable, but they should not be the only way to
exercise lower layers. Use the smallest stable boundary that fully owns the
behavior:

```text
domain -> domain contract test
domain -> application service -> service contract test
domain -> service -> HTTP -> API contract test
backend -> replication -> frontend -> browser feature test
```

This preserves feature-level confidence without forcing every backend edit
through a browser or live server.

### 5. Keep the default suite deterministic and fast

The local/default lane should avoid:

- real network calls;
- unnecessary filesystem setup;
- starting processes repeatedly;
- large fixtures when a tiny scenario proves the same behavior;
- arbitrary sleeps and polling timeouts.

Put unavoidable browser, live-service, process, and visual tests in explicit
slower lanes. Slow tests must still be easy to run and must run in CI.

Record timings so outliers are visible. A handful of slow tests often matters
more than the total amount of production code exercised.

### 6. Preserve causality in asynchronous code

Code that starts background work must return or expose something a caller can
await. Tests must wait for a completion signal, committed revision, event, or
rendered state—not for a guessed amount of time.

```ts
// Bad: hopes the update finishes in time.
await new Promise((resolve) => setTimeout(resolve, 500));

// Good: waits for an observable completion condition.
await expect(status).toHaveText("Turn complete");
```

If no deterministic completion signal exists, the production interface needs a
testable lifecycle before reliable tests can be written.

### 7. Add observability instead of peeking into private state

Some behavior, such as cache usage, replay progress, or rejected authority, is
not normally visible. Expose structured diagnostics or trace evidence at an
intentional boundary, then assert on it.

Do not reach into private dictionaries, monkey-patch an internal method only to
count calls, or depend on debug text that has no stability contract.

### 8. Use mocks narrowly

Mock an external system only when using the real system would be unsafe,
unavailable, or too slow for the chosen test lane. Mock the external protocol,
not our own internal collaborators.

A mock-heavy test often proves only that the mocks were configured to agree
with the implementation. Keep at least one contract or live test that verifies
the substitute still matches reality.

### 9. Make failures explain the broken feature

A good failure shows:

- the scenario or case ID;
- expected versus actual public output;
- a focused structural diff;
- relevant observable diagnostics.

Prefer ordinary `pytest` assertions on structured values. Add custom messages
or a shared normalizer when the first real failure shows that the default diff
is insufficient.

## Choosing the Test Boundary

| Behavior | Preferred boundary | Avoid using as primary proof |
| --- | --- | --- |
| Dice, damage, movement, conditions | In-memory domain scenario | A private helper in isolation |
| Character creation or equipment mutation | Application service plus authoritative snapshot | Mock call order between repositories |
| Authentication, status codes, wire schema | FastAPI `TestClient` | Calling the route function directly |
| Replication and subjective visibility | Serialized input to player projection | Reading private server registries |
| UI labels, affordances, modal flow | Browser-visible roles/text/state | CSS class names or private Zustand fields |
| Canvas animation mapping | Presentation input/output plus a thin browser smoke test | Fixed time sleeps or exact internal object trees |
| Pixel appearance is itself the feature | Reviewed screenshot/visual test | Using screenshots for ordinary logic |
| Dependency/import rule | Static architecture test | Claiming the static check proves runtime behavior |

## Backend Examples

The examples below illustrate the pattern; use the repository's real fixtures,
commands, and projection types when implementing a test.

### Good: one data-driven gameplay check

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MoveCase:
    name: str
    destination: tuple[int, int]
    expected_position: tuple[int, int]
    expected_status: str


def check_move(case: MoveCase) -> None:
    game = make_small_encounter(
        hero_position=(0, 0),
        blocked_tiles={(1, 0)},
    )

    result = submit_player_action(
        game,
        actor_id="hero",
        action={"kind": "move", "destination": case.destination},
    )

    view = project_player_state(game, player_id="player-1")
    assert result.status == case.expected_status, case.name
    assert view.actors["hero"].position == case.expected_position, case.name


def test_player_movement_contract() -> None:
    cases = [
        MoveCase("open tile", (0, 1), (0, 1), "committed"),
        MoveCase("blocked tile", (1, 0), (0, 0), "rejected"),
    ]
    for case in cases:
        check_move(case)
```

Why this is useful:

- it tests a gameplay result, not pathfinding internals;
- it proves rejected movement does not mutate authoritative state;
- adding a relevant regression is one data row;
- pathfinding and event implementation can be replaced without rewriting the
  requirement.

### Bad: freezing backend implementation

```python
def test_move_calls_pathfinder(monkeypatch):
    shortest_path = Mock(return_value=[(0, 0), (0, 1)])
    monkeypatch.setattr("dnd.core.dijkstra.shortest_path", shortest_path)

    controller = Controller(...)
    controller._settle_move("hero", (0, 1))

    shortest_path.assert_called_once_with(...)
    assert controller._pending_events[0].__class__.__name__ == "MoveEvent"
```

Problems:

- it can pass even if the player never moves;
- private methods and collections become accidental contracts;
- a valid pathfinding or event refactor breaks the test;
- the mock duplicates behavior the real integrated path should exercise.

### Good: test the HTTP contract through FastAPI

```python
def check_geometry_query(client, request_json, expected_status, expected_json):
    response = client.post(
        "/v1/geometry/query",
        headers={"Authorization": "Bearer player-token"},
        json=request_json,
    )
    assert response.status_code == expected_status
    assert response.json() == expected_json


def test_geometry_query_returns_the_player_visible_route(server_client):
    check_geometry_query(
        server_client,
        request_json={
            "game_id": "game-1",
            "from": [0, 0],
            "to": [0, 2],
            "known_revision": 7,
        },
        expected_status=200,
        expected_json={
            "route": [[0, 0], [0, 1], [0, 2]],
            "cost": 10,
            "revision": 7,
        },
    )
```

This checks routing, authentication, serialization, and the public result. An
in-memory domain test should cover the larger input matrix; the HTTP test only
needs representative wire-contract cases.

### Bad: testing a route as an ordinary function

```python
def test_geometry_route():
    result = geometry_query(_fake_request_model(), _fake_runtime())
    assert result.cost == 10
```

This misses authentication, dependency wiring, validation, status codes, and
serialization—the things the HTTP layer owns.

## Frontend Examples

### Good: assert what the player can observe and do

```ts
import { expect, test, type Page } from "@playwright/test";

async function checkAttackAvailability(
  page: Page,
  scenario: "player-turn" | "enemy-turn",
  expected: { enabled: boolean; prompt: string },
) {
  await openKnownScenario(page, scenario);

  const attack = page.getByRole("button", { name: "Attack" });
  if (expected.enabled) {
    await expect(attack).toBeEnabled();
    await attack.click();
  } else {
    await expect(attack).toBeDisabled();
  }

  await expect(page.getByRole("status")).toHaveText(expected.prompt);
}

test("attack affordance follows the authoritative turn", async ({ page }) => {
  await checkAttackAvailability(page, "player-turn", {
    enabled: true,
    prompt: "Choose a target",
  });
  await checkAttackAvailability(page, "enemy-turn", {
    enabled: false,
    prompt: "Waiting for enemy turn",
  });
});
```

`openKnownScenario` may establish data through a supported test fixture or
public application boundary. It should not bypass the feature by directly
forcing the private UI store into the expected final state.

### Bad: assert DOM and store implementation

```ts
test("attack button", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => {
    window.__privateStore.setState({ isPlayerTurn: true });
  });
  await expect(page.locator(".hud > div:nth-child(3) > button.action")).toHaveClass(
    /enabled/,
  );
});
```

Problems:

- the test creates a state the real data path might never produce;
- a harmless DOM or CSS refactor breaks it;
- it does not prove the button works;
- it couples the suite to a private store.

### Good: separate presentation computation from browser I/O

```ts
const cases = [
  {
    name: "hidden enemy",
    input: { visible: false, conditions: [] },
    expected: { renderActor: false, badges: [] },
  },
  {
    name: "visible poisoned enemy",
    input: { visible: true, conditions: ["poisoned"] },
    expected: { renderActor: true, badges: ["Poisoned"] },
  },
];

for (const testCase of cases) {
  const actual = buildActorPresentation(testCase.input);
  assert.deepEqual(actual, testCase.expected, testCase.name);
}
```

Use many fast cases at the serialized-data-to-presentation boundary, then keep a
small Playwright test that proves the production browser path consumes that
presentation and renders the player-visible result.

### Bad: use source text as proof of a UI feature

```ts
const source = readFileSync("src/ui/actionBar.ts", "utf8");
assert(source.includes("Choose a target"));
```

This can be a valid static policy check only if the policy is specifically about
source ownership. It does not prove that the prompt is reachable, visible, or
correctly connected to gameplay.

### Bad: synchronize animation with sleep

```ts
await page.getByRole("button", { name: "Move" }).click();
await page.waitForTimeout(1000);
expect(await readActorPixelPosition(page)).toEqual({ x: 320, y: 180 });
```

Prefer a semantic completion signal:

```ts
await page.getByRole("button", { name: "Move" }).click();
await expect(page.getByRole("status")).toHaveText("Movement complete");
await expect(page.getByTestId("hero-position")).toHaveAttribute("data-tile", "2,1");
```

Test IDs and diagnostics are appropriate when they expose stable semantic state,
not internal object identity or arbitrary layout structure.

## Cross-Stack Tests

Use a real backend plus a real browser for a small number of critical journeys:

- create or load a game;
- enter an encounter;
- discover and submit an action;
- observe authoritative state return through replication;
- verify the visible result and reconnect behavior.

Do not use cross-stack tests for every permutation. Put rule matrices in fast
backend or presentation tests, and reserve cross-stack tests for wiring and
high-value journeys.

A cross-stack test should fail if the contract between repositories breaks. It
should not duplicate backend setup by hand in a frontend mock with a schema that
can silently drift.

## Expected Outputs and Snapshots

Snapshots or golden files are useful when the output is large and genuinely
meaningful as a whole, such as a player projection, event transcript, or visual
render.

Rules for updating expected output:

1. Review the diff; never accept it blindly.
2. Confirm every changed field is part of the requested behavior.
3. Keep volatile IDs, timestamps, and ordering out through one shared
   normalizer—unless they are the contract under test.
4. Prefer focused structured assertions when only a few fields matter.
5. Never mix unrelated expectation updates into a scoped feature change.

## Beyond Hand-Written Examples

Once a feature has a data-driven `check` helper, it can support:

- **parameterized cases** for known rules and regressions;
- **property tests** for invariants such as “rejected actions never mutate
  state”;
- **exhaustive small cases** for bounded inputs such as dice modifiers or tiny
  grids;
- **fuzzing** for parsers, schemas, replay streams, and malformed network data;
- **external fixtures** shared by backend, SDK, and frontend contract tests.

Generated cases supplement named examples. Always keep a small, readable smoke
case that is easy to debug in an IDE.

## Test Lanes

### Default local lane

- in-memory domain and service feature tests;
- schema and API tests using `TestClient`;
- pure TypeScript data-to-presentation tests;
- type checking and intentional architecture checks;
- no live services, arbitrary sleeps, or repeated browser startup.

### Browser/CI lane

- production browser wiring;
- DOM and canvas interaction;
- representative screenshots where appearance is the requirement;
- reconnect, animation completion, and browser lifecycle checks.

### Live/integration lane

- real backend/frontend journeys;
- real external protocols where required;
- process, filesystem, persistence, and deployment behavior;
- tests expected to be slower or environment-dependent.

Every test belongs to an explicit lane. Adding a slow test to the default lane
requires a reason and timing evidence.

## Review Checklist

Before accepting a test, confirm:

- [ ] The test names a user-, client-, or architecture-visible requirement.
- [ ] The boundary is the smallest stable boundary that owns the behavior.
- [ ] The test fails when the requested behavior is broken.
- [ ] The test would survive a valid internal refactor.
- [ ] Setup reaches the feature through a supported path.
- [ ] Assertions cover output and important non-mutation on rejection/failure.
- [ ] No arbitrary sleep is used for synchronization.
- [ ] Mocks represent unavoidable external boundaries, not our own internals.
- [ ] The case is deterministic and placed in the correct speed lane.
- [ ] Failure output identifies the case and shows a useful diff.
- [ ] The implementation and test changes stay inside the agreed scope.

## Short Rule

**Describe behavior as data, exercise it at a stable boundary, assert the
observable result, and keep the test independent of how the result is produced.**
