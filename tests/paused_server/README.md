# Paused server tests

This lane has no executable tests. Its final catalog cold-start probe was
removed on 2026-10-19 because `server.spell_catalog` and its obsolete server
package have been retired. The active native-and-extension cold-start contract is
covered by `tests/architecture/test_spell_catalog_composition.py`, which
checks native Fire Bolt and extension Aegis Spark through the current content
bootstrap in a fresh process.

The persistent-character
equipment-mutation and scenario-deployment files were deleted on 2026-10-17:
their server character directory, game directory and character-build modules
no longer exist (see `agent_docs/STALE_TEST_REPAIR_2026-10-17.md`).

Active acceptance commands:

```sh
python -m pytest tests/engine tests/ai tests/progression
python -m pytest tests/architecture
python -m pytest tests/game
python -m pytest tests/test_*.py
```

Active durable-record and composition coverage lives in
`tests/progression/test_direct_item_durable_and_proficiency.py` and
`tests/progression/test_direct_character_builds.py`; native equipment transfer
and mutation remain under `tests/engine`. These do not certify the paused
server's persistent character directory.
