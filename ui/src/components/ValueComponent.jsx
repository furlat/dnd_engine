import styles from '../styles/ValueComponent.module.css';
import JsonTreeView from './JsonTreeView';

function ValueComponent({ data }) {
  // Create a summary of the ModifiableValue
  const summary = {
    basic_info: {
      name: data.name,
      uuid: data.uuid,
      source_entity: {
        uuid: data.source_entity_uuid,
        name: data.source_entity_name
      },
      computed: {
        score: data.score,
        normalized_score: data.normalized_score,
        advantage: data.advantage,
        critical: data.critical,
        auto_hit: data.auto_hit
      }
    },
    // Component summaries
    components: data.components
  };

  // More detailed view with all components
  const details = {
    self_static: data.self_static,
    to_target_static: data.to_target_static,
    self_contextual: data.self_contextual,
    to_target_contextual: data.to_target_contextual
  };

  // Add from_target components if they exist
  if (data.from_target_static) {
    details.from_target_static = data.from_target_static;
  }
  if (data.from_target_contextual) {
    details.from_target_contextual = data.from_target_contextual;
  }
  
  return (
    <div className={styles.valueComponent}>
      <div className={styles.summary}>
        <h3>ModifiableValue Summary</h3>
        <JsonTreeView data={summary} />
      </div>
      
      <div className={styles.details}>
        <h3>Detailed Components</h3>
        <JsonTreeView data={details} />
      </div>
    </div>
  );
}

export default ValueComponent; 