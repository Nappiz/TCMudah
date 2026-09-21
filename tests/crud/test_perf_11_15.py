from unittest.mock import MagicMock

from app.core.rpc import is_unique_violation
from app.crud.crud_feedback import submit_feedback
from app.crud.crud_order import (
    create_payment_proof_read_url,
    create_payment_upload_intent,
    settings,
)
from app.crud.crud_shortlink import resolve_shortlink


def test_feedback_access_check_and_upsert_are_one_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={
            "id": "feedback-1",
            "class_id": "class-1",
            "text": "Sangat membantu",
            "rating": 5,
        }
    )

    result = submit_feedback(
        "user-1", "class-1", False, "Sangat membantu", 5
    )

    assert result["id"] == "feedback-1"
    mock_supabase.rpc.assert_called_once_with(
        "submit_feedback",
        {
            "p_user_id": "user-1",
            "p_class_id": "class-1",
            "p_is_staff": False,
            "p_text": "Sangat membantu",
            "p_rating": 5,
        },
    )
    mock_supabase.table.assert_not_called()


def test_shortlink_resolve_and_increment_are_one_atomic_rpc(mock_supabase):
    mock_supabase.rpc.return_value.execute.return_value = MagicMock(
        data={"url": "https://example.com", "clicks": 8}
    )

    result = resolve_shortlink("Docs")

    assert result["url"] == "https://example.com"
    mock_supabase.rpc.assert_called_once_with(
        "resolve_shortlink", {"p_slug": "Docs"}
    )
    mock_supabase.table.assert_not_called()


def test_payment_upload_intent_never_uploads_file_through_backend(
    mock_supabase, mocker
):
    mocker.patch("app.crud.crud_order.uuid4").return_value.hex = "proof-id"
    mock_supabase.storage.from_.return_value.create_signed_upload_url.return_value = {
        "signed_url": "https://storage.example/upload?token=signed"
    }

    result = create_payment_upload_intent("user-1", "image/jpeg", 1234)

    assert result["path"] == "user-1/proof-id.jpg"
    assert result["max_size_bytes"] == 1234
    mock_supabase.rpc.assert_called_once()
    mock_supabase.storage.from_.return_value.create_signed_upload_url.assert_called_once_with(
        "user-1/proof-id.jpg"
    )
    mock_supabase.storage.from_.return_value.upload.assert_not_called()


def test_private_payment_proof_gets_short_lived_read_url(mock_supabase):
    mock_supabase.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://storage.example/read?token=signed"
    }

    result = create_payment_proof_read_url("user-1/proof.jpg")

    assert result == "https://storage.example/read?token=signed"
    mock_supabase.storage.from_.return_value.create_signed_url.assert_called_once_with(
        "user-1/proof.jpg", 300
    )


def test_legacy_public_proof_is_converted_to_signed_read_url(mock_supabase):
    mock_supabase.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://storage.example/read?token=signed"
    }
    legacy_url = (
        f"{settings.SUPABASE_URL}/storage/v1/object/public/"
        f"{settings.PAYMENTS_BUCKET}/user-1/proof%20old.jpg"
    )

    result = create_payment_proof_read_url(legacy_url)

    assert result == "https://storage.example/read?token=signed"
    mock_supabase.storage.from_.return_value.create_signed_url.assert_called_once_with(
        "user-1/proof old.jpg", 300
    )


def test_unique_violation_uses_database_error_code_only():
    exc = RuntimeError("details not inspected")
    exc.code = "23505"
    assert is_unique_violation(exc) is True
