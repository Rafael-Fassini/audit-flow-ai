from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.models.accounting_process import AccountingProcess
from app.models.report import AnalysisReport
from app.models.risk import RiskInferenceResult
from app.services.reporting.analysis_report_builder import AnalysisReportBuilder
from app.services.scoring.finding_scorer import FindingScorer

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisAssemblyRequest(BaseModel):
    process: AccountingProcess
    risk_result: RiskInferenceResult
    analysis_id: str | None = None


async def get_analysis_report_builder() -> AnalysisReportBuilder:
    return AnalysisReportBuilder(scorer=FindingScorer())


@router.post(
    "/reports",
    response_model=AnalysisReport,
    status_code=status.HTTP_201_CREATED,
)
async def build_analysis_report(
    request: AnalysisAssemblyRequest,
    report_builder: AnalysisReportBuilder = Depends(get_analysis_report_builder),
) -> AnalysisReport:
    return report_builder.build(
        process=request.process,
        risk_result=request.risk_result,
        analysis_id=request.analysis_id,
    )
