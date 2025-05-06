import * as React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box } from '@mui/material';

// Layout
import Layout from './components/common/Layout';

// Pages
import CharacterListPage from './pages/CharacterListPage';
import CharacterSheetPage from './pages/CharacterSheetPage';
import NotFoundPage from './pages/NotFoundPage';

// Context
import { EventQueueProvider } from './contexts/EventQueueContext';

const App: React.FC = () => {
  return (
    <EventQueueProvider>
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<CharacterListPage />} />
          <Route path="characters/:characterId" element={<CharacterSheetPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Box>
    </EventQueueProvider>
  );
};

export default App; 