# Implementation Specification

## Section 1: Scope and acceptance criteria

### 1.1 Product objective
The product is an internal procurement decision assistant for software and service requests. It must review a request against the policy in `data/procurement_policy.md`, gather supporting evidence from the provided datasets and mock vendor-risk API, apply deterministic rules for budget, approval thresholds, security/privacy/legal triggers, and missing/expired information, and produce a recommendation plus concrete next step for a human reviewer.

The recommendation is advisory only. The system must never make a purchasing decision on its own, approve spend, modify budgets, accept legal terms, or override required human controls.

### 1.2 Mandatory assessment deliverables
The implementation must include the following artifacts and behaviors:

- Working local application startup path
- UI for request details and recommendation summary
- Tool-backed evidence gathering with at least three tools
- At least one deterministic tool or policy engine
- Structured procurement decision output
- Single-agent baseline Architecture A
- Lightweight two-agent Architecture B
- Shared evaluation harness using the same public cases for both architectures
- Architecture decision memo and README documentation
- Reproducible local run and evaluation path

### 1.3 Definition of “working”
The implementation is considered working only if all of the following are true:

- UI loads locally and displays request details, evidence, recommendation, required approvals, missing information, risks, and next step
- Request handling calls the adapter `src/solution.py` and returns a `ProcurementDecision`-compatible object
- Tool outputs are visible and traceable to source records or endpoints
- Deterministic checks govern thresholds, budget comparisons, approvals, and missing-knowledge handling
- The product does not infer a favorable outcome when evidence is missing, conflicting, stale, or unavailable
- Human-review status and reasons are explicit
- Evaluation results are produced from the same public cases for both architectures

### 1.4 Mandatory requirements vs optional improvements
Mandatory requirements:

- UI requirement for request details, evidence, recommendation, and required approvals
- Shared policy contract and risk output contract
- Deterministic budget and approval logic
- At least three tools, with one deterministic tool
- Architecture A and Architecture B with the same policy and evaluation set
- Human-review and escalation treatment
- Risk and missing-information handling
- Public-case evaluation and measurement reporting

Optional engineering improvements:

- More polished dashboard design
- Better caching or batching in tool calls
- Additional telemetry dashboards
- Alternative UI frameworks
- Additional hidden-case tests or evaluation summaries

These improvements are allowed only if they do not change the object contract, policy logic, or mandatory human controls.

---

## Section 2: Existing system and component boundaries

### 2.1 Actual current application structure
The current workspace contains the following relevant components:

- `app.py`: Streamlit starter UI that displays a request selector and a “Run analysis” button
- `run_local.py`: starter local launch script that starts the mock vendor-risk API and optionally the UI
- `mock_api/app.py`: FastAPI service with health check and vendor-risk endpoint
- `src/contracts.py`: canonical output contract and validation schema
- `src/data_access.py`: helper layer expected to load business datasets
- `src/vendor_client.py`: expected external vendor-risk client
- `src/solution.py`: required adapter entry point
- `src/sample_output.json`: sample decision payload
- `evals/public_cases.json`: six public evaluation cases and expected behavior
- `evals/run_public_evals.py`: evaluator and contract validation runner
- `data/`: policy and business fixtures

### 2.2 Existing vs scaffold vs missing
Existing and usable:

- Policy source in `data/procurement_policy.md`
- Synthetic request data under `data/requests.json`
- employee, budget, catalog, vendor, and purchase-history source files
- mock vendor-risk API and route contract
- canonical contract in `src/contracts.py`
- public-eval harness and case schema
- Streamlit starter UI

Scaffolds and placeholders:

- `app.py` is a starter UI and not a finished procurement workflow
- `run_local.py` starts services but does not implement decision logic
- `src/solution.py` raises `NotImplementedError`
- `src/data_access.py` and `src/vendor_client.py` are expected helper boundaries but require completion

Missing or not yet defined:

- real deterministic policy engine and full tool adapters
- complete orchestration for Architecture A and Architecture B
- robust evaluation instrumentation and architecture comparison logging
- final README and architecture decision memo

### 2.3 Intended responsibilities
UI responsibilities:

- render request details
- display evidence provenance and unresolved factors
- show recommendation, risk flags, required approvals, missing information, and next steps
- clearly state that recommendation is not approval

Orchestrator responsibilities:

- accept request and architecture mode
- call tool layer in a deterministic order
- apply policy checks and collect evidence
- format decision object and validate it against contract
- pass structured output to UI and evaluator

Deterministic rules responsibilities:

- financial threshold calculation
- budget comparison
- missing-field and invalid-value checks
- approval list normalization
- stale/expired assessment detection
- conflict detection and tool failure categorization
- policy enforcement without LLM discretion

Tool responsibilities:

- request/employee lookup
- software-overlap lookup
- department budget lookup and arithmetic
- vendor-risk lookup and status evaluation
- policy text retrieval and policy-section anchoring
- evaluation/debug logging

Data access layer responsibilities:

- read CSV/JSON files
- normalize source data fields
- return structured records for policy checks and evidence references
- preserve provenance and exact records used

Vendor client responsibilities:

- call mock API with timeout and error handling
- distinguish 404, 503, malformed response, and connection failure
- preserve vendor-risk result and failure message for human review

Contracts responsibilities:

- guarantee required fields, canonical values, and validation shape
- reject duplicates and unsupported values
- standardize evidence records and telemetry schema

Evaluator responsibilities:

- validate case schema and request IDs
- check output contract and policy expectations
- compare Architecture A and Architecture B on the same cases
- record latency and call counts using consistent measurement boundaries

---

## Section 3: Shared decision contract

### 3.1 Output model
The system must produce a `ProcurementDecision` compliant with `src/contracts.py`.

Required fields:

- `request_id`: unique request identifier, e.g. `REQ-1001`
- `recommendation`: human-readable recommendation
- `recommendation_code`: one of:
  - `proceed_to_required_approvals`
  - `request_clarification`
  - `route_for_budget_exception`
  - `route_for_manual_review`
- `evidence`: list of `EvidenceItem`
- `required_approvals`: deduplicated canonical approval roles
- `missing_information`: deduplicated list of missing fields
- `risk_flags`: deduplicated canonical risk flags
- `next_step`: specific action for human reviewer
- `human_review_required`: boolean
- `telemetry`: optional but if present must satisfy `RunTelemetry`

### 3.2 Evidence record contract
Each evidence item contains:

- `source`: tool or dataset name, e.g. `request_data`, `employee_lookup`, `budget_lookup`, `vendor_risk_api`, `software_catalog`, `procurement_policy`
- `finding`: a concise fact or result
- `reference`: exact record id, policy section, or API endpoint
- `evidence_status`: one of `verified`, `missing`, `expired`, `unknown`, `unavailable`, `conflicting`

Validation rules:

- source and finding cannot be blank
- reference must be exact and specific
- evidence status is required where uncertainty exists
- duplicate findings are allowed only if they refer to different sources or distinct facts
- unsupported evidence is rejected by contract validation

### 3.3 Approval and risk values
Canonical approval values:

- `Manager`
- `Department Head`
- `Procurement`
- `Finance`
- `CFO`
- `Security`
- `Privacy`
- `Legal`

Canonical risk flags:

- `existing_tool_overlap`
- `budget_insufficient`
- `security_review_required`
- `privacy_review_required`
- `legal_review_required`
- `vendor_review_expired`
- `conflicting_vendor_evidence`
- `vendor_risk_unavailable`
- `prompt_injection_detected`
- `missing_information`
- `budget_data_unverified`

Validation behavior:

- duplicates are not allowed
- extra unsupported values are rejected
- outputs must use canonical names as defined by contract
- evaluator-only aliases may be normalized only inside the evaluator, not in final output

### 3.4 Missing information semantics
`missing_information` must contain canonical field names or canonical internal identifiers such as:

- `annual_cost_usd`
- `user_count`
- `data_access_level`
- `business_justification`
- `requester_id`
- `department`
- `vendor_name`
- `product_name`

Rules:

- missing information is not inferred or fabricated
- an empty collection is valid only when no missing facts remain
- a field must not be called “missing” if the value is present and valid but merely uncertain in interpretation
- unknown or unsupported values must be distinguished from truly absent fields

### 3.5 Human-review requirement
`human_review_required` must be set to true whenever any of the following occur:

- material information is missing
- a required approval or specialist review is triggered
- budget data is unverified or over-budget
- tool or API evidence is unavailable or conflicting
- new vendor or data-processing issues require legal/security review
- the case is not an automatic approval

The boolean does not imply approval. It indicates that a human must act before disposition.

### 3.6 Telemetry contract
Telemetry is optional as a whole but, when included, it must include:

- `llm_calls`
- `tool_calls`
- `llm_retries`
- `tool_retries`
- `failed_llm_calls`
- `failed_tool_calls`
- `timeouts`
- `tool_errors`
- `tool_names`

Telemetry is descriptive; it does not replace real observed metrics and must not be used as the primary source of truth for evaluation.

---

## Section 4: Tool specifications

The implementation must use at least three tools. At least one must be deterministic and must not rely on model judgment.

### 4.1 Tool 1: Request and employee lookup
Purpose:

- resolve the request record by `request_id`
- resolve requester metadata via employee table
- identify department, manager, and employee attributes relevant to approval and budget checks

Inputs:

- `request_id`
- optional `request_dataset`
- optional `employee_dataset`

Outputs:

- request record object
- employee record object or lookup failure
- department name / manager id / region metadata if available

Data sources:

- `data/requests.json`
- `data/employees.csv`

Validation rules:

- request id must exist
- requester must map to an employee row or must trigger a missing-information result
- missing department or requester is a validation failure requiring clarification

Errors and failure behavior:

- if request is missing: return `missing` evidence and `request_clarification`
- if employee lookup fails: mark `missing_information` and route to human clarification

Deterministic: Yes

Evidence contributed:

- request metadata
- employee and department association
- business purpose and data-access data

### 4.2 Tool 2: Software catalog and purchase-history overlap lookup
Purpose:

- determine whether the requested product or vendor already exists in approved software or purchase history
- assess whether the request is a duplicate, an overlapping product, or a new need with a credible difference

Inputs:

- product name
- vendor name
- category
- request scope and use case

Outputs:

- matched software catalog rows
- prior purchase history rows
- overlap assessment with confidence and reason

Data sources:

- `data/software_catalog.csv`
- `data/purchase_history.csv`
- request data and business justification

Validation rules:

- exact vendor or product matches are stronger than category-only matches
- category-only similarity is not sufficient to assert duplicate functionality
- overlap result must include evidence and a reason if a request is not a confirmed duplicate

Errors and failure behavior:

- missing or empty catalog rows: treat as no match, not favorable evidence
- malformed rows: record evidence as `unknown` and send to human review

Deterministic: Yes, with optional LLM reasoning overlay

Evidence contributed:

- `existing_tool_overlap`
- prior product or reuse evidence
- note when the product is not determined to be redundant

### 4.3 Tool 3: Budget calculation and department budget lookup
Purpose:

- resolve department budget row
- compare request annual cost with available software budget
- identify over-budget or missing budget information conditions

Inputs:

- department name
- annual cost
- budget dataset records

Outputs:

- annual budget
- committed spend
- available budget
- derived available amount if needed
- over-budget decision

Data sources:

- `data/department_budgets.csv`
- `data/README.md` budget formula guidance

Validation rules:

- compare requested annual cost to the available budget using exact decimals
- if required values are missing or inconsistent, do not assume a pass
- if budget is below request cost, create `budget_insufficient` and route for Finance exception

Errors and failure behavior:

- missing row or missing components -> `budget_data_unverified`
- arithmetic mismatch -> `budget_data_unverified`
- invalid negative numbers -> `budget_data_unverified`

Deterministic: Yes

Evidence contributed:

- actual budget values
- `budget_insufficient`
- `budget_data_unverified`

### 4.4 Tool 4: Vendor-risk status lookup and conflict handling
Purpose:

- retrieve vendor security assessment and legal-risk metadata from the external vendor-risk API
- compare registry values with external service values
- surface unavailability, expiration, or conflict states

Inputs:

- vendor name
- vendor registry row
- mock API endpoint

Outputs:

- vendor security status, review date, and related risk metadata
- conflict/warning objects when registry and API disagree
- error or unavailability metadata

Data sources:

- `data/vendors.csv`
- `data/vendor_risk.json`
- `mock_api/app.py`
- external vendor-risk API at `http://127.0.0.1:8001/vendor-risk/{vendor_name}`

Validation rules:

- current assessment window is 365 days from review date using the policy date snapshot
- missing, expired, unknown, or unavailable assessments require security/manual review
- conflicts must be reported, never silently overridden

Errors and failure behavior:

- HTTP 404: missing record (`missing` evidence)
- HTTP 503 or timeout: `vendor_risk_unavailable`
- malformed response: `unknown`/`unavailable` with manual review

Deterministic: Mostly yes; network and status parsing must be deterministic even when data is absent

Evidence contributed:

- security review status
- vendor review freshness
- conflict or API outage signals
- legal/privacy triggers where supported by evidence

### 4.5 Tool 5: Policy text retrieval and rule binding
Purpose:

- anchor decision logic to the authoritative policy source
- link outputs to relevant policy sections and document what rule triggered the approval or review

Inputs:

- policy file path or content
- rule identifiers or section references

Outputs:

- relevant policy sections and enforcement result
- rule mapping for evidence items

Data sources:

- `data/procurement_policy.md`

Validation rules:

- the output must cite the rule section or explain when the rule was applied
- policy text is authoritative; hidden implementation should not add new policy thresholds

Errors and failure behavior:

- if policy file is unavailable, stop and flag a system configuration problem; do not invent a rule

Deterministic: Yes

Evidence contributed:

- rule basis for approvals, missing information, and review triggers

---

## Section 5: Deterministic policy engine

### 5.1 Required request information
The policy requires the following information when applicable:

- requester and department
- product/vendor
- annual cost or reasonable annual estimate
- number of users/licenses
- business purpose
- intended data-access level
- required integrations

Interpretation:

- if a required field is absent, null, blank, unknown, or inadequate, the request is not ready for approval
- do not invent a value; request clarification
- `unknown` and `empty` are not equivalent to explicit “none” in integration data

### 5.2 Approval tiers
Annualized spend sets the minimum business approvals:

- Up to $1,000: Manager
- $1,000.01 to $10,000: Department Head + Procurement
- $10,000.01 to $25,000: Department Head + Finance + Procurement
- Above $25,000: Department Head + Finance + CFO + Procurement

Implementation rules:

- cost must be validated first; no financial approval tier is generated for missing or invalid cost
- duplicate roles are removed
- specialist approvals are added on top of financial approvals when required by security/privacy/legal rules

### 5.3 Budget availability and shortfalls
The policy says:

- if cost is within the department’s available budget, continue review
- if it exceeds available budget, flag `budget_insufficient` and route to Finance exception review
- positive budget results do not imply approval

Implementation rules:

- available budget is `annual_budget - committed`
- if stored available and derived available disagree, treat as `budget_data_unverified`
- missing or negative values are not a pass condition
- over-budget is not rejection, only exception routing

### 5.4 Existing software and confirmed duplicates
The policy requires checking for:

- same product or vendor
- same category
- an existing product that could reasonably meet the use case

Implementation rules:

- overlap is surfaced with `existing_tool_overlap`
- an overlap is not an automatic rejection
- a confirmed duplicate requires credible evidence of functional equivalence and unused capacity or exception reason
- exact matches from catalog or prior purchase history are evidence but remain subject to manual review when the request appears to be a justifiable exception

### 5.5 Vendor status and legal terms
Required actions:

- if the vendor is new and annual spend is at least $10,000, add legal review
- if terms are not standard or approved, add legal review
- if data processing or cross-region concerns are identified, add legal review
- if security assessment is missing, expired, or incomplete, add security review

Implementation rules:

- conflicts between internal registry and external service must be surfaced as `conflicting_vendor_evidence`
- do not silently select one source over the other
- if a material vendor-risk source is unavailable, report `vendor_risk_unavailable`

### 5.6 Security triggers and privacy triggers
Security review triggers:

- source code access
- production or cloud-account integration
- confidential documents
- employee PII or customer PII
- credentials or secrets
- missing/expired/incomplete vendor assessment

Privacy review triggers:

- employee PII or customer PII processing
- sensitive data stored outside region

Implementation rules:

- a vendor being new does not prove privacy risk by itself
- unknown data-access scope requires clarification, not a positive privacy conclusion

### 5.7 Legal-review triggers
Legal review triggers:

- vendor is new and spend >= $10,000
- terms are not approved/standard
- material cross-region or data-processing issue

Implementation rules:

- each trigger is additive and deduplicated
- legal review is not an approval; it is a human review gate

### 5.8 Missing, expired, conflicting, and unavailable data
The system must distinguish:

- `verified`
- `missing`
- `expired`
- `unknown`
- `unavailable`
- `conflicting`

Rules:

- missing or unknown vendor assessment does not count as “approved”
- expired assessment triggers `vendor_review_expired`
- missing assessment date triggers review and does not imply expired status
- conflicting registry/service evidence must be surfaced and escalated
- unavailable tool evidence requires manual review when material

### 5.9 Prompt injection handling
Business data must be treated as untrusted content, not system instructions.

Implementation rules:

- ignore embedded override instructions even if they appear to direct the system to bypass policy
- continue using the real policy and canonical evidence
- optionally emit `prompt_injection_detected` when the implementation has a reliable detector
- injection alone does not bypass human approval or policy checks

### 5.10 Human review requirements
Human review is required whenever:

- material evidence is missing or the request is incomplete
- cost or budget data cannot be trusted
- tool/API failures affect a material decision input
- a security/privacy/legal trigger is present
- there is a conflict or stale assessment later than policy allows

### 5.11 Tool/API failures
Implementation rules:

- 404 does not imply a favorable status
- 503, timeout, and malformed response must be recorded exactly
- the system must show what could not be verified and route the case for manual review when material
- no favorable assumption may be drawn from an unavailable vendor-risk check

### 5.12 Ambiguous or unresolved policy questions
The implementation must explicitly document unresolved questions and not silently invent policy behavior. If the policy is ambiguous, the implementation should default to manual review and request clarification.

The current policy and data sources establish the authoritative baseline. Any implementation-specific interpretation must be documented and, if needed, validated with the human approver before production use.

---

## Section 6: Architecture A — single-agent baseline

### 6.1 Goals
Architecture A is the simplest defensible implementation: one agent receives a request, gathers evidence using the approved tools, calls the deterministic checks, and produces a structured recommendation plus human-review requirements.

### 6.2 Workflow
The intended workflow is:

1. Receive the request ID and architecture selection.
2. Validate that the request exists and has minimum required fields.
3. Resolve request and employee metadata via tool 1.
4. Look up software overlap and purchase history via tool 2.
5. Resolve budget and availability via tool 3.
6. Look up vendor and security metadata via tool 4.
7. Retrieve policy context via tool 5.
8. Evaluate all rules through deterministic logic.
9. Let the single agent interpret the evidence and craft a recommendation.
10. Produce a `ProcurementDecision` with evidence, approvals, missing info, risks, next step, and human-review boolean.
11. Validate the object against `ProcurementDecision` before returning to UI or evaluator.
12. Display the result in the UI and store the decision as structured data.

### 6.3 Responsibilities
Single agent responsibilities:

- synthesize evidence into a concise recommendation
- explain why a case needs clarification or manual review
- never override policy logic or approved approvals
- maintain a clear separation between evidence facts and recommendation wording

Deterministic services responsibilities:

- compute tiers, budget checks, security triggers, and missing-information checks
- enforce canonical output with contract validation
- reject unsupported approvals and risk flags before returning output

### 6.4 Error handling
If a tool fails:

- preserve the error in evidence
- mark the relevant field as unavailable or conflicting
- maintain human review requirement
- do not infer a favorable result

If a request is missing information:

- set `request_clarification` recommendation code
- list missing fields exactly
- do not recommend approval

If policy or contract validation fails:

- return a validation error or route to manual review
- do not silently bypass the validation layer

### 6.5 Acceptance tests for Architecture A
- request with valid complete data and normal approval flow
- over-budget request with `budget_insufficient`
- missing fields and clarification route
- expired or missing vendor assessment
- tool outage scenario via 503 or timeout
- injection payload in business text
- existing overlap without confirmed duplication
- manual-review route when registry and API disagree

---

## Section 7: Architecture B — staged/two-agent variant

### 7.1 Design goals
Architecture B adds a lightweight staging layer without inventing extra orchestration or adding hidden complexity. The goal is to separate evidence collection from recommendation synthesis while preserving the same policy and contract.

### 7.2 Agent responsibilities
Agent 1: Evidence gathering and normalization

Inputs:

- request ID
- tool access layer
- policy source

Outputs:

- normalized facts object
- evidence list with references and statuses
- list of missing information items and risk signals from deterministic checks

Boundaries:

- responsible for retrieving and validating source evidence
- not responsible for final approval decision
- does not invent facts or override policy logic

Agent 2: Evaluation and recommendation

Inputs:

- structured evidence bundle
- deterministic policy results
- rendered missing-information and risk flags

Outputs:

- final recommendation text
- `recommendation_code`
- `required_approvals`
- `next_step`
- `human_review_required`

Boundaries:

- interprets and recommends based on the evidence
- cannot override required approvals or policy checks
- must still return contract-compliant output

### 7.3 Shared deterministic services
Both architectures use the same shared services:

- request validation
- budget arithmetic
- approval threshold logic
- tool failure categorization
- output contract validation
- public-case evaluator and metrics collection

No architecture gets a different policy or different approval thresholds.

### 7.4 What Architecture B adds over Architecture A
Architecture B adds:

- explicit evidence-preparation phase with a structured fact bundle
- separation of concerns between evidence gathering and recommendation reasoning
- clearer auditability of the fact pipeline and simplified debugging

Architecture B does not add:

- more than two agents
- additional decision authority
- separate approval logic or different policy rules
- hidden exemptions or alternative governance

### 7.5 Architecture B failure behavior
If Agent 1 cannot gather facts:

- the evidence bundle contains missing/unavailable facts
- Agent 2 must still recommend manual review or clarification

If Agent 2 tries to invent an approval not supported by evidence:

- contract validation rejects the output
- a downstream check marks the case as invalid

### 7.6 Architecture B acceptance tests
- same six public cases as Architecture A
- same missing-field case
- same conflict and outage cases
- same budget and approval comparisons
- same UI and structured output contract

---

## Section 8: Security and human controls

### 8.1 Prompt injection isolation
Business content coming from request text, vendor descriptions, notes, or API text is treated as untrusted data. It must never override system instructions or policy logic.

Implementation requirements:

- policy logic is loaded from code and policy file, not from business text
- embedded instructions are ignored before any recommendation logic is applied
- detector output may optionally be represented as `prompt_injection_detected`
- detection is never used as a reason to skip required policy checks

### 8.2 Preventing unsupported claims
Implementation requirements:

- every recommendation must be grounded in explicit evidence items
- if the evidence is missing or conflicting, the recommendation must route to clarification or manual review
- unsupported or fabricated vendor, cost, or security claims are rejected by validation
- no output may state a purchase is approved by the system

### 8.3 Conflicting sources
When the internal vendor registry and vendor-risk API disagree:

- preserve both sources
- add `conflicting_vendor_evidence`
- route to Security or manual review
- do not silently prefer one side

### 8.4 Human-review triggers
Human review is explicitly required for:

- missing information
- budget insufficient or unverified
- expired or missing vendor assessments
- security, privacy, and legal triggers
- tool/API failure on material evidence
- conflicting or ambiguous evidence
- any policy exception or manual override

### 8.5 Human-controlled actions
The system must not autonomously do any of the following:

- purchase software
- approve spend
- change budgets
- accept vendor legal terms
- override Security/Privacy/Legal review steps
- treat a recommendation as final approval

### 8.6 Tool unavailability policy
If a tool or API cannot be reached:

- record the failure and source endpoint
- do not infer safety or approval
- route to manual review where the missing fact is material
- show the uncertainty directly in UI and evidence list

---

## Section 9: UI and user workflow

### 9.1 Required screens and components
UI requirements:

- Request details panel
- Evidence panel with source and status
- Recommendation panel
- Required approvals panel
- Missing information panel
- Risk flags panel
- Next step panel
- Human review status banner

### 9.2 User flow
The user flow should be:

1. Select request
2. Choose architecture
3. Click analysis
4. Display evidence summary and recommendation
5. Show required approvals and missing-information list
6. Show a human-review warning if relevant
7. Present next-step instructions for the actual approver

### 9.3 UI constraints
The UI must:

- clearly separate evidence from recommendation
- clearly show uncertainty and missing data
- not imply an approval when only a recommendation is present
- show the role of human reviewers in approval and exceptions
- render structured JSON or equivalent readable decision output

---

## Section 10: Evaluation plan

### 10.1 Public and edge-case execution
The evaluation must run the same six public cases against both architectures.

The same evaluation conditions must be used for both architectures:

- same request order
- same policy snapshot
- same mock vendor-risk API
- same tool behavior and retry rules
- same environment and dataset files
- same evaluator and case schema

### 10.2 Expected results and schema validation
The evaluator validates:

- case schema completeness
- required and forbidden approvals
- required and forbidden risk flags
- missing-information set
- recommendation code and human-review requirement
- next-step phrase checks
- evidence presence and grounding requirements

Machine-checkable results include:

- pass/fail for each public case
- pass/fail for missing information
- pass/fail for required/forbidden approval values
- pass/fail for unsupported risk flags
- pass/fail for evidence reference matching

Qualitative review remains required for whether the recommendation is truly grounded and whether the human reasoning is sound.

### 10.3 Evaluation dimensions
The implementation must evaluate both architectures on:

- correctness of recommendation and next action
- evidence grounding
- policy compliance
- correct escalation and human review
- latency
- LLM call count and tool call count

### 10.4 Required edge cases
The implementation must cover these behaviors:

1. Incomplete or ambiguous requests
2. Existing software that may already solve the need
3. Conflicting or expired vendor information
4. Security-sensitive requests or approval thresholds
5. Prompt injection embedded inside business data
6. Tool/API unavailability

Each edge case must have a test and a documented handling strategy.

### 10.5 Grounding review protocol
A human or reviewer workflow records:

- case ID
- reviewer identity
- notes
- boolean checklist results for each required evidence item
- final pass or fail status

The output is only considered a pass if the grounding review is complete and internally consistent.

---

## Section 11: Measurement and comparison protocol

### 11.1 Metrics captured
The implementation must collect and compare:

- end-to-end latency for each case
- LLM calls and retries
- tool calls and retries
- failed calls and timeout counts
- per-case pass/fail status
- aggregate pass rate across six public cases

### 11.2 Measurement windows
Latency should be measured using a monotonic timer from immediately before `handle_request(...)` and continuing through output validation. It should include model/tool work and retries, but exclude case-loading and post-case evaluation scoring.

LLM and tool call counts are measured at the provider and tool dispatch layers; retries count as additional attempts, not as hidden execution events.

### 11.3 Equivalent conditions
Both architectures run under equivalent conditions:

- same request set and ordering
- same policy and data snapshot
- same mock API and tool layer
- same retry policy and timeout policy
- same evaluator and case schema
- same model/provider configuration where applicable

### 11.4 Reporting limitations
Implementation must clearly state where metrics may be unavailable or limited. If instrumentation is not yet present, the report must say that call counts are unavailable rather than zero or implicit. This is a required honesty standard.

---

## Section 12: Testing strategy

### 12.1 Deterministic rule tests
Tests for:

- approval thresholds
- budget comparisons
- missing and invalid field handling
- stale vendor review detection
- overlap detection and non-redundancy determination
- prompt injection handling

### 12.2 Contract validation tests
Tests for:

- required fields present
- duplicate approvals and risk flags rejected
- unsupported values rejected
- canonical names enforced
- `telemetry` validation rules

### 12.3 Tool and failure-mode tests
Tests for:

- 404 missing vendor record
- 503 unavailable vendor service
- timeout and connection failure
- malformed JSON response
- conflicting vendor registry and mock API values

### 12.4 Public-case evaluation tests
The six public cases must be run against Architecture A and Architecture B using the same evaluation harness.

### 12.5 Edge-case tests
Tests for:

- incomplete requests
- existing overlap vs duplicate
- security and privacy triggers
- stale recommendations and manual review
- prompt injection in request and vendor data
- untrusted manufacturer or vendor notes

### 12.6 UI smoke tests
Tests for:

- selecting request in UI
- showing evidence and recommendation
- confirming human-review banner appears when required
- displaying missing information and risk flags

### 12.7 Architecture comparison checks
Check that both architectures:

- use the same policy contract
- return the same schema-compliant output format
- run against the same case list
- produce comparable pass/fail metrics and latency windows

---

## Section 13: Local setup and run workflow

### 13.1 Current environment and dependency status
The repository currently includes:

- `requirements.txt` with Python dependencies including `fastapi`, `uvicorn`, `pydantic`, `pandas`, `requests`, `python-dotenv`, `streamlit`, and `httpx`
- a mock API served by `uvicorn` on port 8001
- a Streamlit starter UI launched by `python -m streamlit run app.py --server.port 8501`

### 13.2 Intended startup workflow
The implementation should follow the existing documented flow:

1. create and activate virtual environment
2. install dependencies from `requirements.txt`
3. run `python verify_setup.py`
4. if needed, copy `.env.example` to `.env`
5. run `python run_local.py`
6. run public-case evaluation against `Architecture A` and `Architecture B`

### 13.3 Commands to validate during implementation
These are the commands that should be validated once implementation work begins:

- `python verify_setup.py`
- `python run_local.py`
- `python evals/run_public_evals.py --architecture single`
- `python evals/run_public_evals.py --architecture staged`
- `python evals/run_public_evals.py --validate-only`

### 13.4 Documented blockers and verification status
The current specification phase does not claim that these commands have been run successfully. The environment is not yet verified for end-to-end runtime due to the requirement to avoid implementation and dependency installation in this specification step.

Any implementation work must validate these commands and record if runtime blockers remain.

---

## Section 14: Traceability matrix

| Assessment requirement | Planned component | Verification method | Acceptance criterion | Architecture(s) affected |
|---|---|---|---|---|
| Product UI | `app.py` and supporting frontend state | UI smoke tests | Request details, evidence, recommendation, next action visible | A and B |
| At least three tools, one deterministic | Tool layer and policy engine | Source review / tests | 3+ tools, at least one deterministic | A and B |
| Structured output contract | `src/contracts.py` + output builder | Contract tests | Required fields and canonical values | A and B |
| Human handoff | Recommendation and next step flow | Evaluation and UI tests | Human review required where needed | A and B |
| Architecture A baseline | single-agent orchestrator | Public-case evaluation | Works independently | A |
| Architecture B staged variant | two-agent orchestrator | Public-case evaluation | Same contract and policy as A | B |
| Correctness and policy compliance | deterministic rules + evaluator | Public evaluation | Required cases pass | A and B |
| Grounded evidence | tool outputs + evidence references | grounding review | evidence source and finding matches required references | A and B |
| Latency and call counts | instrumentation | measurement check | consistent metrics and reporting | A and B |
| Edge cases | tool and policy tests | edge-case suite | all listed edge cases handled | A and B |
| README and decision memo | docs output | review checklist | submission package complete | A and B |

---

## Section 15: Implementation sequence

1. Resolve specification blockers
   - confirm policy interpretation and required data fields
   - confirm tool and data source boundaries
   - confirm evaluation and comparison plan

2. Implement and test shared contracts, tools, and deterministic rules
   - finalize `data_access` functions
   - implement vendor client
   - implement strict validation and evidence tracking
   - validate the contract with sample outputs and edge cases

3. Build Architecture A
   - implement single request-to-recommendation flow
   - validate public cases and missing-information scenarios

4. Validate Architecture A against public and edge-case tests
   - run the six cases and required edge-case suite
   - check decision structure and evidence grounding

5. Build Architecture B
   - create evidence-gathering agent and recommendation agent
   - keep same contract and policy rules

6. Evaluate both architectures using the same test set and measurement protocol
   - run both approaches under equivalent conditions
   - retain metrics and case-by-case logs

7. Make the evidence-backed ship decision
   - choose the simpler architecture if it performs as well as or better than the more complex variant
   - document why the chosen design satisfies the product objective

8. Complete submission documentation
   - final README
   - architecture decision memo
   - architecture/workflow diagram
   - evaluation results and study notes

Exit criteria for each phase:

- contract validation passes for all cases
- policy checks are deterministic and reviewable
- no hidden implementation bypasses human review
- evaluator passes and metrics are captured honestly

---

## Section 16: Assumptions and unresolved decisions

### 16.1 Policy facts that are settled
- The authoritative policy source is `data/procurement_policy.md`.
- The reference date for age-based checks is `2026-09-30`.
- The contract in `src/contracts.py` is the canonical output contract.
- The public evaluation runner and case set are the baseline comparison standard.

### 16.2 Implementation choices that require explicit documentation
- whether to treat the 365-day boundary inclusive or exclusive
- whether budget “available” should be taken only from stored value or derived value when stored value is missing
- whether to expose optional `prompt_injection_detected` in the UI as a warning versus evidence only
- how to handle provider-specific tool retry and timeout policies in local instrumentation

### 16.3 Assumptions requiring human confirmation before production
- whether a policy owner accepts the chosen 365-day boundary handling as the final production rule
- whether same-product and same-category overlap should require explicit manual review before any exception is granted
- whether the final architecture decision should prefer simplicity or optimization under constrained latency

These points must be documented in implementation and design review notes before production deployment.

---

## Summary
This implementation specification defines a complete, testable path for building both Architecture A and Architecture B without changing the authoritative policy or source fixtures. It aligns the UI, tool layer, deterministic policy engine, shared decision contract, and public evaluation process to the actual repository and assessment requirements while preserving human authority at every approval-critical step.
