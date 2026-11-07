import json
import logging
import time
import os
import httpx
import pika
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .config import Settings, BRANCHES, NODES
from .db import make_db, utcnow
from .models import Outbox, Control, DeadLetter, Reconciliation
from .etl import apply_event
from .domain import snapshot
from .documents import DocumentStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("toychain.worker")


def topology(channel):
    channel.exchange_declare(exchange="toychain", exchange_type="direct", durable=True)
    for node in NODES:
        queue = "toychain." + node
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(queue=queue, exchange="toychain", routing_key=node)
    channel.confirm_delivery()
    channel.basic_qos(prefetch_count=1)


def publish_pending(factory, channel):
    with factory.begin() as db:
        rows = db.scalars(select(Outbox).where(Outbox.sent_at.is_(None)).order_by(Outbox.created_at, Outbox.id).limit(100).with_for_update(skip_locked=True)).all()
        for row in rows:
            channel.basic_publish(exchange="toychain", routing_key=row.target, body=json.dumps(row.payload, ensure_ascii=False).encode(), properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, message_id=row.id), mandatory=True)
            row.sent_at = utcnow()
    return len(rows)


def consume_one(factory, channel, node):
    method, _, body = channel.basic_get(queue="toychain." + node, auto_ack=False)
    if not method:
        return False
    payload = None
    try:
        payload = json.loads(body)
        with factory.begin() as db:
            apply_event(db, node, payload)
    except (ValueError, KeyError, TypeError, IntegrityError) as exc:
        with factory.begin() as db:
            db.add(DeadLetter(payload=payload if isinstance(payload, dict) else {"raw": body.decode(errors="replace")[:10000]}, reason=str(exc)[:2000]))
        log.error("Sự kiện được giữ trong dead_letters: %s", str(exc)[:200])
    # Operational DB failures propagate; closing the connection requeues the unacked message.
    channel.basic_ack(method.delivery_tag)
    return True


def reconcile(factory, settings):
    for branch in BRANCHES:
        try:
            endpoint = os.getenv(f"BRANCH_{branch}_URL", f"http://api-{branch.lower()}:8000")
            response = httpx.get(endpoint + "/api/internal/snapshot", headers={"X-Internal-Key": settings.internal_secret}, timeout=4)
            response.raise_for_status()
            source = response.json()
            with factory.begin() as db:
                consolidated = snapshot(db, branch)
                matching = all(source[key] == consolidated[key] for key in consolidated)
                # A live comparison can catch in-flight writes; drift is advisory until quiescent.
                status = "matched" if matching else "pending" if source["pending"] else "difference"
                db.add(Reconciliation(branch_id=branch, status=status, details={"source": source, "central": consolidated}))
        except Exception as exc:
            with factory.begin() as db:
                db.add(Reconciliation(branch_id=branch, status="unreachable", details={"error": str(exc)[:500]}))


def run():
    settings = Settings()
    settings.validate()
    _, factory = make_db(settings.database_url)
    store = DocumentStore(settings) if settings.node == "CENTRAL" else None
    last_reconcile, initialized = 0, False
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(settings.rabbit_url))
            channel = connection.channel()
            topology(channel)
            while connection.is_open:
                with factory.begin() as db:
                    control = db.get(Control, 1)
                    control.worker_seen_at, control.last_error = utcnow(), ""
                    enabled = control.enabled
                if enabled:
                    publish_pending(factory, channel)
                    for _ in range(100):
                        if not consume_one(factory, channel, settings.node):
                            break
                    if store:
                        try:
                            if not initialized:
                                store.initialize()
                                initialized = True
                            for _ in range(5):
                                if not store.process_one():
                                    break
                        except Exception as exc:
                            log.warning("Xử lý tài liệu tạm lỗi: %s", exc)
                            with factory.begin() as db:
                                db.get(Control, 1).last_error = "Kho tài liệu: " + str(exc)[:500]
                        if time.monotonic() - last_reconcile > 60:
                            reconcile(factory, settings)
                            last_reconcile = time.monotonic()
                connection.process_data_events(time_limit=1)
        except Exception as exc:
            log.warning("Worker sẽ thử lại: %s", exc)
            try:
                with factory.begin() as db:
                    db.get(Control, 1).last_error = str(exc)[:1000]
            except Exception:
                pass
            time.sleep(3)
        finally:
            if connection and connection.is_open:
                connection.close()


if __name__ == "__main__":
    run()
