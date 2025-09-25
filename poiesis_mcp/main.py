"""Main entry point for the Poiesis MCP server."""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from poiesis_mcp.constants import get_constants
from poiesis_mcp.tools.create_task import create_task
from poiesis_mcp.tools.get_task import get_task
from poiesis_mcp.tools.wait import wait_for_task


# Configure logging with more detailed format
def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging for the MCP server."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter with more context
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d]\
        - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def validate_environment() -> tuple[bool, list[str]]:
    """
    Validate that the environment is properly configured.

    Returns:
        Tuple of (is_valid, error_messages)

    """
    constants = get_constants()
    errors = constants.validate_config()

    if errors:
        return False, errors

    # Additional runtime checks
    try:
        from poiesis_mcp.tes.client import PoiesisTesClient

        client = PoiesisTesClient()

        # Test connectivity (optional check)
        if constants.TES_URL:
            is_healthy = client.health_check()
            if not is_healthy:
                errors.append(f"TES service at {constants.TES_URL} is not accessible.")
    except Exception as e:
        errors.append(f"Failed to initialize TES client: {e}")

    return len(errors) == 0, errors


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    constants = get_constants()

    # Enhanced server description with usage guidance
    instructions = """
A Poiesis MCP server that provides access to GA4GH Task Execution Service (TES)
functionality.

This server enables you to:
- Create computational tasks with containerized workflows
- Monitor task execution progress with intelligent polling
- Retrieve detailed task information including logs and outputs
- Handle task failures with comprehensive error information

USAGE PATTERNS:

1. **Basic Task Execution:**
   - Use create_tes_task to submit a new computational task
   - Use wait_for_task_completion to monitor progress
   - Use get_tes_task with view='FULL' to retrieve results

2. **Task Monitoring:**
   - Use wait_for_task_completion for intelligent progress monitoring
   - Follow the next_action guidance in responses
   - Use adaptive polling intervals for efficient resource usage

3. **Debugging Failed Tasks:**
   - Always use get_tes_task with view='FULL' for failed tasks
   - Examine logs section for detailed error information
   - Check resource requirements if tasks fail to start

4. **Best Practices:**
   - Provide meaningful task names and descriptions
   - Specify appropriate resource requirements (CPU, memory, disk)
   - Use proper input/output file specifications with valid URLs
   - Monitor long-running tasks and notify users of delays

The server handles authentication, retries, and error cases automatically.
All tools provide structured responses with clear guidance for next steps.
""".strip()

    # Create server with improved configuration
    server = FastMCP(
        name="Poiesis TES MCP Server",
        instructions=instructions,
        tools=[create_task, wait_for_task, get_task],
        host=constants.MCP_HOST,
        port=constants.MCP_PORT,
    )

    return server


def main() -> None:
    """Entry point for the Poiesis TES MCP server."""
    try:
        # Initialize configuration
        constants = get_constants()

        # Setup logging
        setup_logging(constants.LOG_LEVEL)
        logger = logging.getLogger(__name__)

        logger.info("Starting Poiesis TES MCP Server")
        logger.info("=" * 50)

        # Log configuration (with sensitive data masked)
        config = constants.get_masked_config()
        logger.info("Server Configuration:")
        for key, value in config.items():
            logger.info(f"  {key}: {value}")

        # Validate environment
        logger.info("Validating environment configuration...")
        is_valid, errors = validate_environment()

        if not is_valid:
            logger.error("Environment validation failed:")
            for error in errors:
                logger.error(error)

            logger.error("Please fix the above issues before starting the server.")
            logger.error("See the README.md for configuration instructions.")
            sys.exit(1)

        logger.info("Environment validation successful")

        # Create and start server
        logger.info(f"Creating MCP server on {constants.MCP_HOST}:{constants.MCP_PORT}")
        server = create_mcp_server()

        logger.info("Server starting...")
        logger.info(f"TES Service: {constants.TES_URL}")
        logger.info(
            "Available tools: create_tes_task, wait_for_task_completion, get_tes_task"
        )
        logger.info("=" * 50)

        # Start the server (this blocks)
        server.run()

    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Received shutdown signal (Ctrl+C)")
        logger.info("Shutting down Poiesis TES MCP Server...")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to start server: {e}", exc_info=True)
        logger.error("Please check your configuration and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
