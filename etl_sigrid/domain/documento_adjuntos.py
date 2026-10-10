# etl_sigrid/domain/documento_adjuntos.py
"""
El ÍNDICE DE DOCUMENTOS ADJUNTOS de compras (F-090): qué ficheros cuelgan de
cada factura, contrato, comparativo, oferta y albarán en la pestaña «Gráficos
asociados» de Sigrid.

LA FUENTE SON DOS TABLAS DE SIGRID: `rcg`, el enlace documento <-> gráfico
(`rcg.con` el documento, `rcg.gra` el gráfico), y `gra`, el gráfico: nombre del
fichero (`nom`), fecha de alta (`fec`, AAAAMMDD), login de quien lo subió
(`usu`) y `cod`, la clave con la que la base DOCUMENTAL `ruesma_rep` guarda el
binario. El binario NO entra en el datamart: lo sirve `sigrid-api` con
`POST /api/documents/read` (`id_column` `cod`). Mediciones, en solo lectura el
2026-10-09: `progress/spec_F-090.md`.

LA REGLA LA EJECUTA SQL (`sql/compras/14_documento_adjuntos.sql`) y la ingesta
la filtra en origen (`config/tables_sigrid.yaml`). Aquí está escrita **una sola
vez** como oráculo puro: las familias, las extensiones de cada clase y el
literal de los dos filtros. `tests/test_f090_ingesta_sql.py` comprueba que el
YAML y el SQL llevan LOS MISMOS. Mismo patrón que `domain/documento_procesos.py`
(F-085).

LA CLASE DE FICHERO SALE DE LA EXTENSIÓN, no de la clase de gráfico de Sigrid
(`gra.gratipide`, catálogo `auxgra`): está a 0 en el 100 % de los enlaces de
compras y su catálogo es de RR. HH. (D4).

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from typing import Final

#: Las familias de documento (`con.tip`) cuyos adjuntos se indexan y su nombre
#: publicado (D1 del humano, 2026-10-09: las cinco de compras, 199.042 enlaces).
#: ÚNICA FUENTE: el `IN` de los dos filtros de ingesta y el `IN` y el `CASE`
#: del SQL tienen que llevar exactamente estas parejas. Fuera, a propósito, las
#: de personal (43 empleados, 306 nóminas) y posventa (708): D2.
FAMILIAS_ADJUNTOS: Final[dict[int, str]] = {
    15: "FACTURA",
    44: "CONTRATO",
    46: "COMPARATIVO",
    12: "OFERTA",
    14: "ALBARAN",
}

#: Las extensiones de cada clase de fichero. Una extensión vive en UNA clase.
EXTENSIONES_POR_CLASE: Final[dict[str, frozenset[str]]] = {
    "PDF": frozenset({"pdf"}),
    "EXCEL": frozenset({"xls", "xlsx", "xlsm", "xlsb", "csv"}),
    "WORD": frozenset({"doc", "docx", "rtf", "odt"}),
    "CORREO": frozenset({"msg", "eml"}),
    "IMAGEN": frozenset({"jpg", "jpeg", "png", "tif", "tiff", "gif", "bmp"}),
}

#: Extensión que no es de ninguna clase conocida.
CLASE_OTRO: Final[str] = "OTRO"
#: Nombre nulo, vacío, sin punto o acabado en punto.
CLASE_SIN_EXTENSION: Final[str] = "SIN_EXTENSION"

#: Columnas de `gra` que NO se ingieren: `ima` y `pul` son binario (71 filas,
#: 12,8 MB en `ima`; `pul` vacía) y `tex` y `cam` texto ilimitado que no sirve
#: al índice (`tex` en 370 filas, `cam` vacía).
COLUMNAS_EXCLUIDAS_GRA: Final[frozenset[str]] = frozenset({"ima", "pul", "tex", "cam"})

#: El sufijo tras el ÚLTIMO punto, sin puntos ni espacios, al final del nombre.
#: Es la misma expresión que `14_documento_adjuntos.sql`
#: (`substring(btrim(g.nom) from '\.([^.\s]+)$')`); `\Z` y no `$` para que un
#: salto de línea final no case, igual que en Postgres.
_RE_EXTENSION: Final[re.Pattern[str]] = re.compile(r"\.([^.\s]+)\Z")


def extension(nombre: str | None) -> str | None:
    """La extensión del fichero, en minúsculas, o None si no la tiene (R8).

    Recorta los espacios de los extremos (como `btrim` en el SQL) y toma lo que
    hay tras el ÚLTIMO punto. None si el nombre es nulo, vacío, no tiene punto,
    acaba en punto o lo de tras el punto lleva espacios.
    """
    if nombre is None:
        return None
    casa = _RE_EXTENSION.search(nombre.strip(" "))
    return casa.group(1).lower() if casa else None


def clase_fichero(nombre: str | None) -> str:
    """La clase del fichero por su extensión (R9)."""
    ext = extension(nombre)
    if ext is None:
        return CLASE_SIN_EXTENSION
    for clase, extensiones in EXTENSIONES_POR_CLASE.items():
        if ext in extensiones:
            return clase
    return CLASE_OTRO


def lista_familias_sql() -> str:
    """Las familias para un `IN (...)`, ordenadas: el literal es determinista."""
    return ", ".join(str(tip) for tip in sorted(FAMILIAS_ADJUNTOS))


def filtro_rcg() -> str:
    """El `where` exacto de `rcg` en `tables_sigrid.yaml` (R1, R3)."""
    return f"con IN (SELECT ide FROM dbo.con WHERE tip IN ({lista_familias_sql()}))"


def filtro_gra() -> str:
    """El `where` exacto de `gra` en `tables_sigrid.yaml` (R2, R3)."""
    return (
        "ide IN (SELECT r.gra FROM dbo.rcg r JOIN dbo.con c ON c.ide = r.con "
        f"WHERE c.tip IN ({lista_familias_sql()}))"
    )
