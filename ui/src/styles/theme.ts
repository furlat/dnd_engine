import { createTheme } from '@mui/material/styles';

// DnD color scheme
const theme = createTheme({
  palette: {
    primary: {
      main: '#7B1FA2', // Purple-ish
      light: '#AE52D4',
      dark: '#4A0072',
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: '#D84315', // Reddish-orange
      light: '#FF7D47',
      dark: '#9F0000',
      contrastText: '#FFFFFF',
    },
    background: {
      default: '#F5F5F6',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#262626',
      secondary: '#6E6E6E',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
    body1: {
      fontSize: '1rem',
    },
    body2: {
      fontSize: '0.875rem',
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 6,
          fontWeight: 500,
        },
      },
    },
  },
});

export default theme; 