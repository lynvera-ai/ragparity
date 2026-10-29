"""Local HTTP transport shared by host scripts and the native chat adapter."""

import json
from urllib.request import Request, urlopen

MODEL_URL = "http://127.0.0.1:11445"
APP_URL = "http://127.0.0.1:3188"


def request(url: str, data=None, *, token=None, method=None, timeout=180, headers=None):
    fields = {"Content-Type": "application/json", **(headers or {})}
    if token:
        fields["Authorization"] = "Bearer " + token
    body = (
        data if isinstance(data, bytes) else json.dumps(data).encode() if data is not None else None
    )
    with urlopen(
        Request(url, data=body, headers=fields, method=method), timeout=timeout
    ) as response:
        return json.load(response)
