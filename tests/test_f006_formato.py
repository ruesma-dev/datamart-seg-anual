# tests/test_f006_formato.py
"""
F-006 · Tests del formato del diccionario semántico (R1-R8).

NINGÚN test de este fichero abre red ni BBDD. `validar()` es dominio puro
(R8): recibe entidades y devuelve una lista de errores. Es a propósito, y es
lo que permite que la puerta de cobertura corra en cada `bash harness/init.sh`
sin un servidor delante.

Un principio recorre todos estos tests: **una ficha que miente es peor que una
ficha que falta**, porque el agente que lea el diccionario escribirá el SQL
igual y con aplomo. Por eso el validador es severo y por eso devuelve TODOS
los errores y no el primero.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.diccionario import (
    AGREGACIONES,
    CAPAS,
    CODIGOS_REGLAS_OBLIGATORIAS,
    ESQUEMAS_DEL_DATAMART,
    REFRESCOS,
    TIPOS,
    Columna,
    Diccionario,
    ErrorValidacion,
    Ficha,
    Regla,
    formatear_errores,
    validar,
)

# ---------------------------------------------------------------------------
# Fábricas de fixtures: una ficha válida mínima, para mutarla en cada test
# ---------------------------------------------------------------------------


def _columna(nombre: str = "obra_codigo", **kwargs) -> Columna:
    datos = {"significado": "Código de obra tal y como se teclea en Sigrid."}
    datos.update(kwargs)
    return Columna(nombre=nombre, **datos)


def _ficha(**kwargs) -> Ficha:
    """Ficha válida de referencia. Cada test cambia solo lo que prueba."""
    datos: dict = {
        "esquema": "mart",
        "objeto": "fact_seguimiento_mensual",
        "tipo": "tabla",
        "capa": "consumo",
        "consumo_recomendado": True,
        "descripcion": "El hecho central del seguimiento mensual de obra.",
        "grano": "Una fila por (obra, partida, mes, escenario).",
        "clave_negocio": ("obra_codigo",),
        "paso_etl": "build_mart",
        "refresco": "nocturno",
        "columnas": (_columna(),),
        "relaciones": (),
        "ejemplos_preguntas": ("¿Cuál es la planificación mensual de la obra X?",),
    }
    datos.update(kwargs)
    return Ficha(**datos)


def _esquemas(*nombres: str) -> dict:
    """Entradas de `esquemas` de 00_global.yaml (R4), una por esquema."""
    return {
        nombre: {
            "titulo": f"Esquema {nombre}",
            "para_que_sirve": f"Para lo que sirve {nombre}.",
            "consumo_recomendado": nombre not in ("raw", "stg"),
            "refresco": "nocturno",
            "pasos_etl": ["build_mart"],
        }
        for nombre in (nombres or ESQUEMAS_DEL_DATAMART)
    }


def _regla(codigo: str, **kwargs) -> Regla:
    """Regla dura válida de referencia, con ámbito resoluble."""
    datos: dict = {
        "codigo": codigo,
        "titulo": f"Título de {codigo}",
        "severidad": "bloqueante",
        "ambito": ("mart",),
        "regla": "Qué hacer y qué no hacer.",
        "motivo": "Por qué, con el incidente real.",
    }
    datos.update(kwargs)
    return Regla(**datos)


def _reglas_minimas() -> list[Regla]:
    """Las doce que R9 exige, en su forma mínima válida."""
    return [_regla(codigo) for codigo in CODIGOS_REGLAS_OBLIGATORIAS]


def _dicc(fichas=None, reglas=None, esquemas=None, **kwargs) -> Diccionario:
    datos: dict = {
        "version": "1",
        "base": "sigrid_dm",
        "fichas": tuple(_ficha() for _ in range(1)) if fichas is None else tuple(fichas),
        "reglas": tuple(_reglas_minimas() if reglas is None else reglas),
        "esquemas": _esquemas() if esquemas is None else esquemas,
        "pendientes": (),
        "global_raw": {},
    }
    datos.update(kwargs)
    return Diccionario(**datos)


def _codigos(errores) -> set[str]:
    return {e.regla for e in errores}


# El validador necesita saber qué pasos corren de noche (R14). En los tests de
# formato basta con el del pipeline real que usan las fichas de ejemplo.
PASOS_NOCTURNOS = ("ingest_raw", "load_excel_aux", "build_stg", "build_mart")


# ---------------------------------------------------------------------------
# R2 · Campos mínimos de una ficha
# ---------------------------------------------------------------------------


def test_f006_r2_una_ficha_completa_no_produce_errores() -> None:
    """El caso feliz: la ficha de referencia valida limpia."""
    assert validar(_dicc(), PASOS_NOCTURNOS) == []


@pytest.mark.parametrize(
    "campo",
    ["tipo", "capa", "descripcion", "refresco"],
)
def test_f006_r2_los_campos_obligatorios_vacios_fallan(campo: str) -> None:
    """Un campo obligatorio en blanco es un error, no un valor por defecto."""
    errores = validar(_dicc(fichas=[_ficha(**{campo: ""})]), PASOS_NOCTURNOS)

    assert errores, f"{campo} vacío tenía que fallar"
    assert any(campo in e.detalle for e in errores), (
        f"el error no nombra el campo culpable: {errores}"
    )
    assert all(e.objeto == "mart.fact_seguimiento_mensual" for e in errores), (
        "el error no nombra la ficha culpable"
    )


def test_f006_r2_grano_y_clave_negocio_son_obligatorios_en_tablas_y_vistas() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(grano=None, clave_negocio=())]), PASOS_NOCTURNOS
    )

    assert any("grano" in e.detalle for e in errores)
    assert any("clave_negocio" in e.detalle for e in errores)


def test_f006_r2_una_funcion_no_necesita_grano_ni_clave_negocio() -> None:
    """`grano` y `clave_negocio` no aplican a una función (design §3.4)."""
    funcion = _ficha(
        objeto="fn_mes_de_fase",
        tipo="funcion",
        grano=None,
        clave_negocio=(),
        columnas=(),
        consumo_recomendado=False,
        motivo_no_consumo="Función auxiliar; se usa dentro del SQL, no se consulta.",
        ejemplos_preguntas=(),
    )

    assert validar(_dicc(fichas=[funcion]), PASOS_NOCTURNOS) == []


def test_f006_r2_la_clave_negocio_apunta_a_columnas_de_la_propia_ficha() -> None:
    """Una clave de negocio que nombra una columna inexistente es una mentira."""
    errores = validar(
        _dicc(fichas=[_ficha(clave_negocio=("obra_codigo", "mes_que_no_existe"))]),
        PASOS_NOCTURNOS,
    )

    assert errores
    assert any("mes_que_no_existe" in e.detalle for e in errores)


@pytest.mark.parametrize(
    ("campo", "valido"),
    [("tipo", TIPOS), ("capa", CAPAS), ("refresco", REFRESCOS)],
)
def test_f006_r2_los_vocabularios_son_cerrados(campo: str, valido: tuple) -> None:
    """Un valor fuera del vocabulario falla nombrando los admitidos."""
    errores = validar(_dicc(fichas=[_ficha(**{campo: "inventado"})]), PASOS_NOCTURNOS)

    assert errores, f"{campo}='inventado' tenía que fallar"
    detalle = " ".join(e.detalle for e in errores)
    assert all(v in detalle for v in valido), (
        "el mensaje no lista el vocabulario admitido: " + detalle
    )


def test_f006_r2_el_validador_devuelve_todos_los_errores_no_el_primero() -> None:
    """Con 80 fichas, parar en el primer fallo obliga a 80 vueltas."""
    rota = _ficha(tipo="", capa="", descripcion="")

    errores = validar(_dicc(fichas=[rota]), PASOS_NOCTURNOS)

    assert len(errores) >= 3, f"solo se reportó {len(errores)}: {errores}"


def test_f006_r2_dos_fichas_del_mismo_objeto_son_un_error() -> None:
    """Dos fichas del mismo `esquema.objeto`: el MCP vería una sola, a suertes."""
    errores = validar(_dicc(fichas=[_ficha(), _ficha()]), PASOS_NOCTURNOS)

    assert errores
    assert any("duplicad" in e.detalle.lower() for e in errores)


# ---------------------------------------------------------------------------
# R3 · `consumo_recomendado: false` exige `motivo_no_consumo`
# ---------------------------------------------------------------------------


def test_f006_r3_sin_consumo_recomendado_hace_falta_motivo() -> None:
    """R3 es el antídoto contra la puerta trasera de la puerta de cobertura.

    Sin esta exigencia, bajar `consumo_recomendado` sería la forma silenciosa
    de esquivar el 100 % de columnas descritas (R26) sin que se note en el diff.
    """
    errores = validar(
        _dicc(fichas=[_ficha(consumo_recomendado=False, motivo_no_consumo=None)]),
        PASOS_NOCTURNOS,
    )

    assert errores
    assert any("motivo_no_consumo" in e.detalle for e in errores)


def test_f006_r3_un_motivo_en_blanco_tampoco_vale() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(consumo_recomendado=False, motivo_no_consumo="   ")]),
        PASOS_NOCTURNOS,
    )

    assert any("motivo_no_consumo" in e.detalle for e in errores)


def test_f006_r3_con_motivo_escrito_la_ficha_sin_columnas_es_valida() -> None:
    """Fuera de la superficie de consumo no se exigen columnas ni ejemplos."""
    fuera = _ficha(
        esquema="raw",
        objeto="obrparpre",
        capa="origen",
        consumo_recomendado=False,
        motivo_no_consumo="Copia literal de Sigrid; su diccionario real es sigrid_tablas.md",
        columnas=(),
        ejemplos_preguntas=(),
        clave_negocio=("ide",),
        refresco="nocturno",
        paso_etl="ingest_raw",
    )

    assert validar(_dicc(fichas=[fuera]), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R4 · Los NUEVE esquemas
# ---------------------------------------------------------------------------


def test_f006_r4_son_nueve_esquemas_y_estos() -> None:
    """Los informes de exploración dicen ocho. Son NUEVE (requirements §0.5)."""
    assert len(ESQUEMAS_DEL_DATAMART) == 9
    assert set(ESQUEMAS_DEL_DATAMART) == {
        "_meta", "raw", "stg", "aux", "mart",
        "cierre", "compras", "maestro", "retenciones",
    }


def test_f006_r4_falta_una_entrada_de_esquema_y_falla() -> None:
    errores = validar(
        _dicc(esquemas=_esquemas(*[e for e in ESQUEMAS_DEL_DATAMART if e != "aux"])),
        PASOS_NOCTURNOS,
    )

    assert errores
    assert any("aux" in e.detalle for e in errores)


def test_f006_r4_la_entrada_de_esquema_necesita_titulo_y_para_que_sirve() -> None:
    esquemas = _esquemas()
    esquemas["mart"] = {"titulo": "", "para_que_sirve": "", "refresco": "nocturno"}

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any("titulo" in e.detalle for e in errores)
    assert any("para_que_sirve" in e.detalle for e in errores)


def test_f006_r4_una_ficha_de_un_esquema_no_declarado_falla() -> None:
    """Documentar `tesoreria.movimientos` hoy sería documentar humo."""
    errores = validar(
        _dicc(fichas=[_ficha(esquema="tesoreria")]), PASOS_NOCTURNOS
    )

    assert errores
    assert any("tesoreria" in e.detalle for e in errores)


# ---------------------------------------------------------------------------
# R5 · Relaciones resolubles
# ---------------------------------------------------------------------------


def test_f006_r5_una_relacion_a_un_objeto_inexistente_falla() -> None:
    """Una relación rota es peor que ninguna: el agente escribe el JOIN igual."""
    from etl_sigrid.domain.diccionario import Relacion

    rota = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="maestro.obras.obra_codigo",
                cardinalidad="N:1",
                porque="Para poner nombre a la obra.",
            ),
        )
    )

    errores = validar(_dicc(fichas=[rota]), PASOS_NOCTURNOS)

    assert errores
    assert any("maestro.obras.obra_codigo" in e.detalle for e in errores)
    assert any(e.objeto == "mart.fact_seguimiento_mensual" for e in errores)


def test_f006_r5_una_relacion_a_una_columna_inexistente_del_destino_falla() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    destino = _ficha(
        esquema="maestro",
        objeto="obras",
        tipo="vista",
        paso_etl="build_maestros",
        refresco="manual",
        columnas=(_columna("obra_codigo"),),
    )
    origen = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="maestro.obras.columna_fantasma",
                cardinalidad="N:1",
                porque="Para poner nombre a la obra.",
            ),
        )
    )

    errores = validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS)

    assert any("columna_fantasma" in e.detalle for e in errores)


def test_f006_r5_una_relacion_resoluble_valida() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    destino = _ficha(
        esquema="maestro",
        objeto="obras",
        tipo="vista",
        paso_etl="build_maestros",
        refresco="manual",
        columnas=(_columna("obra_codigo"),),
    )
    origen = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="maestro.obras.obra_codigo",
                cardinalidad="N:1",
                porque="Para poner nombre a la obra.",
            ),
        )
    )

    assert validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS) == []


def test_f006_r5_el_origen_de_la_relacion_tambien_debe_existir() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    rota = _ficha(
        relaciones=(
            Relacion(
                de="columna_que_no_tengo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad="1:1",
                porque="Consigo misma, para probar el lado `de`.",
            ),
        )
    )

    errores = validar(_dicc(fichas=[rota]), PASOS_NOCTURNOS)

    assert any("columna_que_no_tengo" in e.detalle for e in errores)


def test_f006_r5_un_destino_mal_formado_falla_sin_reventar() -> None:
    """`a: maestro.obras` (sin columna) no debe explotar el validador."""
    from etl_sigrid.domain.diccionario import Relacion

    rota = _ficha(
        relaciones=(
            Relacion(de="obra_codigo", a="maestro.obras", cardinalidad="N:1", porque="x"),
        )
    )

    errores = validar(_dicc(fichas=[rota]), PASOS_NOCTURNOS)

    assert errores
    assert any("maestro.obras" in e.detalle for e in errores)


# ---------------------------------------------------------------------------
# R6 · Toda columna documentada lleva significado de negocio
# ---------------------------------------------------------------------------


def test_f006_r6_una_columna_sin_significado_falla() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(columnas=(Columna(nombre="obra_codigo", significado=""),))]),
        PASOS_NOCTURNOS,
    )

    assert errores
    assert any("obra_codigo" in e.detalle for e in errores)


def test_f006_r6_dos_columnas_con_el_mismo_nombre_son_un_error() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(columnas=(_columna(), _columna()))]), PASOS_NOCTURNOS
    )

    assert any("duplicad" in e.detalle.lower() for e in errores)


def test_f006_r6_un_objeto_de_consumo_sin_columnas_falla() -> None:
    """R26 en su forma de formato: la superficie de consumo se describe entera."""
    errores = validar(_dicc(fichas=[_ficha(columnas=())]), PASOS_NOCTURNOS)

    assert errores
    assert any("columnas" in e.detalle for e in errores)


def test_f006_r6_un_objeto_de_consumo_sin_ejemplos_de_pregunta_falla() -> None:
    """R40: sin ejemplos no hay enrutado pregunta -> objeto."""
    errores = validar(_dicc(fichas=[_ficha(ejemplos_preguntas=())]), PASOS_NOCTURNOS)

    assert any("ejemplos_preguntas" in e.detalle for e in errores)


# ---------------------------------------------------------------------------
# R7 · Vocabulario cerrado de `agregacion`
# ---------------------------------------------------------------------------


def test_f006_r7_el_vocabulario_de_agregacion_es_exactamente_este() -> None:
    """Es lo que el MCP traduce a «esta columna no se suma». Cerrado a propósito."""
    assert set(AGREGACIONES) == {
        "suma",
        "promedio",
        "no_sumable",
        "suma_solo_dentro_del_mes",
        "ultimo_valor",
        "clave_sustituta",
    }


@pytest.mark.parametrize("agregacion", AGREGACIONES)
def test_f006_r7_las_agregaciones_del_vocabulario_validan(agregacion: str) -> None:
    ficha = _ficha(columnas=(_columna(agregacion=agregacion),))

    assert validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS) == []


def test_f006_r7_una_agregacion_inventada_falla() -> None:
    ficha = _ficha(columnas=(_columna(agregacion="sumatorio_magico"),))

    errores = validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS)

    assert errores
    assert any("sumatorio_magico" in e.detalle for e in errores)


def test_f006_r7_una_columna_sin_agregacion_es_valida() -> None:
    """`agregacion` es opcional: no toda columna es un importe."""
    assert validar(_dicc(), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R8 · Dominio puro
# ---------------------------------------------------------------------------


def test_f006_r8_el_dominio_no_importa_infraestructura() -> None:
    """`diccionario.py` no puede tocar YAML, SQL, red ni ficheros."""
    from pathlib import Path

    fuente = Path("etl_sigrid/domain/diccionario.py").read_text(encoding="utf-8")

    for prohibido in ("import yaml", "import psycopg", "from pathlib", "import requests",
                      "open(", "etl_sigrid.infrastructure"):
        assert prohibido not in fuente, (
            f"el dominio no puede depender de {prohibido!r} (R8)"
        )


def test_f006_r8_las_entidades_son_inmutables() -> None:
    from dataclasses import FrozenInstanceError

    ficha = _ficha()
    with pytest.raises(FrozenInstanceError):
        ficha.descripcion = "otra cosa"  # type: ignore[misc]


def test_f006_r8_validar_no_modifica_el_diccionario_que_recibe() -> None:
    dicc = _dicc()
    antes = dicc.fichas

    validar(dicc, PASOS_NOCTURNOS)

    assert dicc.fichas == antes


# ---------------------------------------------------------------------------
# Formato del informe de errores
# ---------------------------------------------------------------------------


def test_f006_r2_el_informe_nombra_fichero_ficha_y_regla() -> None:
    """Quien lea el fallo tiene que saber qué abrir y qué corregir."""
    errores = [
        ErrorValidacion(
            fichero="mart.yaml",
            objeto="mart.fact_seguimiento_mensual",
            regla="R2",
            detalle="falta `grano`",
        )
    ]

    texto = formatear_errores(errores)

    assert "mart.yaml" in texto
    assert "mart.fact_seguimiento_mensual" in texto
    assert "R2" in texto
    assert "falta `grano`" in texto


def test_f006_r2_sin_errores_el_informe_lo_dice() -> None:
    assert "OK" in formatear_errores([])


def test_f006_r2_el_informe_es_determinista() -> None:
    """El mismo fallo tiene que producir el mismo texto, entre en el orden que entre."""
    dicc = _dicc(fichas=[_ficha(tipo="", capa="", descripcion="")])

    assert formatear_errores(validar(dicc, PASOS_NOCTURNOS)) == formatear_errores(
        validar(dicc, PASOS_NOCTURNOS)
    )


# ---------------------------------------------------------------------------
# Una regla mal formada también es un error de formato (apoyo de R9)
# ---------------------------------------------------------------------------


def test_f006_r9_una_regla_con_severidad_inventada_falla() -> None:
    regla = Regla(
        codigo="R-INVENTADA",
        titulo="Regla de prueba",
        severidad="catastrofica",
        ambito=("mart",),
        regla="No hagas eso.",
        motivo="Porque no.",
    )

    errores = validar(_dicc(reglas=[regla]), PASOS_NOCTURNOS)

    assert any("catastrofica" in e.detalle for e in errores)
