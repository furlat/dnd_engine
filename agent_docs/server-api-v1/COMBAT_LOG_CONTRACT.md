# Type the combat log at its existing source

Status: implementation design, not a claim that the native log is already typed.
This is part of the server contract preparation. No second log service, event bus,
formatter, SDK game reducer or server-side gameplay DTO is introduced.

## The defect

`dnd/core/combat_log.py` already defines attack, movement, saving-throw, spell-save,
interruption, check, damage, healing, action, turn and roll-modification payloads.
Producers immediately dump them to dictionaries, and `CombatLogEntry.data` accepts
`Dict[str, Any]`. Several other producers construct dictionaries directly. The
subjective projector removes keys and creates partial movement summaries. Thus an
export of the outer type does not describe the actual log contract.

The log supplements existing event facts with the actual recorded dice and modifier
evidence. It is not the source of movement, HP, condition or equipment state and
must not be promoted into a replacement event system. Facts and logs refer to the
same recorded occurrences. No consumer rolls dice or calculates a replacement
outcome from display text.

## One ownership path

1. Existing native producers construct their existing `*LogData` value, with a
   literal discriminator. Add passive payload records beside those models only
   for genuinely untyped producer branches. Reuse `DiceRollDisplay`,
   `DamageRollDisplay`, `ModifierBreakdown`, native enums and coordinate types.
2. `CombatLogEntry.data` becomes the closed union listed in the schema. The outer
   `entry_type` remains the presentation category. Its allowed `data.kind` values
   are checked by the exported compatibility table; they are not always identical
   (death saves are saving throws, for example).
3. `dnd/subjective_combat_log.py` remains the sole subjective log projection owner.
   Replace its unrestricted dictionary walking with finite typed handling. A
   complete source payload and an admitted payload use the same records, with
   explicit omission permissions. Native producers must still supply required
   identities/locations before projection; omission is not a producer shortcut.
4. Existing formatters render admitted values. Update `game/player_projection.py`
   `_action_log` at the same time. Neither it nor a server route may continue
   assuming arbitrary `.get()`, `.items()` or `dict(data)` payloads.
5. Export those types to the public schema. Standalone SDK declarations are
   generated from that schema; they are not independently authored log models.
   Construct/project once, encode once. Store and stream those exact encoded bytes.
   Validation at an untrusted client boundary does not imply decode/re-encode at
   every trusted hop.

The design-time `contract_source.py` overlay specifies these changes before runtime
implementation. It is never imported by gameplay, HTTP handlers or SDKs. During
implementation replace the overlays with schema exports from the source owners,
require exact parity, then retire the overlay logic. Keeping it as a second
schema implementation is a failed acceptance criterion.

## Payloads to close

The exact field shapes and category compatibility are in
[player-api-v1.schema.json](player-api-v1.schema.json); privacy omissions are the
explicit `LOG_OMISSIONS` table in the authoring source, not a suffix heuristic.

Existing typed records: attack; ordinary movement; saving throw; spell save;
spell interruption; skill check; damage taken; heal; generic action; turn;
multi-target summary; ordered roll modification. Entity-spotted and hazard-detected
records exist but have no identified production producer; their declared support
must not be described as a successful gameplay capture.

Previously dictionary-only branches: empty condition/action payload; condition
removal; death; spell damage; death save; shove; individual movement step; forced
movement; jump; traversal connector; observed/partially observed movement;
unlocated movement; unknown moving source; spatial-effect lifecycle and interaction.
These are data variants, not executors, class hierarchies or per-spell adapters.
An empty payload is the literal `empty` variant and is allowed only for the
existing action/condition-application categories, not a fallback for unknown types.

## Privacy semantics

- Missing admitted identity means the source identity was withheld. Existing outer
  log identity convention remains `""` for an unknown source/target UUID and
  `"Unknown"` for its display name; null target means there was no target.
- Hidden UUIDs, exact positions, event ancestry and item/provider identities are
  never inferred from names, fetched from the current engine, or reconstructed in
  an SDK. Last-known identities stay known after death or leaving view.
- Coordinates and direction vectors are distinct fields. A direction is not
  removed merely because its two integers equal a hidden map coordinate.
- Full movement path/cost is available to the controlled mover or when that whole
  path was observed. Partial foreign movement uses observed path segments and
  their recorded costs; it cannot retain total hidden route length. Unknown source
  and known-but-unlocated movement are separate finite summaries. An undisclosed
  connector identity causes a partial/unlocated summary, not a fake connector.
- Step index is within the disclosed segment. The `detailed` string must not retain
  the native `(step i / total)` after the structured index is remapped. Omit a total
  unless the whole path is admitted. Spatial summaries count admitted cells, not
  the native footprint. Format these from the admitted typed data in the existing
  formatter, preserving recorded numbers; do not run a second combat calculation.
- Visible damage from a hidden source remains visible damage. Provenance is absent
  or unknown; it does not justify publishing the hidden attack, source equipment,
  target list or intermediate path.
- `perceiver_uuids`, `revealed_entity_uuids` and the event-time grant maps are native
  admission evidence and excluded from outgoing serialization.

## Multi-target detail and ordering

Keep ordered `sub_entries` as the only detailed child tree. Remove
`MultiEntityLogData.per_target_logs`, which copies child dictionaries.

This is not permission to count every child as a target. The current native
summary chooses targeted action/attack/heal/spell-damage/spell-save children;
cleanup and auxiliary children can also be present. The current subjective summary
instead counts all admitted children, which is a separate defect.

Put one pure target-summary selection helper beside the log models. It takes only
admitted log entries and the original target-effect membership captured by the
native producer. Preserve application order and repetitions (A/B/A is three
applications, not two unique display names). Use an explicit tuple of target child
entry indices in the multi-target payload when auxiliary children coexist; these
indices reference `sub_entries` and do not copy payloads. They are distinct,
in range, and in application order: repeating a target uses different child
entries, while repeating the same child index is invalid. The projector filters and
renumbers the indices as it admits children. Counts, damage and saves are summed
only from those entries' already recorded results. Unknown target identity does
not erase an observed hit; an entirely unobserved target contributes nothing.
No objective target count or positional hole is sent to signal withheld targets.

## Door-edge opportunity attack and retained identity

H19 explicitly starts with an identified opponent beside a doorway. Movement
triggers an opportunity attack at the edge of sight; lethal damage is observed,
then a sensory update loses contact before turn-end formatting. The known actor
identity and observed death survive that update. The turn-end refers to that same
actor, not “Unknown”, and the log/reducer must agree after cold replay.

Use retained event-time identity plus prior admitted knowledge, never the latest
visible-entity list or a live lookup after the victim was removed. A paired
nonlethal exit must retain the name without disclosing the hidden destination; a
paired unobserved death must not announce death just because the engine knows it.
Party member switching must not alter any of those results.

## Bounded implementation and verification

The production change stays in existing log models, their current producers,
subjective projection, formatting and direct consumers. Add no API-specific
sanitizer or conversion registry. Update all dictionary consumers in this same
change so typed records cannot accidentally bypass privacy filtering.

Required regressions use real producers: attack hit/miss/critical and opportunity
attack; save/damage adjustment and roll replacement; repeated A/B/A applications;
auxiliary child removal; known killed actor's turn end; movement/jump/connector
with a hidden prefix; wholly hidden movement; spatial partial footprint; hidden
source damage; condition apply/remove; death/death-save/recovery; spell interruption.
Validate both complete source records and projected records. Reject unknown tags,
wrong category/tag combinations and forbidden properties. Assert no loss or
recalculation of dice/modifiers. Opposing views must not gain each other's private
identities/counters/text. These regressions use the existing capture and reduction
owners; server/SDK acceptance later exercises the same values through HTTP/SSE.
