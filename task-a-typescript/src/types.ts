/**
 * Task Management TypeScript Type Definitions
 * Multi-tenant architecture for company-level isolation and role-based permissions.
 */

export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';

export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export type UserRole = 'manager' | 'employee';

export interface Company {
  id: string;
  name: string;
  createdAt: string; // ISO 8601 string
  updatedAt: string;
}

export interface User {
  id: string;
  companyId: string;
  email: string;
  fullName: string;
  role: UserRole;
  createdAt: string;
  updatedAt: string;
}

export interface Task {
  id: string;
  companyId: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignedTo: string | null; // User ID
  createdBy: string;         // User ID (typically Manager)
  dueDate: string | null;    // ISO 8601 string
  createdAt: string;
  updatedAt: string;
}

export interface TaskFilterOptions {
  status?: TaskStatus | TaskStatus[];
  priority?: TaskPriority;
  assignedTo?: string;
  companyId?: string;
  search?: string;
}

export interface CompletionPercentageOptions {
  /**
   * Whether to exclude 'cancelled' tasks from the total count.
   * Defaults to false (all tasks count towards total denominator).
   */
  excludeCancelled?: boolean;
  /**
   * Decimal precision for rounding. Defaults to 2.
   */
  decimalPrecision?: number;
}

export interface FetchTasksParams {
  /**
   * Filter tasks by lifecycle status
   */
  status?: TaskStatus;
  /**
   * Filter tasks by assignee internal profile UUID.
   * Mapped automatically to backend query parameter 'assigned_to'.
   * Note: For employee users, the backend locks visibility strictly to their own profile.
   */
  assignedTo?: string;
  /**
   * Maximum number of tasks to return (1-100)
   */
  limit?: number;
  /**
   * Offset for pagination
   */
  offset?: number;
}

export interface FetchTasksOptions {
  baseUrl?: string;
  params?: FetchTasksParams;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
  /**
   * Supabase JWT Bearer access token for authenticated API requests
   */
  accessToken?: string;
  /**
   * Custom fetch implementation (allows dependency injection for node/browser/tests)
   */
  customFetch?: typeof fetch;
}

// ============================================================================
// Custom Error Hierarchy for Type-Safe Error Handling
// ============================================================================

export class TaskServiceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'TaskServiceError';
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ApiError extends TaskServiceError {
  public readonly statusCode: number;
  public readonly details?: unknown;

  constructor(message: string, statusCode: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class NetworkError extends TaskServiceError {
  public readonly originalError?: Error;

  constructor(message: string, originalError?: Error) {
    super(message);
    this.name = 'NetworkError';
    this.originalError = originalError;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class TimeoutError extends TaskServiceError {
  constructor(message = 'Request timed out') {
    super(message);
    this.name = 'TimeoutError';
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ValidationError extends TaskServiceError {
  public readonly issues: string[];

  constructor(message: string, issues: string[] = []) {
    super(message);
    this.name = 'ValidationError';
    this.issues = issues;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}
