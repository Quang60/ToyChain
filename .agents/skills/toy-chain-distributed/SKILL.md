---
name: toy-chain-distributed
description: Plan and implement the toy store chain management project with distributed branch data and unified structured/unstructured data. Use for architecture, schema, API, implementation, tests, or documentation in this project.
---

# Toy store chain distributed system

Read [KE_HOACH_DU_AN.md](../../../KE_HOACH_DU_AN.md) before making architectural or scope decisions. The approved scope uses four branches DONG, TAY, NAM, BAC plus CENTRAL, React/TypeScript, FastAPI/Python, PostgreSQL, MongoDB, RabbitMQ and S3-compatible storage in Docker Compose. OCR is deferred; extract existing PDF/TXT text and retain image originals. Preserve existing implementation choices consistent with these requirements.

## Non-negotiable project outcomes

- Model multiple branches with local transactional ownership and a consolidated chain view. State the source of truth for each data type.
- Support structured operational records and unstructured files in one workflow through metadata and explicit links to business records. Keep the original files accessible under the same authorization model.
- Make synchronization observable and recoverable: stable IDs, durable event/outbox handling, idempotent consumers, retry behavior, audit trail, and visible synchronization status where stale data matters.
- Define stock movement as explicit business events. Avoid claims of immediate global consistency where the architecture is asynchronous.
- Make branch access boundaries enforceable in APIs and queries. Validate file type/size, storage access, and document extraction failures.

## Working method

For each requested feature, identify affected branch-local records, central records, files, events, and read models. Implement a complete vertical flow with migration, API, UI when applicable, and a focused test of the critical invariant. Update the plan when an agreed decision changes. Keep diagrams and documentation consistent with running behavior.

For demonstrations, use all four branches and test duplicate delivery, temporary disconnection, restart recovery, and eventual reconciliation. Report observed results and any remaining consistency lag or unsupported scenario. SQLite or mocked service tests do not establish PostgreSQL concurrency or broker/storage integration correctness.

## ETL and operational invariants

Write the business change and outbox event in the same PostgreSQL transaction. Mark sent only after broker publisher confirmation; acknowledge consumed messages only after the destination transaction commits. Inbox event IDs prevent duplicate business effects. Use integer VND amounts, positive sale quantities, stock locking, and explicit refund/transfer events. Never silently overwrite stock with an out-of-order snapshot.

Use stable IDs to join PostgreSQL records, MongoDB documents and S3 originals at the API. Record extraction status and errors; image/scan inputs must be marked as requiring OCR, without claiming recognition occurred. Document text cannot create stock movements automatically.

Periodic reconciliation compares branch truth with the consolidated read model and reports drift. Preserve failed events for inspection and deliberate retry. Tests should cover overselling, repeated client requests, excessive refunds, transfer receipt twice, authorization boundaries, and replayed events. Add separate integration checks for real services and document infrastructure prerequisites honestly.

## Project entry points

Read [README.md](../../../README.md) for startup and supported functions and [docs/KIEN_TRUC.md](../../../docs/KIEN_TRUC.md) for ownership and consistency decisions. Run `python scripts/manage.py check` from the project root after relevant code changes; it runs backend pytest and the frontend build. Run `python scripts/manage.py integration` only with the real Docker stack available; it creates TEST-* data and restarts branch services. Maintain [docs/KIEM_THU.md](../../../docs/KIEM_THU.md) with observed outcomes, separating local API tests from real infrastructure and browser checks.
