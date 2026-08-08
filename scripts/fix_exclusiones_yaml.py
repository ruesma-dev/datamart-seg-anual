# scripts/fix_exclusiones_yaml.py
"""
================================================================================
CORRECTOR AUTOMÁTICO DE exclude_columns EN tables_sigrid.yaml
================================================================================

PROBLEMA QUE RESUELVE
---------------------
El ETL descubre las columnas por INFORMATION_SCHEMA y descarta las de tipo
texto ilimitado o binario al CREAR la tabla en Postgres (no sabe mapearlas),
pero SÍ las pide en el SELECT si no están en `exclude_columns`. Entonces la
API devuelve una columna de más y el COPY falla:

    psycopg.errors.UndefinedColumn: no existe la columna «X» en la relación «Y»

Ir descubriendo esas columnas de una en una (med, eiotex, eittra…) es
inviable: `dca` tiene 142 columnas y varias son texto.

QUÉ HACE ESTE SCRIPT
--------------------
1. Lee config/tables_sigrid.yaml y saca la lista de tablas declaradas.
2. Pregunta a Sigrid (INFORMATION_SCHEMA) qué columnas de cada tabla son de
   tipo text/ntext/image/xml/varbinary/binary.
3. Fusiona esas columnas con las exclusiones que ya tenías (no quita ninguna).
4. Reescribe el YAML EN SITIO, conservando comentarios, orden y formato:
   solo toca los bloques `exclude_columns:`.
5. Antes de escribir, comprueba que ninguna columna necesaria para los SQL de
   compras/retenciones quede excluida por error, y avisa si eso pasara.

Deja una copia de seguridad `tables_sigrid.yaml.bak` antes de modificar.

USO
---
    python scripts/fix_exclusiones_yaml.py --dry-run   # solo informa
    python scripts/fix_exclusiones_yaml.py             # aplica los cambios
    python scripts/fix_exclusiones_yaml.py --tabla dca # una tabla concreta

Requiere: requests, pyyaml, python-dotenv (opcional).
================================================================================
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


RAIZ = Path(__file__).resolve().parent.parent
YAML_PATH = RAIZ / "config" / "tables_sigrid.yaml"

# Tipos SQL Server que el ETL no puede materializar en Postgres.
TIPOS_PROBLEMATICOS = (
    "text", "ntext", "image", "xml", "varbinary", "binary",
    "geography", "geometry", "sql_variant", "hierarchyid",
)

# Columnas imprescindibles. NUNCA se excluyen aunque Sigrid las declare como
# texto/binario: el ETL las necesita para que funcione el pipeline.
#
# ⚠️ obrparpre.planif es la más crítica de todo el proyecto: es la cadena de
# planificación temporal de la que salen stg.plan_mensual, el mart y el cierre.
# Es de tipo `text` en SQL Server, así que sin esta protección un detector
# automático la excluiría y rompería la planificación entera.
COLUMNAS_PROTEGIDAS: dict[str, list[str]] = {
    # --- pipeline original de seguimiento / cierre ---
    "obrparpre": ["ide", "obride", "paride", "amb", "fas", "can", "pre",
                  "planif", "totinc", "impcoe", "impOcoe"],
    "obrparpar": ["ide", "obride", "padide", "cod", "res", "pos", "tipdes",
                  "unimed", "tcaide"],
    "obrfasamb": ["ide", "obride", "amb", "fas", "plafec", "res", "tex", "fec"],
    "obrfas":    ["ide", "obride", "fasnum", "res", "fec"],
    "con":       ["ide", "tip", "cod", "res", "fec"],
    "obr":       ["ide", "entide", "empide", "cenide", "obrtipide", "obrclaide",
                  "decc", "decp", "deci", "coeind", "suptot",
                  "fecinipre", "fecfinpre", "fecinirea", "fecfinrea", "fecadj"],
    "obrctr":    ["ide", "obride", "coegar", "cobporret", "plaret", "plagar",
                  "fecdevret", "fecinigar", "fecfingar",
                  "fecreaact", "fecreaini", "fecreafir", "fecprefin",
                  "fecpreini", "fecinipla", "fecreafin", "fecreaadj",
                  "fecpreadj", "fecprefir"],
    "cen":       ["ide", "cod", "res"],
    "condir":    ["ide", "conide", "dir", "dir1", "dir2", "dircpo",
                  "munide", "proide", "tel", "ele"],
    "prv":       ["ide", "cif", "raz", "tipsub"],
    "conext":    ["ide", "conide", "cod", "val"],
    "ctr":       ["ide", "obride", "entide", "entcif", "comide",
                  "impbru", "impnet", "totbas", "totiva", "totdoc", "tot"],
    # --- módulos compras / retenciones ---
    "ctrpro":    ["ide", "docide", "proide", "res", "unimed", "paride",
                  "cenide", "can", "pre", "tot", "ivacuo", "canser"],
    "dca":       ["ide", "ctride", "comide", "entide", "entcif", "entref"],
    "dcapro":    ["ide", "docide", "obride", "paride", "proide", "res",
                  "unimed", "cenide", "can", "pre", "tot", "ivacuo",
                  "canfac", "docoritip", "docoricod", "docoriide", "linoriide"],
    "dcf":       ["ide", "entide", "entcif", "entref", "cla"],
    "dcfpro":    ["ide", "docide", "obride", "paride", "proide", "res",
                  "unimed", "cenide", "can", "pre", "tot", "ivacuo",
                  "docoritip", "docoricod", "docoriide", "linoriide"],
    "dcfprodes": ["ide", "docproide"],
    "com":       ["ide", "obride"],
    "cob":       ["ide", "tot", "fecven", "conide", "entide", "padide",
                  "fecrea", "cenide", "retide"],
    "pag":       ["ide", "tot", "fecven", "conide", "entide", "padide",
                  "fecrea", "cenide", "retide"],
    "rec":       ["ide", "cla", "valpor", "valcan", "tipdev", "diavto"],
}

# Ámbito por defecto: SOLO las tablas nuevas de compras y retenciones.
# Las 19 tablas originales llevaban meses funcionando; no se tocan salvo que
# se pida explícitamente con --todas.
TABLAS_NUEVAS = [
    "com", "comlin", "comprv", "ctrpro", "dca", "dcapro",
    "dcf", "dcfpro", "dcfprodes", "cob", "pag", "rec",
]


# =============================================================================
# Config / API
# =============================================================================
def _cargar_env() -> None:
    if load_dotenv is None:
        return
    for c in (RAIZ / ".env", Path.cwd() / ".env"):
        if c.exists():
            load_dotenv(c)
            return


def _env(*nombres: str, default: str | None = None) -> str | None:
    for n in nombres:
        v = os.environ.get(n)
        if v:
            return v
    return default


def cargar_config() -> dict[str, Any]:
    _cargar_env()
    base = _env("SIGRID_API_BASE_URL", "SIGRID_API__BASE_URL", "SIGRID_BASE_URL")
    key = _env("SIGRID_API_FUNCTION_KEY", "SIGRID_API__FUNCTION_KEY",
               "SIGRID_FUNCTION_KEY")
    db = _env("SIGRID_API_DATABASE", "SIGRID_API__DATABASE", default="ruesma")
    if not base or not key:
        print("ERROR: faltan SIGRID_API_BASE_URL / SIGRID_API_FUNCTION_KEY.",
              file=sys.stderr)
        sys.exit(2)
    return {
        "url": base.rstrip("/") + "/api/sql/read",
        "headers": {"x-functions-key": key, "Content-Type": "application/json"},
        "database": db,
    }


def columnas_problematicas(cfg: dict[str, Any], tabla: str) -> list[str]:
    """Columnas de la tabla cuyo tipo el ETL no puede materializar."""
    placeholders = ", ".join("?" for _ in TIPOS_PROBLEMATICOS)
    sql = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = ?
          AND DATA_TYPE IN ({placeholders})
        ORDER BY ORDINAL_POSITION
    """
    body = {
        "database": cfg["database"],
        "sql": sql,
        "parameters": [tabla, *TIPOS_PROBLEMATICOS],
        "timeout_seconds": 60,
        "max_rows": 500,
    }
    r = requests.post(cfg["url"], json=body, headers=cfg["headers"], timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    d = r.json()
    if not d.get("ok", False):
        raise RuntimeError(f"API error: {str(d)[:200]}")
    return [row[0] for row in d["rows"]]


# =============================================================================
# Reescritura quirúrgica del YAML (conserva comentarios y formato)
# =============================================================================
def reescribir_exclusiones(
    texto: str, nuevas: dict[str, list[str]]
) -> tuple[str, list[str]]:
    """
    Sustituye el bloque `exclude_columns:` de cada tabla indicada, dejando
    intacto el resto del archivo (comentarios incluidos).

    Conserva:
      · el ORDEN original de las exclusiones que ya estaban (las nuevas se
        añaden al final), para que el diff sea mínimo;
      · los COMENTARIOS EN LÍNEA de cada exclusión existente
        (p. ej. `- ima    # imagen del concepto, binario pesado`).

    Devuelve (texto_nuevo, avisos).
    """
    lineas = texto.splitlines(keepends=True)
    salida: list[str] = []
    avisos: list[str] = []

    tabla_actual: str | None = None
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        stripped = linea.strip()

        if stripped.startswith("- source_table:"):
            tabla_actual = stripped.split(":", 1)[1].strip()
            salida.append(linea)
            i += 1
            continue

        if (stripped.startswith("exclude_columns:")
                and tabla_actual in nuevas):
            indent = linea[: len(linea) - len(linea.lstrip())]
            # Recorrer el bloque antiguo guardando orden y comentarios
            orden_previo: list[str] = []
            comentarios: dict[str, str] = {}
            i += 1
            while i < len(lineas):
                s = lineas[i].strip()
                if s.startswith("- ") and not s.startswith("- source_table:"):
                    cuerpo = s[2:]
                    if "#" in cuerpo:
                        col, com = cuerpo.split("#", 1)
                        col = col.strip()
                        # Conservar el espaciado original hasta la almohadilla
                        bruto = lineas[i].rstrip("\n")
                        sep = bruto[bruto.index(col) + len(col): bruto.index("#")]
                        comentarios[col] = f"{sep}#{com.rstrip()}"
                    else:
                        col = cuerpo.strip()
                    if col:
                        orden_previo.append(col)
                    i += 1
                    continue
                break

            # Orden final: las que ya estaban (en su orden) + las nuevas
            cols = list(nuevas[tabla_actual])
            finales = [c for c in orden_previo if c in cols]
            finales += [c for c in cols if c not in finales]

            if finales:
                salida.append(f"{indent}exclude_columns:\n")
                for c in finales:
                    salida.append(f"{indent}  - {c}{comentarios.get(c, '')}\n")
            else:
                salida.append(f"{indent}exclude_columns: []\n")
            continue

        salida.append(linea)
        i += 1

    return "".join(salida), avisos


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Corrige exclude_columns en tables_sigrid.yaml consultando "
                    "a Sigrid qué columnas son texto/binario."
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo informa, no modifica el archivo")
    ap.add_argument("--tabla", default=None,
                    help="Procesar solo esta tabla")
    ap.add_argument("--todas", action="store_true",
                    help="Procesar TODAS las tablas del YAML (por defecto solo "
                         "las nuevas de compras/retenciones). Úsalo con cuidado: "
                         "las tablas del pipeline original ya funcionaban.")
    ap.add_argument("--yaml", default=None,
                    help="Ruta alternativa al tables_sigrid.yaml")
    args = ap.parse_args()

    ruta = Path(args.yaml) if args.yaml else YAML_PATH
    if not ruta.exists():
        print(f"ERROR: no encuentro {ruta}", file=sys.stderr)
        sys.exit(2)

    cfg = cargar_config()
    texto = ruta.read_text(encoding="utf-8")
    doc = yaml.safe_load(texto)
    todas_las_tablas = [t["source_table"] for t in doc["tables"]]
    actuales = {t["source_table"]: list(t.get("exclude_columns") or [])
                for t in doc["tables"]}

    if args.tabla:
        if args.tabla not in todas_las_tablas:
            print(f"ERROR: '{args.tabla}' no está en el YAML.", file=sys.stderr)
            sys.exit(2)
        tablas = [args.tabla]
        ambito = f"solo {args.tabla}"
    elif args.todas:
        tablas = todas_las_tablas
        ambito = "TODAS (incluido el pipeline original)"
    else:
        tablas = [t for t in todas_las_tablas if t in TABLAS_NUEVAS]
        ambito = "solo tablas nuevas (compras + retenciones)"

    print("=" * 74)
    print("CORRECTOR DE exclude_columns")
    print("=" * 74)
    print(f"  YAML   : {ruta}")
    print(f"  Sigrid : {cfg['database']}")
    print(f"  Ámbito : {ambito}")
    print(f"  Tablas : {len(tablas)}")
    print()

    nuevas: dict[str, list[str]] = {}
    cambios = 0

    for tabla in tablas:
        try:
            problematicas = columnas_problematicas(cfg, tabla)
        except Exception as e:  # noqa: BLE001
            print(f"  {tabla:<12} [ERROR] {e}")
            continue

        previas = actuales.get(tabla, [])
        protegidas = set(COLUMNAS_PROTEGIDAS.get(tabla, []))

        # PROTECCIÓN REAL: una columna protegida NUNCA se excluye, aunque
        # Sigrid la declare como texto/binario. Se avisa para que se sepa.
        conflicto = protegidas & set(problematicas)
        if conflicto:
            print(f"  {tabla:<12} [PROTEGIDA] {', '.join(sorted(conflicto))} "
                  f"es texto/binario pero el ETL la necesita: NO se excluye")
            problematicas = [c for c in problematicas if c not in protegidas]

        # Unión de lo que ya había + lo detectado (sin quitar nada)
        union = sorted(set(previas) | set(problematicas))
        nuevas[tabla] = union

        anadidas = sorted(set(problematicas) - set(previas))
        sobrantes = sorted(set(previas) - set(problematicas))

        if anadidas:
            cambios += 1
            print(f"  {tabla:<12} +{len(anadidas)} nuevas: {', '.join(anadidas)}")
        else:
            print(f"  {tabla:<12} sin cambios ({len(problematicas)} problemáticas)")
        if sobrantes:
            print(f"  {'':<12}   (se conservan por si acaso: {', '.join(sobrantes)})")

    print()
    if not cambios:
        print("Nada que corregir: el YAML ya excluye todas las columnas "
              "texto/binario.")
        return

    if args.dry_run:
        print(f"DRY-RUN: {cambios} tabla(s) necesitan cambios. "
              f"Relanza sin --dry-run para aplicarlos.")
        return

    # Copia de seguridad
    backup = ruta.with_suffix(ruta.suffix + ".bak")
    shutil.copy2(ruta, backup)
    print(f"Copia de seguridad: {backup}")

    texto_nuevo, avisos = reescribir_exclusiones(texto, nuevas)
    for a in avisos:
        print(f"  [AVISO] {a}")

    # Validar que sigue siendo YAML correcto y no se han perdido tablas
    try:
        doc_nuevo = yaml.safe_load(texto_nuevo)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: el YAML resultante no es válido ({e}). "
              f"No se ha modificado nada.", file=sys.stderr)
        sys.exit(1)

    t_antes = {t["source_table"] for t in doc["tables"]}
    t_despues = {t["source_table"] for t in doc_nuevo["tables"]}
    if t_antes != t_despues:
        print(f"ERROR: se han perdido tablas ({t_antes - t_despues}). "
              f"No se escribe.", file=sys.stderr)
        sys.exit(1)

    ruta.write_text(texto_nuevo, encoding="utf-8")
    print(f"\n{ruta} actualizado. {len(doc_nuevo['tables'])} tablas intactas.")
    print("\nAhora:  python main.py ingest")


if __name__ == "__main__":
    main()
