"""Tests for local_shazam."""

from local_shazam.exceptions import LocalShazamError, ServiceError


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_service_error_inherits_from_base(self) -> None:
        assert issubclass(ServiceError, LocalShazamError)

    def test_base_error_inherits_from_exception(self) -> None:
        assert issubclass(LocalShazamError, Exception)
