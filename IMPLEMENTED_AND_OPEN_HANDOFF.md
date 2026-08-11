# Bugs and Fixes

| Bug | What was wrong | What was actually fixed |
|---|---|---|
| BUG-001 | One failed presentation head could block everything queued behind it. | **Not fixed generally.** One concrete cause, BUG-013, was fixed. |
| BUG-002 | Death/result visuals could appear to reorder after an earlier blocked or missing head. | **Not fixed independently.** |
| BUG-003 | A fatal spell root could lose its disclosure authority before completion, hiding the spell cue. | **Fixed.** Replication now retains bounded spell-root projection context; the fatal Fireball path was demonstrated. |
| BUG-004 | Remembered corpses in subjective state caused false objective/subjective parity failures. | **Partially fixed.** Diagnostic parity now filters both sides to the same authority scope. |
| BUG-005 | The Fire Bolt atlas exceeded the browser GPU texture limit. | **Fixed.** Fire Bolt was repacked and assets are size-checked before GPU upload. |
| BUG-006 | Presentation recovery could erase the last committed scene. | **Partially fixed.** Scene preservation/reuse code exists; the complete real recovery journey was not finished. |
| BUG-007 | Turn End and some actions had missing or weak visual feedback. | **Not fixed generally.** Specific spell and item feedback improved. |
| BUG-008 | Haste Potion used a generic Taunt presentation instead of meaningful potion/Haste feedback. | **Fixed.** Authored Haste overlay and semantic feedback were added. |
| BUG-009 | Walking animation stopped and restarted at every tile of a multi-step path. | **Not fixed.** |
| BUG-010 | A visible entity could change position without a matching movement cue. | **Partially fixed.** Lawfully disclosed Steps now receive cues, but final settlement remains unresolved. |
| BUG-011 | Movement cues were not contractually tied to the entity's final position after later movement or relocation. | **Not fixed.** |
| BUG-012 | Acid Splash's one-or-two-target cardinality was ambiguous across the stack. | **Partially fixed.** One-target and two-target UI/product flows work; the public cardinality model remains ambiguous. |
| BUG-013 | Authored intent cloning discarded existing presentation-disposition evidence. | **Fixed.** Replacement intents retain the original evidence. |
| BUG-014 | Arena Water could render as ordinary floor material. | **Fixed.** Arena Water uses the canonical water factory and `water.png`. |
| BUG-015 | The canonical Sorcerer build omitted Invisibility. | **Fixed.** Invisibility was added and exposed through persistence and AvailableActions. |
| BUG-016 | The TypeScript SDK rejected lawful position-only spatial effects with no entity target. | **Fixed.** Python, SDK and client accept position-only effects; producers attach position evidence. |
| BUG-017 | Reconciliation diagnostics flattened causes and downstream symptoms into unrelated faults. | **Partially fixed.** A first-cause/blocked-descendant graph exists; full stored-combat product proof was not completed. |
| BUG-018 | Diagnostic mapping results could directly control gameplay head admission. | **Partially fixed.** Diagnostic/subscriber isolation was improved, but no final full-cutoff proof closed every path. |
| BUG-019 | An in-flight parity request could fail when the terminal player partition was retired. | **Fixed.** Terminal parity is retained as an immutable typed result. |
| BUG-020 | Canceled or replaced generations could still run delayed visual mutations. | **Partially fixed.** Transaction RAF callbacks and host invalidation are fenced; not every delayed mutation sink is covered. |
| BUG-021 | Nonzero or negative map origins could disagree across grid, light and camera consumers. | **Not fixed.** |
| BUG-022 | Browser-storage failure could occur before startup's recoverable error boundary. | **Partially fixed.** A bounded startup-storage recovery correction was added. |
| BUG-023 | Invalid or stale stored directory identity could break startup. | **Partially fixed.** Quarantine/clearing paths were added; not every storage/identity failure mode was closed. |
| BUG-024 | Deferred replication responses risked losing their typed reason code. | **Already working.** Producer, endpoint and SDK were aligned; no substantive fix was needed. |
| BUG-025 | Player-facing game creation could be abused to create AI/Codex administrative simulations. | **Partially fixed.** Gateway authorization now separates player games from administrative simulation; final browser proof remained pending. |
| BUG-026 | Multi-target spells rolled damage separately for each target instead of sharing one execution roll. | **Fixed.** Execution-scoped shared damage-roll packets were implemented across the maintained family. |
| BUG-027 | Typed connector kinds reached the client but rendered as one generic line/traversal type. | **Not fixed.** |
| BUG-028 | Action Studio could not author or simulate connector traversal. | **Not fixed.** |
| BUG-029 | The cold Rolling test used an obsolete Jump intent and never reached the behavior it claimed to test. | **Test fixed only.** The fixture/readiness test was corrected; no product behavior changed. |
| BUG-030 | Studio browser tests assumed the correct tab/workspace was already open. | **Not fixed.** |
| BUG-031 | Async `waitForFunction` predicates could pass on a truthy Promise before the resolved condition became true. | **Partially fixed.** Eight waits were corrected; ten remain: three inventory-panel and seven multi-character-live waits. |
| BUG-032 | Browser tests could reuse unrelated services already running on default ports. | **Not fixed generally.** Some individual tests gained owned-process handling. |
| BUG-033 | RAF/timer callbacks could outlive their transaction or rendering generation. | **Partially fixed.** Transaction RAF work is leased/fenced; general timers remain uncovered. |
| BUG-034 | The Events/Combat Log sidebar risked becoming gameplay authority instead of diagnostics. | **Already guarded.** It remains diagnostics-only. |

## Totals

- Fixed: BUG-003, BUG-005, BUG-008, BUG-013, BUG-014, BUG-015, BUG-016, BUG-019, BUG-026.
- Partially fixed: BUG-004, BUG-006, BUG-010, BUG-012, BUG-017, BUG-018, BUG-020, BUG-022, BUG-023, BUG-025, BUG-031, BUG-033.
- Not fixed: BUG-001, BUG-002, BUG-007, BUG-009, BUG-011, BUG-021, BUG-027, BUG-028, BUG-030, BUG-032.
- Test-only fix: BUG-029.
- Already guarded: BUG-024, BUG-034.
