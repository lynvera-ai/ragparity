"""Metadata, audit and versioned report contracts; document bodies are excluded."""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from lynvera_ragparity.core.codes import FindingCode

Label = Annotated[str, Field(min_length=1, pattern=r"\S")]
BASE_RECORD_FIELDS = (
    "source_id",
    "document_id",
    "source_version",
    "content_hash",
    "collection",
    "is_deleted",
)
DATABASE_DEFAULT_FIELDS = (*BASE_RECORD_FIELDS, "indexed_at")


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
    updated_at: AwareDatetime | None = None
    snapshot_id: Label | None = None
    chunk_id: Label | None = None
    chunk_hash: Label | None = None
    expected_chunks: dict[Label, Label] | None = Field(default=None, max_length=10_000)

    @field_validator("source_id", "document_id", "source_version", "content_hash", "collection")
    @classmethod
    def nonblank(cls, value: str | None) -> str | None:
        return value if value is None or value.strip() else None

    @property
    def identity(self) -> tuple[str, str, str] | None:
        if self.source_id is None or self.document_id is None or self.collection is None:
            return None
        return self.source_id, self.document_id, self.collection


class SnapshotEvidence(Contract):
    """Caller-supplied completion evidence for an immutable, scoped scan."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: Label
    scope: Label
    as_of: AwareDatetime
    completed_at: AwareDatetime | None = None
    record_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def ordered_timestamps(self) -> "SnapshotEvidence":
        if self.completed_at is not None and self.completed_at < self.as_of:
            raise ValueError("Completion must not precede the audit cutoff")
        return self


class Finding(Contract):
    code: FindingCode
    status: Status
    severity: Severity
    source: str
    source_id: str | None = None
    document_id: str | None = None
    collection: str | None = None
    chunk_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str


class CheckPolicy(Contract):
    deletion_policy: Literal["remove", "tombstone", "ignore"] = "remove"
    identity_mode: Literal["document", "chunk"] = "document"
    batch_size: int = Field(default=1000, ge=1, le=100_000)
    max_findings: int = Field(default=1000, ge=1)
    require_snapshot: bool = Field(default=False, strict=True)
    sync_grace_seconds: int = Field(default=0, ge=0, le=31_536_000)
    reference_time: AwareDatetime | None = None
    max_duration_seconds: float | None = Field(default=None, gt=0)
    max_spool_bytes: int | None = Field(default=None, ge=65_536)
    temporary_directory: Path | None = None


class AuditContext(Contract):
    reference_time: AwareDatetime
    identity_mode: Literal["document", "chunk"]
    deletion_policy: Literal["remove", "tombstone", "ignore"]
    sync_grace_seconds: int
    snapshot_validated: bool = False
    source_snapshot: SnapshotEvidence | None = None
    index_snapshot: SnapshotEvidence | None = None


class ExecutionMetrics(Contract):
    elapsed_seconds: float = Field(default=0, ge=0)
    spool_bytes: int = Field(default=0, ge=0)


class CheckReport(Contract):
    schema_version: Literal["1.0", "2.0"] = "2.0"
    generated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Status = Status.INCONCLUSIVE
    source_records: int = Field(default=0, ge=0)
    index_records: int = Field(default=0, ge=0)
    comparisons: int = Field(default=0, ge=0)
    counts: dict[FindingCode, Annotated[int, Field(ge=0)]] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    findings_truncated: bool = False
    audit: AuditContext | None = None
    metrics: ExecutionMetrics | None = None
    redacted: bool = False

    def add(self, finding: Finding, limit: int = 1000) -> None:
        self.counts[finding.code] = self.counts.get(finding.code, 0) + 1
        if len(self.findings) < limit:
            self.findings.append(finding)
        else:
            self.findings_truncated = True
        priority = {Status.PASS: 0, Status.INCONCLUSIVE: 1, Status.FAIL: 2, Status.ERROR: 3}
        if priority[finding.status] > priority[self.status]:
            self.status = finding.status
