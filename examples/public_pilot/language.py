"""Deterministic bilingual query vocabulary for the two fixed public-source adapters.

This translates domain terms, never answers or numbers. Source applicability still comes
from retrieved headings. Unknown wording is retained; this is not a general translator.
"""

import re
import unicodedata


def folded(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.casefold())
        if unicodedata.category(char) != "Mn"
    )


def question_language(text: str) -> str:
    spanish = re.search(
        r"¿|\b(?:cual|cuales|cuanto|cuantos|cuantas|que|segun|temperatura|diametro|"
        r"limite|poblacion|marte|tierra|mercurio|saturno|urano|neptuno|en|"
        r"horas|dias|columnas|tamano|longitud|ahora|hoy|actualmente)\b",
        folded(text),
    )
    return "es" if spanish or re.search(r"[¿ñáéíóúü]", text.casefold()) else "en"


# Longest phrases run first. No question IDs, document IDs, reference values or support
# flags occur here. Entity translations do not assert that an entity is in the corpus.
VOCABULARY = {
    "respecto a las estrellas fijas": "relative to fixed stars",
    "dia solar": "solar day",
    "dia sideral": "sidereal day",
    "rotacion sideral": "sidereal rotation",
    "rotacion": "rotation",
    "temperatura promedio": "average temperature",
    "temperatura": "temperature",
    "diametro": "diameter",
    "radio": "radius",
    "circunferencia": "circumference",
    "promedio": "average",
    "minima": "minimum",
    "minimo": "minimum",
    "mas alta": "highest",
    "mas baja": "lowest",
    "en vez de": "instead of",
    "sin incluir": "not including",
    "mitad": "half",
    "doble": "double",
    "calcula": "calculate",
    "calcular": "calculate",
    "diferencia": "difference",
    "suma": "sum",
    "sin volver a compilar": "without recompiling",
    "sin recompilar": "without recompiling",
    "conjunto de resultados": "result set",
    "bases de datos": "databases",
    "base de datos": "database",
    "tamano de tupla": "tuple size",
    "tamano de bloque": "block size",
    "claves de particion": "partition keys",
    "argumentos de funcion": "function arguments",
    "parametros de consulta": "query parameters",
    "longitud del identificador": "identifier length",
    "periodo de rotacion sideral": "sidereal rotation period",
    "periodo sideral de rotacion": "sidereal rotation period",
    "periodo orbital tropical": "tropical orbital period",
    "duracion solar del dia": "solar length of day",
    "duracion del dia solar": "solar length of day",
    "temperatura media de toda la superficie": "whole-surface mean temperature",
    "temperatura media superficial": "whole-surface mean temperature",
    "temperatura media": "mean temperature",
    "diametro ecuatorial": "equatorial diameter",
    "grados centigrados": "degrees Celsius",
    "grados celsius": "degrees Celsius",
    "grados c": "degrees C",
    "por defecto": "default",
    "en lugar de": "rather than",
    "del momento": "current",
    "en estos momentos": "currently",
    "se midio": "measured",
    "al mediodia": "at noon",
    "a medianoche": "at midnight",
    "en tiempo real": "real time",
    "a fecha de": "as of",
    "ficha planetaria": "planetary fact sheet",
    "con signo": "signed",
    "sujeto a": "subject to",
    "cual es": "what is",
    "cuantas": "how many",
    "cuantos": "how many",
    "cuanto": "how much",
    "cual": "what",
    "que": "what",
    "numero": "number",
    "limites": "limits",
    "limite": "limit",
    "superior": "upper",
    "maximo": "maximum",
    "maxima": "maximum",
    "predeterminado": "default",
    "predeterminada": "default",
    "relaciones": "relations",
    "relacion": "relation",
    "columnas": "columns",
    "tabla": "table",
    "indice": "index",
    "campo": "field",
    "tamano": "size",
    "longitud": "length",
    "identificador": "identifier",
    "parametros": "parameters",
    "argumentos": "arguments",
    "claves": "keys",
    "horas": "hours",
    "dias": "days",
    "terrestres": "Earth",
    "kilometros": "kilometers",
    "poblacion": "population",
    "personas": "people",
    "humana": "human",
    "mercurio": "Mercury",
    "tierra": "Earth",
    "marte": "Mars",
    "jupiter": "Jupiter",
    "saturno": "Saturn",
    "urano": "Uranus",
    "neptuno": "Neptune",
    "sol": "Sun",
    "luna": "Moon",
    "pluton": "Pluto",
    "titan": "Titan",
    "ecuador": "equator",
    "polos": "poles",
    "polo": "pole",
    "ciudad": "city",
    "ciudades": "cities",
    "crater": "crater",
    "crateres": "craters",
    "estacion": "station",
    "estaciones": "stations",
    "latitud": "latitude",
    "longitud geografica": "longitude",
    "lugar de aterrizaje": "landing site",
    "ahora": "now",
    "hoy": "today",
    "ayer": "yesterday",
    "manana": "tomorrow",
    "actualmente": "currently",
    "actual": "current",
    "ultima": "latest",
    "ultimo": "latest",
    "medida": "measured",
    "medido": "measured",
    "registrada": "recorded",
    "registrado": "recorded",
    "observada": "observed",
    "observado": "observed",
    "mediodia": "noon",
    "medianoche": "midnight",
    "enero": "January",
    "febrero": "February",
    "marzo": "March",
    "abril": "April",
    "mayo": "May",
    "junio": "June",
    "julio": "July",
    "agosto": "August",
    "septiembre": "September",
    "octubre": "October",
    "noviembre": "November",
    "diciembre": "December",
    "en": "in",
    "por": "per",
    "de": "of",
    "del": "of",
    "para": "for",
    "con": "with",
    "y": "and",
    "o": "or",
    "es": "is",
    "son": "are",
    "segun": "according to",
    "indica": "lists",
    "indicada": "listed",
    "indicado": "listed",
    "consta": "listed",
    "figura": "listed",
}
_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(key) for key in sorted(VOCABULARY, key=len, reverse=True))
    + r")(?!\w)"
)


def normalize_question(question: str) -> tuple[str, str]:
    language = question_language(question)
    if language == "en":
        return language, question
    normalized = _PATTERN.sub(lambda match: VOCABULARY[match[0]], folded(question))
    # Retain unknown words and every number; neither unknown entities nor scope qualifiers
    # are removed to make a question appear answerable.
    return language, normalized.replace("¿", "")


SUBJECTS_ES = {
    "Mercury": "Mercurio",
    "Earth": "Tierra",
    "Mars": "Marte",
    "Jupiter": "Júpiter",
    "Saturn": "Saturno",
    "Uranus": "Urano",
    "Neptune": "Neptuno",
}
LABELS_ES = {
    "Equatorial diameter": "Diámetro ecuatorial",
    "Sidereal rotation period": "Período de rotación sideral",
    "Solar length of day": "Duración del día solar",
    "Tropical orbital period": "Período orbital tropical",
    "Mean temperature": "Temperatura media",
    "number of databases": "Número de bases de datos",
    "relations per database": "Relaciones por base de datos",
    "relation size": "Tamaño de una relación",
    "columns per table": "Columnas por tabla",
    "columns in a result set": "Columnas en un conjunto de resultados",
    "field size": "Tamaño de un campo",
    "columns per index": "Columnas por índice",
    "partition keys": "Claves de partición",
    "identifier length": "Longitud del identificador",
    "function arguments": "Argumentos de función",
    "query parameters": "Parámetros de consulta",
}
UNITS_ES = {
    "C": "°C",
    "hours": "horas",
    "days": "días",
    "databases": "bases de datos",
    "relations": "relaciones",
    "columns": "columnas",
    "keys": "claves",
    "arguments": "argumentos",
    "parameters": "parámetros",
}
