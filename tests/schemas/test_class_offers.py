import pytest
from pydantic import ValidationError

from app.schemas.schemas import ClassIn, OrderItemIn


def class_payload():
    return {
        "title": "Dasar Pemrograman",
        "description": "Kelas pemrograman dasar",
        "mentor_ids": ["mentor-1"],
        "curriculum_ids": ["curriculum-1"],
        "base_price_per_meeting": 20_000,
        "offers": [
            {
                "meeting_count": 2,
                "list_price": 40_000,
                "price": 40_000,
            },
            {
                "meeting_count": 6,
                "list_price": 120_000,
                "price": 100_000,
                "is_recommended": True,
            },
        ],
    }


def test_class_accepts_multiple_meeting_offers():
    result = ClassIn.model_validate(class_payload())

    assert result.base_price_per_meeting == 20_000
    assert [offer.meeting_count for offer in result.offers] == [2, 6]
    assert result.offers[1].price == 100_000


def test_class_rejects_duplicate_meeting_counts():
    payload = class_payload()
    payload["offers"][1]["meeting_count"] = 2

    with pytest.raises(ValidationError, match="tidak boleh duplikat"):
        ClassIn.model_validate(payload)


def test_class_rejects_sale_price_above_list_price():
    payload = class_payload()
    payload["offers"][0]["price"] = 50_000

    with pytest.raises(ValidationError, match="tidak boleh melebihi"):
        ClassIn.model_validate(payload)


def test_order_item_accepts_specific_offer():
    item = OrderItemIn.model_validate(
        {
            "item_id": "class-1",
            "item_type": "class",
            "offer_id": "offer-2-meetings",
            "qty": 1,
        }
    )

    assert item.offer_id == "offer-2-meetings"
