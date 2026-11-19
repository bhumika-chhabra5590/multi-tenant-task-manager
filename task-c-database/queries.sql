-- ============================================================================
-- SQL Queries for Multi-Tenant Task Management
-- ============================================================================

-- ============================================================================
-- SECTION 1: Queries to Fetch Tasks by Company
-- ============================================================================

-- Query 1.1: Fetch all tasks for a specific company with full assignee & creator details
-- Parameter: :company_id (UUID)
SELECT
    t.id AS task_id,
    t.company_id,
    t.title,
    t.description,
    t.status,
    t.priority,
    t.due_date,
    t.created_at,
    t.updated_at,
    -- Assignee Details
    u_assignee.id AS assignee_id,
    u_assignee.full_name AS assignee_name,
    u_assignee.email AS assignee_email,
    -- Creator Details
    u_creator.id AS creator_id,
    u_creator.full_name AS creator_name,
    u_creator.email AS creator_email
FROM tasks t
LEFT JOIN users u_assignee 
    ON t.assigned_to = u_assignee.id 
    AND t.company_id = u_assignee.company_id
INNER JOIN users u_creator 
    ON t.created_by = u_creator.id 
    AND t.company_id = u_creator.company_id
WHERE t.company_id = :company_id
ORDER BY t.created_at DESC;


-- Query 1.2: Fetch tasks filtered by status for a company (with index utilization)
-- Parameters: :company_id (UUID), :status (task_status)
SELECT
    t.id,
    t.title,
    t.status,
    t.priority,
    t.due_date,
    u.full_name AS assigned_to_name
FROM tasks t
LEFT JOIN users u ON t.assigned_to = u.id
WHERE t.company_id = :company_id
  AND t.status = :status
ORDER BY t.created_at DESC;


-- Query 1.3: Paginated task retrieval with total count window function
-- Parameters: :company_id (UUID), :limit (INT), :offset (INT)
SELECT
    t.id,
    t.title,
    t.status,
    t.priority,
    t.assigned_to,
    t.due_date,
    t.created_at,
    COUNT(*) OVER() AS total_tenant_tasks
FROM tasks t
WHERE t.company_id = :company_id
ORDER BY t.created_at DESC
LIMIT :limit OFFSET :offset;


-- ============================================================================
-- SECTION 2: Queries to Count Completed and Pending Tasks
-- ============================================================================

-- Query 2.1: Single-row summary of completed vs pending tasks with completion percentage
-- Uses conditional aggregation (FILTER clause standard in modern PostgreSQL)
-- Parameter: :company_id (UUID)
SELECT
    :company_id AS company_id,
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE status = 'completed') AS completed_tasks,
    COUNT(*) FILTER (WHERE status = 'pending') AS pending_tasks,
    COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_tasks,
    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_tasks,
    -- Percentage rounded to 2 decimal places, protected against division by zero
    ROUND(
        COALESCE(
            (COUNT(*) FILTER (WHERE status = 'completed')::NUMERIC / 
             NULLIF(COUNT(*), 0)::NUMERIC) * 100, 
            0.0
        ), 
        2
    ) AS completion_percentage
FROM tasks
WHERE company_id = :company_id;


-- Query 2.2: Aggregation grouped by Status for a given company
-- Parameter: :company_id (UUID)
SELECT
    status,
    COUNT(*) AS task_count,
    ROUND(
        (COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER()::NUMERIC) * 100, 
        2
    ) AS percentage_of_tenant_tasks
FROM tasks
WHERE company_id = :company_id
GROUP BY status
ORDER BY task_count DESC;


-- Query 2.3: Per-employee task completion breakdown within a company
-- Parameter: :company_id (UUID)
SELECT
    u.id AS employee_id,
    u.full_name AS employee_name,
    COUNT(t.id) AS total_assigned,
    COUNT(t.id) FILTER (WHERE t.status = 'completed') AS completed_count,
    COUNT(t.id) FILTER (WHERE t.status = 'pending') AS pending_count,
    COUNT(t.id) FILTER (WHERE t.status = 'in_progress') AS in_progress_count,
    ROUND(
        COALESCE(
            (COUNT(t.id) FILTER (WHERE t.status = 'completed')::NUMERIC /
             NULLIF(COUNT(t.id), 0)::NUMERIC) * 100,
            0.0
        ),
        2
    ) AS employee_completion_rate
FROM users u
LEFT JOIN tasks t 
    ON u.id = t.assigned_to 
    AND u.company_id = t.company_id
WHERE u.company_id = :company_id
GROUP BY u.id, u.full_name
ORDER BY total_assigned DESC;
