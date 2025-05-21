import * as React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box } from '@mui/material';

// Layout
import Layout from './components/character_sheet/layout/Layout';

// Pages
import BattleMapPage from './pages/BattleMapPage';
import NotFoundPage from './pages/NotFoundPage';

// Context
import { EventQueueProvider } from './contexts/EventQueueContext';
import { SoundSettingsProvider } from './contexts/SoundSettingsContext';

const App: React.FC = () => {
  return (
    <SoundSettingsProvider>
      <EventQueueProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<BattleMapPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </EventQueueProvider>
    </SoundSettingsProvider>
  );
};

export default App; 