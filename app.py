"""Streamlit front end for Structura AI.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

from src.config import PROVIDER_ENV_VARS, Settings, load_settings
from src.pipeline import ExtractionResult, extract
from src.providers import PROVIDER_LABELS, create_provider
from src.providers.base import ProviderError
from src.schemas import TEMPLATES
from src.utils import redact_secrets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE_FILES = {"invoice": "invoice.txt", "resume": "resume.txt", "generic": "generic.txt"}

st.set_page_config(page_title="Structura AI", page_icon="🧾", layout="wide")


def read_sample(template_key: str) -> str:
    """Load the sample text for a template (empty string if missing)."""
    path = SAMPLES_DIR / SAMPLE_FILES.get(template_key, "")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def on_load_sample() -> None:
    """Button callback: replace the text area content with the sample."""
    st.session_state["input_text"] = read_sample(st.session_state["template_key"])


def render_sidebar(settings: Settings) -> tuple[str, str, str]:
    """Draw the sidebar and return (template_key, provider_key, model)."""
    with st.sidebar:
        st.header("⚙️ Settings")
        template_key = st.selectbox(
            "Document template",
            list(TEMPLATES),
            format_func=lambda key: TEMPLATES[key].label,
            key="template_key",
        )
        provider_key = st.selectbox(
            "AI provider",
            list(PROVIDER_LABELS),
            format_func=lambda key: PROVIDER_LABELS[key],
            key="provider_key",
        )
        model = st.selectbox("Model", settings.models_for(provider_key), key=f"model_{provider_key}")
        if settings.is_configured(provider_key):
            st.success("API key found in the environment.")
        else:
            st.error(f"No API key found. Add {PROVIDER_ENV_VARS[provider_key]} to your .env file and restart the app.")
        st.divider()
        st.button("Load sample text", on_click=on_load_sample, help="Replaces the text with a sample for the chosen template.")
        st.caption(f"Input limit: {settings.max_input_chars:,} characters. Retries after format errors: {settings.max_retries}.")
        st.caption("Results come from an AI model and can contain mistakes. Review them before use.")
    return template_key, provider_key, model


def run_extraction(settings: Settings, template_key: str, provider_key: str, model: str, text: str) -> ExtractionResult:
    """Create the provider and run the pipeline, returning a result (never raising)."""
    try:
        provider = create_provider(provider_key, settings.api_key_for(provider_key))
    except ProviderError as exc:
        return ExtractionResult.failure(exc.kind, redact_secrets(str(exc), settings.secrets()))
    with st.spinner(f"Extracting with {PROVIDER_LABELS[provider_key]} ({model})..."):
        return extract(
            text,
            template_key,
            provider,
            model,
            max_retries=settings.max_retries,
            max_input_chars=settings.max_input_chars,
            secrets=settings.secrets(),
        )


def render_result(result: ExtractionResult | None, template_key: str) -> None:
    """Show validation status, JSON, download button, and errors."""
    st.subheader("2. Result")
    if result is None:
        st.info("Choose a template, add some text, and click **Extract JSON**.")
        return
    if result.is_valid:
        st.success(f"✅ Valid: the output passed schema validation ({result.attempts} attempt(s)).")
        st.json(result.data)
        st.download_button(
            "⬇️ Download JSON",
            data=result.json_text,
            file_name=f"{template_key}_extraction.json",
            mime="application/json",
        )
        return
    titles = {
        "input": "Input problem",
        "invalid_output": "Not valid: the model output failed validation",
        "provider_auth": "Authentication problem",
        "provider_rate_limit": "Rate limit or quota problem",
        "provider_unavailable": "Provider unavailable",
    }
    st.error(f"❌ {titles.get(result.error_kind or '', 'Extraction failed')}")
    for message in result.errors:
        st.write(f"- {message}")
    if result.raw_output:
        with st.expander("Raw model output (NOT validated; do not use as data)"):
            st.code(result.raw_output, language="json")


def main() -> None:
    settings = load_settings()
    if "input_text" not in st.session_state:
        st.session_state["input_text"] = read_sample("invoice")

    template_key, provider_key, model = render_sidebar(settings)

    st.title("🧾 Structura AI")
    st.caption("Intelligent document-to-JSON extraction with schema validation.")

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("1. Document text")
        st.text_area("Document text", key="input_text", height=380, label_visibility="collapsed")
        st.caption(f"{len(st.session_state['input_text']):,} / {settings.max_input_chars:,} characters")
        run_clicked = st.button(
            "Extract JSON",
            type="primary",
            disabled=not settings.is_configured(provider_key),
        )
        if not settings.is_configured(provider_key):
            st.warning("Configure an API key for the selected provider to enable extraction.")

    if run_clicked:
        st.session_state["result"] = run_extraction(
            settings, template_key, provider_key, model, st.session_state["input_text"]
        )
        st.session_state["result_template"] = template_key

    with right:
        render_result(st.session_state.get("result"), st.session_state.get("result_template", template_key))


main()
