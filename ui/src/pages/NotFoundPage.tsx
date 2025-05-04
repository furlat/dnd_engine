import * as React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

const NotFoundPage: React.FC = () => {
  return (
    <Box 
      display="flex" 
      flexDirection="column" 
      alignItems="center" 
      justifyContent="center" 
      py={6}
    >
      <Typography variant="h2" gutterBottom>
        404
      </Typography>
      <Typography variant="h5" gutterBottom>
        Page Not Found
      </Typography>
      <Typography variant="body1" color="textSecondary" paragraph align="center">
        The page you are looking for might have been removed or is temporarily unavailable.
      </Typography>
      <Button 
        variant="contained" 
        color="primary" 
        component={RouterLink} 
        to="/"
      >
        Return to Home
      </Button>
    </Box>
  );
};

export default NotFoundPage; 