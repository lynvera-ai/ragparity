"""Native chat adapter for the same benchmark-independent grounded runtime."""

import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from language import LABELS_ES, SUBJECTS_ES, UNITS_ES, normalize_question, question_language
from runtime import answer_question, refresh_model_catalog
from transport import request

UNIT_PATTERNS = {
    "C": r"Celsius|degrees\s+C|°\s*C|C",
    "km": r"km|kilometers|kilometres",
    "hours": r"hours|hrs",
    "days": r"days",
    "columns": r"columns",
    "databases": r"databases",
    "relations": r"relations",
    "TB": r"TB|terabytes",
    "GB": r"GB|gigabytes",
    "bytes": r"bytes",
    "arguments": r"arguments",
    "keys": r"keys",
    "parameters": r"parameters",
    "people": r"people|population",
}
REASONS = {
    "NO_EVIDENCE_FOR_MEASUREMENT": (
        "The retrieved documents do not contain that measurement with those qualifiers."
    ),
    "AMBIGUOUS_MEASUREMENT": (
        "Ask for one measurement at a time: solar day or sidereal rotation, for example."
    ),
    "MEASUREMENT_UNSPECIFIED": (
        "Name the measurement explicitly, such as mean temperature or solar day."
    ),
    "DERIVED_MEASUREMENT_UNSUPPORTED": (
        "This mode extracts listed measurements and cannot calculate new values."
    ),
    "NO_EVIDENCE_FOR_UNIT": "The public documents contain no evidence for that measurement unit.",
    "NO_EVIDENCE_FOR_SUBJECT": "The requested subject is absent from the retrieved documents.",
    "AMBIGUOUS_SUBJECT": "Please ask about one named subject at a time.",
    "STATIC_EVIDENCE_SCOPE": "These documents contain no local or time-specific readings.",
}

REASONS_ES = {
    "NO_EVIDENCE_FOR_MEASUREMENT": (
        "No hay evidencia de esa medida con los calificadores solicitados."
    ),
    "AMBIGUOUS_MEASUREMENT": (
        "Pregunta por una sola medida: por ejemplo, día solar o rotación sideral."
    ),
    "MEASUREMENT_UNSPECIFIED": "Nombra la medida solicitada, como temperatura media o día solar.",
    "DERIVED_MEASUREMENT_UNSUPPORTED": (
        "Este modo extrae medidas documentadas y no calcula valores nuevos."
    ),
    "NO_EVIDENCE_FOR_UNIT": (
        "Los documentos públicos no contienen evidencia para esa unidad de medida."
    ),
    "NO_EVIDENCE_FOR_SUBJECT": "El sujeto solicitado no aparece en los documentos recuperados.",
    "AMBIGUOUS_SUBJECT": "Pregunta por un solo sujeto con nombre explícito cada vez.",
    "STATIC_EVIDENCE_SCOPE": (
        "Estos documentos no contienen mediciones locales ni de un momento concreto."
    ),
}


class ChatInputError(ValueError):
    """A safe clarification message, rather than an operational failure."""


def question_text(body: dict, language="en") -> str:
    message = next(
        (item for item in reversed(body.get("messages", [])) if item.get("role") == "user"), {}
    )
    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip() or len(content) > 4000:
        raise ChatInputError(
            "Usa una sola pregunta de texto de hasta 4.000 caracteres."
            if language == "es"
            else "Use one text question of at most 4,000 characters."
        )
    return content.strip()


def infer_unit(question: str) -> str | None:
    _, question = normalize_question(question)
    matches = {
        unit
        for unit, pattern in UNIT_PATTERNS.items()
        if re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", question, re.IGNORECASE)
    }
    # Prefer the requested 'in <unit>' over units mentioned only as build conditions.
    explicit = {
        unit
        for unit in matches
        if re.search(
            r"\b(?:in|expressed in|units of)\s+(?:" + UNIT_PATTERNS[unit] + r")(?!\w)",
            question,
            re.IGNORECASE,
        )
    }
    # Coordinated requested units are ambiguous even if only the first follows 'in'.
    if explicit:
        explicit.update(
            unit
            for unit in matches
            if re.search(
                r"\b(?:and|or)\s+(?:in\s+)?(?:" + UNIT_PATTERNS[unit] + r")(?!\w)",
                question,
                re.IGNORECASE,
            )
        )
    selected = explicit or matches
    return next(iter(selected)) if len(selected) == 1 else None


def render_answer(result: dict, versions: dict, language="en") -> str:
    spanish = language == "es"
    if result["status"] == "ANSWERED":
        answer = result["structured_answer"]
        fact = result["eligible_evidence_rows"][result["selection_index"]]
        identity = result["retrieved_documents"][fact["document_id"]]
        if identity["source_id"] == "nasa-planetary":
            url = versions["nasa"]["files"]["facts.html"]["url"]
        else:
            url = (
                "https://github.com/postgres/postgres/blob/"
                + versions["corpus_revision"]
                + "/doc/src/sgml/limits.sgml"
            )
        unit = "°C" if answer["unit"] == "C" else answer["unit"]
        if spanish:
            unit = UNITS_ES.get(answer["unit"], answer["unit"])
        subject = SUBJECTS_ES.get(fact["subject"], fact["subject"]) if spanish else fact["subject"]
        label = LABELS_ES.get(fact["label"], fact["label"]) if spanish else fact["label"]
        source_label = "Fuente" if spanish else "Source"
        extracted = (
            "Extraído del documento recuperado. Extracto original en inglés."
            if spanish
            else "Extracted from the retrieved document."
        )
        quote = fact["quote"]
        if quote.startswith("Metric ID:"):
            quote = quote.split("; ", 1)[-1]
        conditions = (
            ("\n\nCondiciones de la fuente (inglés): " if spanish else "\n\nSource conditions: ")
            + fact["conditions"]
            if identity["source_id"] == "nasa-planetary"
            else ""
        )
        return (
            f"**{answer['value']} {unit}**\n\n"
            f"{subject} — {label}.\n\n"
            f"{source_label}: [{fact['document_id']}]({url}).\n\n"
            f"> {quote}\n\n" + extracted + conditions
        )
    if result["status"] == "ABSTAINED":
        reason = REASONS.get(
            result.get("abstention_reason"), "No supporting evidence was selected."
        )
        if spanish:
            reason = REASONS_ES.get(
                result.get("abstention_reason"), "No se seleccionó evidencia suficiente."
            )
        return (
            "**No hay una respuesta respaldada.**\n\n"
            if spanish
            else "**No supported answer.**\n\n"
        ) + reason
    if result["status"] == "CLARIFICATION":
        return result["message"]
    if spanish:
        return (
            "**No se pudo responder de forma segura.**\n\n"
            "La comprobación local de la evidencia no se completó."
        )
    return "**Unable to answer safely.**\n\nThe local evidence check did not complete."


class ChatAdapter:
    def __init__(self, bundle_root=None, receipts_root=None):
        self.bundle = Path(bundle_root or "/app/ragparity")
        self.receipts = Path(receipts_root or "/app/backend/data/ragparity-receipts")
        self.lock = asyncio.Lock()

    def configuration(self) -> dict:
        config = json.loads((self.bundle / "ui-config.json").read_text())
        for name, checksum in config["code_sha256"].items():
            if hashlib.sha256((self.bundle / name).read_bytes()).hexdigest() != checksum:
                raise ValueError("The deployed runtime does not match its installation manifest")
        return config

    def execute(self, question: str, unit: str, token: str, config: dict) -> dict:
        versions = config["versions"]
        models = request("http://127.0.0.1:11445/api/tags")
        digests = {item["name"]: item["digest"] for item in models["models"]}
        if any(digests.get(key) != digest for key, digest in versions["model_digests"].items()):
            raise ValueError("The local model digest differs from the pinned installation")
        refresh_model_catalog(token, versions["generation_model"], app_url="http://127.0.0.1:8080")
        return answer_question(
            question,
            unit,
            token,
            config["uploads"],
            versions["generation_model"],
            app_url="http://127.0.0.1:8080",
        )

    def save_receipt(self, record: dict) -> str:
        self.receipts.mkdir(parents=True, exist_ok=True)
        self.receipts.chmod(0o700)
        identifier = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
        path = self.receipts / (identifier + ".json")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps(record, indent=2) + "\n")
        return identifier

    async def pipe(
        self,
        body: dict,
        __user__=None,
        __request__=None,
        __event_emitter__=None,
        __chat_id__=None,
        __message_id__=None,
        __task__=None,
        __files__=None,
    ):
        config = self.configuration()
        last = next(
            (
                m.get("content", "")
                for m in reversed(body.get("messages", []))
                if m.get("role") == "user"
            ),
            "",
        )
        language = question_language(last) if isinstance(last, str) else "en"
        spanish = language == "es"
        if (__user__ or {}).get("id") != config["owner_id"]:
            return (
                "Este modo está restringido a la cuenta local del piloto."
                if spanish
                else "This document mode is restricted to the local pilot account."
            )
        if __task__:
            if __task__ == "title_generation":
                return json.dumps({"title": "Public documents · RAGParity"})
            return json.dumps({"tags": [], "follow_ups": []})
        question, unit = "", None
        try:
            question = question_text(body, language)
            if __files__:
                raise ChatInputError(
                    "Este modo usa los documentos públicos cargados; "
                    "retira los otros archivos adjuntos."
                    if spanish
                    else "This mode uses the loaded public documents; remove other attachments."
                )
            authorization = __request__.headers.get("authorization", "") if __request__ else ""
            if not authorization.startswith("Bearer "):
                raise ChatInputError(
                    "Vuelve a iniciar sesión antes de usar este modo."
                    if spanish
                    else "Please sign in again before using the document mode."
                )
            token = authorization.removeprefix("Bearer ")
            unit = infer_unit(question)
            if unit is None:
                result = {
                    "status": "CLARIFICATION",
                    "message": (
                        "Nombra un solo sujeto e incluye una unidad de medida, "
                        "como Celsius, km, horas o columnas."
                        if spanish
                        else "Name one subject and include one requested unit "
                        "such as Celsius, km, hours or columns."
                    ),
                }
            else:
                if __event_emitter__:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "Comprobando los documentos públicos…"
                                if spanish
                                else "Checking the public documents…",
                                "done": False,
                            },
                        }
                    )
                async with self.lock:
                    # Run blocking HTTP off-loop so nested retrieval cannot deadlock the server.
                    result = await asyncio.to_thread(self.execute, question, unit, token, config)
        except ChatInputError as exc:
            result = {"status": "CLARIFICATION", "message": str(exc)}
        except Exception as exc:
            result = {"status": "ERROR", "error_type": type(exc).__name__}
        rendered = render_answer(result, config["versions"], language)
        self.save_receipt(
            {
                "schema_version": 1,
                "language": language,
                "chat_id": __chat_id__,
                "message_id": __message_id__,
                "question": question,
                "unit": unit,
                "result": result,
                "rendered_answer": rendered,
                "versions": config["versions"],
                "code_sha256": config["code_sha256"],
            }
        )
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Comprobación documental completada"
                        if spanish
                        else "Document check complete",
                        "done": True,
                    },
                }
            )
        return rendered
