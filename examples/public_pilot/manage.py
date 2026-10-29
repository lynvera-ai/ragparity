"""Manage the isolated macOS public-document pilot. Runtime data stays outside Git."""

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import signal
import subprocess
import tarfile
import time
from contextlib import suppress
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from corpus import HERE, ROOT, prepare
from transport import APP_URL, MODEL_URL, request

PROFILE = "ragparity-public"


def private_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(value)


def healthy(url: str) -> bool:
    try:
        request(url, timeout=3)
        return True
    except (URLError, TimeoutError, ConnectionError, ValueError):
        return False


def wait_for(url: str, seconds: int = 180) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if healthy(url):
            return
        time.sleep(2)
    raise RuntimeError("A pilot service did not become ready; inspect the private runtime logs")


def settings() -> dict:
    ROOT.mkdir(parents=True, exist_ok=True)
    ROOT.chmod(0o700)
    path = ROOT / "secrets.json"
    if not path.exists():
        private_write(
            path,
            json.dumps(
                {
                    "database_password": secrets.token_hex(24),
                    "reader_password": secrets.token_hex(24),
                    "webui_secret": secrets.token_hex(32),
                    "email": "pilot@ragparity.invalid",
                    "password": secrets.token_urlsafe(24),
                }
            ),
        )
    value = json.loads(path.read_text())
    private_write(
        ROOT / "login.txt",
        f"URL: {APP_URL}\nEmail: {value['email']}\nPassword: {value['password']}\n",
    )
    return value


def docker_environment() -> dict:
    data = settings()
    config = ROOT / "docker"
    config.mkdir(exist_ok=True)
    (ROOT / "ui-bundle").mkdir(exist_ok=True)
    private_write(config / "config.json", '{"auths":{}}\n')
    env = os.environ.copy()
    env.pop("DOCKER_CONTEXT", None)
    env.update(
        DOCKER_HOST=f"unix://{Path.home()}/.colima/{PROFILE}/docker.sock",
        DOCKER_CONFIG=str(config),
        PILOT_DB_PASSWORD=data["database_password"],
        PILOT_WEBUI_SECRET=data["webui_secret"],
        PILOT_UI_BUNDLE=str(ROOT / "ui-bundle"),
    )
    return env


def compose(*args: str) -> None:
    executable = shutil.which("docker-compose")
    prefix = [executable] if executable else ["docker", "compose"]
    subprocess.run(
        [*prefix, "-f", str(HERE / "compose.yaml"), *args], env=docker_environment(), check=True
    )


def model_environment() -> dict:
    return {
        **os.environ,
        "OLLAMA_HOST": "127.0.0.1:11445",
        "OLLAMA_MODELS": str(ROOT / "models"),
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_MAX_LOADED_MODELS": "1",
        "OLLAMA_NUM_PARALLEL": "1",
        "OLLAMA_KEEP_ALIVE": "0",
        "OLLAMA_CONTEXT_LENGTH": "4096",
    }


def spawn(name: str, arguments: list[str], env=None) -> None:
    path = ROOT / f"{name}.pid"
    if path.exists():
        try:
            pid = int(path.read_text())
            os.kill(pid, 0)
            command = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True, check=True
            ).stdout
            if str(ROOT) in command:
                return
            path.unlink()
        except (ProcessLookupError, subprocess.CalledProcessError):
            path.unlink(missing_ok=True)
    with (ROOT / f"{name}.log").open("ab") as output:
        process = subprocess.Popen(
            arguments, stdout=output, stderr=subprocess.STDOUT, start_new_session=True, env=env
        )
    private_write(path, str(process.pid))
    time.sleep(0.3)
    if process.poll() is not None:
        path.unlink(missing_ok=True)
        raise RuntimeError("A pilot process could not start; check for occupied local ports")


def install() -> None:
    settings()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("This isolated installer targets Apple Silicon macOS")
    for executable in ("docker", "colima", "ssh"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"Install the free prerequisite {executable} before continuing")
    versions = json.loads((HERE / "versions.json").read_text())
    binary = ROOT / "ollama/ollama"
    if not binary.exists():
        if shutil.disk_usage(ROOT).free < 8 * 2**30:
            raise RuntimeError(
                "At least 8 GiB of free space is needed for the initial pilot downloads"
            )
        archive = ROOT / "ollama-darwin.tgz"
        with urlopen(versions["ollama_url"], timeout=60) as response, archive.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != versions["ollama_sha256"]:
            archive.unlink()
            raise RuntimeError("The official runtime archive failed its checksum check")
        with tarfile.open(archive) as bundle:
            bundle.extractall(ROOT / "ollama", filter="data")
        archive.unlink()
    start()
    for model in (versions["embedding_model"], versions["generation_model"]):
        outcome = request(MODEL_URL + "/api/pull", {"model": model, "stream": False}, timeout=900)
        if outcome.get("status") != "success":
            raise RuntimeError("A local model download did not complete")
        print(f"Local model ready: {model}", flush=True)
    installed = request(MODEL_URL + "/api/tags")
    actual = {item["name"]: item["digest"] for item in installed["models"]}
    if any(actual.get(name) != digest for name, digest in versions["model_digests"].items()):
        raise RuntimeError("A downloaded model differs from the reviewed model digest")
    private_write(ROOT / "installed-models.json", json.dumps(installed, indent=2))
    manifest = prepare()
    print(f"Prepared {len(manifest['documents'])} attributed public excerpts.")


def start() -> None:
    settings()
    binary = ROOT / "ollama/ollama"
    if not binary.exists():
        raise RuntimeError("Run install before starting the pilot")
    if not healthy(MODEL_URL + "/api/version"):
        spawn("ollama", [str(binary), "serve"], model_environment())
    wait_for(MODEL_URL + "/api/version")
    pid_path = ROOT / "ollama.pid"
    if not pid_path.exists():
        raise RuntimeError("The model port belongs to a server not managed by this pilot")
    pid = int(pid_path.read_text())
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True, check=True
    ).stdout
    if str(binary) not in command:
        raise RuntimeError("The model server process does not belong to this installation")
    version = json.loads((HERE / "versions.json").read_text())["ollama_version"]
    if request(MODEL_URL + "/api/version").get("version") != version:
        raise RuntimeError("The running model server differs from the pinned runtime version")
    subprocess.run(
        [
            "colima",
            "start",
            PROFILE,
            "--activate=false",
            "--cpus",
            "2",
            "--memory",
            "1.5",
            "--disk",
            "10",
            "--ssh-config=false",
            "--port-forwarder",
            "none",
            "--runtime",
            "docker",
        ],
        check=True,
    )
    config = subprocess.check_output(["colima", "ssh-config", PROFILE], text=True)
    private_write(ROOT / "ssh.config", config)
    spawn(
        "tunnel",
        [
            "ssh",
            "-F",
            str(ROOT / "ssh.config"),
            "-N",
            "-o",
            "ControlMaster=no",
            "-o",
            "ControlPath=none",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
            "-L",
            "127.0.0.1:3188:127.0.0.1:8080",
            "-L",
            "127.0.0.1:55433:127.0.0.1:5432",
            "-R",
            "127.0.0.1:11445:127.0.0.1:11445",
            "colima-" + PROFILE,
        ],
    )
    compose("up", "-d")
    wait_for(APP_URL + "/health", 240)
    print("Pilot UI ready at http://127.0.0.1:3188")


def authenticate() -> str:
    credentials = settings()
    if credentials.get("token"):
        try:
            request(APP_URL + "/api/v1/auths/", token=credentials["token"], timeout=10)
            return credentials["token"]
        except HTTPError:
            pass
    payload = {"email": credentials["email"], "password": credentials["password"]}
    try:
        result = request(APP_URL + "/api/v1/auths/signin", payload)
    except HTTPError as exc:
        if exc.code not in (400, 401, 403):
            raise
        result = request(APP_URL + "/api/v1/auths/signup", {**payload, "name": "Public pilot"})
    credentials["token"] = result["token"]
    private_write(ROOT / "secrets.json", json.dumps(credentials))
    return credentials["token"]


def upload(path: Path, token: str) -> dict:
    boundary = secrets.token_hex(16)
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{path.name}"\r\n'
            "Content-Type: text/plain\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return request(
        APP_URL + "/api/v1/files/?process_in_background=false",
        body,
        token=token,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
        timeout=300,
    )


def ingest() -> None:
    token = authenticate()
    manifest = json.loads((ROOT / "corpus/manifest.json").read_text())
    uploads_path = ROOT / "uploads.json"
    uploads = json.loads(uploads_path.read_text()) if uploads_path.exists() else {}
    for document in manifest["documents"]:
        if document["id"] in uploads:
            existing = request(APP_URL + f"/api/v1/files/{uploads[document['id']]}", token=token)
            if (existing.get("data") or {}).get("status") == "completed":
                continue
            raise RuntimeError("An existing pilot upload is incomplete; inspect it before retrying")
        path = ROOT / "corpus" / document["filename"]
        if "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != document["content_hash"]:
            raise RuntimeError("A source excerpt changed after its reference manifest was prepared")
        result = upload(path, token)
        uploads[document["id"]] = result["id"]
        private_write(uploads_path, json.dumps(uploads, indent=2))
        ready = request(APP_URL + f"/api/v1/files/{result['id']}", token=token)
        if (ready.get("data") or {}).get("status") != "completed":
            raise RuntimeError("The application has not completed document ingestion")
        print(f"Indexed public document: {document['id']}", flush=True)
    provision_audit(manifest)


def provision_audit(manifest: dict) -> None:
    import psycopg
    from psycopg import sql

    credentials = settings()
    with psycopg.connect(
        host="127.0.0.1",
        port=55433,
        user="pilot_owner",
        dbname="pilot",
        password=credentials["database_password"],
        connect_timeout=10,
    ) as connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='pilot_reader'").fetchone():
            connection.execute(
                sql.SQL("CREATE ROLE pilot_reader LOGIN PASSWORD {}").format(
                    sql.Literal(credentials["reader_password"])
                )
            )
        connection.execute((HERE / "audit.sql").read_text())
        for document in manifest["documents"]:
            connection.execute(
                "INSERT INTO pilot_sources(source_id,document_id,source_version,"
                "content_hash,collection,is_deleted,expected_chunks) "
                "VALUES (%s,%s,%s,%s,%s,false,%s) ON CONFLICT(document_id) DO NOTHING",
                (
                    document["source_id"],
                    document["id"],
                    document["source_version"],
                    document["content_hash"],
                    document["collection"],
                    psycopg.types.json.Jsonb({"0": document["chunk_hash"]}),
                ),
            )
    print("Read-only audit projections prepared from the independent source manifest.")


def audit() -> None:
    from sqlalchemy import create_engine

    from lynvera_ragparity.checks import ConsistencyChecker
    from lynvera_ragparity.core import CheckPolicy
    from lynvera_ragparity.indexes import PgVectorIndex
    from lynvera_ragparity.reports import write_report
    from lynvera_ragparity.sources import PostgreSQLSource

    password = settings()["reader_password"]
    engine = create_engine(
        f"postgresql+psycopg://pilot_reader:{password}@127.0.0.1:55433/pilot", hide_parameters=True
    )
    source_fields = (
        "source_id",
        "document_id",
        "source_version",
        "content_hash",
        "collection",
        "is_deleted",
        "expected_chunks",
    )
    index_fields = (*source_fields[:-1], "chunk_id", "chunk_hash")
    try:
        report = ConsistencyChecker(CheckPolicy(identity_mode="chunk")).check(
            PostgreSQLSource(engine, "pilot_sources", columns={key: key for key in source_fields}),
            PgVectorIndex(
                engine, "pilot_index_metadata", columns={key: key for key in index_fields}
            ),
        )
        write_report(report, ROOT / "metadata-report.json", "json")
        write_report(report, ROOT / "metadata-report.html", "html")
        print(f"{report.status}: source={report.source_records} index={report.index_records}")
        for code, count in report.counts.items():
            print(f"{code}: {count}")
        raise SystemExit({"PASS": 0, "FAIL": 1, "ERROR": 2, "INCONCLUSIVE": 3}[report.status.value])
    finally:
        engine.dispose()


def stop() -> None:
    with suppress(subprocess.CalledProcessError):
        compose("stop")
    for name in ("tunnel", "ollama"):
        path = ROOT / f"{name}.pid"
        if path.exists():
            pid = int(path.read_text())
            arguments = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True
            ).stdout
            if str(ROOT) in arguments:
                with suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGTERM)
            path.unlink()
    subprocess.run(["colima", "stop", PROFILE], check=True)
    print("Pilot stopped; downloaded models, documents and application data are retained.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("install", "start", "corpus", "ingest", "audit", "status", "stop")
    )
    args = parser.parse_args()
    actions = {
        "install": install,
        "start": start,
        "corpus": prepare,
        "ingest": ingest,
        "audit": audit,
        "stop": stop,
        "status": lambda: print(
            json.dumps(
                {
                    "webui": healthy(APP_URL + "/health"),
                    "models": healthy(MODEL_URL + "/api/version"),
                }
            )
        ),
    }
    try:
        actions[args.action]()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Pilot action failed ({type(exc).__name__}); inspect the private runtime logs.")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
