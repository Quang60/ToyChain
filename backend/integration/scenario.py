"""Run against the real Compose stack: python -m integration.scenario.

Creates distinctly named test data; never clears existing business data.
"""
import json
import hashlib
import os
import sys
import time
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
import pika
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.config import Settings, BRANCHES
from app.models import Outbox, Inbox

PASSWORD = os.environ["DEMO_PASSWORD"]
BASES = {node: f"http://api-{node.lower()}:8000" for node in ["CENTRAL", *BRANCHES]}
TOKENS = {}
STATE = Path('/tmp/toychain-integration.json')


def call(node, method, path, **kwargs):
    headers = {"Authorization": "Bearer " + TOKENS[node], **kwargs.pop('headers', {})}
    response = httpx.request(method, BASES[node] + '/api' + path, headers=headers, timeout=20, **kwargs)
    response.raise_for_status()
    return response.json()


def wait_for(check, description, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise AssertionError('Timeout: ' + description)


def quantities(node, pid):
    return {row['branch_id']: row['quantity'] for row in call(node,'GET','/stock') if row['product_id']==pid}


def transact(node,pid,quantity,kind='sale',key=None):
    return call(node,'POST','/transactions',json={'kind':kind,'lines':[{'product_id':pid,'quantity':quantity,'unit_price':100000}]},headers={'Idempotency-Key':key or str(uuid4())})


def login_all():
    for node in BASES:
        response=httpx.post(BASES[node]+'/api/auth/login',json={'username':'admin','password':PASSWORD},timeout=20)
        response.raise_for_status()
        TOKENS[node]=response.json()['access_token']


def pause_sync(node):
    call(node, 'POST', '/sync/control', json={'enabled': False})
    seen = call(node, 'GET', '/sync')['control']['worker_seen_at']
    wait_for(lambda: call(node, 'GET', '/sync')['control']['worker_seen_at'] != seen,
             'worker observes pause: ' + node)


def publish_payload(channel, payload):
    channel.basic_publish(exchange='toychain', routing_key='CENTRAL',
                          body=json.dumps(payload).encode(), mandatory=True,
                          properties=pika.BasicProperties(delivery_mode=2, message_id=payload['id']))


def event_received(event_id):
    engine = create_engine(Settings().database_url)
    try:
        with Session(engine) as db:
            return db.get(Inbox, event_id) is not None
    finally:
        engine.dispose()


def persistence():
    state=json.loads(STATE.read_text())
    try:
        # The pause itself must survive the central PostgreSQL restart.
        assert call('CENTRAL', 'GET', '/sync')['control']['enabled'] is False
        assert not event_received(state['broker_probe'])
        for node in BRANCHES:
            assert quantities(node,state['product'])==state['quantities'][node]
        assert quantities('CENTRAL',state['product'])=={n:q[n] for n,q in state['quantities'].items()}
        document = next(r for r in call('CENTRAL','GET','/documents') if r['id']==state['document'])
        assert document['sha256'] == state['document_sha256']
        download = httpx.get(BASES['CENTRAL']+'/api/documents/'+state['document']+'/download',
                            headers={'Authorization':'Bearer '+TOKENS['CENTRAL']}, timeout=20)
        download.raise_for_status()
        assert hashlib.sha256(download.content).hexdigest() == state['document_sha256']
        print('PASS: PostgreSQL, MongoDB metadata and S3 originals survive full stack restart', flush=True)
    finally:
        call('CENTRAL', 'POST', '/sync/control', json={'enabled': True})
    wait_for(lambda: event_received(state['broker_probe']), 'durable RabbitMQ message after restart')
    assert quantities('CENTRAL', state['product']) == {n:q[n] for n,q in state['quantities'].items()}
    started = datetime.now(timezone.utc)
    for node in BASES:
        def worker_alive():
            seen = call(node, 'GET', '/sync')['control']['worker_seen_at']
            return seen is not None and datetime.fromisoformat(seen) > started
        wait_for(worker_alive, 'worker heartbeat after restart: ' + node)
    print('PASS: queued RabbitMQ event recovered and all five workers resumed', flush=True)


def run():
    login_all()
    if '--check-persistence' in sys.argv:
        persistence()
        return
    suffix=uuid4().hex[:10]
    p=call('CENTRAL','POST','/products',json={'sku':'TEST-'+suffix,'name':'Sản phẩm kiểm thử '+suffix,'category':'Kiểm thử','price':200000})
    pid=p['id']
    for node in BRANCHES:
        wait_for(lambda:any(r['id']==pid for r in call(node,'GET','/products')),'catalog '+node)
        transact(node,pid,10,'purchase')
        key=str(uuid4())
        first=transact(node,pid,2,key=key)
        assert transact(node,pid,2,key=key)['id']==first['id']
    wait_for(lambda:quantities('CENTRAL',pid)=={n:8 for n in BRANCHES},'four branch convergence')
    print('PASS: four branches + request idempotency + real ETL',flush=True)
    # A broker duplicate must have no additional business effect.
    url=create_engine(Settings().database_url).url.set(host='db-dong')
    engine=create_engine(url)
    with Session(engine) as db:
        payload=next(r.payload for r in db.scalars(select(Outbox).where(Outbox.payload.is_not(None)).order_by(Outbox.created_at.desc())) if r.payload.get('data',{}).get('transaction',{}).get('lines',[{}])[0].get('product_id')==pid)
    engine.dispose()
    conn=pika.BlockingConnection(pika.URLParameters(Settings().rabbit_url))
    channel=conn.channel(); channel.confirm_delivery()
    publish_payload(channel, payload)
    # A following event on the same queue proves the duplicate was traversed.
    # It reuses business IDs, so only its new inbox ID should be recorded.
    marker = deepcopy(payload)
    marker['id'] = str(uuid4())
    publish_payload(channel, marker)
    conn.close()
    wait_for(lambda: event_received(marker['id']), 'duplicate and following marker consumed')
    assert quantities('CENTRAL',pid)=={n:8 for n in BRANCHES}
    print('PASS: RabbitMQ duplicate delivery does not change stock twice',flush=True)
    pause_sync('DONG')
    try:
        transact('DONG',pid,1)
        assert quantities('DONG',pid)['DONG']==7
        assert call('DONG','GET','/sync')['pending']>=1
        assert quantities('CENTRAL',pid)['DONG']==8
    finally:
        call('DONG','POST','/sync/control',json={'enabled':True})
    wait_for(lambda:quantities('CENTRAL',pid)['DONG']==7,'offline recovery')
    print('PASS: local operation during synchronization pause and recovery',flush=True)
    transfer=call('DONG','POST','/transfers',json={'destination':'TAY','lines':[{'product_id':pid,'quantity':3}]},headers={'Idempotency-Key':str(uuid4())})
    wait_for(lambda:any(t['id']==transfer['id'] for t in call('TAY','GET','/transfers')),'transfer destination')
    for _ in range(2):
        call('TAY','POST','/transfers/'+transfer['id']+'/receive')
    wait_for(lambda:quantities('CENTRAL',pid)['DONG']==4 and quantities('CENTRAL',pid)['TAY']==11,'transfer reconciliation')
    print('PASS: cross-branch transfer and duplicate receipt',flush=True)
    def sell_concurrently(_):
        response=httpx.post(BASES['BAC']+'/api/transactions',headers={'Authorization':'Bearer '+TOKENS['BAC'],'Idempotency-Key':str(uuid4())},json={'kind':'sale','lines':[{'product_id':pid,'quantity':3}]},timeout=30)
        return response.status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses=list(pool.map(sell_concurrently,range(5)))
    assert statuses.count(201)==2 and statuses.count(409)==3,statuses
    assert quantities('BAC',pid)['BAC']==2
    print('PASS: PostgreSQL concurrent stock locking prevents overselling',flush=True)
    text='Chứng nhận an toàn đồ chơi '+suffix
    document=call('CENTRAL','POST','/documents',files={'file':('chung-nhan.txt',text.encode(),'text/plain')},data={'branch_id':'DONG','product_id':pid})
    wait_for(lambda:any(d['id']==document['id'] and d['status']=='ready' for d in call('CENTRAL','GET','/documents')),'document ETL')
    found=call('CENTRAL','GET','/search',params={'q':suffix})
    assert any(v['id']==pid and v['documents'] for v in found['products'])
    download=httpx.get(BASES['CENTRAL']+'/api/documents/'+document['id']+'/download',headers={'Authorization':'Bearer '+TOKENS['CENTRAL']},timeout=10)
    assert download.content==text.encode()
    other=httpx.post(BASES['CENTRAL']+'/api/auth/login',json={'username':'ql.tay','password':PASSWORD}).json()['access_token']
    denied=httpx.get(BASES['CENTRAL']+'/api/documents/'+document['id']+'/download',headers={'Authorization':'Bearer '+other})
    assert denied.status_code==404
    print('PASS: MongoDB/S3 document ETL + unified search + branch permissions',flush=True)
    expected={node:quantities(node,pid) for node in BRANCHES}
    wait_for(lambda:quantities('CENTRAL',pid)=={n:q[n] for n,q in expected.items()},'final convergence')
    # Leave one persistent event unconsumed in the real central queue through restart.
    pause_sync('CENTRAL')
    try:
        probe = deepcopy(payload)
        probe['id'] = str(uuid4())
        conn = pika.BlockingConnection(pika.URLParameters(Settings().rabbit_url))
        try:
            channel = conn.channel()
            channel.confirm_delivery()
            publish_payload(channel, probe)
        finally:
            conn.close()
        assert not event_received(probe['id'])
        STATE.write_text(json.dumps({'product':pid,'document':document['id'],
                                    'document_sha256':hashlib.sha256(text.encode()).hexdigest(),
                                    'quantities':expected,'broker_probe':probe['id']}))
    except BaseException:
        call('CENTRAL', 'POST', '/sync/control', json={'enabled': True})
        raise
    print('PASS: live scenarios; restart recovery is pending. Central sync is paused for the restart test.',flush=True)


if __name__=='__main__':
    run()
