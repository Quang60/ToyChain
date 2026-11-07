from contextlib import ExitStack
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.config import BRANCHES
from app.db import utcnow
from app.models import Outbox, Stock, Inbox, Product, Movement
from app.etl import apply_event
from app.worker import publish_pending, consume_one
from conftest import settings, auth


@pytest.fixture
def cluster():
    with ExitStack() as stack:
        nodes={}
        for node in ["CENTRAL",*BRANCHES]:
            app=create_app(settings(node))
            client=stack.enter_context(TestClient(app))
            nodes[node]=(app,client,auth(client))
        yield nodes


def pump(nodes):
    # Direct event delivery for domain tests; real RabbitMQ is tested separately.
    for _ in range(10):
        count=0
        for node,(app,_,_) in nodes.items():
            with app.state.factory.begin() as db:
                for row in db.scalars(select(Outbox).where(Outbox.sent_at.is_(None)).order_by(Outbox.created_at)):
                    target=nodes[row.target][0]
                    with target.state.factory.begin() as dest:
                        apply_event(dest,row.target,row.payload)
                    row.sent_at=utcnow()
                    count+=1
        if not count:
            break


def stock(nodes,node,pid):
    _,c,h=nodes[node]
    return next(r['quantity'] for r in c.get('/api/stock',headers=h).json() if r['product_id']==pid)


def test_four_branch_consolidation_replay_and_transfer(cluster):
    pump(cluster)
    ca,cc,ch=cluster['CENTRAL']
    for node in BRANCHES:
        _,c,h=cluster[node]
        local=c.get('/api/stock',headers=h).json()
        central=cc.get('/api/stock?branch='+node,headers=ch).json()
        assert [(s['product_id'],s['quantity']) for s in local]==[(s['product_id'],s['quantity']) for s in central]
    a,c,h=cluster['DONG']
    with a.state.factory() as db:
        seed_event=deepcopy(db.scalar(select(Outbox)).payload)
    with ca.state.factory.begin() as db:
        assert not apply_event(db,'CENTRAL',seed_event)
    pid=c.get('/api/products',headers=h).json()[0]['id']
    source_before=stock(cluster,'DONG',pid)
    target_before=stock(cluster,'TAY',pid)
    body={'destination':'TAY','lines':[{'product_id':pid,'quantity':3}]}
    headers={**h,'Idempotency-Key':str(uuid4())}
    response=c.post('/api/transfers',headers=headers,json=body)
    assert response.status_code==201,response.text
    transfer=response.json()
    assert c.post('/api/transfers',headers=headers,json=body).json()['id']==transfer['id']
    pump(cluster)
    _,dest,dh=cluster['TAY']
    for _ in range(2):
        assert dest.post('/api/transfers/'+transfer['id']+'/receive',headers=dh).status_code==200
    pump(cluster)
    assert stock(cluster,'DONG',pid)==source_before-3
    assert stock(cluster,'TAY',pid)==target_before+3
    assert c.get('/api/transfers',headers=h).json()[0]['status']=='received'
    assert c.get('/api/transfers',headers=h).json()[0]['received_by']=='admin'
    central_stock=cc.get('/api/stock',headers=ch).json()
    assert sum(r['quantity'] for r in central_stock if r['product_id']==pid)==sum(stock(cluster,node,pid) for node in BRANCHES)


def test_catalog_version_and_user_distribution(cluster):
    _,c,h=cluster['CENTRAL']
    data={'sku':'NEW-001','name':'Sản phẩm thử','category':'Giáo dục','price':199000}
    p=c.post('/api/products',json=data,headers=h).json()
    pump(cluster)
    for node in BRANCHES:
        app,client,headers=cluster[node]
        assert any(v['id']==p['id'] for v in client.get('/api/products',headers=headers).json())
    assert c.put('/api/products/'+p['id'],json={**data,'price':250000},headers=h).status_code==200
    pump(cluster)
    app=cluster['DONG'][0]
    with app.state.factory.begin() as db:
        old={'id':str(uuid4()),'source':'CENTRAL','type':'product.updated','version':1,'data':p}
        apply_event(db,'DONG',old)
        assert db.get(Product,p['id']).price==250000
    assert c.post('/api/users',headers=h,json={'username':'staff.new','name':'Nhân viên mới','password':'NewPassword2026!','role':'cashier','branch_id':'BAC'}).status_code==201
    pump(cluster)
    assert cluster['BAC'][1].post('/api/auth/login',json={'username':'staff.new','password':'NewPassword2026!'}).status_code==200
    assert cluster['DONG'][1].post('/api/auth/login',json={'username':'staff.new','password':'NewPassword2026!'}).status_code==401


def test_failed_publish_keeps_outbox(branch):
    _,app,_=branch
    class BrokerDown:
        def basic_publish(self,**kwargs):
            raise ConnectionError('broker unavailable')
    with pytest.raises(ConnectionError):
        publish_pending(app.state.factory,BrokerDown())
    with app.state.factory() as db:
        assert all(row.sent_at is None for row in db.scalars(select(Outbox)))


def test_ack_happens_after_commit(branch,central):
    import json
    _,source,_=branch
    _,target,_=central
    with source.state.factory() as db:
        event=db.scalar(select(Outbox)).payload
    class Channel:
        acked=False
        def basic_get(self,**kwargs):
            return type('Method',(),{'delivery_tag':1})(),None,json.dumps(event).encode()
        def basic_ack(self,tag):
            with target.state.factory() as db:
                assert db.get(Inbox,event['id']) is not None
            self.acked=True
    channel=Channel()
    consume_one(target.state.factory,channel,'CENTRAL')
    assert channel.acked


def test_wrong_branch_event_rejected(branch,central):
    _,source,_=branch
    _,target,_=central
    with source.state.factory() as db:
        event=deepcopy(db.scalar(select(Outbox)).payload)
    event['data']['transaction']['branch_id']='BAC'
    with pytest.raises(ValueError),target.state.factory.begin() as db:
        apply_event(db,'CENTRAL',event)
