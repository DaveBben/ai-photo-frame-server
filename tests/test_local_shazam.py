"""Tests for local_shazam."""

from local_shazam.exceptions import ConfigurationError, LocalShazamError


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_configuration_error_inherits_from_base(self) -> None:
        assert issubclass(ConfigurationError, LocalShazamError)

    def test_base_error_inherits_from_exception(self) -> None:
        assert issubclass(LocalShazamError, Exception)
