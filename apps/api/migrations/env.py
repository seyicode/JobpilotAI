from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from jobpilot.core.config import get_settings
from jobpilot.db.models import Base
from jobpilot.db.session import sqlalchemy_url

config = context.config
if config.config_file_name and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

# Tests pass an explicit URL; otherwise use DATABASE_URL from settings.
url = config.attributes.get("database_url") or sqlalchemy_url(get_settings().database_url)

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
