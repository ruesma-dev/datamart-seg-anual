# tests/test_f108_claves_alternativas.py
"""
F-108 · Las claves alternativas del diccionario, vigiladas por `check-unicidad`.

Origen: las desviaciones 4 y 6 de F-102. `maestro.obras.clave_obra` y
`personal.recursos.clave_recurso` son unicas (922/922 y 2.619/2.619 el
2026-09-24), pero nadie lo vigilaba en la base porque `check-unicidad` solo
lee `clave_negocio`; y las cinco relaciones de `compras` por `clave_obra` se
declaraban `N:N` porque el validador solo aceptaba el lado 1 sobre la clave de
negocio o una `clave_sustituta`. Decision del humano (opcion B, 2026-09-24):
claves alternativas declaradas, que el validador acepta y `check-unicidad`
comprueba; sin indice unico, para no tumbar la nocturna.

Sin red ni BBDD: fichas sinteticas, el diccionario real y un doble del cliente
de Postgres (como `_PgUnicidad` de `test_f006_comandos.py`).
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re
from functools import lru_cache

import pytest
import yaml
from click.testing import CliRunner

from etl_sigrid.domain.diccionario import (
    Columna,
    Diccionario,
    Ficha,
    Relacion,
    _es_unica_por,
    validar,
)
from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
    DiccionarioIlegible,
    cargar_diccionario,
)
from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_diccionario
from etl_sigrid.infrastructure.postgres.unicidad_sql import (
    ConsultaUnicidad,
    consultas_de_unicidad,
    interpretar_resultado,
    veredicto_no_comprobado,
)
from tests._texto import contiene

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

PASOS_NOCTURNOS = ("ingest_raw", "load_excel_aux", "build_stg", "build_mart")

VISTAS_COMPRAS_CON_CLAVE_OBRA = (
    "v_pbi_proveedor_obra",
    "v_pbi_partida_coste",
    "v_pbi_contrato_consumo",
    "v_pbi_albaranes_sin_facturar",
    "v_control_forma_pago",
)

#: Las seis claves alternativas que declara F-108 (R20 y R22, con D3 aprobada).
DECLARADAS = {
    "maestro.obras": (("clave_obra",),),
    "personal.recursos": (("clave_recurso",),),
    "maestro.v_obra_fichas": (("clave_obra",),),
    "maestro.cuentas_analiticas": (("empresa_id", "codigo_cuenta"),),
    "maestro.centros_coste": (("empresa", "codigo_centro"),),
    "stg.obras": (("codigo_obra",),),
}


@lru_cache(maxsize=1)
def _dicc_real() -> Diccionario:
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _ficha(**kwargs) -> Ficha:
    base = dict(
        esquema="maestro",
        objeto="obras",
        tipo="vista",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano="Una fila por ficha de obra, que es su clave.",
        clave_negocio=("obra_id",),
        paso_etl="build_maestros",
        refresco="nocturno",
        columnas=(
            Columna(nombre="obra_id", significado="S" * 40),
            Columna(nombre="clave_obra", significado="S" * 40),
            Columna(nombre="empresa_id", significado="S" * 40),
            Columna(nombre="codigo_obra", significado="S" * 40),
        ),
        relaciones=(),
        ejemplos_preguntas=("Que obras tiene la empresa X",),
    )
    base.update(kwargs)
    return Ficha(**base)


def _origen(*relaciones: Relacion, **kwargs) -> Ficha:
    base = dict(
        esquema="compras",
        objeto="v_pbi_proveedor_obra",
        clave_negocio=("proveedor_id", "obra_id"),
        grano="Una fila por proveedor y obra, que es su clave.",
        columnas=(
            Columna(nombre="proveedor_id", significado="S" * 40),
            Columna(nombre="obra_id", significado="S" * 40),
            Columna(nombre="clave_obra", significado="S" * 40),
            Columna(nombre="codigo_obra", significado="S" * 40),
        ),
        relaciones=relaciones,
    )
    base.update(kwargs)
    return _ficha(**base)


def _relacion(**kwargs) -> Relacion:
    base = dict(
        de="clave_obra",
        a="maestro.obras.clave_obra",
        cardinalidad="N:1",
        porque="P" * 40,
    )
    base.update(kwargs)
    return Relacion(**base)


def _dicc(*fichas: Ficha) -> Diccionario:
    return Diccionario(
        version="1",
        base="sigrid_dm",
        fichas=fichas,
        reglas=(),
        esquemas={},
        pendientes=(),
        global_raw={},
    )


def _errores_de_alternativas(ficha: Ficha) -> list:
    """Los errores R2 que habla de claves alternativas, y solo esos.

    Una ficha sintetica produce otros errores ajenos (esquemas sin entrada en el
    global, reglas); aqui solo interesa lo que dice F-108.
    """
    return [
        e
        for e in validar(_dicc(ficha), PASOS_NOCTURNOS)
        if e.regla == "R2" and "claves_alternativas" in e.detalle
    ]


def _errores_de_cardinalidad(dicc: Diccionario) -> list:
    return [
        e
        for e in validar(dicc, PASOS_NOCTURNOS)
        if e.regla == "R5" and "fan-out" in e.detalle
    ]


def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Cargador (R1, R2): escribe YAML en tmp_path
# ---------------------------------------------------------------------------

GLOBAL_MINIMO = """
version: 1
base: sigrid_dm
esquemas:
  mart:
    titulo: Seguimiento mensual
    para_que_sirve: Superficie principal de consumo.
    consumo_recomendado: true
    refresco: nocturno
    pasos_etl: [build_mart]
reglas: []
pendientes: []
"""

MART_CON_ALTERNATIVAS = """
version: 1
esquema: mart
objetos:
  obras:
    tipo: tabla
    capa: consumo
    consumo_recomendado: true
    descripcion: Las obras.
    grano: Una fila por obra.
    clave_negocio: [obra_id]
{claves}
    paso_etl: build_mart
    refresco: nocturno
    columnas:
      obra_id: El identificador tecnico de la obra.
      clave_obra: La clave legible de la obra.
      empresa_id: La empresa de la ficha.
      codigo_obra: El codigo de la obra en Sigrid.
    relaciones: []
    ejemplos_preguntas:
      - Que obras hay
"""


def _directorio(tmp_path, claves: str) -> pathlib.Path:
    destino = tmp_path / "diccionario"
    destino.mkdir()
    (destino / "00_global.yaml").write_text(GLOBAL_MINIMO, encoding="utf-8")
    (destino / "mart.yaml").write_text(
        MART_CON_ALTERNATIVAS.format(claves=claves), encoding="utf-8"
    )
    return destino


def test_f108_r1_el_cargador_lee_claves_alternativas(tmp_path) -> None:
    directorio = _directorio(
        tmp_path,
        "    claves_alternativas: [[clave_obra], [empresa_id, codigo_obra]]",
    )
    dicc, _ = cargar_diccionario(directorio)
    (ficha,) = dicc.fichas
    assert ficha.claves_alternativas == (
        ("clave_obra",),
        ("empresa_id", "codigo_obra"),
    )


def test_f108_r1_sin_la_clave_la_ficha_se_comporta_como_hoy(tmp_path) -> None:
    dicc, _ = cargar_diccionario(_directorio(tmp_path, ""))
    (ficha,) = dicc.fichas
    assert ficha.claves_alternativas == ()
    # Y quien construye una Ficha sin nombrarla sigue funcionando.
    assert _ficha().claves_alternativas == ()


@pytest.mark.parametrize(
    "forma",
    [
        "clave_obra",  # escalar
        "[clave_obra]",  # lista plana: ambigua, no se adivina
        "[[]]",  # clave vacia
        "[]",  # lista sin claves: declarar nada no es declarar
        "{clave_obra: 1}",  # mapa
        "[[clave_obra], clave_obra]",  # mezcla
        "[[[clave_obra]]]",  # una columna que no es texto
    ],
)
def test_f108_r2_una_forma_invalida_no_se_carga(tmp_path, forma: str) -> None:
    directorio = _directorio(tmp_path, f"    claves_alternativas: {forma}")
    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    errores = [e for e in excinfo.value.errores if "claves_alternativas" in e.detalle]
    assert len(errores) == 1, excinfo.value.errores
    (error,) = errores
    assert error.regla == "R1"
    assert error.objeto == "mart.obras"
    assert "mart.obras" in error.detalle, "el error nombra la ficha"
    assert "[[clave_obra]]" in error.detalle, "y ensena la forma correcta"


# ---------------------------------------------------------------------------
# Validacion de la ficha (R3, R4, R5)
# ---------------------------------------------------------------------------


def test_f108_r3_una_clave_bien_formada_no_da_error() -> None:
    ficha = _ficha(claves_alternativas=(("clave_obra",), ("empresa_id", "codigo_obra")))
    assert _errores_de_alternativas(ficha) == []


def test_f108_r3_una_columna_no_documentada_es_error_r2() -> None:
    ficha = _ficha(claves_alternativas=(("clave_fantasma",),))
    (error,) = _errores_de_alternativas(ficha)
    assert "`clave_fantasma`" in error.detalle
    assert error.objeto == "maestro.obras"


def test_f108_r3_una_ficha_sin_columnas_no_puede_declararlas() -> None:
    ficha = _ficha(columnas=(), claves_alternativas=(("clave_obra",),))
    (error,) = _errores_de_alternativas(ficha)
    assert contiene(error.detalle, "no documenta columnas")


@pytest.mark.parametrize(
    ("claves", "motivo"),
    [
        ((("clave_obra", "clave_obra"),), "repite la columna"),
        ((("obra_id",),), "clave_negocio"),
        ((("clave_obra",), ("clave_obra",)), "repite otra"),
        ((("empresa_id", "codigo_obra"), ("codigo_obra", "empresa_id")), "repite otra"),
        (((),), "vacia"),
    ],
)
def test_f108_r4_repeticiones_y_claves_vacias_son_error_r2(claves, motivo: str) -> None:
    errores = _errores_de_alternativas(_ficha(claves_alternativas=claves))
    assert len(errores) == 1, errores
    assert contiene(errores[0].detalle, motivo), errores[0].detalle


def test_f108_r4_igual_a_la_clave_de_negocio_como_conjunto() -> None:
    ficha = _ficha(
        clave_negocio=("empresa_id", "codigo_obra"),
        claves_alternativas=(("codigo_obra", "empresa_id"),),
    )
    (error,) = _errores_de_alternativas(ficha)
    assert contiene(error.detalle, "clave_negocio")


def test_f108_r5_una_funcion_no_declara_claves_alternativas() -> None:
    ficha = _ficha(tipo="funcion", claves_alternativas=(("clave_obra",),))
    (error,) = _errores_de_alternativas(ficha)
    assert contiene(error.detalle, "funcion")


# ---------------------------------------------------------------------------
# El validador de relaciones las acepta como lado 1 (R6, R7, R8)
# ---------------------------------------------------------------------------


def test_f108_r6_una_alternativa_de_una_columna_es_unica() -> None:
    destino = _ficha(claves_alternativas=(("clave_obra",),))
    assert _es_unica_por(destino, "clave_obra") is True
    # Sin declararla, sigue sin serlo: el tercer caso es la declaracion.
    assert _es_unica_por(_ficha(), "clave_obra") is False


def test_f108_r6_el_lado_1_derecho_por_alternativa_valida() -> None:
    destino = _ficha(claves_alternativas=(("clave_obra",),))
    dicc = _dicc(_origen(_relacion(cardinalidad="N:1")), destino)
    assert _errores_de_cardinalidad(dicc) == []


def test_f108_r6_el_lado_1_izquierdo_por_alternativa_valida() -> None:
    origen = _ficha(
        claves_alternativas=(("clave_obra",),),
        relaciones=(
            _relacion(
                de="clave_obra",
                a="compras.v_pbi_proveedor_obra.clave_obra",
                cardinalidad="1:N",
            ),
        ),
    )
    dicc = _dicc(origen, _origen())
    assert _errores_de_cardinalidad(dicc) == []


def test_f108_r6_sin_alternativa_el_mismo_n_1_sigue_siendo_error() -> None:
    """El control: la relacion de arriba es error sin la declaracion."""
    dicc = _dicc(_origen(_relacion(cardinalidad="N:1")), _ficha())
    assert len(_errores_de_cardinalidad(dicc)) == 1


def test_f108_r7_una_columna_de_una_alternativa_compuesta_no_es_unica() -> None:
    cuentas = _ficha(
        objeto="cuentas_analiticas",
        clave_negocio=("cuenta_analitica_id",),
        columnas=(
            Columna(nombre="cuenta_analitica_id", significado="S" * 40),
            Columna(nombre="empresa_id", significado="S" * 40),
            Columna(nombre="codigo_cuenta", significado="S" * 40),
        ),
        claves_alternativas=(("empresa_id", "codigo_cuenta"),),
    )
    assert _es_unica_por(cuentas, "codigo_cuenta") is False
    origen = _origen(
        _relacion(de="codigo_obra", a="maestro.cuentas_analiticas.codigo_cuenta"),
    )
    assert len(_errores_de_cardinalidad(_dicc(origen, cuentas))) == 1


def test_f108_r8_el_rechazo_cita_las_claves_alternativas_del_extremo() -> None:
    destino = _ficha(claves_alternativas=(("empresa_id", "codigo_obra"),))
    origen = _origen(_relacion(de="codigo_obra", a="maestro.obras.codigo_obra"))
    (error,) = _errores_de_cardinalidad(_dicc(origen, destino))
    assert "su clave es ['obra_id']" in error.detalle
    assert "claves alternativas: [['empresa_id', 'codigo_obra']]" in error.detalle


def test_f108_r8_sin_alternativas_el_mensaje_es_el_de_hoy() -> None:
    origen = _origen(_relacion(de="codigo_obra", a="maestro.obras.codigo_obra"))
    (error,) = _errores_de_cardinalidad(_dicc(origen, _ficha()))
    assert "(su clave es ['obra_id'])" in error.detalle
    assert "claves alternativas" not in error.detalle


# ---------------------------------------------------------------------------
# Las consultas de `check-unicidad` (R9, R10, R11)
# ---------------------------------------------------------------------------


def test_f108_r9_una_consulta_por_clave_alternativa_tras_la_de_negocio() -> None:
    ficha = _ficha(claves_alternativas=(("clave_obra",), ("empresa_id", "codigo_obra")))
    consultas = consultas_de_unicidad(_dicc(ficha))
    assert [(c.objeto, c.clave, c.tipo_clave) for c in consultas] == [
        ("maestro.obras", ("obra_id",), "negocio"),
        ("maestro.obras", ("clave_obra",), "alternativa"),
        ("maestro.obras", ("empresa_id", "codigo_obra"), "alternativa"),
    ]


def test_f108_r9_la_alternativa_se_comprueba_aunque_se_salte_la_de_negocio() -> None:
    sustituta = _ficha(
        objeto="con_sustituta",
        columnas=(
            Columna(nombre="obra_id", significado="S" * 40, agregacion="clave_sustituta"),
            Columna(nombre="clave_obra", significado="S" * 40),
        ),
        claves_alternativas=(("clave_obra",),),
    )
    sin_clave = _ficha(
        objeto="sin_clave",
        clave_negocio=(),
        claves_alternativas=(("clave_obra",),),
    )
    consultas = consultas_de_unicidad(_dicc(sustituta, sin_clave))
    assert [(c.objeto, c.tipo_clave) for c in consultas] == [
        ("maestro.con_sustituta", "alternativa"),
        ("maestro.sin_clave", "alternativa"),
    ]


def test_f108_r9_mismo_alcance_que_la_de_negocio() -> None:
    interna = _ficha(
        objeto="interna",
        consumo_recomendado=False,
        claves_alternativas=(("clave_obra",),),
    )
    funcion = _ficha(objeto="f", tipo="funcion", claves_alternativas=(("clave_obra",),))
    assert consultas_de_unicidad(_dicc(interna, funcion)) == []
    todas = consultas_de_unicidad(_dicc(interna, funcion), solo_consumo=False)
    assert [(c.objeto, c.tipo_clave) for c in todas] == [
        ("maestro.interna", "negocio"),
        ("maestro.interna", "alternativa"),
    ]


def test_f108_r10_tipo_clave_por_defecto_es_negocio() -> None:
    consulta = ConsultaUnicidad(objeto="a.b", clave=("c",), sql="x", sql_detalle="y")
    assert consulta.tipo_clave == "negocio"


def test_f108_r11_la_alternativa_excluye_los_null_y_no_usa_distinct() -> None:
    ficha = _ficha(claves_alternativas=(("empresa_id", "codigo_obra"),))
    (_, alternativa) = consultas_de_unicidad(_dicc(ficha))
    assert alternativa.sql == (
        "SELECT count(*) AS claves_duplicadas,\n"
        "       COALESCE(sum(filas), 0) AS filas_implicadas\n"
        "FROM (\n"
        "    SELECT empresa_id, codigo_obra, count(*) AS filas\n"
        "    FROM maestro.obras\n"
        "    WHERE empresa_id IS NOT NULL AND codigo_obra IS NOT NULL\n"
        "    GROUP BY empresa_id, codigo_obra\n"
        "    HAVING count(*) > 1\n"
        ") AS duplicadas"
    )
    assert alternativa.sql_detalle == (
        "SELECT empresa_id, codigo_obra, count(*) AS filas\n"
        "FROM maestro.obras\n"
        "WHERE empresa_id IS NOT NULL AND codigo_obra IS NOT NULL\n"
        "GROUP BY empresa_id, codigo_obra\n"
        "HAVING count(*) > 1\n"
        "ORDER BY filas DESC\n"
        "LIMIT 20"
    )
    assert "DISTINCT" not in alternativa.sql.upper()


def test_f108_r11_la_de_negocio_sale_byte_a_byte_como_hoy() -> None:
    ficha = _ficha(claves_alternativas=(("clave_obra",),))
    (negocio, _) = consultas_de_unicidad(_dicc(ficha))
    assert negocio.sql == (
        "SELECT count(*) AS claves_duplicadas,\n"
        "       COALESCE(sum(filas), 0) AS filas_implicadas\n"
        "FROM (\n"
        "    SELECT obra_id, count(*) AS filas\n"
        "    FROM maestro.obras\n"
        "    GROUP BY obra_id\n"
        "    HAVING count(*) > 1\n"
        ") AS duplicadas"
    )
    assert "WHERE" not in negocio.sql_detalle


def test_f108_r11_una_columna_alternativa_no_interpolable_se_rechaza() -> None:
    ficha = _ficha(claves_alternativas=(("clave_obra; DROP TABLE x",),))
    with pytest.raises(ValueError, match="no interpolable"):
        consultas_de_unicidad(_dicc(ficha))


# ---------------------------------------------------------------------------
# Veredictos (R12, R13)
# ---------------------------------------------------------------------------


def _alternativa() -> ConsultaUnicidad:
    ficha = _ficha(claves_alternativas=(("clave_obra",),))
    return consultas_de_unicidad(_dicc(ficha))[1]


def test_f108_r12_el_ko_de_una_alternativa_dice_que_es_y_que_rompe() -> None:
    consulta = _alternativa()
    texto = interpretar_resultado(consulta, 3, 7)
    assert texto.startswith("KO   maestro.obras")
    assert "clave alternativa (clave_obra)" in texto
    assert "3 combinacion(es)" in texto and "7 filas" in texto
    assert contiene(texto, "fan-out") and "`N:1`" in texto
    assert consulta.sql_detalle in texto


def test_f108_r13_el_ok_de_una_alternativa_conserva_la_advertencia() -> None:
    texto = interpretar_resultado(_alternativa(), 0, 0)
    assert texto.startswith("OK   maestro.obras")
    assert "clave alternativa (clave_obra)" in texto
    assert "No prueba que sea correcta" in texto


def test_f108_r13_el_timeout_de_una_alternativa_no_es_un_ok() -> None:
    texto = veredicto_no_comprobado(_alternativa(), "timeout de 30s")
    assert "NO COMPROBADO" in texto and "No es un OK" in texto
    assert "clave alternativa (clave_obra)" in texto


def test_f108_r12_r13_la_de_negocio_no_cambia_de_texto() -> None:
    ficha = _ficha(claves_alternativas=(("clave_obra",),))
    negocio = consultas_de_unicidad(_dicc(ficha))[0]
    assert "alternativa" not in interpretar_resultado(negocio, 0, 0)
    assert "alternativa" not in interpretar_resultado(negocio, 1, 2)
    assert "alternativa" not in veredicto_no_comprobado(negocio, "t")


# ---------------------------------------------------------------------------
# El comando (R12, R14, R15) con el diccionario real y un doble del cliente
# ---------------------------------------------------------------------------


class _PgPorClave:
    """Responde por (objeto, tipo de clave) y anota que se le pregunto."""

    def __init__(self, respuestas=None, por_defecto=(0, 0)):
        self.respuestas = respuestas or {}
        self.por_defecto = por_defecto
        self.preguntadas: list[tuple[str, str, tuple[str, ...]]] = []

    def comprobar_unicidad(self, consulta, timeout_s):
        self.preguntadas.append((consulta.objeto, consulta.tipo_clave, consulta.clave))
        return self.respuestas.get(
            (consulta.objeto, consulta.tipo_clave), self.por_defecto
        )


def _invocar(monkeypatch, pg, *argumentos: str):
    import main

    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    return CliRunner().invoke(main.cli, ["check-unicidad", *argumentos])


def test_f108_r12_una_alternativa_rota_sale_con_uno(monkeypatch) -> None:
    pg = _PgPorClave(respuestas={("maestro.obras", "alternativa"): (2, 4)})
    resultado = _invocar(monkeypatch, pg)

    assert resultado.exit_code == 1, resultado.output
    assert ("maestro.obras", "alternativa", ("clave_obra",)) in pg.preguntadas
    assert "KO   maestro.obras: la clave alternativa (clave_obra)" in resultado.output
    assert "1 con la clave rota" in resultado.output


def test_f108_r12_todo_limpio_con_alternativas_sale_con_cero(monkeypatch) -> None:
    pg = _PgPorClave()
    resultado = _invocar(monkeypatch, pg)
    assert resultado.exit_code == 0, resultado.output
    alternativas = [p for p in pg.preguntadas if p[1] == "alternativa"]
    assert len(alternativas) == len(DECLARADAS), alternativas
    assert "0 con la clave rota" in resultado.output


def test_f108_r13_un_timeout_en_una_alternativa_no_es_un_ok(monkeypatch) -> None:
    pg = _PgPorClave(respuestas={("personal.recursos", "alternativa"): None})
    resultado = _invocar(monkeypatch, pg)
    assert resultado.exit_code == 1
    assert "?    personal.recursos: NO COMPROBADO" in resultado.output
    assert "1 sin comprobar" in resultado.output


def test_f108_r14_un_objeto_que_no_existe_se_informa_una_vez(monkeypatch) -> None:
    pg = _PgPorClave(respuestas={("maestro.obras", "negocio"): "NO_EXISTE"})
    resultado = _invocar(monkeypatch, pg)

    assert resultado.exit_code == 1
    assert resultado.output.count("maestro.obras: FICHADO Y NO EXISTE") == 1
    assert "1 fichados que no existen" in resultado.output
    assert [p for p in pg.preguntadas if p[0] == "maestro.obras"] == [
        ("maestro.obras", "negocio", ("obra_id",))
    ], "las demas consultas del objeto no se lanzan"
    assert "0 con la clave rota" in resultado.output
    # La consulta omitida no se cuenta como OK: de todas, una no existe y otra
    # (la alternativa de `maestro.obras`) ni se lanzo. Superviviente de T10.
    total = len(consultas_de_unicidad(_dicc_real()))
    assert f"Resumen: {total - 2} sin contradiccion" in resultado.output
    # El recorrido sigue con los demas objetos.
    assert ("personal.recursos", "alternativa", ("clave_recurso",)) in pg.preguntadas


def test_f108_r15_el_dry_run_rotula_las_alternativas_sin_conectar(monkeypatch) -> None:
    pg = _PgPorClave()
    resultado = _invocar(monkeypatch, pg, "--dry-run")

    assert resultado.exit_code == 0, resultado.output
    assert pg.preguntadas == []
    assert "-- maestro.obras  clave: (obra_id)" in resultado.output
    assert "-- maestro.obras  clave alternativa: (clave_obra)" in resultado.output
    assert (
        "-- maestro.cuentas_analiticas  clave alternativa: (empresa_id, codigo_cuenta)"
        in resultado.output
    )
    assert "IS NOT NULL" in resultado.output
    total = len(consultas_de_unicidad(_dicc_real()))
    assert f"{total} comprobacion(es) ({len(DECLARADAS)} de clave alternativa)" in (
        resultado.output
    )


# ---------------------------------------------------------------------------
# Guardas de la opcion B y de la premisa del fan-out (R16, R17)
# ---------------------------------------------------------------------------


def test_f108_r16_la_nocturna_no_ejecuta_check_unicidad() -> None:
    import main

    for fuente in (
        inspect.getsource(main.build_pipeline_steps),
        inspect.getsource(main.run_all.callback),
    ):
        assert "unicidad" not in fuente
    for fichero in (RAIZ / "infra").rglob("*"):
        if fichero.is_file() and fichero.suffix in {".ps1", ".sh", ".yaml", ".yml"}:
            assert "check-unicidad" not in fichero.read_text(
                encoding="utf-8", errors="replace"
            ), fichero


def test_f108_r16_ningun_sql_crea_un_indice_unico_sobre_las_claves_legibles() -> None:
    patron = re.compile(r"UNIQUE[^;]*\b(clave_obra|clave_recurso)\b", re.IGNORECASE)
    ficheros = list(DIR_SQL.rglob("*.sql"))
    assert len(ficheros) > 50, "el barrido no ha visto el SQL"
    culpables = [
        str(f.relative_to(RAIZ)) for f in ficheros
        if patron.search(f.read_text(encoding="utf-8"))
    ]
    assert culpables == [], (
        f"{culpables}: la opcion B descarto el indice unico; un duplicado "
        f"tumbaria el build esa noche"
    )


def _lados_uno_por_alternativa() -> set[tuple[str, tuple[str, ...]]]:
    """(objeto, (columna,)) de todo lado 1 que solo sostiene una alternativa."""
    dicc = _dicc_real()
    indice = dicc.por_nombre
    lados: set[tuple[str, tuple[str, ...]]] = set()

    def por_alternativa(ficha: Ficha, columna: str) -> bool:
        if tuple(ficha.clave_negocio) == (columna,):
            return False
        if any(
            c.nombre == columna and c.agregacion == "clave_sustituta"
            for c in ficha.columnas
        ):
            return False
        return (columna,) in ficha.claves_alternativas

    for ficha in dicc.fichas:
        for relacion in ficha.relaciones:
            if ":" not in (relacion.cardinalidad or ""):
                continue
            izquierda, derecha = relacion.cardinalidad.split(":")
            partes = relacion.a.split(".")
            if izquierda == "1" and por_alternativa(ficha, relacion.de):
                lados.add((ficha.nombre, (relacion.de,)))
            destino = indice.get(".".join(partes[:2]))
            if derecha == "1" and destino and por_alternativa(destino, partes[2]):
                lados.add((destino.nombre, (partes[2],)))
    return lados


def test_f108_r17_control_hay_lados_uno_sostenidos_por_alternativa() -> None:
    assert ("maestro.obras", ("clave_obra",)) in _lados_uno_por_alternativa()


def test_f108_r17_cada_lado_uno_por_alternativa_se_comprueba_en_la_base() -> None:
    comprobadas = {
        (c.objeto, c.clave)
        for c in consultas_de_unicidad(_dicc_real(), solo_consumo=False)
        if c.tipo_clave == "alternativa"
    }
    sin_verificar = sorted(_lados_uno_por_alternativa() - comprobadas)
    assert sin_verificar == [], (
        f"{sin_verificar} sostienen un lado `1` por una clave alternativa y "
        f"`check-unicidad` no la comprueba ni con `--todos`"
    )


# ---------------------------------------------------------------------------
# Publicacion (R18) y version (R19)
# ---------------------------------------------------------------------------


def test_f108_r18_el_jsonb_publica_las_claves_solo_si_las_hay() -> None:
    con = _ficha(claves_alternativas=(("clave_obra",), ("empresa_id", "codigo_obra")))
    sin = _ficha(objeto="sin")
    filas = {fila[1]: fila for fila in filas_diccionario(_dicc(con, sin))}

    assert all(len(fila) == 14 for fila in filas.values()), "sin columnas nuevas"
    assert json.loads(filas["obras"][-1])["claves_alternativas"] == [
        ["clave_obra"],
        ["empresa_id", "codigo_obra"],
    ]
    assert "claves_alternativas" not in json.loads(filas["sin"][-1])
    assert filas["obras"][8] == ["obra_id"], "la columna clave_negocio no cambia"


def test_f108_r19_la_version_sube_a_33() -> None:
    # F-108 la sube a la siguiente de `main` (32 -> 33, decision D5): lo que se
    # fija es que la subio; una feature posterior puede subirla mas.
    assert int(_yaml("00_global.yaml")["version"]) >= 33
    cabecera = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "version 33 (F-108" in cabecera


# ---------------------------------------------------------------------------
# Las claves declaradas (R20, R21, R22)
# ---------------------------------------------------------------------------


def _significado(nombre: str, columna: str) -> str:
    ficha = _dicc_real().por_nombre[nombre]
    return next(c.significado for c in ficha.columnas if c.nombre == columna)


@pytest.mark.parametrize("nombre", ["maestro.obras", "personal.recursos"])
def test_f108_r20_las_dos_claves_de_f102_estan_declaradas(nombre: str) -> None:
    ficha = _dicc_real().por_nombre[nombre]
    assert ficha.claves_alternativas == DECLARADAS[nombre]
    for columna in DECLARADAS[nombre][0]:
        texto = _significado(nombre, columna)
        assert contiene(texto, "clave alternativa") and "check-unicidad" in texto


@pytest.mark.parametrize("vista", VISTAS_COMPRAS_CON_CLAVE_OBRA)
def test_f108_r21_las_relaciones_de_compras_por_clave_obra_son_n_1(vista: str) -> None:
    ficha = _dicc_real().por_nombre[f"compras.{vista}"]
    (relacion,) = [
        r for r in ficha.relaciones
        if r.de == "clave_obra" and r.a == "maestro.obras.clave_obra"
    ]
    assert relacion.cardinalidad == "N:1"
    assert "DE HECHO ES N:1" not in relacion.porque
    assert not contiene(relacion.porque, "se declara N:N")
    assert contiene(relacion.porque, "clave alternativa")
    assert "check-unicidad" in relacion.porque


@pytest.mark.parametrize(
    "nombre",
    [
        "maestro.v_obra_fichas",
        "maestro.cuentas_analiticas",
        "maestro.centros_coste",
        "stg.obras",
    ],
)
def test_f108_r22_las_cuatro_claves_extra_estan_declaradas(nombre: str) -> None:
    ficha = _dicc_real().por_nombre[nombre]
    assert ficha.claves_alternativas == DECLARADAS[nombre]
    for columna in DECLARADAS[nombre][0]:
        texto = _significado(nombre, columna)
        assert contiene(texto, "clave alternativa") and "check-unicidad" in texto


def test_f108_r22_solo_estan_las_seis_aprobadas() -> None:
    """H1 (partidas) NO es unica: que nadie la declare por inercia."""
    declaradas = {
        f.nombre: f.claves_alternativas
        for f in _dicc_real().fichas
        if f.claves_alternativas
    }
    assert declaradas == DECLARADAS


# ---------------------------------------------------------------------------
# Documentacion (R24)
# ---------------------------------------------------------------------------


def test_f108_r24_la_arquitectura_explica_las_claves_alternativas() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    seccion = texto.split("### El datamart se explica solo", 1)[1].split("\n## ", 1)[0]
    assert "claves_alternativas" in seccion
    assert "check-unicidad" in seccion
    assert contiene(seccion, "lado 1") and "F-108" in seccion


def test_f108_r24_azure_apps_recoge_la_clave_nueva_del_jsonb() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    assert "claves_alternativas" in texto and "F-108" in texto
