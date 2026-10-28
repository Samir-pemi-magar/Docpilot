from __future__ import annotations

import pymupdf

from app.auth.security import hash_password
from app.models.evaluation_dataset import EvaluationDataset
from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun
from app.models.membership import Membership
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


async def create_dataset(client, token: str, organization_id, name: str):
    response = await client.post(
        f"/organizations/{organization_id}/evaluation-datasets",
        json={"name": name, "description": "PDF export test"},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_download_evaluation_pdf_contains_saved_run_and_results(
    client, db_session
):
    owner = await create_user(
        db_session, "eval-pdf-owner@example.com", "PDF Report Owner"
    )
    organization = await create_organization(
        db_session, owner.id, "PDF Report Org", "pdf-report-org"
    )
    token = await login(client, owner.email)

    dataset_data = await create_dataset(
        client, token, organization.id, "Admissions Benchmark"
    )
    dataset_id = dataset_data["id"]

    run = EvaluationRun(
        dataset_id=dataset_id,
        started_by_user_id=owner.id,
        status="completed",
        total_cases=1,
        completed_cases=1,
        failed_cases=0,
        metrics={
            "hit_rate_at_k": 1.0,
            "recall_at_k": 0.75,
            "reciprocal_rank": 0.5,
            "top_k": 5,
        },
    )
    db_session.add(run)
    await db_session.flush()

    db_session.add(
        EvaluationResult(
            run_id=run.id,
            question_snapshot="What is the admissions deadline?",
            reference_answer_snapshot="Applications close on 30 June.",
            case_metadata_snapshot={"category": "admissions"},
            actual_answer="The deadline is 30 June.",
            retrieved_sources=[
                {
                    "document_name": "Admissions Handbook",
                    "chunk_index": 2,
                    "text": "Applications must be submitted by 30 June.",
                }
            ],
            metrics={
                "hit_rate_at_k": 1.0,
                "recall_at_k": 1.0,
                "reciprocal_rank": 1.0,
            },
            status="completed",
            duration_ms=425,
        )
    )
    await db_session.flush()

    response = await client.get(
        f"/organizations/{organization.id}/evaluation-datasets/"
        f"{dataset_id}/runs/{run.id}/pdf",
        headers=auth(token),
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment;" in response.headers["content-disposition"]
    assert f"docpilot-evaluation-{run.id}.pdf" in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF")

    document = pymupdf.open(stream=response.content, filetype="pdf")
    try:
        extracted_text = "\n".join(page.get_text() for page in document)
    finally:
        document.close()

    for expected in (
        "DocPilot",
        "Evaluation report",
        "Admissions Benchmark",
        str(run.id),
        "completed",
        "Aggregate metrics",
        "hit rate at k",
        "What is the admissions deadline?",
        "Applications close on 30 June.",
        "The deadline is 30 June.",
        "Admissions Handbook",
        "Applications must be submitted by 30 June.",
        "admissions",
    ):
        assert expected.lower() in extracted_text.lower(), (
            f"Expected {expected!r} in PDF text"
        )


async def test_evaluation_pdf_cannot_be_downloaded_from_another_organization(
    client, db_session
):
    owner = await create_user(
        db_session, "eval-pdf-private-owner@example.com", "Private Report Owner"
    )
    other_user = await create_user(
        db_session, "eval-pdf-other@example.com", "Other Organization User"
    )
    organization = await create_organization(
        db_session, owner.id, "Private Report Org", "private-report-org"
    )
    other_organization = await create_organization(
        db_session,
        other_user.id,
        "Other Report Org",
        "other-report-org",
    )
    owner_token = await login(client, owner.email)
    other_token = await login(client, other_user.email)

    dataset_data = await create_dataset(
        client, owner_token, organization.id, "Private Benchmark"
    )
    run = EvaluationRun(
        dataset_id=dataset_data["id"],
        started_by_user_id=owner.id,
        status="completed",
        total_cases=0,
        completed_cases=0,
        failed_cases=0,
        metrics={},
    )
    db_session.add(run)
    await db_session.flush()

    response = await client.get(
        f"/organizations/{other_organization.id}/evaluation-datasets/"
        f"{dataset_data['id']}/runs/{run.id}/pdf",
        headers=auth(other_token),
    )

    assert response.status_code == 404
