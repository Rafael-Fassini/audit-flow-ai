import type { AnalysisReport, ApiError, DocumentUploadResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export async function checkHealth(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return response.ok;
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/documents/`, {
    method: "POST",
    headers: {
      "X-Request-ID": `ui-upload-${crypto.randomUUID()}`,
    },
    body: formData,
  });

  return parseResponse<DocumentUploadResponse>(response);
}

export async function analyzeDocument(documentId: string): Promise<AnalysisReport> {
  const response = await fetch(`${API_BASE_URL}/analysis/documents/${documentId}`, {
    method: "POST",
    headers: {
      "X-Request-ID": `ui-analysis-${crypto.randomUUID()}`,
    },
  });

  return parseResponse<AnalysisReport>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const apiError = payload as ApiError | null;
    const message =
      apiError?.error?.message ??
      (typeof apiError?.detail === "string" ? apiError.detail : null) ??
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}
