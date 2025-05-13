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
import { useModifiableValue } from '../../hooks/character/useModifiableValue';

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
  const [expanded, setExpanded] = React.useState(!compact);
  const { details } = useModifiableValue(valuePath);

  if (!details) {
    return null;
  }

  const displayTitle = title || details.name;

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
          {displayTitle} ({details.value})
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
            Base Value: {details.baseValue}
          </Typography>
          
          <List dense disablePadding>
            {details.modifiers.map((mod, index) => (
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