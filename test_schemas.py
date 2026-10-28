"""Tests for the Pydantic schemas."""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.schemas import (
    GenericDocumentSchema,
    InvoiceSchema,
    ResumeSchema,
    TEMPLATES,
    get_template,
)


def valid_invoice(**overrides):
    data = {
        "invoice_number": "INV-1",
        "vendor": "Acme",
        "invoice_date": "2024-03-12",
        "due_date": "2024-04-11",
        "currency": "usd",
        "subtotal": 100,
        "tax": "18.00",
        "total_amount": "1,118.50",
        "payment_status": "Partially Paid",
    }
    data.update(overrides)
    return data


def test_valid_invoice_is_normalized():
    invoice = InvoiceSchema.model_validate(valid_invoice())
    assert invoice.currency == "USD"
    assert invoice.invoice_date == date(2024, 3, 12)
    assert invoice.total_amount == Decimal("1118.50")
    assert invoice.payment_status == "partially_paid"


def test_money_is_serialized_as_two_place_strings():
    dumped = InvoiceSchema.model_validate(valid_invoice()).model_dump(mode="json")
    assert dumped["subtotal"] == "100.00"
    assert dumped["total_amount"] == "1118.50"
    assert dumped["invoice_date"] == "2024-03-12"


def test_missing_values_are_allowed_and_stay_null():
    invoice = InvoiceSchema.model_validate({"invoice_number": "INV-9"})
    dumped = invoice.model_dump(mode="json")
    assert dumped["vendor"] is None and dumped["total_amount"] is None


def test_empty_string_is_rejected_so_unknown_is_not_empty():
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(valid_invoice(vendor=""))


@pytest.mark.parametrize(
    "field, value",
    [
        ("invoice_date", "12/03/2024"),
        ("currency", "DOLLARS"),
        ("total_amount", "twelve"),
        ("total_amount", -5),
        ("tax", True),
        ("payment_status", "maybe"),
    ],
)
def test_invalid_invoice_fields_are_rejected(field, value):
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(valid_invoice(**{field: value}))


def test_due_date_before_invoice_date_is_rejected():
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(valid_invoice(due_date="2024-01-01"))


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(valid_invoice(discount=5))


def test_resume_valid_with_nested_entries():
    resume = ResumeSchema.model_validate(
        {
            "full_name": "Aarav Menon",
            "email": "aarav@example.com",
            "phone": "+91 98765 43210",
            "skills": ["Python", "SQL"],
            "education": [{"institution": "Osmania University", "degree": "B.Tech"}],
            "experience": [{"company": "Brightwave", "title": "Engineer", "end_date": "Present"}],
            "certifications": [],
        }
    )
    assert resume.skills == ["Python", "SQL"]
    assert resume.experience[0].end_date == "Present"


def test_resume_null_lists_become_empty_lists():
    resume = ResumeSchema.model_validate({"full_name": "A", "skills": None, "education": None})
    assert resume.skills == [] and resume.education == []


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.com", "@x.com"])
def test_resume_rejects_bad_email(email):
    with pytest.raises(ValidationError):
        ResumeSchema.model_validate({"email": email})


def test_resume_rejects_phone_without_enough_digits():
    with pytest.raises(ValidationError):
        ResumeSchema.model_validate({"phone": "123"})


def test_resume_rejects_blank_education_entry():
    with pytest.raises(ValidationError):
        ResumeSchema.model_validate({"education": [{}]})


def test_resume_rejects_wrong_type_for_skills():
    with pytest.raises(ValidationError):
        ResumeSchema.model_validate({"skills": "Python"})


def test_generic_document_valid():
    doc = GenericDocumentSchema.model_validate(
        {
            "document_type": "memo",
            "title": "Safety Audit",
            "key_entities": [{"name": "Harlow Logistics", "entity_type": "organization"}],
            "dates": ["2024-05-06"],
            "summary": "Audits begin in May.",
        }
    )
    assert doc.dates == [date(2024, 5, 6)]
    assert doc.model_dump(mode="json")["dates"] == ["2024-05-06"]


def test_generic_document_defaults_to_empty_lists():
    doc = GenericDocumentSchema.model_validate({})
    assert doc.key_entities == [] and doc.dates == [] and doc.summary is None


def test_generic_document_rejects_partial_dates():
    with pytest.raises(ValidationError):
        GenericDocumentSchema.model_validate({"dates": ["May 2024"]})


def test_template_registry():
    assert set(TEMPLATES) == {"invoice", "resume", "generic"}
    assert get_template("invoice").schema is InvoiceSchema
    with pytest.raises(KeyError):
        get_template("nope")
