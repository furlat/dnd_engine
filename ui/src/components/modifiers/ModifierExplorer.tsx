import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Drawer,
  useTheme,
  useMediaQuery
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useModifiableValue } from '../../hooks/character/useModifiableValue';

interface ModifierExplorerProps {
  valuePath?: string | null;
  onClose?: () => void;
}

// This component is a more detailed version of the ModifierPanel
// It shows a full exploration UI for a selected value
const ModifierExplorer: React.FC<ModifierExplorerProps> = ({ 
  valuePath: externalValuePath,
  onClose: externalOnClose
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  // Since we might not have a valuePath yet, we'll use internal state
  const [internalValuePath, setInternalValuePath] = React.useState<string | null>(null);
  
  // Use either external valuePath (from props) or internal state
  const valuePath = externalValuePath || internalValuePath;
  
  // If external onClose wasn't provided, create a default one
  const handleClose = externalOnClose || (() => setInternalValuePath(null));

  // Use the new hook
  const { details, value } = useModifiableValue(valuePath);

  if (!valuePath) {
    return null;
  }

  if (!value || !details) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography>No value found</Typography>
      </Paper>
    );
  }

  const content = (
    <Box sx={{ p: 2, width: '100%', maxWidth: 500, maxHeight: '80vh', overflow: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">Value Details</Typography>
        <IconButton size="small" onClick={handleClose}>
          <CloseIcon />
        </IconButton>
      </Box>

      <Paper elevation={2} sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle1">
          {details.name}
        </Typography>
        <Typography variant="h4" sx={{ mb: 1 }}>
          {details.value}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Base Value: {details.baseValue}
        </Typography>
      </Paper>

      <Typography variant="subtitle2" gutterBottom>
        Modifiers
      </Typography>
      <List disablePadding>
        {details.modifiers.map((mod, index) => (
          <ListItem key={index} divider>
            <ListItemText
              primary={mod.source}
              secondary={mod.value}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );

  // On mobile, use a drawer; otherwise use a regular component
  if (isMobile) {
    return (
      <Drawer
        anchor="bottom"
        open={!!valuePath}
        onClose={handleClose}
      >
        {content}
      </Drawer>
    );
  }

  return (
    <Paper elevation={3}>
      {content}
    </Paper>
  );
};

export default ModifierExplorer; 