from alembic import context
from sqlalchemy import text
from app.config import settings
from app.database import metadata, SCHEMA, make_database_engine


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == SCHEMA
    return True


if context.is_offline_mode():
    context.configure(url="postgresql+psycopg://", target_metadata=metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      version_table_schema=SCHEMA)
    with context.begin_transaction():
        context.execute("CREATE SCHEMA IF NOT EXISTS interviewai")
        context.run_migrations()
else:
    if not settings.database_url:
        raise RuntimeError("Set DATABASE_URL in backend/.env before running migrations.")
    engine = make_database_engine(settings.database_url.get_secret_value())
    try:
        with engine.connect() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS interviewai"))
            connection.commit()
            context.configure(connection=connection, target_metadata=metadata,
                              version_table_schema=SCHEMA, include_schemas=True,
                              include_name=include_name)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
