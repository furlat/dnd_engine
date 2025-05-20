import TabPanel from './TabPanel';
import Layout from './Layout';

// Common utility components
export interface SectionProps {
  title: string;
  children: React.ReactNode;
}

export interface InfoCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
}

export { TabPanel, Layout }; 