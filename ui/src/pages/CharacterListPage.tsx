import * as React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Typography,
  Box,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  CircularProgress,
  Alert
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import { fetchCharacters } from '../api/characterApi';
import { Character } from '../models/character';

const CharacterListPage: React.FC = () => {
  const [characters, setCharacters] = React.useState<Character[]>([]);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    const loadCharacters = async (): Promise<void> => {
      try {
        setLoading(true);
        const data = await fetchCharacters();
        setCharacters(data);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch characters:', err);
        setError('Failed to load characters. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    loadCharacters();
  }, []);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Characters
      </Typography>

      {loading && (
        <Box display="flex" justifyContent="center" my={4}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ my: 2 }}>
          {error}
        </Alert>
      )}

      {!loading && characters.length === 0 && !error && (
        <Alert severity="info" sx={{ my: 2 }}>
          No characters found. The API server might not be running.
        </Alert>
      )}

      <Grid container spacing={3}>
        {characters.map((character: Character) => (
          <Grid item xs={12} sm={6} md={4} key={character.uuid}>
            <Card elevation={2}>
              <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                  <PersonIcon fontSize="large" color="primary" sx={{ mr: 1 }} />
                  <Typography variant="h6">{character.name}</Typography>
                </Box>
              </CardContent>
              <CardActions>
                <Button
                  component={RouterLink}
                  to={`/characters/${character.uuid}`}
                  variant="contained"
                  color="primary"
                  size="small"
                >
                  View Character
                </Button>
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default CharacterListPage; 