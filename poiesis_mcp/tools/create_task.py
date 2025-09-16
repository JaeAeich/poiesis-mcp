"""Tool for creating tasks in the TES (Task Execution Service)."""

import logging

from mcp.server.fastmcp.tools import Tool

from poiesis_mcp.tes.client import (
    PoiesisTesClient,
    TESAuthenticationError,
    TESClientError,
    TESServerError,
)
from poiesis_mcp.tes.models import TesCreateTaskResponse, TesTask

logger = logging.getLogger(__name__)


def create_task_logic(
    task: TesTask,
) -> TesCreateTaskResponse:
    """
    Create a new computational task in the TES (Task Execution Service).

    This function submits a task to the TES service for execution. The task will be
    queued and executed according to the provided specifications including Docker
    containers, input/output files, and resource requirements.

    Args:
        task: A TesTask object containing the complete task specification including:
            - name: A descriptive name for the task
            - description: Optional detailed description
            - executors: List of commands/containers to execute
            - inputs: Input files to be mounted in the container
            - outputs: Output files to be collected after execution
            - resources: CPU, memory, and storage requirements
            - volumes: Shared directories between executors

    Returns:
        Dict containing:
            - response: Response from TES which would contain the task ID
            - message: Instruction for waiting for task completion

    Raises:
        ValueError: If task creation fails for any reason, with a clear error message

    """
    try:
        # Validate task has required fields
        if not task.executors:
            raise ValueError(
                "Task must have at least one executor. Please provide a list of "
                + "executors with commands to run."
            )

        # Log task creation attempt
        task_name = task.name or "Unnamed Task"
        logger.info(f"Creating task: {task_name}")
        logger.debug(f"Task specification: {task.model_dump_json(indent=2)}")

        # Create TES client and submit task
        client = PoiesisTesClient()
        response_data = client.create_task(task)

        if not response_data.id:
            raise ValueError(
                "Task was submitted but no task ID was returned from the TES service."
                + "This indicates a server-side issue."
            )

        return TesCreateTaskResponse.model_validate(response_data)

    except TESAuthenticationError as e:
        error_msg = f"Authentication failed when creating task: {e}. Please check your "
        "TES_TOKEN environment variable and ensure you have permission to create tasks."
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except TESServerError as e:
        error_msg = f"TES server error when creating task: {e}. The TES service may be "
        "experiencing issues. You may want to retry this operation."
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except TESClientError as e:
        error_msg = f"Client error when creating task: {e}. Please check your task "
        "specification and network connectivity."
        logger.error(error_msg)
        raise ValueError(error_msg) from e

    except Exception as e:
        error_msg = f"Unexpected error creating task '{task.name or 'Unnamed'}': {e}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e


create_task = Tool.from_function(
    fn=create_task_logic,
    name="create_tes_task",
    title="Create TES Computational Task",
    description="""
Creates a new computational task using the GA4GH Task Execution Service (TES).

**When to use this tool:**
- When you need to execute computational workflows or analyses
- When processing data that requires specific software environments
- When running batch jobs that need defined resource allocations

**Required task components:**
- `executors`: At least one executor defining the command(s) to run
- `name`: A descriptive name for the task (recommended)

**After creating a task:**
1. Use `wait_for_task_completion` to monitor progress
2. Use `get_tes_task` with view="FULL" to see logs and detailed status
3. Check outputs once the task completes successfully

**Returns:** Task ID and success confirmation with guidance on next steps.
""".strip(),
    structured_output=True,
)
