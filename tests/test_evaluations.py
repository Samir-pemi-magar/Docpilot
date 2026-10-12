from __future__ import annotations

import json

from app.auth.security import hash_password
from app.embeddings.dependencies import get_embedding_provider
from app.embeddings.models import BatchEmbeddingResult, EmbeddingResult
from app.main import app
from app.services.evaluation_runner import get_evaluation_llm_client
from app.models.membership import Membership
from app.models.evaluation_dataset import EvaluationDataset
from app.models.evaluation_run import EvaluationRun
from app.models.organization import Organization
from app.models.user import User


PASSWORD = "TestPassword123!"


async def create_user(db_session, email: str, full_name: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        full_name=full_name,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def create_organization(db_session, owner_id, name: str, slug: str):
    organization = Organization(name=name, slug=slug)
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=owner_id,
            role="owner",
        )
    )
    await db_session.flush()
    return organization


async def login(client, email: str) -> str:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_dataset(client, token: str, organization_id, name="Admissions QA"):
    return await client.post(
        f"/organizations/{organization_id}/evaluation-datasets",
        json={"name": name, "description": "Admissions questions"},
        headers=auth(token),
    )


async def test_dataset_and_case_crud(client, db_session):
    owner = await create_user(db_session, "eval-owner@example.com", "Eval Owner")
    organization = await create_organization(
        db_session, owner.id, "Evaluation Org", "evaluation-org"
    )
    token = await login(client, owner.email)

    created = await create_dataset(client, token, organization.id)
    assert created.status_code == 201, created.text
    dataset = created.json()
    assert dataset["name"] == "Admissions QA"
    assert dataset["organization_id"] == str(organization.id)

    listed = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets",
        headers=auth(token),
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [dataset["id"]]

    case_response = await client.post(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}/cases",
        json={
            "question": "  What is the admissions deadline?  ",
            "reference_answer": "  See the admissions notice.  ",
            "metadata": {"category": "admissions"},
        },
        headers=auth(token),
    )
    assert case_response.status_code == 201, case_response.text
    case = case_response.json()
    assert case["question"] == "What is the admissions deadline?"
    assert case["reference_answer"] == "See the admissions notice."
    assert case["position"] == 0
    assert case["metadata"] == {"category": "admissions"}

    second_case = await client.post(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}/cases",
        json={"question": "Which documents are required?"},
        headers=auth(token),
    )
    assert second_case.status_code == 201, second_case.text
    assert second_case.json()["position"] == 1

    cases = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}/cases",
        headers=auth(token),
    )
    assert cases.status_code == 200, cases.text
    assert [item["position"] for item in cases.json()] == [0, 1]

    updated_case = await client.patch(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}/cases/{case['id']}",
        json={"question": "What is the final admissions deadline?"},
        headers=auth(token),
    )
    assert updated_case.status_code == 200, updated_case.text
    assert updated_case.json()["question"] == "What is the final admissions deadline?"

    updated_dataset = await client.patch(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}",
        json={"name": "Updated Admissions QA"},
        headers=auth(token),
    )
    assert updated_dataset.status_code == 200, updated_dataset.text
    assert updated_dataset.json()["name"] == "Updated Admissions QA"

    deleted_case = await client.delete(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}/cases/{case['id']}",
        headers=auth(token),
    )
    assert deleted_case.status_code == 204

    deleted_dataset = await client.delete(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}",
        headers=auth(token),
    )
    assert deleted_dataset.status_code == 204

    missing = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets/{dataset['id']}",
        headers=auth(token),
    )
    assert missing.status_code == 404


async def test_blank_dataset_name_is_rejected(client, db_session):
    owner = await create_user(db_session, "eval-blank@example.com", "Blank Name")
    organization = await create_organization(
        db_session, owner.id, "Blank Org", "blank-evaluation-org"
    )
    token = await login(client, owner.email)

    response = await create_dataset(client, token, organization.id, name="   ")
    assert response.status_code == 422


async def test_non_member_cannot_access_evaluation_datasets(client, db_session):
    owner = await create_user(db_session, "eval-private-owner@example.com", "Owner")
    outsider = await create_user(
        db_session, "eval-outsider@example.com", "Outsider"
    )
    organization = await create_organization(
        db_session, owner.id, "Private Eval Org", "private-evaluation-org"
    )
    token = await login(client, outsider.email)

    response = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets",
        headers=auth(token),
    )
    assert response.status_code == 403


async def test_dataset_isolation_between_organizations(client, db_session):
    owner_a = await create_user(db_session, "eval-org-a@example.com", "Owner A")
    owner_b = await create_user(db_session, "eval-org-b@example.com", "Owner B")
    organization_a = await create_organization(
        db_session, owner_a.id, "Evaluation A", "evaluation-a"
    )
    organization_b = await create_organization(
        db_session, owner_b.id, "Evaluation B", "evaluation-b"
    )
    token_a = await login(client, owner_a.email)
    token_b = await login(client, owner_b.email)

    created = await create_dataset(client, token_a, organization_a.id)
    assert created.status_code == 201, created.text
    dataset_id = created.json()["id"]

    # The second organization cannot read the first organization's dataset.
    response = await client.get(
        f"/organizations/{organization_b.id}/evaluation-datasets/{dataset_id}",
        headers=auth(token_b),
    )
    assert response.status_code == 404



class FakeEvaluationEmbeddingProvider:
    """Deterministic embedding provider for evaluation API tests."""

    def embed_query(self, text: str) -> EmbeddingResult:
        if text == "force embedding failure":
            raise RuntimeError("Simulated embedding failure")

        return EmbeddingResult(
            vector=[0.0] * 1024,
            model="fake-evaluation-model",
            dimension=1024,
        )

    def embed_documents(self, texts) -> BatchEmbeddingResult:
        return BatchEmbeddingResult(
            embeddings=[
                EmbeddingResult(
                    vector=[0.0] * 1024,
                    model="fake-evaluation-model",
                    dimension=1024,
                )
                for _ in texts
            ]
        )


class FakeEvaluationLLM:
    async def generate(self, messages) -> str:
        return "Fake evaluation answer"


async def test_evaluation_run_results_and_failure_filtering(
    client, db_session, monkeypatch
):
    owner = await create_user(
        db_session, "eval-run-owner@example.com", "Evaluation Run Owner"
    )
    organization = await create_organization(
        db_session,
        owner.id,
        "Evaluation Run Org",
        "evaluation-run-org",
    )
    token = await login(client, owner.email)
    headers = auth(token)

    dataset_response = await create_dataset(
        client, token, organization.id, name="Run API Tests"
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    cases_url = (
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/cases"
    )

    for question in ("a question with no matching sources", "force embedding failure"):
        response = await client.post(
            cases_url,
            json={"question": question},
            headers=headers,
        )
        assert response.status_code == 201, response.text

    # Give the successful case explicit ground truth. The failed case must
    # not contribute to the aggregate retrieval metrics.
    import uuid
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.models.evaluation_case import EvaluationCase
    import app.services.evaluation_runner as evaluation_runner

    relevant_document_id = uuid.uuid4()
    successful_case = (
        await db_session.execute(
            select(EvaluationCase).where(
                EvaluationCase.dataset_id == dataset_id,
                EvaluationCase.question == "a question with no matching sources",
            )
        )
    ).scalar_one()
    successful_case.relevant_document_ids = [str(relevant_document_id)]
    await db_session.flush()

    fake_source = SimpleNamespace(
        chunk=SimpleNamespace(
            id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            chunk_index=0,
            text="Fake aggregate retrieval evidence",
        ),
        distance=0.1,
        model="fake-evaluation-model",
        document_id=relevant_document_id,
        document_name="Fake document",
    )

    async def fake_retrieve_chunks(*args, **kwargs):
        return [fake_source]

    monkeypatch.setattr(
        evaluation_runner, "retrieve_hybrid_chunks", fake_retrieve_chunks
    )

    app.dependency_overrides[get_embedding_provider] = (
        lambda: FakeEvaluationEmbeddingProvider()
    )
    app.dependency_overrides[get_evaluation_llm_client] = (
        lambda: FakeEvaluationLLM()
    )

    runs_url = (
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/runs"
    )

    started = await client.post(
        runs_url,
        json={"top_k": 5},
        headers=headers,
    )
    assert started.status_code == 201, started.text

    run = started.json()
    assert run["dataset_id"] == dataset_id
    assert run["status"] == "completed"
    assert run["total_cases"] == 2
    assert run["completed_cases"] == 1
    assert run["failed_cases"] == 1

    # Only the successful case has ground truth and contributes to metrics.
    assert run["metrics"]["retrieval_evaluated_cases"] == 1
    assert run["metrics"]["hit_rate_at_k"] == 1.0
    assert run["metrics"]["recall_at_k"] == 1.0
    assert run["metrics"]["reciprocal_rank"] == 1.0

    run_url = f"{runs_url}/{run['id']}"
    fetched_run = await client.get(run_url, headers=headers)
    assert fetched_run.status_code == 200, fetched_run.text
    assert fetched_run.json()["id"] == run["id"]

    results_url = f"{run_url}/results"
    all_results = await client.get(results_url, headers=headers)
    assert all_results.status_code == 200, all_results.text
    results = all_results.json()
    assert len(results) == 2
    assert {item["status"] for item in results} == {"completed", "failed"}

    completed_only = await client.get(
        results_url,
        params={"include_failures": "false"},
        headers=headers,
    )
    assert completed_only.status_code == 200, completed_only.text
    assert len(completed_only.json()) == 1
    assert completed_only.json()[0]["status"] == "completed"

    failed_only = await client.get(
        results_url,
        params={"include_failures": "true", "limit": 1, "offset": 1},
        headers=headers,
    )
    assert failed_only.status_code == 200, failed_only.text
    assert len(failed_only.json()) == 1

    first_page = await client.get(
        results_url,
        params={"limit": 1, "offset": 0},
        headers=headers,
    )
    second_page = await client.get(
        results_url,
        params={"limit": 1, "offset": 1},
        headers=headers,
    )
    assert first_page.status_code == 200, first_page.text
    assert second_page.status_code == 200, second_page.text
    assert len(first_page.json()) == 1
    assert len(second_page.json()) == 1
    assert first_page.json()[0]["id"] != second_page.json()[0]["id"]

    # A member of another organization must not read this run through
    # a different dataset path.
    other_owner = await create_user(
        db_session, "eval-run-other@example.com", "Other Evaluation Owner"
    )
    other_org = await create_organization(
        db_session,
        other_owner.id,
        "Other Evaluation Org",
        "other-evaluation-run-org",
    )
    other_token = await login(client, other_owner.email)
    other_dataset_response = await create_dataset(
        client, other_token, other_org.id, name="Other Dataset"
    )
    assert other_dataset_response.status_code == 201

    other_dataset_id = other_dataset_response.json()["id"]
    cross_org_url = (
        f"/organizations/{other_org.id}/evaluation-datasets/"
        f"{other_dataset_id}/runs/{run['id']}"
    )
    cross_org_response = await client.get(
        cross_org_url,
        headers=auth(other_token),
    )
    assert cross_org_response.status_code == 404

    # Results must obey the same organization boundary as run details.
    cross_org_results = await client.get(
        f"{cross_org_url}/results",
        headers=auth(other_token),
    )
    assert cross_org_results.status_code == 404

    # Request validation should reject invalid execution options.
    invalid_top_k = await client.post(
        runs_url,
        json={"top_k": 0},
        headers=headers,
    )
    assert invalid_top_k.status_code == 422

    # Pagination bounds should be enforced by FastAPI.
    invalid_limit = await client.get(
        results_url,
        params={"limit": 201},
        headers=headers,
    )
    assert invalid_limit.status_code == 422


def test_retrieval_metrics_use_unique_documents():
    import uuid
    from types import SimpleNamespace

    from app.services.evaluation_runner import _retrieval_metrics

    relevant_document = uuid.uuid4()
    irrelevant_document = uuid.uuid4()

    # Two chunks from the same irrelevant document must count as one
    # document when calculating ranks.
    sources = [
        SimpleNamespace(document_id=irrelevant_document),
        SimpleNamespace(document_id=irrelevant_document),
        SimpleNamespace(document_id=relevant_document),
    ]

    metrics = _retrieval_metrics([str(relevant_document)], sources)

    assert metrics == {
        "hit_rate_at_k": 1.0,
        "recall_at_k": 1.0,
        "reciprocal_rank": 0.5,
    }


def test_retrieval_metrics_are_zero_when_no_relevant_document_is_found():
    import uuid
    from types import SimpleNamespace

    from app.services.evaluation_runner import _retrieval_metrics

    relevant_document = uuid.uuid4()
    retrieved_document = uuid.uuid4()

    metrics = _retrieval_metrics(
        [str(relevant_document)],
        [SimpleNamespace(document_id=retrieved_document)],
    )

    assert metrics == {
        "hit_rate_at_k": 0.0,
        "recall_at_k": 0.0,
        "reciprocal_rank": 0.0,
    }


def test_retrieval_metrics_are_omitted_without_ground_truth():
    from app.services.evaluation_runner import _retrieval_metrics

    assert _retrieval_metrics(None, []) == {}
    assert _retrieval_metrics([], []) == {}



async def test_unexpected_run_error_marks_persisted_run_failed(
    client, db_session, monkeypatch
):
    import uuid

    from sqlalchemy import select

    from app.models.evaluation_case import EvaluationCase
    from app.models.evaluation_run import EvaluationRun
    import app.services.evaluation_runner as evaluation_runner

    owner = await create_user(
        db_session, "eval-recovery-owner@example.com", "Evaluation Recovery Owner"
    )
    organization = await create_organization(
        db_session,
        owner.id,
        "Evaluation Recovery Org",
        "evaluation-recovery-org",
    )
    token = await login(client, owner.email)
    headers = auth(token)

    dataset_response = await create_dataset(
        client, token, organization.id, name="Recovery Test"
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    cases_url = (
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/cases"
    )
    case_response = await client.post(
        cases_url,
        json={"question": "trigger unexpected run-level error"},
        headers=headers,
    )
    assert case_response.status_code == 201, case_response.text

    class FakeEmbeddingProvider:
        def embed_query(self, text):
            from app.embeddings.base import EmbeddingResult

            return EmbeddingResult(
                vector=[0.0] * 1024,
                model="fake-recovery-model",
                dimension=1024,
            )

    class FakeLLM:
        async def generate(self, messages):
            return "Fake answer"

    fake_source = type(
        "FakeSource",
        (),
        {
            "chunk": type(
                "FakeChunk",
                (),
                {
                    "id": uuid.uuid4(),
                    "document_version_id": uuid.uuid4(),
                    "chunk_index": 0,
                    "text": "Evidence to trigger snapshot failure",
                },
            )(),
            "distance": 0.1,
            "model": "fake-recovery-model",
            "document_id": uuid.uuid4(),
            "document_name": "Fake document",
        },
    )()

    async def fake_retrieve_chunks(*args, **kwargs):
        return [fake_source]

    def fail_source_snapshot(item):
        raise RuntimeError("simulated run-level snapshot failure")

    monkeypatch.setattr(
        evaluation_runner, "retrieve_hybrid_chunks", fake_retrieve_chunks
    )
    monkeypatch.setattr(
        evaluation_runner, "_source_snapshot", fail_source_snapshot
    )

    app.dependency_overrides[get_embedding_provider] = (
        lambda: FakeEmbeddingProvider()
    )
    app.dependency_overrides[get_evaluation_llm_client] = lambda: FakeLLM()

    runs_url = (
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/runs"
    )
    response = await client.post(
        runs_url,
        json={"top_k": 5},
        headers=headers,
    )
    assert response.status_code == 201, response.text

    run_data = response.json()
    assert run_data["status"] == "failed"
    assert run_data["error_message"] == (
        "The evaluation run stopped because an unexpected internal "
        "error occurred."
    )

    persisted_run = await db_session.get(
        EvaluationRun, uuid.UUID(run_data["id"])
    )
    assert persisted_run is not None
    assert persisted_run.status == "failed"
    assert persisted_run.completed_at is not None


async def test_evaluation_run_history_is_organization_scoped(
    client, db_session
):
    owner = await create_user(
        db_session, "eval-history-owner@example.com", "History Owner"
    )
    organization_a = await create_organization(
        db_session, owner.id, "History Org A", "history-org-a"
    )
    organization_b = await create_organization(
        db_session, owner.id, "History Org B", "history-org-b"
    )
    token = await login(client, owner.email)

    dataset_a = EvaluationDataset(
        organization_id=organization_a.id,
        created_by_user_id=owner.id,
        name="Org A dataset",
    )
    dataset_b = EvaluationDataset(
        organization_id=organization_b.id,
        created_by_user_id=owner.id,
        name="Org B dataset",
    )
    db_session.add_all([dataset_a, dataset_b])
    await db_session.flush()

    runs_a = [
        EvaluationRun(
            dataset_id=dataset_a.id,
            started_by_user_id=owner.id,
            status="completed",
            total_cases=1,
            completed_cases=1,
            failed_cases=0,
            metrics={"hit_rate_at_k": float(i) / 10},
        )
        for i in range(3)
    ]
    run_b = EvaluationRun(
        dataset_id=dataset_b.id,
        started_by_user_id=owner.id,
        status="completed",
        total_cases=1,
        completed_cases=1,
        failed_cases=0,
        metrics={"hit_rate_at_k": 1.0},
    )
    db_session.add_all([*runs_a, run_b])
    await db_session.flush()

    response_a = await client.get(
        f"/organizations/{organization_a.id}/evaluation-datasets/runs?limit=50",
        headers=auth(token),
    )
    assert response_a.status_code == 200, response_a.text
    history_a = response_a.json()
    assert len(history_a) == 3
    assert {item["id"] for item in history_a} == {
        str(item.id) for item in runs_a
    }
    assert str(run_b.id) not in {item["id"] for item in history_a}

    limited = await client.get(
        f"/organizations/{organization_a.id}/evaluation-datasets/runs?limit=2",
        headers=auth(token),
    )
    assert limited.status_code == 200, limited.text
    assert len(limited.json()) == 2

    response_b = await client.get(
        f"/organizations/{organization_b.id}/evaluation-datasets/runs",
        headers=auth(token),
    )
    assert response_b.status_code == 200, response_b.text
    assert [item["id"] for item in response_b.json()] == [str(run_b.id)]


async def test_evaluation_run_history_requires_organization_access(client):
    response = await client.get(
        "/organizations/00000000-0000-0000-0000-000000000000/"
        "evaluation-datasets/runs"
    )
    assert response.status_code in (401, 403)



async def test_jsonl_import_preserves_benchmark_metadata(client, db_session):
    owner = await create_user(
        db_session, "jsonl-owner@example.com", "JSONL Owner"
    )
    organization = await create_organization(
        db_session, owner.id, "JSONL Org", "jsonl-org"
    )
    token = await login(client, owner.email)
    created = await create_dataset(client, token, organization.id)
    assert created.status_code == 201, created.text
    dataset_id = created.json()["id"]
    headers = auth(token)

    records = [
        {
            "case_id": "FA-04",
            "category": "factual",
            "question": "What is the admissions deadline?",
            "answerable": True,
            "expected_behavior": "Answer from the official notice.",
            "expected_answer": "See the current admissions notice.",
            "relevant_document_ids": ["DOC-003"],
            "context_document_ids": ["DOC-003", "DOC-008"],
            "relevant_sections": ["Application timeline"],
            "essential_facts": [
                {"fact_id": "F1", "statement": "The deadline is in the notice."}
            ],
            "reasoning": "Requires finding the admissions notice.",
            "difficulty": "medium",
            "requires_multiple_documents": False,
            "requires_calculation": False,
            "involves_historical_policy": False,
            "policy_versions": [],
        },
        {
            "case_id": "HV-01",
            "category": "unanswerable",
            "question": "What is the unpublished internal code?",
            "answerable": False,
            "expected_behavior": "State that the information is unavailable.",
            "expected_answer": None,
            "relevant_document_ids": [],
            "essential_facts": [],
        },
    ]
    content = "\n".join(json.dumps(item) for item in records)

    response = await client.post(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/cases/import",
        json={"content": content},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["imported_count"] == 2
    assert len(payload["cases"]) == 2

    first, second = payload["cases"]
    assert first["position"] == 0
    assert second["position"] == 1
    assert first["question"] == records[0]["question"]
    assert first["reference_answer"] == records[0]["expected_answer"]
    assert first["relevant_document_ids"] is None
    assert first["metadata"]["case_id"] == "FA-04"
    assert first["metadata"]["relevant_document_ids"] == ["DOC-003"]
    assert first["metadata"]["context_document_ids"] == ["DOC-003", "DOC-008"]
    assert first["metadata"]["essential_facts"] == records[0]["essential_facts"]
    assert first["metadata"]["policy_versions"] == []
    assert second["metadata"]["answerable"] is False


async def test_jsonl_import_rejects_invalid_file_without_partial_import(
    client, db_session
):
    owner = await create_user(
        db_session, "jsonl-invalid@example.com", "JSONL Invalid"
    )
    organization = await create_organization(
        db_session, owner.id, "JSONL Invalid Org", "jsonl-invalid-org"
    )
    token = await login(client, owner.email)
    created = await create_dataset(client, token, organization.id)
    assert created.status_code == 201, created.text
    dataset_id = created.json()["id"]
    headers = auth(token)
    base = (
        f"/organizations/{organization.id}/evaluation-datasets/{dataset_id}"
    )

    valid_line = json.dumps({
        "case_id": "VALID-01",
        "question": "This case must not be saved if another line is invalid.",
    })
    response = await client.post(
        f"{base}/cases/import",
        json={"content": valid_line + "\n{invalid json"},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert "Line 2" in response.text
    assert "no cases were imported" in response.text.lower()

    listed = await client.get(f"{base}/cases", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


async def test_jsonl_import_rejects_duplicate_case_ids(client, db_session):
    owner = await create_user(
        db_session, "jsonl-duplicate@example.com", "JSONL Duplicate"
    )
    organization = await create_organization(
        db_session, owner.id, "JSONL Duplicate Org", "jsonl-duplicate-org"
    )
    token = await login(client, owner.email)
    created = await create_dataset(client, token, organization.id)
    assert created.status_code == 201, created.text
    dataset_id = created.json()["id"]
    headers = auth(token)
    base = (
        f"/organizations/{organization.id}/evaluation-datasets/{dataset_id}"
    )

    line_one = json.dumps({"case_id": "DUP-01", "question": "First question?"})
    line_two = json.dumps({"case_id": "DUP-01", "question": "Second question?"})
    response = await client.post(
        f"{base}/cases/import",
        json={"content": line_one + "\n" + line_two},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert "duplicate case_id" in response.text.lower()

    listed = await client.get(f"{base}/cases", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json() == []


async def test_delete_all_cases_only_affects_selected_dataset(client, db_session):
    owner = await create_user(
        db_session, "eval-bulk-delete@example.com", "Bulk Delete Owner"
    )
    organization = await create_organization(
        db_session, owner.id, "Bulk Delete Org", "bulk-delete-org"
    )
    token = await login(client, owner.email)

    first_response = await create_dataset(
        client, token, organization.id, name="Dataset to clear"
    )
    second_response = await create_dataset(
        client, token, organization.id, name="Dataset to preserve"
    )
    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text

    first_dataset = first_response.json()
    second_dataset = second_response.json()

    for question in ("Question A", "Question B", "Question C"):
        response = await client.post(
            f"/organizations/{organization.id}/evaluation-datasets/"
            f"{first_dataset['id']}/cases",
            json={"question": question},
            headers=auth(token),
        )
        assert response.status_code == 201, response.text

    preserved_response = await client.post(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{second_dataset['id']}/cases",
        json={"question": "Keep this question"},
        headers=auth(token),
    )
    assert preserved_response.status_code == 201, preserved_response.text

    deleted = await client.delete(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{first_dataset['id']}/cases",
        headers=auth(token),
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted_count": 3}

    remaining_first = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{first_dataset['id']}/cases",
        headers=auth(token),
    )
    assert remaining_first.status_code == 200, remaining_first.text
    assert remaining_first.json() == []

    remaining_second = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{second_dataset['id']}/cases",
        headers=auth(token),
    )
    assert remaining_second.status_code == 200, remaining_second.text
    assert len(remaining_second.json()) == 1
    assert remaining_second.json()[0]["question"] == "Keep this question"
