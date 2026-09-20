from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


def ensure_schema(engine):
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    with engine.begin() as connection:
        if inspector.has_table("gmail_connection"):
            columns = {column["name"] for column in inspector.get_columns("gmail_connection")}
            if "connected_at" not in columns:
                connection.execute(text("ALTER TABLE gmail_connection ADD COLUMN connected_at DATETIME"))
        if inspector.has_table("decisions"):
            columns = {column["name"] for column in inspector.get_columns("decisions")}
            if "is_demo" not in columns:
                connection.execute(text("ALTER TABLE decisions ADD COLUMN is_demo BOOLEAN DEFAULT 0 NOT NULL"))


def create_database(settings):
    settings.ensure_data_dir()
    options = {"connect_args": {"check_same_thread": False, "timeout": 30}}
    if ":memory:" in settings.database_url:
        options["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **options)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    ensure_schema(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
