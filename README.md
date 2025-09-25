# Poiesis MCP Server

A Model Context Protocol (MCP) server that provides seamless access to GA4GH
Task Execution Service (TES) functionality. This server enables AI assistants
and LLMs to create, monitor, and manage computational tasks through a
TES-compliant service.

## Prerequisites

- Access to a GA4GH TES-compliant service, Check out Poiesis.
- MCP clients like Claude, Gemini etc.

## Installation

TBA.

tl;dr: Either install `poiesis_mcp` or use its Docker image to start the server.

## Configuration

Configure the server using environment variables:

### Required Configuration

- `TES_URL`: The base URL of your TES service (e.g., `https://tes.example.com`)
- `TES_TOKEN`: Authentication token for the TES service

### Optional Configuration

- `TES_REQUEST_TIMEOUT`: HTTP request timeout in seconds (default: 60)
- `TES_MAX_RETRIES`: Maximum number of retry attempts (default: 3)
- `TES_BACKOFF_FACTOR`: Backoff factor for retries (default: 1.0)
- `MCP_HOST`: Server host address (default: 0.0.0.0)
- `MCP_PORT`: Server port number (default: 8080)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)
- `TASK_POLL_INTERVAL`: Polling interval for task monitoring in seconds
  (default: 5)
- `TASK_POLL_MAX_ATTEMPTS`: Maximum polling attempts (default: 120)
