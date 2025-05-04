import * as React from 'react';
import {
  Box,
  Paper,
  Typography,
  Divider,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Drawer,
  useTheme,
  useMediaQuery
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useEntity } from '../../contexts/EntityContext';

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
  const { entity } = useEntity();
  
  // Since EntityContext doesn't have selectedValuePath yet, we'll use props or internal state
  const [internalValuePath, setInternalValuePath] = React.useState<string | null>(null);
  
  // Use either external valuePath (from props) or internal state
  const valuePath = externalValuePath || internalValuePath;
  
  // If external onClose wasn't provided, create a default one
  const handleClose = externalOnClose || (() => setInternalValuePath(null));

  if (!valuePath) {
    return null;
  }

  if (!entity) {
    return (
      <Paper sx={{ p: 2 }}>
        <Typography>No entity loaded</Typography>
      </Paper>
    );
  }

  // Get value details
  const getValueDetails = (path: string) => {
    // This is a stub for now - in a real implementation, 
    // this would navigate the entity to find the value at the given path
    return {
      name: path.split('.').pop() || path,
      value: "5",
      baseValue: "3",
      modifiers: [
        { source: "Ability Modifier", value: "+2" },
        { source: "Proficiency", value: "+2" },
        { source: "Magic Item", value: "+1" }
      ]
    };
  };

  const valueDetails = getValueDetails(valuePath);

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
          {valueDetails.name}
        </Typography>
        <Typography variant="h4" sx={{ mb: 1 }}>
          {valueDetails.value}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Base Value: {valueDetails.baseValue}
        </Typography>
      </Paper>

      <Typography variant="subtitle2" gutterBottom>
        Modifiers
      </Typography>
      <List disablePadding>
        {valueDetails.modifiers.map((mod, index) => (
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