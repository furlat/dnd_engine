import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  Collapse,
  IconButton,
  useTheme
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CloseIcon from '@mui/icons-material/Close';
import { useEntity } from '../../contexts/EntityContext';

interface ModifierPanelProps {
  valuePath: string | null;
  title?: string;
  compact?: boolean;
  onClose?: () => void;
}

/**
 * A component that displays modifiers for a value
 * This is a simpler version compared to ModifierExplorer
 */
const ModifierPanel: React.FC<ModifierPanelProps> = ({ 
  valuePath, 
  title, 
  compact = false,
  onClose
}) => {
  const theme = useTheme();
  const { entity } = useEntity();
  const [expanded, setExpanded] = React.useState(!compact);

  if (!entity || !valuePath) {
    return null;
  }

  // Get value details - this would be replaced with actual logic to retrieve from entity
  const getValueDetails = (path: string) => {
    // In a real implementation, this would navigate the entity to find the value at the given path
    return {
      name: path.split('.').pop() || path,
      value: "5",
      baseValue: "3",
      modifiers: [
        { source: "Ability Modifier", value: "+2" },
        { source: "Proficiency", value: "+2" }
      ]
    };
  };

  const valueDetails = getValueDetails(valuePath);
  const displayTitle = title || valueDetails.name;

  return (
    <Paper elevation={1} sx={{ p: 1, mb: 1 }}>
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center'
        }}
      >
        <Typography variant="subtitle2" sx={{ cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
          {displayTitle} ({valueDetails.value})
        </Typography>
        <Box>
          {expanded ? 
            <IconButton size="small" onClick={() => setExpanded(false)}>
              <ExpandLessIcon fontSize="small" />
            </IconButton> : 
            <IconButton size="small" onClick={() => setExpanded(true)}>
              <ExpandMoreIcon fontSize="small" />
            </IconButton>
          }
          {onClose && 
            <IconButton size="small" onClick={onClose}>
              <CloseIcon fontSize="small" />
            </IconButton>
          }
        </Box>
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Base Value: {valueDetails.baseValue}
          </Typography>
          
          <List dense disablePadding>
            {valueDetails.modifiers.map((mod, index) => (
              <ListItem key={index} dense sx={{ py: 0.5 }}>
                <ListItemText
                  primary={`${mod.source}: ${mod.value}`}
                  primaryTypographyProps={{ variant: 'body2' }}
                />
              </ListItem>
            ))}
          </List>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default ModifierPanel; 