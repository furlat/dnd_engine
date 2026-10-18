# Paused server tests

This lane holds only the catalog cold-start probe, split from the active
architecture test. It is not a native engine test. The persistent-character
equipment-mutation and scenario-deployment files were deleted on 2026-10-17:
their server character directory, game directory and character-build modules
no longer exist (see `agent_docs/STALE_TEST_REPAIR_2026-10-17.md`).

Run explicitly with the project environment:

```sh
python -m pytest tests/paused_server
```

Known blocker: the probe's subprocess imports `server.spell_catalog`, which now
exists only under `server_obsolete/`. No skip, xfail or automatic collection
filter hides this failure. `pytest tests` still includes this lane.

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
