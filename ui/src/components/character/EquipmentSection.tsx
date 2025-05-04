import * as React from 'react';
import { Box, Typography, List, ListItem, ListItemText, Divider, Card, CardContent, Chip } from '@mui/material';
import { Character, EquipmentSnapshot } from '../../models/character';
import { SectionProps } from '../common';
import { useEntity } from '../../contexts/EntityContext';

const EquipmentSection: React.FC = () => {
  const { entity } = useEntity();
  const equipment = entity?.equipment;

  if (!equipment) {
    return (
      <Box>
        <Typography variant="h6">Equipment data not available</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Equipment
      </Typography>
      
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Armor Class
          </Typography>
          <Box display="flex" alignItems="center">
            <Typography variant="h4" color="primary">
              {equipment.armor_class}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* In a full implementation, we would show equipment items here */}
      <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
        Equipment details coming in future updates
      </Typography>
    </Box>
  );
};

export default EquipmentSection; 