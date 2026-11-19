import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  filterTasksByStatus,
  calculateCompletionPercentage,
  fetchTasks,
} from '../src/taskService.js';
import {
  Task,
  ApiError,
  NetworkError,
  TimeoutError,
  ValidationError,
  TaskServiceError,
} from '../src/types.js';

const mockTasks: Task[] = [
  {
    id: 'task-1',
    companyId: 'company-alpha',
    title: 'Setup PostgreSQL RLS',
    description: 'Implement row level security policies for multi-tenancy',
    status: 'completed',
    priority: 'high',
    assignedTo: 'user-emp-1',
    createdBy: 'user-mgr-1',
    dueDate: '2026-12-01T00:00:00Z',
    createdAt: '2026-11-01T10:00:00Z',
    updatedAt: '2026-11-02T15:30:00Z',
  },
  {
    id: 'task-2',
    companyId: 'company-alpha',
    title: 'Build FastAPI Endpoints',
    description: 'Create POST, GET, PATCH endpoints with Pydantic validation',
    status: 'in_progress',
    priority: 'urgent',
    assignedTo: 'user-emp-1',
    createdBy: 'user-mgr-1',
    dueDate: '2026-12-05T00:00:00Z',
    createdAt: '2026-11-02T09:00:00Z',
    updatedAt: '2026-11-02T11:00:00Z',
  },
  {
    id: 'task-3',
    companyId: 'company-alpha',
    title: 'Write Documentation',
    description: 'Draft multi-tenant architecture and security guide',
    status: 'pending',
    priority: 'medium',
    assignedTo: 'user-emp-2',
    createdBy: 'user-mgr-1',
    dueDate: '2026-12-10T00:00:00Z',
    createdAt: '2026-11-03T08:00:00Z',
    updatedAt: '2026-11-03T08:00:00Z',
  },
  {
    id: 'task-4',
    companyId: 'company-alpha',
    title: 'Legacy Migration',
    description: 'Migrate deprecated v1 endpoints',
    status: 'cancelled',
    priority: 'low',
    assignedTo: null,
    createdBy: 'user-mgr-1',
    dueDate: null,
    createdAt: '2026-11-01T08:00:00Z',
    updatedAt: '2026-11-02T08:00:00Z',
  },
];

describe('Task A: TypeScript Task Management Module', () => {
  describe('filterTasksByStatus()', () => {
    it('filters tasks by a single status', () => {
      const completed = filterTasksByStatus(mockTasks, 'completed');
      assert.equal(completed.length, 1);
      assert.equal(completed[0]?.id, 'task-1');

      const pending = filterTasksByStatus(mockTasks, 'pending');
      assert.equal(pending.length, 1);
      assert.equal(pending[0]?.id, 'task-3');
    });

    it('filters tasks by multiple statuses', () => {
      const active = filterTasksByStatus(mockTasks, ['pending', 'in_progress']);
      assert.equal(active.length, 2);
      const ids = active.map((t) => t.id).sort();
      assert.deepEqual(ids, ['task-2', 'task-3']);
    });

    it('returns an empty array when no tasks match the given status', () => {
      const emptyTasks: Task[] = [];
      const result = filterTasksByStatus(emptyTasks, 'completed');
      assert.deepEqual(result, []);
    });

    it('throws ValidationError when tasks input is invalid', () => {
      assert.throws(
        () => filterTasksByStatus(null as unknown as Task[], 'completed'),
        ValidationError
      );
    });
  });

  describe('calculateCompletionPercentage()', () => {
    it('calculates completion percentage for a standard task set', () => {
      // 1 completed out of 4 total tasks = 25%
      const percentage = calculateCompletionPercentage(mockTasks);
      assert.equal(percentage, 25);
    });

    it('returns 100% when all tasks are completed', () => {
      const allCompleted: Task[] = [
        { ...mockTasks[0]!, id: 'c-1', status: 'completed' },
        { ...mockTasks[1]!, id: 'c-2', status: 'completed' },
      ];
      assert.equal(calculateCompletionPercentage(allCompleted), 100);
    });

    it('returns 0% when no tasks are completed', () => {
      const noneCompleted: Task[] = [
        { ...mockTasks[1]!, status: 'in_progress' },
        { ...mockTasks[2]!, status: 'pending' },
      ];
      assert.equal(calculateCompletionPercentage(noneCompleted), 0);
    });

    it('returns 0% for an empty task list without division by zero errors', () => {
      assert.equal(calculateCompletionPercentage([]), 0);
    });

    it('correctly handles excludeCancelled option', () => {
      // Total 4 tasks: 1 completed, 1 in_progress, 1 pending, 1 cancelled
      // With excludeCancelled: 1 completed out of 3 = 33.33%
      const percentage = calculateCompletionPercentage(mockTasks, {
        excludeCancelled: true,
        decimalPrecision: 2,
      });
      assert.equal(percentage, 33.33);
    });

    it('respects decimalPrecision configuration', () => {
      // 1 out of 3 = 33.33333...
      const threeTasks = mockTasks.slice(0, 3); // 1 completed, 1 in_progress, 1 pending
      assert.equal(
        calculateCompletionPercentage(threeTasks, { decimalPrecision: 0 }),
        33
      );
      assert.equal(
        calculateCompletionPercentage(threeTasks, { decimalPrecision: 4 }),
        33.3333
      );
    });

    it('throws ValidationError when input is not an array', () => {
      assert.throws(
        () => calculateCompletionPercentage(undefined as unknown as Task[]),
        ValidationError
      );
    });
  });

  describe('fetchTasks()', () => {
    it('successfully fetches tasks from an API endpoint', async () => {
      const mockFetch: typeof fetch = async (input) => {
        const urlStr = String(input);
        assert.ok(urlStr.includes('companyId=company-alpha'));
        return new Response(JSON.stringify(mockTasks), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      };

      const tasks = await fetchTasks({
        baseUrl: 'https://api.example.com/v1/tasks',
        params: { companyId: 'company-alpha' },
        customFetch: mockFetch,
      });

      assert.equal(tasks.length, 4);
      assert.equal(tasks[0]?.title, 'Setup PostgreSQL RLS');
    });

    it('handles wrapped envelope responses ({ items: [...] })', async () => {
      const mockFetch: typeof fetch = async () => {
        return new Response(
          JSON.stringify({
            items: mockTasks.slice(0, 2),
            total: 2,
            page: 1,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      };

      const tasks = await fetchTasks({
        baseUrl: 'https://api.example.com/v1/tasks',
        customFetch: mockFetch,
      });

      assert.equal(tasks.length, 2);
      assert.equal(tasks[0]?.id, 'task-1');
    });

    it('throws ApiError with HTTP status on 403 Forbidden or 404 Not Found', async () => {
      const mockFetch: typeof fetch = async () => {
        return new Response(
          JSON.stringify({ detail: 'Access to tenant denied' }),
          { status: 403, statusText: 'Forbidden' }
        );
      };

      await assert.rejects(
        () =>
          fetchTasks({
            baseUrl: 'https://api.example.com/v1/tasks',
            customFetch: mockFetch,
          }),
        (err: unknown) => {
          assert.ok(err instanceof ApiError);
          assert.equal(err.statusCode, 403);
          assert.ok(err.message.includes('403 Forbidden'));
          return true;
        }
      );
    });

    it('throws NetworkError when fetch fails due to network outage or connection error', async () => {
      const mockFetch: typeof fetch = async () => {
        throw new TypeError('Failed to fetch: ECONNREFUSED');
      };

      await assert.rejects(
        () =>
          fetchTasks({
            baseUrl: 'https://api.example.com/v1/tasks',
            customFetch: mockFetch,
          }),
        (err: unknown) => {
          assert.ok(err instanceof NetworkError);
          assert.ok(err.message.includes('ECONNREFUSED'));
          return true;
        }
      );
    });

    it('throws ValidationError when response schema is invalid', async () => {
      const mockFetch: typeof fetch = async () => {
        return new Response(
          JSON.stringify([{ invalid: 'structure', lacksRequiredFields: true }]),
          { status: 200 }
        );
      };

      await assert.rejects(
        () =>
          fetchTasks({
            baseUrl: 'https://api.example.com/v1/tasks',
            customFetch: mockFetch,
          }),
        (err: unknown) => {
          assert.ok(err instanceof ValidationError);
          assert.ok(err.message.includes('failed schema validation'));
          return true;
        }
      );
    });

    it('throws TimeoutError when request exceeds timeoutMs', async () => {
      const mockFetch: typeof fetch = async (_input, init) => {
        return new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            resolve(new Response(JSON.stringify([]), { status: 200 }));
          }, 200);

          init?.signal?.addEventListener('abort', () => {
            clearTimeout(timeout);
            const abortError = new Error('The operation was aborted');
            abortError.name = 'AbortError';
            reject(abortError);
          });
        });
      };

      await assert.rejects(
        () =>
          fetchTasks({
            baseUrl: 'https://api.example.com/v1/tasks',
            timeoutMs: 50, // Short timeout to trigger timeout
            customFetch: mockFetch,
          }),
        (err: unknown) => {
          assert.ok(err instanceof TimeoutError);
          assert.ok(err.message.includes('timed out'));
          return true;
        }
      );
    });

    it('throws TaskServiceError if caller aborts via external AbortSignal', async () => {
      const controller = new AbortController();
      controller.abort();

      await assert.rejects(
        () =>
          fetchTasks({
            baseUrl: 'https://api.example.com/v1/tasks',
            signal: controller.signal,
          }),
        (err: unknown) => {
          assert.ok(err instanceof TaskServiceError);
          return true;
        }
      );
    });
  });
});
