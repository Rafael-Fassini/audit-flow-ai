import { useEffect, useMemo, useState } from "react";

import { analyzeDocument, checkHealth, uploadDocument } from "./api/client";
import type {
  AnalysisReport,
  DocumentUploadResponse,
  FinalResponse,
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
  const finalResponse = currentReport ? getFinalResponse(currentReport) : null;

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
      setDocuments((current) => [
        document,
        ...current.filter((item) => item.id !== document.id),
      ]);
      setSelectedDocumentId(document.id);
      setSelectedFile(null);
      setMessage(`Documento enviado: ${document.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Falha no envio.");
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
      setMessage(`Análise concluída para ${document.filename}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Falha na análise.");
    } finally {
      setRequestState("idle");
    }
  }

  const isUploading = requestState === "uploading";
  const isAnalyzing = requestState === "analyzing";

  return (
    <SinglePageLayout>
      <Header apiHealthy={apiHealthy} />

      {message ? <div className="message success">{message}</div> : null}
      {errorMessage ? <div className="message error">{errorMessage}</div> : null}

      <UploadSection
        isUploading={isUploading}
        onFileChange={setSelectedFile}
        onUpload={() => void handleUpload()}
        selectedFile={selectedFile}
      />

      <DocumentsSection
        documents={documents}
        isAnalyzing={isAnalyzing}
        onAnalyze={(document) => void handleAnalyze(document)}
        onSelect={setSelectedDocumentId}
        selectedDocumentId={selectedDocumentId}
      />

      <AnalysisResultCard
        document={selectedDocument}
        finalResponse={finalResponse}
        report={currentReport}
      />
    </SinglePageLayout>
  );
}

function SinglePageLayout({ children }: { children: React.ReactNode }) {
  return <main className="single-page-layout">{children}</main>;
}

function Header({ apiHealthy }: { apiHealthy: boolean | null }) {
  return (
    <header className="app-header">
      <div>
        <p className="product-name">AuditFlow</p>
        <h1>Revisão documental com escopo definido</h1>
        <p className="header-copy">
          Uma verificação focada em inconsistências de documentação, aprovação,
          valores, classificação e aderência normativa no escopo definido.
        </p>
      </div>
      <div className="api-status">
        <span className={apiHealthy ? "status-dot ok" : "status-dot"} />
        {apiHealthy === null
          ? "Verificando backend"
          : apiHealthy
            ? "Backend online"
            : "Backend indisponível"}
      </div>
    </header>
  );
}

function UploadSection({
  isUploading,
  onFileChange,
  onUpload,
  selectedFile,
}: {
  isUploading: boolean;
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
  selectedFile: File | null;
}) {
  return (
    <section className="panel upload-section" aria-labelledby="upload-title">
      <div>
        <p className="eyebrow">1. Envio</p>
        <h2 id="upload-title">Adicione um documento de suporte</h2>
        <p className="muted">PDF, DOCX ou TXT. O arquivo é armazenado antes da análise.</p>
      </div>
      <label className="file-input">
        <input
          accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
          type="file"
        />
        <span>{selectedFile ? selectedFile.name : "Escolher arquivo"}</span>
      </label>
      <button
        className="primary-button"
        disabled={!selectedFile || isUploading}
        onClick={onUpload}
        type="button"
      >
        {isUploading ? "Enviando..." : "Enviar"}
      </button>
    </section>
  );
}

function DocumentsSection({
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
  return (
    <section className="panel" aria-labelledby="documents-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">2. Documentos</p>
          <h2 id="documents-title">Enviados neste navegador</h2>
        </div>
        <span className="quiet-note">Lista da sessão</span>
      </div>

      {documents.length ? (
        <div className="documents-list">
          {documents.map((document) => (
            <article
              className={
                document.id === selectedDocumentId
                  ? "document-item active"
                  : "document-item"
              }
              key={document.id}
            >
              <button
                className="document-main"
                onClick={() => onSelect(document.id)}
                type="button"
              >
                <strong>{document.filename}</strong>
                <span>{formatBytes(document.size_bytes)} · {document.status}</span>
              </button>
              <button
                className="secondary-button"
                disabled={isAnalyzing}
                onClick={() => onAnalyze(document)}
                type="button"
              >
                {isAnalyzing && document.id === selectedDocumentId
                  ? "Analisando..."
                  : "Analisar"}
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-text">Envie um documento para começar.</p>
      )}
    </section>
  );
}

function AnalysisResultCard({
  document,
  finalResponse,
  report,
}: {
  document: DocumentUploadResponse | null;
  finalResponse: FinalResponse | null;
  report: AnalysisReport | null;
}) {
  if (!report || !finalResponse) {
    return (
      <section className="panel result-empty" aria-labelledby="result-title">
        <p className="eyebrow">3. Resultado</p>
        <h2 id="result-title">Execute uma análise para ver a conclusão</h2>
        <p className="muted">
          O resultado ficará nesta página e priorizará a resposta pronta para decisão.
        </p>
      </section>
    );
  }

  const documentaryFindings = report.findings.filter(
    (finding) => finding.category === "documentary_gap",
  );
  const evidence = collectEvidence(report);

  return (
    <section className="result-stack" aria-labelledby="result-title">
      <div className="panel result-header">
        <div>
          <p className="eyebrow">3. Resultado</p>
          <h2 id="result-title">{document?.filename ?? report.summary.source_filename}</h2>
          <p className="muted">
            {report.summary.total_findings} achado{report.summary.total_findings === 1 ? "" : "s"} ·{" "}
            revisão necessária: {report.summary.review_required_count}
          </p>
        </div>
        <ConclusionBadge conclusion={finalResponse.conclusion} />
      </div>

      <FindingsList findings={finalResponse.top_findings} />
      <MissingItemsList
        documentaryFindings={documentaryFindings}
        missingItems={finalResponse.missing_items}
      />

      <div className="two-card-grid">
        <NormativeRationaleCard rationale={finalResponse.normative_rationale} />
        <RecommendedActionCard action={finalResponse.recommended_action} />
      </div>

      <OptionalDetailsAccordion evidence={evidence} report={report} />
    </section>
  );
}

function ConclusionBadge({ conclusion }: { conclusion: string }) {
  const tone = conclusionTone(conclusion);
  return (
    <div className={`conclusion-badge ${tone}`}>
      <span>Conclusão</span>
      <strong>{normalizeConclusion(conclusion)}</strong>
    </div>
  );
}

function FindingsList({ findings }: { findings: FinalResponse["top_findings"] }) {
  return (
    <section className="panel" aria-labelledby="findings-title">
      <p className="eyebrow">Principais achados</p>
      <h2 id="findings-title">Pontos mais relevantes</h2>
      {findings.length ? (
        <div className="finding-list">
          {findings.map((finding) => (
            <article className="finding-row" key={`${finding.title}-${finding.evidence}`}>
              <div className="finding-row-header">
                <h3>{finding.title}</h3>
                <span className={`severity ${finding.severity}`}>
                  {formatLabel(finding.severity)}
                </span>
              </div>
              <p>{finding.evidence}</p>
              <span className="category-pill">{formatLabel(finding.category)}</span>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-text">Nenhum problema com evidência foi retornado.</p>
      )}
    </section>
  );
}

function MissingItemsList({
  documentaryFindings,
  missingItems,
}: {
  documentaryFindings: ReportFinding[];
  missingItems: string[];
}) {
  const items = mergeMissingItems(missingItems, documentaryFindings);

  return (
    <section className="panel" aria-labelledby="missing-title">
      <p className="eyebrow">Itens ausentes</p>
      <h2 id="missing-title">Lacunas documentais</h2>
      {items.length ? (
        <ul className="missing-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">Nenhum item ausente foi destacado.</p>
      )}
    </section>
  );
}

function NormativeRationaleCard({ rationale }: { rationale: string }) {
  return (
    <section className="panel compact-panel" aria-labelledby="rationale-title">
      <p className="eyebrow">Justificativa normativa</p>
      <h2 id="rationale-title">Por que isso importa</h2>
      <p>{rationale}</p>
    </section>
  );
}

function RecommendedActionCard({ action }: { action: string }) {
  return (
    <section className="panel compact-panel" aria-labelledby="action-title">
      <p className="eyebrow">Ação recomendada</p>
      <h2 id="action-title">Próximo passo</h2>
      <p>{action}</p>
    </section>
  );
}

function OptionalDetailsAccordion({
  evidence,
  report,
}: {
  evidence: FindingEvidence[];
  report: AnalysisReport;
}) {
  return (
    <details className="panel optional-details">
      <summary>Detalhes opcionais</summary>
      <div className="details-grid">
        <div>
          <h3>Evidências</h3>
          {evidence.length ? (
            <ul className="detail-list">
              {evidence.map((item, index) => (
                <li key={`${item.source}-${item.text}-${index}`}>
                  <strong>{formatLabel(item.source)}</strong>
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-text">Nenhum trecho de evidência foi retornado.</p>
          )}
        </div>
        <div>
          <h3>Perguntas complementares</h3>
          {report.follow_up_questions.length ? (
            <ul className="detail-list">
              {report.follow_up_questions.slice(0, 5).map((question) => (
                <li key={question.id}>{question.question}</li>
              ))}
            </ul>
          ) : (
            <p className="empty-text">Nenhuma pergunta complementar foi retornada.</p>
          )}
          <div className="metadata-box">
            <span>ID da análise</span>
            <strong>{report.analysis_id}</strong>
            <span>Gerado em</span>
            <strong>{new Date(report.generated_at).toLocaleString()}</strong>
          </div>
        </div>
      </div>
    </details>
  );
}

function getFinalResponse(report: AnalysisReport): FinalResponse {
  if (report.final_response) {
    return report.final_response;
  }

  const topFindings = report.scoped_answer?.top_findings.map((finding) => ({
    title: finding.title,
    category: finding.category,
    severity:
      report.findings.find((item) => item.id === finding.finding_id)?.score.severity ??
      "medium",
    evidence: finding.evidence_text,
  })) ?? [];

  return {
    conclusion: report.scoped_answer?.conclusion ?? "INDETERMINATE / HUMAN REVIEW REQUIRED",
    top_findings: topFindings,
    missing_items: report.findings
      .filter((finding) => finding.category === "documentary_gap")
      .slice(0, 5)
      .map((finding) => finding.title),
    normative_rationale:
      report.scoped_answer?.rationale ??
      "O backend não retornou uma justificativa normativa curta.",
    recommended_action:
      report.follow_up_questions[0]?.question ??
      "Revise o resultado e solicite o suporte ausente, se necessário.",
  };
}

function collectEvidence(report: AnalysisReport): FindingEvidence[] {
  const evidence = [
    ...report.evidence,
    ...report.findings.flatMap((finding) => finding.evidence),
  ];
  const seen = new Set<string>();
  return evidence
    .filter((item) => {
      const key = `${item.source}:${item.text}:${item.knowledge_chunk_id ?? ""}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 8);
}

function mergeMissingItems(
  missingItems: string[],
  documentaryFindings: ReportFinding[],
) {
  const values = [
    ...missingItems,
    ...documentaryFindings.map((finding) => finding.title),
  ];
  const seen = new Set<string>();
  return values.filter((item) => {
    const key = item.trim().toLowerCase();
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 5);
}

function normalizeConclusion(conclusion: string) {
  const normalized = conclusion.trim().toUpperCase();
  if (normalized === "YES") {
    return "SIM";
  }
  if (normalized === "NO") {
    return "NÃO";
  }
  return "INDETERMINADO / REVISÃO HUMANA NECESSÁRIA";
}

function conclusionTone(conclusion: string) {
  const normalized = conclusion.trim().toUpperCase();
  if (normalized === "YES") {
    return "attention";
  }
  if (normalized === "NO") {
    return "clear";
  }
  return "review";
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatBytes(value: number) {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
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
