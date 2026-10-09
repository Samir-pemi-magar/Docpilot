from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import ingestion_task


class FakeResult:
    def __init__(self, version):
        self.version = version

    def scalar_one_or_none(self):
        return self.version


class FakeSession:
    def __init__(self, version):
        self.version = version
        self.committed_statuses = []
        self.rollback_count = 0

    async def execute(self, statement):
        return FakeResult(self.version)

    async def commit(self):
        if self.version is not None:
            self.committed_statuses.append(
                self.version.ingestion_status
            )

    async def rollback(self):
        self.rollback_count += 1


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def configure_task(monkeypatch, session):
    monkeypatch.setattr(
        ingestion_task,
        "AsyncSessionLocal",
        lambda: FakeSessionContext(session),
    )
    monkeypatch.setattr(
        ingestion_task,
        "get_storage",
        lambda: object(),
    )
    monkeypatch.setattr(
        ingestion_task,
        "create_document_processor",
        lambda: object(),
    )
    monkeypatch.setattr(
        ingestion_task,
        "get_default_embedding_provider",
        lambda: object(),
    )


@pytest.mark.asyncio
async def test_background_task_completes_ingestion(monkeypatch):
    version = SimpleNamespace(
        id="test-version-id",
        ingestion_status="pending",
    )
    session = FakeSession(version)
    configure_task(monkeypatch, session)

    async def fake_ingest_document_version(**kwargs):
        kwargs["document_version"].ingestion_status = "completed"
        await kwargs["db"].commit()

    monkeypatch.setattr(
        ingestion_task,
        "ingest_document_version",
        fake_ingest_document_version,
    )

    await ingestion_task.process_document_version_background(
        version.id
    )

    assert session.committed_statuses == [
        "processing",
        "completed",
    ]
    assert version.ingestion_status == "completed"
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_background_task_marks_ingestion_failed(monkeypatch):
    version = SimpleNamespace(
        id="test-version-id",
        ingestion_status="pending",
    )
    session = FakeSession(version)
    configure_task(monkeypatch, session)

    async def failing_ingestion(**kwargs):
        raise RuntimeError("Simulated ingestion failure")

    monkeypatch.setattr(
        ingestion_task,
        "ingest_document_version",
        failing_ingestion,
    )

    await ingestion_task.process_document_version_background(
        version.id
    )

    assert session.rollback_count == 1
    assert session.committed_statuses == [
        "processing",
        "failed",
    ]
    assert version.ingestion_status == "failed"


@pytest.mark.asyncio
async def test_background_task_handles_missing_version(monkeypatch):
    session = FakeSession(version=None)
    configure_task(monkeypatch, session)

    await ingestion_task.process_document_version_background(
        "missing-version-id"
    )

    assert session.committed_statuses == []
    assert session.rollback_count == 0
