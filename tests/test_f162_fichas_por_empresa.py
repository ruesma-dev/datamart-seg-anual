# tests/test_f162_fichas_por_empresa.py
"""
F-162 · El seguimiento lleva TODAS las fichas de obra, cada una con su empresa,
y marca la ficha por defecto de cada código.

Modelo del humano (2026-11-11): «Debes leer los proyectos en ambas empresas. No
tener que elegir: cada uno con su propia empresa, sin cruces entre empresas.»
Y el criterio de la ficha por defecto: «en caso de duda, Construcciones Ruesma
por delante, salvo que se diga lo contrario; los datos deciden antes que la
duda». `conext` 15 fuera del criterio (D2).

Ningún test toca red ni base de datos (convención del proyecto): se fijan sobre
el TEXTO del SQL, del diccionario y de los documentos las decisiones de la spec
(`specs/F-162-obra-duplicada-ruesma/`). El SQL contra un PostgreSQL desechable
va en `tests/test_f162_sandbox.py` (con `F162_SANDBOX_DSN`).

Helpers COPIADOS de `tests/test_f102_obra_principal.py` y no importados: si
alguien borra aquel fichero, estos guardas siguen en pie.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = Path("C:/Users/pgris/PycharmProjects/azure-apps/datamart_seg_anual.md")

RUTA_DDL = DIR_SQL / "stg" / "01_ddl.sql"
RUTA_STG_OBRAS = DIR_SQL / "stg" / "03_obras.sql"
RUTA_MAESTRO_OBRAS = DIR_SQL / "maestro" / "01_obras.sql"
RUTA_MAESTRO_SETUP = DIR_SQL / "maestro" / "00_setup.sql"
RUTA_DIM_OBRA = DIR_SQL / "mart" / "05_views_powerbi.sql"
RUTA_CABECERA = DIR_SQL / "cierre" / "05_views_cabecera.sql"
RUTA_EXCEPCIONES = RAIZ / "config" / "cobertura_excepciones.yaml"

#: Las tres columnas nuevas de `stg.obras`, AL FINAL y en este orden (R3).
COLUMNAS_NUEVAS = ("empresa_id", "clave_obra", "es_por_defecto")

#: Las columnas de `stg.obras` antes de F-162: ninguna cambia (R3).
COLUMNAS_STG_ANTES = ("obra_id", "codigo_obra", "nombre_obra", "activa", "_built_at")

#: La lista cerrada de códigos administrativos de `03_obras.sql`, sin cambios (R1).
CODIGOS_ADMINISTRATIVOS = (
    "0001", "0002", "0003", "0004", "0005",
    "CM", "CP", "GG", "VAR", "POSTV", "POSTV2",
    "BD", "BD1", "BD2", "BDS",
    "BDDIAMAD", "BDDIASUR", "BDDIANORTE", "BDDIAGRANADA",
    "GGD", "GINT", "OT",
)

#: Las columnas de `maestro.obras` antes de F-162 (F-073 + F-102).
COLUMNAS_MAESTRO_ANTES = (
    "obra_id", "codigo_obra", "nombre_obra", "estado_id", "fecha_alta",
    "fecha_baja", "es_activa", "cliente_id", "codigo_cliente", "nombre_cliente",
    "estado", "dir1", "dir2", "codigo_postal", "direccion_completa",
    "municipio_id", "municipio", "provincia_id", "provincia",
    "tiene_presupuesto", "tiene_seguimiento",
    "empresa_id", "nombre_empresa", "clave_obra", "num_fichas_codigo",
    "es_ficha_principal", "obra_principal_id",
)


# ---------------------------------------------------------------------------
# Helpers de texto
# ---------------------------------------------------------------------------


@cache
def _leer(ruta: Path) -> str:
    assert ruta.exists(), f"no existe {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto EJECUTABLE: sin las líneas `--` ni los comentarios de final de línea."""
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("--"):
            continue
        lineas.append(re.sub(r"\s--\s.*$", "", linea))
    return "\n".join(lineas)


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _troceado_en_profundidad_cero(texto: str, separador: str) -> list[str]:
    piezas: list[str] = []
    actual: list[str] = []
    profundidad = 0
    i = 0
    while i < len(texto):
        caracter = texto[i]
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if profundidad == 0 and texto.startswith(separador, i):
            piezas.append("".join(actual))
            actual = []
            i += len(separador)
            continue
        actual.append(caracter)
        i += 1
    piezas.append("".join(actual))
    return piezas


def _nivel_cero(texto: str) -> str:
    salida: list[str] = []
    profundidad = 0
    for caracter in texto:
        if caracter == "(":
            profundidad += 1
            continue
        if caracter == ")":
            profundidad -= 1
            continue
        if profundidad == 0:
            salida.append(caracter)
    return "".join(salida)


def _sentencia_vista(ruta: Path, marca: str) -> str:
    """La sentencia que empieza por `marca` (`CREATE ... VIEW x AS `), hasta su `;`."""
    compacto = _compacto(_leer(ruta))
    assert marca in compacto, f"{ruta.name} no contiene «{marca}»"
    resto = compacto[compacto.index(marca) + len(marca):]
    return _troceado_en_profundidad_cero(resto, ";")[0]


def _columnas_select(cuerpo: str) -> list[str]:
    """Lo que EXPONE el SELECT de profundidad cero de `cuerpo`, en orden."""
    cuerpo = " " + cuerpo
    seleccion = _troceado_en_profundidad_cero(cuerpo, " SELECT ")[-1]
    seleccion = _troceado_en_profundidad_cero(seleccion, " FROM ")[0]
    nombres: list[str] = []
    for pieza in _troceado_en_profundidad_cero(seleccion, ","):
        pieza = pieza.strip()
        if not pieza:
            continue
        if " AS " in pieza:
            nombres.append(pieza.rsplit(" AS ", 1)[1].strip())
        else:
            nombres.append(pieza.rsplit(".", 1)[-1].strip())
    return nombres


def _normalizado(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def _plano(texto: str) -> str:
    return " ".join(str(texto).split())


@cache
def _yaml(fichero: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / fichero).read_text(encoding="utf-8"))


def _ficha(nombre: str) -> dict:
    esquema, objeto = nombre.split(".")
    objetos = _yaml(f"{esquema}.yaml")["objetos"]
    assert objeto in objetos, f"no hay ficha de {nombre}"
    return objetos[objeto]


def _texto(valor: object) -> str:
    if isinstance(valor, dict):
        return " ".join(_texto(v) for v in valor.values())
    if isinstance(valor, list):
        return " ".join(_texto(v) for v in valor)
    return "" if valor is None else str(valor)


def _regla(codigo: str) -> dict:
    reglas = {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}
    assert codigo in reglas, f"no está la regla {codigo}"
    return reglas[codigo]


def _pregunta(identificador: str) -> dict:
    preguntas = {p["id"]: p for p in _yaml("00_global.yaml")["preguntas_aceptacion"]}
    assert identificador in preguntas, f"no está la pregunta {identificador}"
    return preguntas[identificador]


# ---------------------------------------------------------------------------
# El `03_obras.sql`: sus CTE y su SELECT final
# ---------------------------------------------------------------------------


def _insert_obras() -> str:
    """El `INSERT INTO stg.obras ...` compacto, hasta su `;`."""
    return _sentencia_vista(RUTA_STG_OBRAS, "INSERT INTO stg.obras ")


def _entre_parentesis(texto: str, inicio: int) -> str:
    """Lo que hay desde `inicio` (justo detrás de un `(`) hasta su `)` pareja."""
    profundidad = 1
    i = inicio
    while profundidad:
        if texto[i] == "(":
            profundidad += 1
        elif texto[i] == ")":
            profundidad -= 1
        i += 1
    return texto[inicio:i - 1].strip()


def _cte(nombre: str) -> str:
    """El cuerpo de la CTE `nombre` (lo que va entre sus paréntesis)."""
    insert = _insert_obras()
    marca = re.search(rf"\b{nombre} AS \(", insert)
    assert marca, f"03_obras.sql no tiene la CTE «{nombre}»"
    return _entre_parentesis(insert, marca.end())


def _select_final() -> str:
    """El SELECT de profundidad cero que sigue a las CTE."""
    insert = _insert_obras()
    return " SELECT " + _troceado_en_profundidad_cero(" " + insert, " SELECT ")[-1]


def _condiciones_de_fichas() -> list[str]:
    where = _troceado_en_profundidad_cero(_cte("fichas"), " WHERE ")
    assert len(where) == 2, "la CTE `fichas` tiene un único WHERE"
    return [c.strip() for c in _troceado_en_profundidad_cero(where[1], " AND ")]


# ===========================================================================
# R1-R2 · `stg.obras`: una fila por ficha, sin desempate y sin filtro nuevo
# ===========================================================================


def test_f162_r1_sin_desempate() -> None:
    ejecutable = _compacto(_leer(RUTA_STG_OBRAS))
    assert "rn = 1" not in ejecutable, "stg.obras ya no se queda con una ficha (R1)"
    assert "DISTINCT ON" not in ejecutable.upper(), "ni un desempate por DISTINCT ON (R1)"
    assert " WHERE " not in _nivel_cero(_select_final()), (
        "el SELECT final no filtra: todas las fichas de `fichas` entran (R1)"
    )


def test_f162_r1_los_filtros_de_hoy_y_ninguno_mas() -> None:
    condiciones = _condiciones_de_fichas()
    assert len(condiciones) == 4, f"cuatro filtros, los de hoy (R1): {condiciones}"
    lista = condiciones[0]
    assert lista.startswith("con.cod NOT IN (")
    codigos = tuple(re.findall(r"'([^']*)'", lista))
    assert codigos == CODIGOS_ADMINISTRATIVOS, "la lista cerrada no cambia (R1)"
    assert condiciones[1:] == [
        "con.cod !~ '[0-9]{5,}'",
        "con.cod IS NOT NULL",
        "length(trim(con.cod)) > 0",
    ]


def test_f162_r1_lee_obr_unida_a_con() -> None:
    assert "FROM raw.obr obr JOIN raw.con con ON con.ide = obr.ide" in _cte("fichas")


def test_f162_r2_cada_ficha_sale_con_su_empresa() -> None:
    final = _select_final()
    assert re.search(r"FROM fichas f LEFT JOIN lineas l ON l\.obride = f\.obra_id\s*$", final), (
        "el SELECT final lee TODAS las fichas; las líneas por LEFT JOIN (R2)"
    )
    fichas = _cte("fichas")
    assert "con.emp AS empresa_id" in fichas
    assert "con.emp::text || '-' || con.cod AS clave_obra" in fichas, (
        "clave_obra = '<empresa>-<codigo>', como maestro.v_obra_fichas (R3)"
    )


# ===========================================================================
# R3 · DDL, migración e INSERT
# ===========================================================================


def _create_table_obras() -> list[tuple[str, str]]:
    compacto = _compacto(_leer(RUTA_DDL))
    marca = "CREATE TABLE IF NOT EXISTS stg.obras ("
    assert marca in compacto
    cuerpo = _entre_parentesis(compacto, compacto.index(marca) + len(marca))
    columnas = []
    for pieza in _troceado_en_profundidad_cero(cuerpo, ","):
        nombre, _, tipo = pieza.strip().partition(" ")
        columnas.append((nombre, " ".join(tipo.split())))
    return columnas


def test_f162_r3_create_table_con_las_tres_al_final() -> None:
    columnas = _create_table_obras()
    nombres = [n for n, _ in columnas]
    assert nombres == list(COLUMNAS_STG_ANTES + COLUMNAS_NUEVAS), nombres
    tipos = dict(columnas)
    assert tipos["empresa_id"] == "INTEGER NULL"
    assert tipos["clave_obra"] == "VARCHAR(40) NULL"
    assert tipos["es_por_defecto"] == "BOOLEAN NOT NULL DEFAULT FALSE"
    assert tipos["obra_id"] == "BIGINT PRIMARY KEY", "la clave no cambia (R4)"
    assert tipos["codigo_obra"] == "VARCHAR(24)"


def test_f162_r3_la_migracion_las_anade_en_el_mismo_orden() -> None:
    ejecutable = _compacto(_leer(RUTA_DDL))
    altas = re.findall(r"ALTER TABLE stg\.obras ADD COLUMN (\w+) ([^;]+);", ejecutable)
    assert [n for n, _ in altas] == list(COLUMNAS_NUEVAS), altas
    tipos = {n: t.strip() for n, t in altas}
    assert tipos["empresa_id"] == "INTEGER NULL"
    assert tipos["clave_obra"] == "VARCHAR(40) NULL"
    assert tipos["es_por_defecto"] == "BOOLEAN NOT NULL DEFAULT FALSE"
    for columna in COLUMNAS_NUEVAS:
        assert re.search(
            rf"IF NOT EXISTS \( SELECT 1 FROM information_schema\.columns WHERE "
            rf"table_schema = 'stg' AND table_name = 'obras' AND column_name = '{columna}' \) "
            rf"THEN ALTER TABLE stg\.obras ADD COLUMN {columna} ",
            ejecutable,
        ), f"la migración de {columna} es idempotente (R3)"


def test_f162_r3_la_migracion_va_dentro_de_un_do() -> None:
    ejecutable = _compacto(_leer(RUTA_DDL))
    posicion = ejecutable.index("ALTER TABLE stg.obras ADD COLUMN empresa_id")
    antes = ejecutable[:posicion]
    assert antes.rfind("DO $$") > antes.rfind("END $$;"), "el ALTER va dentro de un bloque DO"


def test_f162_r3_indice_por_empresa_y_codigo_tras_la_migracion() -> None:
    ejecutable = _compacto(_leer(RUTA_DDL))
    indice = (
        "CREATE INDEX IF NOT EXISTS idx_obras_empresa_codigo "
        "ON stg.obras (empresa_id, codigo_obra);"
    )
    assert indice in ejecutable
    assert ejecutable.index(indice) > ejecutable.index(
        "ALTER TABLE stg.obras ADD COLUMN es_por_defecto"
    ), "en Azure la columna existe solo tras la migración"


def test_f162_r3_el_insert_nombra_sus_siete_columnas() -> None:
    insert = _insert_obras()
    assert insert.startswith(
        "(obra_id, codigo_obra, nombre_obra, activa, empresa_id, clave_obra, es_por_defecto) "
    ), "INSERT INTO stg.obras con sus siete columnas nombradas (R3)"
    assert _columnas_select(_select_final()) == [
        "obra_id", "codigo_obra", "nombre_obra", "activa", "empresa_id", "clave_obra",
        "es_por_defecto",
    ]


# ===========================================================================
# R4 · las claves
# ===========================================================================


def test_f162_r4_clave_de_negocio_y_alternativas() -> None:
    ficha = _ficha("stg.obras")
    assert ficha["clave_negocio"] == ["obra_id"]
    assert ficha["claves_alternativas"] == [["clave_obra"], ["empresa_id", "codigo_obra"]]
    for columna in COLUMNAS_NUEVAS:
        assert columna in ficha["columnas"], f"la ficha documenta {columna} (R4)"


# ===========================================================================
# R5-R7 · el criterio de la ficha por defecto
# ===========================================================================


def _f(obra_id, empresa_id, num_lineas=0, tiemod=None, codigo="0721"):
    from etl_sigrid.domain.ficha_obra import FichaObra

    return FichaObra(
        obra_id=obra_id, codigo_obra=codigo, empresa_id=empresa_id,
        num_lineas=num_lineas, tiemod=tiemod,
    )


#: Cada caso: (fichas como argumentos de `_f`, `obra_id` que debe ganar).
CASOS_R5 = {
    # (1) Ruesma gana aunque la otra tenga más líneas, tiemod e ide mayores.
    "ruesma_gana_a_todo": ([(10, 1, 5, 1.0), (99, 28, 900, 9.0)], 10),
    "ruesma_gana_sin_lineas": ([(2759553, 1), (2855829, 28, 0, 5.0)], 2759553),
    # (2) ficha única: esa, sea de la empresa que sea.
    "ficha_unica_de_porsan": ([(7, 28)], 7),
    "ficha_unica_sin_empresa": ([(8, None)], 8),
    # (3) varias sin Ruesma: líneas > tiemod > ide.
    "sin_ruesma_mandan_las_lineas": ([(1, 27, 50, 1.0), (2, 31, 10, 9.0)], 1),
    "sin_ruesma_empate_de_lineas_tiemod": ([(1, 27, 10, 9.0), (2, 31, 10, 1.0)], 1),
    "sin_ruesma_empate_total_ide": ([(1, 27, 10, 5.0), (2, 31, 10, 5.0)], 2),
    "tiemod_null_pierde": ([(1, 27, 10, None), (2, 31, 10, 0.5)], 2),
    "empresa_nula_no_es_ruesma": ([(1, None, 0), (2, 28, 3)], 2),
    # dos fichas de la empresa 1 (hoy no pasa): deciden las líneas.
    "dos_de_ruesma_lineas": ([(1, 1, 3), (2, 1, 1), (3, 28, 99)], 1),
}


@pytest.mark.parametrize("caso", list(CASOS_R5), ids=list(CASOS_R5))
def test_f162_r5_oraculo_de_la_ficha_por_defecto(caso: str) -> None:
    from etl_sigrid.domain.ficha_obra import ficha_por_defecto

    argumentos, ganadora = CASOS_R5[caso]
    fichas = [_f(*a) for a in argumentos]
    assert ficha_por_defecto(fichas).obra_id == ganadora
    assert ficha_por_defecto(list(reversed(fichas))).obra_id == ganadora, (
        "el orden de entrada no decide"
    )


def test_f162_r5_sin_fichas_o_con_codigos_mezclados_es_error() -> None:
    from etl_sigrid.domain.ficha_obra import ficha_por_defecto

    with pytest.raises(ValueError):
        ficha_por_defecto([])
    with pytest.raises(ValueError):
        ficha_por_defecto([_f(1, 1, codigo="0721"), _f(2, 28, codigo="0720")])


def test_f162_r5_la_empresa_ruesma_es_la_1() -> None:
    from etl_sigrid.domain.ficha_obra import EMPRESA_RUESMA

    assert EMPRESA_RUESMA == 1


def test_f162_r5_las_lineas_se_cuentan_antes_de_unir() -> None:
    lineas = _cte("lineas")
    assert re.fullmatch(
        r"SELECT p\.obride, count\(\*\) AS num_lineas FROM raw\.obrparpre p "
        r"WHERE p\.obride IN \(SELECT obra_id FROM dudosas\) GROUP BY p\.obride",
        lineas,
    ), lineas


def test_f162_r5_solo_se_cuentan_las_fichas_dudosas() -> None:
    """Solo los códigos donde la empresa 1 no decide sola (varias fichas y no
    exactamente una de Ruesma): `raw.obrparpre` tiene 13,7 M de filas."""
    dudosas = _cte("dudosas")
    assert "GROUP BY codigo_obra HAVING count(*) > 1" in dudosas
    assert "count(*) FILTER (WHERE empresa_id = 1) <> 1" in dudosas


def test_f162_r6_conext_no_interviene() -> None:
    assert "conext" not in _compacto(_leer(RUTA_STG_OBRAS)), "D2: conext 15 fuera (R6)"
    from etl_sigrid.domain import ficha_obra

    assert "conext" not in Path(ficha_obra.__file__).read_text(encoding="utf-8").split('"""', 2)[2], (
        "el código del criterio no mira conext (R6)"
    )


#: Cada criterio del dominio y su expresión en el `ORDER BY` del SQL (R7).
SQL_DE_CADA_CRITERIO = {
    "empresa_ruesma": "CASE WHEN f.empresa_id = 1 THEN 0 ELSE 1 END",
    "num_lineas": "COALESCE(l.num_lineas, 0) DESC",
    "tiemod": "f.tiemod DESC NULLS LAST",
    "obra_id": "f.obra_id DESC",
}


def test_f162_r7_el_sql_sigue_al_dominio_criterio_a_criterio() -> None:
    from etl_sigrid.domain.ficha_obra import CRITERIOS

    assert tuple(SQL_DE_CADA_CRITERIO) == CRITERIOS
    final = _select_final()
    ventana = re.search(
        r"ROW_NUMBER\(\) OVER \( ?PARTITION BY f\.codigo_obra ORDER BY (.+?) ?\) = 1 AS es_por_defecto",
        final,
    )
    assert ventana, "es_por_defecto = primer puesto de la ventana por código (R5)"
    orden = [c.strip() for c in _troceado_en_profundidad_cero(ventana.group(1), ",")]
    assert orden == [SQL_DE_CADA_CRITERIO[c] for c in CRITERIOS]


def test_f162_r7_clave_por_defecto_ordena_como_el_sql() -> None:
    from etl_sigrid.domain.ficha_obra import clave_por_defecto

    fichas = [_f(1, 27, 10, None), _f(2, 1, 0, None), _f(3, 31, 10, 2.0), _f(4, 28, 11, 1.0)]
    assert [f.obra_id for f in sorted(fichas, key=clave_por_defecto)] == [2, 4, 3, 1]


# ===========================================================================
# R8 · `maestro.obras.es_por_defecto` (D1)
# ===========================================================================


def test_f162_r8_es_por_defecto_es_la_ultima_columna() -> None:
    sentencia = _sentencia_vista(RUTA_MAESTRO_OBRAS, "CREATE OR REPLACE VIEW maestro.obras AS ")
    assert _columnas_select(sentencia) == [*COLUMNAS_MAESTRO_ANTES, "es_por_defecto"]


def test_f162_r8_sale_de_stg_y_fuera_del_seguimiento_de_la_principal() -> None:
    sentencia = _sentencia_vista(RUTA_MAESTRO_OBRAS, "CREATE OR REPLACE VIEW maestro.obras AS ")
    assert "LEFT JOIN stg.obras so ON so.obra_id = c.ide" in sentencia
    assert "COALESCE(so.es_por_defecto, vf.es_ficha_principal) AS es_por_defecto" in sentencia
    assert " WHERE " not in _nivel_cero(sentencia), "maestro.obras no filtra"


def test_f162_r8_v_obra_fichas_no_cambia_de_columnas() -> None:
    sentencia = _sentencia_vista(RUTA_MAESTRO_SETUP, "CREATE OR REPLACE VIEW maestro.v_obra_fichas AS ")
    assert "es_por_defecto" not in sentencia, "la vista de fichas lee solo raw (design §3.3)"


# ===========================================================================
# R10 · nada cruza por código sin `obra_id`
# ===========================================================================


def test_f162_r10_ningun_group_by_por_codigo_sin_obra_id() -> None:
    """El barrido de design §4.1, fijado: ningún GROUP BY/PARTITION BY de `sql/`
    lleva `codigo_obra` sin `obra_id`, salvo el ranking de fichas (intencionado)
    y el `es_por_defecto` de `03_obras.sql`, que es el criterio."""
    permitidos = {RUTA_MAESTRO_SETUP, RUTA_STG_OBRAS}
    hallazgos = []
    for ruta in sorted(DIR_SQL.rglob("*.sql")):
        if ruta in permitidos:
            continue
        ejecutable = _compacto(_leer(ruta))
        for clausula in re.findall(
            r"(?:GROUP BY|PARTITION BY) ([^;]*?)(?= ORDER BY| HAVING| \)| LIMIT| WINDOW|;|$)",
            ejecutable,
        ):
            if re.search(r"\bcodigo_obra\b", clausula) and not re.search(
                r"\bobra_id\b|\bobride\b|\.obra_id\b", clausula
            ):
                hallazgos.append(f"{ruta.relative_to(DIR_SQL)}: {clausula[:80]}")
    assert not hallazgos, hallazgos


# ===========================================================================
# R11 · las vistas de Power BI (D3)
# ===========================================================================


def test_f162_r11_dim_obra_publica_las_tres_al_final() -> None:
    sentencia = _sentencia_vista(RUTA_DIM_OBRA, "CREATE VIEW mart.v_pbi_dim_obra AS ")
    assert _columnas_select(sentencia) == [
        "obra_id", "codigo_obra", "nombre_obra", "obra_label", *COLUMNAS_NUEVAS,
    ]
    assert sentencia.endswith("FROM stg.obras")


def test_f162_r11_obra_label_lleva_la_clave() -> None:
    sentencia = _sentencia_vista(RUTA_DIM_OBRA, "CREATE VIEW mart.v_pbi_dim_obra AS ")
    assert (
        "COALESCE(clave_obra, codigo_obra) || ' · ' || COALESCE(nombre_obra, '(sin nombre)') "
        "AS obra_label"
    ) in sentencia, "D3: clave_obra · nombre, distingue las fichas de un código"


def test_f162_r11_cabecera_publica_las_tres_al_final() -> None:
    sentencia = _sentencia_vista(RUTA_CABECERA, "CREATE VIEW cierre.v_pbi_cierre_cabecera AS ")
    columnas = _columnas_select(sentencia)
    assert columnas[-3:] == list(COLUMNAS_NUEVAS), columnas[-5:]
    assert columnas[:3] == ["obra_id", "codigo_obra", "nombre_obra"]
    for columna in COLUMNAS_NUEVAS:
        assert f"o.{columna}" in sentencia, f"{columna} sale de stg.obras o"
    assert "presupuesto_vigente_venta_con_coeficientes" == columnas[-4]


# ===========================================================================
# R12 · los comandos de inspección de `main.py`
# ===========================================================================


class _CursorFalso:
    """Simula `stg.obras` con unas pocas fichas: devuelve las que casan por
    código o por clave, como haría la consulta del ayudante."""

    FICHAS = [
        # obra_id, codigo, nombre, clave, es_por_defecto
        (2759553, "0721", "OBRA 0721", "1-0721", True),
        (2855829, "0721", "OBRA 0721", "28-0721", False),
        (650280, "0252", "C.P. PRIMO DE RIVERA", "12-0252", False),
        (587639, "0252", "C.P. PRIMO DE RIVERA", "1-0252", True),
    ]

    def __init__(self) -> None:
        self.sql: list[str] = []
        self._filas: list[tuple] = []

    def execute(self, sql: str, params) -> None:
        self.sql.append(sql)
        valor = params[0] if isinstance(params, (tuple, list)) else next(iter(params.values()))
        self._filas = [
            (oid, nom, clave, defecto, cod)
            for oid, cod, nom, clave, defecto in self.FICHAS
            if cod == valor or clave == valor
        ]

    def fetchall(self) -> list[tuple]:
        return list(self._filas)

    def fetchone(self):  # pragma: no cover - el ayudante no debe usarlo
        raise AssertionError("con varias fichas por código, fetchone coge una al azar")


def test_f162_r12_por_codigo_la_ficha_por_defecto() -> None:
    from main import _obra_de_stg

    cursor = _CursorFalso()
    assert _obra_de_stg(cursor, "0721")[:3] == (2759553, "OBRA 0721", "1-0721")
    assert "stg.obras" in cursor.sql[0] and "es_por_defecto" in cursor.sql[0]
    assert _obra_de_stg(cursor, "0252")[:3] == (587639, "C.P. PRIMO DE RIVERA", "1-0252")


def test_f162_r12_por_clave_la_ficha_de_esa_empresa() -> None:
    from main import _obra_de_stg

    cursor = _CursorFalso()
    assert _obra_de_stg(cursor, "28-0721")[:3] == (2855829, "OBRA 0721", "28-0721")
    assert "clave_obra" in cursor.sql[0]


def test_f162_r12_codigo_inexistente_sale_con_mensaje(capsys) -> None:
    from main import _obra_de_stg

    with pytest.raises(SystemExit) as salida:
        _obra_de_stg(_CursorFalso(), "9999")
    assert salida.value.code == 2
    error = capsys.readouterr().err
    assert "9999" in error and "clave_obra" in error


COMANDOS_R12 = (
    "list_master_cierre", "inspect_cierre", "inspect_indirectos_detalle",
    "inspect_generales_detalle", "inspect_cabecera", "inspect_planif_vs_real",
)


def _cuerpo_funcion(nombre: str) -> str:
    texto = _leer(RAIZ / "main.py")
    inicio = texto.index(f"\ndef {nombre}(")
    fin = texto.find("\n@cli.command", inicio)
    return texto[inicio:fin]


@pytest.mark.parametrize("comando", COMANDOS_R12)
def test_f162_r12_los_seis_comandos_usan_el_ayudante(comando: str) -> None:
    cuerpo = _cuerpo_funcion(comando)
    assert "_obra_de_stg(" in cuerpo, f"{comando} resuelve la obra por el ayudante"
    assert "FROM stg.obras WHERE codigo_obra = %s" not in cuerpo, (
        f"{comando} ya no busca por código con fetchone"
    )


def test_f162_r12_ningun_fetchone_por_codigo_en_main() -> None:
    assert "FROM stg.obras WHERE codigo_obra = %s" not in _leer(RAIZ / "main.py")


def test_f162_r12_find_obra_muestra_la_empresa() -> None:
    cuerpo = _cuerpo_funcion("find_obra")
    for columna in COLUMNAS_NUEVAS:
        assert columna in cuerpo, f"find-obra muestra {columna}"


# ===========================================================================
# R13-R17 · el diccionario
# ===========================================================================


def test_f162_r13_empresa_por_defecto_dice_el_modelo_por_ficha() -> None:
    regla = _regla("R-EMPRESA-POR-DEFECTO")
    texto = _plano(regla["regla"])
    for termino in (
        "`es_por_defecto`", "mismo codigo", "varias empresas",
        "Nunca se suman fichas de empresas distintas sin decirlo",
        "sin datos", "`obra_id` → `stg.obras`",
    ):
        assert termino in texto, f"la regla no dice «{termino}» (R13)"
    assert "`descompuestos` no tienen empresa" not in texto
    assert "`stg`, `mart`, `cierre` y `descompuestos` no" not in texto


def test_f162_r13_el_resumen_dice_es_por_defecto_y_conserva_empresa_1() -> None:
    resumen = _plano(_regla("R-EMPRESA-POR-DEFECTO")["resumen"])
    assert "`es_por_defecto`" in resumen
    assert "`empresa_id = 1`" in resumen, "F-147 R7"
    assert "nunca sumes" in resumen.lower()
    assert len(resumen) <= 250


@pytest.mark.parametrize("esquema", ["stg", "mart", "cierre"])
def test_f162_r13_el_ambito_alcanza_al_seguimiento(esquema: str) -> None:
    assert esquema in _regla("R-EMPRESA-POR-DEFECTO")["ambito"]


def test_f162_r14_universo_obra_una_fila_por_ficha() -> None:
    regla = _regla("R-UNIVERSO-OBRA")
    texto = _plano(f"{regla['resumen']} {regla['regla']}")
    assert "conext" not in texto, "ya no deduplica por conext 15 (R14)"
    assert "deduplica" not in texto
    assert "una fila por ficha" in texto
    assert "lo dice su ficha" in _plano(regla["regla"]), "F-102 R18 la remite a la ficha"


@pytest.mark.parametrize(
    "objeto", ["stg.obras", "mart.v_pbi_dim_obra", "cierre.v_pbi_cierre_cabecera"]
)
def test_f162_r14_codigo_por_empresa_alcanza_al_seguimiento(objeto: str) -> None:
    assert objeto in _regla("R-CODIGO-POR-EMPRESA")["ambito"]


FICHAS_R15 = (
    "stg.obras", "maestro.obras", "mart.v_pbi_dim_obra", "cierre.v_pbi_cierre_cabecera",
)


@pytest.mark.parametrize("objeto", FICHAS_R15)
def test_f162_r15_las_fichas_dicen_que_el_codigo_no_es_unico(objeto: str) -> None:
    ficha = _ficha(objeto)
    assert "es_por_defecto" in ficha["columnas"], f"{objeto} documenta es_por_defecto"
    texto = _normalizado(_texto(ficha))
    assert "no es unico" in texto, f"{objeto} no dice que el código no es único (R15)"
    assert "es_por_defecto" in texto


@pytest.mark.parametrize(
    "objeto", ["mart.fact_seguimiento_mensual", "cierre.fact_cierre_mensual"]
)
def test_f162_r15_el_codigo_de_los_hechos_avisa(objeto: str) -> None:
    texto = _normalizado(_texto(_ficha(objeto)["columnas"]["codigo_obra"]))
    assert "no es unico" in texto
    assert "es_por_defecto" in texto and "obra_id" in texto


def test_f162_r15_stg_obras_tiene_grano_por_ficha() -> None:
    grano = _normalizado(_texto(_ficha("stg.obras")["grano"]))
    assert "una fila por ficha" in grano
    assert "deduplicada" not in grano


@pytest.mark.parametrize("pregunta", ["P4", "P6", "P7", "P10", "P11", "P14"])
def test_f162_r16_las_preguntas_de_la_obra_x_llevan_la_regla(pregunta: str) -> None:
    assert "R-EMPRESA-POR-DEFECTO" in _pregunta(pregunta).get("reglas_implicadas", [])


def test_f162_r16_p9_cuenta_fichas_por_defecto() -> None:
    respuesta = _plano(_pregunta("P9")["respuesta_correcta"])
    assert "`es_por_defecto`" in respuesta


def test_f162_r17_la_version_sube_con_su_nota() -> None:
    assert int(_yaml("00_global.yaml")["version"]) >= 76
    assert "# version 76 (F-162, 2026-11-11): " in _leer(DIR_DICCIONARIO / "00_global.yaml")


# ===========================================================================
# R18 · los guardas que caen a propósito
# ===========================================================================


@pytest.mark.parametrize(
    ("fichero", "test"),
    [
        ("test_f102_obra_principal.py", "test_f102_r7_stg_obras_es_identico_al_de_main"),
        ("test_f102_obra_principal.py", "test_f102_r7_el_guarda_de_f073_sigue_en_pie"),
        ("test_f102_obra_principal.py", "test_f102_r18_la_ficha_de_stg_obras_dice_donde_difiere"),
        ("test_f102_obra_principal.py", "test_f102_r18_la_regla_del_universo_tambien"),
        ("test_f073_sql.py", "test_f073_r26_no_toca_el_desempate_de_stg_obras"),
    ],
)
def test_f162_r18_los_guardas_viejos_se_retiran_con_motivo(fichero: str, test: str) -> None:
    texto = _leer(RAIZ / "tests" / fichero)
    assert f"def {test}(" not in texto, f"{test} sigue en pie"
    assert test in texto and "F-162" in texto, f"{fichero} no dice por qué se retiró {test}"


# ===========================================================================
# R19 · las excepciones de cobertura de F-053
# ===========================================================================


def test_f162_r19_el_trinquete_baja_a_19() -> None:
    from tests.test_f052_cobertura import EXCEPCIONES_MAX

    assert EXCEPCIONES_MAX == 19


def test_f162_r19_las_cuatro_de_f053_salen() -> None:
    datos = yaml.safe_load(_leer(RUTA_EXCEPCIONES))
    codigos = {e.get("codigo_obra") for e in datos["excepciones"]}
    assert not codigos & {"0517", "0252", "0720", "0606"}
    assert all(e.get("feature") != "F-053" for e in datos["excepciones"])


# ===========================================================================
# R20 · los textos que decían «stg.obras no cambia»
# ===========================================================================


FRASES_VIEJAS = (
    "sigue eligiendo",
    "se queda con UNA ficha por codigo",
    "`stg.obras` no cambia",
    "**`stg.obras` no cambia**",
    "deduplicada",
)


@pytest.mark.parametrize(
    "ruta",
    [
        DIR_DICCIONARIO / "maestro.yaml",
        DIR_DICCIONARIO / "stg.yaml",
        RUTA_MAESTRO_SETUP,
        RUTA_MAESTRO_OBRAS,
        RUTA_STG_OBRAS,
        DOC_ARQUITECTURA,
        RAIZ / "CLAUDE.md",
    ],
    ids=lambda r: r.name,
)
def test_f162_r20_ningun_texto_dice_que_stg_obras_elige(ruta: Path) -> None:
    texto = _plano(_leer(ruta))
    for frase in FRASES_VIEJAS:
        assert frase not in texto, f"{ruta.name} sigue diciendo «{frase}» (R20)"


@pytest.mark.parametrize(
    "ruta", [DOC_ARQUITECTURA, RUTA_MAESTRO_SETUP, RUTA_STG_OBRAS], ids=lambda r: r.name
)
def test_f162_r20_los_textos_dicen_lo_nuevo(ruta: Path) -> None:
    texto = _plano(_leer(ruta))
    assert "F-162" in texto and "es_por_defecto" in texto


def test_f162_r20_azure_apps_dice_lo_nuevo() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no está en este puesto")
    texto = _plano(_leer(DOC_AZURE_APPS))
    assert "**`stg.obras` no cambia**" not in texto
    assert "F-162" in texto and "es_por_defecto" in texto


# ===========================================================================
# R21 · F-053 absorbida y F-106 enmendada
# ===========================================================================


def _feature(identificador: str) -> dict:
    import json

    datos = json.loads(_leer(RAIZ / "harness" / "features.json"))
    lista = datos["features"] if isinstance(datos, dict) else datos
    return next(f for f in lista if f["id"] == identificador)


def test_f162_r21_f053_absorbida() -> None:
    texto = _texto(_feature("F-053"))
    assert "absorbida por F-162" in texto


def test_f162_r21_f106_enmendada_sin_cambiar_de_estado() -> None:
    f106 = _feature("F-106")
    texto = _plano(_texto(f106))
    assert "lleva desde F-162 todas las fichas de todas las empresas" in texto
    assert "F-106 queda para RECURSOS, PARTES y COMPRAS" in texto
    assert f106["status"] == "pending"
