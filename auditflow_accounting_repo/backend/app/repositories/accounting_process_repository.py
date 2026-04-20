import json
from pathlib import Path

from app.models.accounting_process import AccountingProcess


class AccountingProcessRepository:
    def save(self, process_id: str, process: AccountingProcess) -> AccountingProcess:
        raise NotImplementedError

    def get(self, process_id: str) -> AccountingProcess | None:
        raise NotImplementedError


class JsonAccountingProcessRepository(AccountingProcessRepository):
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path

    def save(self, process_id: str, process: AccountingProcess) -> AccountingProcess:
        records = self._load_records()
        records[process_id] = process.model_dump(mode="json")
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(
            json.dumps(records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return process

    def get(self, process_id: str) -> AccountingProcess | None:
        record = self._load_records().get(process_id)
        if record is None:
            return None
        return AccountingProcess.model_validate(record)

    def _load_records(self) -> dict[str, dict[str, object]]:
        if not self._storage_path.exists():
            return {}

        content = self._storage_path.read_text(encoding="utf-8").strip()
        if not content:
            return {}

        records = json.loads(content)
        if not isinstance(records, dict):
            return {}
        return records
