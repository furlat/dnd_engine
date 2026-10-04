# Packet 5 native implementation handoff — 2026-10-04

Implementation checkpoint, not independent approval. Scope is the approved
Spirit Guardians, Guardian of Faith and Heroes' Feast native sections in
`dnd/spells/conjuration.py`; no presentation or artwork changes.

- Spirit Guardians retains exact source memberships, explicit visible cast-time
  exclusions, radiant/necrotic choice, 100-round concentration and native
  3d8/+1d8 scaling. Appearance and aura movement update slow immediately without
  inventing entry damage. Actual first entry per turn and turn-start damage
  remain separate. Both discovery and direct cast facts carry the chosen energy.
- Guardian materializes its existing object with a Large 2x2 footprint within
  30 feet. The existing support-distance query determines its 10-foot reach.
  Movement within reach triggers once per turn; creation/standing does not.
  Stored source/DC/faction survive caster absence. Its budget consumes exact
  linked committed DamageApplied facts including temporary HP and defenses;
  the final hit can exceed the 60-point threshold. Expiry uses the world clock.
- Feast uses existing paid item use and charge admission, exact once-per-creature
  receipts, twelve guest servings plus the caster's serving, and a ten-world-round
  prop lifetime. Destroying/expiring the prop leaves eaten benefits intact.
  Each serving owns an independent ten-recipient-turn condition. The existing
  shared-child ownership graph selects the strongest/latest HP contribution;
  expiry and owner changes preserve/clamp normal HP without healing again.
  Poison/disease cleanup, poison damage immunity, Poisoned/Frightened immunity
  and Wisdom-save advantage retain exact ordinary ownership.

Evidence:

- `/tmp/dnd-holy-combined2.log`: 35 passed in 11.93s. Includes the new public
  native command/event cases, relevant existing spell-family/direct-object/cleric
  cases, and the existing anchored-condition input suite.
- `/tmp/dnd-holy-metadata-final.log`: final energy-metadata change, both choices,
  2 passed in 1.30s.
- `/tmp/dnd-holy-type-final2.log`: production `conjuration.py` typing, zero errors
  and zero warnings.
- New cases: `tests/engine/test_spell_handoff_holy.py`. Four existing fixture
  sections were corrected for the approved explicit ally exclusion, Guardian
  30-foot range/Large footprint and native deterministic Feast dice.

Antimagic contribution suspension is the following packet's explicit native
acceptance dependency. No suppressed-state round trip is claimed here.
Independent review remains required.
