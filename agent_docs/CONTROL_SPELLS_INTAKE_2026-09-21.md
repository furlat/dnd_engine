# Received control-spell art handoff

**Superseded intake limitation:** the dedicated `control-spells-review/sleep-sustain-v1/`
package was delivered on September 21 with a seamless 576-frame loop, corrected
face registration and arbitrary-phase removal. Integration is authorized and
tracked in [the execution plan](CONTROL_SPELLS_IMPLEMENTATION_2026-09-21.md).
The initial observations below are historical.

Received after completion of the native typing/Goblin repair. This records the
delivery and initial source inspection; it is not an integration result or an
approved implementation plan. No production files were changed during intake.

Authoritative art brief:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/docs/CONTROL_SPELLS_HANDOFF_2026-09-21.md`.
Selected art root:
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx`.

The batch contains Charm Person/Charmed, Blindness/Blinded,
Deafness/Deafened, Command, Color Spray, Silence and a Sleep Zzz replacement.
Backend implementations already exist in `dnd/spells/enchantment.py`,
`necromancy.py` and `illusion.py`; their presence is not yet evidence that every
required lifecycle fact reaches presentation. Inspect them before proposing
mechanical changes. Existing condition media already support application,
sustained media and removal fading in `game/condition_media.py`.

Integration constraints carried from the brief:

- Consume real condition membership and turn events. Multiple sources retain
  one effective cue until the last contributing source ends. In particular,
  Silence-derived Deafened must coexist with independent Deafness.
- Reuse the existing condition recipe/media owners. Head sockets are authored
  per actor, clip, frame and facing; the supplied sockets belong to the preview
  actor and are not a universal offset. Combined cues and front/back layers
  need ordinary actor/world depth composition.
- Retain the authored 144 Hz sample timeline, page dimensions, bounds and
  full-cell pivots. Preload selected media; do not decode atlas pages per frame.
- Color Spray has eight native directions and genuinely multicolor hands.
  Preserve its selected SE export and current gameplay selection/rule version.
- Command waits for actual turn execution. Grovel's prone state is independent
  of the crest. Preserve backend variants; the art demo's deferred Drop does not
  authorize deleting gameplay behavior.
- Sleep changes only the Zzz layer. Keep the approved cast, projectile, impact,
  palette, fall and wake behavior. The requested small upward/forward adjustment
  remains visually unapproved. The demo clamps at frame 430 and has **no delivered
  seamless sustained Sleep loop**; copying that clamp would introduce a frozen
  persistent effect. Resolve that media requirement before replacing sustained
  production playback.
- Browser demos establish visual intent, not native targeting, movement,
  subjective visibility or causal event timing.

Before implementation, a bounded production plan needs the repository's
anti-slop and anti-OOP reviews, real-event test cases, and four-camera gameplay
review clips. This delivery does not supersede the separately documented stats
snapshot retention defect or imply that defect was repaired.
