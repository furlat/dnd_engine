# Debuff overhead marker audit

Scope: current registered condition-backed behaviors and core standard conditions,
not the old spell gallery alone. Full identity/layer inventory is in
[CONDITION_MARKER_INVENTORY_2026-10-05.json](CONDITION_MARKER_INVENTORY_2026-10-05.json).
An attachment or a body animation is not automatically a readable status symbol.
This is a production ownership/data audit; final artwork acceptance requires clips.


## October 5 steady-marker integration update

The original gaps below are now covered by thirteen delivered still glyphs plus
reused Incapacitated/Life Drain symbols, except Ray of Frost's missing recipient
projection. Mark Target's rejected crimson reticle is unbound. Existing body VFX
are preserved. Only overhead symbols cycle; their source pixels do not animate.

Explicit Unconscious membership has its symbol; native dying/stable life states
do not automatically create that condition and have not been relabeled as such.
The review separates actual spell/recovery triggers from labeled condition fixtures.
See [integration evidence](../DEBUFF_MARKER_INTEGRATION_2026-10-05.md).

## Existing symbols or supplied components

| State family | Current symbol | Ownership / reuse |
| --- | --- | --- |
| Blinded | Existing eye cue | Canonical Blinded; Sunbeam/Sunburst/Color Spray wrappers do not need new icons |
| Deafened | Existing sensory cue | Canonical Deafened, including Silence sources |
| Incapacitated | Pause-like cue | Shared with Hypnotic Pattern; deduplicate the shared symbol |
| Stunned | Existing head cue | Canonical Stunned, including Power Word Stun |
| Restrained | Fetter cue | Canonical restraint and jaw trap share it; Web/Prismatic children retain their body effects |
| Asleep | Existing Zzz | Sleep and Eyebite Asleep share one semantic slot; maintain their lying-down poses |
| Cursed | Existing curse head marks | Four Bestow Curse variants share one slot, while ground/body rings remain |
| Marked target | Rejected crimson reticle, now unbound | Custom ability remains pending user decision |
| No Reactions | Delivered interrupted arrow | Canonical NoReactions; no Incapacitated substitution |
| Guiding Bolt mark | Delivered radiant star | Consumed/expired with native mark |
| Healing blocked | Delivered bone hand/slash | Target-owned NoHealing child; not Chill Touch's caster tracker |
| Life Drain maximum-HP loss | Delivered broken vitality vessel | Actual reduction owner; never shown on saved hit or miss |

The six newly supplied individual marks and shared jaw restraint are authored in
this integration. True Seeing/Darkvision/See Invisibility eyes are sensory VFX,
not debuff symbols and must not silently enter a debuff carousel.

## Original missing overhead symbols / adaptation work (superseded above)

| State | Current presentation | Required work |
| --- | --- | --- |
| Frightened | Ground wisps | New overhead symbol requested by user; applies to Fear and other fear sources |
| Exhaustion | No usable overhead symbol | New overhead symbol requested by user; no pose deformation |
| Poisoned | No dedicated overhead bank | Poison symbol; do not confuse coating on a weapon with a poisoned creature |
| Charmed | Body-attached hearts | Inspect/adapt existing hearts into an overhead cue; no need for unrelated new art |
| Paralyzed | Frozen body pose; Holds may add chains | Distinct paralysis symbol, independent of magical chains |
| Petrified | Stone material and frozen body | Stone/petrification symbol; retain actual material |
| Prone | Lying pose | Compact prone symbol if all debuffs require head markers; never a death icon |
| Unconscious | Lying body state | Distinct unconscious symbol; sleeping Zzz only for actual sleep |
| Bane | Body-attached material | Penalty/bane symbol or overhead adaptation of its existing motif |
| Command Flee/Grovel/Halt | Shared body effect | One commanded symbol; retain the commanded action's distinct mechanics |
| Slow | Body-attached effect | Overhead slow symbol/adaptation; do not duplicate for every slowing source |
| Eyebite Sickened | Ground/body effect | Sickened symbol; separate from the frightened cue |
| Haste Lethargy | No marker; directly owns incapacitation transform | Reuse an explicit exhaustion/incapacitation-like symbol through its own real owner; no imaginary child condition |
| Stinking Cloud Nauseated | No marker | Nausea/retching symbol; shares artist vocabulary with Sickened if appropriate |
| Harm maximum-HP loss | No marker | Reuse delivered vitality-loss vessel through Harm's actual victim-owned condition, with disease distinction in HUD |
| Ray of Frost slowing | Caster-side tracker | Audit target projection before adding a slow symbol; never attach it to caster merely because tracker lives there |
| Spirit Guardians slowing | Target-owned speed penalty | Reuse slow symbol with actual zone entry/exit state |
| Reduce | Scaled body | Optional reduced-size symbol; only Reduce mode, never beneficial Enlarge |

No new rules are required just to supply these symbols. A visual family shared by
several rules does not merge their native condition owners or durations.

## Exclusions and traps in the count

- Grappled is removed by user decision, not a missing-art ticket.
- Wet and all terrain/surface effects are deferred to the separate surfaces pass.
- Area owners (Cloudkill, Silence, Web, walls, etc.) are not creature debuffs by
  themselves. Display their real creature consequences, not a zone-owner badge.
- Banished creatures are absent: do not draw an overhead marker revealing a
  creature that is not currently visible/participating in the scene.
- Spell wrappers and caster-side controllers (Fear, Chill Touch, Blindness/Deafness,
  Divine Word, Power Word Stun, Hold, etc.) do not each need a new marker when
  their actual target child already exposes the state.
- Passive Ghoul Paralysis is an attack capability, not proof its bearer is paralyzed.
- Beneficial Field Focus and Leadership pennants are part of this handoff, but are
  not counted as missing debuffs. Equipped weapon glows are not overhead marks.

## Multiple marks

Only explicitly tagged `markerGroup` layers enter one cycling slot. A semantic
symbol's rear/front components stay together; duplicate owners do not double it.
The stable absolute presentation clock selects a slot every1.8seconds. Body
materials, equipment, ongoing spell volumes, and untagged sensory effects continue.
Retired cues never overlay active symbols; when none remain, the final existing
removal fade may complete. No backend condition or queue is introduced.

Artist follow-up is documentation only: the user forwards it. No artist messages
were sent. This document does not authorize generating replacement artwork.
