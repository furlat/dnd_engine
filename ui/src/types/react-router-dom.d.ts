// Type definitions for React Router DOM v6
declare module 'react-router-dom' {
  import * as React from 'react';

  // Router Components
  export interface BrowserRouterProps {
    children?: React.ReactNode;
    basename?: string;
  }
  
  export class BrowserRouter extends React.Component<BrowserRouterProps, any> {}
  
  export interface RouteProps {
    caseSensitive?: boolean;
    children?: React.ReactNode;
    element?: React.ReactNode | null;
    index?: boolean;
    path?: string;
  }
  
  export function Route(props: RouteProps): React.ReactElement | null;
  
  export interface RoutesProps {
    children?: React.ReactNode;
    location?: any;
  }
  
  export function Routes(props: RoutesProps): React.ReactElement;

  // Navigation Components
  export interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
    to: string;
    replace?: boolean;
    state?: any;
  }
  
  export const Link: React.ForwardRefExoticComponent<LinkProps & React.RefAttributes<HTMLAnchorElement>>;
  
  // Hooks
  export function useParams<T = Record<string, string | undefined>>(): T;
  export function useNavigate(): (to: string, options?: { replace?: boolean, state?: any }) => void;
  export function useLocation(): Location;
  
  // Layout Components
  export function Outlet(props?: any): React.ReactElement | null;
} 