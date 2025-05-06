import * as React from 'react';
import { Outlet } from 'react-router-dom';
import {
  AppBar,
  Box,
  Container,
  Toolbar,
  Typography,
  Button,
  useTheme
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import EventQ from '../events/EventQ';

const Layout: React.FC = () => {
  const theme = useTheme();

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* Main content area */}
      <Box sx={{ 
        flex: 1, 
        display: 'flex',
        flexDirection: 'column',
        overflow: 'auto',
        maxWidth: 'calc(100vw - 350px)' // Account for EventQ width
      }}>
        <AppBar position="static">
          <Toolbar>
            <Typography
              variant="h6"
              component={RouterLink}
              to="/"
              sx={{
                flexGrow: 1,
                textDecoration: 'none',
                color: 'inherit',
                fontWeight: 'bold'
              }}
            >
              D&D Character Sheet
            </Typography>
            <Button 
              color="inherit" 
              component={RouterLink} 
              to="/"
            >
              Characters
            </Button>
          </Toolbar>
        </AppBar>
        <Box
          sx={{
            flexGrow: 1,
            bgcolor: theme.palette.background.default,
            py: 3
          }}
        >
          <Container maxWidth="lg">
            <Outlet />
          </Container>
        </Box>
        <Box
          component="footer"
          sx={{
            py: 3,
            px: 2,
            mt: 'auto',
            backgroundColor: theme.palette.grey[200],
          }}
        >
          <Container maxWidth="lg">
            <Typography variant="body2" color="text.secondary" align="center">
              D&D Character Sheet - {new Date().getFullYear()}
            </Typography>
          </Container>
        </Box>
      </Box>
      
      {/* Event Queue */}
      <Box sx={{ 
        width: '350px',
        borderLeft: 1,
        borderColor: 'divider',
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
      }}>
        <EventQ />
      </Box>
    </Box>
  );
};

export default Layout; 