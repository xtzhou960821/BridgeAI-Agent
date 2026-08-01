import pytest

from tests.backend.postgres_test_support import reset_test_tables


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://127.0.0.1:1/bridgeai_agent",
        "postgresql://127.0.0.1:1/bridgeai_agent_test?dbname=bridgeai_agent",
    ],
)
def test_reset_test_tables_refuses_a_database_other_than_test_database(database_url):
    with pytest.raises(RuntimeError, match="bridgeai_agent_test"):
        reset_test_tables(database_url)
