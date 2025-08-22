import * as React from 'react';
import { Container, Box, Toolbar, useMediaQuery, useTheme, Paper } from '@mui/material';
import AppBar from '@mui/material/AppBar';
import Typography from '@mui/material/Typography';
import { Outlet } from 'react-router-dom';

interface LayoutProps {
  children?: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const isTablet = useMediaQuery(theme.breakpoints.between('md', 'lg'));
  
  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <AppBar 
        position="fixed" 
        sx={{ 
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Neurodragon 5e v0.1
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Box
        component="main"
        sx={{ 
          flexGrow: 1,
          overflow: 'hidden',
          pt: 8,
          position: 'relative',
          height: '100%',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        {children ? children : <Outlet />}
      </Box>
    </Box>
  );
};

export default Layout; 