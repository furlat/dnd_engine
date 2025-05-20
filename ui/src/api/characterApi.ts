import axios from 'axios';
import { 
  Character, 
  ConditionType, 
  DurationType,
  EquipmentItem
} from '../types/characterSheet_types';
import { EntitySummary, Position } from '../types/common';

// Update to point directly to FastAPI backend
const API_BASE_URL = 'http://localhost:8000/api';

// Common params for character fetching
const DEFAULT_INCLUDE_PARAMS = {
  include_skill_calculations: true,
  include_saving_throw_calculations: true,
  include_ac_calculation: true,
  include_attack_calculations: true,
  include_target_summary: true
}; 