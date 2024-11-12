from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from models import Base  # Імпорт основного класу моделей
import os

# Ця частина налаштовує логування з файлу alembic.ini
config = context.config
fileConfig(config.config_file_name)

# Додавання основного класу моделей для автогенерації міграцій
target_metadata = Base.metadata

# Підключення до бази даних через sqlalchemy.url з файлу конфігурації alembic.ini
def get_url():
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

def run_migrations_offline():
    """Запускає міграції в 'offline' режимі."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"}
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Запускає міграції в 'online' режимі."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url()
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
