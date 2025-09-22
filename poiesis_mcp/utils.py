"""Utils for poiesis_mcp."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseWithMessage(BaseModel, Generic[T]):  # noqa: UP046
    """Response with message."""

    message: str
    data: T
