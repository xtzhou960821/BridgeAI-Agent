"""Explicit PostgreSQL migration command for local V0.2 development."""

from __future__ import annotations

from pathlib import Path

from backend.app.repositories.postgres.connection import connect, get_database_url


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def apply_migrations(
    database_url: str,
    migrations_dir: Path | None = None,
) -> list[str]:
    """Apply unapplied SQL files in filename order and return their names."""

    directory = MIGRATIONS_DIR if migrations_dir is None else migrations_dir
    applied_now: list[str] = []
    with connect(database_url) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS bridgeai_schema_migrations ("
            "filename TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
            ")",
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT filename FROM bridgeai_schema_migrations",
            ).fetchall()
        }
        for path in sorted(directory.glob("*.sql")):
            if path.name in applied:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO bridgeai_schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
            applied_now.append(path.name)
    return applied_now


def main() -> None:
    """Apply migrations using BRIDGEAI_DATABASE_URL."""

    database_url = get_database_url()
    if not database_url:
        raise SystemExit("BRIDGEAI_DATABASE_URL is required")
    for filename in apply_migrations(database_url):
        print(f"applied {filename}")


if __name__ == "__main__":
    main()
