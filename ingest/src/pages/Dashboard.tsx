import * as React from 'react';
import { Box, Typography, Grid, Paper, CircularProgress, Alert, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { fetchCharacters } from '../api/characterApi';
import { Character } from '../models/character';

// Simple dashboard that shows a list of entities from the API
const Dashboard: React.FC = () => {
  const [entities, setEntities] = React.useState<Character[]>([]);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  // Load entities on component mount
  React.useEffect(() => {
    const loadEntities = async () => {
      try {
        setLoading(true);
        const data = await fetchCharacters();
        setEntities(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch entities:', err);
        setError('Failed to load entities. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    loadEntities();
  }, []);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ my: 2 }}>
        {error}
      </Alert>
    );
  }

  if (entities.length === 0) {
    return (
      <Alert severity="info" sx={{ my: 2 }}>
        No entities found.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Available Characters
      </Typography>

      <Grid container spacing={3}>
        {entities.map((entity) => (
          <Grid item xs={12} sm={6} md={4} key={entity.uuid}>
            <Paper elevation={2} sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                {entity.name}
              </Typography>
              
              {entity.description && (
                <Typography variant="body2" color="text.secondary" paragraph noWrap>
                  {entity.description}
                </Typography>
              )}

              <Button
                component={RouterLink}
                to={`/characters/${entity.uuid}`}
                variant="contained"
                color="primary"
              >
                View Character
              </Button>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default Dashboard; 