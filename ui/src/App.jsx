import { useState } from 'react';
import SearchBar from './components/SearchBar';
import ModifiableValueViewer from './components/ModifiableValueViewer';
import './App.css';

function App() {
  const [valueData, setValueData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (uuid) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:8000/api/values/${uuid}`);
      
      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }
      
      const data = await response.json();
      setValueData(data);
    } catch (err) {
      setError(err.message);
      setValueData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <h1>D&D Engine ModifiableValue Viewer</h1>
      <SearchBar onSearch={handleSearch} />
      
      {loading && <p className="loading">Loading...</p>}
      {error && <p className="error">Error: {error}</p>}
      
      {valueData && !loading && !error && (
        <ModifiableValueViewer data={valueData} />
      )}
    </div>
  );
}

export default App; 