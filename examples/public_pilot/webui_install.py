"""Install or collect evidence from the local Open WebUI grounded document mode."""

import argparse
import hashlib
import json
from urllib.error import HTTPError

from manage import APP_URL, HERE, ROOT, authenticate, compose, private_write, request, wait_for

FUNCTION_ID = "ragparity_grounded"
FUNCTION_NAME = "RAGParity · Public documents"
BUNDLE_FILES = ("runtime.py", "transport.py", "grounded.py", "language.py", "chat_adapter.py")


def install() -> None:
    token = authenticate()
    owner = request(APP_URL + "/api/v1/auths/", token=token)
    bundle = ROOT / "ui-bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in BUNDLE_FILES:
        text = (HERE / name).read_text()
        hashes[name] = hashlib.sha256(text.encode()).hexdigest()
        private_write(bundle / name, text)
    config = {
        "schema_version": 1,
        "owner_id": owner["id"],
        "uploads": json.loads((ROOT / "uploads.json").read_text()),
        "versions": json.loads((HERE / "versions.json").read_text()),
        "code_sha256": hashes,
    }
    private_write(bundle / "ui-config.json", json.dumps(config, indent=2))
    # Only this isolated application's container is recreated; its volume is retained.
    compose("up", "-d", "--no-deps", "--force-recreate", "webui")
    wait_for(APP_URL + "/health", 240)
    content = (HERE / "webui_pipe.py").read_text()
    state_path = ROOT / "ui-install.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    existing = None
    try:
        existing = request(APP_URL + f"/api/v1/functions/id/{FUNCTION_ID}", token=token)
    except HTTPError as exc:
        if exc.code not in (401, 404):
            raise
    form = {
        "id": FUNCTION_ID,
        "name": FUNCTION_NAME,
        "content": content,
        "meta": {
            "description": "Static public documents with local evidence selection and abstention."
        },
    }
    if existing:
        actual = hashlib.sha256(existing["content"].encode()).hexdigest()
        if actual not in (
            state.get("function_sha256"),
            hashlib.sha256(content.encode()).hexdigest(),
        ):
            raise RuntimeError(
                "The existing function was edited separately; inspect it before updating"
            )
        if existing["content"] != content:
            existing = request(
                APP_URL + f"/api/v1/functions/id/{FUNCTION_ID}/update", form, token=token
            )
    else:
        existing = request(APP_URL + "/api/v1/functions/create", form, token=token)
    if not existing["is_active"]:
        request(APP_URL + f"/api/v1/functions/id/{FUNCTION_ID}/toggle", {}, token=token)
    catalog = request(APP_URL + "/api/models", token=token)
    if FUNCTION_ID not in {model["id"] for model in catalog.get("data", [])}:
        raise RuntimeError("The grounded document mode was not registered")
    private_write(
        state_path,
        json.dumps(
            {
                "function_id": FUNCTION_ID,
                "function_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "code_sha256": hashes,
            },
            indent=2,
        ),
    )
    print(f"Chat mode ready: {FUNCTION_NAME}")


def collect() -> None:
    destination = ROOT / "ui-receipts"
    destination.mkdir(parents=True, exist_ok=True)
    destination.chmod(0o700)
    compose("cp", "webui:/app/backend/data/ragparity-receipts/.", str(destination))
    for path in destination.glob("*.json"):
        path.chmod(0o600)
    print(f"Collected {len(list(destination.glob('*.json')))} private chat receipts.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "collect"))
    args = parser.parse_args()
    {"install": install, "collect": collect}[args.action]()


if __name__ == "__main__":
    main()
