from alembic import command
from alembic.config import Config
from .config import Settings
from .db import make_db
from .seed import seed


def main():
    settings = Settings()
    settings.validate()
    command.upgrade(Config("alembic.ini"), "head")
    engine, factory = make_db(settings.database_url)
    with factory.begin() as db:
        seed(db, settings)
    engine.dispose()


if __name__ == "__main__":
    main()
