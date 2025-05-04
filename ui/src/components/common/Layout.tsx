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

const Layout: React.FC = () => {
  const theme = useTheme();

  return (
    <>
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
    </>
  );
};

export default Layout; 