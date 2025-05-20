import * as React from 'react';
import { 
  Grid, 
  Paper,
  Typography,
  Box,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  useTheme,
  Divider,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Card,
  CardContent
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { 
  AbilityScoresSnapshot, 
  AbilityScore, 
  ModifiableValueSnapshot, 
  ScoreModifier,
  ModifierDisplay 
} from '../../../types/characterSheet_types';
import { useAbilityScores } from '../../../hooks/character_sheet/useAbilityScores';

interface AbilityDetailDialogProps {
  open: boolean;
  onClose: () => void;
  ability: AbilityScore | null;
}

// Helper component to display JSON data recursively
const DisplayJSON = ({ data, name = "Data" }: { data: unknown, name?: string }) => {
  return (
    <div>
      {(typeof data === 'object' && data !== null) ? (
        <>
          {Object.keys(data as Record<string, unknown>).map((key) => {
            const value = (data as Record<string, unknown>)[key];
            const isObject = typeof value === 'object' && value !== null;
            
            if (Array.isArray(value)) {
              return (
                <div key={key} style={{ marginLeft: 10 }}>
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                    {key} [{value.length}]:
                  </Typography>
                  {value.map((item, idx) => (
                    <Box key={idx} sx={{ ml: 2, mb: 1 }}>
                      <DisplayJSON data={item} name={`${key}[${idx}]`} />
                    </Box>
                  ))}
                </div>
              );
            }
            
            return (
              <div key={key} style={{ marginLeft: 10 }}>
                <Typography variant="body2">
                  <span style={{ fontWeight: 'bold' }}>{key}:</span> {isObject ? '' : String(value)}
                </Typography>
                {isObject && <DisplayJSON data={value} name={key} />}
              </div>
            );
          })}
        </>
      ) : (
        <Typography variant="body2">{String(data)}</Typography>
      )}
    </div>
  );
};

const AbilityDetailDialog: React.FC<AbilityDetailDialogProps> = (props) => {
  const { open, onClose, ability } = props;
  if (!ability) return null;
  
  const getTotalValue = (modifiableValue: ModifiableValueSnapshot): number => {
    return modifiableValue.modifiers.reduce((sum: number, mod) => sum + mod.value, 0);
  };
  
  // Access ability_score if available
  const abilityScore = ability.ability_score || { 
    modifiers: [], 
    base_value: ability.score, 
    final_value: ability.score,
    normalized_value: ability.score
  };
  
  // Get the modifier_bonus data
  const modifierBonus = ability.modifier_bonus || {
    modifiers: [],
    base_value: 0,
    final_value: 0,
    normalized_value: 0
  };
  
  const hasModifiers = abilityScore.modifiers && Array.isArray(abilityScore.modifiers);
  const modifiers: ModifierDisplay[] = hasModifiers ? 
    (abilityScore.modifiers as ScoreModifier[]).map(m => ({
      name: m.name,
      value: m.value,
      source_entity_name: m.source_entity_name
    })) : [];
  
  // Check for base_modifier in ability.ability_score
  const baseModifier = abilityScore.modifiers.find(m => m.name === 'Base') as ScoreModifier | undefined;
  // Get actual raw and normalized scores from ability_score if available
  const rawScore = abilityScore.final_value || ability.score;
  const normalizedScore = abilityScore.normalized_value || ability.normalized_value || ability.score;
  
  // Get the normalized_value from the modifier_bonus (usually adds directly to the ability modifier)
  const modifierBonusValue = modifierBonus.normalized_value || 0;
  // The normalized_value is already in modifier range, so we use it directly
  const baseCalculation = normalizedScore;
  const calculatedModifier = baseCalculation + modifierBonusValue;
  const modifierMatches = calculatedModifier === ability.modifier;
  
  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {ability.name.charAt(0).toUpperCase() + ability.name.slice(1)} Details
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <Paper elevation={1} sx={{ p: 2, mb: 2 }}>
                <Grid container spacing={2}>
                  <Grid size={6}>
                    <Typography variant="body2" color="text.secondary">Raw Score</Typography>
                    <Typography variant="h5">{rawScore}</Typography>
                  </Grid>
                  <Grid size={6}>
                    <Typography variant="body2" color="text.secondary">Normalized Score</Typography>
                    <Typography variant="h5">{normalizedScore}</Typography>
                  </Grid>
                  <Grid size={12}>
                    <Divider sx={{ my: 1 }} />
                    <Typography variant="body2" color="text.secondary">Ability Modifier</Typography>
                    <Typography variant="h4" color={ability.modifier >= 0 ? "success.main" : "error.main"}>
                    {ability.modifier >= 0 ? `+${ability.modifier}` : ability.modifier}
                    </Typography>
                    
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption">
                      Calculated as: {baseCalculation >= 0 ? `+${baseCalculation}` : baseCalculation} 
                        {modifierBonusValue !== 0 && (
                          modifierBonusValue > 0 
                            ? <> + {modifierBonusValue}</> 
                            : <> - {Math.abs(modifierBonusValue)}</>
                        )} 
                        = {calculatedModifier >= 0 ? `+${calculatedModifier}` : calculatedModifier}
                        {!modifierMatches && (
                          <Chip 
                            size="small" 
                            color="warning" 
                            label="Calculation mismatch" 
                            sx={{ ml: 1, height: 16, fontSize: '0.6rem' }} 
                          />
                        )}
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
              
              <Typography variant="h6" gutterBottom>
                Base Values
              </Typography>
              <Paper elevation={1} sx={{ p: 2 }}>
                <Typography variant="body2" color="text.secondary">Base Score</Typography>
                <Typography variant="h6">{ability.base_score || abilityScore.base_value || rawScore}</Typography>
                
                {baseModifier && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Base Modifier: {baseModifier.name} ({baseModifier.value >= 0 ? `+${baseModifier.value}` : baseModifier.value})
                    </Typography>
                  </Box>
                )}
                
                {modifierBonus.modifiers.find(m => m.name === 'Base') && (
                  <>
                    <Divider sx={{ my: 1 }} />
                    <Typography variant="body2" color="text.secondary">Modifier Bonus</Typography>
                    <Typography variant="h6">
                      {modifierBonusValue >= 0 ? `+${modifierBonusValue}` : modifierBonusValue}
                    </Typography>
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Source: {modifierBonus.modifiers.find(m => m.name === 'Base')?.name}
                      </Typography>
                    </Box>
                  </>
                )}
              </Paper>
              {/* Quick view of main static modifiers if available */}
              {modifiers.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Ability Score Modifiers
                  </Typography>
                  <Paper elevation={1} sx={{ p: 2 }}>
                    {modifiers.map((mod, idx) => (
                      <Box key={idx} sx={{ mb: idx < modifiers.length - 1 ? 1 : 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2">{mod.name}</Typography>
                          <Chip 
                            size="small" 
                            label={`${mod.value}`}
                            color={mod.value >= 0 ? "success" : "error"}
                          />
                        </Box>
                        {mod.source_entity_name && (
                          <Typography variant="caption" color="text.secondary">
                            Source: {mod.source_entity_name}
                          </Typography>
                        )}
                      </Box>
                    ))}
                  </Paper>
                </Box>
              )}
              
              {/* Display modifier bonus modifiers if available */}
              {modifierBonus.modifiers.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Modifier Bonus Modifiers
                  </Typography>
                  <Paper elevation={1} sx={{ p: 2 }}>
                    {(modifierBonus.modifiers as ScoreModifier[]).map((mod, idx) => (
                      <Box key={idx} sx={{ mb: idx < modifierBonus.modifiers.length - 1 ? 1 : 0 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2">{mod.name}</Typography>
                          <Chip 
                            size="small" 
                            label={`${mod.value}`}
                            color={mod.value >= 0 ? "success" : "error"}
                          />
                        </Box>
                        {mod.source_entity_name && (
                          <Typography variant="caption" color="text.secondary">
                            Source: {mod.source_entity_name}
                          </Typography>
                        )}
                      </Box>
                    ))}
                  </Paper>
                </Box>
              )}
            </Box>
          </Grid>
          
          <Grid size={{ xs: 12, md: 6 }}>
            <Typography variant="h6" gutterBottom>
              Modifier Breakdown
            </Typography>
            
            {/* Build accordion sections */}
            {(() => {
              const sections: { label: string; modifiers: ReadonlyArray<ModifierDisplay> }[] = [];
              if (hasModifiers) {
                sections.push({ label: 'Ability Score Modifiers', modifiers });
              }
              if (modifierBonus.modifiers && modifierBonus.modifiers.length > 0) {
                sections.push({ 
                  label: 'Modifier Bonus Modifiers', 
                  modifiers: (modifierBonus.modifiers as ScoreModifier[]).map(m => ({
                    name: m.name,
                    value: m.value,
                    source_entity_name: m.source_entity_name
                  }))
                });
              }
              if (sections.length === 0) {
                return (
                  <Paper elevation={1} sx={{ p: 2 }}>
                    <Typography variant="body2">No detailed modifier breakdown available.</Typography>
                  </Paper>
                );
              }
              return sections.map((section, sIdx) => (
                <Accordion key={sIdx} defaultExpanded sx={{ mb: 1 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}> 
                    <Typography variant="subtitle1">{section.label}</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Box key={sIdx} sx={{ mb: 2 }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {section.label} – Total: {section.modifiers.reduce((sum, mod) => sum + mod.value, 0)}
                      </Typography>
                      <List dense disablePadding>
                        {section.modifiers.map((mod, mIdx) => (
                          <ListItem key={mIdx} dense divider={mIdx < section.modifiers.length - 1}>
                            <ListItemText
                              primary={mod.name}
                              secondary={mod.source_entity_name}
                              primaryTypographyProps={{ variant: 'body2' }}
                              secondaryTypographyProps={{ variant: 'caption' }}
                            />
                            <Chip
                              label={`${mod.value}`}
                              color={mod.value >= 0 ? 'success' : 'error'}
                              size="small"
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Box>
                  </AccordionDetails>
                </Accordion>
              ));
            })()}
          </Grid>
          
          {/* Debug accordion for raw data inspection */}
          <Grid size={12}>
            <Accordion sx={{ mt: 2 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography color="error">Debug: Raw Ability Data</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      Full Ability Object:
                    </Typography>
                    <Box sx={{ mt: 1, p: 1, backgroundColor: '#f5f5f5', borderRadius: 1, maxHeight: 300, overflow: 'auto' }}>
                      <DisplayJSON data={ability} />
                    </Box>
                    
                    {/* Show ability_score details separately since it should have the channels */}
                    {ability.ability_score && (
                      <>
                        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                          Ability Score Object:
                        </Typography>
                        <Box sx={{ mt: 1, p: 1, backgroundColor: '#f5f5f5', borderRadius: 1, maxHeight: 300, overflow: 'auto' }}>
                          <DisplayJSON data={ability.ability_score} />
                        </Box>
                      </>
                    )}
                  </CardContent>
                </Card>
              </AccordionDetails>
            </Accordion>
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

const AbilityScoresBlock: React.FC = () => {
  const theme = useTheme();
  const { 
    abilityScores,
    selectedAbility,
    dialogOpen,
    handleAbilityClick,
    handleCloseDialog
  } = useAbilityScores();
  
  if (!abilityScores) return null;
  
  const abilityCards = [
    { key: 'strength', label: 'Strength' },
    { key: 'dexterity', label: 'Dexterity' },
    { key: 'constitution', label: 'Constitution' },
    { key: 'intelligence', label: 'Intelligence' },
    { key: 'wisdom', label: 'Wisdom' },
    { key: 'charisma', label: 'Charisma' }
  ];
  
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Ability Scores
      </Typography>
      <Grid container spacing={2}>
        {abilityCards.map(({ key, label }) => {
          const ability = abilityScores[key as keyof AbilityScoresSnapshot];
          const modifierText = ability.modifier >= 0 ? `+${ability.modifier}` : ability.modifier;
          
          // Access ability_score if available
          const abilityScore = ability.ability_score || { final_value: ability.score, normalized_value: ability.score };
          const showNormalizedScore = abilityScore.normalized_value !== undefined && 
                                     abilityScore.normalized_value !== abilityScore.final_value;
          
          return (
            <Grid size={{ xs: 6, sm: 4, md: 2 }} key={key}>
              <Paper 
                elevation={3} 
                sx={{ 
                  textAlign: 'center', 
                  p: 1.5,
                  cursor: 'pointer',
                  '&:hover': {
                    bgcolor: theme.palette.action.hover
                  }
                }}
                onClick={() => handleAbilityClick(ability)}
              >
                <Typography variant="subtitle1" gutterBottom>
                  {label}
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: 0.5 }}>
                  <Typography variant="h4">{abilityScore.final_value}</Typography>
                  <Typography
                    variant="subtitle1"
                    color={ability.modifier >= 0 ? 'success.main' : 'error.main'}
                  >({modifierText})</Typography>
                </Box>
                {showNormalizedScore && (
                  <Typography variant="caption" color="text.secondary">
                    Normalized: {abilityScore.normalized_value}
                  </Typography>
                )}
              </Paper>
            </Grid>
          );
        })}
      </Grid>
      <AbilityDetailDialog 
        open={dialogOpen} 
        onClose={handleCloseDialog} 
        ability={selectedAbility} 
      />
    </Box>
  );
};

export default React.memo(AbilityScoresBlock);