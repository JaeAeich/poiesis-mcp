"""Tool to retrieve detailed information about a TES task."""

import logging

from mcp.server.fastmcp.tools import Tool

from poiesis_mcp.tes.client import (
    PoiesisTesClient,
    TESAuthenticationError,
    TESClientError,
    TESServerError,
    TESTaskNotFoundError,
)
from poiesis_mcp.tes.models import MinimalTesTask, TesState, TesTask
from poiesis_mcp.utils import ResponseWithMessage

logger = logging.getLogger(__name__)


def get_task_logic(
    task_id: str, view: str = "BASIC"
) -> ResponseWithMessage[TesTask | MinimalTesTask]:
    """
    Retrieve detailed information about a TES task.

    This function fetches comprehensive information about a previously created task,
    including its current status, execution logs, resource usage, and output files.
    The level of detail returned depends on the specified view parameter.

    Args:
        task_id: The unique identifier of the task to retrieve. This should be
            the task ID returned from create_tes_task.
        view: The level of detail to return. Options:
            - "MINIMAL": Basic task info (id, name, state, creation_time)
            - "BASIC": Standard info including inputs, outputs, resources (default)
            - "FULL": Complete information including detailed logs and system info

    Returns:
        Dict containing:
            - success: True if task was retrieved successfully
            - task: The task data (structure depends on view level)
            - status_summary: Human-readable status description
            - next_steps: Guidance based on current task state
            - view_used: The view level that was applied

    Raises:
        ValueError: If task retrieval fails, with specific error context

    """
    try:
        # Validate and normalize inputs
        if not task_id or not task_id.strip():
            raise ValueError("Task ID is required and cannot be empty.")

        task_id = task_id.strip()
        view = view.upper().strip() if view else "BASIC"

        # Validate view parameter
        valid_views = ["MINIMAL", "BASIC", "FULL"]
        if view not in valid_views:
            raise ValueError(
                f"Invalid view '{view}'. Must be one of: {', '.join(valid_views)}. "
                + "Use MINIMAL for quick status checks, BASIC for standard info, or "
                + "FULL for complete details including logs."
            )

        logger.info(f"Retrieving task {task_id} with {view} view")

        # Create client and retrieve task
        client = PoiesisTesClient()
        task_data = client.get_task(task_id, view)

        # Extract key information
        state = getattr(task_data, "state", TesState.UNKNOWN.value)
        name = getattr(task_data, "name", "Unnamed Task")
        creation_time = getattr(task_data, "creation_time", "Unknown")

        # Create status summary
        status_summary = _create_status_summary(state, name, creation_time)

        # Generate next steps guidance based on state
        next_steps = _generate_next_steps(state, view)

        # Convert task data to dict for JSON serialization
        task_dict = task_data.model_dump(exclude_none=True)

        message = f"{status_summary}\n{next_steps}"

        if view == "MINIMAL":
            data = MinimalTesTask.model_validate(task_dict)
        else:
            data = TesTask.model_validate(task_dict)

        return ResponseWithMessage(data=data, message=message)

    except TESTaskNotFoundError as e:
        error_msg = (
            f"Task {task_id} not found: {e}. Please verify the task ID is "
            + "correct and the task exists."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except TESAuthenticationError as e:
        error_msg = (
            f"Authentication failed when retrieving task {task_id}: {e}. "
            + "Please check your TES_TOKEN environment variable."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except TESServerError as e:
        error_msg = (
            f"TES server error when retrieving task {task_id}: {e}. The service"
            + " may be experiencing issues."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except TESClientError as e:
        error_msg = (
            f"Client error when retrieving task {task_id}: {e}. Please check "
            + "your network connectivity and task ID format."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except Exception as e:
        error_msg = f"Unexpected error retrieving task {task_id}: {e}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e


def _create_status_summary(state: str, name: str, creation_time: str) -> str:
    """Create a human-readable status summary."""
    state_descriptions = {
        TesState.UNKNOWN.value: "Status is unknown or not yet determined",
        TesState.QUEUED.value: "Task is queued and waiting to start execution",
        TesState.INITIALIZING.value: "Task is being initialized for execution",
        TesState.RUNNING.value: "Task is currently running",
        TesState.PAUSED.value: "Task execution has been paused",
        TesState.COMPLETE.value: "Task completed successfully",
        TesState.EXECUTOR_ERROR.value: "Task failed due to an error in the executor",
        TesState.SYSTEM_ERROR.value: "Task failed due to a system error",
        TesState.CANCELED.value: "Task was canceled",
        TesState.PREEMPTED.value: "Task was preempted by the system",
    }

    state_desc = state_descriptions.get(state, f"Unknown state: {state}")
    return f"Task '{name}' (created {creation_time}): {state_desc}"


def _generate_next_steps(state: str, current_view: str) -> str:
    """Generate contextual guidance based on task state."""
    if state == TesState.COMPLETE.value:
        if current_view != "FULL":
            return (
                "Task completed successfully! Use get_tes_task with view='FULL' to "
                + "see execution logs and output file details."
            )
        else:
            return (
                "Task completed successfully. Check the 'outputs' and 'logs' "
                + "sections for results and execution details."
            )

    elif state in [TesState.EXECUTOR_ERROR.value, TesState.SYSTEM_ERROR.value]:
        if current_view != "FULL":
            return (
                f"Task failed with {state}. Use get_tes_task with view='FULL' to "
                + "see detailed error logs and determine the cause."
            )
        else:
            return (
                "Task failed. Review the 'logs' section for error details. You may "
                + "need to modify the task specification and retry."
            )

    elif state == TesState.CANCELED.value:
        return (
            "Task was canceled. Check with the user if this was intentional, or if "
            + "the task should be recreated."
        )

    elif state in [
        TesState.RUNNING.value,
        TesState.QUEUED.value,
        TesState.INITIALIZING.value,
    ]:
        return (
            f"Task is still {state.lower()}. Use wait_for_task_completion to monitor "
            + "progress, or check again later."
        )

    elif state == TesState.PAUSED.value:
        return (
            "Task is paused. You may need to resume it or check with the TES service"
            + " administrator."
        )

    else:
        return (
            f"Task is in {state} state. Use wait_for_task_completion to monitor for"
            + "changes."
        )


get_task = Tool.from_function(
    fn=get_task_logic,
    name="get_tes_task",
    title="Get TES Task Details",
    description="""
Retrieve detailed information about a TES (Task Execution Service) task.

This tool fetches comprehensive information about a previously created computational
task, including its current execution status, resource usage, input/output files, and
execution logs.

**When to use this tool:**
- Check the current status of a running task
- Retrieve execution logs after task completion or failure
- Get detailed information about task inputs, outputs, and resource usage
- Debug failed tasks by examining error logs
- Verify task configuration and parameters

**Parameters:**
- `task_id` (required): The unique task identifier returned when the task was created
- `view` (optional): Level of detail to retrieve:
  - "MINIMAL": Basic info only (id, name, state, creation time) - fastest
  - "BASIC": Standard details including inputs, outputs, resources - default
  - "FULL": Complete information including detailed execution logs - most comprehensive

**View Level Guide:**
- Use "MINIMAL" for quick status checks when monitoring many tasks
- Use "BASIC" for general task information and standard debugging
- Use "FULL" when you need detailed logs, error information, or output file details

**Returns:** Complete task information with status summary and contextual guidance for
next steps.
""".strip(),
    structured_output=True,
)
