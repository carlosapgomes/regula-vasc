"""Root-level pytest fixtures shared across all apps."""

from collections.abc import Iterator

import pytest
from django.test import Client


@pytest.fixture
def client() -> Iterator[Client]:
    """Provide a Django test client."""
    yield Client()
