import * as React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { useSnapshot } from 'valtio';
import { characterStore } from '../../../store/characterStore';

// Update the EntityContext interface to add selectValue
interface ValueDisplayProps {
  value: {
    path: string;
    displayValue: string | number;
    description?: string;
  };
  showTooltip?: boolean;
}

// This component displays a value that can be selected for detailed inspection
const ModifiableValueDisplay: React.FC<ValueDisplayProps> = ({ 
  value, 
  showTooltip = true 
}) => {
  const snap = useSnapshot(characterStore);
  
  if (!snap.character) return null;

  const content = (
    <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
      {showTooltip && value.description ? (
        <Tooltip title={value.description} arrow>
          <Typography>{value.displayValue}</Typography>
        </Tooltip>
      ) : (
        <Typography>{value.displayValue}</Typography>
      )}
    </Box>
  );

  return content;
};

export default React.memo(ModifiableValueDisplay); 