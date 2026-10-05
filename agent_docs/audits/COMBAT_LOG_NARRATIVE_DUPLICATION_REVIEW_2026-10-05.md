# Combat log / narrative duplication — independent anti-slop review

Date: 2026-10-05. Scope: source review and inspection of existing exported transcripts only. No tests run, production changes, or conversations with other user chats. This review does not inherit the earlier implementation approvals.

## Verdict

**Changes required.** The new code does not duplicate combat execution or create a second event queue. It does duplicate part of mechanical outcome wording ownership, and its flat transcript repeats parent summaries and their child outcomes. The delivered UI is a technical transcript, not the requested procedural English narrative. The useful timing, permitted-data, and selected-animation work should be retained; another registry, event system, or scheduler is not the remedy.

An important correction to the broad accusation: `bind_narrative` at `game/presentation_text.py:494` chooses a projected combat log **or** `fact_text`, not both for one node. The duplication is a maintenance responsibility and aggregation problem, not unconditional double formatting of each event.

## Actual ownership path

1. Native events author combat wording: damage (`dnd/core/events.py:5206`), healing (`:5369`), saves (`:2863`), attacks (`dnd/actions.py:1681`), condition application/removal (`dnd/core/base_conditions.py:187`, `:258`). Conditions can own special application wording (`:441`; Hidden customizes it in `dnd/conditions.py:2437`).
2. Event completion records the generated entry and attaches child entries (`dnd/core/events.py:480–512`, `:587`). `CombatLogEntry` already carries compact/verbose/detailed wording, structured data, participants and child entries (`dnd/core/combat_log.py:548`).
3. `dnd/subjective_combat_log.py:35` projects/sanitizes participants and coordinates, recurses through children, and rebuilds movement/multi-target summaries from permitted children. `game/presentation.py:597` invokes that projection. This is disclosure adaptation, not redundant narrative authoring.
4. `game/player_projection.py:1063` preserves the projected log alongside typed public facts on `PlayerNode`. `_action_log` at `:67` is a narrowly scoped foreign-resource redaction; it is not a general second outcome formatter.
5. `game/presentation_text.py:400` binds text to existing presentation evidence. At `:494` it copies projected wording, or at `:497` invokes its own fact formatter. It adds selected authored gesture/media descriptions and sorts the combined rows.
6. `game/text_replay.py:49` uses the shared binder and those same text functions; `game/narrative_view.py:19` only wraps/draws supplied strings. The encounter panel at `game/encounter_play.py:375–379` shows the timestamped rows. These adapters do not independently generate mechanical outcomes.

## Findings

### P1 — A second mechanical outcome formatter has no clear ownership contract

`game/presentation_text.py:49–211` independently writes damage, healing, saving throws, death saves, life transitions, conditions, actions, attacks, movement and other outcomes. Many already have native wording owners listed above. For example native healing says “heals for … HP” and carries source detail; the fallback says “recovers … HP” with the same text at all three verbosity levels. Native condition formatting can have a condition-specific description, while the fallback at `:105` reconstructs a generic “gains …” string.

`combat_log is None` does not explain why wording is absent. Native default generation can be absent; internal conditions intentionally suppress logs; subjective projection can suppress a log; other facts were designed as state evidence rather than narrative occurrences. The fallback already has local exclusions for INTERNAL conditions, snapshots, requests and state refreshes, showing that absence alone is insufficient policy. This review does **not** establish a hidden-information leak: facts and state are already observer-permitted. It establishes a second place deciding what deserves an outcome sentence and how to say it.

Not every fallback is redundant. Committed object removal, cancellation, permitted condition-state changes and other unworded transitions may legitimately need text coverage. Deleting every fallback without replacing that coverage would lose behavior. The repair is explicit ownership, not hiding the function in a differently named file.

**Smallest correction:** retain the existing combat-log owner for existing mechanical wording. Classify the genuinely unworded public outcomes and intentionally silent facts explicitly; extend the existing outcome/log path for missing outcomes, with passive formatting inputs where necessary. Do not call native event methods or import live entities from the text renderer. Any reusable wording helper belongs below both consumers in the DAG, using existing passive facts/log records; avoid a new content registry or callback hierarchy.

### P1 — Flattening summaries and their details repeats the same outcome in the narrative

`bind_narrative` emits each node's own log (`game/presentation_text.py:493–502`). It correctly avoids traversing `sub_entries`, so it does not recursively print every child twice. However, parent logs already summarize child facts, and both parent and child nodes become independent rows. `narrative_at` at `:516` deduplicates event/phase/component identity only; it cannot recognize summary/detail ownership across different events.

This is visible in existing artifacts, not merely hypothetical:

- `.runtime/shared-presentation-20261005/corpus/nature-produce-hit.json`: “Recipient takes 4 fire” followed by “Caster hits Recipient for 4 damage”. The earlier movement similarly emits individual steps plus the root “moves 10ft” summary.
- `.runtime/shared-presentation-20261005/corpus/electric-lightning-bolt.json`: each target's save and damage are printed, then its combined save/damage application summary, followed by the parent “4 observed targets, 60 observed damage” summary.

The special damage request/result check at `game/presentation_text.py:85–89` correctly covers one resolution pair, but does not solve action/application/outcome aggregation. Repetition can be appropriate in an expandable mechanical log; flattened prose has no such hierarchy.

**Smallest correction:** compose one narrative action from existing root/child/application/resolution identities and retain mechanical detail as optional detail. Track which occurrences a composed sentence covers; preserve each distinct application (including repeated A/B/A missiles), reactions and cancellation. Never deduplicate by matching strings or guessing that equal damage values mean the same hit.

### P1 — The narrative assembly does not produce the requested prose

`game/presentation_text.py:502–512` appends result, gesture and effect rows; `game/encounter_play.py:379` prints each separately with a timestamp. There is no composition connecting actor, meaningful gesture, selected spell effect, target and observed result. Delivery/finite media text is often merely “impact effect at …” or “A visual effect appears …” (`:303–375`), and selecting a spell label is not a description of the visual itself.

This is distinct from outcome duplication. Gesture descriptions from the selected rig (`:219`) are legitimate added information, as are known-state inspection and presentation timing. Removing them would defeat the user's purpose. But adding them to a log does not complete that purpose.

**Smallest correction:** use a pure composition pass in the existing text presentation module over the current permitted action relationships and already selected authored descriptions. Produce readable English/pseudosentences, with optional mechanical detail separated. For example, when actually supported: “Caster extends a hand and releases Produce Flame toward Recipient. The flame strikes, dealing 4 fire damage.” Do not invent a flinch, scream, intention, hidden participant, successful impact or flame appearance from a content ID. When an authored visual description is missing, use a restrained factual sentence rather than asserting generic ‘visual effect’ is complete narrative coverage. Release and result may be separate progressively admitted clauses; do not expose outcomes before existing commit clocks admit them.

### P2 — The exported narrative drops useful composition structure too early

`NarrativeEntry` (`game/presentation_text.py:30–43`) preserves event UUID, source index, timing, phase and component ID, which is useful. But it exports only preformatted strings for meaning, and has no explicit covered child/application occurrences or source/target semantic slots. The binder has the native permitted lineage relationships and facts, but the final transcript does not retain them for a later compositional consumer. The text layer also throws away structured `CombatLogEntry.data` while copying only its three strings (`:494–499`).

**Smallest correction:** perform composition while the existing typed facts and relations are available. If composition must be portable downstream, extend the existing passive narrative record only with the identities/slots actually needed; do not add a second event schema mirroring all gameplay. Keep raw mechanical entries accessible as details/debug evidence.

## Things that are not duplication defects

- Removing display markup (`plain_log_text`) is normal output adaptation.
- Dating text by existing presentation milestones is necessary to keep results from preceding impacts. No separate simulation or scheduler was found here.
- The graphical and headless adapters share `bind_narrative`; the Pygame panel only lays out strings.
- Selected rig/motion descriptions are authored visual semantics, not competing combat rules.
- Inspection of currently known state must remain separate from claims that a condition was just applied.
- Archived repeated “Unknown gains Bloodied” rows have distinct event identities. They must not be merged or assigned an actor from word similarity. Their source quality is a separate issue, not proof that `fact_text` duplicated them.

## Bounded correction and acceptance

1. Establish one owner for mechanical outcome wording; map overlapping fallback branches to existing owners and preserve explicit coverage for truly unworded public transitions.
2. Compose action-level prose using existing permitted lineage/application/resolution identities, selected authored descriptions and current commit timing. Preserve separate repeated hits and interrupting reactions; make mechanical summaries/detail optional rather than repeating them in the prose.
3. Keep graphics binding, world rules and native execution unchanged. Keep timing evidence, headless replay and panel layout.
4. Review real native examples: Produce Flame hit/miss, repeated A/B/A missiles, multi-target Lightning Bolt mixed saves, movement interrupted by reaction, condition application/removal/suppression, canceled cast and observer visibility loss. Check prose for redundant results, invention, early disclosure and lost occurrences. Include a genuinely unworded public transition so cleanup cannot silently delete it.
5. Anti-slop review should verify one wording owner and understandable prose; ECS/DAG review should verify passive records, no live-entity dependency and retained disclosure boundaries. Existing previous approvals are not acceptance for this repair.

No implementation is performed by this review.

## Removal follow-up — supersedes the proposed narrative correction

The user subsequently chose to remove narrative rendering and retain the existing combat log. **The bounded source removal is approved.** This approval is for that changed scope; it does not implement or approve the composition recommendation above.

Independently checked the working tree after removal:

- The four narrative-only runtime modules (`presentation_text`, `presentation_inspection`, `narrative_view`, `text_replay`) are absent. There is no remaining `fact_text`, `bind_narrative`, narrative record, panel, or replay reference in `game`, `devtools`, or tests.
- Schema export retains `presentation-catalog-v1` but no narrative replay schema. Review tracing no longer imports or emits narrative rows; graphical timing/provenance traces remain.
- `game/encounter_play.py` restores the existing `_log_lines` implementation, verified against `HEAD`: it reads only already-projected compact log strings, strips their markup, and retains the prior within-lineage string deduplication. The existing 20-line deque, completion-time logging and last-three-line display are restored. This removal does not redesign that pre-existing log behavior.
- F4 scene/split/narrative switching, text scrolling and split-view camera offsets are absent. Existing F3 debug and mouse-wheel camera behavior remain.
- Surviving uses of the ordinary word “narrative” in scenario comments and old `_log_lines` commentary are not executable remnants of the removed feature.
- Shared presentation binding/retention, timing evidence, catalog export and authored animation descriptions remain. They have graphical or authoring responsibilities independently of the removed text feature.

The duplicated fallback outcome formatter and the new flat narrative transcript identified above are therefore removed rather than relocated. No alternative narrative framework was introduced. Old archived review HTML/transcripts are historical artifacts, not production execution; documentation should make their superseded status clear.

This follow-up is source review only. Root is running the regression checks; no test result is claimed here. No source or test files were changed by this reviewer.

### Removal verification (root)

The affected encounter, interruption, headless binding and schema tests passed
**20 checks**. The recorder regression passed **1 test / 9 recorded cases**.
Full game/review-tool Pyright reports **0 errors, 0 warnings**; `git diff --check`
is clean. No full-suite rerun is claimed for this bounded removal.
