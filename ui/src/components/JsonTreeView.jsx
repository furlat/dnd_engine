import { useState } from 'react';
import styles from '../styles/JsonTreeView.module.css';

function JsonTreeView({ data, level = 0, label = null }) {
  const [expanded, setExpanded] = useState(level < 1); // Auto-expand first level
  
  // Skip rendering for null or undefined
  if (data === null || data === undefined) {
    return <span className={styles.null}>null</span>;
  }
  
  // Handle primitive values
  if (typeof data !== 'object') {
    if (typeof data === 'string') {
      return <span className={styles.string}>"{data}"</span>;
    }
    return <span className={styles[typeof data]}>{String(data)}</span>;
  }
  
  // Handle empty objects/arrays
  if (Object.keys(data).length === 0) {
    return <span className={styles.empty}>{Array.isArray(data) ? '[]' : '{}'}</span>;
  }
  
  // For arrays and objects, create expandable view
  const isArray = Array.isArray(data);
  const toggleExpand = () => setExpanded(!expanded);
  
  return (
    <div className={styles.node} style={{ marginLeft: `${level * 16}px` }}>
      {label && <span className={styles.label}>{label}: </span>}
      
      <span className={styles.toggle} onClick={toggleExpand}>
        {expanded ? '▼' : '►'}
      </span>
      
      <span className={styles.bracket} onClick={toggleExpand}>
        {isArray ? '[' : '{'}
      </span>
      
      {expanded && (
        <div className={styles.children}>
          {Object.entries(data).map(([key, value], index) => (
            <div key={key} className={styles.property}>
              <JsonTreeView 
                data={value} 
                level={level + 1} 
                label={isArray ? null : key} 
              />
              {index < Object.entries(data).length - 1 && <span className={styles.comma}>,</span>}
            </div>
          ))}
        </div>
      )}
      
      <span className={styles.bracket}>
        {isArray ? ']' : '}'}
      </span>
    </div>
  );
}

export default JsonTreeView; 