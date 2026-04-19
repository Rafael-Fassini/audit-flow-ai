# Architecture

## 1. Objective
Define the technical architecture for the AuditFlow AI MVP focused on the **accounting entry process** and the **chart of accounts**.

## 2. Architectural style
The system uses a **modular orchestrated backend pipeline**.

It is intentionally **not**:
- a single prompt wrapped in an API
- a generic chat-with-PDF app
- an autonomous agent as the product core

The backend orchestrates specialized stages with validated schemas and explicit data flow.

## 3. High-level components

### 3.1 API Layer
FastAPI endpoints responsible for:
- upload ingestion
- triggering analysis
- retrieving analysis results
- health/status endpoints

### 3.2 Orchestration Layer
Coordinates the main analysis pipeline and ensures the stages are executed in order.

### 3.3 Document Intelligence Layer
Responsible for:
- file reception
- text extraction
- normalization
- section segmentation
- chunk preparation

### 3.4 Process Structuring Layer
Transforms raw text into a structured accounting-process representation, including:
- process name
- process steps
- actors
- systems
- controls mentioned
- chart of accounts references
- accounts cited
- posting logic described
- gaps in narrative

### 3.5 Knowledge Retrieval Layer
Queries the knowledge base for contextual information relevant to:
- accounting posting logic
- chart of accounts usage
- policies and procedures
- internal control cues
- accounting inconsistency patterns

### 3.6 Inconsistency and Risk Engine
Combines:
- heuristic rules
- structured process data
- retrieved context
- LLM inference

to produce:
- accounting inconsistencies
- risks
- gaps
- follow-up questions
- evidence references

### 3.7 Scoring Layer
Assigns:
- severity
- confidence
- review-required flags

### 3.8 Reporting Layer
Builds the final structured output payload to support downstream visualization/export.

## 4. End-to-end flow
1. Client uploads a document.
2. API stores metadata and forwards the file to ingestion.
3. Parsing extracts normalized text.
4. Chunking organizes the document into meaningful sections.
5. Extraction generates a structured accounting-process model.
6. Retrieval queries the knowledge base.
7. Risk engine evaluates inconsistencies and risks.
8. Scoring assigns severity/confidence.
9. Reporting serializes the final result.
10. API returns the analysis payload.

## 5. Domain-centered entities
Core domain concepts expected in the backend:
- Document
- DocumentSection
- AccountingProcess
- ProcessStep
- ChartOfAccounts
- AccountReference
- AccountingEntryPattern
- ControlSignal
- EvidenceSnippet
- Inconsistency
- RiskItem
- FollowUpQuestion
- AnalysisResult

## 6. Persistence strategy

### PostgreSQL
Use PostgreSQL for structured data:
- document metadata
- extracted text references
- process structures
- results metadata
- scores and statuses

### Qdrant
Use Qdrant for knowledge-base embeddings and semantic retrieval.

## 7. AI strategy
The MVP uses an **LLM-backed workflow**, not a single free-form completion.

Recommended stages:
- structured process extraction
- retrieval-grounded enrichment
- hybrid inconsistency/risk inference
- structured final reporting

The LLM must return schema-constrained outputs.

## 8. Heuristic layer
Heuristics should complement the model. Examples:
- generic or catch-all account referenced without clear rationale
- narrative suggests one event type but account class suggests another
- missing approval/control description around posting
- repeated use of transitional accounts without closure logic
- missing linkage between policy and described posting practice

## 9. Why this architecture
This design is appropriate because it:
- supports traceability
- keeps the pipeline testable
- separates concerns clearly
- makes the product more credible than a prompt wrapper
- is realistic for a hackathon with a small team

## 10. Out of scope for MVP
- authentication/authorization
- multi-tenant support
- agentic autonomy
- model fine-tuning
- advanced multimodal ingestion
- full accounting reconciliation engine
- frontend implementation
