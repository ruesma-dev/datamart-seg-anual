# tests/test_f102_obra_principal.py
"""
F-102 · HOTFIX 2: la obra y el recurso son de UNA empresa. Claves legibles
(`clave_obra`, `clave_recurso`) y la ficha de Ruesma como referencia.

Modelo del humano (2026-09-23): las obras son por empresa; el mismo codigo es la
misma obra vista desde cada empresa, SIN consolidar. Este hotfix solo publica
IDENTIFICADORES: `obra_id` sigue siendo la clave tecnica, `stg.obras` no cambia
y el seguimiento por empresa es F-106.

Ningun test toca red ni base de datos (convencion del proyecto): las vistas se
construyen contra un PostgreSQL compartido en produccion. Se fijan sobre el
TEXTO las decisiones que la spec tomo midiendo en solo lectura el 2026-09-23;
las cifras contra la base viva son las verificaciones MANUALES R11, R12 y R30
(`specs/F-102-obra-duplicada-empresa-28/tasks.md`, T3 y T16).

Helpers COPIADOS de `tests/test_f073_sql.py` y no importados, como hace
`tests/test_f101_cabecera_parte.py`: si alguien borra aquel fichero, estos
guardas siguen en pie.

DONDE VIVE `maestro.v_obra_fichas`: en `sql/maestro/00_setup.sql`, no en
`01_obras.sql` como decia el diseno. `tests/test_f073_sql.py` lee las columnas
de `maestro.obras` del PRIMER `CREATE OR REPLACE VIEW` de `01_obras.sql`, asi
que una vista antepuesta en ese fichero rompe sus guardas de orden (R18 de
F-073). `00_setup.sql` corre antes, en el mismo paso, y cumple lo que el diseno
pedia de verdad: que la vista exista antes que `maestro.obras`, lea solo `raw` y
no se dropee. La desviacion esta justificada en `progress/impl_F-102.md`.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_STEPS = RAIZ / "etl_sigrid" / "application" / "steps"
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

RUTA_FICHAS = DIR_SQL / "maestro" / "00_setup.sql"
RUTA_OBRAS = DIR_SQL / "maestro" / "01_obras.sql"
RUTA_STG_OBRAS = DIR_SQL / "stg" / "03_obras.sql"
RUTA_VISTAS_COMPRAS = DIR_SQL / "compras" / "03_views.sql"
RUTA_PAGO_FACTURA = DIR_SQL / "compras" / "06_pago_factura.sql"
RUTA_PERSONAL_SETUP = DIR_SQL / "personal" / "00_setup.sql"
RUTA_RECURSOS = DIR_SQL / "personal" / "01_recursos.sql"

VISTA = "maestro.v_obra_fichas"

#: Las diez columnas de la vista de fichas, en el orden de R1.
COLUMNAS_FICHAS = (
    "obra_id",
    "codigo_obra",
    "empresa_id",
    "clave_obra",
    "marcada_vigente",
    "num_cierres",
    "num_fichas_codigo",
    "rango_ficha",
    "es_ficha_principal",
    "obra_principal_id",
)

#: Lo que `maestro.obras` publicaba en `main` antes de F-102 (F-073 incluida).
#: Ninguna se cae, se renombra ni se mueve: `CREATE OR REPLACE VIEW` solo admite
#: columnas nuevas AL FINAL (R8).
COLUMNAS_OBRAS_ANTES = (
    "obra_id", "codigo_obra", "nombre_obra", "estado_id", "fecha_alta",
    "fecha_baja", "es_activa", "cliente_id", "codigo_cliente", "nombre_cliente",
    "estado", "dir1", "dir2", "codigo_postal", "direccion_completa",
    "municipio_id", "municipio", "provincia_id", "provincia",
    "tiene_presupuesto", "tiene_seguimiento",
)

#: Las seis que anade F-102, al final y en este orden (R8).
COLUMNAS_OBRAS_NUEVAS = (
    "empresa_id",
    "nombre_empresa",
    "clave_obra",
    "num_fichas_codigo",
    "es_ficha_principal",
    "obra_principal_id",
)

#: Las cinco vistas de consumo de `compras` con obra (R21): (fichero, vista).
VISTAS_COMPRAS = (
    (RUTA_VISTAS_COMPRAS, "compras.v_pbi_contrato_consumo"),
    (RUTA_VISTAS_COMPRAS, "compras.v_pbi_proveedor_obra"),
    (RUTA_VISTAS_COMPRAS, "compras.v_pbi_albaranes_sin_facturar"),
    (RUTA_VISTAS_COMPRAS, "compras.v_pbi_partida_coste"),
    (RUTA_PAGO_FACTURA, "compras.v_control_forma_pago"),
)

#: `sha256` de `sql/stg/03_obras.sql` en `main` el 2026-09-23 (R7), con los
#: finales de linea normalizados a LF. `stg.obras` no cambia: pasar el
#: seguimiento a «solo Ruesma» es F-106.
HASH_STG_OBRAS_MAIN = "851dea9012987f8fcbc7099ff2542f3cb80978db87b8067f7587dc9fe9071d27"

#: `depends_on` de cada paso en `main` el 2026-09-23 (R24): la vista nueva no
#: anade dependencias. `compras` la lee sin depender de `build_maestros`, como
#: `retenciones` lee `maestro.centros_coste` desde F-094.
DEPENDS_ON_MAIN = {
    "apply_grants_step.py": ["build_mart"],
    "build_compras_step.py": ["ingest_raw"],
    "build_maestros_step.py": ["ingest_raw", "build_stg"],
    "build_mart_step.py": ["build_stg"],
    "build_personal_step.py": ["build_stg"],
    "build_retenciones_step.py": ["ingest_raw"],
    "build_stg_step.py": ["ingest_raw"],
}

#: Frase canonica del aviso: `obra_principal_id` es referencia, no llave de
#: agregacion (R16, R23). La misma en todas las fichas para que se pueda buscar.
AVISO_PRINCIPAL = "no sirve para agregar hechos de otras empresas"


# ---------------------------------------------------------------------------
# Helpers de texto
# ---------------------------------------------------------------------------


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto EJECUTABLE: sin las lineas `--` de comentario."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    """Una sola linea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


def _troceado_en_profundidad_cero(texto: str, separador: str) -> list[str]:
    """Trocea por `separador`, ignorando lo que caiga dentro de parentesis."""
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


def _sentencia(ruta: Path, vista: str) -> str:
    """El `CREATE OR REPLACE VIEW <vista> AS ...` compacto, hasta su `;`."""
    compacto = _compacto(_sql(ruta))
    marca = f"CREATE OR REPLACE VIEW {vista} AS "
    assert marca in compacto, f"{ruta.name} no crea la vista {vista}"
    resto = compacto[compacto.index(marca) + len(marca):]
    return _troceado_en_profundidad_cero(resto, ";")[0]


def _columnas_en_orden(ruta: Path, vista: str) -> list[str]:
    """Lo que la vista EXPONE, en orden: el SELECT de profundidad cero."""
    cuerpo = " " + _sentencia(ruta, vista)
    seleccion = _troceado_en_profundidad_cero(cuerpo, " SELECT ")[1]
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


def _nivel_cero(texto: str) -> str:
    """El texto sin nada de lo que va entre parentesis (subconsultas, CTE)."""
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


def _hash(ruta: Path) -> str:
    texto = ruta.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _normalizado(texto: str) -> str:
    """Minusculas y sin tildes: el diccionario se escribe sin ellas."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


@cache
def _yaml(fichero: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / fichero).read_text(encoding="utf-8"))


def _ficha(nombre: str) -> dict:
    esquema, objeto = nombre.split(".")
    fichero = "aux_.yaml" if esquema == "aux" else f"{esquema}.yaml"
    objetos = _yaml(fichero)["objetos"]
    assert objeto in objetos, f"no hay ficha de {nombre}"
    return objetos[objeto]


def _texto(valor: object) -> str:
    """Todo el texto de una ficha o de un trozo de ella, aplanado."""
    if isinstance(valor, dict):
        return " ".join(_texto(v) for v in valor.values())
    if isinstance(valor, list):
        return " ".join(_texto(v) for v in valor)
    return "" if valor is None else str(valor)


def _significado(ficha: dict, columna: str) -> str:
    valor = ficha["columnas"][columna]
    return _texto(valor)


def _regla(codigo: str) -> dict:
    reglas = {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}
    assert codigo in reglas, f"no esta la regla {codigo}"
    return reglas[codigo]


# ===========================================================================
# R1-R6 · `maestro.v_obra_fichas`: una fila por ficha, la de Ruesma primero
# ===========================================================================


def test_f102_r1_la_vista_de_fichas_se_crea_antes_que_maestro_obras() -> None:
    """Vive en `00_setup.sql`, que el paso ejecuta antes que `01_obras.sql`."""
    assert f"CREATE OR REPLACE VIEW {VISTA} AS" in _compacto(_sql(RUTA_FICHAS))
    assert VISTA not in _compacto(_sql(RUTA_OBRAS)).split("LEFT JOIN")[0], (
        "maestro.obras no puede crearla: solo la lee (R1, R9)"
    )


def test_f102_r1_publica_las_diez_columnas_en_orden() -> None:
    assert _columnas_en_orden(RUTA_FICHAS, VISTA) == list(COLUMNAS_FICHAS), (
        "maestro.v_obra_fichas publica exactamente las diez columnas de R1"
    )


def test_f102_r1_lee_solo_de_raw() -> None:
    """Si leyera de `stg`, el seguimiento pareceria seguirla; y `compras` la lee."""
    origenes = set(re.findall(r"\b(?:FROM|JOIN) (\w+)\.", _sentencia(RUTA_FICHAS, VISTA)))
    assert origenes == {"raw"}, f"la vista lee de {sorted(origenes)}: solo `raw` (R1)"


def test_f102_r1_la_empresa_es_con_emp() -> None:
    assert re.search(r"\bc\.emp AS empresa_id\b", _sentencia(RUTA_FICHAS, VISTA))


def _criterios_del_ranking() -> list[str]:
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    hallazgo = re.search(
        r"WINDOW w AS \(\s*PARTITION BY codigo_obra ORDER BY (.*?) ROWS BETWEEN",
        sentencia,
    )
    assert hallazgo, "la ventana `w` ordena las fichas de cada codigo (R2)"
    return [c.strip() for c in _troceado_en_profundidad_cero(hallazgo.group(1), ",")]


def test_f102_r2_el_ranking_tiene_cinco_criterios_y_en_este_orden() -> None:
    criterios = _criterios_del_ranking()
    assert len(criterios) == 5, f"el ranking son cinco criterios, hay {criterios} (R2)"
    assert "empresa_id = 1" in criterios[0], "(1) Ruesma primero (R2)"
    assert "marcada_vigente" in criterios[1], "(2) la marca de conext (R2)"
    assert criterios[2] == "num_cierres DESC", "(3) mas cierres primero (R2)"
    assert criterios[3].startswith("tiemod DESC"), "(4) la mas reciente (R2)"
    assert criterios[4] == "obra_id DESC", "(5) desempate por ide DESC (R2)"


def test_f102_r2_ninguna_regla_elige_por_obra_id_menor() -> None:
    """«`obra_id` menor» falla en la 0680: la copia de la 28 tiene el menor."""
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    for prohibido in (r"obra_id ASC", r"\bide ASC", r"min\(\s*\w*\.?(obra_id|ide)\s*\)"):
        assert not re.search(prohibido, sentencia, re.IGNORECASE), (
            f"el ranking elige por `{prohibido}`: es la heuristica descartada (R2)"
        )
    assert not any(c.endswith("ASC") for c in _criterios_del_ranking())


def test_f102_r3_sin_ficha_de_ruesma_decide_el_resto_del_ranking() -> None:
    """La particion es SOLO por codigo y la vista no filtra: los codigos sin
    ficha de la empresa 1 (0001-0005) se ordenan por (2)-(5)."""
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    particiones = re.findall(r"PARTITION BY ([\w, ]+?)(?: ORDER BY|\))", sentencia)
    assert particiones, "la vista particiona por codigo (R3)"
    assert set(p.strip() for p in particiones) == {"codigo_obra"}, (
        f"particiones {particiones}: con la empresa dentro, cada ficha seria "
        "principal de si misma (R3)"
    )
    filtros = re.findall(r"WHERE (.*?)\)", sentencia)
    assert filtros == ["x.conide = o.ide AND x.cod = '15'"], (
        f"la vista no filtra fichas; su unico WHERE es la marca de conext: {filtros}"
    )


def test_f102_r4_la_principal_es_el_primer_puesto() -> None:
    assert "(rango_ficha = 1) AS es_ficha_principal" in _sentencia(RUTA_FICHAS, VISTA)
    assert "ROW_NUMBER() OVER w AS rango_ficha" in _sentencia(RUTA_FICHAS, VISTA), (
        "ROW_NUMBER y no RANK: exactamente una principal por codigo (R4)"
    )


def test_f102_r4_la_marca_de_conext_es_un_exists_y_no_multiplica() -> None:
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    assert re.search(
        r"EXISTS \(SELECT 1 FROM raw\.conext x WHERE x\.conide = o\.ide "
        r"AND x\.cod = '15'\) AS marcada_vigente",
        sentencia,
    ), "la marca se evalua con EXISTS (R4)"
    assert "JOIN raw.conext" not in sentencia, (
        "un JOIN a conext multiplica la ficha que tenga dos filas cod 15 (R4)"
    )


def test_f102_r4_los_cierres_se_cuentan_antes_de_unir() -> None:
    """`num_cierres` sale de `raw.obrfas` AGREGADO por obra: sin agregar, el
    JOIN multiplicaria la ficha por sus fases."""
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    assert re.search(r"FROM raw\.obrfas \w+ GROUP BY \w+\.obride", sentencia)
    assert "COALESCE(" in sentencia, "la obra sin cierres cuenta 0, no NULL"


def test_f102_r5_la_ficha_de_ruesma_sale_de_la_misma_ventana() -> None:
    """`obra_principal_id` y `es_ficha_principal` no pueden divergir."""
    sentencia = _sentencia(RUTA_FICHAS, VISTA)
    assert "first_value(obra_id) OVER w" in sentencia, "la misma ventana `w` (R5)"
    assert re.search(
        r"bool_or\(empresa_id = 1\) OVER \(PARTITION BY codigo_obra\) AS hay_ruesma",
        sentencia,
    )
    assert "CASE WHEN hay_ruesma THEN primera ELSE obra_id END AS obra_principal_id" in (
        sentencia
    ), "sin ficha de la 1, la propia (R5)"


def test_f102_r5_la_ventana_mira_el_codigo_entero() -> None:
    """`first_value` necesita el marco completo, o la ultima fila se ve a si misma."""
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING" in _sentencia(
        RUTA_FICHAS, VISTA
    )


def test_f102_r6_la_clave_es_empresa_guion_codigo() -> None:
    """`1-0581`, `27-0581`: la empresa es entera, asi que no puede colisionar."""
    assert "c.emp::text || '-' || c.cod AS clave_obra" in _sentencia(RUTA_FICHAS, VISTA)


# ===========================================================================
# R7 · `stg.obras` no cambia
# ===========================================================================


def test_f102_r7_stg_obras_es_identico_al_de_main() -> None:
    assert _hash(RUTA_STG_OBRAS) == HASH_STG_OBRAS_MAIN, (
        "`sql/stg/03_obras.sql` no se toca en F-102: el seguimiento «solo "
        "Ruesma» es F-106 (R7)"
    )


def test_f102_r7_el_guarda_de_f073_sigue_en_pie() -> None:
    texto = (RAIZ / "tests" / "test_f073_sql.py").read_text(encoding="utf-8")
    assert "def test_f073_r26_no_toca_el_desempate_de_stg_obras" in texto
    assert '"rn = 1" in texto' in texto


def test_f102_r7_stg_no_lee_la_vista_de_fichas() -> None:
    for ruta in sorted((DIR_SQL / "stg").glob("*.sql")):
        assert "v_obra_fichas" not in _sql(ruta), f"{ruta.name} la lee (R7)"


# ===========================================================================
# R8-R10 · `maestro.obras`: empresa y claves, sin perder filas
# ===========================================================================


def test_f102_r8_las_seis_columnas_van_al_final_y_en_orden() -> None:
    publicadas = _columnas_en_orden(RUTA_OBRAS, "maestro.obras")
    assert publicadas == list(COLUMNAS_OBRAS_ANTES + COLUMNAS_OBRAS_NUEVAS), (
        "las de antes en su orden, y las seis nuevas DETRAS: el replace solo "
        "admite columnas al final (R8)"
    )


def test_f102_r9_une_la_vista_de_fichas_por_obra_id_y_sin_filtrar() -> None:
    sentencia = _sentencia(RUTA_OBRAS, "maestro.obras")
    assert re.search(
        r"LEFT JOIN maestro\.v_obra_fichas (\w+) ON \1\.obra_id = c\.ide", sentencia
    ), "LEFT JOIN por obra_id: no se pierde ninguna de las 922 fichas (R9)"
    assert " WHERE " not in _nivel_cero(sentencia), "maestro.obras no filtra (R9)"


def test_f102_r9_las_marcas_se_leen_y_no_se_recalculan() -> None:
    sentencia = _sentencia(RUTA_OBRAS, "maestro.obras")
    alias = re.search(r"LEFT JOIN maestro\.v_obra_fichas (\w+) ON", sentencia).group(1)
    for columna in ("empresa_id", "clave_obra", "num_fichas_codigo",
                    "es_ficha_principal", "obra_principal_id"):
        assert f"{alias}.{columna} AS {columna}" in sentencia, (
            f"{columna} sale de maestro.v_obra_fichas (R9)"
        )
    assert " OVER " not in sentencia, "ninguna ventana en maestro.obras (R9)"


def test_f102_r10_el_nombre_de_la_empresa_por_lateral_limit_1() -> None:
    sentencia = _sentencia(RUTA_OBRAS, "maestro.obras")
    lateral = re.search(
        r"LEFT JOIN LATERAL \( SELECT (\w+)\.res AS nombre_empresa FROM raw\.auxemp \1 "
        r"WHERE \1\.numemp = c\.emp ORDER BY \1\.ide LIMIT 1 \) (\w+) ON TRUE",
        sentencia,
    )
    assert lateral, "auxemp por lateral con ORDER BY + LIMIT 1 (R10)"
    assert f"{lateral.group(2)}.nombre_empresa AS nombre_empresa" in sentencia


# ===========================================================================
# R13-R14 · la ingesta de `auxemp`
# ===========================================================================


def _tablas() -> list[dict]:
    return yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))["tables"]


def test_f102_r13_auxemp_se_ingiere_entera() -> None:
    entradas = [t for t in _tablas() if t["source_table"] == "auxemp"]
    assert len(entradas) == 1, "auxemp declarada una vez (R13)"
    auxemp = entradas[0]
    assert auxemp["target_table"] == "auxemp"
    assert auxemp["id_column"] == "ide"
    assert auxemp["incremental_column"] is None, "38 filas: refresco completo (R13)"
    assert auxemp["where"] is None
    assert auxemp["exclude_columns"] == []


def test_f102_r13_el_censo_sube_a_69() -> None:
    from tests.test_f066_ingesta_raw import TOTAL_TABLAS as TOTAL_F066
    from tests.test_f074_ingesta_censo import TOTAL_TABLAS as TOTAL_F074

    # F-107 suma `caa` y el censo pasa a 70: lo que este test fija es que
    # `auxemp` sigue contada, no que nadie mas pueda entrar despues.
    assert len(_tablas()) == TOTAL_F066 == TOTAL_F074 >= 69


def test_f102_r14_la_ficha_de_auxemp_dice_que_numemp_es_con_emp() -> None:
    ficha = _ficha("raw.auxemp")
    texto = _texto(ficha)
    assert "`numemp`" in texto and "`con.emp`" in texto, (
        "la ficha dice por que campo se cruza: numemp = con.emp (R14)"
    )
    assert "28" in texto and "PORSAN" in texto.upper()


def test_f102_r14_la_cabecera_de_raw_yaml_cuenta_69() -> None:
    texto = (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")
    hallazgo = re.search(r"[Ss]on (\d+) tablas", texto)
    assert hallazgo and int(hallazgo.group(1)) >= 69, "F-107 la sube a 70"


# ===========================================================================
# R15-R16, R19 · la ficha de `maestro.obras` y la de la vista nueva
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_OBRAS_NUEVAS)
def test_f102_r15_la_ficha_documenta_las_seis_columnas(columna: str) -> None:
    ficha = _ficha("maestro.obras")
    assert columna in ficha["columnas"], f"falta la ficha de {columna} (R15)"
    assert len(_significado(ficha, columna)) > 60, f"{columna}: ficha vacia (R15)"


def test_f102_r15_la_ficha_explica_el_modelo_sin_consolidar() -> None:
    descripcion = _normalizado(_ficha("maestro.obras")["descripcion"])
    assert "misma obra" in descripcion and "sin consolidar" in descripcion, (
        "el modelo del humano: misma obra vista desde cada empresa (R15)"
    )


def test_f102_r15_la_ficha_ya_no_dice_un_tercio() -> None:
    texto = _normalizado(_texto(_ficha("maestro.obras")))
    assert "un tercio" not in texto
    assert "dos de cada tres" not in texto


def test_f102_r15_la_cobertura_va_por_tramo_y_con_fecha() -> None:
    texto = _texto(_ficha("maestro.obras"))
    for cifra in ("310 de 846", "49 de 59", "77 de 252", "2026-09-23"):
        assert cifra in texto, f"falta la cobertura medida «{cifra}» (R15)"


def test_f102_r15_las_fichas_de_la_28_no_traen_direccion_ni_cliente() -> None:
    texto = _normalizado(_texto(_ficha("maestro.obras")))
    assert "103 fichas de la empresa 28" in texto, "R15"


def test_f102_r16_por_codigo_se_cruza_siempre_con_la_empresa() -> None:
    texto = _texto(_ficha("maestro.obras"))
    assert re.search(r"[Ss]iempre", texto)
    assert "`empresa_id`" in texto and "`clave_obra`" in texto, "R16"


def test_f102_r16_obra_principal_id_es_solo_referencia() -> None:
    significado = _normalizado(_significado(_ficha("maestro.obras"), "obra_principal_id"))
    assert "referencia" in significado
    assert AVISO_PRINCIPAL in significado, "R16"


def test_f102_r16_los_codigos_administrativos_se_advierten() -> None:
    """11 fichas apuntan a la de Ruesma sin ser la misma cosa (design §1.3)."""
    significado = _significado(_ficha("maestro.obras"), "obra_principal_id")
    for codigo in ("CM", "CP", "GG"):
        assert f"`{codigo}`" in significado or f"{codigo} " in significado


def test_f102_r19_la_vista_de_fichas_tiene_ficha() -> None:
    ficha = _ficha(VISTA)
    assert ficha["tipo"] == "vista"
    assert ficha["capa"] == "consumo"
    # DESVIACION JUSTIFICADA de design.md §3 («no recomendada»): F-079 fijo que
    # `consumo_recomendado: false` es solo para objetos rotos, vacios o de
    # instrumentacion, nunca una preferencia de enrutado
    # (`test_f079_r3_el_inventario_de_lo_que_no_se_toca_esta_completo`). Esta
    # vista es correcta y consultable: se recomienda y su descripcion enruta.
    assert ficha["consumo_recomendado"] is True
    assert "maestro.obras" in ficha["descripcion"]
    assert ficha["clave_negocio"] == ["obra_id"]
    assert ficha["paso_etl"] == "build_maestros"
    assert list(ficha["columnas"]) == list(COLUMNAS_FICHAS)


def test_f102_r19_la_ficha_de_obras_dice_que_condir_no_aporta() -> None:
    texto = _texto(_ficha("maestro.obras"))
    assert "`condir`" in texto and "0 de 922" in texto, "R19"


# ===========================================================================
# R17-R18, R20 · la regla nueva, `stg.obras` y la version
# ===========================================================================

AMBITO_REGLA = (
    "maestro.obras",
    "maestro.v_obra_fichas",
    "stg.obras",
    "personal.partes_lineas",
    "personal.partes",
    "personal.recursos",
    "retenciones.movimientos",
    "maestro.centros_coste",
    "compras.contratos",
    "compras.albaran_lineas",
    "compras.factura_lineas",
    "compras.fact_compras_linea",
)


def test_f102_r17_la_regla_es_bloqueante_y_alcanza_a_obras_y_recursos() -> None:
    regla = _regla("R-CODIGO-POR-EMPRESA")
    assert regla["severidad"] == "bloqueante"
    faltan = set(AMBITO_REGLA) - set(regla["ambito"])
    assert not faltan, f"el ambito no alcanza a {sorted(faltan)} (R17)"


def test_f102_r17_la_regla_trae_las_cifras_medidas() -> None:
    regla = _regla("R-CODIGO-POR-EMPRESA")
    texto = f"{regla['regla']} {regla['motivo']}"
    for cifra in ("922", "846", "2.618", "`clave_obra`", "`clave_recurso`"):
        assert cifra in texto, f"la regla no dice «{cifra}» (R17)"


def test_f102_r18_la_ficha_de_stg_obras_dice_donde_difiere() -> None:
    texto = _texto(_ficha("stg.obras"))
    for codigo in ("0581", "0606", "0671", "0720", "F-106", "es_ficha_principal"):
        assert codigo in texto, f"stg.obras no dice «{codigo}» (R18)"


def test_f102_r18_la_regla_del_universo_tambien() -> None:
    regla = _regla("R-UNIVERSO-OBRA")
    texto = f"{regla['regla']} {regla['motivo']}"
    for codigo in ("0581", "0606", "0671", "0720", "F-106"):
        assert codigo in texto, f"R-UNIVERSO-OBRA no dice «{codigo}» (R18)"


def test_f102_r20_la_version_sube_sobre_la_de_main() -> None:
    """`main` publica la 28 (F-101); F-102 la sube en uno."""
    assert int(_yaml("00_global.yaml")["version"]) >= 29, "F-107 la sube a 30"


# ===========================================================================
# R21-R23 · `compras` y las fichas que apuntan a `maestro.obras.obra_id`
# ===========================================================================


@pytest.mark.parametrize(
    ("ruta", "vista"), VISTAS_COMPRAS, ids=[v for _, v in VISTAS_COMPRAS]
)
def test_f102_r21_las_vistas_de_compras_acaban_en_empresa_y_clave(
    ruta: Path, vista: str
) -> None:
    columnas = _columnas_en_orden(ruta, vista)
    assert columnas[-2:] == ["empresa_id", "clave_obra"], (
        f"{vista}: empresa_id y clave_obra al final y en ese orden (R21)"
    )
    assert "obra_principal_id" not in columnas


@pytest.mark.parametrize(
    ("ruta", "vista"), VISTAS_COMPRAS, ids=[v for _, v in VISTAS_COMPRAS]
)
def test_f102_r21_se_toman_de_la_vista_de_fichas_con_left_join(
    ruta: Path, vista: str
) -> None:
    sentencia = _sentencia(ruta, vista)
    unir = re.search(
        r"LEFT JOIN maestro\.v_obra_fichas (\w+) ON \1\.obra_id = \w+\.obra_id", sentencia
    )
    assert unir, f"{vista}: LEFT JOIN por obra_id, NULL si no hay obra (R21)"
    alias = unir.group(1)
    assert f"{alias}.empresa_id AS empresa_id" in sentencia
    assert f"{alias}.clave_obra AS clave_obra" in sentencia


@pytest.mark.parametrize(
    ("vista", "grupo_de_siempre"),
    [
        ("compras.v_pbi_proveedor_obra",
         "GROUP BY l.obra_id, l.codigo_obra, l.proveedor_id, l.proveedor_nombre, "
         "l.proveedor_cif, l.anio"),
        ("compras.v_pbi_partida_coste",
         "GROUP BY f.obra_id, f.codigo_obra, f.partida_id, par.cod, par.res"),
    ],
)
def test_f102_r21_las_vistas_agregadas_no_cambian_de_grano(
    vista: str, grupo_de_siempre: str
) -> None:
    """DESVIACION JUSTIFICADA de R21 («sobre el resultado ya agregado»): la union
    va ANTES de agregar y las dos columnas se agrupan con el resto, porque la
    puerta de F-006 (`test_f006_r2_control_el_group_by_se_lee_donde_se_puede_leer`)
    exige el `GROUP BY` en el nivel 0. El grano no cambia: la vista de fichas
    tiene una fila por `obra_id` y las dos columnas dependen solo de el. Lo que
    se fija aqui es justo eso: el `GROUP BY` de siempre, entero y en su orden,
    mas `empresa_id` y `clave_obra` DETRAS, y ni una columna mas."""
    sentencia = _sentencia(RUTA_VISTAS_COMPRAS, vista)
    alias = re.search(r"LEFT JOIN maestro\.v_obra_fichas (\w+) ON", sentencia).group(1)
    esperado = f"{grupo_de_siempre}, {alias}.empresa_id, {alias}.clave_obra"
    assert re.search(rf"{re.escape(esperado)}$", sentencia.strip()), (
        f"{vista}: el GROUP BY de siempre mas empresa y clave, nada mas (R21)"
    )
    assert "GROUP BY" in _nivel_cero(sentencia), "el GROUP BY en el nivel 0"


def test_f102_r21_ningun_sql_de_compras_publica_la_ficha_de_ruesma() -> None:
    """Cada factura con SU empresa: nadie suma la UTE en la obra de Ruesma."""
    for ruta in sorted((DIR_SQL / "compras").glob("*.sql")):
        assert "obra_principal_id" not in _sql(ruta), f"{ruta.name} (R21)"


VISTAS_FICHA_COMPRAS = (
    "v_pbi_contrato_consumo",
    "v_pbi_proveedor_obra",
    "v_pbi_albaranes_sin_facturar",
    "v_pbi_partida_coste",
    "v_control_forma_pago",
)


@pytest.mark.parametrize("vista", VISTAS_FICHA_COMPRAS)
def test_f102_r22_las_fichas_documentan_empresa_y_clave(vista: str) -> None:
    ficha = _ficha(f"compras.{vista}")
    for columna in ("empresa_id", "clave_obra"):
        assert columna in ficha["columnas"], f"{vista}.{columna} sin ficha (R22)"
    assert list(ficha["columnas"])[-2:] == ["empresa_id", "clave_obra"]


@pytest.mark.parametrize("vista", VISTAS_FICHA_COMPRAS)
def test_f102_r22_la_relacion_por_clave_esta_declarada(vista: str) -> None:
    """DESVIACION JUSTIFICADA de R22 («(N:1)»): se declara `N:N` y el `porque`
    dice que de hecho es N:1. El validador del diccionario (R5 de F-006,
    `_es_unica_por`) solo acepta el lado «1» sobre la clave de negocio ENTERA o
    una `clave_sustituta`, y la de `maestro.obras` es `obra_id`: declarar `N:1`
    tumba la puerta, y marcar `clave_obra` como sustituta seria falso (no es un
    BIGSERIAL y `check-unicidad` la trataria como garantizada)."""
    relaciones = [
        r for r in _ficha(f"compras.{vista}")["relaciones"]
        if r["de"] == "clave_obra" and r["a"] == "maestro.obras.clave_obra"
    ]
    assert len(relaciones) == 1, f"{vista}: clave_obra -> maestro.obras.clave_obra (R22)"
    relacion = relaciones[0]
    assert relacion["cardinalidad"] == "N:N"
    assert "DE HECHO ES N:1" in relacion["porque"] and "922 para 922" in relacion["porque"]


@pytest.mark.parametrize("vista", VISTAS_FICHA_COMPRAS)
def test_f102_r22_avisa_de_que_agregar_por_codigo_mezcla_empresas(vista: str) -> None:
    texto = _normalizado(_texto(_ficha(f"compras.{vista}")))
    assert "mezcla empresas" in texto, f"{vista}: el aviso de R22"
    assert "`clave_obra`" in texto


FICHAS_CON_OBRA = (
    "compras.contratos",
    "compras.albaran_lineas",
    "compras.factura_lineas",
    "compras.fact_compras_linea",
    "retenciones.movimientos",
    "retenciones.v_pbi_retencion_obra",
    "maestro.proveedores_obra",
    "maestro.centros_coste",
)


@pytest.mark.parametrize("nombre", FICHAS_CON_OBRA)
def test_f102_r23_el_obra_id_es_la_ficha_de_la_empresa_del_documento(nombre: str) -> None:
    significado = _normalizado(_significado(_ficha(nombre), "obra_id"))
    assert "empresa del documento" in significado, f"{nombre}.obra_id (R23)"
    assert "maestro.obras" in significado


@pytest.mark.parametrize("nombre", FICHAS_CON_OBRA)
def test_f102_r23_la_relacion_prohibe_agregar_por_la_ficha_de_ruesma(nombre: str) -> None:
    relaciones = [
        r for r in _ficha(nombre)["relaciones"] if r["a"] == "maestro.obras.obra_id"
    ]
    assert relaciones, f"{nombre} no tiene relacion con maestro.obras.obra_id"
    porque = _normalizado(" ".join(r["porque"] for r in relaciones))
    assert "obra_principal_id" in porque and AVISO_PRINCIPAL in porque, (
        f"{nombre}: el porque de la relacion (R23)"
    )


# ===========================================================================
# R24-R25 · lo que NO cambia
# ===========================================================================

SQL_QUE_NO_LEEN_LA_VISTA = (
    "compras/01_documentos.sql",
    "compras/02_fact_linea.sql",
    "compras/05_vencimientos.sql",
    "compras/07_texto.sql",
    "maestro/03_proveedores_obra.sql",
    "maestro/04_centros_coste.sql",
)


@pytest.mark.parametrize("relativa", SQL_QUE_NO_LEEN_LA_VISTA)
def test_f102_r24_las_tablas_no_reescriben_su_obra_id(relativa: str) -> None:
    assert "v_obra_fichas" not in _sql(DIR_SQL / relativa), f"{relativa} (R24, D2)"


@pytest.mark.parametrize("esquema", ["retenciones", "personal"])
def test_f102_r24_retenciones_y_personal_no_leen_la_vista(esquema: str) -> None:
    for ruta in sorted((DIR_SQL / esquema).glob("*.sql")):
        assert "v_obra_fichas" not in _sql(ruta), f"{esquema}/{ruta.name} (R24)"


def _depends_on(fichero: str) -> list[str]:
    texto = (DIR_STEPS / fichero).read_text(encoding="utf-8")
    bloque = texto[texto.index("def depends_on"):]
    hallazgo = re.search(r"return \[(.*?)\]", bloque, re.DOTALL)
    assert hallazgo, f"{fichero}: depends_on sin lista literal"
    return re.findall(r'"(\w+)"', hallazgo.group(1))


@pytest.mark.parametrize("fichero", sorted(DEPENDS_ON_MAIN))
def test_f102_r24_ningun_paso_cambia_su_depends_on(fichero: str) -> None:
    assert _depends_on(fichero) == DEPENDS_ON_MAIN[fichero], f"{fichero} (R24)"


def test_f102_r25_la_cabecera_de_obras_ya_no_dice_un_tercio() -> None:
    texto = _normalizado(_sql(RUTA_OBRAS))
    assert "un tercio" not in texto and "dos de cada tres" not in texto, "R25"
    # Las frases que veta `test_f073_r11`, sobre el fichero entero.
    crudo = _sql(RUTA_OBRAS).lower()
    assert "las obras no tienen dirección" not in crudo
    assert "sin dirección" not in crudo


def test_f102_r25_el_comment_explica_el_modelo() -> None:
    comentario = re.search(r"COMMENT ON VIEW maestro\.obras IS (.*?);", _compacto(
        _sql(RUTA_OBRAS)
    ))
    assert comentario, "maestro.obras lleva COMMENT"
    texto = _normalizado(comentario.group(1))
    assert "clave_obra" in texto and "empresa_id" in texto
    assert "un tercio" not in texto


# ===========================================================================
# R28 · la arquitectura
# ===========================================================================


def test_f102_r28_la_arquitectura_explica_el_modelo() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("clave_obra", "clave_recurso", "es_ficha_principal", "F-106",
                    "R-CODIGO-POR-EMPRESA", "F-102"):
        assert termino in texto, f"ARCHITECTURE.md no dice «{termino}» (R28)"


# ===========================================================================
# R29 · el documento de `azure-apps`
# ===========================================================================


def test_f102_r29_azure_apps_recoge_las_columnas_y_la_regla() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("clave_obra", "es_ficha_principal", "obra_principal_id",
                    "maestro.v_obra_fichas", "R-CODIGO-POR-EMPRESA",
                    "v_control_forma_pago", "F-106", "auxemp"):
        assert termino in texto, f"azure-apps no dice «{termino}» (R29)"


# ===========================================================================
# R26-R27 · `personal.recursos`: empresa, nombre y clave legible (T15)
# ===========================================================================

COLUMNAS_RECURSO_NUEVAS = ("empresa_id", "nombre_empresa", "clave_recurso")

#: Lo que features POSTERIORES anaden detras de las tres de F-102, tambien al
#: final: F-107, la contrapartida del recurso. «Al final» para F-102 es «justo
#: antes de estas».
COLUMNAS_RECURSO_POSTERIORES = (
    "centro_coste_contrapartida_id",
    "cuenta_analitica_contrapartida_id",
)


def _sin_posteriores(columnas: list[str]) -> list[str]:
    """Quita por la cola las columnas que anadieron features posteriores."""
    n = len(COLUMNAS_RECURSO_POSTERIORES)
    assert columnas[-n:] == list(COLUMNAS_RECURSO_POSTERIORES), columnas[-n:]
    return columnas[:-n]


@pytest.mark.parametrize("columna", COLUMNAS_RECURSO_NUEVAS)
def test_f102_r26_la_tabla_existente_gana_la_columna_sin_drop(columna: str) -> None:
    """`CREATE TABLE IF NOT EXISTS` no anade columnas a la tabla que la
    nocturna ya creo: van con `ADD COLUMN IF NOT EXISTS`, nunca con `DROP`."""
    compacto = _compacto(_sql(RUTA_PERSONAL_SETUP))
    assert re.search(
        rf"ALTER TABLE personal\.recursos ADD COLUMN IF NOT EXISTS {columna} ", compacto
    ), f"personal.recursos gana {columna} con ADD COLUMN IF NOT EXISTS (R26)"
    assert "DROP TABLE" not in compacto.upper()


def test_f102_r26_la_tabla_nueva_nace_con_las_tres_al_final() -> None:
    compacto = _compacto(_sql(RUTA_PERSONAL_SETUP))
    ddl = re.search(r"CREATE TABLE IF NOT EXISTS personal\.recursos \((.*?)\);", compacto)
    assert ddl, "falta el CREATE TABLE de personal.recursos"
    columnas = [c.strip().split(" ")[0] for c in _troceado_en_profundidad_cero(
        ddl.group(1), ",")]
    assert _sin_posteriores(columnas)[-3:] == list(COLUMNAS_RECURSO_NUEVAS), (
        "en una base nueva nacen al final, igual que las anade el ALTER (R26)"
    )


def test_f102_r26_el_insert_publica_las_tres_al_final() -> None:
    compacto = _compacto(_sql(RUTA_RECURSOS))
    lista = re.search(r"INSERT INTO personal\.recursos \((.*?)\) SELECT", compacto)
    assert lista, "falta el INSERT de personal.recursos"
    columnas = [c.strip() for c in lista.group(1).split(",")]
    assert _sin_posteriores(columnas)[-3:] == list(COLUMNAS_RECURSO_NUEVAS), "R26"


def test_f102_r26_la_empresa_y_la_clave_salen_de_con() -> None:
    compacto = _compacto(_sql(RUTA_RECURSOS))
    assert re.search(r"\bc\.emp AS empresa_id\b", compacto), "R26"
    assert "c.emp::text || '-' || c.cod AS clave_recurso" in compacto, (
        "la clave es empresa, guion y codigo, con la empresa delante (R26)"
    )


def test_f102_r26_el_nombre_de_la_empresa_por_lateral_sin_where_fuera() -> None:
    compacto = _compacto(_sql(RUTA_RECURSOS))
    lateral = re.search(
        r"LEFT JOIN LATERAL \( SELECT (\w+)\.res AS nombre_empresa FROM raw\.auxemp \1 "
        r"WHERE \1\.numemp = c\.emp ORDER BY \1\.ide LIMIT 1 \) (\w+) ON TRUE",
        compacto,
    )
    assert lateral, "auxemp por lateral con ORDER BY + LIMIT 1 (R26)"
    assert f"{lateral.group(2)}.nombre_empresa AS nombre_empresa" in compacto
    fuera = re.sub(r"LEFT JOIN LATERAL \(.*?\) \w+ ON TRUE", " ", compacto)
    assert " WHERE " not in fuera.upper(), "ni un WHERE fuera de los laterales (R26)"
    # El lateral de `raw.emp` sigue siendo el PRIMERO: los guardas de F-057 lo
    # buscan asi y leen su lista blanca.
    assert compacto.index("FROM raw.emp ") < compacto.index("FROM raw.auxemp ")


def test_f102_r27_la_ficha_de_recursos_documenta_las_tres() -> None:
    ficha = _ficha("personal.recursos")
    for columna in COLUMNAS_RECURSO_NUEVAS:
        assert columna in ficha["columnas"], f"{columna} sin ficha (R27)"
        assert len(_significado(ficha, columna)) > 60
    assert _sin_posteriores(list(ficha["columnas"]))[-3:] == list(COLUMNAS_RECURSO_NUEVAS)


def test_f102_r27_la_ficha_dice_que_la_clave_legible_es_clave_recurso() -> None:
    texto = _texto(_ficha("personal.recursos"))
    for cifra in ("61", "2.618", "`MO/0009`", "`clave_recurso`"):
        assert cifra in texto, f"la ficha no dice «{cifra}» (R27)"
    assert "una ficha por empresa" in _normalizado(texto)


def test_f102_r27_no_se_publica_marca_de_misma_persona() -> None:
    """D5 (A): el humano decidio no publicar la marca de «misma persona»."""
    columnas = _ficha("personal.recursos")["columnas"]
    assert not [c for c in columnas if "persona" in c and c != "clase"], columnas
    assert "misma_persona" not in _sql(RUTA_RECURSOS)


def test_f102_r29_azure_apps_recoge_personal_recursos() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    assert "clave_recurso" in DOC_AZURE_APPS.read_text(encoding="utf-8"), "R29"
