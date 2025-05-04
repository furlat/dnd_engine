import * as React from 'react';
import { Box, Typography, Card, CardContent, Accordion, AccordionSummary, AccordionDetails, Chip, List, ListItem, ListItemText, Divider } from '@mui/material';
import { useEntity } from '../../contexts/EntityContext';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ModifiableValueSnapshot } from '../../models/character';

const format = (v: number) => `${v}`;

const renderMVChannels = (mv: ModifiableValueSnapshot) => {
  if (!mv || !mv.channels) return null;
  return (
    <List dense disablePadding>
      {mv.channels.map((ch, idx) => (
        <Box key={idx} sx={{ mb: 1 }}>
          <Typography variant="body2" fontWeight="bold">
            {ch.name} – Total: {format(ch.normalized_score)}
          </Typography>
          <List dense disablePadding>
            {ch.value_modifiers.map((mod, i) => (
              <ListItem key={i} dense divider={i < ch.value_modifiers.length - 1}>
                <ListItemText
                  primary={mod.name}
                  secondary={mod.source_entity_name}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
                <Chip label={format(mod.value)} size="small" color={mod.value >= 0 ? 'success' : 'error'} />
              </ListItem>
            ))}
          </List>
        </Box>
      ))}
    </List>
  );
};

const EquipmentSection: React.FC = () => {
  const { entity } = useEntity();
  const equipment = entity?.equipment;
  const acCalc = entity?.ac_calculation;

  if (!equipment) {
    return (
      <Box>
        <Typography variant="h6">Equipment data not available</Typography>
      </Box>
    );
  }

  const bodyArmorName = equipment.body_armor ? equipment.body_armor.name : equipment.unarmored_ac_type;
  const shieldName = equipment.weapon_off_hand && (equipment.weapon_off_hand as any).ac_bonus ? (equipment.weapon_off_hand as any).name : null;

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
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="h4" color="primary">
              {equipment.armor_class ?? '—'}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {bodyArmorName}
              {shieldName ? ` + ${shieldName}` : ''}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Equipped armor/shield list */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Equipped Armor / Shield
          </Typography>
          <List dense>
            <ListItem>
              <ListItemText primary="Body Armor" secondary={bodyArmorName || 'None'} />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText primary="Shield" secondary={shieldName || 'None'} />
            </ListItem>
          </List>
        </CardContent>
      </Card>

      {/* AC Detailed calculation */}
      {acCalc && (
        <Accordion defaultExpanded sx={{ mb: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1">AC Calculation Details</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {/* Show different sections depending on unarmored */}
            {acCalc.is_unarmored ? (
              <>
                {/* Base/unarmored values */}
                {acCalc.unarmored_values && acCalc.unarmored_values.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Base Values</Typography>
                    {acCalc.unarmored_values.map((mv, idx) => (
                      <Box key={idx} sx={{ ml: 2, mt: 1 }}>
                        {renderMVChannels(mv)}
                      </Box>
                    ))}
                  </Box>
                )}

                {/* Ability Bonuses */}
                {acCalc.ability_bonuses && acCalc.ability_bonuses.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Ability Bonuses</Typography>
                    {acCalc.ability_bonuses.map((mv, idx) => (
                      <Box key={idx} sx={{ ml: 2, mt: 1 }}>
                        {renderMVChannels(mv)}
                      </Box>
                    ))}
                  </Box>
                )}

                {/* Ability Modifier Bonuses */}
                {acCalc.ability_modifier_bonuses && acCalc.ability_modifier_bonuses.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Ability Modifier Bonuses</Typography>
                    {acCalc.ability_modifier_bonuses.map((mv, idx) => (
                      <Box key={idx} sx={{ ml: 2, mt: 1 }}>
                        {renderMVChannels(mv)}
                      </Box>
                    ))}
                  </Box>
                )}
              </>
            ) : (
              <>
                {/* Armored values */}
                {acCalc.armored_values && acCalc.armored_values.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Armored Values</Typography>
                    {acCalc.armored_values.map((mv, idx) => (
                      <Box key={idx} sx={{ ml: 2, mt: 1 }}>
                        {renderMVChannels(mv)}
                      </Box>
                    ))}
                  </Box>
                )}
                {/* Combined Dex bonus */}
                {acCalc.combined_dexterity_bonus && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Dexterity Bonus (capped by armor)</Typography>
                    {renderMVChannels(acCalc.combined_dexterity_bonus)}
                  </Box>
                )}
              </>
            )}

            {/* Final total */}
            <Divider sx={{ my: 1 }} />
            <Typography variant="subtitle2">Final AC: {acCalc.final_ac}</Typography>
          </AccordionDetails>
        </Accordion>
      )}

      <Typography variant="body1" color="text.secondary" sx={{ mt: 2 }}>
        Armor and shield details shown above. Additional equipment info coming soon.
      </Typography>
    </Box>
  );
};

export default EquipmentSection; 