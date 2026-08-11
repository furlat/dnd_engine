# Current Gameplay Stabilization Manifest — 2026-08-10

Status: **IN PROGRESS — NOT ACCEPTED**

This manifest is the entry gate for the accepted automated-testing-surface
plan at SHA-256
`2ce76d85eaed46c54f7574ffac02b01cf6688f2af18c6994201d615ba8b7f8a5`.
The testing-surface runner, harness, schema, and migrations remain
implementation-unauthorized until this manifest is complete and receives the
required fresh three-way implementation review.

No focused smoke alone closes a product row. A completed row must retain its
pre-fix reproducer, pass the focused owner gates, pass its owned-process
canonical product journey without route interception, return the presentation
head and command surface to a lawful state, and report zero unexpected page,
console, network, WebGL, reconciliation, or teardown faults.

## Role and acceptance boundary

This document is being assembled by implementation coordinators. The root task
and every agent which wrote any current-cutoff source, test, plan, manifest, or
artifact byte is an **IMPLEMENTER/COORDINATOR**, not an independent reviewer of
those bytes. In particular, the current implementation tasks
`/root`, `/root/reducer_sequence_surface`, `/root/ai_terminal_oracle_red`, and
`/root/unit5_replay_terminal_final2` cannot contribute an acceptance verdict
for their own current-cutoff work. Every earlier ACCEPT/REJECT or slice-review
message from one of those tasks is discovery or implementation history only;
it is revoked for acceptance and cannot transfer to the final cutoff.

Focused green gates are implementation evidence, not accepted product
completion. The accepted automated-testing plan also does not imply that its
testing-surface implementation exists or that the game is accepted; that plan
remains blocked at its entry gate while this manifest is `IN PROGRESS`.

Before any acceptance claim, the coordinator must perform this exact handoff:

1. stop every writer and verify the normal and owned test processes are joined;
2. freeze and publish exact backend, generated SDK, NeuroClient, focused-test,
   owned-product artifact, and manifest hashes, together with changed-file
   ownership by implementation task;
3. run the cold/default/focused and owned-process product gates against that
   one immutable cutoff, with no source drift or verdict transfer;
4. dispatch three fresh read-only whole-cutoff reviewer tasks which made zero
   edits to the reviewed bytes: one internal architecture/causality review,
   one engine-external review, and one NeuroClient-external product review;
5. record each fresh reviewer task ID and its exact read-only scope here at
   dispatch, then require all three to recheck the final hash after reading.

The fresh reviewer task IDs are intentionally **UNASSIGNED** while writers are
active. They must not be pre-created, reused from an implementation task, or
filled from a prior review thread.

## Preserved live evidence

| Artifact | SHA-256 | Scope |
|---|---|---|
| `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-subjective-pre-fix.json` | `103e109a205c4b216f0cdc42b4d2bf823b630443b7618312e80dc2639ffc04d1` | Repository-preserved exact 111-delivery sibling-class reproduction; final observation 69, presentation 92, combat-log 42. It is not claimed to be byte-identical to the user's Haste/16/25 sequence. |
| `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-objective-pre-fix.json` | `0c6f1051867a876d93942b14e89955a3b8927b7512c6ce74aecf094b6e234f39` | Repository-preserved exact objective events 1..1105. Events 1058..1100 contain the complete fatal second Fireball root. |
| `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-combat-log-pre-fix.json` | `234f5be0398190b90452b26bd3ee0f652d1d49c57a70383f787915524f7aae22` | Repository-preserved exact canonical combat-log evidence paired with the replay and objective stream. |
| `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-objective-current-nearest.json` | `cdf0de449f30390a9f23d3d15366ed93be8c7d051d4527412d818098e400fb19` | Immutable current objective artifact for game `0dbb4bb4-095a-4003-9438-eee942a6a96c`, source `8f1a39cf-7d03-433d-9459-d786d03b29fe`, generation `b1926256-6d75-4356-85b9-9cbe9e01982f`. |
| `agent_docs/evidence/current_gameplay_stabilization/fireball-haste-fatal-subjective-current-nearest.json` | `05dfa3c729b602b5f76ad853ed512855a6db251966575f006249b552e4fe4205` | Exact paired player archive containing first Fireball/deaths, Haste Potion/Haste, second Fireball/death/Turn End. It remains deliberately `nearest`: it lacks Invisibility removal and cannot qualify the full named corrected sequence. |

The later testing surface must import each preserved pre-fix artifact as an
intended-red case and its complete current fixed counterpart as a positive
case without rolling production code back. The `current-nearest` pair is not
that counterpart and must not be promoted by prose; a new immutable pair with
the full Fireball -> Haste -> Fireball -> Invisibility removal -> death -> Turn
End chain is still required.

## Stabilization ledger

### Player game creation and administrative-simulation authority

- Status: **FOCUSED BACKEND GREEN; CURRENT OWNED PRODUCT RERUN PENDING**.
- Escaped product boundary: the ordinary player-facing empty-profile path used
  to compose/start an observer/AI game, while a forged AI-only start could
  replace the hot game before the backend rejected the missing owned Human
  roster. The mounted empty-profile UI and standalone pre-reset backend
  boundary are now focused green, but that does not close hosted authority.
- Required operation contract: `player_game` requires at least one exact
  principal-owned playable Human roster member and its exact owner roster-slot
  identity. `admin_simulation` is not a browser assertion: hosted creation
  requires an authenticated SERVICE principal with server-provisioned
  administrative-simulation authority; standalone local simulation remains a
  separate local-trust boundary. Missing/unknown/crossed operation shapes fail
  before mutation.
- Hosted red/green: the old gateway validated administrative authority before
  worker/game/membership creation but after character deployment preparation.
  The red-first gate proved an unauthorized request invoked the deployment
  builder for a stale owned character before returning 403. The gateway now
  resolves the request-owned roster and authorizes the exact operation/principal
  before required-character enumeration or any deployment/rebase/settings
  owner. Guest, name-only Human, and unprivileged SERVICE requests all return
  exact `admin_simulation_authority_required` without calling the deployment
  builder; character snapshot and revision histories, settings, directory
  events, workers, games, and memberships remain byte/row equal.
- Current owners: `server/game_gateway.py` SHA-256
  `e5a7ff902ded32a50aaa02b3fa4890f666e0cdc90ed58bfd9298cb8286fc06a0`
  and `tests/manual/test_110_multi_game_gateway.py` SHA-256
  `4e1bde9729d049fd88285ce7824cb282df163f90d06432e944ed79d28501bb50`.
  Independent focused reruns pass the preauthorization negative, authorized
  SERVICE observer positive, and two-owned-character player/deployment
  positive; scoped Pyright and semantic diff checks are green.
- Adjacent lifecycle red is closed without weakening the public contract. The
  old reconnect fixture's allied Sorcerer cast Fireball twice (including a
  Haste action), ended combat in 0.762668 seconds at cursors 328/5, and therefore
  correctly received typed `game_not_live`. The live reconnect/observe/stop
  fixture now uses one owned Human fighter under fixed-player opening and
  asserts repository `ACTIVE` after bootstrap. The exact node passes twice;
  ended-game attachment remains a typed 409 with no sleep or grace period.
  The complete red terminal spool is repository-preserved at
  `agent_docs/evidence/current_gameplay_stabilization/gateway-fast-terminal-reconnect-pre-fix/`;
  its manifest SHA-256 is
  `3f37151c6ac4b7c700a8f34aff8896ea97a28dc67dfeefdbd123fc5fe5f15128`
  and each objective/subjective/summary/holdings filename retains its exact
  content digest.
- Product closure: a fresh owned backend+Vite+browser journey must show exact
  empty-profile guidance with zero compose/start requests, then one persisted
  character, one explicit `player_game` request, exact owned assignment,
  compose/start/join/bootstrap/activate, a rendered controllable actor, and one
  real state-changing command. A mounted hosted guest must see administrative
  creation controls disabled/inert; a real authorized SERVICE positive remains
  separate.

### Shared damage-roll allocation across multi-target actions

- Status: **ENGINE FAMILY GREEN; CURRENT HASH CUTOFF RECORDED**.
- Red: deterministic process seed 6 produced one Fireball whose three failed
  saves independently rolled 30, 35, and 38 damage. The cast lawfully ended the
  encounter in one controller turn, exposing both the mechanics defect and a
  stale AI replay oracle that unconditionally demanded two controllers.
- Required owner contract: dependency-neutral action-outcome metadata declares
  `shared_execution` versus `per_application`. One execution-scoped component
  packet owns the concrete roll identity/formula/result across target-local
  saves, resistance, HP, and combat-log applications; component keys are exact,
  nested/exceptional/second executions cannot leak packets, and multiple
  damage components remain distinct.
- Complete maintained family: Acid Splash, Magic Missile, Fireball, Burning
  Hands, Lightning Bolt, Thunderwave, Shatter, Circle of Death, Cone of Cold,
  Sunburst, Ice Storm, Chain Lightning, Flame Strike, Acid Flask, Sunbeam
  Strike, and Dragonborn Breath Weapon. Scorching Ray, Prismatic Spray,
  persistent-zone triggers, and single-target saves are intentionally outside
  the shared-execution set.
- Non-vacuous closure requires an executable inventory plus mixed failed/saved
  target orders, nonrepeating RNG consumption, exact shared `roll_uuid` and
  `dice_uuid`/results, half-or-zero semantics, fresh identity on the next
  execution, Magic Missile's authored `1d4+1`, two stable components for Ice
  Storm/Flame Strike, and the two non-SpellAction owners. Same-face totals or an
  all-failed-save subset cannot qualify. Chain Lightning remains exactly 10d8
  when upcast; only its target count grows.
- Current proof: the original Fireball strict xfail is removed and its
  `KNOWN_ISSUES` row is `FIXED`. The complete executable inventory and mixed
  target-order gates are green, including Magic Missile/Acid success-zero,
  Acid Flask half damage, distinct Flame Strike components, two consecutive
  Sunbeam and Dragonborn executions, generic nested/exception/spec-drift
  isolation, and Chain Lightning's exact 10d8 upcast rule. Maintained owner
  results are 36/36 remaining spell contracts, 16/16 Dragonborn runtime,
  60/60 spell families, 14/14 catalog, 17/17 spellcasting core, 48/48
  subjective observation, 54/54 combat-log projection, 8/8 spell-item
  factories, 3/3 execution-scope isolation, and 10/10 native-AI game creation
  and replay. Scoped Pyright is 0/0; event and TypeScript SDK generator checks
  are green.
- Exact production cutoff: `dnd/actions.py` SHA-256 `c5ffe1110b132255ed080a8d6b49f869500e205a27bd5bc3cec032db4b77d77d`;
  `dnd/core/action_execution.py` `02f83b0e21f07d05ebc825e0dcabf9a6323e2cc72e3782c6f42b299dbb16befb`;
  `dnd/core/action_outcomes.py` `af1a304703a8a40f7eee153837ad457a9820bb190fde38034ab43608ec20916e`;
  `dnd/core/spell_execution.py` `97270953661bf653dae9b489d1452667e6cb0f01de1925cf8b480eec49f5593c`;
  `dnd/spells/evocation.py` `6593162d7c55e67ff6dae223cf43cbdb9bdc9afca5c6c881ac1754b854a10834`;
  `dnd/spells/conjuration.py` `98beffb3fd4ba1aa53c5bd9695904a940c056c0c3ee16c798bb7c78ce5dc3967`;
  `dnd/items/spell_items.py` `975fb246f1b14a7e55f23bbf091f1b498b6117376ea479a3718dc92ed4d29db1`;
  `dnd/origins/dragonborn.py` `1fe1c8db2bb7a873365fe477dc6009a105ce3777fd300bcc445e19e617b2bb87`;
  and `dnd/core/combat_log.py`
  `52b0d22435a25f372657bf6de9edc7a551441d74891b21b6217eb2e325ec4fe8`.
  Auto-hit Magic Missile children now expose the same typed `roll_uuid`,
  `dice_uuid`, results, and formula evidence as attack/save applications; equal
  damage totals alone are not the oracle. Generated contract JSON and
  TypeScript hashes are
  `e3db5716239b9f967314b912976b469e8bcc9427a945ac7ac9465c8129fcdb69`
  and
  `d9e727352926a0f376d37d1199a6b86ff6fc9e0dc6f116ff5a57ff6480005fd9`.
- Independent rerun on these exact bytes: execution packet owner 3/3,
  remaining spell-family owner 36/36, Dragonborn owner 16/16, and native AI
  game-creation/replay owner 10/10.

### Fatal spell-root disclosure / second Fireball cue

- Status: **LIVE PRODUCT GREEN**.
- Red: in the preserved trace, objective events 1058..1100 contain the full
  fatal Fireball, while subjective observation 69/source 1105 contains damage,
  death, light, turn-end, and encounter-end presentation but no spell cue.
- Cause: the spell root was rechecked against completion-time location
  authority after the only observer died during the root.
- Correction: the canonical runtime now owns a bounded, generation-local,
  exact spell-root projection-context store. Only lawful declaration,
  execution, and effect facts may create or monotonically merge disclosure;
  completion can only validate and consume an already-admitted exact context.
  The frozen detached signature equality-binds every cue-owned immutable fact,
  including source/target/position, spell identity/name/school, base and cast
  levels, range/projectile/area facts, and behavior/content attribution.
  Explicit-batch incomplete or poisoned sibling roots are audited and evicted
  at their containing delivery boundary, while lawful singleton split
  lifecycles remain supported. The global mapper remains stateless;
  completion-only grants cannot create or widen disclosure.
- Spell-semantic cutoff owners: `server/player_replication/mapper.py`,
  SHA-256
  `fbda5b2c90c5de35ad830ca7130f55556806213d94ee0e1720eebc6b41ac2b36`,
  and `server/player_replication/runtime.py`, SHA-256
  `307bd8e909215fe161caf9307ca4b86434f81e5e33b8f7dd5207c6ef0ad30034`.
  Later isolated movement-privacy and terminal-diagnostics work moves the
  current combined files to mapper SHA-256
  `da94cb3665752a05e292f54538244ed0d1ef7a48d10229880bc9cd83d9446426`
  and runtime SHA-256
  `950e109c75134e632a267de30d0472f57075c3c18112f9f9d78c81c130d4cd63`.
- Focused green at the semantic cutoff: mapper 75/75 and runtime 51/51,
  including completion-only,
  terminal-signature mutation, poison-sibling, explicit-incomplete,
  split-batch fatal, cleanup, and stale-completion adversaries,
  and scoped Pyright zero errors.
- Owned product proof: deterministic seed 36 independently completes one
  subjective Fireball root followed by exact damage, `life_state=dead`, light,
  turn-end, and encounter-end cues. The cast, death, nested terminal banner,
  and encounter-result intents all complete; client state is ended, backlog is
  zero, source/combat-log cursors are 828/33, WebGL is zero, and coverage,
  diagnostics, page, console, and network faults are zero. The ordinary
  no-relay green JSON/PNG hashes are
  `4b6b8adbf6b9094a056e9e288e502b81d1029ca496689b03066ca144582d7da8`
  and `410751a8456ad8885ae31a5ca9a44368d1bb0f7af6f14d23413e3aa954c4c073`.
  Two additional unchanged-source seed-36 runs exercise the deterministic
  terminal-parity overlap described below and preserve the same complete
  gameplay/presentation result.

### Remembered-corpse objective/subjective parity

- Status: **FOCUSED GREEN**.
- Red: a W_i prefix after lethal multi-target Fireball retained authorized
  unseen corpses in the subjective replica, while the parity oracle compared
  them against a current-visible-only objective set.
- Correction: diagnostic entity/loadout/encounter scopes now use the same
  controlled, observer, or currently visible authority. The reducer's corpse
  memory is unchanged.
- Owner: `server/subjective_parity_diagnostics.py`, SHA-256
  `052476c730df4dc1763f776015fe331ced616c719b539c345bd7740841719341`.
- Green: `tests/manual/test_125_subjective_objective_render_parity.py` 9/9.

### Decorative RAF/timer resource lifetime

- Status: **FOCUSED GREEN**.
- Red: a completed Banner/FloatingText transaction left request-frame work
  alive; later replay state synchronization destroyed its Pixi child and the
  stale callback dereferenced the destroyed container.
- Correction: ClipQueue gives each exact transaction a callback lease; every
  request-frame continuation is canceled/fenced at transaction terminal,
  failure, reset, seek, or host destruction.
- Owner: `src/render/clipQueue.ts`, SHA-256
  `d52ae54bf374f6697969b847837a379c611725de9b3e41992271b85a2724c1cf`.
- Green: presentation-runtime-host, ClipQueue liveness, replay head-drain,
  animation coverage, diagnostics isolation, and TypeScript gates.

### Fire Bolt atlas, GPU admission, and scene preservation

- Status: **LIVE PRODUCT GREEN**.
- Preserved red fixture: the shipped legacy Fire Bolt atlas is exactly
  9216x2048 while the live Chromium WebGL `MAX_TEXTURE_SIZE` is 8192.
- Correction: the authored visual uses the supported 5760x1024 repacked atlas;
  the asset owner validates physical dimensions against the actual renderer
  before GPU upload; required media fails the transaction rather than being
  silently omitted; asynchronous prepare/release failures remain observed and
  causal.
- Key owners: `src/render/presentationAssetService.ts` SHA-256
  `8623eb057e433c30bb61607e3325ef9188e7c7e5176978f78974610d88d727bc`,
  `src/render/clips/CastClip.ts` combined SHA-256
  `2a6fbe33aa6feeac46afac3bd3d523d792eb6d7a126df5481156d0dc33e99c13`.
- Green: repaired real authored visual completes; legacy fixture rejects before
  upload; actor/target scene remains; queue becomes idle; WebGL error is zero.
- Product proof: a fresh owned backend, Vite process, and persistent Sorcerer
  use the exact lease-owned Fire Bolt row and target through the mounted action
  bar. One POST returns 200, source cursor advances 160 to 179 and combat-log
  cursor 1 to 2, target HP falls 15 to 3, the exact direct spell cue completes,
  Pixi world children move 6 to 8 to 6, and input resumes with backlog zero,
  WebGL error zero, and no diagnostic, console, or network fault.
- Product script SHA-256:
  `b3a3ed0d3e797951076693d3cfc37502a9c4ce3ee4b6bc5ad8a4bc11e99e018d`.
  Machine-readable artifact SHA-256:
  `efa38dc1dbda72760df1ecc699752bdfad46afb49def59912e74871ce416b179`.
  Mounted screenshot SHA-256:
  `8626cd3082296fa360385e5a822c56a021dcc1a4b13d4ec52ff0c135a77c202a`.

### Last-committed-scene recovery

- Status: **FOCUSED GREEN; OWNED PRODUCT RECOVERY GATE PENDING**.
- Correction: presentation-incident restart preserves the last committed
  scene while command/targeting authority is revoked; only the first
  authenticated replacement reuses it, and the latch clears after successful
  state synchronization.
- Production owners: `src/engine/eventStream.ts` SHA-256
  `9e755c32bcba8cf253a133823a34c77660805a5e63bb8269da863c0f8508b709`,
  `src/engine/eventIngestion.ts` SHA-256
  `6158333e075afc5a2fa4239d667730bedfc5995d8bed5677760a0cb9dc00b0da`,
  and `src/render/sceneRenderer.ts` SHA-256
  `0097e8983e862edee7ef8da6be7b2fb817c90443ed45f1f2479d41fc76401df2`.
- Focused gate: the real SDK follower/journal, production event-stream/head
  drain, and scene owner preserve the same Pixi actor through delayed
  authenticated replacement and a throwing post-install callback.
  `presentation-head-drain-live-smoke.mjs` SHA-256
  `c8ef9f91d1bcc59336153484707d69b3be353d0e2a17ddd9f74b69bf795c61e8`.
  This is a browser module-integration gate with synthetic transport/Pixi
  fixtures, not an owned backend+Vite product journey.
- Adjacent non-substitutable evidence: the physical asset/runtime-host gate
  `presentation-asset-service-smoke.mjs` SHA-256
  `4e82d2d78f9cc919e1985a8cc87cdcbc7c02e085046fbe0f9f30a011daf2e10f`
  proves supported media and the legacy oversize pre-upload rejection; the
  owned Sorcerer product gate `sorcerer-spell-product-journey-smoke.mjs`
  SHA-256
  `210f4b2b32989d77e88837792751b3b6effb9f77948fe683fe2f6d56fd98a858`
  proves the repaired Fire Bolt visual succeeds. Neither joins a real
  asset/GPU presentation incident to authenticated replacement recovery.
- Remaining product proof: in one owned backend+Vite+browser journey, execute
  the real lease-owned Fire Bolt command with a declared failing required-media
  fixture, hold the real replacement bootstrap, prove the last committed
  actor/scene/canvas survives and authority stays revoked, then release exactly
  one authenticated replacement and prove stateSync, scene reuse, cleared
  preserve latch, idle backlog, and lawful input restoration with zero page,
  console, network, WebGL, reconciliation, or teardown faults.

### Potion/Haste semantic presentation

- Status: **LIVE PRODUCT GREEN**.
- Red: the authored item action was a generic Taunt and its existing smoke
  treated the cue count as sufficient semantic feedback.
- Correction: the exact item recipe retains its mechanical body action while
  adding an effect-bound authored overlay and semantic action-feedback badge.
- Key owners: recipe SHA-256
  `8131f9215664ac5aa2dc072d2f184c426610123a5a96446df71723c3d49c8460`,
  action recipe SHA-256
  `e86245a055bbb2e1e5685a182cf63c0342aaf81b37ebf85355c32176f312f1c3`.
- Focused green: immutable historical-boundary fixture SHA-256
  `1710b4daaf6ca9ea68bbbf714ff9cdf6cbe6b8dfbb3d9898492ac31b29e057d7`
  reproduces the retired validator contradiction; current boundary smoke
  SHA-256
  `fccc6e21caeb4ad2f58360da32b085ae1f794392d038232315656fcf74f779ca`,
  generator check, TypeScript, recipe registry, and mounted potion animation
  smoke SHA-256
  `365853e309ca5d0940e9f672e9151c70bf6d265ac3c1a6c87a034177b6362e24`
  prove the exact Haste overlay, feedback, condition folding, equipment
  restoration, and idle completion.
- Product gate: owned-process script SHA-256
  `b93e043f9c539171bc4156d3c3d5318b22db4ff3914a925816d20f86c2bd71eb`
  creates and persists the exact character, boots a fresh backend and Vite,
  acquires the lease-owned Haste Potion row, and sends one HTTP-200 command.
  Source/combat cursors advance 194/1 to 207/2; the semantic Haste condition,
  `Haste Potion` and `+Haste` overlays, exact root action and folded condition
  child all complete. Pixi returns to idle, a fresh lease/input is restored,
  backlog is zero, and presentation, WebGL, page, and network faults are zero.
  Immutable product JSON SHA-256:
  `7d3154e3f49980ecaa1efb2a291d4dd5179883e784cdf92bf2c14036ba82493e`;
  mounted screenshot SHA-256:
  `406303a573523d2fd1060a59a29e35a353c4147a3aaa9bb4da2a4bd7aa01d295`.
- Offline authoring closure: the canonical JSON's deliberate Healing Potion
  strip is now validated exactly instead of being erased by a stale zero-media
  migration. Population owner SHA-256
  `2b702a2126dcbbc76100a5ac3238fc9769ef95f506edb5b560bcd420106fcebf`;
  the exact generator check, potion runtime gate, TypeScript, and cold
  ports-down build pass.

### Canonical Water material

- Status: **LIVE PRODUCT GREEN**.
- Red: the arena authored a tile named Water without the canonical factory, so
  projection fell back to `floor.png`.
- Correction: the arena uses `water_factory`; walking remains forbidden with
  projected cost 0, swimming remains lawful, and `water.png` is the exact
  semantic material.
- Owner: `dnd/maps/arena_layout.py`, SHA-256
  `45654e913e06d5b4537ee1fb30176fa12132b0e6158a622c73d36159c8df3068`.
- Product gate: the canonical owned-process game mounts all six disclosed
  water cells with `visual_key=water.png`, `walking_cost=0`, a nonblank Pixi
  canvas, and no rendering/network fault.

### Acid Splash one-of-two targeting

- Status: **LIVE PRODUCT GREEN**.
- Historical red: an exact failed-save Acid frame had a direct spell root and
  folded damage child, but authored damage/condition cloning discarded the
  child's already-authorized intent evidence. Mapping failed with
  `cue ...:4:2 has no exact presentation disposition` after the 200 action.
- Correction: authored intent transformations transfer the exact existing cue
  evidence to their replacement object; no new disposition policy or inferred
  ownership was added.
- Product matrix: exact mounted Finish and Enter primary-only casts, full
  adjacent Wolf+Guard allocation, and the only-one-discoverable duel all pass.
  Full-two sends the exact Guard extra UUID and advances source 149 to 185;
  the single duel exercises a failed save, HP 50 to 47, and source 54 to 80.
  Each case returns to fresh lease plus `my_turn_input`, with one POST and the
  exact presentation head committed.
- Owners: mapper SHA-256
  `66f42ecafe998efbd536d66ef4c8ea196649611eebcdffc98d6fbe8d35aee361`,
  live product smoke SHA-256
  `e64d12284dc72d72476e69aee1308cd58a4d527fba3ed9188a4bc107f1284e2e`,
  semantic regression SHA-256
  `c081ee9ed77af405cdc855b25ece8cca5016bfc7fd2210bcbf7b5ad161a5c751`.
- Immutable historical-red/current-green frame fixture SHA-256:
  `516aef57453b09e5ac146dbf2acd649ee36fb2617ac2c54f0971bab50a7596ff`.

### Default Sorcerer Invisibility

- Status: **LIVE PRODUCT GREEN**.
- Red: `hero.sorcerer_l5_standard_torch` omitted Invisibility from its authored
  spell set.
- Correction: the canonical six-ranked-spell build includes Invisibility and
  retains its exact content reference/contract hash.
- Owner: `dnd/content_system/builtin_character_builds.py`, SHA-256
  `43bd8d91b8dcecd2ab9816f866e84e3b09baa32f6110a235c29f09f748ea3d5d`.
- Green: create, persist, reload, materialize, and AvailableActions expose exact
  level-2 and level-3 variants.
- Product proof: a fresh persisted canonical Sorcerer exposes exact lease-owned
  `Invisibility__slot_2` and `Invisibility__slot_3` rows. The mounted level-2
  variant and self target issue one 200 POST; the store installs `Invisible`,
  the mounted actor settles at alpha 0.5, the direct spell cue and condition
  child clips complete, and input resumes with backlog zero, WebGL error zero,
  and no diagnostic, console, or network fault.
- Machine-readable artifact SHA-256:
  `bc54c703bf228defc65e12a9e3b3108e7d2cc3459b0baf5291c9f60eea5300b2`.
  Mounted screenshot SHA-256:
  `3acd837348ede22e55bc70edf960e6f04105b03e0811ea030c632f5cfccef9a0`.

### Position-only SpatialEffect parity

- Status: **LIVE PRODUCT GREEN**.
- Red: the SDK rejected a lawful DIRECT Grease spell effect with
  `target_uuid=null` and an exact disclosed position.
- Correction: SpatialEffect children require a null entity and membership in
  disclosed geometry; non-spatial children still require an entity. Neuro has
  a distinct position delivery and never invents a target entity or AoE.
- SDK validator SHA-256
  `fb6f750b70c065c05ab3d68565fe2ba8e504c976b518c5f27406bb25bee7c5e4`.
- Green: Python mapper 62/62, SDK replication 52/52, TypeScript, subjective
  presentation, disposition matrix, target facing, and combined Fire Bolt.
- Product red: a real mounted Fog Cloud cast issued one exact POST 200 and
  installed the correct nine-tile reducer footprint, but its real
  `SpatialEffectChangeEvent(CREATED)` had no position-authority evidence. The
  mapper therefore privacy-dropped the spatial child and the DIRECT root had
  no application. Preserved product script SHA-256
  `813b9c654d1d091343160d67c3815badea96abebc54262c1dc977e5cd96c2550`;
  red artifact SHA-256
  `325a83d7559e47553874b3f69a0581a0bc64cc4a94a4930277e9101803322ed0`.
- Producer correction: `dnd/spatial_effects.py` snapshots nonempty exact
  `GridMap` subscribers for affected and previous cells into canonical
  position-evidence keys before lifecycle publication. SHA-256
  `154649ff2d3fa0218b827aa8d7cf39a9e12845e008d7f55d09c0eab5d350b767`.
  The real Fog gate proves reciprocal DIRECT root/spatial cues for the
  authorized observer and no cue or coordinate for an unauthorized observer.
  Python gates: mapper 65/65, spatial effects 42/42, senses/light/stealth 38/38,
  spell families 60/60, and scoped Pyright zero errors.
- Product proof: one no-interception mounted cast sends the exact lease-owned
  `Fog Cloud__slot_1` row to position `(1,7)` with no target UUID, receives one
  HTTP 200, and advances source/combat cursors 149/1 to 175/2. Observation 4
  contains one DIRECT spell application at `(1,7)` and one reciprocal
  SpatialEffect child. The reducer and Pixi semantic board contain the same
  effect, the head drains to backlog zero, a fresh lease/input returns, and
  coverage, diagnostics, page, and network faults remain zero.
- Hardened product script SHA-256:
  `c95614073b6f0aae0965e29f6164d530f27168f080a594aaaa98f3e1d79b0c0b`.
  Immutable green JSON SHA-256:
  `567770a19ebf60dec992ce9deb06d72878f921a27bf280b15de4d63518fcfcbe`;
  mounted screenshot SHA-256:
  `9c85e0789a963e25aadfc2f6b83681a1362bc87f4e8d61b5bd27574a66d6c2fb`.
- Evidence-integrity note: the old fixed-name harness overwrote the originally
  announced red JSON SHA `325a83d7...` during the first successful rerun. The
  complete raw pre-fix command log was independently retained and is now
  immutable at SHA-256
  `95f60a2ea651b0d60a76ca9e133f3dadef65c23395513683d5f7ea48ca507050`,
  with unchanged failure screenshot SHA-256
  `9c7b057c6fe69e02afa01d075dc1344fd1aeb93af10841c02e85664eb08ff082`.
  The unavailable red JSON bytes are not claimed restored. A deterministic
  extractor at SHA-256
  `395dedf15c304520353c6b96243a7dbbdae3516e3955cd82c6343250e71556f6`
  validates that exact raw-log digest and preserves the complete raw
  subjective frame, exact action request/200 response, and reconciliation
  diagnostic as
  `fog-cloud-position-spatial-product-pre-fix-extracted.json`, SHA-256
  `e120349072360edc7ccddf9f362bbbba5944222f3cf0b4523a217bb496d5aa88`.
  This is an extracted immutable historical input, not a reconstruction of the
  overwritten container bytes. The harness now writes run-specific red/green
  files atomically and cannot overwrite a prior artifact.

### Visible movement patch without a movement cue

- Status: **PRODUCT VISUAL AND SAME-OBSERVER PRIVACY GREEN;
  SETTLEMENT CONTRACT/SDK INTEGRITY REJECTED**.
- Red: in the deterministic seed-7301 owned product artifact, observations
  22, 23, and 24 move an already-visible Goblin through entity upserts
  `(10,7) -> (9,7) -> (8,7) -> (7,7)` while emitting only light cues. The
  later observation 26 lawfully emits only the final movement leg
  `(7,7) -> (6,6)`. Pixi therefore remains behind the authoritative SDK
  projection and the presentation coverage/parity gate reports the exact
  mismatch.
- Preserved reproducer:
  `DND_TEST_RANDOM_SEED=7301 node scripts/sorcerer-spell-product-journey-smoke.mjs fatal-fireball`.
  Raw artifact SHA-256
  `bb89ab3fbbb17679896a9c82206ed1057875a6f1fb117d9c98d0579cd0e73012`.
- Scope: this is distinct from body-cycle continuity. The correction must
  restore a lawful cue for each disclosed visible position change without
  inventing hidden movement, coordinate adjacency, timing, or a path/root
  correlation contract.
- Cause: `_add_movement_nodes` required identity only from the movement root's
  first EFFECT. A mover that was hidden at root admission could become lawfully
  identified and located at both endpoints of a later exact Step, yet the Step
  was still suppressed.
- Correction: after exact root/Step correlation, source identity may come from
  the frozen root or that completed Step's own exact identity evidence. The
  exact endpoint geometry remains mandatory, and one same observer must own
  identity plus both endpoint grants; perspective-wide union across different
  observers is not authority. Forced movement likewise requires one observer
  to own every non-controlled actor/target identity plus both endpoints, while
  the controlled actor and controlled target remain lawful bypasses. A hidden
  Step emits no cue or coordinates, and a later disclosed edge stands alone.
- Privacy red/green: the pre-fix focused matrix failed four of five exact
  root-identity, Step-identity, forced-identity/endpoint, and controlled-bypass
  cases. The final direct-`project_frame` matrix is 7/7 green, including the
  lawful one-spectator positive and both controlled forced-movement roles;
  scoped Pyright is clean. The combined disclosure owner is intentionally
  named `_movement_step_disclosure_allowed` and owns the one-witness decision
  once; there is no duplicate geometry authorization seam.
- Owners: `server/player_replication/mapper.py`, SHA-256
  `da94cb3665752a05e292f54538244ed0d1ef7a48d10229880bc9cd83d9446426`,
  and `tests/manual/test_121_canonical_presentation_mapper.py`, SHA-256
  `a54deab8ce120eb60da8784d6a95ca2b0765019ca7e3e9ddf4a2a3abcf070f3f`.
  After withdrawing the rejected per-cue settlement heuristic, the full mapper
  gate is 81/81 green with zero privacy failures. The unresolved mismatch is
  retained separately as one strict xfail in the contract owner; it was not
  deleted or weakened.
- Product evidence: the preserved current seed-7301 artifact SHA-256
  `877fe7f3f91ae08ff0e9c3ba91476d607d360e89c4f7b95e77fdf5a6d433b659`
  proves observations 21--24 and 26 now carry matching movement cues and
  entity upserts with zero presentation faults. The immutable-source validator
  is SHA-256
  `6fc8e605ca585b96b6dc33197be291eb7aefa75c5dfdd93ea7ac7134e117ca36`;
  its green evidence JSON is SHA-256
  `900d9add0d6ce59aeda620134d7d744b4f46e3f1f5c65ec9f3d3364dae091f19`.
- Remaining rejection: cue order alone cannot soundly identify final spatial
  settlement when a later synchronous forced displacement or a lawful
  cue-less relocation changes final occupancy. The first per-cue exact-upsert
  and presence-only validator drafts are withdrawn; fixtures must not be
  mutated to satisfy them. The architecture candidate awaiting explicit
  approval is a frame-level
  `entity_position_settlements` row containing `entity_uuid`, the sole terminal
  same-UUID entity patch index, every committed Movement/Forced/Relocation
  presentation ID exactly once, and one discriminated terminal authority:
  `presentation_endpoint {presentation_id}`,
  `state_only_supersession {frame-bound opaque authority_id}`, or
  `state_only_absence`. NOT_COMMITTED cues never appear. A presented terminal
  ID must belong to the same entity and match the upsert position; remove
  requires absence. State-only authority is minted only when the causal index
  proves the latest spatial entry/absence has no delivered direct cue. The
  frame permits at most one canonical entity transition per UUID. This handles
  multiple cues sharing a final patch, death upserts, and hidden lawful
  supersession while rejecting cue-without-patch and ambiguous transitions.
  Disclosed teleports require a direct relocation cue. This is a proposed
  producer-authenticated settlement ledger and still requires explicit
  architect approval before implementation.
- Real-runtime spectator proof must use an ACTIVE encounter, because identity
  observers are installed at `Encounter.start_encounter`. In that lawful setup
  a zero-control spectator with the mover and cells visible receives Step 1
  cue/upsert at `(2)` and Step 2 cue/upsert at `(3)`, with exact identity and
  endpoint grants. A private `SubjectiveReplayCaptureStore` retains the exact
  same rows and the ended bundle survives Python JSON roundtrip. The earlier
  NOT_STARTED cue-less probe is invalid and does not authorize a producer
  change. The rejected patch heuristic has been removed from Python and SDK;
  `test_117_player_replication_contract.py` is 30 passed / 1 strict xfailed,
  and SDK replication is 52/52. The strict xfail is the exact cue-at-1/upsert-
  at-2 mismatch and remains OPEN until an approved settlement contract lands.

### Subjective parity acquisition retirement race

- Status: **FOCUSED GREEN; LIVE PRODUCT GREEN**.
- Immutable red artifact:
  `/home/tommaso/Dev/NeuroClient/app/test-results/sorcerer-fatal-fireball-red-2026-08-10T02-02-51.391Z.json`,
  SHA-256
  `c174f56e26dabc2da08cd28c307c82f18c6a8bf47141763f55f638771eae3634`.
- Confirmed clean gameplay boundary: the accepted terminal head immediately
  fences new parity acquisition (`postTerminalParityRequests=[]`); the full
  Fireball, damage, death, banner, and encounter-result transactions complete;
  client state is ended, backlog is zero, source/combat-log cursors are
  828/33, objective terminal history is complete, and WebGL is zero.
- Red: one parity GET was already in flight before the terminal head reached
  the client. The server retired the mutable player partition first and
  returned typed HTTP 409 `subjective_parity_partition_unavailable`, which the
  browser correctly surfaced as a resource/console failure. Client abort at
  head acceptance cannot retroactively erase a completed non-2xx response.
- Required correction: the composition-owned terminal callback must capture
  one immutable independently-censored terminal parity result after the
  objective stream and subjective runtime callbacks have completed, but before
  terminal publication/cleanup. Runtime and objective snapshots are captured
  in two phases with no nested cross-owner locks: immutable runtime snapshots
  are copied and released first; the objective source boundary is then
  captured, built, and revalidated before a lock-independent result CAS. The
  live diagnostic path uses the same ordering. This prevents the proven ABBA
  deadlock between terminal capture (`source -> runtime`) and bind
  (`runtime -> source`). It validates the uncanceled final
  `EncounterEndEvent`, source/generation, ended state, and source/log frontiers,
  builds pure DTOs, revalidates the source, and compare-and-set publishes the
  first result. The runtime exposes immutable snapshots only; it does not own
  diagnostic retention or read objective globals.
- Retained keys include the full runtime session and resolved authority scope,
  source, generation, perspective epoch, and source/log frontier. Repeated
  authenticated reads return the same bounded `TERMINAL_RETAINED` HTTP-200
  evidence without recreating a journal or reducer. Session deletion,
  authority/perspective rotation, source/generation replacement, declared
  expiry, and bounded-capacity cleanup are explicit lifecycle operations, not
  silent FIFO loss. An explicit per-perspective capture failure uses a closed
  typed HTTP-200 unavailable result and cannot block terminal publication; it
  is not the normal product path.
- Retained reads capture only the current objective source identity/frontier,
  then validate and return the immutable DTO without rebuilding objective
  state. Heavy/sensitive objective projection runs only for a live comparison.
  Barrier-driven bind-versus-terminal and bind-versus-live-diagnostic gates
  must complete without deadlock or mixed-boundary results.
- Hosted retention is process-local and lasts only while the exact worker and
  its authority remain alive. Hosted terminal adoption deliberately keeps the
  player partition live for ended bootstrap/reconnect, so no test may invent a
  hosted retirement seam. For an exact ended source/frontier the diagnostics
  route consults the immutable terminal store before rebuilding a live
  comparison, while leaving that partition intact. A real ADMINISTER proxy
  gate must preserve the terminal response body, identity/cursors/lifecycle,
  and `Cache-Control: private, no-store`; worker/session cleanup then revokes
  it. Post-worker-stop availability would require a generation-fenced terminal
  spool/gateway artifact and is outside this narrow correction.
- Backend owners at this cutoff: `server/event_server.py` SHA-256
  `981e3bd1ec80d03cd2d944527295c20804e8ff1a137033643cfb0436da24c07a`,
  `server/player_replication/runtime.py` SHA-256
  `950e109c75134e632a267de30d0472f57075c3c18112f9f9d78c81c130d4cd63`,
  and diagnostics DTOs SHA-256
  `344ce766c2098eecf534c3cea36be705667dbd44ee3402a1729c4141b0c07832`.
- Focused green: route/runtime test SHA-256
  `b2e6ea1f28d8e77bcd4c7a9545b61c04a1c76286e0baf71641cddda178e551c4`
  is 28/28; scoped Pyright has zero errors; terminal callback ordering is
  1/1. The real hosted worker/gateway gate SHA-256
  `afdc2c9b7f2e2dcd6eee398b4e1467bcb522b341813b7666af1f3e795d4084fc`
  returns exact terminal-retained HTTP 200 with final source/log cursors and
  `private, no-store`, then returns canonical nested
  `runtime_authority_rejected` HTTP 403 after worker stop.
- The real standalone coordinator regression now proves the composition
  callback remains attached after world replacement, captures the terminal
  result before publication, preserves its durable standalone membership
  authority after coordinator cleanup, and returns exact retained HTTP 200.
  Replay-close publication retry is owned by a bounded task set: normal and
  deferred paths cannot publish local/hosted terminal evidence twice, and
  lifespan shutdown cancels and joins every deferred task. The real coordinator,
  retry/no-duplicate, and shutdown nodes pass together 3/3; route, callback,
  and hosted gates pass 30/30. The lifecycle test owner is SHA-256
  `bccd4304085c760918039827aca5d57388dc63e11b8256592db714d7ac4e8f47`.
- SDK/frontend coherence: the canonical generator includes the typed
  available/unavailable response union and `--check` is green. The SDK build,
  objective diagnostics 9/9, and replication 52/52 are green. NeuroClient
  accepts exact `terminal_retained`, terminalizes typed HTTP-200 unavailable,
  and fences late old-incarnation responses. At accepted terminal staging it
  prevents every new poll while allowing only the already-running exact
  request to settle; only an identity-matching available `terminal_retained`
  result is observed, while late live, mismatched, and failed responses are
  inert. The mounted lifecycle gate and TypeScript check are green. Frontend
  owner hashes are `5ed143ad3843d6ad29297a76b44aa10c5059932a354c3e70b778680bfe8ce271`
  for `subjectiveParityAcquisition.ts` and
  `b4e7049b1ce4fc035a1f8e5a4ce936023ef10b90dfb81a8ca3c7e9c2fcacaa79`
  for the focused lifecycle gate.
- Preserved real-product red is immutable artifact SHA-256
  `4b684733507bac75a79c5291c23746c6e232ed5ca64141d2a2c749d2a2a68f4c`.
  Seed 36 completes the Fireball, damage, death, banner, encounter result,
  final cursors, scene, and zero-fault presentation chain, and starts no parity
  requests after terminal acceptance. Its sole failure is one request already
  in flight returning HTTP 409 `subjective_parity_partition_unavailable`.
  That historical request returned typed HTTP 409 before terminal retention and
  is the intended-red counterpart.
- Deterministic owned-product race proof uses an explicit relay that delays the
  arrival of exactly one already-started production parity request; it never
  alters, filters, retries, or suppresses the backend response. The request is
  held before mounted End Turn, released only after the accepted terminal head
  and visual drain, and must complete afterward as exact HTTP 200
  `terminal_retained`. No request may start after head acceptance. Two
  unchanged-source runs independently return exact final identity and frontier
  828/33, `matches=true`, with the complete Fireball/death/terminal chain,
  backlog zero, WebGL zero, and zero coverage, diagnostics, page, console,
  HTTP, or teardown faults. Their JSON/PNG hashes are respectively
  `82ebfca7dbc5cfe56a689b487fa115b05bc4f0c4abbeb2838a940116ac789487` /
  `ce493e28029b9e59086144411fff0163a45b665f90feb8f226ef9545f8b07f92`
  and
  `1757fe9ec6277d8055aa681d8f0090412c6d03d5f01e6b09e7a74ff8b67c3a34` /
  `ce9dd6de9ebcab71e331c16881e15273dc2499a632352285e0935421f6099ea7`.
  The hardened product harness SHA-256 is
  `210f4b2b32989d77e88837792751b3b6effb9f77948fe683fe2f6d56fd98a858`.

### Multi-Step walking phase continuity

- Status: **BACKEND CONTRACT BLOCKED — ARCHITECT REVIEW REQUIRED; NO SOURCE
  MUTATION AUTHORIZED**.
- Confirmed cause: each disclosed PATH Step is a distinct one-edge cue/head;
  the public cue contains no mechanical root correlation, continuation fact,
  or terminal fact. The runtime correctly ends each frame-local spatial clip,
  so the body returns to Idle and restarts at every tile.
- Forbidden workaround: coordinate/timing adjacency or hidden path stitching.
- Proposed next boundary: architect approval of a privacy-safe public tail
  link to only the immediately prior disclosed Movement presentation ID plus a
  minimal explicit body-cycle-end cue. A hidden step severs the link; the wire
  exposes no root ID, path index/count, timing, duration, or hidden coordinate.
  After approval: Python contract,
  mapper, SDK, runtime-host lease, reset/seek/generation fencing, and mounted
  phase-continuity regressions.
- Smallest concrete contract proposal:
  - each committed PATH cue adds nullable
    `body_cycle_predecessor_presentation_id`; the first disclosed fragment is
    null and a compatible next fragment may cite only the immediately prior
    already-delivered Movement cue;
  - a leaf `movement_body_cycle_end` cue contains only `entity_uuid` and
    `tail_movement_presentation_id`; it carries no reason, route/root token,
    coordinate, count, index, duration, or timestamp;
  - the canonical runtime owns the private root-to-public-tail association per
    exact source/generation/perspective. The mapper remains stateless, and the
    accepted journal advances the tail only after append. A filtered Step
    severs the public link; no hidden-step terminator is emitted;
  - SDK journal validation rejects skipped/stale/cross-generation links and a
    terminal that does not cite the current tail. RESET/bootstrap/invalidate,
    entity loss, attachment retirement, replay seek/reset, and host destroy
    clear the body-cycle lease;
  - Neuro's host-owned locomotion session preserves Walking phase only across
    an exact predecessor link. Each spatial head still settles/commits
    independently; null predecessor, explicit end, incompatible cue,
    turn/action/terminal/reset/cancel, or entity loss produces one Idle end;
  - deterministic red/green gates use four one-edge disclosed heads, assert
    one Walking entry, monotonic body phase, no intermediate Idle, four
    independent position/head commits, then one explicit end. A second trace
    with disclosed edge, hidden edge, disclosed edge requires the later cue's
    predecessor to be null and exposes no hidden coordinate/count. Live,
    replay, Studio, reset, seek, and late-generation continuations are all
    separately fenced.

### Reconciliation first-cause evidence

- Status: **FOCUSED GREEN; CANONICAL STORED-COMBAT PRODUCT REPRESENTATIVE
  PENDING**.
- Red: one real ClipQueue head with a missing-entity slide produced intent,
  transaction, and consumer-barrier failures as three unrelated flat roots.
- Correction: the production diagnostics owner freezes one normalized snapshot
  from the real ledger/fault lifecycle. It retains one immutable first failure
  per exact source/generation/perspective/observation head, preserves completed
  siblings, marks issued/materialized descendants as `BLOCKED_BY`, and marks
  never-issued categories as `NOT_MATERIALIZED_DUE_TO` at the nearest real
  identity. It never invokes the planner to synthesize transaction/clip IDs.
  Subscriber, view, and persistence faults remain observational and cannot own
  causal blocked descendants or alter queue/commit/recovery truth.
- Bounds: 12 retained faults and 100 retained head identities; eviction cannot
  orphan the retained first-cause relation. Persisted entries are validated and
  refrozen.
- Owners: `src/render/reconciliationIncident.ts` SHA-256
  `09aa7897251a5f88b808ee036f272909bc1fba1a496c55f1cf1ed80cdef28921`,
  `src/render/presentationDiagnostics.ts` SHA-256
  `ffbac489c79c92b5ce2d73139ded6cbbde035c5c62378da720514a52d8f75aaa`,
  `src/render/presentationLedger.ts` SHA-256
  `e7b5b738de11cee9a4ca73a124fd49e393ce9b715277ca78a9b0463ef84292fc`,
  and `src/ui/reconciliationDiagnosticsPanel.ts` SHA-256
  `9a6203d29097947661619d7ae06fc7535d9714d1dd76500de00ffa9a380e8f81`.
- Focused green: one retained normalized snapshot drives the machine-readable
  mounted model, clipboard copy, and downloaded canonical JSON. Structural
  projection equality and byte equality replace the former substring/count
  assertion. `presentation-diagnostics-isolation`,
  `presentation-persistence-cut`, and `subjective-animation-coverage` all pass
  against one owned temporary Vite process; TypeScript is green and the port is
  released. Focused smoke SHA-256:
  `1a570790f7e43d12ef424d98b64917161565ef1596451320eac8d66f223bd5d1`.
- This is not the canonical product representative. Closure still requires an
  immutable server-produced stored combat trace through the mounted public live
  composition root and the separately mounted Studio replay root, with the same
  first-cause/node graph and one frozen JSON/UI value. The current
  `studio-evidence-import` fixture is stale before this boundary (missing the
  required `encounter_terminal` field and carrying retired movement-cue shape)
  and must not be patched to the architect-rejected endpoint heuristic.

### Adjacent confirmed seams

- Best-effort diagnostics subscribers: **FOCUSED GREEN**; throwing subscribers
  are quarantined and cannot change queue admission or settlement.
- Canceled-generation mutation sinks: **FOCUSED GREEN** for transaction-owned
  request-frame continuations and live/replay host invalidation.
- Nonzero/negative grid-origin and pre-try storage failures: no new current
  product defect has yet been established in this stabilization run. Existing
  maintained gates must remain green; a deterministic current red is required
  before expanding production scope.

## Remaining entry-gate work

1. Obtain explicit architecture approval for the held frame-level movement
   settlement authority, then close its Python, generated SDK, runtime, and
   replay integrity boundary without reviving the rejected patch heuristics.
2. Obtain the locomotion contract decision, implement it, and prove mounted
   phase continuity without hidden-path inference.
3. Exercise the fixed first-cause evidence in the canonical stored combat
   product representative together with the remaining spell journeys.
4. Rerun focused backend/SDK/Neuro gates, cold build/check, owned-process
   product journeys, and teardown checks on one immutable cutoff.
5. Request fresh internal, engine-external, and NeuroClient-external reviews of
   this manifest and its exact source hashes.
