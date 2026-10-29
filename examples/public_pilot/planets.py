"""Prepare an independently pinned, attributed planetary reference corpus."""

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from corpus import HERE, reference_document, verified_download

METRICS = {
    "diameter": ("Diameter (km)", "Equatorial diameter", "km"),
    "rotation-period": ("Rotation Period (hours)", "Sidereal rotation period", "hours"),
    "length-of-day": ("Length of Day (hours)", "Solar length of day", "hours"),
    "orbital-period": ("Orbital Period (days)", "Tropical orbital period", "days"),
    "mean-temperature": ("Mean Temperature (C)", "Mean temperature", "C"),
}
PLANETS = ("MERCURY", "VENUS", "EARTH", "MARS", "JUPITER", "SATURN", "URANUS", "NEPTUNE")


class PlanetTable(HTMLParser):
    """Read header positions, including the Moon column between Earth and Mars."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.cells = None
        self.parts = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag in ("td", "th") and self.cells is not None:
            self.parts = []

    def handle_data(self, data):
        if self.parts is not None:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.parts is not None and self.cells is not None:
            self.cells.append(" ".join("".join(self.parts).split()))
            self.parts = None
        elif tag == "tr" and self.cells:
            self.rows.append(self.cells)
            self.cells = None

    def values(self) -> dict:
        header = next(row for row in self.rows if "MERCURY" in row and "NEPTUNE" in row)
        result = {}
        for metric, (label, _, _) in METRICS.items():
            row = next(row for row in self.rows if row[0] == label)
            if len(row) != len(header):
                raise ValueError("Planetary table dimensions changed")
            result[metric] = {}
            for planet in PLANETS:
                raw = row[header.index(planet)]
                # Group separators are removed only in the authoritative table parser.
                if re.fullmatch(r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", raw) is None:
                    raise ValueError("Unexpected planetary reference number")
                result[metric][planet.lower()] = raw.replace(",", "")
        return result


def render_planet(planet: str, values: dict, config: dict) -> str:
    lines = [
        f"Planetary reference excerpt: {planet.title()}",
        f"Document ID: nasa-{planet}",
        f"Source revision (SHA-256): {config['revision']}",
        f"Source material: {config['files']['facts.html']['url']}",
        f"Definitions: {config['files']['notes.html']['url']}",
        "Source: NASA/NSSDCA Planetary Fact Sheet - Metric, updated 18 March 2025.",
        "These are rounded values from this fixed source edition, not live measurements.",
        "",
    ]
    for metric, (_, label, unit) in METRICS.items():
        lines.append(f"Metric ID: {metric}; {label}: {values[metric][planet]} {unit}.")
    lines.extend(
        [
            "",
            "Diameter is measured at the equator. Rotation period is relative to fixed stars;",
            "a negative sign indicates retrograde rotation. Solar length of day is a different",
            "measurement. Orbital period uses Earth days, from equinox to equinox.",
            "Mean temperature is a whole-surface average, or at one bar for gas giants;",
            "it is not the temperature of every location or the current weather.",
            "",
            "Numerical source material credited to NASA/NSSDCA. Excerpt and model responses",
            "are produced by this pilot; NASA has not reviewed or endorsed them.",
            "No NASA logos, imagery or third-party media are included.",
            "Usage guidance: https://www.nasa.gov/nasa-brand-center/images-and-media/",
        ]
    )
    return "\n".join(lines) + "\n"


def prepare_planets(destination: Path, config: dict) -> list[dict]:
    revision = hashlib.sha256(json.dumps(config["files"], sort_keys=True).encode()).hexdigest()
    if config["revision"] != revision:
        raise ValueError("Planetary revision does not match the pinned source files")
    for name, spec in config["files"].items():
        verified_download(destination / "nasa" / name, spec["url"], spec["sha256"])
    parser = PlanetTable()
    parser.feed((destination / "nasa/facts.html").read_text())
    values = parser.values()
    for question in json.loads((HERE / "nasa_questions.json").read_text()):
        if question.get("supported", True):
            if values[question["metric"]][question["planet"]] != question["value"]:
                raise ValueError("Planetary source differs from the reviewed reference")
            if METRICS[question["metric"]][2] != question["unit"]:
                raise ValueError("Planetary reference unit mismatch")
    result = []
    for planet in (name.lower() for name in PLANETS):
        body = render_planet(planet, values, config)
        filename = f"rns-nasa-{planet}--{config['revision']}.txt"
        document = reference_document(
            body,
            {
                "id": f"nasa-{planet}",
                "source_id": "nasa-planetary",
                "collection": config["collection"],
            },
            filename,
            config["revision"],
        )
        (destination / filename).write_text(body, encoding="utf-8")
        result.append(document)
    return result
