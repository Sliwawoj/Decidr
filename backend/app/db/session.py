from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base


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

    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
