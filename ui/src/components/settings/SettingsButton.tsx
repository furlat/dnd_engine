import * as React from 'react';
import {
  IconButton,
  Tooltip,
  Dialog,
  DialogContent,
  Tabs,
  Tab,
  Box
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import SoundSettingsPanel from './SoundSettingsPanel';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ py: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const SettingsButton: React.FC = () => {
  const [open, setOpen] = React.useState(false);
  const [tabValue, setTabValue] = React.useState(0);

  const handleOpen = () => setOpen(true);
  const handleClose = () => setOpen(false);
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <>
      <Tooltip title="Settings">
        <IconButton 
          onClick={handleOpen}
          size="small"
          sx={{ color: 'white' }}
        >
          <SettingsIcon />
        </IconButton>
      </Tooltip>

      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogContent sx={{ p: 0 }}>
          <Tabs
            value={tabValue}
            onChange={handleTabChange}
            aria-label="Settings tabs"
            centered
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab icon={<VolumeUpIcon />} label="SOUND" />
            {/* Additional tabs can be added here in the future */}
          </Tabs>

          <TabPanel value={tabValue} index={0}>
            <SoundSettingsPanel onClose={handleClose} />
          </TabPanel>
          {/* Additional tab panels for future settings */}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default SettingsButton; 