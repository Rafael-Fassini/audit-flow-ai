from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExpectedEvaluationLabels:
    conclusion: str
    required_categories: frozenset[str] = frozenset()
    forbidden_categories: frozenset[str] = frozenset()
    required_missing_item_terms: tuple[str, ...] = ()
    required_evidence_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class FictionalEvaluationCase:
    case_id: str
    filename: str
    document_text: str
    expected: ExpectedEvaluationLabels


FICTIONAL_EVALUATION_DATASET: tuple[FictionalEvaluationCase, ...] = (
    FictionalEvaluationCase(
        case_id="clean_case",
        filename="eval_clean_payment_memo.txt",
        document_text=(
            "Clean Payment Support Memo\n\n"
            "The invoice, purchase order, contract, and accounting support were attached. "
            "The invoice was received on 2026-03-01. "
            "Payment was made on 2026-03-10. "
            "Formal manager approval was documented before payment. "
            "The posting was reviewed and reconciled. "
            "The chart of accounts support identifies debit 5100 expense "
            "and credit 2100 accounts payable. "
            "The cost center matches the IT services allocation."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="NO",
            forbidden_categories=frozenset(
                {
                    "documentary_gap",
                    "control_gap",
                    "approval_weakness",
                    "cost_center_inconsistency",
                    "posting_inconsistency",
                    "conflicting_values",
                }
            ),
        ),
    ),
    FictionalEvaluationCase(
        case_id="documentary_inconsistency",
        filename="eval_documentary_gap_memo.txt",
        document_text=(
            "Accounts Payable Support Memo\n\n"
            "The invoice was received on 2026-03-01 and payment was made on 2026-03-10. "
            "No purchase order or contract was provided for the procurement. "
            "The accounting rationale is not documented and supporting evidence is missing. "
            "Formal approval was documented before payment."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="YES",
            required_categories=frozenset({"documentary_gap"}),
            required_missing_item_terms=("procurement",),
            required_evidence_terms=("No purchase order or contract",),
        ),
    ),
    FictionalEvaluationCase(
        case_id="value_inconsistency",
        filename="eval_value_conflict_memo.txt",
        document_text=(
            "Payment Value Memo\n\n"
            "The invoice, contract, and purchase order were attached. "
            "Invoice amount is R$ 1.000,00 but payment amount is R$ 1.500,00. "
            "Formal approval was documented before payment and the posting was reviewed."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="YES",
            required_categories=frozenset({"posting_inconsistency"}),
            required_evidence_terms=("R$ 1.000,00", "R$ 1.500,00"),
        ),
    ),
    FictionalEvaluationCase(
        case_id="approval_inconsistency",
        filename="eval_approval_gap_memo.txt",
        document_text=(
            "Approval Exception Memo\n\n"
            "The invoice, purchase order, and contract were attached. "
            "Approval was informal via WhatsApp after payment. "
            "The payment was made to the registered supplier account after invoice receipt."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="YES",
            required_categories=frozenset({"approval_weakness"}),
            required_evidence_terms=("Approval was informal via WhatsApp",),
        ),
    ),
    FictionalEvaluationCase(
        case_id="classification_inconsistency",
        filename="eval_classification_gap_memo.txt",
        document_text=(
            "Accounting Classification Memo\n\n"
            "The invoice, purchase order, and contract were attached. "
            "Posting to account 4.1.01 - supplier expenses is inconsistent with the freight narrative. "
            "Cost center CC-200 Sales does not match the IT services allocation. "
            "Formal approval was documented before payment."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="YES",
            required_categories=frozenset(
                {"posting_inconsistency", "cost_center_inconsistency"}
            ),
            required_evidence_terms=("4.1.01 - supplier expenses", "CC-200 Sales"),
        ),
    ),
    FictionalEvaluationCase(
        case_id="multi_red_flag_case",
        filename="eval_multi_red_flag_memo.txt",
        document_text=(
            "Emergency Payment Red Flag Memo\n\n"
            "Invoice date is 2026-02-30. "
            "Payment date was 2026-03-01. Invoice date was 2026-03-15. "
            "Invoice amount is R$ 2.000,00 but payment amount is R$ 2.750,00. "
            "No purchase order or contract was provided for the procurement. "
            "Payment instructions with PIX key were sent by WhatsApp message. "
            "Payment was transferred to a personal account not registered to the supplier. "
            "Urgent override was requested without support or evidence."
        ),
        expected=ExpectedEvaluationLabels(
            conclusion="YES",
            required_categories=frozenset(
                {
                    "documentary_gap",
                    "posting_inconsistency",
                    "approval_weakness",
                    "payment_control_weakness",
                    "control_gap",
                }
            ),
            required_missing_item_terms=("procurement", "support"),
            required_evidence_terms=("2026-02-30", "PIX key", "personal account"),
        ),
    ),
)
