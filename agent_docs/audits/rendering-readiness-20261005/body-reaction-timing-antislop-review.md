# Body, equipment, reaction and interruption timing review

Independent source review of body_action.py, compile_equipment in animation.py, choreography joins/child gates, interruption.py and timing_evidence fraction/translation support.

Verdict: accepted after two provenance corrections, verified in current source:
- Forced displacement child gating now references the producer's contact anchor at travel_end_ms, rather than an unproduced arrival alias.
- Multi-application cast interruption candidates retain each delivery application_id on launch/contact inputs, preserving which projectile contributes the minimum cutoff.

Existing equations remain unchanged. Body joins use actual descendant ends and selected recovery duration; equipment preserves separate frame commit and completion, including reversed playback and disabled body. Reaction alignment records its existing maximum and translates cue evidence with cue clocks. Interrupted timelines retain prefix/cutoff evidence rather than falsely claiming full delivery happened. Fraction is a passive representation of existing endpoint interpolation; consumers validate it and do not schedule from it. Child injury/HP versus presentation-start distinctions remain intact.

Some references are explicitly external measured anchors, including initial body joins and old completion values, rather than fully linked local producers. This is honest bounded evidence, not global causal closure. No extra scheduler or gameplay branch introduced. Runtime verification belongs to the implementer's focused suite. Remaining producers are enumerated in timing-final-producer-gaps.md.
