from __future__ import annotations

from sqlalchemy import select

from app.db.models import ChatMessage, ChatSession, PublicMessageRequest, PublicSession
from conftest import (
    ALPHA_FACT,
    ALPHA_ORIGIN,
    ALPHA_TITLE,
    BETA_FACT,
    BETA_ORIGIN,
    BETA_TITLE,
    UNAUTHORISED_ORIGIN,
    create_public_session,
    post_widget_message,
    seed_alpha_beta,
)


def get_config(client, widget, *, origin=None, etag: str | None = None):
    headers = {"Origin": origin or widget.origin, "X-Request-ID": f"req-{widget.label}-config"}
    if etag:
        headers["If-None-Match"] = etag
    return client.get(f"/api/v1/widget/{widget.public_key}/config", headers=headers)


def test_config_smoke_origin_etag_and_cache_isolation(client) -> None:
    alpha, beta = seed_alpha_beta(client)

    alpha_response = get_config(client, alpha)
    beta_response = get_config(client, beta)

    assert alpha_response.status_code == 200, alpha_response.text
    assert beta_response.status_code == 200, beta_response.text
    assert alpha_response.json()["widget"]["bot_name"] == alpha.bot_name
    assert beta_response.json()["widget"]["bot_name"] == beta.bot_name
    assert alpha_response.json()["widget"]["bot_name"] != beta_response.json()["widget"]["bot_name"]
    assert alpha_response.headers["vary"] == "Origin"
    assert beta_response.headers["vary"] == "Origin"
    assert alpha_response.headers["etag"] != beta_response.headers["etag"]
    assert "no-store" not in alpha_response.headers["cache-control"]

    alpha_304 = get_config(client, alpha, etag=alpha_response.headers["etag"])
    assert alpha_304.status_code == 304
    assert alpha_304.text == ""

    beta_with_alpha_etag = get_config(client, beta, etag=alpha_response.headers["etag"])
    assert beta_with_alpha_etag.status_code == 200
    assert beta_with_alpha_etag.json()["widget"]["bot_name"] == beta.bot_name

    denied_cross_origin = get_config(client, alpha, origin=BETA_ORIGIN)
    denied_unknown_origin = get_config(client, alpha, origin=UNAUTHORISED_ORIGIN)
    unknown_key = client.get("/api/v1/widget/wpk_dev_unknown_synthetic_b2/config", headers={"Origin": ALPHA_ORIGIN})

    assert denied_cross_origin.status_code == 403
    assert denied_cross_origin.json()["error"]["code"] == "origin_not_allowed"
    assert denied_unknown_origin.status_code == 403
    assert unknown_key.status_code == 404


def test_session_smoke_and_cross_widget_session_isolation(client) -> None:
    alpha, beta = seed_alpha_beta(client)
    alpha_token = create_public_session(client, alpha)
    beta_token = create_public_session(client, beta)

    assert alpha_token != beta_token
    assert alpha_token not in get_config(client, alpha).text

    alpha_wrong_widget = post_widget_message(client, beta, alpha_token, message=BETA_FACT, idempotency_key="idem-alpha-token-beta-route")
    beta_wrong_widget = post_widget_message(client, alpha, beta_token, message=ALPHA_FACT, idempotency_key="idem-beta-token-alpha-route")
    invalid_token = post_widget_message(client, alpha, "pss_dev_invalid.invalid.invalid", message=ALPHA_FACT, idempotency_key="idem-invalid-token-route")

    assert alpha_wrong_widget.status_code == 401
    assert alpha_wrong_widget.json()["error"]["code"] == "invalid_session"
    assert beta_wrong_widget.status_code == 401
    assert beta_wrong_widget.json()["error"]["code"] == "invalid_session"
    assert invalid_token.status_code in {400, 401}

    with client.app.state.testing_session() as db:
        sessions = db.execute(select(PublicSession)).scalars().all()
        assert len(sessions) == 2
        assert {session.credential_id for session in sessions} == {alpha.credential_id, beta.credential_id}


def test_message_smoke_positive_and_negative_retrieval_isolation(client) -> None:
    alpha, beta = seed_alpha_beta(client)
    alpha_token = create_public_session(client, alpha)
    beta_token = create_public_session(client, beta)

    alpha_answer = post_widget_message(client, alpha, alpha_token, message=ALPHA_FACT, idempotency_key="idem-alpha-positive-b2")
    beta_answer = post_widget_message(client, beta, beta_token, message=BETA_FACT, idempotency_key="idem-beta-positive-b2")

    assert alpha_answer.status_code == 200, alpha_answer.text
    assert beta_answer.status_code == 200, beta_answer.text
    assert alpha_answer.headers["cache-control"] == "no-store"
    assert beta_answer.headers["cache-control"] == "no-store"
    _assert_only_expected_citations(alpha_answer.json(), expected_title=ALPHA_TITLE, forbidden_title=BETA_TITLE)
    _assert_only_expected_citations(beta_answer.json(), expected_title=BETA_TITLE, forbidden_title=ALPHA_TITLE)

    alpha_asks_beta = post_widget_message(client, alpha, alpha_token, message=BETA_FACT, idempotency_key="idem-alpha-negative-b2")
    beta_asks_alpha = post_widget_message(client, beta, beta_token, message=ALPHA_FACT, idempotency_key="idem-beta-negative-b2")

    assert alpha_asks_beta.status_code == 200, alpha_asks_beta.text
    assert beta_asks_alpha.status_code == 200, beta_asks_alpha.text
    assert BETA_TITLE not in alpha_asks_beta.text
    assert "Cobalt library" not in alpha_asks_beta.text
    assert "Harbor Station" not in alpha_asks_beta.text
    assert ALPHA_TITLE not in beta_asks_alpha.text
    assert "Aurora chamber" not in beta_asks_alpha.text
    assert "Meridian Base" not in beta_asks_alpha.text

    with client.app.state.testing_session() as db:
        chat_sessions = db.execute(select(ChatSession)).scalars().all()
        assert len(chat_sessions) == 2
        messages = db.execute(select(ChatMessage)).scalars().all()
        assert {message.organisation_id for message in messages} == {alpha.organisation_id, beta.organisation_id}
        public_sessions = db.execute(select(PublicSession)).scalars().all()
        assert sorted(session.message_count for session in public_sessions) == [2, 2]


def test_idempotent_reuse_no_cookies_and_no_public_response_token_leakage(client) -> None:
    alpha, _beta = seed_alpha_beta(client)
    token = create_public_session(client, alpha)

    first = post_widget_message(client, alpha, token, message=ALPHA_FACT, idempotency_key="idem-alpha-duplicate-b2")
    duplicate = post_widget_message(client, alpha, token, message=ALPHA_FACT, idempotency_key="idem-alpha-duplicate-b2")

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json() == first.json()
    assert "set-cookie" not in first.headers
    assert token not in first.text

    with client.app.state.testing_session() as db:
        assert len(db.execute(select(PublicMessageRequest)).scalars().all()) == 1
        assert len(db.execute(select(ChatMessage)).scalars().all()) == 2
        assert db.execute(select(PublicSession)).scalar_one().message_count == 1


def test_cors_preflight_and_application_origin_denial(client) -> None:
    alpha, _beta = seed_alpha_beta(client)

    allowed = client.options(f"/api/v1/widget/{alpha.public_key}/messages", headers={"Origin": alpha.origin, "Access-Control-Request-Method": "POST"})
    denied = client.options(f"/api/v1/widget/{alpha.public_key}/messages", headers={"Origin": UNAUTHORISED_ORIGIN, "Access-Control-Request-Method": "POST"})

    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == alpha.origin
    assert allowed.headers["access-control-allow-credentials"] == "false"
    assert "Idempotency-Key" in allowed.headers["access-control-allow-headers"]
    assert denied.status_code == 403
    assert "access-control-allow-origin" not in denied.headers


def _assert_only_expected_citations(body: dict, *, expected_title: str, forbidden_title: str) -> None:
    assert body["answer_state"] == "answered"
    assert body["fallback_used"] is False
    citations = body["citations"]
    assert citations
    assert all(citation["source_title"] == expected_title for citation in citations)
    assert forbidden_title not in str(body)
    assert "chunk_id" not in str(body)
    assert "similarity_score" not in str(body)
    assert "document_version_id" not in str(body)
