import pytest

from tests.backend.postgres_test_support import reset_test_tables


def test_reset_test_tables_refuses_a_database_other_than_test_database():
    with pytest.raises(RuntimeError, match="bridgeai_agent_test"):
        reset_test_tables("postgresql://127.0.0.1:1/bridgeai_agent")
