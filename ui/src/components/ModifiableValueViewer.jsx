import ValueComponent from './ValueComponent';
import styles from '../styles/ModifiableValueViewer.module.css';

function ModifiableValueViewer({ data }) {
  return (
    <div className={styles.container}>
      <h2>ModifiableValue: {data.name}</h2>
      <ValueComponent data={data} />
    </div>
  );
}

export default ModifiableValueViewer; 