// Common type definitions

// Use string for UUID to match API responses
export type UUID = string;

// Common response types
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

// Common error type
export interface ApiError {
  message: string;
  status?: number;
  details?: any;
} 