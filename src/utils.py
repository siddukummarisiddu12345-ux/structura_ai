"""Pydantic v2 schemas for document extraction."""

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


def truncate(text: str, max_length: int = 200) -> str:
    """Shorten text safely to a maximum length."""
    if not isinstance(text, str):
        text = str(text)

    if max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    if max_length <= 3:
        return "." * max_length

    return text[: max_length - 3] + "..."


def _parse_money(value: Any) -> Any:
    """Convert monetary values into Decimal with two decimal places."""
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError("Amount must be a number, not true/false")

    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip().replace(",", "")
    else:
        raise ValueError("Amount must be a number")

    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{value!r} is not a valid number") from exc

    if not amount.is_finite():
        raise ValueError("Amount must be finite")

    try:
        return amount.quantize(MONEY_PLACES)
    except InvalidOperation as exc:
        raise ValueError("Amount is too large") from exc


Money = Annotated[Decimal, BeforeValidator(_parse_money), Field(ge=0)]


class _StrictModel(BaseModel):
    """Reject unexpected fields."""

    model_config = ConfigDict(extra="forbid")


def _null_means_empty_list(value: Any) -> Any:
    """Convert null list values to empty lists."""
    return [] if value is None else value


class InvoiceSchema(_StrictModel):
    """Key facts from an invoice."""

    invoice_number: NonEmptyStr | None = None
    vendor: NonEmptyStr | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    subtotal: Money | None = None
    tax: Money | None = None
    total_amount: Money | None = None
    payment_status: Literal[
        "paid", "unpaid", "partially_paid", "overdue"
    ] | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip().upper()
            if len(value) != 3 or not value.isalpha():
                raise ValueError("Currency must be a three-letter code")
        return value

    @field_validator("payment_status", mode="before")
    @classmethod
    def _normalize_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_").replace("-", "_")
        return value

    @model_validator(mode="after")
    def _check_dates(self) -> InvoiceSchema:
        if self.invoice_date and self.due_date:
            if self.due_date < self.invoice_date:
                raise ValueError("Due date cannot precede invoice date")
        return self


class EducationEntry(_StrictModel):
    """One education record."""

    institution: NonEmptyStr | None = None
    degree: NonEmptyStr | None = None
    field_of_study: NonEmptyStr | None = None
    start_date: NonEmptyStr | None = None
    end_date: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _not_blank(self) -> EducationEntry:
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("Education entry has no information")
        return self


class ExperienceEntry(_StrictModel):
    """One work-experience record."""

    company: NonEmptyStr | None = None
    title: NonEmptyStr | None = None
    start_date: NonEmptyStr | None = None
    end_date: NonEmptyStr | None = None
    description: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _not_blank(self) -> ExperienceEntry:
        if all(getattr(self, name) is None for name in type(self).model_fields):
            raise ValueError("Experience entry has no information")
        return self


class ResumeSchema(_StrictModel):
    """Key facts from a resume."""

    full_name: NonEmptyStr | None = None
    email: NonEmptyStr | None = None
    phone: NonEmptyStr | None = None
    skills: list[NonEmptyStr] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    certifications: list[NonEmptyStr] = Field(default_factory=list)

    @field_validator(
        "skills", "education", "experience", "certifications", mode="before"
    )
    @classmethod
    def _null_to_empty(cls, value: Any) -> Any:
        return _null_means_empty_list(value)

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        if value is not None:
            local, separator, domain = value.partition("@")
            if (
                not separator
                or not local
                or "." not in domain
                or " " in value
                or domain.startswith(".")
                or domain.endswith(".")
            ):
                raise ValueError("Email is not a valid address")
        return value

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is not None:
            digits = sum(ch.isdigit() for ch in value)
            if not 7 <= digits <= 15:
                raise ValueError("Phone must contain between 7 and 15 digits")
        return value


class EntityEntry(_StrictModel):
    """A named entity found in a document."""

    name: NonEmptyStr
    entity_type: NonEmptyStr | None = None


class GenericDocumentSchema(_StrictModel):
    """High-level facts from any business document."""

    document_type: NonEmptyStr | None = None
    title: NonEmptyStr | None = None
    key_entities: list[EntityEntry] = Field(default_factory=list)
    dates: list[date] = Field(default_factory=list)
    summary: NonEmptyStr | None = Field(default=None, max_length=1000)

    @field_validator("key_entities", "dates", mode="before")
    @classmethod
    def _null_to_empty(cls, value: Any) -> Any:
        return _null_means_empty_list(value)


@dataclass(frozen=True)
class Template:
    """Metadata for one extraction template."""

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
            "Extract invoice details exactly as written. Convert dates to "
            "YYYY-MM-DD. Represent amounts as numbers without currency symbols. "
            "Only include an explicit due date. Do not calculate totals."
        ),
    ),
    "resume": Template(
        key="resume",
        label="Resume",
        schema=ResumeSchema,
        guidance=(
            "Extract only information stated in the resume. Keep education "
            "and experience dates as written. Do not guess contact details."
        ),
    ),
    "generic": Template(
        key="generic",
        label="Generic Document",
        schema=GenericDocumentSchema,
        guidance=(
            "Identify the document type, title, named entities, full dates, "
            "and a neutral summary of no more than three sentences."
        ),
    ),
}


def get_template(key: str) -> Template:
    """Return a template by key."""
    try:
        return TEMPLATES[key]
    except KeyError:
        raise KeyError(
            f"Unknown template '{key}'. Choose one of: {', '.join(TEMPLATES)}"
        ) from None