import { useEffect, useMemo, useState } from "react";

import { analyzeDocument, checkHealth, uploadDocument } from "./api/client";
import type {
  AnalysisReport,
  DocumentUploadResponse,
  FindingEvidence,
  ReportFinding,
} from "./api/types";

const DOCUMENTS_STORAGE_KEY = "auditflow.sessionDocuments";
const REPORTS_STORAGE_KEY = "auditflow.analysisReports";

type RequestState = "idle" | "uploading" | "analyzing";

export default function App() {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [documents, setDocuments] = useState<DocumentUploadResponse[]>(() =>
    readStorage<DocumentUploadResponse[]>(DOCUMENTS_STORAGE_KEY, []),
  );
  const [reports, setReports] = useState<Record<string, AnalysisReport>>(() =>
    readStorage<Record<string, AnalysisReport>>(REPORTS_STORAGE_KEY, {}),
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    documents[0]?.id ?? null,
  );
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );
  const currentReport = selectedDocumentId ? reports[selectedDocumentId] ?? null : null;

  const mainFindings = currentReport
    ? currentReport.findings.filter((finding) => finding.category !== "documentary_gap")
    : [];
  const documentaryFindings = currentReport
    ? currentReport.findings.filter((finding) => finding.category === "documentary_gap")
    : [];
  const evidenceItems = currentReport ? collectEvidence(currentReport) : [];

  useEffect(() => {
    checkHealth().then(setApiHealthy).catch(() => setApiHealthy(false));
  }, []);

  useEffect(() => {
    writeStorage(DOCUMENTS_STORAGE_KEY, documents);
  }, [documents]);

  useEffect(() => {
    writeStorage(REPORTS_STORAGE_KEY, reports);
  }, [reports]);

  async function handleUpload() {
    if (!selectedFile) {
      return;
    }

    setRequestState("uploading");
    setErrorMessage(null);
    setMessage(null);

    try {
      const document = await uploadDocument(selectedFile);
      setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
      setSelectedDocumentId(document.id);
      setSelectedFile(null);
      setMessage(`Document uploaded: ${document.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setRequestState("idle");
    }
  }

  async function handleAnalyze(document: DocumentUploadResponse) {
    setRequestState("analyzing");
    setErrorMessage(null);
    setMessage(null);
    setSelectedDocumentId(document.id);

    try {
      const report = await analyzeDocument(document.id);
      setReports((current) => ({ ...current, [document.id]: report }));
      setMessage(`Analysis completed for ${document.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Analysis failed.");
    } finally {
      setRequestState("idle");
    }
  }

  const isUploading = requestState === "uploading";
  const isAnalyzing = requestState === "analyzing";

  return (
    <main className="page-shell">
      <Header apiHealthy={apiHealthy} />

      {message ? <div className="message success">{message}</div> : null}
      {errorMessage ? <div className="message error">{errorMessage}</div> : null}

      <section className="card upload-card" aria-labelledby="upload-title">
        <div>
          <p className="eyebrow">Upload Document</p>
          <h2 id="upload-title">Select a PDF, DOCX, or TXT file</h2>
          <p className="muted">The backend stores the document before analysis is triggered.</p>
        </div>
        <label className="file-input">
          <input
            accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            type="file"
          />
          <span>{selectedFile ? selectedFile.name : "Choose file"}</span>
        </label>
        <button
          className="primary-button"
          disabled={!selectedFile || isUploading}
          onClick={() => void handleUpload()}
          type="button"
        >
          {isUploading ? "Uploading..." : "Upload"}
        </button>
      </section>

      <section className="card" aria-labelledby="documents-title">
        <div className="section-title">
          <div>
            <p className="eyebrow">Documents</p>
            <h2 id="documents-title">Uploaded in this browser</h2>
          </div>
          <span className="note">No backend list endpoint exists yet.</span>
        </div>
        <DocumentsTable
          documents={documents}
          isAnalyzing={isAnalyzing}
          onAnalyze={(document) => void handleAnalyze(document)}
          onSelect={setSelectedDocumentId}
          selectedDocumentId={selectedDocumentId}
        />
      </section>

      <AnalysisSummary report={currentReport} selectedDocument={selectedDocument} />

      <section className="card" aria-labelledby="overview-title">
        <p className="eyebrow">Overview</p>
        <h2 id="overview-title">Process summary</h2>
        <p className="body-text">
          {currentReport?.process.summary ??
            "Run an analysis to see the backend-generated process summary."}
        </p>
      </section>

      <FindingsSection findings={mainFindings} />
      <MissingItemsSection findings={documentaryFindings} report={currentReport} />
      <FollowUpSection report={currentReport} />
      <EvidenceSection evidence={evidenceItems} />
      <ProcessStepsSection report={currentReport} />
    </main>
  );
}

function Header({ apiHealthy }: { apiHealthy: boolean | null }) {
  return (
    <header className="app-header">
      <div className="header-title">
        <img
          src="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=128&q=80"
          alt=""
        />
        <div>
          <p className="product-name">AuditFlow</p>
          <h1>Document Analysis</h1>
        </div>
      </div>
      <div className="api-status">
        <span className={apiHealthy ? "status-dot ok" : "status-dot"} />
        {apiHealthy === null ? "Checking backend" : apiHealthy ? "Backend online" : "Backend unavailable"}
      </div>
    </header>
  );
}

function DocumentsTable({
  documents,
  selectedDocumentId,
  isAnalyzing,
  onAnalyze,
  onSelect,
}: {
  documents: DocumentUploadResponse[];
  selectedDocumentId: string | null;
  isAnalyzing: boolean;
  onAnalyze: (document: DocumentUploadResponse) => void;
  onSelect: (documentId: string) => void;
}) {
  if (!documents.length) {
    return <p className="empty-text">No documents uploaded in this browser session.</p>;
  }

  return (
    <div className="documents-list">
      {documents.map((document) => (
        <article
          className={document.id === selectedDocumentId ? "document-item active" : "document-item"}
          key={document.id}
        >
          <button className="document-main" onClick={() => onSelect(document.id)} type="button">
            <strong>{document.filename}</strong>
            <span>{document.id}</span>
          </button>
          <span className="status-badge">{document.status}</span>
          <button
            className="secondary-button"
            disabled={isAnalyzing}
            onClick={() => onAnalyze(document)}
            type="button"
          >
            {isAnalyzing && document.id === selectedDocumentId ? "Analyzing..." : "Analyze"}
          </button>
        </article>
      ))}
    </div>
  );
}

function AnalysisSummary({
  report,
  selectedDocument,
}: {
  report: AnalysisReport | null;
  selectedDocument: DocumentUploadResponse | null;
}) {
  return (
    <section className="card summary-card" aria-labelledby="summary-title">
      <div>
        <p className="eyebrow">Analysis Summary</p>
        <h2 id="summary-title">{report?.summary.process_name ?? "No analysis yet"}</h2>
        <p className="muted">{report?.summary.source_filename ?? selectedDocument?.filename ?? "Select a document."}</p>
      </div>
      <div className="summary-meta">
        <Metric label="Status" value={report?.status ?? "not started"} />
        <Metric label="Analysis ID" value={report?.analysis_id ?? "-"} />
        <Metric label="Total findings" value={String(report?.summary.total_findings ?? 0)} />
        <Metric label="Review required" value={String(report?.summary.review_required_count ?? 0)} />
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FindingsSection({ findings }: { findings: ReportFinding[] }) {
  return (
    <section className="card" aria-labelledby="findings-title">
      <p className="eyebrow">Findings</p>
      <h2 id="findings-title">Operational and control findings</h2>
      {findings.length ? (
        <div className="findings-grid">
          {findings.map((finding) => (
            <article className="finding-card" key={finding.id}>
              <div className="finding-tags">
                <span className={`severity ${finding.score.severity}`}>{finding.score.severity}</span>
                <span>{formatLabel(finding.category)}</span>
              </div>
              <h3>{finding.title}</h3>
              <p>{finding.description}</p>
              <div className="confidence">
                Confidence: {Math.round(finding.score.confidence * 100)}%
              </div>
              <EvidencePreview evidence={finding.evidence[0]} />
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-text">No operational findings returned yet.</p>
      )}
    </section>
  );
}

function MissingItemsSection({
  findings,
  report,
}: {
  findings: ReportFinding[];
  report: AnalysisReport | null;
}) {
  const gapDescriptions = report?.process.narrative_gaps
    .filter((gap) => /not identified|not found|não foi identificada|nao foi identificada/i.test(gap.description))
    .map((gap) => gap.description) ?? [];

  return (
    <section className="card" aria-labelledby="missing-title">
      <p className="eyebrow">Missing Items</p>
      <h2 id="missing-title">Documentary gaps</h2>
      {findings.length || gapDescriptions.length ? (
        <ul className="simple-list">
          {findings.map((finding) => (
            <li key={finding.id}>
              <strong>{finding.title}</strong>
              <span>{finding.description}</span>
            </li>
          ))}
          {gapDescriptions.map((description) => (
            <li key={description}>
              <strong>Missing document detail</strong>
              <span>{description}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">No documentary gaps returned yet.</p>
      )}
    </section>
  );
}

function FollowUpSection({ report }: { report: AnalysisReport | null }) {
  return (
    <section className="card" aria-labelledby="questions-title">
      <p className="eyebrow">Follow-up Questions</p>
      <h2 id="questions-title">Suggested audit questions</h2>
      {report?.follow_up_questions.length ? (
        <ul className="question-list">
          {report.follow_up_questions.map((question) => (
            <li key={question.id}>{question.question}</li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">No follow-up questions returned yet.</p>
      )}
    </section>
  );
}

function EvidenceSection({ evidence }: { evidence: FindingEvidence[] }) {
  return (
    <section className="card" aria-labelledby="evidence-title">
      <p className="eyebrow">Evidence</p>
      <h2 id="evidence-title">Referenced excerpts</h2>
      {evidence.length ? (
        <ul className="evidence-list">
          {evidence.map((item, index) => (
            <li key={`${item.source}-${item.text}-${index}`}>
              <strong>{formatLabel(item.source)}</strong>
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">No evidence excerpts returned yet.</p>
      )}
    </section>
  );
}

function ProcessStepsSection({ report }: { report: AnalysisReport | null }) {
  return (
    <section className="card" aria-labelledby="steps-title">
      <p className="eyebrow">Process Steps</p>
      <h2 id="steps-title">Extracted operational flow</h2>
      {report?.process.steps.length ? (
        <ol className="steps-list">
          {report.process.steps.map((step) => (
            <li key={`${step.index}-${step.description}`}>
              <strong>{formatLabel(step.step_type)}</strong>
              <span>{step.description}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-text">No process steps returned yet.</p>
      )}
    </section>
  );
}

function EvidencePreview({ evidence }: { evidence?: FindingEvidence }) {
  if (!evidence) {
    return <p className="evidence-preview">No evidence attached.</p>;
  }

  return (
    <p className="evidence-preview">
      <strong>Evidence:</strong> {evidence.text}
    </p>
  );
}

function collectEvidence(report: AnalysisReport): FindingEvidence[] {
  const evidence = [
    ...report.evidence,
    ...report.findings.flatMap((finding) => finding.evidence),
  ];
  const seen = new Set<string>();
  return evidence.filter((item) => {
    const key = `${item.source}:${item.text}:${item.knowledge_chunk_id ?? ""}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 10);
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function readStorage<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}
