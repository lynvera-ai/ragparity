"""Exercise disposable updates and restore both application stores into isolated volumes.

Only files created by this run may be edited/deleted. Recovery containers must use a
new project and new database/application volumes. Originals remain stopped and retained
while their backup is verified in the isolated stack; they are always restarted in finally.
"""

import fcntl
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from datetime import UTC, datetime
from urllib.request import Request, urlopen

import psycopg
from manage import (
    APP_URL,
    HERE,
    ROOT,
    authenticate,
    compose,
    docker_environment,
    private_write,
    request,
    settings,
    upload,
    wait_for,
)
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from lynvera_ragparity.checks import ConsistencyChecker
from lynvera_ragparity.core import CheckPolicy
from lynvera_ragparity.indexes import PgVectorIndex
from lynvera_ragparity.sources import PostgreSQLSource


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(source: str, revision: str) -> tuple[str, dict]:
    """Two independent paragraph spans, each below 4096 but together above it."""
    flattened = " ".join(source.split())
    repeated = (flattened + " ") * (2300 // len(flattened) + 1)
    blocks = [
        f"Controlled public-copy block {i}; operations revision {revision}. " + repeated.strip()
        for i in (1, 2)
    ]
    if not all(2200 < len(b) < 4096 for b in blocks) or len("\n\n".join(blocks)) <= 4096:
        raise ValueError("The operational fixture must have exactly two bounded paragraphs")
    body = "\n\n".join(blocks) + "\n"
    return body, {
        str(offset): "sha256:" + digest(block.encode())
        for offset, block in ((0, blocks[0]), (len(blocks[0]) + 2, blocks[1]))
    }


def clone_configuration(config: dict, project: str) -> dict:
    if re.fullmatch(r"ragparity-recovery-[a-f0-9]{12}", project) is None:
        raise ValueError("Recovery project must use an isolated generated name")
    result = json.loads(json.dumps(config))
    result["name"] = project
    for key in ("webui-data", "postgres-data"):
        result["volumes"][key] = {"name": project + "-" + key}
    validate_isolation(result, project)
    return result


def validate_isolation(config: dict, project: str) -> None:
    for service, key, target in (
        ("webui", "webui-data", "/app/backend/data"),
        ("postgres", "postgres-data", "/var/lib/postgresql/data"),
    ):
        mounts = [m for m in config["services"][service]["volumes"] if m["target"] == target]
        if len(mounts) != 1 or mounts[0]["type"] != "volume" or mounts[0]["source"] != key:
            raise ValueError("Recovery data must use dedicated named volumes")
        if config["volumes"][key] != {"name": project + "-" + key}:
            raise ValueError("Recovery must never mount primary data volumes")
        for mount in config["services"][service]["volumes"]:
            if mount["type"] == "volume" and mount["source"] != key:
                raise ValueError("Recovery has an additional unapproved data volume")
            if mount["type"] == "bind" and (
                not mount.get("read_only")
                or mount["target"]
                not in ("/app/ragparity", "/docker-entrypoint-initdb.d/01-pilot.sql")
            ):
                raise ValueError("Recovery bind mounts must be read-only code or initialization")
        environment = config["services"][service]["environment"]
        if service == "webui" and (
            environment["HOST"] != "127.0.0.1" or environment["PORT"] != "8080"
        ):
            raise ValueError("Recovery must retain the existing loopback endpoint")


class Operations:
    def __init__(self):
        self.identifier = uuid.uuid4().hex[:12]
        self.project = "ragparity-recovery-" + self.identifier
        self.directory = (
            ROOT
            / "operations"
            / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + self.identifier)
        )
        self.directory.mkdir(parents=True, mode=0o700)
        self.credentials = settings()
        self.token = authenticate()
        self.created_ids = set()
        self.events = []
        self.recovery_config = self.directory / "recovery-compose.json"
        self.primary_stopped = False
        self.clone_created = False
        self.current_id = None

    def event(self, name: str, passed: bool, **detail) -> None:
        self.events.append(
            {"at": datetime.now(UTC).isoformat(), "check": name, "passed": bool(passed), **detail}
        )
        private_write(self.directory / "journal.json", json.dumps(self.events, indent=2))
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
        if not passed:
            raise RuntimeError("An operational acceptance check failed: " + name)

    def docker(self, *args: str, input=None) -> str:
        result = subprocess.run(
            ["docker", *args],
            env=docker_environment(),
            input=input,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout

    def recovery(self, *args: str) -> str:
        executable = shutil.which("docker-compose")
        prefix = [executable] if executable else ["docker", "compose"]
        result = subprocess.run(
            [*prefix, "-p", self.project, "-f", str(self.recovery_config), *args],
            env=docker_environment(),
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout

    def connection(self, reader=False):
        return psycopg.connect(
            host="127.0.0.1",
            port=55433,
            dbname="pilot",
            connect_timeout=10,
            user="pilot_reader" if reader else "pilot_owner",
            password=self.credentials["reader_password" if reader else "database_password"],
        )

    def source(self, body: str, chunks: dict, deleted=False) -> None:
        private_write(self.directory / f"source-{digest(body.encode())[:12]}.txt", body)
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO pilot_operation_sources VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(document_id) DO UPDATE SET source_version=excluded.source_version,"
                "content_hash=excluded.content_hash,is_deleted=excluded.is_deleted,"
                "expected_chunks=excluded.expected_chunks",
                (
                    "public-document-operations",
                    self.identifier,
                    digest(body.encode()),
                    "sha256:" + digest(body.encode()),
                    "operations-test",
                    deleted,
                    Jsonb(chunks),
                ),
            )
        private_write(
            self.directory / "expected-source.json",
            json.dumps(
                {
                    "body_sha256": digest(body.encode()),
                    "expected_chunks": chunks,
                    "deleted": deleted,
                },
                indent=2,
            ),
        )

    def audit(self, name: str, expected="PASS", required_code=None, original=False) -> None:
        url = URL.create(
            "postgresql+psycopg",
            username="pilot_reader",
            password=self.credentials["reader_password"],
            host="127.0.0.1",
            port=55433,
            database="pilot",
        )
        engine = create_engine(url, hide_parameters=True)
        fields = (
            "source_id",
            "document_id",
            "source_version",
            "content_hash",
            "collection",
            "is_deleted",
        )
        try:
            report = ConsistencyChecker(CheckPolicy(identity_mode="chunk")).check(
                PostgreSQLSource(
                    engine,
                    "pilot_sources" if original else "pilot_operation_sources",
                    columns={k: k for k in (*fields, "expected_chunks")},
                ),
                PgVectorIndex(
                    engine,
                    "pilot_index_metadata" if original else "pilot_operation_index",
                    columns={k: k for k in (*fields, "chunk_id", "chunk_hash")},
                ),
            )
        finally:
            engine.dispose()
        private_write(self.directory / (name + ".json"), report.model_dump_json(indent=2))
        self.event(
            name,
            report.status.value == expected
            and (required_code is None or required_code in report.counts)
            and (
                not original
                or report.source_records
                == report.index_records
                == len(json.loads((ROOT / "uploads.json").read_text()))
            ),
            observed=report.status.value,
            counts=dict(report.counts),
            snapshot_validated=report.audit.snapshot_validated,
            scope="original-corpus" if original else "disposable-copies",
        )

    def reader_privileges(self, name: str) -> None:
        with self.connection(reader=True) as conn:
            privileges = conn.execute(
                "SELECT current_setting('default_transaction_read_only'), "
                "has_table_privilege(current_user,'document_chunk','SELECT'), "
                "has_table_privilege(current_user,'document_chunk','INSERT'), "
                "has_table_privilege(current_user,'pilot_operation_sources','UPDATE'), "
                "has_table_privilege(current_user,'pilot_operation_index','SELECT')"
            ).fetchone()
        self.event(name, privileges == ("on", False, False, False, True))

    def own_file(self, identifier: str) -> dict:
        if identifier not in self.created_ids:
            raise ValueError("Only files created by this operation may be mutated")
        record = request(APP_URL + "/api/v1/files/" + identifier, token=self.token)
        if record["filename"] != f"rpo-operations-{self.identifier}.txt":
            raise ValueError("The disposable file identity changed")
        return record

    def update(self, identifier: str, body: str) -> None:
        self.own_file(identifier)
        request(
            APP_URL + f"/api/v1/files/{identifier}/data/content/update",
            {"content": body},
            token=self.token,
            timeout=300,
        )

    def add(self, body: str) -> str:
        path = self.directory / f"rpo-operations-{self.identifier}.txt"
        private_write(path, body)
        record = upload(path, self.token)
        self.created_ids.add(record["id"])
        self.current_id = record["id"]
        private_write(
            self.directory / "created-file-ids.json", json.dumps(sorted(self.created_ids))
        )
        return record["id"]

    def delete(self, identifier: str) -> None:
        self.own_file(identifier)
        request(APP_URL + f"/api/v1/files/{identifier}", token=self.token, method="DELETE")

    def baseline(self) -> dict:
        uploads = json.loads((ROOT / "uploads.json").read_text())
        files = {}
        for identifier in uploads.values():
            record = request(APP_URL + "/api/v1/files/" + identifier, token=self.token)
            files[identifier] = {key: record[key] for key in ("filename", "hash", "data")}
        with urlopen(
            Request(
                APP_URL + "/api/v1/chats/all",
                headers={
                    "Authorization": "Bearer " + self.token,
                },
            ),
            timeout=30,
        ) as response:
            chats = sorted(
                (json.loads(line) for line in response if line.strip()), key=lambda c: c["id"]
            )
        function = request(APP_URL + "/api/v1/functions/id/ragparity_grounded", token=self.token)
        return {
            "files_sha256": digest(json.dumps(files, sort_keys=True).encode()),
            "chat_sha256": digest(json.dumps(chats, sort_keys=True).encode()),
            "chat_count": len(chats),
            "function_sha256": digest(
                json.dumps(
                    {k: function[k] for k in ("id", "name", "content", "is_active")}, sort_keys=True
                ).encode()
            ),
            "source_count": len(files),
        }

    def target(self, service: str) -> str:
        identifier = self.recovery("ps", "-aq", service).strip()
        if not identifier:
            raise ValueError("Recovery container was not created")
        info = json.loads(self.docker("inspect", identifier))[0]
        if info["Config"]["Labels"].get("com.docker.compose.project") != self.project:
            raise ValueError("The target container is not the isolated recovery project")
        target = "/app/backend/data" if service == "webui" else "/var/lib/postgresql/data"
        expected = self.project + ("-webui-data" if service == "webui" else "-postgres-data")
        if [m.get("Name") for m in info["Mounts"] if m["Destination"] == target] != [expected]:
            raise ValueError("The target container does not use its isolated data volume")
        return identifier

    def wait_database(self) -> None:
        import time

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                with self.connection() as conn:
                    conn.execute("SELECT 1")
                return
            except psycopg.OperationalError:
                time.sleep(1)
        raise RuntimeError("The database did not recover within its startup budget")

    def backup_restore(self, baseline: dict) -> None:
        backup = self.directory / "backup"
        data = backup / "webui-data"
        data.mkdir(parents=True, mode=0o700)
        dump = backup / "pilot.dump"
        with self.connection() as conn:
            system_id = conn.execute(
                "SELECT system_identifier::text FROM pg_control_system()"
            ).fetchone()[0]
        config_command = [
            shutil.which("docker-compose"),
            "-f",
            str(HERE / "compose.yaml"),
            "config",
            "--format",
            "json",
        ]
        config = json.loads(
            subprocess.check_output(config_command, env=docker_environment(), text=True)
        )
        isolated = clone_configuration(config, self.project)
        runtime = backup / "runtime"
        runtime.mkdir(mode=0o700)
        for name in ("secrets.json", "uploads.json", "ui-install.json"):
            shutil.copy2(ROOT / name, runtime / name)
        shutil.copy2(HERE / "versions.json", runtime / "versions.json")
        shutil.copytree(ROOT / "ui-bundle", runtime / "ui-bundle")
        for mount in isolated["services"]["webui"]["volumes"]:
            if mount["target"] == "/app/ragparity":
                mount["source"] = str(runtime / "ui-bundle")
        private_write(self.recovery_config, json.dumps(isolated, indent=2))
        self.primary_stopped = True
        compose("stop", "webui")
        compose("cp", "webui:/app/backend/data/.", str(data))
        temporary = "/tmp/ragparity-backup-" + self.identifier + ".dump"
        compose(
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "pilot_owner",
            "-d",
            "pilot",
            "-Fc",
            "-f",
            temporary,
        )
        compose("cp", "postgres:" + temporary, str(dump))
        manifest = {
            str(p.relative_to(backup)): digest(p.read_bytes())
            for p in backup.rglob("*")
            if p.is_file()
        }
        private_write(backup / "manifest.json", json.dumps(manifest, indent=2))
        for path in [backup, *backup.rglob("*")]:
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.event(
            "backup-recorded",
            bool(manifest) and dump.stat().st_size > 0,
            files=len(manifest),
            postgres_system_id=system_id,
        )
        compose("stop", "postgres")
        self.recovery("create")
        self.clone_created = True
        postgres_id, webui_id = self.target("postgres"), self.target("webui")
        self.recovery("start", "postgres")
        self.wait_database()
        with self.connection() as conn:
            restored_id = conn.execute(
                "SELECT system_identifier::text FROM pg_control_system()"
            ).fetchone()[0]
            self.event(
                "isolated-new-database-cluster",
                restored_id != system_id,
                restored_system_id=restored_id,
            )
            conn.execute(
                sql.SQL("CREATE ROLE pilot_reader LOGIN PASSWORD {}").format(
                    sql.Literal(self.credentials["reader_password"])
                )
            )
            conn.execute("ALTER ROLE pilot_reader SET default_transaction_read_only = on")
        self.docker("cp", str(dump), postgres_id + ":/tmp/restore.dump")
        self.recovery(
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "-U",
            "pilot_owner",
            "-d",
            "pilot",
            "--exit-on-error",
            "/tmp/restore.dump",
        )
        self.docker("cp", str(data) + "/.", webui_id + ":/app/backend/data")
        self.recovery("start", "webui")
        wait_for(APP_URL + "/health", 240)
        self.event(
            "restored-original-files-chats-function",
            self.baseline() == baseline,
            preserved_chat_count=baseline["chat_count"],
        )
        self.audit("restored-metadata")
        self.audit("restored-original-corpus", original=True)
        self.reader_privileges("restored-auditor-select-only")
        self.smoke("restored-retrieval-generation")
        canary_path = self.directory / f"rpo-recovery-canary-{self.identifier}.txt"
        canary_body = "Recovery canary on an isolated restored pilot.\n"
        private_write(canary_path, canary_body)
        uploaded = upload(canary_path, self.token)
        private_write(
            self.directory / "canary-upload-response.json", json.dumps(uploaded, indent=2)
        )
        # Upload responses may retain pre-processing metadata; read the committed record.
        canary = request(APP_URL + "/api/v1/files/" + uploaded["id"], token=self.token)
        self.event(
            "restored-stack-accepts-new-committed-file",
            canary["hash"] == digest(canary_body.encode())
            and canary["data"].get("status") == "completed",
        )
        # Kill only the verified disposable containers. Original volumes are not mounted.
        self.docker("kill", self.target("webui"), self.target("postgres"))
        self.recovery("start", "postgres")
        self.wait_database()
        self.recovery("start", "webui")
        wait_for(APP_URL + "/health", 240)
        self.event("abrupt-restart-preserves-original-state", self.baseline() == baseline)
        self.audit("abrupt-restart-metadata")
        self.audit("abrupt-restart-original-corpus", original=True)
        recovered_canary = request(APP_URL + "/api/v1/files/" + canary["id"], token=self.token)
        with self.connection() as conn:
            canary_chunks = conn.execute(
                "SELECT encode(digest(text,'sha256'),'hex') FROM document_chunk "
                "WHERE collection_name=%s",
                ("file-" + canary["id"],),
            ).fetchall()
        self.event(
            "new-file-survives-abrupt-restart",
            recovered_canary["hash"] == canary["hash"]
            and recovered_canary["data"]["content"] == canary_body
            and canary_chunks == [(digest(canary_body.strip().encode()),)],
        )
        self.smoke("abrupt-restart-retrieval-generation")
        self.event(
            "backup-checksums-unchanged",
            all(
                digest((backup / name).read_bytes()) == checksum
                for name, checksum in manifest.items()
            ),
        )

    def smoke(self, name: str) -> None:
        versions = json.loads((HERE / "versions.json").read_text())
        result = request(
            APP_URL + "/api/chat/completions",
            {
                "model": "ragparity_grounded",
                "stream": False,
                "id": str(uuid.uuid4()),
                "chat_id": "local:recovery-" + self.identifier,
                "messages": [
                    {
                        "role": "user",
                        "content": "What whole-surface mean temperature in C is listed for Mars?",
                    }
                ],
            },
            token=self.token,
            timeout=240,
        )
        private_write(self.directory / (name + ".json"), json.dumps(result, indent=2))
        text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.event(
            name,
            text.startswith("**-65 °C**")
            and "nasa-mars" in text
            and versions["nasa"]["files"]["facts.html"]["url"] in text,
        )

    def run(self) -> None:
        print("Operations: " + str(self.directory.name), flush=True)
        provenance = {
            "started_at": datetime.now(UTC).isoformat(),
            "code_sha256": {
                name: digest((HERE / name).read_bytes())
                for name in (
                    "operations.py",
                    "operations.sql",
                    "manage.py",
                    "transport.py",
                    "versions.json",
                )
            },
            "project": self.project,
        }
        private_write(self.directory / "provenance.json", json.dumps(provenance, indent=2))
        for name in provenance["code_sha256"]:
            private_write(self.directory / "code" / name, (HERE / name).read_text())
        baseline = self.baseline()
        private_write(self.directory / "baseline.json", json.dumps(baseline, indent=2))
        source_manifest = json.loads((ROOT / "corpus/manifest.json").read_text())
        mars = next(d for d in source_manifest["documents"] if d["id"] == "nasa-mars")
        original = (ROOT / "corpus" / mars["filename"]).read_text()
        body1, chunks1 = fixture(original, "A")
        body2, chunks2 = fixture(original, "B")
        with self.connection() as conn:
            conn.execute((HERE / "operations.sql").read_text())
        self.reader_privileges("original-auditor-select-only")
        try:
            self.source(body1, chunks1)
            identifier = self.add(body1)
            self.audit("initial-two-chunk-ingestion")
            self.source(body2, chunks2)
            self.audit("stale-index-detected", "FAIL", "VERSION_MISMATCH")
            self.update(identifier, body2)
            self.audit("updated-and-reindexed")
            with self.connection() as conn:
                removed = conn.execute(
                    "DELETE FROM document_chunk WHERE ctid IN (SELECT ctid FROM document_chunk "
                    "WHERE collection_name=%s LIMIT 1) RETURNING id",
                    ("file-" + identifier,),
                ).fetchall()
            self.event("one-test-fragment-interrupted", len(removed) == 1)
            self.audit("missing-fragment-detected", "FAIL", "MISSING_CHUNK")
            self.update(identifier, body2)
            self.audit("partial-index-repaired")
            self.source(body2, chunks2, True)
            self.audit("pending-deletion-detected", "FAIL", "DELETED_PRESENT")
            self.delete(identifier)
            self.current_id = None
            self.audit("deletion-propagated")
            self.source(body2, chunks2)
            self.audit("restore-gap-detected", "FAIL", "MISSING_CHUNK")
            identifier = self.add(body2)
            self.audit("deleted-document-recovered")
            self.backup_restore(baseline)
        finally:
            try:
                if self.clone_created:
                    self.recovery("stop")
            finally:
                if self.primary_stopped:
                    compose("start", "postgres")
                    self.wait_database()
                    compose("start", "webui")
                    wait_for(APP_URL + "/health", 240)
            if self.current_id:
                self.source(body2, chunks2, True)
                self.delete(self.current_id)
                self.current_id = None
            self.event("original-pilot-state-preserved", self.baseline() == baseline)
        self.audit("disposable-copy-cleanup")
        self.audit("original-corpus-after-recovery", original=True)
        self.smoke("original-pilot-after-recovery")
        private_write(
            self.directory / "report.json",
            json.dumps(
                {
                    "checks": len(self.events),
                    "passed": all(e["passed"] for e in self.events),
                    "events": self.events,
                },
                indent=2,
            ),
        )
        print("Operation reports: " + str(self.directory), flush=True)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "operations.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        operation = Operations()
        try:
            operation.run()
        except Exception as exc:
            private_write(
                operation.directory / "failure.json",
                json.dumps(
                    {"error_type": type(exc).__name__, "checks": operation.events}, indent=2
                ),
            )
            print(
                "Operations failed: " + type(exc).__name__ + "; private journal retained.",
                flush=True,
            )
            raise SystemExit(2) from None


if __name__ == "__main__":
    main()
