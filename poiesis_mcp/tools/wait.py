"""Tool for waiting on TES tasks."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from mcp.server.fastmcp.tools import Tool

from poiesis_mcp.constants import get_constants
from poiesis_mcp.tes.client import (
    PoiesisTesClient,
    TESAuthenticationError,
    TESClientError,
    TESServerError,
    TESTaskNotFoundError,
)
from poiesis_mcp.tes.models import TesState, TesView

logger = logging.getLogger(__name__)
constants = get_constants()


class TaskStatus(Enum):
    """Enumeration of simplified task states for agent guidance."""

    COMPLETED_SUCCESS = "completed_success"
    COMPLETED_FAILED = "completed_failed"
    STILL_RUNNING = "still_running"
    STILL_RUNNING_TIMEOUT = "still_running_timeout"
    CANCELED = "canceled"
    ERROR_STATE = "error_state"
    UNKNOWN_STATE = "unknown_state"


class WaitStrategy(Enum):
    """Enumeration of recommended wait strategies."""

    CONTINUE_WAITING = "continue_waiting"
    CHECK_LOGS = "check_logs"
    NOTIFY_USER = "notify_user"
    SUCCESS_PROCEED = "success_proceed"


def wait_for_task_completion(
    task_id: str, max_wait_minutes: int = 10
) -> dict[str, Any]:
    """
    Monitor a TES task and return a structured status with guidance on next steps.

    This function implements an adaptive polling strategy based on task state and
    duration, providing a clear recommendation for whether to continue waiting,
    inspect results, or notify a user.

    Args:
        task_id: The unique identifier of the task to monitor.
        max_wait_minutes: Maximum time in minutes to wait before recommending
            user notification.

    Returns:
        A dictionary containing a structured status report, including the raw TES
        state, a simplified status, a recommended next action, and a message.

    """
    try:
        if not task_id or not task_id.strip():
            raise ValueError("Task ID cannot be empty.")
        task_id = task_id.strip()

        if max_wait_minutes <= 0:
            max_wait_minutes = 10

        logger.info(f"Checking status of task {task_id}")

        client = PoiesisTesClient()
        task_data = client.get_task(task_id, view=TesView.MINIMAL.value)

        current_state = getattr(task_data, "state", TesState.UNKNOWN.value)
        task_name = getattr(task_data, "name", "Unnamed Task")
        creation_time = getattr(task_data, "creation_time", None)

        duration_minutes = _calculate_task_duration(creation_time)

        status = _analyze_task_status(current_state, duration_minutes, max_wait_minutes)
        check_interval_seconds = _calculate_adaptive_interval(
            current_state, duration_minutes
        )

        logger.info(
            f"Task {task_id} status: {current_state}, duration: "
            + f"{duration_minutes:.1f}min"
        )

        response_payload = _build_response_payload(
            status,
            task_id,
            task_name,
            current_state,
            duration_minutes,
            check_interval_seconds,
            max_wait_minutes,
        )
        return response_payload

    except TESTaskNotFoundError as e:
        raise ValueError(f"Task {task_id} not found.") from e
    except TESAuthenticationError as e:
        raise ValueError("TES authentication failed. Verify credentials.") from e
    except TESServerError as e:
        raise ValueError("TES server error during status check.") from e
    except TESClientError as e:
        raise ValueError(f"Client error checking task {task_id}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error monitoring task {task_id}: {e}", exc_info=True)
        raise ValueError(f"An unexpected error occurred: {e}") from e


def _calculate_task_duration(creation_time: str | None) -> float:
    """Calculate the task's running duration in minutes from an RFC 3339 timestamp."""
    if not creation_time:
        return 0.0
    try:
        # RFC 3339 timestamps ending in 'Z' denote UTC.
        # Replace 'Z' with '+00:00' for compatibility with fromisoformat.
        if creation_time.endswith("Z"):
            creation_time = creation_time[:-1] + "+00:00"
        start_time = datetime.fromisoformat(creation_time)
        duration_seconds = (datetime.now(UTC) - start_time).total_seconds()
        return duration_seconds / 60.0
    except (ValueError, TypeError):
        logger.warning(f"Could not parse creation time: '{creation_time}'")
        return 0.0


def _calculate_adaptive_interval(state: str, duration_minutes: float) -> int:
    """Determine polling interval based on task state and duration."""
    base_interval = constants.TASK_POLL_INTERVAL

    if duration_minutes < 1:
        return max(2, base_interval // 2)

    if state in (TesState.RUNNING.value, TesState.INITIALIZING.value):
        if duration_minutes < 5:
            return base_interval
        elif duration_minutes < 15:
            return base_interval * 2
        else:
            return base_interval * 3
    elif state == TesState.QUEUED.value:
        return base_interval
    elif state in (TesState.UNKNOWN.value, TesState.PAUSED.value):
        return max(3, base_interval // 2)

    return base_interval


def _analyze_task_status(
    state: str, duration_minutes: float, max_wait_minutes: int
) -> TaskStatus:
    """Analyze the raw TES state and duration to determine a simplified status."""
    if state == TesState.COMPLETE.value:
        return TaskStatus.COMPLETED_SUCCESS
    if state in (TesState.EXECUTOR_ERROR.value, TesState.SYSTEM_ERROR.value):
        return TaskStatus.COMPLETED_FAILED
    if state == TesState.CANCELED.value:
        return TaskStatus.CANCELED
    if state in (
        TesState.RUNNING.value,
        TesState.QUEUED.value,
        TesState.INITIALIZING.value,
    ):
        if duration_minutes >= max_wait_minutes:
            return TaskStatus.STILL_RUNNING_TIMEOUT
        return TaskStatus.STILL_RUNNING
    if state in (TesState.PAUSED.value, TesState.PREEMPTED.value):
        return TaskStatus.ERROR_STATE

    return TaskStatus.UNKNOWN_STATE


RESPONSE_TEMPLATES = {
    TaskStatus.COMPLETED_SUCCESS: {
        "should_continue_waiting": False,
        "wait_recommendation": WaitStrategy.SUCCESS_PROCEED.value,
        "next_action": "get_tes_task",
        "message": "Task '{task_name}' completed successfully after "
        + "{duration_minutes:.1f} minutes.",
        "details": "Use get_tes_task with view='FULL' to retrieve outputs and logs.",
    },
    TaskStatus.COMPLETED_FAILED: {
        "should_continue_waiting": False,
        "wait_recommendation": WaitStrategy.CHECK_LOGS.value,
        "next_action": "get_tes_task",
        "message": "Task '{task_name}' failed after {duration_minutes:.1f} minutes.",
        "details": "Use get_tes_task with view='FULL' to examine error logs.",
    },
    TaskStatus.CANCELED: {
        "should_continue_waiting": False,
        "wait_recommendation": WaitStrategy.NOTIFY_USER.value,
        "next_action": None,
        "message": "Task '{task_name}' was canceled after {duration_minutes:.1f}"
        + " minutes.",
        "details": "The task was canceled. Confirm with the user before resubmitting.",
    },
    TaskStatus.STILL_RUNNING: {
        "should_continue_waiting": True,
        "wait_recommendation": WaitStrategy.CONTINUE_WAITING.value,
        "next_action": "wait_for_task_completion",
        "message": "Task '{task_name}' is running ({duration_minutes:.1f} "
        + "min elapsed).",
        "details": "Task is in progress. Check again in {check_interval_seconds} "
        + "seconds.",
    },
    TaskStatus.STILL_RUNNING_TIMEOUT: {
        "should_continue_waiting": True,
        "wait_recommendation": WaitStrategy.NOTIFY_USER.value,
        "next_action": "wait_for_task_completion",
        "message": "Task '{task_name}' running for {duration_minutes:.1f} minutes, "
        + "exceeding threshold of {max_wait_minutes} min.",
        "details": "Task is taking longer than expected. Continue waiting or notify "
        + "user. Next check in {check_interval_seconds} seconds.",
    },
    TaskStatus.ERROR_STATE: {
        "should_continue_waiting": False,
        "wait_recommendation": WaitStrategy.CHECK_LOGS.value,
        "next_action": "get_tes_task",
        "message": "Task '{task_name}' is in an error state ({state}).",
        "details": "Use get_tes_task with view='FULL' to investigate.",
    },
    TaskStatus.UNKNOWN_STATE: {
        "should_continue_waiting": True,
        "wait_recommendation": WaitStrategy.CONTINUE_WAITING.value,
        "next_action": "wait_for_task_completion",
        "message": "Task '{task_name}' is in an unknown state ({state}).",
        "details": "Continue monitoring. Next check in {check_interval_seconds} "
        + "seconds.",
    },
}


def _build_response_payload(
    status: TaskStatus,
    task_id: str,
    task_name: str,
    state: str,
    duration_minutes: float,
    check_interval_seconds: int,
    max_wait_minutes: int,
) -> dict[str, Any]:
    """Construct the final response dictionary from a template."""
    template = RESPONSE_TEMPLATES.get(
        status, RESPONSE_TEMPLATES[TaskStatus.UNKNOWN_STATE]
    )

    format_args = {
        "task_name": task_name,
        "duration_minutes": duration_minutes,
        "check_interval_seconds": check_interval_seconds,
        "max_wait_minutes": max_wait_minutes,
        "state": state,
    }

    assert template is not None
    assert template["message"] is not None
    assert template["details"] is not None

    return {
        "success": True,
        "task_id": task_id,
        "task_name": task_name,
        "status": status.value,
        "state": state,
        "task_duration_minutes": round(duration_minutes, 1),
        "estimated_wait_time": check_interval_seconds,
        "should_continue_waiting": template["should_continue_waiting"],
        "wait_recommendation": template["wait_recommendation"],
        "next_action": template["next_action"],
        "message": template["message"].format(**format_args),  # type: ignore
        "details": template["details"].format(**format_args),  # type: ignore
    }


# Create the MCP tool
wait_for_task = Tool.from_function(
    fn=wait_for_task_completion,
    name="wait_for_task_completion",
    title="Monitor TES Task Progress",
    description="""
Monitor the progress of a TES (Task Execution Service) task and receive intelligent
guidance on next steps.

This tool provides smart task monitoring with adaptive polling intervals, timeout
handling, and contextual recommendations. It helps LLMs efficiently wait for tasks
while providing clearguidance on when to take action or notify users.

**When to use this tool:**
- After creating a task to monitor its execution progress
- When you need to wait for a task to complete before proceeding
- To check if a long-running task needs user attention

**Parameters:**
- `task_id` (required): The unique task identifier to monitor
- `max_wait_minutes` (optional): Minutes to wait before recommending user notification
    (default: 10)
- `check_interval_seconds` (optional): Polling interval in seconds (uses adaptive
    interval if not specified)

**Example Usage Pattern:**
1. Create task with `create_tes_task`
2. Use `wait_for_task_completion` to monitor progress
3. Follow the `next_action` guidance:
   - If "get_tes_task": Retrieve full results and logs
   - If "wait_for_task_completion": Continue monitoring
   - If "notify_user": Inform user of status or delays

**Returns:** Comprehensive status with specific guidance for efficient task monitoring.
""".strip(),
    structured_output=True,
)
