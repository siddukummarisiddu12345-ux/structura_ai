"""Pydantic v2 schemas for the three extraction templates.

Conventions used everywhere:
* ``null`` (None) means "not stated in the document" (unknown).
* An empty string is never a valid value; it is rejected so unknown is not
  confused with empty.
* Money is a Decimal with two places and is written to JSON as a string
  (for example "1392.40") so no floating-point rounding can creep in.
* Dates are ISO 8601 (YYYY-MM-DD).
* Unexpected extra fields are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MONEY_PLACES = Decimal("0.01")


def _parse_money(value: Any) -> Any:
    """Turn 1234.5, '1,234.50' or Decimal into Decimal('1234.50')."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("amount must be a number, not true/false")
    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip().replace(",", "")
    else:
        raise ValueError("amount must be a number")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"'{value}' is not a valid number") from exc
    if not amount.is_finite():
        raise ValueError("amount must be a finite number")
    try:
        return amount.quantize(MONEY_PLACES)
    except InvalidOperation as exc:
        raise ValueError("amount is too large") from exc


Money = Annotated[Decimal, BeforeValidator(_parse_money), Field(ge=0)]


class _StrictModel(BaseModel):
    """Base class: no extra keys allowed."""

    model_config = ConfigDict(extra="forbid")


def _null_means_empty_list(value: Any) -> Any:
    """Models often send null for 'no items'; for list fields that means []."""
    return [] if value is None else value


# --------------------------------------------------------------------------- #
# Invoice
# --------------------------------------------------------------------------- #
class InvoiceSchema(_StrictModel):
    """Key facts from an invoice."""

    invoice_number: NonEmptyStr | None = Field(
        default=None, description="Invoice identifier exactly as written, or null if absent."
    )
    vendor: NonEmptyStr | None = Field(
        default=None, description="Name of the company issuing the invoice, or null."
    )
    invoice_date: date | None = Field(
        default=None, description="Date the invoice was issued, ISO format YYYY-MM-DD, or null."
    )
    due_date: date | None = Field(
        default=None,
        description="Explicit payment due date, ISO format YYYY-MM-DD. "
        "Null if only terms such as 'Net 30' are given.",
    )
    currency: str | None = Field(
        default=None, description="Three-letter ISO 4217 code such as USD, or null."
    )
    subtotal: Money | None = Field(default=None, description="Amount before tax, or null.")
    tax: Money | None = Field(default=None, description="Total tax amount, or null.")
    total_amount: Money | None = Field(default=None, description="Final amount due, or null.")
    payment_status: Literal["paid", "unpaid", "partially_paid", "overdue"] | None = Field(
        default=None, description="Payment status only if the document states it, else null."
    )

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip().upper()
            if len(value) != 3 or not value.isalpha():
                raise ValueError("currency must be a 3-letter ISO 4217 code such as USD")
        return value

    @field_validator("payment_status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_").replace("-", "_")
        return value

    @model_validator(mode="after")
    def _check_dates(self) -> "InvoiceSchema":
        if self.invoice_date and self.due_date and self.due_date < self.invoice_date:
            raise ValueError("due_date cannot be earlier than invoice_date")
        return self


# --------------------------------------------------------------------------- #
# Resume
# --------------------------------------------------------------------------- #
class EducationEntry(_StrictModel):
    """One education record."""

    institution: NonEmptyStr | None = Field(default=None, description="School or university.")
    degree: NonEmptyStr | None = Field(default=None, description="Degree or qualification.")
    field_of_study: NonEmptyStr | None = Field(default=None, description="Major or subject.")
    start_date: NonEmptyStr | None = Field(
        default=None, description="Start as written, e.g. '2019' or '2019-08'."
    )
    end_date: NonEmptyStr | None = Field(
        default=None, description="End as written, e.g. '2023', or 'Present'."
    )

    @model_validator(mode="after")
    def _not_blank(self) -> "EducationEntry":
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("education entry has no information; omit it instead")
        return self


class ExperienceEntry(_StrictModel):
    """One work-experience record."""

    company: NonEmptyStr | None = Field(default=None, description="Employer name.")
    title: NonEmptyStr | None = Field(default=None, description="Job title.")
    start_date: NonEmptyStr | None = Field(
        default=None, description="Start as written, e.g. '2021-06'."
    )
    end_date: NonEmptyStr | None = Field(
        default=None, description="End as written, or 'Present'."
    )
    description: NonEmptyStr | None = Field(
        default=None, description="Short summary of responsibilities taken from the text."
    )

    @model_validator(mode="after")
    def _not_blank(self) -> "ExperienceEntry":
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("experience entry has no information; omit it instead")
        return self


class ResumeSchema(_StrictModel):
    """Key facts from a resume."""

    full_name: NonEmptyStr | None = Field(default=None, description="Candidate's full name, or null.")
    email: NonEmptyStr | None = Field(default=None, description="Email address, or null.")
    phone: NonEmptyStr | None = Field(default=None, description="Phone number as written, or null.")
    skills: list[NonEmptyStr] = Field(
        default_factory=list, description="Skills listed in the document; [] if none."
    )
    education: list[EducationEntry] = Field(
        default_factory=list, description="Education entries; [] if none."
    )
    experience: list[ExperienceEntry] = Field(
        default_factory=list, description="Work experience entries; [] if none."
    )
    certifications: list[NonEmptyStr] = Field(
        default_factory=list, description="Certifications listed; [] if none."
    )

    @field_validator("skills", "education", "experience", "certifications", mode="before")
    @classmethod
    def _null_to_empty(cls, value: Any) -> Any:
        return _null_means_empty_list(value)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        if value is not None:
            local, _, domain = value.partition("@")
            if not local or "." not in domain or " " in value or domain.startswith(".") or domain.endswith("."):
                raise ValueError("email is not a valid address")
        return value

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None and not 7 <= sum(ch.isdigit() for ch in value) <= 15:
            raise ValueError("phone must contain between 7 and 15 digits")
        return value


# --------------------------------------------------------------------------- #
# Generic document
# --------------------------------------------------------------------------- #
class EntityEntry(_StrictModel):
    """A named entity found in the text."""

    name: NonEmptyStr = Field(description="Entity name exactly as written.")
    entity_type: NonEmptyStr | None = Field(
        default=None, description="Kind of entity, e.g. person, organization, location, product."
    )


class GenericDocumentSchema(_StrictModel):
    """High-level facts from any business document."""

    document_type: NonEmptyStr | None = Field(
        default=None, description="Short label such as 'memo', 'contract', 'meeting notice'."
    )
    title: NonEmptyStr | None = Field(
        default=None, description="Title or subject line if present, else null."
    )
    key_entities: list[EntityEntry] = Field(
        default_factory=list, description="People, organizations, places, products; [] if none."
    )
    dates: list[date] = Field(
        default_factory=list, description="Full dates found, ISO YYYY-MM-DD; [] if none."
    )
    summary: NonEmptyStr | None = Field(
        default=None, max_length=1000, description="Neutral summary of at most 3 sentences."
    )

    @field_validator("key_entities", "dates", mode="before")
    @classmethod
    def _null_to_empty(cls, value: Any) -> Any:
        return _null_means_empty_list(value)


# --------------------------------------------------------------------------- #
# Template registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Template:
    """Everything the app needs to know about one extraction template."""

    key: str
    label: str
    schema: type[BaseModel]
    guidance: str


TEMPLATES: dict[str, Template] = {
    "invoice": Template(
        key="invoice",
        label="Invoice",
        schema=InvoiceSchema,
        guidance=(
            "The text is an invoice. Copy the invoice number and vendor exactly as written. "
            "Convert dates to YYYY-MM-DD. Amounts are plain numbers without currency symbols "
            "or thousands separators. Only fill due_date when an explicit date is written; "
            "payment terms such as 'Net 30' do NOT give you a due date. Only fill "
            "payment_status when the document states it. Do not calculate totals yourself."
        ),
    ),
    "resume": Template(
        key="resume",
        label="Resume",
        schema=ResumeSchema,
        guidance=(
            "The text is a resume or CV. Extract only what is written. Keep dates as written "
            "(for example '2021-06' or 'Present'). List each skill and certification as a "
            "separate short string. Do not guess an email address or phone number."
        ),
    ),
    "generic": Template(
        key="generic",
        label="Generic Document",
        schema=GenericDocumentSchema,
        guidance=(
            "The text is a general business document. Identify its type and title, list the "
            "named entities that appear, list full calendar dates (YYYY-MM-DD only; skip "
            "partial dates), and write a neutral summary of at most three sentences."
        ),
    ),
}


def get_template(key: str) -> Template:
    """Look up a template by key, raising KeyError with a helpful message."""
    try:
        return TEMPLATES[key]
    except KeyError:
        raise KeyError(f"Unknown template '{key}'. Choose one of: {', '.join(TEMPLATES)}") from None