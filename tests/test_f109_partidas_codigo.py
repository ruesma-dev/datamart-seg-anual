# tests/test_f109_partidas_codigo.py
"""
F-109 · El código de partida NO es único ni dentro de su obra.

`(obra_id, codigo_partida)` se repite en 5.202 pares (8.933 filas de más, 158
obras) en `stg.partidas` y en `mart.v_pbi_dim_partida`, medido en solo lectura
el 2026-09-25 (`specs/F-109-partidas-codigo-no-unico/design.md` §1). Tres fichas
del diccionario decían lo contrario. Esta feature corrige el TEXTO que lee el
agente —fichas, una regla dura, `ARCHITECTURE.md`— y no toca ningún SQL.

Decisiones del humano (2026-09-26, `progress/spec_F-109.md`, «APROBADA»): la
única clave de una partida es `partida_id` (D1); la regla
`R-PARTIDA-CODIGO-NO-UNICO` prohíbe UNIR por obra + código y permite AGRUPAR por
código si se declara (D2, redacción literal del humano); los nombres de escalón
resueltos por código se documentan aquí y se arreglan en F-111 (D3); el
diccionario sube a la versión 35 (D4).

Ningún test toca red ni base de datos: todo se comprueba sobre el diccionario
del árbol (`cargar_diccionario`, `derivar_avisos`, `validar`) y sobre los
ficheros SQL y Markdown. Las cifras contra la base viva son la verificación
MANUAL R18.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import yaml

from etl_sigrid.domain.diccionario import (
    MINIMOS_TEXTO,
    derivar_avisos,
    validar,
)
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"

CODIGO_REGLA = "R-PARTIDA-CODIGO-NO-UNICO"

#: El ámbito mínimo de la regla (R9): todo objeto publicado que lleva
#: `codigo_partida` o resuelve algo con él.
AMBITO_MINIMO = (
    "stg.partidas",
    "mart.v_pbi_dim_partida",
    "mart.v_pbi_dim_partida_niveles",
    "mart.fact_seguimiento_mensual",
    "mart.v_fact_periodificado",
    "compras.v_pbi_partida_coste",
    "cierre.v_pbi_dim_subcategoria_ci",
)

#: Los ficheros SQL que resuelven algo por `(obra_id, codigo_partida)` el
#: 2026-09-25 (R15). Los dos resuelven NOMBRES, no importes, y los arregla
#: F-111. TRINQUETE: la lista solo puede bajar.
AGRUPAN_POR_OBRA_Y_CODIGO = frozenset({
    "cierre/04_views_detalle.sql",
    "mart/05b_view_dim_partida_niveles.sql",
})

#: `GROUP BY obra_id, codigo_partida`, sin distinguir mayúsculas ni espacios.
PATRON_AGRUPA = re.compile(r"GROUP\s+BY\s+obra_id\s*,\s*codigo_partida", re.I)

#: Frases que atribuyen unicidad al código dentro de la obra (R4), sobre texto
#: normalizado (sin tildes, sin marcas Markdown, minúsculas, espacios
#: colapsados). Una negación inmediata («no es único dentro de la obra») no
#: cuenta: es justo lo que la ficha tiene que decir.
PATRON_UNICIDAD = re.compile(
    r"(?<!no es )(?<!no son )"
    r"unic[oa]s? (?:por|en|dentro de) (?:su |la |cada )?obra"
    r"|solo son unic[oa]s? dentro"
)


# ---------------------------------------------------------------------------
# Utilidades (copiadas, no importadas, como en tests/test_f102_obra_principal.py)
# ---------------------------------------------------------------------------


def _norm(texto: str | None) -> str:
    """Texto comparable: sin tildes, sin `*` ni `` ` ``, en minúsculas y con
    todo espacio colapsado. Una frase envuelta por un bloque `>-` o escrita con
    tilde en un sitio y sin ella en otro es la misma frase."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "")
        if not unicodedata.combining(c)
    )
    limpio = sin_tildes.replace("*", "").replace("`", "").lower()
    return re.sub(r"\s+", " ", limpio).strip()


@cache
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _ficha(nombre: str):
    ficha = _diccionario().por_nombre.get(nombre)
    assert ficha is not None, f"el diccionario no tiene ficha de `{nombre}`"
    return ficha


def _columna(nombre_ficha: str, columna: str) -> str:
    """El `significado` de una columna, normalizado."""
    for col in _ficha(nombre_ficha).columnas:
        if col.nombre == columna:
            return _norm(col.significado)
    raise AssertionError(f"`{nombre_ficha}` no documenta la columna `{columna}`")


def _regla():
    regla = next((r for r in _diccionario().reglas if r.codigo == CODIGO_REGLA), None)
    assert regla is not None, f"00_global.yaml no declara `{CODIGO_REGLA}`"
    return regla


def _faltan(texto: str, *frases: str) -> list[str]:
    return [f for f in frases if _norm(f) not in texto]


def _afirmaciones_de_unicidad(texto: str) -> list[str]:
    return [m.group(0) for m in PATRON_UNICIDAD.finditer(_norm(texto))]


def _sql_que_agrupa(directorio: Path) -> set[str]:
    """Ficheros de `directorio` (recursivo) con `GROUP BY obra_id, codigo_partida`,
    como ruta relativa con barras normales."""
    return {
        ruta.relative_to(directorio).as_posix()
        for ruta in directorio.rglob("*.sql")
        if PATRON_AGRUPA.search(ruta.read_text(encoding="utf-8"))
    }


def _comprobar_trinquete(directorio: Path) -> list[str]:
    """Los errores del trinquete de R15: un fichero NUEVO que agrupa por obra y
    código, nombrado. Vacío si todo está en orden."""
    nuevos = sorted(_sql_que_agrupa(directorio) - AGRUPAN_POR_OBRA_Y_CODIGO)
    return [
        f"{fichero} resuelve algo por (obra_id, codigo_partida), que NO es unico "
        f"(F-109): une o agrupa por partida_id, o declaralo aqui con su porque"
        for fichero in nuevos
    ]


# ---------------------------------------------------------------------------
# Las fichas dicen la verdad (R1-R8)
# ---------------------------------------------------------------------------


def test_f109_r1_stg_partidas_obra_id_no_dice_que_el_codigo_sea_unico() -> None:
    texto = _columna("stg.partidas", "obra_id")

    assert _afirmaciones_de_unicidad(texto) == [], texto
    assert "partida_id" in texto, "no dice que la partida se identifica por partida_id"
    assert "no es unico" in texto, "no dice que el codigo NO es unico en la obra"


def test_f109_r2_dim_partida_obra_id_no_dice_que_el_codigo_sea_unico() -> None:
    texto = _columna("mart.v_pbi_dim_partida", "obra_id")

    assert _afirmaciones_de_unicidad(texto) == [], texto
    assert "partida_id" in texto
    assert "no es unico" in texto


def test_f109_r3_fact_codigo_partida_no_dice_unico_por_obra() -> None:
    texto = _columna("mart.fact_seguimiento_mensual", "codigo_partida")

    assert "unico por obra" not in texto
    assert _afirmaciones_de_unicidad(texto) == [], texto
    assert "partida_id" in texto
    assert "no es unico" in texto


def test_f109_r4_ninguna_ficha_dice_que_el_codigo_es_unico() -> None:
    """Barrido de TODO el diccionario: descripción, grano, motivo de no consumo,
    columnas y reglas. Nombra ficha y campo culpables."""
    culpables: list[str] = []
    for ficha in _diccionario().fichas:
        textos = {
            "descripcion": ficha.descripcion,
            "grano": ficha.grano,
            "motivo_no_consumo": ficha.motivo_no_consumo,
            **{f"columna {c.nombre}": c.significado for c in ficha.columnas},
        }
        for campo, texto in textos.items():
            for frase in _afirmaciones_de_unicidad(texto or ""):
                culpables.append(f"{ficha.nombre} · {campo}: «{frase}»")
    for regla in _diccionario().reglas:
        for frase in _afirmaciones_de_unicidad(f"{regla.regla} {regla.motivo}"):
            culpables.append(f"regla {regla.codigo}: «{frase}»")

    assert culpables == [], (
        "el diccionario atribuye unicidad al codigo de partida dentro de la obra, "
        "y NO la tiene (F-109: 5.202 pares repetidos):\n" + "\n".join(culpables)
    )


def test_f109_r4_el_barrido_muerde_con_y_sin_tildes() -> None:
    """El patrón caza las tres frases que había en `main` y deja pasar la
    negación que ahora escriben las fichas."""
    for frase in (
        "Los codigos de partida solo son unicos DENTRO de su obra.",
        "los códigos de partida sólo son únicos dentro de su obra",
        "Codigo jerarquico ('01.02'). Unico por\n        obra, no entre obras.",
    ):
        assert _afirmaciones_de_unicidad(frase), frase

    for frase in (
        "el codigo de partida NO es unico ni dentro de ella",
        "**NO es único dentro de la obra**",
    ):
        assert _afirmaciones_de_unicidad(frase) == [], frase


def test_f109_r5_codigo_partida_explica_la_repeticion_con_cifras() -> None:
    texto = _columna("stg.partidas", "codigo_partida")

    faltan = _faltan(
        texto,
        "no es unico dentro de la obra",
        "5.202", "158", "2026-09-25",
        "contrato", "expediente", "capitulo", "raices paralelas", "errata",
        "4.437", "partida_id", "ruta_capitulos",
    )
    assert faltan == [], f"a la ficha de stg.partidas.codigo_partida le falta {faltan}"


def test_f109_r6_codigo_partida_no_dice_nunca_vacio_sin_matizar() -> None:
    texto = _columna("stg.partidas", "codigo_partida")

    assert "nunca es null ni vacio" not in texto, (
        "2 filas traen un codigo de solo espacios, que el filtro `cod <> ''` deja pasar"
    )
    assert "solo espacios" in texto


def test_f109_r7_ruta_capitulos_es_casi_unica_y_no_sirve_para_unir() -> None:
    texto = _columna("stg.partidas", "ruta_capitulos")

    faltan = _faltan(
        texto, "casi", "155", "162", "25 obras", "38", "2026-09-25",
        "partida_id", "no para unir",
    )
    assert faltan == [], f"a la ficha de stg.partidas.ruta_capitulos le falta {faltan}"


def test_f109_r8_el_codigo_no_identifica_la_partida_en_consumo() -> None:
    for ficha, columna in (
        ("compras.v_pbi_partida_coste", "codigo_partida"),
        ("mart.v_pbi_dim_partida", "codigo_partida"),
        ("mart.v_pbi_dim_partida", "partida_label"),
    ):
        texto = _columna(ficha, columna)
        assert "partida_id" in texto, f"{ficha}.{columna} no manda unir por partida_id"
        assert "no identifica" in texto, f"{ficha}.{columna} no dice que no identifica"


def test_f109_r8_partida_label_avisa_de_las_homonimas() -> None:
    texto = _columna("mart.v_pbi_dim_partida", "partida_label")

    faltan = _faltan(texto, "4.127", "2026-09-25", "segmentador")
    assert faltan == [], f"partida_label no avisa de las homonimas: falta {faltan}"


# ---------------------------------------------------------------------------
# La regla dura (R9-R12)
# ---------------------------------------------------------------------------


def test_f109_r9_la_regla_existe_es_bloqueante_y_cubre_el_ambito() -> None:
    regla = _regla()

    assert regla.severidad == "bloqueante"
    faltan = sorted(set(AMBITO_MINIMO) - set(regla.ambito))
    assert faltan == [], f"el ambito de {CODIGO_REGLA} no cubre {faltan}"


def test_f109_r10_la_regla_manda_unir_por_partida_id_con_las_cifras() -> None:
    regla = _regla()
    texto = _norm(f"{regla.regla} {regla.motivo}")

    faltan = _faltan(
        texto, "partida_id", "5.202", "158", "2026-09-25",
        "0437", "883.460,55", "3.474.491,83",
    )
    assert faltan == [], f"{CODIGO_REGLA} no cita {faltan}"


def test_f109_r10_la_regla_lleva_la_redaccion_aprobada_por_el_humano() -> None:
    """D2 (2026-09-26): lo prohibido es UNIR por obra + código; AGRUPAR por
    código se permite declarándolo; ante el usuario, la ruta de capítulos."""
    texto = _norm(_regla().regla)

    faltan = _faltan(
        texto,
        "No cruces tablas por obra + código de partida: usa partida_id.",
        "Agrupar por código es válido si se quiere sumar todas las copias del "
        "concepto (por ejemplo, la misma partida en todos los bloques o fases), "
        "y hay que decirlo.",
        "Para identificar una partida ante el usuario, enseña su ruta de capítulos.",
    )
    assert faltan == [], f"{CODIGO_REGLA} no lleva la redaccion aprobada: {faltan}"
    assert "funde partidas distintas" not in texto, (
        "la regla vuelve a prohibir AGRUPAR por codigo, y el humano lo permite"
    )


def test_f109_r11_los_avisos_llevan_la_regla_a_las_siete_fichas() -> None:
    derivado = derivar_avisos(_diccionario()).por_nombre

    sin_aviso = [n for n in AMBITO_MINIMO if CODIGO_REGLA not in derivado[n].avisos]
    assert sin_aviso == [], f"{CODIGO_REGLA} no llega como aviso a {sin_aviso}"


def test_f109_r12_el_diccionario_real_valida_sin_errores() -> None:
    import main

    ajustes = SimpleNamespace(postgres=SimpleNamespace(
        readonly_role="mcp_sigrid_dm_ro", set_role="sigrid_dm_etl",
        consumption_schema_list=["mart"],
    ))
    pasos = tuple(p.name for p in main.build_pipeline_steps(ajustes))
    errores = validar(_diccionario(), pasos)

    assert errores == [], "\n".join(f"{e.objeto}: {e.detalle}" for e in errores[:10])


def test_f109_r12_la_regla_cumple_las_exigencias_de_f006() -> None:
    regla = _regla()
    indice = _diccionario().por_nombre

    assert len(regla.regla.strip()) >= 40
    assert len(regla.motivo.strip()) >= 30
    assert len(regla.titulo.strip()) >= MINIMOS_TEXTO["significado"]
    sin_ficha = [a for a in regla.ambito if "." in a and a not in indice]
    assert sin_ficha == [], f"ambito que no resuelve contra el diccionario: {sin_ficha}"


# ---------------------------------------------------------------------------
# Los nombres resueltos por código (R13-R15; el arreglo es F-111)
# ---------------------------------------------------------------------------


def test_f109_r13_niveles_avisan_del_nombre_por_codigo() -> None:
    texto = _columna("mart.v_pbi_dim_partida_niveles", "nivel_1")

    faltan = _faltan(
        texto, "(obra, codigo)", "max(descripcion_corta)", "10.593", "4.657",
        "2026-09-25", "F-111",
    )
    assert faltan == [], f"nivel_1 no avisa del nombre resuelto por codigo: {faltan}"

    for n in range(2, 7):
        otro = _columna("mart.v_pbi_dim_partida_niveles", f"nivel_{n}")
        assert "igual que nivel_1" in otro, f"nivel_{n} no remite al aviso de nivel_1"


def test_f109_r14_dimension_ci_avisa_de_que_funde_homonimos() -> None:
    for columna in ("grupo_nombre", "subcategoria_nombre"):
        texto = _columna("cierre.v_pbi_dim_subcategoria_ci", columna)
        faltan = _faltan(texto, "codigo", "0444", "CI-FII", "F-111")
        assert faltan == [], f"cierre.v_pbi_dim_subcategoria_ci.{columna}: falta {faltan}"


def test_f109_r15_solo_dos_ficheros_agrupan_por_obra_y_codigo() -> None:
    """Trinquete: hoy los dos que resuelven NOMBRES (F-111). Si aparece otro, el
    test lo nombra; si uno deja de hacerlo, hay que sacarlo de la lista."""
    encontrados = _sql_que_agrupa(DIR_SQL)

    assert _comprobar_trinquete(DIR_SQL) == []
    assert encontrados == AGRUPAN_POR_OBRA_Y_CODIGO, (
        f"la lista ha bajado: {sorted(AGRUPAN_POR_OBRA_Y_CODIGO - encontrados)} ya no "
        f"agrupa por (obra_id, codigo_partida). Sacalo de AGRUPAN_POR_OBRA_Y_CODIGO"
    )


def test_f109_r15_el_trinquete_muerde_y_nombra_el_fichero(tmp_path: Path) -> None:
    """Caso sintético: los dos ficheros permitidos más un tercero que agrupa
    igual. El trinquete tiene que nombrar al tercero y solo a él."""
    for relativo in AGRUPAN_POR_OBRA_Y_CODIGO:
        destino = tmp_path / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            "SELECT obra_id, codigo_partida FROM stg.partidas\n"
            "GROUP BY obra_id, codigo_partida;\n",
            encoding="utf-8",
        )
    intruso = tmp_path / "compras" / "99_nuevo.sql"
    intruso.parent.mkdir(parents=True)
    intruso.write_text(
        "select p.nombre from stg.partidas p\n"
        "group   by obra_id ,\n  codigo_partida;\n",
        encoding="utf-8",
    )
    (tmp_path / "mart" / "98_bien.sql").write_text(
        "SELECT partida_id FROM stg.partidas GROUP BY partida_id;\n", encoding="utf-8"
    )

    errores = _comprobar_trinquete(tmp_path)

    assert len(errores) == 1, errores
    assert "compras/99_nuevo.sql" in errores[0]


# ---------------------------------------------------------------------------
# Versión y documentación (R16, R17)
# ---------------------------------------------------------------------------


def test_f109_r16_la_version_sube() -> None:
    """D4: `main` está en la 34 (F-108 33, F-110 34); F-109 sube a la 35. No se
    clava el número exacto: otra feature puede fusionar antes."""
    global_ = yaml.safe_load((DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8"))

    assert int(global_["version"]) >= 35


def test_f109_r16_la_historia_de_la_version_nombra_f109() -> None:
    cabecera = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")

    assert re.search(r"^# version \d+ \(F-109, ", cabecera, re.M), (
        "00_global.yaml no lleva el comentario de historia de la version de F-109"
    )


def test_f109_r17_arquitectura_documenta_el_codigo_no_unico() -> None:
    texto = _norm(DOC_ARQUITECTURA.read_text(encoding="utf-8"))

    faltan = _faltan(
        texto,
        "el codigo de partida no es unico ni dentro de su obra (f-109)",
        "partida_id", "contrato", "raices paralelas", "5.202",
    )
    assert faltan == [], f"ARCHITECTURE.md no documenta F-109: falta {faltan}"
