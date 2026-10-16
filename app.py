from __future__ import annotations

import streamlit as st

from src.contracts import ProcurementDecision
from src.data_access import load_employees, load_requests
from src.solution import default_provider, evaluate_request

REQUESTS = load_requests()
BY_ID = {request["request_id"]: request for request in REQUESTS}
CUSTOM = "Custom request"
STATUS_STYLE = {
    "verified": ("green", "Source record was available and checked."),
    "missing": ("orange", "The source record or assessment is missing or incomplete."),
    "expired": ("yellow", "The source assessment is past the policy review window."),
    "unknown": ("gray", "The status could not be established."),
    "unavailable": ("red", "The source or service could not be reached; nothing is assumed about it."),
    "conflicting": ("red", "Available sources disagree."),
}
ARCH_LABEL = {
    "single": "A - single agent (one tool-using agent)",
    "staged": "B - staged (analyst agent, then independent reviewer agent)",
}
ACCESS_LEVELS = ["unknown", "none", "internal_marketing", "internal_documents", "confidential_documents", "source_code",
                 "production_telemetry", "employee_pii", "customer_pii", "credentials"]


def esc(value: object) -> str:
    """Streamlit renders $...$ as LaTeX; escape dollar signs so amounts display literally."""
    return str(value).replace("$", "\\$")


def _ai_banner(decision: ProcurementDecision) -> None:
    meta = decision.metadata
    if meta is None:
        return
    if meta.llm_status == "live":
        st.caption(f"AI interpretation: live model `{meta.model}` via {meta.provider}. Approvals, flags and thresholds come from deterministic code.")
    elif meta.llm_status == "mock":
        st.caption("AI interpretation: scripted test provider (not a live model).")
    elif meta.llm_status == "fallback":
        st.warning(f"The model was unavailable ({meta.fallback_reason}). This result uses deterministic policy checks only; "
                   "ambiguity in the request was not assessed by AI.")
    else:
        st.info("No model is configured, so this result uses deterministic policy checks only. Add a Groq key to `.env` to enable AI interpretation.")


def _render_decision(decision: ProcurementDecision) -> None:
    st.subheader("Recommendation")
    st.write(esc(decision.recommendation))
    st.caption(f"Decision code: {decision.recommendation_code}")
    _ai_banner(decision)

    handoff = decision.human_handoff
    if decision.human_review_required:
        st.warning("Human review is required. This recommendation is not an approval or a purchase.")
    else:
        st.info("No additional human review was flagged; this is still a recommendation, not approval.")
    if handoff:
        with st.expander("Human handoff - who must act", expanded=True):
            for reason in handoff.reasons:
                st.markdown(f"- {esc(reason)}")
            if handoff.escalate_to:
                st.markdown("**Decision owners:** " + ", ".join(handoff.escalate_to))
            st.caption(esc(handoff.authority_note))

    if decision.rationale:
        st.markdown("**Why**")
        st.write(esc(decision.rationale))

    approvals_column, risks_column = st.columns(2)
    with approvals_column:
        st.subheader("Required approvals")
        if decision.required_approvals:
            for approval in decision.required_approvals:
                st.markdown(f"- {approval}")
        elif decision.missing_information:
            st.write("No approval tier assigned while required information is missing.")
        else:
            st.write("No additional approval roles were identified.")
    with risks_column:
        st.subheader("Risk flags")
        if decision.risk_flags:
            for flag in decision.risk_flags:
                st.markdown(f"- `{flag}`")
        else:
            st.write("No risk flags identified.")

    st.subheader("Missing information")
    if decision.missing_information:
        for field in decision.missing_information:
            st.markdown(f"- `{field}`")
        if decision.ai_assessment and decision.ai_assessment.clarifying_questions:
            st.markdown("**Suggested questions for the requester**")
            for question in decision.ai_assessment.clarifying_questions:
                st.markdown(f"- {esc(question)}")
    else:
        st.write("None identified.")

    st.subheader("Next step")
    st.write(esc(decision.next_step))

    st.subheader("Supporting evidence")
    st.caption("Every item below was produced from a tool result or the policy file; none is model-written.")
    for item in decision.evidence:
        status = (item.evidence_status or "unknown").casefold()
        color, help_text = STATUS_STYLE.get(status, STATUS_STYLE["unknown"])
        with st.container(border=True):
            status_column, source_column = st.columns([1, 5])
            with status_column:
                st.badge(status.title(), color=color, help=help_text)
            with source_column:
                st.markdown(f"**{item.source}**")
                st.caption(esc(item.reference) + (f" · tool: {item.tool}" if item.tool else ""))
            st.write(esc(item.finding))

    if decision.ai_assessment and (decision.ai_assessment.overlap_note or decision.ai_assessment.injection_suspected):
        with st.expander("AI interpretation (advisory only)"):
            ai = decision.ai_assessment
            if ai.overlap_note:
                st.markdown(f"**Existing-tool overlap ({ai.overlap_view}):** {esc(ai.overlap_note)}")
            if ai.injection_suspected:
                st.markdown(f"**Instruction-like text ignored:** “{esc(ai.injection_quote)}”")

    if decision.metadata and decision.telemetry:
        with st.expander("Run details (measured, not estimated)"):
            t, m = decision.telemetry, decision.metadata
            st.table({
                "Architecture": [ARCH_LABEL[m.architecture]], "Agents": [", ".join(m.agents)], "Model calls": [t.llm_calls],
                "Tool calls": [t.tool_calls], "Failed model calls": [t.failed_llm_calls], "Failed tool calls": [t.failed_tool_calls],
                "Model latency (ms)": [t.llm_latency_ms], "Rate-limit wait (ms)": [t.rate_limit_wait_ms], "Tokens (in/out)": [f"{t.prompt_tokens}/{t.completion_tokens}"],
            })
            for note in m.guardrail_notes:
                st.markdown(f"- Guardrail: {esc(note)}")


def _custom_request() -> dict:
    employees = load_employees()
    ids = employees["employee_id"].tolist()
    names = dict(zip(employees["employee_id"], employees["name"] + " (" + employees["department"] + ")"))
    request_id = "CUSTOM-1"
    requester = st.selectbox("Requester", ids, format_func=lambda i: f"{i} - {names[i]}")
    product = st.text_input("Product name")
    vendor = st.text_input("Vendor name")
    category = st.text_input("Category")
    cost = st.text_input("Annual cost (USD) - leave blank if unknown")
    users = st.text_input("User count - leave blank if unknown")
    purpose = st.text_area("Business justification")
    access = st.selectbox("Data access level", ACCESS_LEVELS)
    integrations = st.text_input("Requested integrations (comma separated, blank = none)")
    return {
        "request_id": request_id, "requester_id": requester, "product_name": product, "vendor_name": vendor, "category": category,
        "annual_cost_usd": cost.strip() or None, "user_count": users.strip() or None, "business_justification": purpose,
        "data_access_level": access, "requested_integrations": [i.strip() for i in integrations.split(",") if i.strip()], "urgency": "normal",
    }


st.set_page_config(page_title="Procurement Request Review", layout="wide")
st.title("Procurement request review")
st.caption("Advisory review only. Authorized humans retain all approval and purchasing authority.")

choice = st.sidebar.selectbox(
    "Request", [*BY_ID.keys(), CUSTOM],
    format_func=lambda selected: selected if selected == CUSTOM else f"{selected} - {BY_ID[selected]['product_name']}",
)
architecture = st.sidebar.radio("Architecture", ["single", "staged"], format_func=lambda a: ARCH_LABEL[a])
provider = default_provider()
st.sidebar.caption("Model: " + (f"{provider.name} / {provider.model}" if provider.model else "not configured (deterministic mode)"))
if st.session_state.get("_selected_request_id") != choice:
    st.session_state.pop("_analysis_decision", None)
    st.session_state.pop("_analysis_error", None)
    st.session_state["_selected_request_id"] = choice

st.subheader("Request details")
if choice == CUSTOM:
    request = _custom_request()
else:
    request = BY_ID[choice]
    st.table({
        "Field": ["Requester", "Product", "Vendor", "Category", "Annual cost (USD)", "Users", "Data access", "Integrations", "Urgency", "Business justification"],
        "Value": [str(v) for v in (
            request.get("requester_id"), request.get("product_name"), request.get("vendor_name"), request.get("category"),
            "unknown" if request.get("annual_cost_usd") is None else f"{request['annual_cost_usd']:,}",
            "unknown" if request.get("user_count") is None else request.get("user_count"), request.get("data_access_level"),
            ", ".join(request.get("requested_integrations") or []) or "none", request.get("urgency"), request.get("business_justification"))],
    })
    with st.expander("Raw request record (untrusted business data)"):
        st.json(request, expanded=False)

run_analysis = st.button("Run analysis", type="primary", use_container_width=True)
if run_analysis:
    st.session_state.pop("_analysis_decision", None)
    st.session_state.pop("_analysis_error", None)
    try:
        with st.spinner("Gathering evidence and applying policy..."):
            raw_decision = evaluate_request(request, architecture=architecture)
            decision = ProcurementDecision.model_validate(raw_decision)
    except Exception as exc:
        details = str(exc).strip() or "No additional error details were provided."
        st.session_state["_analysis_error"] = f"{type(exc).__name__}: {details}"
    else:
        st.session_state["_analysis_decision"] = decision.model_dump()

decision_payload = st.session_state.get("_analysis_decision")
analysis_error = st.session_state.get("_analysis_error")
if analysis_error:
    st.error(f"Analysis failed. No recommendation was generated. {analysis_error}")
elif decision_payload and decision_payload.get("request_id") == request.get("request_id"):
    _render_decision(ProcurementDecision.model_validate(decision_payload))
else:
    st.info("No analysis has been run for this request.")
