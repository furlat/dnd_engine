# Chain Lightning native and selection review — 2026-10-04

Verdict: **approved within the native/target-selection scope after the two
corrections below**. This does not approve unfinished electric media or its
paired-observer presentation acceptance. No production code was edited by this
reviewer; root authorized the appended Antimagic regression.

The engine owns the primary-dependent secondary pool in the existing
AvailableTarget record. Native execution validates that pool and rechecks actual
contacts; AI immutable affordances and the ordinary player menu consume the same
choices. Optional dependent pools preserve ordinary multi-target behavior. The
leaf frozen EffectEndpoint/EffectPropagationLink values carry actual identity,
position, height and application ID through existing ActionEvent/SpellFact
projection. Root owns the original action; applications retain independent
resolution membership, and branch origins are the primary rather than a nearest
previous recipient. There is no new targeting manager, spell dispatcher, native
event executor, frontend radius search, import cycle or late-import workaround
in this reviewed extension.

Findings and resolution:

1. Antimagic checked caster-to-secondary rather than the recorded branch. An
   installed-content probe with caster(2,2), primary(8,2), secondary(8,8) and
   field(5,5) reproduced primary HP220 / secondary HP240 even though both actual
   legs avoided the field. Root changed the shared blocker to consume the typed
   propagation endpoints when present. The appended native regression now proves
   both recipients lose20 HP and the second application retains primary origin.
2. The old non-area projection guard rejected a visible linked application when
   another declared recipient was undisclosed. Root now detects propagated
   applications, filters the declared allocation and gates each actual edge;
   bind_cast accepts sparse unique retained application indices. Read review
   confirms the correction preserves endpoint disclosure. The new paired
   electric fixture/visual acceptance remains root-owned and pending here.

The actor-cast item endpoint correction was also verified: holding a source item
does not replace the caster UUID when cast_origin is actor.

Independent verification: all9 native Chain cases passed in6.43s
(`/tmp/dnd-chain-independent-review.log`). A separate run of player Chain
selection, ordinary controls, Continual Flame presentation and dependency
boundaries passed42 cases in42.47s
(`/tmp/dnd-chain-continual-independent-review.log`). No rendering job or external
chat was used. Continual Flame's separate remaining object-route finding is in
its own review receipt.

Reviewed checkpoint pins (shared files may continue changing in other lanes):
evocation.py `f53b82114527d9b18ed7e43cc6e7d343d1e0f57394aac1f574e43a6b8cd46ec3`;
base_actions.py `f841d551e818c4876773563561b74775a6c2da4cc15b794923b533f46a19c345`;
effect_types.py `eb2e17f0fc5b1af61cb5c3f8418be686c6d78dbe26bcef3fdb000c6f09fba22c`;
player_projection.py `dbf1f6c1f5c403061811594213cb6f5cf106ba27c1f08162e6110af7ac51f2f4`;
controls.py `e862da869482041363d78c028e38639f5db9ee24f99dceac6befaad1b56add77`.
