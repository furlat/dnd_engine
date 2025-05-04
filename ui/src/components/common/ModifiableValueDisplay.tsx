import * as React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { useEntity } from '../../contexts/EntityContext';

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
  // Use a dummy implementation since selectValue doesn't exist in EntityContext yet
  const handleClick = () => {
    console.log(`Selecting value path: ${value.path}`);
    // In a full implementation, this would call context.selectValue(value.path)
  };

  const content = (
    <Box 
      component="span" 
      onClick={handleClick}
      sx={{ 
        cursor: 'pointer',
        '&:hover': { textDecoration: 'underline' }
      }}
    >
      {value.displayValue}
    </Box>
  );

  if (showTooltip && value.description) {
    return (
      <Tooltip title={`${value.description} (click to inspect)`} arrow>
        {content}
      </Tooltip>
    );
  }

  return content;
};

export default ModifiableValueDisplay; 