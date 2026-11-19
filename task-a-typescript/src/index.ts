export {
  TaskStatus,
  TaskPriority,
  UserRole,
  Company,
  User,
  Task,
  TaskFilterOptions,
  CompletionPercentageOptions,
  FetchTasksParams,
  FetchTasksOptions,
  TaskServiceError,
  ApiError,
  NetworkError,
  TimeoutError,
  ValidationError,
} from './types.js';

export {
  filterTasksByStatus,
  calculateCompletionPercentage,
  fetchTasks,
} from './taskService.js';
