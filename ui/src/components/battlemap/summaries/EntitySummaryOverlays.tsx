import React, { useCallback } from 'react';
import { Box } from '@mui/material';
import { useSnapshot } from 'valtio';
import { battlemapStore } from '../../../store';
import { useEntitySelection } from '../../../hooks/battlemap';
import EntitySummaryBar from '../EntitySummaryBar';

/**
 * Component that renders overlays for selected/hovered entities
 */
const EntitySummaryOverlays: React.FC = () => {
  const snap = useSnapshot(battlemapStore);
  const { selectedEntityId } = useEntitySelection();
  
  // Get the selected entity
  const selectedEntity = selectedEntityId 
    ? snap.entities.summaries[selectedEntityId] 
    : undefined;
  
  // Calculate screen position for summary overlay
  const calculatePosition = useCallback(() => {
    if (!selectedEntity) return { top: 0, left: 0 };
    
    // For now, position at the top of the screen
    return {
      top: 16,
      left: 16
    };
  }, [selectedEntity]);
  
  if (!selectedEntity) return null;
  
  const position = calculatePosition();
  
  return (
    <Box
      sx={{
        position: 'absolute',
        top: position.top,
        left: position.left,
        zIndex: 10,
        pointerEvents: 'none', // Allow clicks to pass through
      }}
    >
      <EntitySummaryBar entity={selectedEntity} />
    </Box>
  );
};

export default EntitySummaryOverlays; 