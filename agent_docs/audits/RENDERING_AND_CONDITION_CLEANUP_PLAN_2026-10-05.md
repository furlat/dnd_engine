# Rendering and condition cleanup: proposed implementation

Scope: follow-up to [the codebase review](CODEBASE_INTEGRITY_REVIEW_2026-10-05.md),
using current code, including committed code. This is a proposal, not an
implementation receipt. Production is unchanged by this review.

**Implementation scope approved afterward:** only Steps 1 and 2 (condition and
rendering-material fixes). Steps 3–5 are deferred. The user requires a separate
broader discussion before general `/game` changes; AI and schema work are not
part of this implementation. See the scoped acceptance report for results.

## Decisions from the user

- Review `/game` broadly, especially material composition, authored spell data,
  boundaries and the types needed for eventual client portability.
- Treat Antimagic failures as a cause/classification/lifetime consistency issue.
- Fix the demonstrated AI publication defect in a bounded change; broader AI
  redesign gets a separate plan.
- Defer F05 (negative target-list indices). These are not negative world
  coordinates. No restriction on world coordinates is proposed.
- No new content, artwork, rules, server work or cross-chat coordination.

## What already works structurally

The client is not a collection of independent spell renderers. Preserve this
existing flow:

1. `presentation.py` detaches received native events; `player_facts.py` supplies
   passive subjective facts. The renderer must not regain access to live entities.
2. `animation_data.py` admits authored recipes, rigs, media and contexts.
3. Motion/choreography binding turns facts plus recipes into timelines. This is
   where release, impact, formation and removal timing belong.
4. `body_presentation.py` samples body poses; `playback_frame.py` combines bodies,
   conditions, world transitions, attachments and feedback at a presentation date.
5. `animation_draw.py` and specialized draw modules turn sampled data into raster
   commands; spatial composition retains its existing visibility/depth rules.

The problems are duplicated admission and implicit composition precedence, not
the absence of a registry. Preserve recipes, timeline samplers and the existing
subjective event boundary. Do not invent a generic event scripting language.

## Step 1: spell causes and suppression deadlines

Owners: existing condition tags/contribution gates, `dnd/spells/abjuration.py`,
`evocation.py`, and the current expiry helper.

- Fix Shield's existing turn-start expiry to execute while suppressed.
- Classify Guiding Bolt's mark as magical, and fix its deadline in the same change.
- Inventory other spell-installed conditions by cause, magical classification,
  gameplay contributions, deadline, consumption and suppression behavior. A
  lingering consequence of magic is not automatically an ongoing magical effect.
- Reuse the existing source-turn helper only for matching semantics. Moving it
  to a neutral spell utility is acceptable if the import DAG stays acyclic.
  Shield's target turn-start and summoning's interval/world clock are distinct.
- Suppression stops benefits/effects; it must not silently pause elapsed time.
  Consumption is a separate decision: an inactive benefit must not consume itself
  merely because an unrelated action occurred.

Acceptance: native cast/application, enter field, deadline inside field, leave
field; no reactivation after expiry. Also verify ordinary expiry and consumption,
overlapping suppression sources, and an effect that legitimately resumes before
expiry. No spell-name checks in Antimagic.

The independent backend sweep identified these additional bounded corrections:

| Effect | Gap and implementation owner |
| --- | --- |
| No Healing | `necromancy.py:129–159` writes an unowned healing-blocked boolean. Make the contribution owner-scoped and suppression-aware through the authoritative `Health.is_healing_blocked()` query; preserve any baseline flag. |
| Light | `evocation.py:4314–4320` omits the light's condition owner. Supply the existing `contribution_owner_uuid` so existing grid light suppression works. |
| Continual Flame | Its light has ownership, but the condition lacks magical classification at class and construction. Correct the tag. |
| Regenerate | Missing magical classification; healing and duration counting share one handler. Separate elapsed lifetime from gated healing without changing authored duration. |
| Command | Suppression postpones next-turn bookkeeping and can execute the command on a later turn. Advance target-turn deadline bookkeeping while keeping commanded behavior suppressed. |

Evidence limits: the reviewer exercised No Healing, Light, Regenerate
classification and Command using ordinary condition installation followed by a
real Antimagic cast, not full originating spell casts. Continual Flame is
source-confirmed. Full originating-spell cases belong to implementation acceptance.

Move the existing source-turn helper to `dnd/spells/spell_utils.py` if sharing is
needed; school modules may import that utility, never the reverse. Keep Command's
target-turn and Regenerate's healing bookkeeping explicit. Do not enable every
handler during suppression: damage, healing and commanded actions remain gated;
repeat-save semantics must be checked individually. Preserve Haste's existing
owner-gated entitlement, without removal/regrant or suppression-induced lethargy.

## Step 2: make material composition independent of caching

Owners: `animation_draw.py`, `condition_draw.py`, `item_effects.py`, existing
`ConditionAppearance` and `ConditionItemModifier`.

Current bug: `_ramp_image` drops `item_modifiers` only for cached ramp kinds.
Equipment is explicitly part of `CONDITION_BODY_SLOTS`; simply drawing equipment
outside the ramp would change established semantics and is not the fix.

Preserve the ordinary path's order: source pixels -> item palette/material and
item-owned modifiers -> applicable body material -> existing finite effects and
compositing. Keep shadows and independent casting layers under their existing
separate rules. Hit-flash overrides remain deliberate and temporary.

Implementation: keep the static row cache for genuinely static inputs. When
item-owned modifiers affect a ramped slot, compose that sampled frame with its
current modifiers/time and then apply the same ramp. First use this bounded
uncached path; only optimize it if measurement shows a need. Never add continuous
time to a growing cache key. Do not create a second item-material implementation.

Put effective item-modifier selection beside `item_material`, not in a second
renderer filter. Static cache keys must include the complete relevant immutable
material value, rather than a manually maintained subset of fields.

Also reconcile admitted ramp modes with their evaluator: only two modes currently
bypass row caching, whereas other admitted modes use age/strength or require a
normal texture. This is a contract gap, not a proven shipped persistent-scene bug.
Centralize mapping-specific sampling/cache eligibility in `condition_draw.py`.
Cache only proven static modes; pass required inputs to the existing frame
evaluator for supported dynamic modes. Reject unsupported persistent combinations
at admission rather than silently rendering them incorrectly. No new shader
framework or material subclasses.

Document precedence next to the existing composition functions. Existing types
already carry item identity, modifier, ramp, strength and time; this defect does
not justify a new material graph or condition type.

Acceptance: native Stoneskin + Shillelagh, Petrified with equipment, Barkskin as
the existing dynamic-path comparison; multiple dates, modifier removal, ramp
removal, flash recovery, main/offhand and fixed/modular rigs where supported.
Compare cached and uncached static results and retain bounded cache checks.
Check each admitted persistent mapping either executes with all required inputs
or is explicitly rejected. Offline spell-palette baking remains separate from
runtime item-owned material composition.

## Step 3: one presentation admission path

Owners: duplicated blocks in `encounter_play.py` and
`devtools/animation_review/record.py`; existing bind/load/register functions.

Extract their shared preparation into an ordinary `game` function with explicit
inputs and a passive result: bound motion/choreography, loaded media references,
updated lifetime maps, feedback/motion cues, retained body history and gaps.
Both callers invoke it. The function must not own a clock, event queue, renderer
loop or recording policy. Recorder assertions, trace export and frame pacing stay
in devtools; interactive input/pause policy stays in live play.

Use `walk_bound_timelines` for body-history traversal instead of a second recursive
walk. Preserve body-history cut policy. Do not collapse distinct condition,
construction, spatial and concentration lifetime models into one universal timer.

Acceptance: the same retained input and presentation dates produce matching
admission results in live and recorded paths, including nested reactions,
condition removal, item transfer, construction and delayed spatial commits.

## Step 4: contract completeness and `/game` boundaries

Export the existing missing authored contracts: condition-media documents,
projectile storage/assets, body-action recipes, movement/interruption presentation
and attack-profile documents. Check representative admitted JSON against exports;
replace the schema test's fixed count with actual contract coverage.

Keep three type responsibilities distinct:

- Wire facts: serializable subjective observations, without native executable data.
- Authored records: validated recipe/media/motion data with explicit units and
  references, exportable without Pygame or asset loading.
- Bound/sampled results: passive internal timelines/poses; raster surfaces belong
  only to loading/drawing, not serialized facts or authored records.

Before adding any field, show the missing information and its authoritative owner.
Do not duplicate an existing authored field in an event or infer it from spell
names. Missing schema exports do not require replacement runtime types.

Broader design notes: `playback_frame.py` is a large composition coordinator and
`animation_draw.py` combines loading, actor materials and multiple draw families.
Extract cohesive pure helpers only for duplication encountered in the named
steps, preserving call order and dependency direction. Other observations become
design notes, not additional implementation scope. File size alone is not grounds for a rewrite.
Do not reorganize every module or change the event protocol in this pass.

## Step 5: bounded AI ownership fix

At `dnd/ai/runtime/state_projection.py` publication, detach mutable observation
values and nested collections from retained knowledge and earlier publications.
Prefer deep-copying the existing passive observation values for this bounded fix;
do not convert all AI contracts or introduce another world model. Include reused
combat-log containers in the ownership check.

Acceptance: mutate nested entity/object/tile/observer data and logs in a published
world; retained knowledge and previous publications remain unchanged. New observed
events still appear in the next world. Wider policy/decision cleanup is deferred.

## Delivery and review

Each step gets focused behavioral checks, scoped typing and import-DAG validation.
Rendering changes additionally get native visual evidence for composition and
live/recorded equivalence, not another all-spell export. Run the affected complete
test files after integration. Report unrelated failures separately, without
weakening tests or silently updating historical hashes.

Independent anti-slop and ECS/anti-OOP review is required for this plan and final
implementation. Review priorities: no duplicate ownership, passive data, no import
cycles/late imports, no new scheduler, no per-spell rendering workaround, cache
equivalence and unchanged disclosure. Review receipts follow below.

### Review receipts

- Independent client anti-slop reviewer: no ownership/scope blocker; requested
  mapping-aware cache eligibility, complete static keys and limiting helper
  extraction to named steps. All three incorporated.
- Independent backend ECS/anti-OOP reviewer: approved the written plan with no
  blockers; confirmed bounded condition-owner fixes and DAG-safe helper ownership;
  explicitly excluded universal suppression toggles, universal clocks and
  provenance-based magical inference. Final owner cleanup, overlapping suppression
  and effective-state publication still require implementation review.
- These are plan/source reviews, not implementation approval or new test results.
