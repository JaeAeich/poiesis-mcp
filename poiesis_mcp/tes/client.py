"""TES client."""

import logging
from uuid import UUID

from requests import ConnectionError, HTTPError, Session, Timeout
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from poiesis_mcp.constants import get_constants
from poiesis_mcp.tes.models import (
    MinimalTesTask,
    TesCreateTaskResponse,
    TesTask,
    TesView,
)

logger = logging.getLogger(__name__)

constants = get_constants()


class TESClientError(Exception):
    """Base exception for TES client errors."""

    pass


class TESAuthenticationError(TESClientError):
    """Raised when authentication fails."""

    pass


class TESTaskNotFoundError(TESClientError):
    """Raised when a task is not found."""

    pass


class TESServerError(TESClientError):
    """Raised when the TES server returns an error."""

    pass


class PoiesisTesClient:
    """A client for interacting with the GA4GH Task Execution Service (TES) API."""

    def __init__(
        self,
        base_url: str | None = None,
        auth_token: str | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize the TES client.

        Args:
            base_url: The base URL of the TES service. If not provided, uses TES_URL
                environment variable.
            auth_token: Authentication token. If not provided, uses TES_TOKEN
                environment variable.
            timeout: Request timeout in seconds. If not provided, uses
                TES_REQUEST_TIMEOUT environment variable.

        Raises:
            TESClientError: If required configuration is missing.

        """
        self.base_url: str | None = base_url or constants.TES_URL
        self._auth_token: str | None = auth_token or constants.REQUEST_TOKEN
        self._timeout: int = timeout or constants.REQUEST_TIMEOUT

        if not self.base_url:
            raise TESClientError(
                "TES service URL is required. Set TES_URL environment variable or "
                + "provide base_url parameter."
            )

        if not self._auth_token or self._auth_token == "asdf":
            logger.warning(
                "No authentication token provided or using default token. Set "
                + "TES_TOKEN environment variable for secure access."
            )

        # Remove trailing slash from base_url
        self.base_url = self.base_url.rstrip("/")

        self._session: Session = self._create_session()

    def _create_session(self) -> Session:
        """
        Create a requests session with retry strategy and default headers.

        Returns:
            Configured requests session with retry logic.

        """
        session = Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "poiesis-mcp-client/1.0",
            }
        )

        # Add authentication header if token is available
        if self._auth_token:
            session.headers.update({"Authorization": f"Bearer {self._auth_token}"})

        return session

    def create_task(self, task: TesTask) -> TesCreateTaskResponse:
        """
        Submit a task creation request to the TES service.

        Args:
            task: A TesTask model instance representing the task to create.

        Returns:
            TesCreateTaskResponse: The response containing the created task ID and
                metadata.

        Raises:
            TESAuthenticationError: If authentication fails.
            TESServerError: If the TES server returns an error.
            TESClientError: For other client-side errors.

        """
        endpoint = f"{self.base_url}/tasks"
        task_data = task.model_dump(exclude_none=True)

        logger.info(f"Creating task at {endpoint}")
        logger.debug(f"Task payload: {task_data}")

        try:
            response = self._session.post(
                endpoint, json=task_data, timeout=self._timeout
            )

            if response.status_code == 401:
                raise TESAuthenticationError(
                    "Authentication failed. Check your TES_TOKEN."
                )
            elif response.status_code == 403:
                raise TESAuthenticationError(
                    "Access forbidden. Check your permissions."
                )
            elif response.status_code >= 500:
                raise TESServerError(
                    f"TES server error ({response.status_code}): {response.text}"
                )

            response.raise_for_status()

            result = TesCreateTaskResponse.model_validate(response.json())

            if not result.id:
                raise TESClientError(
                    "Task creation succeeded but no task ID was returned."
                )

            logger.info(f"Task created successfully with ID: {result.id}")
            return result

        except HTTPError as e:
            logger.error(f"HTTP error creating task: {e}")
            raise TESServerError(f"Failed to create task: {e}") from e
        except (ConnectionError, Timeout) as e:
            logger.error(f"Network error creating task: {e}")
            raise TESClientError(f"Network error while creating task: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating task: {e}")
            raise TESClientError(f"Unexpected error while creating task: {e}") from e

    def get_task(  # noqa: C901
        self, task_id: UUID | str, view: str | None = None
    ) -> TesTask | MinimalTesTask:
        """
        Retrieve a task from the TES service.

        Args:
            task_id: The ID of the task to retrieve (UUID or string).
            view: The level of detail to retrieve. Options:
                - "MINIMAL": Returns only basic task information
                - "BASIC": Returns task with some additional details (default)
                - "FULL": Returns complete task information including logs

                Each view level includes progressively more information.

        Returns:
            Union[TesTask, MinimalTesTask]: The task data. Returns MinimalTesTask
            for MINIMAL view, TesTask for BASIC and FULL views.

        Raises:
            TESTaskNotFoundError: If the task does not exist.
            TESAuthenticationError: If authentication fails.
            TESServerError: If the TES server returns an error.
            TESClientError: For other client-side errors.

        """
        # Normalize task_id to string
        task_id_str = str(task_id)

        # Set default view if not provided
        if view is None:
            view = TesView.BASIC.value

        # Validate view parameter
        valid_views = [TesView.MINIMAL.value, TesView.BASIC.value, TesView.FULL.value]
        if view not in valid_views:
            raise TESClientError(
                f"Invalid view '{view}'. Must be one of: {', '.join(valid_views)}"
            )

        endpoint = f"{self.base_url}/tasks/{task_id_str}"
        if view:
            endpoint += f"?view={view}"

        logger.info(f"Retrieving task {task_id_str} from {endpoint}")

        try:
            response = self._session.get(endpoint, timeout=self._timeout)

            if response.status_code == 401:
                raise TESAuthenticationError(
                    "Authentication failed. Check your TES_TOKEN."
                )
            elif response.status_code == 403:
                raise TESAuthenticationError(
                    "Access forbidden. Check your permissions."
                )
            elif response.status_code == 404:
                raise TESTaskNotFoundError(f"Task {task_id_str} not found.")
            elif response.status_code >= 500:
                raise TESServerError(
                    f"TES server error ({response.status_code}): {response.text}"
                )

            response.raise_for_status()

            if view == TesView.MINIMAL.value:
                result = MinimalTesTask.model_validate(response.json())
            else:
                result = TesTask.model_validate(response.json())

            logger.info(f"Task {task_id_str} retrieved successfully")
            return result

        except HTTPError as e:
            logger.error(f"HTTP error retrieving task {task_id_str}: {e}")
            raise TESServerError(f"Failed to retrieve task {task_id_str}: {e}") from e
        except (ConnectionError, Timeout) as e:
            logger.error(f"Network error retrieving task {task_id_str}: {e}")
            raise TESClientError(
                f"Network error while retrieving task {task_id_str}: {e}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving task {task_id_str}: {e}")
            raise TESClientError(
                f"Unexpected error while retrieving task {task_id_str}: {e}"
            ) from e

    def health_check(self) -> bool:
        """
        Check if the TES service is accessible.

        Returns:
            bool: True if the service is accessible, False otherwise.

        """
        try:
            endpoint = f"{self.base_url}/service-info"
            response = self._session.get(endpoint, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
