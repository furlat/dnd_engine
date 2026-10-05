# Standalone root timing additions

Independent source review of DamageCue timing evidence plumbing, EntityLifecycleCue body-end evidence, retained replay admission UUID, and motion dependency export.

Accepted within scope. Damage binding passes the existing actual contact date into compile_damage's optional passive recorder. Entity lifecycle body_end is precisely the existing bodyFadeMs end (or zero duration), not an invented character animation. Retained dependency records preserve absolute dates and use the admitting root UUID to distinguish snapshots. Motion exports add enclosing visit offsets, with locally recorded indices unchanged.

No source/clip invention or playback change found. Compile_damage completion operands and remaining movement/life producers are reviewed separately when complete; this receipt does not approve unfinished coverage.
