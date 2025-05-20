import * as React from 'react';
import { Box, Typography, Card, CardContent, Accordion, AccordionSummary, AccordionDetails, Chip, List, ListItem, ListItemText, Divider } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useEquipment } from '../../../hooks/character_sheet/useEquipment';
import type { ReadonlyModifiableValueSnapshot } from '../../../models/readonly';

const EquipmentSection: React.FC = () => {
  const { 
    equipment, 
    acCalculation: acCalc,
    stats,
    renderModifierChannels
  } = useEquipment();

  if (!equipment || !stats) {
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
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="h4" color="primary">
              {stats.armorClass}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {stats.bodyArmorName}
              {stats.shieldName ? ` + ${stats.shieldName}` : ''}
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
              <ListItemText primary="Body Armor" secondary={stats.bodyArmorName || 'None'} />
            </ListItem>
            <Divider />
            <ListItem>
              <ListItemText primary="Shield" secondary={stats.shieldName || 'None'} />
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
                        {renderModifierChannels(mv) && (
                          <List dense disablePadding>
                            <Typography variant="body2" fontWeight="bold">
                              {renderModifierChannels(mv)!.name} – Total: {renderModifierChannels(mv)!.total}
                            </Typography>
                            {renderModifierChannels(mv)!.modifiers.map((mod, i) => (
                              <ListItem key={i} dense divider={i < renderModifierChannels(mv)!.modifiers.length - 1}>
                                <ListItemText
                                  primary={mod.name}
                                  secondary={mod.sourceName}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                  secondaryTypographyProps={{ variant: 'caption' }}
                                />
                                <Chip 
                                  label={mod.value.toString()} 
                                  size="small" 
                                  color={mod.value >= 0 ? 'success' : 'error'} 
                                />
                              </ListItem>
                            ))}
                          </List>
                        )}
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
                        {renderModifierChannels(mv) && (
                          <List dense disablePadding>
                            <Typography variant="body2" fontWeight="bold">
                              {renderModifierChannels(mv)!.name} – Total: {renderModifierChannels(mv)!.total}
                            </Typography>
                            {renderModifierChannels(mv)!.modifiers.map((mod, i) => (
                              <ListItem key={i} dense divider={i < renderModifierChannels(mv)!.modifiers.length - 1}>
                                <ListItemText
                                  primary={mod.name}
                                  secondary={mod.sourceName}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                  secondaryTypographyProps={{ variant: 'caption' }}
                                />
                                <Chip 
                                  label={mod.value.toString()} 
                                  size="small" 
                                  color={mod.value >= 0 ? 'success' : 'error'} 
                                />
                              </ListItem>
                            ))}
                          </List>
                        )}
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
                        {renderModifierChannels(mv) && (
                          <List dense disablePadding>
                            <Typography variant="body2" fontWeight="bold">
                              {renderModifierChannels(mv)!.name} – Total: {renderModifierChannels(mv)!.total}
                            </Typography>
                            {renderModifierChannels(mv)!.modifiers.map((mod, i) => (
                              <ListItem key={i} dense divider={i < renderModifierChannels(mv)!.modifiers.length - 1}>
                                <ListItemText
                                  primary={mod.name}
                                  secondary={mod.sourceName}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                  secondaryTypographyProps={{ variant: 'caption' }}
                                />
                                <Chip 
                                  label={mod.value.toString()} 
                                  size="small" 
                                  color={mod.value >= 0 ? 'success' : 'error'} 
                                />
                              </ListItem>
                            ))}
                          </List>
                        )}
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
                        {renderModifierChannels(mv) && (
                          <List dense disablePadding>
                            <Typography variant="body2" fontWeight="bold">
                              {renderModifierChannels(mv)!.name} – Total: {renderModifierChannels(mv)!.total}
                            </Typography>
                            {renderModifierChannels(mv)!.modifiers.map((mod, i) => (
                              <ListItem key={i} dense divider={i < renderModifierChannels(mv)!.modifiers.length - 1}>
                                <ListItemText
                                  primary={mod.name}
                                  secondary={mod.sourceName}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                  secondaryTypographyProps={{ variant: 'caption' }}
                                />
                                <Chip 
                                  label={mod.value.toString()} 
                                  size="small" 
                                  color={mod.value >= 0 ? 'success' : 'error'} 
                                />
                              </ListItem>
                            ))}
                          </List>
                        )}
                      </Box>
                    ))}
                  </Box>
                )}
                {/* Combined Dex bonus */}
                {acCalc.combined_dexterity_bonus && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Dexterity Bonus (capped by armor)</Typography>
                    {renderModifierChannels(acCalc.combined_dexterity_bonus) && (
                      <List dense disablePadding>
                        <Typography variant="body2" fontWeight="bold">
                          {renderModifierChannels(acCalc.combined_dexterity_bonus)!.name} – Total: {renderModifierChannels(acCalc.combined_dexterity_bonus)!.total}
                        </Typography>
                        {renderModifierChannels(acCalc.combined_dexterity_bonus)!.modifiers.map((mod, i) => (
                          <ListItem key={i} dense divider={i < renderModifierChannels(acCalc.combined_dexterity_bonus)!.modifiers.length - 1}>
                            <ListItemText
                              primary={mod.name}
                              secondary={mod.sourceName}
                              primaryTypographyProps={{ variant: 'body2' }}
                              secondaryTypographyProps={{ variant: 'caption' }}
                            />
                            <Chip 
                              label={mod.value.toString()} 
                              size="small" 
                              color={mod.value >= 0 ? 'success' : 'error'} 
                            />
                          </ListItem>
                        ))}
                      </List>
                    )}
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

export default React.memo(EquipmentSection); 