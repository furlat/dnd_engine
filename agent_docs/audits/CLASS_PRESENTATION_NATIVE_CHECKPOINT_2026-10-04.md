# Class presentation native checkpoint — 2026-10-04

Packet 8 now publishes the missing passive facts on existing native owners and events. Class mechanics, action costs, spell-slot transactions and attack routes are unchanged. Class artwork and client bindings remain in progress; this receipt does not approve those unfinished consumers.

- `SavingThrowEvent.indomitable_reroll` records the actual reroll result, with an exact condition UUID only when a retained feature condition exists. Direct progression uses the existing identified class-handler attribution.
- `TakeDamageEvent.relentless_rage` records the actual survival-save result, with an exact condition UUID only when a retained feature condition exists. Direct progression uses the existing class-handler attribution. The client must join this request to its committed damage; neither one remaining HP nor an arbitrary damage reduction proves intervention.
- Survivor fills existing `HealEvent.source_condition_uuid`; its actual healing and original turn-start owner remain authoritative.
- Font conversion uses the existing cost applier, recording actual point/slot deltas, followed by the actual capped gain or restored-slot delta. `ActionFact` discloses direction to an identified observer and numeric amounts only to the acting owner. No additional transaction is emitted.
- `ConditionState.metamagic_mode` carries the closed Quickened/Twinned/Distant selection. Affinity fills existing `energy_type` from its native damage type.
- Draconic Presence exposes its accepted visible field through the ordinary observed-cell spatial snapshot, with a closed awe/fear mode and the already witnessed actor anchor.
- Protection continues to use existing effective reaction attribution. None of these additions fabricates a cast, attack or reaction.

New passive records live in `dnd/types/class_features.py`, which imports only standard-library values and Pydantic. The architecture policy admits the exact senses-to-class-values edge and enforces the new module as a safe leaf.

Validation: **83 passed** across focused class facts and direct Fighter/Barbarian/Sorcerer progression (`/tmp/class-native-final.log`, 5.35s); **21 dependency checks passed** (`/tmp/class-dag.log`); changed native/projection typing **0 errors/warnings** (`/tmp/class-native-types2.log`). Cached environment: `/home/tommaso/.cache/dnd-engine/venv`.

The preliminary test failures were fixture issues: the wrong imported Affinity action class name, a misspelled slot cost identifier, expecting unclamped native normal HP to become zero after overkill, asserting a live reaction budget after native death cleanup, and comparing a set to the senses dictionary instead of its keys. They did not require class-rule changes. Earlier logs are retained. Native edits are frozen for the parent's full active-suite run; any later native change requires an explicit affected rerun.

The later direct-progression audit added four actual installed-handler success/failure cases (18 focused facts passed, `/tmp/class-native-direct4.log`). Indomitable, Survivor and Relentless explicitly retain their existing CLASS_FEATURE handler kind; existing handler evidence now admits that closed kind alongside REACTION under unchanged identification gates. No inferred condition or feature UUID is manufactured. Root separately corrected Mindless Rage cleanse children to use the still-live action parent after Raging commits; native Barbarian28 passes. Independent observer tests use a real Encounter, and Font’s foreign-facing name now discloses direction only, matching its typed payload. Final Retaliation provenance and full-suite reconciliation are recorded by the parent checkpoint.
