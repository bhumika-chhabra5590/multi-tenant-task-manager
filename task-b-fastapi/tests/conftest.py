import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repositories.task_repository import TaskRepository, task_repository
from app.services.task_service import task_service


@pytest.fixture(autouse=True)
def reset_repository_state():
    """Reset repository before each test so tests remain isolated and deterministic."""
    fresh_repo = TaskRepository()
    task_repository._tasks = fresh_repo._tasks.copy()
    task_service.repo = task_repository
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mgr_alpha_headers():
    return {"X-User-Id": "usr_mgr_alpha"}


@pytest.fixture
def emp_alpha_headers():
    return {"X-User-Id": "usr_emp_alpha_1"}


@pytest.fixture
def emp_alpha_2_headers():
    return {"X-User-Id": "usr_emp_alpha_2"}


@pytest.fixture
def mgr_beta_headers():
    return {"X-User-Id": "usr_mgr_beta"}


@pytest.fixture
def emp_beta_headers():
    return {"X-User-Id": "usr_emp_beta_1"}
