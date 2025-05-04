/// <reference types="react-scripts" />

// Module declarations for file imports
declare module '*.json';
declare module '*.png';
declare module '*.jpg';
declare module '*.svg' {
  import * as React from 'react';
  export const ReactComponent: React.FunctionComponent<React.SVGProps<SVGSVGElement>>;
  const src: string;
  export default src;
} 