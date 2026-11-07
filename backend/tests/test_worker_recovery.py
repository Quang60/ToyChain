import json
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models import DeadLetter, Inbox, Outbox
from app.worker import consume_one


class Channel:
    def __init__(self, bodies, on_ack=lambda tag: None):
        self.bodies = list(bodies)
        self.acked = []
        self.on_ack = on_ack

    def basic_get(self, **kwargs):
        if not self.bodies:
            return None, None, None
        return SimpleNamespace(delivery_tag=len(self.acked) + 1), None, self.bodies.pop(0)

    def basic_ack(self, tag):
        self.on_ack(tag)
        self.acked.append(tag)


@pytest.mark.parametrize('body', [b'null', b'[]', b'"text"', b'123', b'true', b'{broken'], ids=['null', 'list', 'string', 'number', 'boolean', 'invalid-json'])
def test_malformed_message_is_committed_before_ack_and_next_message_runs(branch, central, body):
    _, source, _ = branch
    _, target, _ = central
    with source.state.factory() as db:
        valid = deepcopy(db.scalar(select(Outbox)).payload)

    def verify_commit(tag):
        with target.state.factory() as db:
            if tag == 1:
                dead = db.scalar(select(DeadLetter))
                assert dead and dead.payload['raw'] == body.decode()
                assert dead.reason and dead.retried_at is None
            else:
                assert db.get(Inbox, valid['id']) is not None

    channel = Channel([body, json.dumps(valid).encode()], verify_commit)
    assert consume_one(target.state.factory, channel, 'CENTRAL')
    assert consume_one(target.state.factory, channel, 'CENTRAL')
    assert not consume_one(target.state.factory, channel, 'CENTRAL')
    assert channel.acked == [1, 2]


@pytest.mark.parametrize('field,value', [('id', []), ('id', ''), ('id', 'x' * 37), ('data', None), ('data', []), ('type', None), ('source', 'UNKNOWN'), ('version', True)])
def test_invalid_envelope_is_quarantined_without_business_effects(branch, central, field, value):
    _, source, _ = branch
    client, target, headers = central
    with source.state.factory() as db:
        payload = deepcopy(db.scalar(select(Outbox)).payload)
    payload[field] = value
    before = client.get('/api/stock', headers=headers).json()
    channel = Channel([json.dumps(payload).encode()])
    assert consume_one(target.state.factory, channel, 'CENTRAL')
    assert channel.acked == [1]
    assert client.get('/api/stock', headers=headers).json() == before
    with target.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(Inbox)) == 0
        assert db.scalar(select(DeadLetter)).payload == payload


@pytest.mark.parametrize('body', [b'null', b'{"version":1,"source":"DONG","id":"event-1","type":"transaction.created","data":{}}'], ids=['dead-letter-db-down', 'business-db-down'])
def test_database_outage_does_not_ack_or_discard_message(body):
    class UnavailableDatabase:
        @contextmanager
        def begin(self):
            raise OperationalError('connect', {}, ConnectionError('database offline'))
            yield

    channel = Channel([body])
    with pytest.raises(OperationalError):
        consume_one(UnavailableDatabase(), channel, 'CENTRAL')
    assert channel.acked == []


def test_dead_letter_commit_failure_does_not_ack(central):
    _, target, _ = central

    class CommitFailure:
        @contextmanager
        def begin(self):
            with target.state.factory.begin() as db:
                yield db
                raise OperationalError('commit', {}, ConnectionError('connection lost'))

    channel = Channel([b'null'])
    with pytest.raises(OperationalError):
        consume_one(CommitFailure(), channel, 'CENTRAL')
    assert not channel.acked
    with target.state.factory() as db:
        assert db.scalar(select(func.count()).select_from(DeadLetter)) == 0
