import * as React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, CssBaseline, ThemeProvider, createTheme } from '@mui/material';

// Layout
import Layout from './components/layout/Layout';

// Pages
import BattleMapPage from './pages/BattleMapPage';
import NotFoundPage from './pages/NotFoundPage';

// Note: Sound settings now managed by valtio store in store/soundStore.ts

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
        <Box sx={{ bgcolor: '#000000', minHeight: '100vh' }}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<BattleMapPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Box>
    </ThemeProvider>
  );
};

export default App; 