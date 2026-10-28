# Structura AI: Intelligent Document-to-JSON Extraction

Structura AI turns unstructured text (invoices, resumes, general business
documents) into **validated, machine-readable JSON** using an LLM (Google
Gemini or OpenAI). Every result is checked against a Pydantic v2 schema before
it is shown as valid.

> This is a learning/portfolio project. It is **not** presented as
> production-ready, and extraction accuracy is **not guaranteed**. Always have a
> person review results before relying on them.

## Real-world use cases

- Accounts payable: pull invoice numbers, dates and totals into a spreadsheet or ERP import.
- Recruiting: turn resumes into consistent candidate records.
- Operations: summarize memos and notices and list the people, organizations and dates in them.

## Architecture and extraction workflow

```
 Streamlit UI (app.py)
        |
        v
 pipeline.extract()  --->  prompts.py   (schema + guidance + document)
        |
        |  LLMProvider.generate()        <- shared interface (providers/base.py)
        |      |-- GeminiProvider        (providers/gemini_provider.py)
        |      |-- OpenAIProvider        (providers/openai_provider.py)
        v
 utils.parse_json_object()   strip Markdown fences, find the JSON object
 utils.normalize_payload()   trim strings, "N/A"/"unknown" -> null
 schemas.<Template>.model_validate()   Pydantic v2 validation
        |
        |-- valid   -> ExtractionResult(is_valid=True, data=...)
        |-- invalid -> one limited retry (prompt includes the exact problem),
                       then ExtractionResult(is_valid=False, errors=[...])
```

Key rules:

- `null` means "not stated in the document". Empty strings are rejected, so unknown and empty are never mixed up. List fields use `[]` when nothing is found.
- Only output-format failures (bad JSON, schema violations) are retried, up to `MAX_RETRIES` times (default 1). Authentication, quota and network errors are reported immediately.
- Invalid output is never labeled valid. The raw reply is shown only as "NOT validated".
- Provider error messages are fixed strings (plus the HTTP status), then passed through secret redaction.

## Features

- Three templates: Invoice, Resume, Generic Document, each with a sample.
- Choose Gemini or OpenAI and a model from a configurable list.
- Editable input, validation status, readable errors, JSON download (valid results only).
- Input size limit (default 20,000 characters).
- API keys come only from environment variables or `.env`; they are never displayed or logged.
- Adding a provider means one new class plus two registry entries.

## Technology stack

Python 3.10+, Streamlit, `google-genai`, `openai`, Pydantic v2, python-dotenv, pytest.

## Project structure

```
structura-ai/
├── app.py                      Streamlit interface
├── requirements.txt
├── pytest.ini
├── .env.example                placeholders only
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py               env loading, settings, limits
│   ├── schemas.py              Pydantic models + template registry
│   ├── prompts.py              parameterized prompt builders
│   ├── pipeline.py             provider-independent workflow + retry
│   ├── utils.py                input checks, JSON cleanup, redaction
│   └── providers/
│       ├── __init__.py         provider registry
│       ├── base.py             LLMProvider interface + error types
│       ├── gemini_provider.py
│       └── openai_provider.py
├── tests/
│   ├── test_schemas.py
│   ├── test_pipeline.py        uses a fake provider (no network)
│   └── test_utils.py
└── samples/
    ├── invoice.txt
    ├── resume.txt
    └── generic.txt
```

## Installation

```bash
cd structura-ai
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

## Configure a provider

Edit `.env` (it is git-ignored) and set the key for the provider you want:

| Provider | Variable | Where to get a key |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |

Optional: `GEMINI_MODELS`, `OPENAI_MODELS` (comma-separated; first is the default),
`MAX_INPUT_CHARS`, `MAX_RETRIES`. Model names change over time. If a default is
retired, set the variable to a model available to your account.

## Run the app

```bash
streamlit run app.py
```

## Run the tests

```bash
pytest
```

Tests use a fake provider, so they need no API keys and cost nothing.

## Example

Input (`samples/invoice.txt`, shortened):

```
Northwind Office Supplies Ltd.
Invoice No: INV-2024-0457
Invoice Date: March 12, 2024
Payment Terms: Net 30
Subtotal: 1,180.00   Tax (18%): 212.40   Total Due: 1,392.40
Currency: USD        Payment Status: Unpaid
```

Typical output (real model output can vary):

```json
{
  "invoice_number": "INV-2024-0457",
  "vendor": "Northwind Office Supplies Ltd.",
  "invoice_date": "2024-03-12",
  "due_date": null,
  "currency": "USD",
  "subtotal": "1180.00",
  "tax": "212.40",
  "total_amount": "1392.40",
  "payment_status": "unpaid"
}
```

`due_date` is `null` on purpose: "Net 30" is a term, not a stated date, and the
pipeline does not calculate or invent values. Money is a two-decimal string and
dates are ISO 8601.

## Security notes and limitations

- Keys live in `.env` or the process environment only. `.env` is git-ignored; `.env.example` holds placeholders. Never commit real keys.
- Document text is sent to the selected third-party provider. Do not use sensitive documents unless that is acceptable under your policies.
- Prompt injection inside a document is mitigated (document is delimited and marked untrusted) but not eliminated. Schema validation limits the shape of output, not its truthfulness.
- A valid result means "matches the schema", not "is correct".
- Text input only: no PDF/image parsing or OCR. Long documents are rejected rather than chunked.
- Amounts must be non-negative (credit notes are not supported) and use two decimal places.
- No authentication, database, rate-limit handling beyond reporting the error, or deployment tooling. This is a local demo app.

## Future improvements

- PDF and image input with OCR.
- Chunking for long documents.
- Line-item extraction for invoices.
- Currency-aware decimal places and arithmetic cross-checks (subtotal + tax = total) as warnings.
- Additional providers (register a new `LLMProvider` subclass).
- Evaluation set to measure accuracy per template.
