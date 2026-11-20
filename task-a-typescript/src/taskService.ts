import {
  Task,
  TaskStatus,
  CompletionPercentageOptions,
  FetchTasksOptions,
  ApiError,
  NetworkError,
  TimeoutError,
  ValidationError,
  TaskServiceError,
} from './types.js';

/**
 * Filters a list of tasks by one or more statuses in a type-safe manner.
 *
 * @param tasks - Array of Task objects to filter
 * @param status - Single TaskStatus or array of TaskStatus values to match
 * @returns Filtered array of tasks matching the status criteria
 * @throws ValidationError if tasks is not an array or status is invalid
 */
export function filterTasksByStatus(
  tasks: Task[],
  status: TaskStatus | TaskStatus[]
): Task[] {
  if (!Array.isArray(tasks)) {
    throw new ValidationError('Expected an array of tasks to filter', [
      'tasks must be an Array',
    ]);
  }

  const allowedStatuses: Set<TaskStatus> = new Set(
    Array.isArray(status) ? status : [status]
  );

  return tasks.filter((task) => allowedStatuses.has(task.status));
}

/**
 * Calculates the percentage of completed tasks in a collection.
 *
 * @param tasks - Array of tasks
 * @param options - Optional configuration (excludeCancelled, decimalPrecision)
 * @returns Number representing percentage between 0 and 100 (inclusive)
 * @throws ValidationError if tasks is not an array
 */
export function calculateCompletionPercentage(
  tasks: Task[],
  options: CompletionPercentageOptions = {}
): number {
  if (!Array.isArray(tasks)) {
    throw new ValidationError('Expected an array of tasks', [
      'tasks must be an Array',
    ]);
  }

  const { excludeCancelled = false, decimalPrecision = 2 } = options;

  const relevantTasks = excludeCancelled
    ? tasks.filter((t) => t.status !== 'cancelled')
    : tasks;

  if (relevantTasks.length === 0) {
    return 0;
  }

  const completedCount = relevantTasks.filter(
    (t) => t.status === 'completed'
  ).length;

  const percentage = (completedCount / relevantTasks.length) * 100;
  const factor = Math.pow(10, decimalPrecision);
  return Math.round(percentage * factor) / factor;
}

/**
 * Validates that an object conforms to the minimum Task interface at runtime.
 */
function normalizeApiTask(item: unknown): Task | null {
  if (!item || typeof item !== 'object') {
    return null;
  }

  const raw = item as Record<string, unknown>;

  // Convert Python snake_case fields into TypeScript camelCase.
  const id = raw.id;
  const companyId = raw.company_id ?? raw.companyId;
  const title = raw.title;
  const description = raw.description;
  const status = raw.status;
  const priority = raw.priority;

  const assignedTo =
    raw.assigned_to !== undefined
      ? raw.assigned_to
      : raw.assignedTo;

  const createdBy = raw.created_by ?? raw.createdBy;

  const dueDate =
    raw.due_date !== undefined
      ? raw.due_date
      : raw.dueDate;

  const createdAt = raw.created_at ?? raw.createdAt;
  const updatedAt = raw.updated_at ?? raw.updatedAt;

  const validStatuses = [
    'pending',
    'in_progress',
    'completed',
    'cancelled',
  ];

  const validPriorities = [
    'low',
    'medium',
    'high',
    'urgent',
  ];

  const isNullableString = (
    value: unknown
  ): value is string | null =>
    value === null || typeof value === 'string';

  if (
    typeof id !== 'string' ||
    typeof companyId !== 'string' ||
    typeof title !== 'string' ||
    !isNullableString(description) ||
    typeof status !== 'string' ||
    !validStatuses.includes(status) ||
    typeof priority !== 'string' ||
    !validPriorities.includes(priority) ||
    !isNullableString(assignedTo) ||
    typeof createdBy !== 'string' ||
    !isNullableString(dueDate) ||
    typeof createdAt !== 'string' ||
    typeof updatedAt !== 'string'
  ) {
    return null;
  }

  return {
    id,
    companyId,
    title,
    description,
    status: status as Task['status'],
    priority: priority as Task['priority'],
    assignedTo,
    createdBy,
    dueDate,
    createdAt,
    updatedAt,
  };
}

/**
 * Asynchronously fetches tasks from an API endpoint with comprehensive error handling,
 * multi-tenant query parameter support, timeout cancellation, and type safety.
 *
 * @param options - Configuration including baseUrl, query params, headers, timeout, and fetcher
 * @returns Promise resolving to an array of Task objects
 * @throws ApiError on non-2xx HTTP response
 * @throws TimeoutError when request times out
 * @throws NetworkError on connection/DNS/socket failures
 * @throws ValidationError if response payload does not match expected Task schema
 */
export async function fetchTasks(
  options: FetchTasksOptions = {}
): Promise<Task[]> {
  const {
    baseUrl = 'http://localhost:8000/api/v1/tasks',
    params,
    headers = {},
    signal,
    timeoutMs = 8000,
    accessToken,
    customFetch = globalThis.fetch,
  } = options;

  if (typeof customFetch !== 'function') {
    throw new TaskServiceError(
      'No fetch implementation available. Provide a customFetch option or use a compatible runtime.'
    );
  }

  // Construct URL with query parameters
  let url: URL;
  try {
    url = new URL(baseUrl);
  } catch (err) {
    throw new ValidationError(`Invalid base URL: "${baseUrl}"`, [
      (err as Error).message,
    ]);
  }

  if (params) {
    if (params.status !== undefined && params.status !== null) {
      url.searchParams.set('status', params.status);
    }
    // Map camelCase assignedTo to backend snake_case assigned_to parameter
    if (params.assignedTo !== undefined && params.assignedTo !== null) {
      url.searchParams.set('assigned_to', params.assignedTo);
    }
    if (params.limit !== undefined && params.limit !== null) {
      url.searchParams.set('limit', String(params.limit));
    }
    if (params.offset !== undefined && params.offset !== null) {
      url.searchParams.set('offset', String(params.offset));
    }
  }

  // Handle timeout coordination with user-provided signal
  const timeoutController = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    timeoutController.abort();
  }, timeoutMs);

  // If user passed a signal, abort if user signal aborts
  const cleanupUserSignal = signal
    ? () => signal.removeEventListener('abort', onUserAbort)
    : () => { };

  function onUserAbort() {
    timeoutController.abort();
  }

  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      throw new TaskServiceError('Operation aborted by user signal');
    }
    signal.addEventListener('abort', onUserAbort);
  }

  try {
    const requestHeaders: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...headers,
    };

    if (accessToken) {
      requestHeaders['Authorization'] = `Bearer ${accessToken.trim()}`;
    }

    const response = await customFetch(url.toString(), {
      method: 'GET',
      headers: requestHeaders,
      signal: timeoutController.signal,
    });

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }

      throw new ApiError(
        `Failed to fetch tasks: HTTP ${response.status} ${response.statusText}`,
        response.status,
        errorBody
      );
    }

    let data: unknown;
    try {
      data = await response.json();
    } catch (parseErr) {
      throw new ValidationError('Failed to parse JSON response from tasks API', [
        (parseErr as Error).message,
      ]);
    }

    // Handle APIs that wrap lists in an object (e.g. { items: [...], total: 10 } or directly [...])
    let rawList: unknown[];
    if (Array.isArray(data)) {
      rawList = data;
    } else if (
      data &&
      typeof data === 'object' &&
      'items' in data &&
      Array.isArray((data as { items: unknown[] }).items)
    ) {
      rawList = (data as { items: unknown[] }).items;
    } else {
      throw new ValidationError(
        'Expected API response to be an array or an object containing an "items" array'
      );
    }

    // Validate that items match Task schema
    const invalidItems: string[] = [];
    const validTasks: Task[] = [];

    rawList.forEach((item, index) => {
      const normalizedTask = normalizeApiTask(item);

      if (normalizedTask) {
        validTasks.push(normalizedTask);
      } else {
        invalidItems.push(
          `Item at index ${index} is missing required Task fields`
        );
      }
    });

    if (invalidItems.length > 0) {
      throw new ValidationError(
        'One or more tasks in the response payload failed schema validation',
        invalidItems
      );
    }

    return validTasks;
  } catch (error: unknown) {
    if (error instanceof TaskServiceError) {
      throw error;
    }

    if (timedOut) {
      throw new TimeoutError(`Request timed out after ${timeoutMs}ms`);
    }

    if (error instanceof Error && error.name === 'AbortError') {
      throw new TaskServiceError('Request aborted by client');
    }

    if (error instanceof Error) {
      throw new NetworkError(
        `Network error occurred while fetching tasks: ${error.message}`,
        error
      );
    }

    throw new TaskServiceError('An unknown error occurred while fetching tasks');
  } finally {
    clearTimeout(timeoutId);
    cleanupUserSignal();
  }
}
