# Assessment 3 Initial Specification

## 1. Project Overview

### 1.1 Product

The product is an **AI Procurement Request Copilot** for evaluating employee requests for software and services. The system must gather evidence from request data, policy text, approved-software records, departmental budgets, vendor records, purchase history, and an external vendor-risk service. It must apply deterministic procurement rules where those rules are objective, while allowing an LLM to interpret contextual evidence and produce a recommendation.

The system is advisory. It must not autonomously purchase software, approve spend, modify budgets, accept legal terms, or override human security, privacy, legal, or approval controls.

### 1.2 Assessment context

The repository is a starter pack for a forward-deployed engineering assessment. It provides synthetic business data, a mock external vendor-risk service, an interface contract, an optional UI scaffold, public evaluation cases, reporting templates, and starter-pack integrity tests. The starter pack intentionally does not implement the agent, tool strategy, policy engine, or complete procurement workflow.

### 1.3 Scope for this specification

This specification covers the initial assessment phase and defines the requirements for:

- Architecture A: a working single-agent baseline.
- Architecture B: an exactly two-agent project design.
- A common procurement decision contract.
- Tool-backed evidence gathering.
- Deterministic policy checks.
- Human approval and escalation.
- Reproducible evaluation using the public case set.
- Submission documentation and evidence.

This specification does not implement any of those components.

> **Project decision:** The two-agent design and xAI Grok preference are implementation choices made for this project. They are not PDF mandates. The original assessment PDF remains the source for scoring categories and assessment requirements.

---

## 2. Assessment Objectives

### 2.1 Primary objectives

1. Build a working procurement copilot that can inspect a software or service request.
2. Use at least three tools, with at least one deterministic tool or rule check.
3. Ground recommendations in actual tool and data results rather than unsupported model assertions.
4. Produce a structured procurement decision with evidence, approvals, risk flags, missing information, and next steps.
5. Preserve human authority for sensitive approvals and exceptions.
6. Compare Architecture A and Architecture B on the same public evaluation set.
7. Produce a defensible architecture decision memo with measured evidence.
8. Deliver a working local application and reproducible submission package.

### 2.2 Assessment deadline

Source-backed deadline: **8 October 2026** from the Assessment 3 PDF. This deadline is recorded as a source fact and is not treated as evidence that work has been submitted or completed.

### 2.3 Explicit product outcomes

The final product must provide:

- A mandatory product UI for entering or reviewing procurement requests.
- An evidence panel that shows what was checked and where the information came from.
- A recommendation and a concrete next action.
- A structured output containing recommendation, evidence, required approvals, missing information, risk flags, and next step.
- Human handoff for approvals, exceptions, and unresolved evidence.
- An implementation that can be evaluated using the provided public cases and hidden cases.

The existing Streamlit scaffold is the default UI implementation unless repository inspection establishes a concrete reason to choose another framework. The mandatory UI must support request selection, architecture selection, evidence, recommendation, approvals, risks, missing information, and next steps.

---

## 3. Existing Repository Structure

### 3.1 Top-level areas

| Area | Current purpose evidenced by source | Current implementation status |
|---|---|---|
| [README.md](../README.md) | User-facing assessment overview, quick start, requirements, starter-pack rules, and suggested workflow | Documentation only; no runtime validation performed by this source inspection |
| [STUDENT_CHECKLIST.md](../STUDENT_CHECKLIST.md) | Final submission checklist | Documentation only |
| [app.py](../app.py) | Mandatory Streamlit UI scaffold | Starter UI; analysis button requires an implementation in [src/solution.py](../src/solution.py) |
| [run_local.py](../run_local.py) | Local startup orchestration for mock API and optional UI | Reads environment and starts services; no application logic |
| [verify_setup.py](../verify_setup.py) | Pre-flight validation for environment, datasets, contracts, and mock API | Script is present and can be inspected; implementation has not been executed as part of this specification |
| [requirements.txt](../requirements.txt) | Python dependency declarations | Declares starter dependencies; no provider SDK is preselected |
| [data/](../data/) | Synthetic business data and policy source | Data and integrity rules are present; no application-facing processing is implemented |
| [mock_api/](../mock_api/) | External vendor-risk API simulation | Healthy and failure-response behaviors are implemented |
| [src/](../src/) | Contracts, data access helpers, optional telemetry, sample output, and extension point | Contract and helper scaffolding are present; no real agent implementation |
| [templates/](../templates/) | Evaluation and architecture-decision templates | Templates are present; no output data has been generated |
| [docs/](../docs/) | Assignment brief PDF and assignment artifacts | Brief is present; PDF extraction was not available in the current environment |
| [evals/](../evals/) | Public evaluation cases and runner | Runner and six public cases are present; implementation is untested by this specification |
| [tests/](../tests/) | Data-integrity and mock-API tests | Source-based tests are present; no implementation-level test results are available |

### 3.2 Key source files

- [src/contracts.py](../src/contracts.py): Defines `EvidenceItem`, `RunTelemetry`, `ProcurementDecision`, and the supported `Architecture` values.
- [src/data_access.py](../src/data_access.py): Loads employees, budgets, software catalog, vendors, purchase history, requests, and policy text.
- [src/vendor_client.py](../src/vendor_client.py): Calls the vendor-risk service using `VENDOR_RISK_BASE_URL` with a three-second timeout.
- [src/solution.py](../src/solution.py): Required adapter entry point for `handle_request(request_id, architecture)`.
- [src/sample_output.json](../src/sample_output.json): Example structured decision payload.
- [src/telemetry.py](../src/telemetry.py): Optional per-run metrics helper.
- [mock_api/app.py](../mock_api/app.py): FastAPI service with health and vendor-risk endpoints.
- [evals/public_cases.json](../evals/public_cases.json): Six public evaluation cases and minimum expectations.
- [evals/run_public_evals.py](../evals/run_public_evals.py): Runner that validates schema, minimum expectations, latency, and calls.
- [templates/architecture_decision.md](../templates/architecture_decision.md): Final architecture decision memo template.
- [templates/evaluation_results_template.csv](../templates/evaluation_results_template.csv): Evaluation result-column template.
- [templates/workflow_notes.md](../templates/workflow_notes.md): Architecture and responsibility scratch template.

---

## 4. Current Setup and Execution Workflow

### 4.1 Required environment

The documented setup requires:

- Python 3.11 or 3.12 recommended.
- A virtual environment.
- Dependencies from [requirements.txt](../requirements.txt).
- Optional LLM-provider credentials via `.env`.

The documented startup workflow is:

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run `python verify_setup.py`.
4. Copy `.env.example` to `.env` and add provider credentials if needed.
5. Run `python run_local.py`.
6. Implement `src/solution.py`.
7. Run the architecture-specific public evaluations.

### 4.2 Current verified setup status

The repository contains a setup pre-flight script and dependency list, but the pre-flight was not executed in this specification because the task specifically prohibits altering the project environment and does not require package installation. The current setup state is therefore **not yet verified** from execution.

### 4.3 Current local-service startup

[run_local.py](../run_local.py) starts:

- Vendor-risk API on `http://127.0.0.1:8001`.
- Streamlit UI on `http://127.0.0.1:8501` if Streamlit is installed.

The script also exits cleanly on `SIGTERM` and terminates child processes.

### 4.4 Known setup constraints

- The repository has no committed `.env` file; `.env` is ignored by [.gitignore](../.gitignore).
- `.env.example` contains the vendor-risk URL and optional provider credential variables.
- The user must install a provider SDK if the selected LLM provider requires one.
- The package installation and local-service startup are not part of this specification’s file changes.

---

## 5. Existing Data Sources and Their Intended Roles

### 5.1 Employee data

[employees.csv](../data/employees.csv) contains employee identifiers, names, departments, managers, levels, and countries. It is used to validate requesters, reporting lines, and department ownership.

### 5.2 Department budgets

[department_budgets.csv](../data/department_budgets.csv) provides annual budgets, committed amounts, and available software budgets. The dataset guide states that `available_usd = annual_software_budget_usd - committed_usd`.

### 5.3 Software catalog

[software_catalog.csv](../data/software_catalog.csv) contains approved products, categories, vendors, status, cost, licensed seats, scope, and notes. It is the basis for detecting existing overlap and potential reuse.

### 5.4 Vendor registry

[vendors.csv](../data/vendors.csv) provides vendor status, security status, review dates, legal-term status, and notes. The registry is an internal source that may conflict with the mock external service.

### 5.5 Purchase history

[purchase_history.csv](../data/purchase_history.csv) records previous purchases and renewals. It can be used to identify prior approvals, recurring spend, or existing vendor relationships if implemented.

### 5.6 Requests

[requests.json](../data/requests.json) contains example procurement requests with requester, product, vendor, category, annual cost, user count, business justification, data-access level, integrations, and urgency. The six public evaluation cases are mapped to request IDs inside this file.

### 5.7 Policy

[procurement_policy.md](../data/procurement_policy.md) is the policy source of truth. It defines required request information, budget checks, overlap checks, approval thresholds, security/privacy/legal rules, prompt-injection instructions, tool failure behavior, and human authority rules.

### 5.8 Vendor-risk service data

[vendor_risk.json](../data/vendor_risk.json) backs the mock external vendor-risk API. It includes security-review status, last review date, personal-data processing, cross-region storage, and simulated failure conditions. The assessment requires the system to access this information through the API rather than treating it as a direct data dependency when possible.

---

## 6. Existing Components and Dependencies

### 6.1 Component dependency map

```text
User / Streamlit UI
        |
        v
src.solution.handle_request(request_id, architecture)
        |
        +--> src.data_access helpers
        |       +--> CSV and JSON data files
        |       +--> procurement_policy.md
        |
        +--> src.vendor_client.get_vendor_risk()
        |       +--> vendor-risk API at 127.0.0.1:8001
        |
        +--> model provider (selected by implementation)
        |
        +--> deterministic policy checks
        |
        +--> ProcurementDecision contract

Public evaluation runner
        |
        v
src.solution.handle_request(...)
        |
        v
ProcurementDecision validation and CSV output
```

### 6.2 Dependency status

- **FastAPI**: Required by mock API and is already declared.
- **Uvicorn**: Required to run the mock API and is already declared.
- **Pydantic**: Required for contract validation and is already declared.
- **Pandas**: Declared and used by the data-access helpers.
- **Requests**: Declared and used by the vendor client.
- **httpx**: Declared but not otherwise used in the starter code.
- **Streamlit**: Declared and used by the optional UI scaffold.
- **python-dotenv**: Declared and used by [run_local.py](../run_local.py).
- **LLM provider SDK**: Not selected by the starter pack and must be added by the implementation if required.

### 6.3 Current implementation status of each major component

| Component | Current status | Source evidence |
|---|---|---|
| Request adapter | Missing implementation | [src/solution.py](../src/solution.py) raises `NotImplementedError` |
| Single-agent flow | Missing implementation | No agent or orchestration exists in [src/](../src/) |
| Staged / two-agent flow | Missing implementation | No staged workflow exists |
| Deterministic checks | No implementation in adapter; data helpers are available | [src/data_access.py](../src/data_access.py) and policy source |
| Deterministic tool calls | Basic vendor API client exists | [src/vendor_client.py](../src/vendor_client.py) |
| UI | Optional scaffold is present | [app.py](../app.py) |
| Evidence panel | Not implemented beyond static request display | UI uses request JSON and a recommendation placeholder |
| Evaluation telemetry | Helper present but not integrated | [src/telemetry.py](../src/telemetry.py) |
| Public evaluation | Runner and case set present | [evals/run_public_evals.py](../evals/run_public_evals.py) |
| Architecture decision memo | Template present | [templates/architecture_decision.md](../templates/architecture_decision.md) |

---

## 7. Functional Requirements

### 7.1 Requirement set

| ID | Description | Source | Priority | Acceptance criteria | Verification method |
|---|---|---|---|---|---|
| FR-001 | The system shall accept a request identifier and architecture selection through `handle_request(request_id, architecture)`. | Existing adapter contract and README | Must | Function is callable with `request_id` and `architecture`; return is accepted by `ProcurementDecision.model_validate`. | Unit/integration test exercising each architecture value and valid request ID. |
| FR-002 | The system shall return a `ProcurementDecision` object with all required fields. | [src/contracts.py](../src/contracts.py) | Must | Object contains request ID, recommendation, evidence, required approvals, missing information, risk flags, next step, human review flag, and optional telemetry. | Schema validation and public evaluator. |
| FR-003 | The system shall evaluate a request using data from the request, employee, budget, catalog, vendor, purchase-history, and policy sources. | Assessment brief; data source docs | Must | Output evidence references at least one factual source; no evidence is generated from unsupported claims. | Review output against source records and expected cases. |
| FR-004 | The system shall identify missing required request information and request clarification instead of inventing values. | [data/procurement_policy.md](../data/procurement_policy.md) | Must | Missing fields are listed under `missing_information`; the decision explicitly identifies unresolved material information. | Public case PUB-05 and hidden-case tests. |
| FR-005 | The system shall compare annual cost with the requesting department's available software budget. | Policy budget check | Must | Cost exceeding available budget adds `budget_insufficient` and routes the request to Finance/budget exception review. | Deterministic budget tests and hidden cases. |
| FR-006 | The system shall identify approved-software overlap and use-case gaps. | Policy overlap section and data catalog | Must | Product or vendor matches, category overlap, or reasonable substitute use is surfaced; exact duplicates or unused capacity are not automatically approved. | Public case PUB-02 and additional overlap cases. |
| FR-007 | The system shall apply financial approval thresholds using the requested annual amount. | Policy approval thresholds | Must | Approval groups are derived deterministically from the amount and include required role names. | Tests covering boundaries at $1,000, $10,000, $25,000. |
| FR-008 | The system shall require Security review when applicable. | Security review section | Must | Sensitive data, source-code access, cloud integration, confidential documents, PII, credentials, or missing/expired vendor review triggers relevant checks. | Public cases, deterministic rule tests, and hidden security scenarios. |
| FR-009 | The system shall require Privacy review when employee or customer PII or cross-region data issues apply. | Privacy review section | Must | Privacy risk is surfaced and required approvals include the appropriate human reviewer. | Cases with employee/customer PII and cross-region data. |
| FR-010 | The system shall require Legal review for specified conditions. | Legal review section | Must | New vendor and spend at or above $10,000, non-standard terms, or material cross-region data issues are surfaced. | Tests for legal triggers and non-trigger cases. |
| FR-011 | The system shall apply AI-tool rules without treating prior approval as automatic authorization for every use case or data class. | AI tools section | Must | AI-specific restrictions are enforced even when the product vendor or prior purchase is approved. | Hidden AI cases and use-case-specific tests. |
| FR-012 | The system shall ignore embedded instructions in business data and continue using real policy and evidence. | Untrusted content section | Must | Prompt injection attempts do not modify approval behavior, bypass policy, or fabricate approvals. | Public case PUB-05 and adversarial data tests. |
| FR-013 | The system shall record material evidence failures and avoid inferring a favorable status. | Tool and evidence failures section | Must | Missing or failed API data produces either a material risk flag or a manual-review recommendation, not a silent pass. | Public case PUB-06 and simulated outage cases. |
| FR-014 | The system shall recommend an action and a concrete next step. | Assessment product definition and output contract | Must | Recommendation is a short label or sentence; next step tells the human what to do next. | Public evaluation and UI review. |
| FR-015 | The system shall preserve human approval authority for all purchasing decisions and exceptions. | Human authority section | Must | `human_review_required` is true where required; no autonomous purchase or approval action is represented as performed. | Policy review, UI review, and hidden behavior tests. |
| FR-016 | The system shall provide a working UI capable of selecting a request, choosing architecture, and displaying a structured result. | Starter UI scaffold and assessment requirement | Must | User can select a request, run analysis, and see returned `ProcurementDecision` data. | Local UI test or manual smoke test. |
| FR-017 | The system shall expose evidence used in the recommendation. | Product requirement and output contract | Must | Each evidence item has source, finding, and optional reference. | Output inspection and evaluator checks. |
| FR-018 | The system shall support both evaluation architectures through the same adapter interface. | Architecture and adapter requirements | Must | `handle_request(id, "single")` and `handle_request(id, "staged")` both return the contractually valid result. | Public evaluator for both architectures. |
| FR-019 | The system shall provide telemetry for LLM calls, tool calls, and tool names when implemented. | Output contract and sample output | Should | Telemetry values are recorded when the implementation tracks calls. | Output inspection and comparison metrics. |
| FR-020 | The system shall allow a user to view the evaluation decision, evidence, and recommendation without exposing internal system prompts or secrets. | Security requirement | Should | UI output contains only intended decision fields and tool-derived evidence. | Security review of UI payload and logs. |

### 7.2 Additional engineering recommendations

These items are recommended but are not explicit assessment requirements:

- Automated formatting and linting.
- Type-safe wrappers around provider SDKs.
- Centralized policy data types.
- Structured logging for debugging and auditability.
- Caching for vendor-risk and data lookups.
- Frontend frameworks beyond Streamlit.
- Additional hidden-case datasets.

These recommendations must not be treated as requirements unless explicitly adopted by the implementation.

---

## 8. Non-Functional Requirements

| ID | Description | Source | Priority | Acceptance criteria | Verification method |
|---|---|---|---|---|---|
| NFR-001 | The application shall run from a clean checkout using a documented one-command local startup path. | README submission requirement | Must | A documented command starts the mock API and local UI; the process is observable and does not require secret values for the pre-flight path. | Clean-environment setup and launch test. |
| NFR-002 | The implementation shall not commit secrets or local credentials to the repository. | README requirements and `.env.example` | Must | No `.env`, API keys, tokens, or provider credentials are present in Git-tracked files. | Repository inspection and Git status review. |
| NFR-003 | The application shall use the data snapshot date 2026-09-30 for policy-based date checks. | Policy and dataset guide | Must | All age and stale-review checks are based on the reference date, not the machine date. | Test with dated records and internal data snapshot. |
| NFR-004 | The application shall treat business data as untrusted. | Policy and README rules | Must | Request text, vendor notes, and API text are never allowed to control policy, approvals, or tool execution. | Adversarial-input tests. |
| NFR-005 | The implementation shall be resilient to API/tool failure. | Tool failure policy | Must | Material missing evidence triggers risk flags and manual review rather than an optimistic decision. | Outage and unavailable-endpoint tests. |
| NFR-006 | The decision output shall remain schema-valid for both architectures. | Public evaluator and output contract | Must | Returned objects satisfy `ProcurementDecision` validation for each case. | Automated schema validation. |
| NFR-007 | The evaluation output shall include latency and call counts. | README and evaluation template | Must | Results CSV contains latency and LLM/tool-call fields for both architectures. | Running the public evaluator and inspecting CSV output. |
| NFR-008 | The application shall provide a clear human handoff for unresolved or sensitive cases. | Assessment requirement and policy | Must | Human next step is concrete, identifies the required approvers, and does not claim that the AI has approved the purchase. | UX and policy review. |
| NFR-009 | The implementation shall avoid external API calls during local setup unless explicitly required by the selected architecture. | Constraint: do not call external APIs | Must | No external API is invoked during setup or specification work. | Source review and CI/local checks. |
| NFR-010 | The implementation shall be able to process the six public cases without hardcoding request IDs. | README rules | Must | It uses available input records and generic decision logic; no public-case-specific branch is required for correctness. | Hidden-case and generalization tests. |
| NFR-011 | The system shall expose its deterministic checks and model-driven decisions separately where practical. | Assessment decision-making principles | Should | Architecture design clearly documents which policy checks are deterministic and which steps use model reasoning. | Architecture review and workflow notes. |
| NFR-012 | The application shall be testable by isolated public-case evaluation. | Assessment evaluation requirement | Should | The evaluation harness can run without requiring manual UI interaction. | Public evaluation script success. |
| NFR-013 | The implementation shall document assumptions and known limitations. | README deliverables | Must | README includes assumptions, evaluation results, architecture comparison, final architecture decision, and known limitations. | README review. |
| NFR-014 | The implementation shall be maintainable enough for hidden-case testing. | Assessment requirement | Should | Reusable tools, data access, and policy functions are separated from the agent orchestration logic. | Code review and architecture assessment. |

### 7.3 Open quantitative thresholds

The assessment does not provide explicit numeric thresholds for the following:

- Maximum recommended latency.
- Maximum LLM calls or tool calls.
- Minimum accuracy or pass rate.
- Required approval-response time.
- Maximum failure probability.

These remain open questions unless the assessment PDF or grader provides them. The implementation must not invent numeric targets.

---

## 9. Agent Architecture Requirements

### 9.1 Architecture A: single-agent baseline

Architecture A must use a single agent to perform the complete procurement review using visible tools and deterministic checks.

Requirements:

- The agent should have an explicit request-analysis workflow.
- The agent should invoke at least three tools or data sources.
- At least one tool or check must be deterministic.
- The agent must not treat tool outputs as permission to approve.
- The agent must return the required `ProcurementDecision` structure.
- The agent must preserve human review when policy requires it.

Acceptance criteria:

- The architecture runs through `handle_request(..., architecture="single")`.
- Public evaluation cases return schema-valid decisions.
- At least three named tool/data sources are used in the final flow.
- The architecture records telemetry or equivalent call counts.
- The case set is evaluated without hardcoded request-specific responses.

### 9.2 Architecture B: exactly two-agent variant

Architecture B is a project design decision to use exactly two agents. The assessment does not require more than two agents.

Agent responsibilities:

- **Agent 1:** Gathers evidence, coordinates tool use, and preserves the initial evidence set.
- **Agent 2:** Evaluates the gathered evidence, produces the recommendation and human handoff, and identifies remaining risks or required approvals.

Deterministic policy checks must remain code-enforced. They must not be delegated exclusively to either agent. The agents may use deterministic results as inputs, but the rule engine determines the applicable thresholds and enforceable conditions.

Requirements:

- The two agents must have explicit interfaces and a defined evidence handoff.
- Agent 1 must not make the final approval or purchase decision.
- Agent 2 must not invent or silently discard evidence received from Agent 1 or deterministic checks.
- Deterministic checks must be independently testable from the LLM layers.
- The architecture must remain observable through telemetry.
- The final structured output must be equivalent in contract shape to Architecture A.

Acceptance criteria:

- `handle_request(..., architecture="staged")` returns a valid decision.
- Evidence is preserved across the Agent 1-to-Agent 2 handoff.
- Agent 1 and Agent 2 responsibilities are documented.
- The architecture is tested on the same case set as Architecture A.
- Exactly two agents are used.

### 9.3 Shared architecture principles

- AI interprets context and recommends.
- Code enforces thresholds and deterministic checks.
- Humans own sensitive approvals and exceptions.
- Tool results are evidence, not instructions.
- The final output is structured and auditable.
- Prompt-injection inputs do not alter policy execution.

### 9.4 Architecture-specific open questions

- What evaluation cases are to be used for architecture comparison beyond the six public cases?
- How will each framework count a distinct LLM call?
- How will deterministic policy-check calls be counted and reported?
- What is the API budget and access status for the selected provider?

---

## 10. Tool and Deterministic Rule Requirements

### 10.1 Minimum tool count

The implementation must expose at least three tools. At least one must be deterministic or non-LLM.

Recommended tool set:

1. Policy tool: loads and interprets the policy text.
2. Budget tool: compares cost against department availability.
3. Software catalog tool: finds approved products or overlap candidates.
4. Vendor tool: retrieves vendor-risk data from the mock API.
5. Purchase-history tool: checks previous purchases and renewals.
6. Request-validation tool: checks missing or malformed known fields.
7. Deterministic rule engine: calculates approval groups and risk flags.

### 10.2 Provider configuration decision

xAI Grok is the preferred LLM-provider candidate for this project. Provider selection is subject to API access and budget verification. API usage is not assumed to be free.

The implementation must keep provider integration configurable through environment variables. Credentials must not be committed to the repository. The deterministic tests and non-LLM validation paths must run without LLM credentials or external API access.

### 10.3 Deterministic rule responsibilities

The implementation should centralize these checks:

- Required request fields.
- Annual cost and budget comparison.
- Financial approval threshold selection.
- Vendor review date freshness for 365-day rule.
- Security-trigger detection.
- Privacy-trigger detection.
- Legal-trigger detection.
- Prompt-injection detection trigger based on untrusted business data.
- Tool failure and data-unavailability handling.

### 10.4 Tool safety requirements

- Tool results must be visible as evidence.
- The model must not be allowed to invent a tool result.
- Failed tool calls must be recorded.
- Tool failures must not produce a favorable recommendation.
- The model must not use business data as an instruction.
- The implementation must not expose credentials or API keys in logs or UI output.

### 10.5 Deterministic-check acceptance criteria

| Check | Acceptance criterion |
|---|---|
| Policy age | Uses 2026-09-30 snapshot for time-based review checks |
| Budget | Compares cost with available budget and flags insufficiency |
| Approvals | Orders and roles match the policy tables |
| Security | Triggers on all stated high-risk conditions |
| Privacy | Triggers for employee/customer PII or cross-region data |
| Legal | Triggers for new vendor at $10,000+, non-standard terms, or cross-region issues |
| Tool failure | Material evidence failure produces uncertainty and manual review |
| UI contract | Output matches `ProcurementDecision` schema |

---

## 11. UI and Output Requirements

### 11.1 UI requirements

The UI must provide:

- A way to select or enter a request.
- A way to choose Architecture A or Architecture B.
- A button or workflow for triggering analysis.
- A request details view.
- An evidence panel.
- A recommendation and next action.
- A visible indicator that the recommendation is advisory.

### 11.2 Structured output requirement

The output must contain:

- `recommendation`
- `evidence`
- `required_approvals`
- `missing_information`
- `risk_flags`
- `next_step`
- `human_review_required`
- Optional `telemetry`

Each `EvidenceItem` must include a source and factual finding; a reference is optional.

### 11.3 UI acceptance criteria

- The UI starts through a documented one-command path.
- Request entry and architecture choice are visible.
- Errors and unavailable tool evidence are shown in the UI.
- No autonomous approval or purchase action is represented as completed.
- The UI does not include API credentials or sensitive secrets.
- The user can inspect the exact evidence used in the recommendation.

---

## 12. Evaluation Requirements

### 12.1 Public evaluation

The final implementation must be evaluated on both architectures using the six public cases in [evals/public_cases.json](../evals/public_cases.json).

The required public-evaluation metrics are:

- Cases meeting minimum expectations.
- Average latency in milliseconds.
- Average LLM calls.
- Average tool calls.
- Correct policy and evidence-grounding behavior.
- Correct human escalation decisions.

The assessment requires actual measurements for both architectures on the same test set. It defines no numerical acceptance thresholds for latency, LLM calls, tool calls, or pass rate. The implementation must not invent targets. The results must be reported from measured runs, including any environment limitations or missing measurements.

### 12.2 Evaluation acceptance criteria

| ID | Description | Acceptance criteria | Verification |
|---|---|---|---|
| EVAL-001 | Both architectures must be evaluated against the same case set. | Public runner is run for each architecture with identical case IDs and expectations. | Compare CSV results and console output. |
| EVAL-002 | Architecture A baseline must be runnable. | `python evals/run_public_evals.py --architecture single` executes and returns rows for all public cases. | Runner output and generated CSV. |
| EVAL-003 | Architecture B must be runnable. | `python evals/run_public_evals.py --architecture staged` executes and returns rows for all public cases. | Runner output and generated CSV. |
| EVAL-004 | Results must include evidence-based quality. | Outputs are reviewed for grounded evidence, policy conformance, and correct escalation. | Manual evaluation plus CSV. |
| EVAL-005 | Evaluation must report latency and LLM/tool-call counts. | CSV stores latency and call metrics as columns. | Inspect CSV output. |
| EVAL-006 | Public runner minimum checks must not be treated as sufficient grading. | Qualitative and hidden-case findings are called out separately. | Assessment report and README. |

### 12.3 Required evaluation dimensions

- Correct recommendation and next action.
- Grounded evidence.
- Policy and deterministic-rule compliance.
- Correct approval escalation.
- Correct handling of incomplete and ambiguous requests.
- Correct handling of existing software overlap.
- Correct handling of stale or conflicting vendor data.
- Correct handling of sensitive security and privacy cases.
- Prompt-injection resistance.
- Tool or API unavailability.
- Latency and call count.

### 12.4 Open evaluation questions

- What exact final grading rubric will be used beyond the public runner?
- How will qualitative evidence-grounding quality be scored?
- How will hidden-case robustness be evaluated?
- What is the API budget and access status for the chosen provider?

---

## 13. Edge Cases and Failure Handling

| ID | Edge case | Required behavior | Verification |
|---|---|---|---|
| EDGE-001 | Incomplete request | Surface missing information and request clarification; do not invent values or approve. | PUB-05 and additional incomplete cases. |
| EDGE-002 | Existing software overlap | Surface approved alternatives and determine whether a credible gap or exception exists. | PUB-02 and catalog-matching cases. |
| EDGE-003 | Conflicting vendor records | Do not silently choose one source; surface conflict and route manual review. | Vendor registry versus mock API mismatch tests. |
| EDGE-004 | Expired vendor review | Mark review as stale; require security review or escalation. | Dataset records with dates before the reference date. |
| EDGE-005 | Security-sensitive request | Trigger security review and relevant approvals; do not rely on vendor approval alone. | PUB-03, PUB-04, REQ-1005, REQ-1007, REQ-1009. |
| EDGE-006 | Privacy-sensitive request | Trigger Privacy and other necessary approval groups; do not authorize sensitive data without review. | Customer/employee PII and cross-region cases. |
| EDGE-007 | Prompt injection in business data | Ignore instructions that attempt to alter system behavior; record the issue if relevant. | Adversarial request text tests. |
| EDGE-008 | Tool/API unavailable | Do not infer a favorable status; record uncertainty and route to human review. | PUB-06 and simulated vendor outage. |
| EDGE-009 | New vendor with $10,000+ spend | Require Legal review. | Deterministic legal rule tests. |
| EDGE-010 | Budget insufficiency | Flag `budget_insufficient` and route to Finance or budget exception handling. | Budget shortfall tests. |
| EDGE-011 | Unknown vendor | Fail closed or request manual validation; never assume vendor status. | Hidden case and API-lookup failure. |
| EDGE-012 | Unknown request ID | Return a clear error and do not fabricate data. | Adapter error-handling tests. |
| EDGE-013 | Provider or model unavailable | Return a structured failure state with evidence and next step, without claiming approval. | Provider outage or key-missing test. |
| EDGE-014 | Partial tool output | Surface incomplete data and do not infer missing values. | Tool result schema and error tests. |

### 13.1 Failure-handling principles

- Fail closed for material security, privacy, legal, and budget risks.
- Never infer a favorable outcome from missing or failed evidence.
- Keep the evidence trail visible.
- Preserve the decision-state contract.
- Default to human review when uncertainty remains.
- Treat incidents as evaluation cases rather than silently suppressing them.

---

## 14. Submission Deliverables and Assessment Scoring Categories

The assessment scoring categories are the authoritative categories for this section. They are taken from the original assessment PDF and must not be treated as deliverables. The repository does not contain numeric weights for individual deliverables beyond the assessment categories listed below.

| Assessment scoring category | Weight | Source status |
|---|---:|---|
| Product + workflow | 15% | Assessment PDF category |
| End-to-end product | 20% | Assessment PDF category |
| Agent + tool design | 20% | Assessment PDF category |
| Reliability + human controls | 15% | Assessment PDF category |
| Evaluation + comparison | 20% | Assessment PDF category |
| Engineering + communication | 10% | Assessment PDF category |

The following deliverables support those categories but are not additional scoring weights:

- Working local application.
- Architecture A and Architecture B implementations.
- Evidence-grounded recommendations and deterministic checks.
- Reproducible evaluation results.
- Architecture comparison and decision memo.
- README and submission documentation.

### 14.1 Required deliverable set

- Public GitHub repository.
- Working local application with one-command startup path.
- Architecture or workflow diagram and documented assumptions.
- Reproducible evaluation script and results.
- Architecture decision memo of no more than 500 words.
- No secrets committed; `.env.example` if needed.
- README covering setup, execution, workflow, architecture, tools/agents, assumptions, evaluation results, architecture comparison, final architecture decision, and known limitations.

### 14.2 Submission evidence requirements

The Git repository must contain:

- Source code.
- Data and policy assets.
- Evaluation results generated by the runner.
- Architecture decision memo.
- README with local setup and execution instructions.
- A clear record of all external dependencies and provider choices.
- No `.env` file or credentials.

---

## 15. Acceptance Criteria

### 15.1 End-to-end product acceptance

- [ ] The application starts via a documented one-command path.
- [ ] A user can select a real request and architecture.
- [ ] The application returns a valid `ProcurementDecision`.
- [ ] Recommendation, evidence, approvals, missing information, risks, and next step are visible.
- [ ] No purchase or approval action is performed by the system.
- [ ] Human review is required for nontrivial or sensitive decisions.

### 15.2 Architecture acceptance

- [ ] Architecture A returns valid decisions for public cases.
- [ ] Architecture B returns valid decisions for the same case set.
- [ ] Both architectures use the same contract and evaluation harness.
- [ ] At least three tools are visible and used by each architecture.
- [ ] At least one tool/check is deterministic.
- [ ] Tool results are visible as evidence.
- [ ] Architecture choice is justified by measured results.

### 15.3 Policy acceptance

- [ ] Required request fields are checked deterministically.
- [ ] Budget and approval thresholds use the policy data snapshot.
- [ ] Existing-software overlap is surfaced.
- [ ] Security, privacy, and legal triggers are enforced.
- [ ] Prompt injection is ignored and surfaced when relevant.
- [ ] Tool/API failures do not yield a favorable status.

### 15.4 Evaluation acceptance

- [ ] Both architecture runs generate results CSV files.
- [ ] The results include latency and LLM/tool-call counts.
- [ ] Minimum public expectations are checked.
- [ ] Qualitative grounding and escalation behavior are documented.
- [ ] Architecture comparison and recommended shipping decision are described.

### 15.5 Documentation acceptance

- [ ] README covers setup, execution, architecture, workflow, tools, agents, assumptions, results, comparison, decision, and limitations.
- [ ] Architecture decision memo is 500 words or fewer.
- [ ] Known limitations and unresolved questions are documented.
- [ ] Requirements, deliverables, and evidence are traceable to the source.

---

## 16. Existing Gaps and Risks

### 16.1 Implemented and verified

The following items are present in the repository, but they should not be considered fully verified until run in the target environment:

- Data files and integrity constraints are present.
- Mock vendor-risk API implementation exists.
- FastAPI, Streamlit, Pydantic, requests, and data-access dependencies are declared.
- The `ProcurementDecision` schema exists.
- Adapter function signature exists.
- Six public cases and a public-runner script exist.
- Evaluation CSV template exists.
- Architecture decision memo template exists.
- Workflow notes are present.
- `.env.example` exists and Git ignore rules exclude `.env`.

### 16.2 Partially implemented

| Area | Finding | Evidence |
|---|---|---|
| UI | UI scaffold loads request data, selects architecture, and displays analysis results; it does not implement the procurement workflow. | [app.py](../app.py) |
| Tool interfaces | `get_vendor_risk()` exists, but there are no full policy, budget, catalog, or purchase-history tools integrated to the adapter. | [src/vendor_client.py](../src/vendor_client.py), [src/data_access.py](../src/data_access.py) |
| Telemetry | Helper exists but does not prove call counts are integrated into a real implementation. | [src/telemetry.py](../src/telemetry.py) |
| Data access | Helpers are available, but no deterministic policy engine consumes them. | [src/data_access.py](../src/data_access.py) |
| Evaluation | Runner is present, but no implementation result or comparison metrics are available. | [evals/run_public_evals.py](../evals/run_public_evals.py) |
| README | Documentation describes the required flow but does not provide proof that all steps work. | [README.md](../README.md) |

### 16.3 Missing

- A working `handle_request` implementation.
- A concrete agent architecture.
- A working policy engine using deterministic rules.
- A complete tool inventory with at least three named tools.
- A staged/two-agent implementation.
- A real evidence panel with grounded findings.
- An architecture comparison with measured outputs.
- A complete architecture decision memo.
- A README containing verified evaluation results.
- A final public GitHub repository state.

### 16.4 Broken or blocked

- The adapter currently raises `NotImplementedError`, so the public evaluator stops immediately.
- The current UI cannot perform an actual analysis because the implementation is absent.
- The public evaluation cannot produce a valid architecture comparison until the adapter is implemented.
- The environment has not been verified because the task constraints prohibit package installation and environment modification.
- The PDF extraction utility is absent in the current environment; only repository source and task-provided text are available.

### 16.5 Not yet verified

- Dependency installation.
- Python version compatibility.
- Local startup of the mock API.
- Streamlit UI rendering.
- LLM-provider integration.
- Public evaluator run results.
- Architecture A and B behavior.
- Hidden-case handling.
- End-to-end procurement decisions.
- Architecture scoring and decision memo.

### 16.6 Minimum work required

The minimum work to satisfy the assessment is:

1. Implement the adapter with Architecture A and Architecture B.
2. Add deterministic request-validation, budget, overlap, approval, security, privacy, legal, and tool-failure checks.
3. Implement at least three tool-aware evidence gathering steps.
4. Produce grounded `ProcurementDecision` output.
5. Add a working UI and one-command startup path.
6. Run the public evaluator for both architectures.
7. Record latency, LLM calls, and tool-call counts.
8. Implement reliability and prompt-injection tests.
9. Write the final architecture decision memo and README.
10. Prepare a clean repository without secrets.

### 16.7 Optional improvements

Optional improvements that are not required for the assessment minimum include:

- A more advanced frontend.
- Additional caching.
- A more elaborate agent framework.
- Additional policy-rule configurability.
- A full audit log or data lineage view.
- Automated dependency or security scanning beyond the assessment requirements.
- Additional hidden-case test generation.

---

## 17. Assumptions and Open Questions

### 17.1 Assumptions

- The public evaluation runner is the minimum test harness and is the earliest authoritative behavior check.
- `ProcurementDecision` is the bounded product contract.
- The assessment expects an internal implementation rather than a purely static rules engine.
- The final implementation may use an LLM provider if credentials and an SDK are installed.
- The same request and architecture adapter can be used for both UI and evaluator paths.
- The project should remain Python-based unless a justified alternative is needed.

### 17.2 Open questions

1. What is the API budget and access status for xAI Grok?
2. What hidden-case evaluation criteria will be used by the grading system?
3. What is the expected level of auditability for tool calls and evidence lineage?
4. Are there required hidden cases that must be addressed beyond those present in the public dataset?

---

## 18. Recommended Implementation Milestones

### Milestone 1: Environment and starter-pack verification

- Confirm Python version and dependencies.
- Verify datasets and mock API.
- Validate the schema and public case references.
- Record any environment-specific blockers.

### Milestone 2: Domain rules, data sources, and deterministic checks

- Implement deterministic request validation.
- Implement budget and approval-threshold checks.
- Implement catalog overlap detection.
- Implement security, privacy, and legal trigger logic.
- Implement vendor-review freshness and conflict checks.
- Use the 2026-09-30 policy snapshot date.

### Milestone 3: Tool interfaces and structured outputs

- Implement at least three tools.
- Ensure tool results are evidence-backed and visible.
- Build the common decision contract.
- Create failure states for unavailable tools and material evidence gaps.

### Milestone 4: Minimum viable product UI and end-to-end workflow

- Implement a UI or equivalent request interface.
- Connect it to the common adapter.
- Display evidence, recommendations, and next steps.
- Preserve human approval obligations.

### Milestone 5: Architecture A single-agent baseline

- Wire the single agent to the tool set and policy engine.
- Validate the public cases.
- Measure and record latency and call counts.
- Fix grounding and policy compliance issues.

### Milestone 6: Architecture B staged/two-agent variant

- Define explicit stage interfaces and handoff contract.
- Implement the staged workflow.
- Ensure the final output is equivalent to Architecture A.
- Run the same public evaluation set.

### Milestone 7: Shared evaluation dataset and reproducible comparison

- Run both architectures on the same cases.
- Record pass, latency, LLM calls, tool calls, and qualitative findings.
- Export the results to the required CSV format.
- Compare architecture trade-offs.

### Milestone 8: Reliability testing and edge cases

- Test incomplete requests, overlap, conflicts, expired reviews, security/privacy cases, prompt injection, and tool failures.
- Check all failure modes avoid favorable assumptions.
- Add human-review and exception cases.

### Milestone 9: Submission documentation and verification

- Update README with setup, workflow, architecture, evaluation results, and assumptions.
- Write architecture decision memo under 500 words.
- Verify no secrets and clean Git state.
- Run final local startup and evaluator checks.
- Review all submission checklist items.

---

## 19. Out of Scope for the Initial Phase

The following are explicitly out of scope for the initial specification and implementation unless required by the assessment or a later decision:

- Production-grade procurement system integration.
- Enterprise identity, SSO, or role-management implementation.
- Actual purchase execution or payment processing.
- Automatic approval or budget modification.
- External live vendor assessment services.
- Real business integrations beyond the mock API.
- A full workflow engine or state machine.
- Enterprise audit retention beyond the implementation’s evidence logs.
- Complex frontend frameworks beyond the assessment’s starter environment.
- Fully generalized multi-tenant or fiscal-year architecture.
- Hidden-case development before the public implementation works.

---

## 20. Source Traceability

### 20.1 Source-backed facts

| Fact | Source |
|---|---|
| Assessment product and objective | Original Assessment 3 PDF; summarized in [README.md](../README.md) |
| Assessment deadline | Original Assessment 3 PDF; recorded as **8 October 2026** |
| Assessment scoring categories and weights | Original Assessment 3 PDF |
| Required output contract | [src/contracts.py](../src/contracts.py) |
| Public evaluation case count and commands | [evals/README.md](../evals/README.md) |
| Policy rules and reference date | [data/procurement_policy.md](../data/procurement_policy.md) |
| Data source roles | [data/README.md](../data/README.md) |
| UI scaffold behavior | [app.py](../app.py) |
| Mock API behavior and failure mode | [mock_api/app.py](../mock_api/app.py) |
| Decision memo template | [templates/architecture_decision.md](../templates/architecture_decision.md) |
| Submission checklist | [STUDENT_CHECKLIST.md](../STUDENT_CHECKLIST.md) |
| Data integrity rules | [tests/test_data_integrity.py](../tests/test_data_integrity.py) |
| Mock API tests | [tests/test_mock_api.py](../tests/test_mock_api.py) |
| One-command local startup | [run_local.py](../run_local.py) |
| Required no-secrets behavior | [.env.example](../.env.example), [.gitignore](../.gitignore) |

### 20.2 Project decisions

| Decision | Classification |
|---|---|
| Exactly two agents | Project design decision; not a PDF mandate |
| Agent 1 evidence gathering and tool coordination | Project design decision |
| Agent 2 evaluation, recommendation, and human handoff | Project design decision |
| xAI Grok as preferred LLM candidate | Project decision; subject to API access and budget verification |
| Existing Streamlit scaffold as default UI | Project decision based on repository inspection |

### 20.3 Source limitations

- The PDF was not extracted in the current environment because the required PDF text utility is unavailable.
- The repository provides the assessment source as a PDF and provides summary text in README and evaluator files; page-level citations are not available from the current extraction environment.
- No implementation-level execution results are available for the current repository.
- The current setup was not executed because the task deliberately prohibits altering the environment.

### 20.4 Inference and recommendation separation

| Classification | Example |
|---|---|
| Source-backed fact | The adapter must return a `ProcurementDecision`. |
| Source-backed fact | The assessment categories are Product + workflow, End-to-end product, Agent + tool design, Reliability + human controls, Evaluation + comparison, and Engineering + communication. |
| Repository inference | The adapter and UI are intended to be connected; this is supported by their code and README but not independently executed. |
| Engineering recommendation | Use a deterministic rules engine plus a single model stage where practical. |
| Project design decision | Use exactly two agents with Agent 1 and Agent 2 responsibilities. |
| Project decision | Prefer xAI Grok subject to API access and budget verification. |
| Open question | Whether hidden-case grading uses additional qualitative criteria. |

### 20.5 Accuracy and traceability rules for implementation

- Do not claim that a component works unless it is verified in the target environment.
- Do not treat the existence of files as proof of behavior.
- Do not infer approval or policy outcomes from vendor names or approved products alone.
- Do not silently modify policy thresholds.
- Do not use the computer’s current date for policy date checks.
- Do not fabricate results, metrics, or architecture behavior.
- Record unresolved ambiguities and confirm them before committing to a design or scoring assumption.

---

## 21. Final Specification Status

This document is the initial specification for Assessment 3. It is intentionally limited to analysis and requirements definition; it does not implement application functionality or modify working files.

The next implementation phase should begin only after the specification has been reviewed and the unresolved questions are answered or explicitly accepted as assumptions.
