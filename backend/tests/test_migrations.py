from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from app.db import Base
from app.seed import seed
from app.models import Stock
from test_business import first,create,qty


def test_migration_round_trip(tmp_path,monkeypatch):
    url='sqlite:///'+str(tmp_path/'migration.db')
    monkeypatch.setenv('DATABASE_URL',url)
    config=Config('alembic.ini')
    command.upgrade(config,'head')
    engine=create_engine(url)
    inspector=inspect(engine)
    assert set(Base.metadata.tables).issubset(inspector.get_table_names())
    for name,table in Base.metadata.tables.items():
        assert {c.name for c in table.columns}=={c['name'] for c in inspector.get_columns(name)}
    engine.dispose()
    command.downgrade(config,'base')
    command.upgrade(config,'head')


def test_restart_seed_does_not_replenish_sold_stock(branch):
    c,app,h=branch
    pid=first(c,h)['id']
    create(c,h,pid,2)
    before=qty(c,h,pid)
    with app.state.factory.begin() as db:
        seed(db,app.state.settings)
    assert qty(c,h,pid)==before
