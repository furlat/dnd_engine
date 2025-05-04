import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import App from './App';
import theme from './styles/theme';

// Get the root element
const rootElement = document.getElementById('root');

// Ensure the element exists
if (!rootElement) {
  throw new Error('Root element not found');
}

// Create a root
const root = ReactDOM.createRoot(rootElement);

// Render the App
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// Log rendering status
console.log('React app rendering started'); 