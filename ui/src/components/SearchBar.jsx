import { useState } from 'react';
import styles from '../styles/SearchBar.module.css';

function SearchBar({ onSearch }) {
  const [uuid, setUuid] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (uuid.trim()) {
      onSearch(uuid.trim());
    }
  };

  return (
    <div className={styles.container}>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={uuid}
          onChange={(e) => setUuid(e.target.value)}
          placeholder="Enter ModifiableValue UUID"
          className={styles.input}
        />
        <button type="submit" className={styles.button}>Search</button>
      </form>
    </div>
  );
}

export default SearchBar; 