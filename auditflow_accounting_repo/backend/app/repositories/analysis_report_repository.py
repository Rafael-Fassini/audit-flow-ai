import json
from pathlib import Path

from app.models.report import AnalysisReport


class AnalysisReportRepository:
    def save(self, document_id: str, report: AnalysisReport) -> AnalysisReport:
        raise NotImplementedError

    def get(self, analysis_id: str) -> AnalysisReport | None:
        raise NotImplementedError


class JsonAnalysisReportRepository(AnalysisReportRepository):
    def __init__(self, report_path: Path) -> None:
        self._report_path = report_path

    def save(self, document_id: str, report: AnalysisReport) -> AnalysisReport:
        records = self._load_records()
        records[report.analysis_id] = {
            "document_id": document_id,
            "report": report.model_dump(mode="json"),
        }
        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        self._report_path.write_text(
            json.dumps(records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report

    def get(self, analysis_id: str) -> AnalysisReport | None:
        record = self._load_records().get(analysis_id)
        if not isinstance(record, dict):
            return None
        report = record.get("report")
        if not isinstance(report, dict):
            return None
        return AnalysisReport.model_validate(report)

    def _load_records(self) -> dict[str, dict[str, object]]:
        if not self._report_path.exists():
            return {}

        content = self._report_path.read_text(encoding="utf-8").strip()
        if not content:
            return {}

        records = json.loads(content)
        if not isinstance(records, dict):
            return {}
        return records
