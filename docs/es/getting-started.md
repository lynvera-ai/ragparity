# Guía rápida de RAGParity 0.2.0b1

RAGParity compara los metadatos de una fuente con los de un índice RAG y valida
afirmaciones numéricas estructuradas. La beta incluye una biblioteca Python y una
herramienta de consola. Los chats son ejemplos experimentales.

El ejemplo inicial utiliza datos inventados. Necesita Python 3.12 o posterior e internet
para instalar dependencias gratuitas. Después funciona localmente sin modelos, base de
datos, cuenta ni suscripción. Las guías de referencia completas están en inglés.

## Instalación desde GitHub

En macOS o Linux:

```bash
git clone --branch main --single-branch https://github.com/lynvera-ai/ragparity.git
cd ragparity
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install .
```

En Windows PowerShell, después de clonar y entrar en el repositorio:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade 'pip>=26.2,<27'
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m lynvera_ragparity version
```

La instalación limpia de esta preparación se comprobó en macOS ARM64 con Python 3.12.9.
Windows y una instalación limpia nueva en Linux siguen pendientes de confirmación.
Consulta los [métodos de instalación](../getting-started.md#choose-an-installation-method)
si tienes un wheel o un archivo fuente revisado.

## Primera comprobación

Con el entorno activo y desde una carpeta de trabajo nueva:

```bash
ragparity version
ragparity init
ragparity check --output report.json
ragparity report --input report.json --output report.html
```

En PowerShell puedes usar la ruta completa del ejecutable del entorno, o ejecutar
`python -m lynvera_ragparity` con ese mismo Python. La versión esperada es `0.2.0b1`.
La comprobación inicial devuelve:

```text
PASS: source=1 index=1 comparisons=1
RECORD_SYNCED: 1
```

Abre `report.html` en un navegador. No necesita servidor ni recursos externos.
`init` conserva los archivos existentes; usa otro nombre si ya tienes configuración.

En `ragparity.toml`, cambia solo `source_version` dentro de `[[index.records]]` de
`"1"` a `"2"`. Repite la comprobación: debe devolver `FAIL`, código 1, y
`VERSION_MISMATCH: 1`. Es una diferencia detectada, no un error de instalación.

| Resultado | Código | Qué significa |
| --- | ---: | --- |
| PASS | 0 | La evidencia suministrada coincide bajo las reglas configuradas. |
| FAIL | 1 | Se encontró al menos una inconsistencia determinista. |
| ERROR | 2 | Un problema de configuración, acceso o ejecución impidió completar la comprobación. |
| INCONCLUSIVE | 3 | Falta evidencia verificable; una revisión vacía también es inconclusa. |

## Conectar una aplicación

Empieza con una muestra pequeña de metadatos y resultados esperados conocidos. Para
PostgreSQL o pgvector instala el extra `postgres` y utiliza una cuenta con permisos
de solo lectura. Las credenciales van en variables de entorno, no en TOML ni en Git.
Sigue el [ejemplo de base de datos](../../examples/postgresql_pgvector/README.md) o la
[guía de integración Python](../python-api.md).

PASS no certifica una respuesta completa del chat ni la corrección de los embeddings.
El piloto experimental de Haystack conserva 22 aciertos y 24 fallos de 46 preguntas.
La aceptación por usuarios independientes sigue pendiente.

## Ayuda y próximos pasos

Consulta [diagnóstico y preguntas frecuentes](../troubleshooting.md),
[actualización y desinstalación](../maintenance.md) y
[el formulario de revisión externa](../beta-feedback.md). Los informes pueden contener
identificadores y evidencia privados; utiliza `--redact` antes de compartirlos.

[Índice de documentación](../README.md). [English](../getting-started.md).
