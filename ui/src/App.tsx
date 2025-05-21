import * as React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, CssBaseline, ThemeProvider, createTheme } from '@mui/material';

// Layout
import Layout from './components/layout/Layout';

// Pages
import BattleMapPage from './pages/BattleMapPage';
import NotFoundPage from './pages/NotFoundPage';

// Context
import { EventQueueProvider } from './contexts/EventQueueContext';
import { SoundSettingsProvider } from './contexts/SoundSettingsContext';

// Create a dark theme with black background
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#000000',
      paper: '#000000',
    },
    text: {
      primary: '#FFFFFF',
      secondary: 'rgba(255, 255, 255, 0.7)',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: '#000000',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#000000',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#000000',
        },
      },
    },
  },
});

const App: React.FC = () => {
  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <SoundSettingsProvider>
        <EventQueueProvider>
          <Box sx={{ bgcolor: '#000000', minHeight: '100vh' }}>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<BattleMapPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </Box>
        </EventQueueProvider>
      </SoundSettingsProvider>
    </ThemeProvider>
  );
};

export default App; 