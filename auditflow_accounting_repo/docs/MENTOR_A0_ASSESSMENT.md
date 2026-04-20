# Mentor A0 Assessment

## Objective
Assess the current multi-agent implementation against the mentor package before refactoring runtime behavior.

The mentor package reframes the product as a scoped multi-agent audit support tool for memoranda and walkthroughs related to payments, accounting entries, and operational documentation. The target answer should focus on whether the document presents relevant inconsistencies in documentation, approval, value, classification, or minimum adherence to the defined normative scope.

## Current Multi-Agent Flow
The current API dependency constructs the multi-agent stack in `backend/app/api/analysis.py`:
- `DocumentUnderstandingAgent`
- `RedFlagAgent`
- `AccountingAuditAgent`
- `ReviewerAgent`
- `ReportAgent`

The runtime flow is coordinated by `MultiAgentAnalysisOrchestrator.enrich_report` in `backend/app/agents/orchestrator.py`. It runs document understanding, red flag detection, accounting/audit classification, reviewer consolidation, then report enrichment.

The existing document-analysis service still owns the main pipeline in `backend/app/services/analysis/document_analysis_orchestrator.py`:
1. load stored document metadata and file
2. parse document
3. chunk document
4. extract accounting process
5. retrieve knowledge context
6. run risk inference
7. build base `AnalysisReport`
8. optionally enrich through the multi-agent orchestrator
9. persist the final report

This means the multi-agent flow is currently an enrichment layer over the original pipeline, not yet the primary source of the final answer.

## Where Scope Is Currently Defined
Scope is currently implicit and spread across several places:
- Accepted document formats are defined by parsing/storage behavior, not by mentor product scope. `DocumentMetadata` stores filename/content type, but has no document category field.
- `DocumentUnderstandingAgent` extracts generic process entities from any parsed text.
- `RedFlagAgent` defines deterministic red flag categories in `RedFlagType`.
- `AccountingAuditAgent` defines audit implication categories in `AccountingAuditCategory`.
- `ReviewerAgent` normalizes red flag categories into reviewer categories.
- Prompt builders include safety instructions, but do not yet encode the mentor-approved document categories or answer space.

Missing for A1:
- explicit supported document categories: memorandum, walkthrough, payment request, accounting support memo
- explicit normative scope: NBC TG / CPC 00 (R2), LC 214/2025 within scoped use case
- explicit final answer values: YES, NO, INDETERMINATE / HUMAN REVIEW REQUIRED
- explicit out-of-scope handling

## Where Final Response Contract Is Built
The frontend-facing response is still `AnalysisReport` from `backend/app/models/report.py`.

There are two report-building layers:
- `AnalysisReportBuilder` builds the base report from `AccountingProcess` and `RiskInferenceResult`.
- `ReportAgent.build_final_report` enriches the base `AnalysisReport` with reviewed multi-agent findings, recomputes summary counts, deduplicates findings/evidence/questions, and preserves the existing endpoint contract.

Current gap against mentor target:
- the response does not yet expose a simple top-level conclusion of YES / NO / INDETERMINATE
- top findings are not capped at 3 to 5
- missing items are represented as findings/documentary gaps, but not yet a first-class response section
- normative rationale and recommended action are not yet first-class fields

Migration point for A4:
- add a scoped final answer schema beside or inside `AnalysisReport`, while preserving backward-compatible detailed fields for the current frontend.

## Where Retrieval Scope Can Be Restricted
Retrieval is currently configured in `backend/app/api/analysis.py` and executed by `KnowledgeRetrievalService`.

Restriction seams already exist:
- `retrieve_for_query` accepts `metadata_filter`
- `retrieve_for_process` forwards `metadata_filter`
- `preferred_document_scope` and `preferred_regime_applicability` can adjust ranking
- knowledge metadata includes `document_family`, `document_scope`, `authority_level`, and `regime_applicability`

Current behavior:
- curated knowledge is indexed via `default_knowledge_documents()`
- general queries penalize DeRE and regime-specific scope, but this is not the same as mentor-approved filtering
- no explicit whitelist exists for NBC TG / CPC 00 (R2) and LC 214/2025
- no policy object controls approved normative families

Migration point for A5:
- introduce a scoped retrieval policy that passes `metadata_filter` / ranking preferences based on the approved mentor scope
- add tests proving unrelated knowledge families are excluded or deprioritized
- keep support-missing cases explicit when approved-scope retrieval returns no useful support

## Where Deterministic Checks Can Be Inserted
Some deterministic checks already exist:
- `RedFlagAgent` detects impossible dates, conflicting values, missing procurement artifacts, informal approval, payment before invoice, personal/third-party account wording, informal payment instructions, and urgency override without support.
- `AccountingAuditAgent` detects documentary gaps, control gaps, traceability gaps, reconciliation gaps, cost center inconsistency, approval weakness, and posting inconsistency.
- `ReviewerAgent` deduplicates and normalizes severity/confidence/review flags.

Current gaps:
- deterministic checks are embedded inside agent classes rather than isolated as reusable rule modules
- checks do not yet map to the mentor’s single central question
- checks are not yet explicitly fed into a final YES / NO / INDETERMINATE conclusion

Migration point for A3:
- extract deterministic checks into a dedicated rules package or service
- keep rule outputs evidence-backed and feed them into the reviewer/report layer
- add a small labeled test matrix for objective cases

## Current Testing and Evaluation Hooks
Existing hooks:
- unit tests for each agent: document understanding, red flag, accounting/audit, reviewer, report
- security hardening tests for malformed agent outputs, config literals, and safe failure envelopes
- integration tests for `/analysis/documents/{document_id}`
- regression tests for insurance broker memo, fictitious internal AP memo, prompt-injection-like content, and agent enrichment failure

Current limitations:
- tests are scenario-specific, not yet a labeled evaluation dataset
- no metrics exist for precision, recall, false positive rate, false negative rate, or conclusion agreement
- expected outputs do not yet include the mentor conclusion values

Migration point for A6:
- create a fictional labeled dataset with expected conclusion, top findings, missing items, evidence anchors, and ambiguity notes
- add a lightweight evaluation test that computes agreement against expected labels

## Recommended Next-Step Map
1. A1: Add explicit scope models/config for document category, normative family, and allowed conclusion values.
2. A2: Add a bounded answer contract centered on the mentor question.
3. A3: Extract deterministic checks from agent classes into reusable evidence-backed rule modules.
4. A4: Add a simplified final response section while keeping existing `AnalysisReport` fields for compatibility.
5. A5: Add retrieval policy filters for approved normative sources and tests for unrelated-source exclusion.
6. A6: Add fictional labeled evaluation fixtures and regression metrics.

## A0 Decision
No runtime refactor is required for this phase. The current implementation has enough seams for the mentor changes, but scope, final answer format, retrieval policy, and evaluation labels need to be made explicit in follow-up phases.
