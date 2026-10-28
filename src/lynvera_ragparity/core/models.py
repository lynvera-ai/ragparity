"""Public metadata and result contracts. Document bodies are deliberately excluded."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Record(Contract):
    source_id: str | None = None
    document_id: str | None = None
    source_version: str | None = None
    content_hash: str | None = None
    collection: str | None = None
    is_deleted: bool | None = Field(default=None, strict=True)
    indexed_at: AwareDatetime | None = None

    @field_validator("source_id", "document_id", "source_version", "content_hash", "collection")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        return value if value is None or value.strip() else None

    @property
    def identity(self) -> tuple[str, str, str] | None:
        if self.source_id is None or self.document_id is None or self.collection is None:
            return None
        return self.source_id, self.document_id, self.collection


class Finding(Contract):
    code: str
    status: Status
    severity: Severity
    source: str
    source_id: str | None = None
    document_id: str | None = None
    collection: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str


class CheckPolicy(Contract):
    deletion_policy: str = Field(default="remove", pattern="^(remove|tombstone|ignore)$")
    batch_size: int = Field(default=1000, ge=1, le=100_000)
    max_findings: int = Field(default=1000, ge=1)


class CheckReport(Contract):
    schema_version: str = "1.0"
    generated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Status = Status.INCONCLUSIVE
    source_records: int = 0
    index_records: int = 0
    comparisons: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    findings_truncated: bool = False

    def add(self, finding: Finding, limit: int = 1000) -> None:
        self.counts[finding.code] = self.counts.get(finding.code, 0) + 1
        if len(self.findings) < limit:
            self.findings.append(finding)
        else:
            self.findings_truncated = True
        priority = {Status.PASS: 0, Status.INCONCLUSIVE: 1, Status.FAIL: 2, Status.ERROR: 3}
        if priority[finding.status] > priority[self.status]:
            self.status = finding.status
