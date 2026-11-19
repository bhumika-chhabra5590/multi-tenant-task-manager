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
function isValidTask(item: unknown): item is Task {
  if (!item || typeof item !== 'object') return false;
  const t = item as Record<string, unknown>;
  return (
    typeof t.id === 'string' &&
    typeof t.companyId === 'string' &&
    typeof t.title === 'string' &&
    typeof t.status === 'string' &&
    typeof t.priority === 'string' &&
    typeof t.createdBy === 'string'
  );
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
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
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
    : () => {};

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
    const response = await customFetch(url.toString(), {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...headers,
      },
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
      if (isValidTask(item)) {
        validTasks.push(item);
      } else {
        invalidItems.push(`Item at index ${index} is missing required Task fields`);
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
