"""Cold identities for shared configured body and residue behavior."""

from dnd.body_responses import BodyResponseHandler
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus,
)
from dnd.core.content.registration import behavior_identity, get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.residues import TileResidueCondition


_BODY_BEHAVIORS = (
    (BodyResponseHandler, "trait.body_response", "Body Response",
     "Release authored body material after a qualifying physical injury.",
     ContentDefinitionKind.TRAIT, RuntimeBehaviorKind.TRAIT),
    (TileResidueCondition, "condition.tile.residue", "Tile Residue",
     "Persistent material deposited on a tile.",
     ContentDefinitionKind.CONDITION, RuntimeBehaviorKind.CONDITION),
)

for behavior, content_id, name, description, definition_kind, runtime_kind in _BODY_BEHAVIORS:
    behavior_identity(
        definition_kind=definition_kind, runtime_behavior_kind=runtime_kind,
        pack_id="content.neurodragon", content_id=content_id, version=1,
        descriptor=ContentDescriptorSpec(
            display_name=name, description=description,
            visibility=ContentVisibility.PUBLIC,
            tags=("body_material",),
        ),
        provenance=ContentProvenance(
            primary_source_id="neurodragon.original_b2b3930",
            source_anchor="Body releases and tile residues, September 2026",
            relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
            fidelity=ContentFidelity.PARTIAL,
            review_status=ContentReviewStatus.REVIEWED,
        ),
    )(behavior)

BODY_BEHAVIOR_DECLARATIONS_BY_CLASS = {
    row[0]: get_content_declaration(row[0]) for row in _BODY_BEHAVIORS
}
BODY_BEHAVIOR_DECLARATIONS = tuple(BODY_BEHAVIOR_DECLARATIONS_BY_CLASS.values())
