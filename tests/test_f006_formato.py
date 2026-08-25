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


# ===========================================================================
# Cargador de YAML (T7 · R1, R6, R8, R22)
#
# El cargador es INFRAESTRUCTURA: toca el sistema de ficheros. Estos tests
# escriben YAML en `tmp_path`, nunca leen el diccionario real del repositorio
# (de eso se ocupa la puerta de `tests/test_f006_cobertura.py`).
# ===========================================================================


GLOBAL_MINIMO = """
version: 1
base: sigrid_dm
titulo: Datamart de prueba
convenciones:
  moneda: EUR
esquemas:
  mart:
    titulo: Seguimiento mensual
    para_que_sirve: Superficie principal de consumo.
    consumo_recomendado: true
    refresco: nocturno
    pasos_etl: [build_mart]
reglas:
  - codigo: R-IMPORTE-MES
    titulo: importe_mes no se suma entre meses
    severidad: bloqueante
    ambito: [mart]
    regla: No sumes importe_origen en el tiempo.
    motivo: Bug de la Tanda 1.4; multiplicaba por nueve.
pendientes: []
"""

MART_MINIMO = """
version: 1
esquema: mart
objetos:
  fact_seguimiento_mensual:
    tipo: tabla
    capa: consumo
    consumo_recomendado: true
    descripcion: El hecho central del seguimiento.
    grano: Una fila por (obra, partida, mes, escenario).
    clave_negocio: [obra_codigo, importe_mes]
    paso_etl: build_mart
    refresco: nocturno
    columnas:
      obra_codigo: Codigo de obra tal y como se teclea en Sigrid.
      importe_mes:
        significado: Importe imputado a ese mes concreto.
        unidad: EUR
        agregacion: suma_solo_dentro_del_mes
    relaciones: []
    ejemplos_preguntas:
      - Cual es la planificacion mensual de la obra X
"""


def _directorio(tmp_path, **ficheros):
    """Escribe un diccionario de prueba y devuelve su directorio."""
    destino = tmp_path / "diccionario"
    destino.mkdir()
    contenido = {"00_global.yaml": GLOBAL_MINIMO, "mart.yaml": MART_MINIMO}
    contenido.update(ficheros)
    for nombre, texto in contenido.items():
        if texto is None:
            continue
        (destino / nombre).write_text(texto, encoding="utf-8")
    return destino


def test_f006_r1_cargador_lee_un_fichero_por_esquema(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _hash = cargar_diccionario(_directorio(tmp_path))

    assert dicc.version == "1"
    assert dicc.base == "sigrid_dm"
    assert [f.nombre for f in dicc.fichas] == ["mart.fact_seguimiento_mensual"]
    assert [r.codigo for r in dicc.reglas] == ["R-IMPORTE-MES"]
    assert dicc.esquemas["mart"]["refresco"] == "nocturno"


def test_f006_r1_cargador_deja_el_resto_del_global_a_mano(tmp_path) -> None:
    """`convenciones`, `ejes`, `ocultar` y la batería se sirven tal cual."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(_directorio(tmp_path))

    assert dicc.global_raw["convenciones"] == {"moneda": "EUR"}
    assert dicc.global_raw["titulo"] == "Datamart de prueba"


def test_f006_r6_cargador_admite_la_forma_abreviada_de_columna(tmp_path) -> None:
    """`columna: "<significado>"` equivale a `columna: {significado: ...}`.

    Sin esto, las 800+ columnas del datamart costarían tres líneas cada una y
    nadie las escribiría.
    """
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(_directorio(tmp_path))

    ficha = dicc.por_nombre["mart.fact_seguimiento_mensual"]
    abreviada = next(c for c in ficha.columnas if c.nombre == "obra_codigo")
    completa = next(c for c in ficha.columnas if c.nombre == "importe_mes")

    assert abreviada.significado.startswith("Codigo de obra")
    assert abreviada.unidad is None and abreviada.agregacion is None
    assert completa.unidad == "EUR"
    assert completa.agregacion == "suma_solo_dentro_del_mes"


def test_f006_r6_cargador_conserva_el_orden_de_las_columnas(tmp_path) -> None:
    """El orden del YAML es editorial: primero las claves, luego los importes."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(_directorio(tmp_path))

    ficha = dicc.por_nombre["mart.fact_seguimiento_mensual"]
    assert [c.nombre for c in ficha.columnas] == ["obra_codigo", "importe_mes"]


def test_f006_r22_cargador_el_hash_es_estable_entre_cargas(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    directorio = _directorio(tmp_path)

    _, uno = cargar_diccionario(directorio)
    _, dos = cargar_diccionario(directorio)

    assert uno == dos
    assert len(uno) == 64  # SHA-256 en hexadecimal


def test_f006_r22_cargador_el_hash_cambia_si_cambia_una_letra(tmp_path) -> None:
    """Es lo que permite responder «¿esto es lo que hay en el repositorio?»."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    directorio = _directorio(tmp_path)
    _, antes = cargar_diccionario(directorio)

    (directorio / "mart.yaml").write_text(
        MART_MINIMO.replace("El hecho central", "El hecho centrico"), encoding="utf-8"
    )
    _, despues = cargar_diccionario(directorio)

    assert antes != despues


def test_f006_r22_cargador_el_hash_no_depende_del_fin_de_linea(tmp_path) -> None:
    """CRLF en Windows y LF en el contenedor tienen que dar el mismo hash."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    directorio = _directorio(tmp_path)
    _, con_lf = cargar_diccionario(directorio)

    for nombre in ("00_global.yaml", "mart.yaml"):
        ruta = directorio / nombre
        texto = ruta.read_text(encoding="utf-8").replace("\n", "\r\n")
        ruta.write_bytes(texto.encode("utf-8"))
    _, con_crlf = cargar_diccionario(directorio)

    assert con_lf == con_crlf


def test_f006_r22_cargador_el_hash_cubre_el_conjunto_de_ficheros(tmp_path) -> None:
    """Añadir un fichero cambia el hash aunque no cambie ninguno de los viejos.

    El nombre de cada fichero entra en el resumen, no solo su contenido: si no,
    un esquema nuevo vacío pasaría por «el mismo diccionario de siempre».
    """
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    directorio = _directorio(tmp_path)
    _, antes = cargar_diccionario(directorio)

    (directorio / "cierre.yaml").write_text(
        "version: 1\nesquema: cierre\nobjetos: {}\n", encoding="utf-8"
    )
    _, despues = cargar_diccionario(directorio)

    assert antes != despues


def test_f006_r8_cargador_un_yaml_roto_no_devuelve_una_traza_de_yaml(tmp_path) -> None:
    """Quien lo lea tiene que ver el fichero y la línea, no un `ScannerError`."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    directorio = _directorio(tmp_path, **{"mart.yaml": "objetos:\n  a: [1,\n"})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    errores = excinfo.value.errores
    assert any(e.fichero == "mart.yaml" for e in errores)
    assert any(
        "linea" in e.detalle.lower() or "línea" in e.detalle.lower() for e in errores
    )


def test_f006_r6_cargador_rechaza_una_clave_desconocida_en_una_columna(tmp_path) -> None:
    """Un `significao:` mal escrito dejaría la columna sin significado y muda."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace("        unidad: EUR", "        unidadd: EUR")
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("unidadd" in e.detalle for e in excinfo.value.errores)


def test_f006_r2_cargador_rechaza_una_clave_desconocida_en_una_ficha(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace("    grano:", "    granoo:")
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("granoo" in e.detalle for e in excinfo.value.errores)


def test_f006_r1_cargador_exige_que_el_nombre_del_fichero_sea_el_esquema(
    tmp_path,
) -> None:
    """`mart.yaml` con `esquema: cierre` dentro es una bomba de relojería."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace("esquema: mart", "esquema: cierre")
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any(
        "cierre" in e.detalle and "mart" in e.detalle for e in excinfo.value.errores
    )


def test_f006_r1_cargador_ignora_lo_que_no_sea_yaml(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    directorio = _directorio(tmp_path)
    (directorio / "README.md").write_text("no soy una ficha", encoding="utf-8")

    dicc, _ = cargar_diccionario(directorio)

    assert [f.nombre for f in dicc.fichas] == ["mart.fact_seguimiento_mensual"]


def test_f006_r1_cargador_sin_global_no_hay_diccionario(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    directorio = _directorio(tmp_path)
    (directorio / "00_global.yaml").unlink()

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("00_global.yaml" in e.fichero for e in excinfo.value.errores)


def test_f006_r12_cargador_pasa_los_avisos_escritos_a_mano_al_validador(
    tmp_path,
) -> None:
    """El cargador no los borra en silencio: `validar` tiene que poder acusarlos."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    con_avisos = MART_MINIMO.replace(
        "    relaciones: []", "    avisos: [R-IMPORTE-MES]\n    relaciones: []"
    )
    directorio = _directorio(tmp_path, **{"mart.yaml": con_avisos})

    dicc, _ = cargar_diccionario(directorio)

    assert dicc.por_nombre["mart.fact_seguimiento_mensual"].avisos == ("R-IMPORTE-MES",)


def test_f006_r1_cargador_lee_las_relaciones(tmp_path) -> None:
    from etl_sigrid.domain.diccionario import Relacion
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    con_relacion = MART_MINIMO.replace(
        "    relaciones: []",
        "    relaciones:\n"
        "      - de: obra_codigo\n"
        "        a: mart.fact_seguimiento_mensual.obra_codigo\n"
        "        cardinalidad: 1 a 1\n"
        "        porque: Consigo misma, para la prueba.\n",
    )
    directorio = _directorio(tmp_path, **{"mart.yaml": con_relacion})

    dicc, _ = cargar_diccionario(directorio)

    assert dicc.por_nombre["mart.fact_seguimiento_mensual"].relaciones == (
        Relacion(
            de="obra_codigo",
            a="mart.fact_seguimiento_mensual.obra_codigo",
            cardinalidad="1 a 1",
            porque="Consigo misma, para la prueba.",
        ),
    )


def test_f006_r1_cargador_una_ficha_sin_cuerpo_es_un_error(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    directorio = _directorio(
        tmp_path, **{"mart.yaml": "esquema: mart\nobjetos:\n  fact_vacio:\n"}
    )

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("fact_vacio" in e.detalle for e in excinfo.value.errores)


# ===========================================================================
# El bloque global REAL (T10 · R4, R10)
#
# Estos tests leen `config/diccionario/00_global.yaml`, no fixtures: son la
# diferencia entre «el validador sabe exigir nueve esquemas» y «los nueve
# esquemas están escritos».
# ===========================================================================


def _global_real():
    from pathlib import Path

    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        cargar_diccionario,
    )

    dicc, _ = cargar_diccionario(
        Path(__file__).resolve().parents[1] / "config" / "diccionario"
    )
    return dicc


def test_f006_r4_el_global_real_declara_los_nueve_esquemas() -> None:
    dicc = _global_real()

    assert set(dicc.esquemas) == set(ESQUEMAS_DEL_DATAMART)


def test_f006_r4_cada_esquema_global_dice_para_que_sirve() -> None:
    """Es lo primero que lee el agente para decidir dónde buscar."""
    dicc = _global_real()

    for nombre, entrada in dicc.esquemas.items():
        assert entrada.get("titulo"), f"{nombre}: sin `titulo`"
        assert len(str(entrada.get("para_que_sirve", "")).strip()) >= 40, (
            f"{nombre}: `para_que_sirve` demasiado corto para ser útil"
        )
        assert isinstance(entrada.get("consumo_recomendado"), bool), (
            f"{nombre}: `consumo_recomendado` tiene que ser booleano"
        )
        assert entrada.get("refresco") in REFRESCOS, f"{nombre}: refresco inválido"


def test_f006_r4_raw_y_stg_quedan_fuera_de_la_superficie_de_consumo() -> None:
    """`raw` es una copia literal de Sigrid sin semántica, y `stg.plan_mensual`
    multiplica los importes si se consulta sin filtrar versión. Ofrecérselos al
    agente es ofrecerle el camino que produce números falsos."""
    dicc = _global_real()

    assert dicc.esquemas["raw"]["consumo_recomendado"] is False
    assert dicc.esquemas["stg"]["consumo_recomendado"] is False
    for consumo in ("mart", "cierre", "compras", "maestro", "retenciones", "_meta"):
        assert dicc.esquemas[consumo]["consumo_recomendado"] is True


def test_f006_r4_los_cuatro_esquemas_manuales_lo_declaran_en_el_global() -> None:
    """El régimen de refresco tiene que verse ya al listar los esquemas, sin
    tener que abrir una ficha."""
    dicc = _global_real()

    for manual in ("cierre", "compras", "maestro", "retenciones"):
        assert dicc.esquemas[manual]["refresco"] == "manual", manual
    for nocturno in ("raw", "stg", "mart", "_meta"):
        assert dicc.esquemas[nocturno]["refresco"] == "nocturno", nocturno


def test_f006_r4_el_global_real_trae_las_convenciones_que_mas_confunden() -> None:
    """IVA, fechas de Sigrid y zona horaria: las tres que se equivocan solas."""
    dicc = _global_real()

    convenciones = dicc.global_raw["convenciones"]

    assert convenciones["moneda"] == "EUR"
    assert "IVA" in convenciones["importes_iva"]
    assert "maestro.proveedores_obra.importe_contratado" in convenciones["importes_iva"]
    assert "YYYYMMDD" in convenciones["fechas"]
    assert "0" in convenciones["fechas"]
    assert "UTC" in convenciones["timestamps"]


def test_f006_r4_el_global_real_declara_los_ejes_del_modelo() -> None:
    """Los cuatro escenarios son el esqueleto del seguimiento."""
    dicc = _global_real()

    ejes = {e["eje"]: e["valores"] for e in dicc.global_raw["ejes"]}

    assert ejes["magnitud"] == ["COSTE", "VENTA"]
    assert ejes["naturaleza"] == ["REAL", "PLANIFICADO"]
    assert set(ejes["escenario"]) == {
        "Coste Real",
        "Coste Planificado",
        "Venta Real",
        "Venta Planificada",
    }


def test_f006_r4_los_escenarios_declarados_son_los_del_sql() -> None:
    """Los literales tienen que ser EXACTOS: el agente los va a poner en un
    `WHERE escenario = '...'`. Se contrastan contra `mart.v_pbi_dim_escenario`,
    que es donde el modelo los fija."""
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1]
        / "etl_sigrid/infrastructure/postgres/sql/mart/05_views_powerbi.sql"
    ).read_text(encoding="utf-8")

    ejes = {e["eje"]: e["valores"] for e in _global_real().global_raw["ejes"]}

    for escenario in ejes["escenario"]:
        assert f"'{escenario}'" in sql, f"{escenario!r} no aparece en el SQL"


def test_f006_r4_el_global_real_oculta_las_columnas_tecnicas() -> None:
    """Las columnas de instrumentación no son negocio y ensucian el catálogo."""
    dicc = _global_real()

    ocultar = dicc.global_raw["ocultar"]

    assert "_ingested_at" in ocultar
    assert "_source_tiemod" in ocultar
    assert "_built_at" in ocultar


def test_f006_r2_el_diccionario_global_real_valida_entero() -> None:
    """LA COMPROBACIÓN QUE IMPORTA: lo que se va a publicar en `_meta` pasa el
    validador completo, con los pasos nocturnos leídos del pipeline real."""
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    errores = validar(_global_real(), pasos_del_pipeline_nocturno())

    assert errores == [], "\n" + formatear_errores(errores)


# ===========================================================================
# Ramas defensivas del validador y del cargador
#
# Todas nacen de la misma idea: **un YAML mal escrito tiene que dar un mensaje
# accionable, no una excepción de Python ni un silencio**. Sin estos tests la
# rama existe pero nadie ha comprobado nunca que el mensaje salga, que es la
# forma más común de que un manejo de errores esté roto el día que hace falta.
# ===========================================================================


def test_f006_r4_un_esquema_de_mas_en_el_global_falla() -> None:
    """Declarar `tesoreria` en `esquemas` sería anunciar algo que no existe."""
    esquemas = _esquemas()
    esquemas["tesoreria"] = {
        "titulo": "Tesorería",
        "para_que_sirve": "Cobros y pagos.",
        "consumo_recomendado": True,
        "refresco": "manual",
    }

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any("tesoreria" in e.detalle for e in errores)


def test_f006_r4_un_refresco_inventado_en_la_entrada_de_esquema_falla() -> None:
    esquemas = _esquemas()
    esquemas["mart"] = dict(esquemas["mart"], refresco="cuando_apetezca")

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any("cuando_apetezca" in e.detalle for e in errores)


def test_f006_r4_consumo_recomendado_no_booleano_en_el_esquema_falla() -> None:
    """`consumo_recomendado: "si"` es un texto y en Python es siempre cierto."""
    esquemas = _esquemas()
    esquemas["mart"] = dict(esquemas["mart"], consumo_recomendado="si")

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any("booleano" in e.detalle for e in errores)


def test_f006_r4_una_ficha_de_un_esquema_real_sin_entrada_en_el_global_falla() -> None:
    """El esquema existe, pero nadie ha escrito para qué sirve."""
    esquemas = _esquemas(*[e for e in ESQUEMAS_DEL_DATAMART if e != "mart"])

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any(
        e.objeto == "mart.fact_seguimiento_mensual" and "esquemas" in e.detalle
        for e in errores
    )


def test_f006_r2_consumo_recomendado_no_booleano_en_la_ficha_falla() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(consumo_recomendado="si")]), PASOS_NOCTURNOS
    )

    assert any("booleano" in e.detalle for e in errores)


def test_f006_r6_una_columna_sin_nombre_falla() -> None:
    """Pasa con un `- :` suelto en el YAML y dejaría una columna anónima."""
    errores = validar(
        _dicc(fichas=[_ficha(columnas=(Columna(nombre="  ", significado="Algo."),))]),
        PASOS_NOCTURNOS,
    )

    assert any("sin nombre" in e.detalle for e in errores)


# --- Cargador: formas del YAML que no se pueden convertir en entidades -----


def test_f006_r1_cargador_un_escalar_suelto_vale_como_lista_de_uno(tmp_path) -> None:
    """`clave_negocio: obra_id` sin corchetes es un error humano frecuente y
    tiene una interpretación obvia. Se acepta en vez de reventar."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    texto = MART_MINIMO.replace(
        "    clave_negocio: [obra_codigo, importe_mes]", "    clave_negocio: obra_codigo"
    )
    directorio = _directorio(tmp_path, **{"mart.yaml": texto})

    dicc, _ = cargar_diccionario(directorio)

    assert dicc.por_nombre["mart.fact_seguimiento_mensual"].clave_negocio == (
        "obra_codigo",
    )


def test_f006_r1_cargador_un_fichero_de_esquema_vacio_falla(tmp_path) -> None:
    """Un `aux.yaml` en blanco es un fichero a medio escribir, no un esquema sin
    objetos: se rechaza nombrandolo, en vez de aportar cero fichas en silencio."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    directorio = _directorio(tmp_path)
    (directorio / "aux.yaml").write_text("", encoding="utf-8")

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any(e.fichero == "aux.yaml" for e in excinfo.value.errores)


def test_f006_r1_cargador_un_fichero_que_no_es_un_mapa_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    directorio = _directorio(tmp_path, **{"mart.yaml": "- uno\n- dos\n"})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("mapa" in e.detalle for e in excinfo.value.errores)


def test_f006_r1_cargador_esquemas_que_no_es_un_mapa_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = GLOBAL_MINIMO.replace(
        "esquemas:\n  mart:", "esquemas: [mart]\notro_bloque:\n  mart:"
    )
    directorio = _directorio(tmp_path, **{"00_global.yaml": roto})

    with pytest.raises(DiccionarioIlegible):
        cargar_diccionario(directorio)


@pytest.mark.parametrize(
    ("bloque", "roto", "esperado"),
    [
        ("reglas", "reglas: no soy una lista", "lista"),
        ("objetos", None, "mapa"),
    ],
)
def test_f006_r1_cargador_bloques_con_la_forma_equivocada(
    tmp_path, bloque: str, roto: str | None, esperado: str
) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    if bloque == "reglas":
        texto = GLOBAL_MINIMO.split("reglas:")[0] + roto + "\npendientes: []\n"
        directorio = _directorio(tmp_path, **{"00_global.yaml": texto})
    else:
        directorio = _directorio(
            tmp_path, **{"mart.yaml": "esquema: mart\nobjetos: no soy un mapa\n"}
        )

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any(esperado in e.detalle for e in excinfo.value.errores)


def test_f006_r1_cargador_una_regla_que_no_es_un_mapa_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    texto = GLOBAL_MINIMO.split("reglas:")[0] + "reglas:\n  - solo texto\npendientes: []\n"
    directorio = _directorio(tmp_path, **{"00_global.yaml": texto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("posición" in e.detalle for e in excinfo.value.errores)


def test_f006_r6_cargador_columnas_que_no_es_un_mapa_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace(
        "    columnas:\n      obra_codigo:", "    columnas: [obra_codigo]\n    _sobra:"
    )
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible):
        cargar_diccionario(directorio)


def test_f006_r6_cargador_una_columna_que_es_una_lista_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace(
        "      obra_codigo: Codigo de obra tal y como se teclea en Sigrid.",
        "      obra_codigo: [uno, dos]",
    )
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("ni un texto ni un mapa" in e.detalle for e in excinfo.value.errores)


def test_f006_r5_cargador_relaciones_que_no_es_una_lista_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace("    relaciones: []", "    relaciones: no soy una lista")
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("lista" in e.detalle for e in excinfo.value.errores)


def test_f006_r5_cargador_una_relacion_que_no_es_un_mapa_falla(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import (
        DiccionarioIlegible,
        cargar_diccionario,
    )

    roto = MART_MINIMO.replace("    relaciones: []", "    relaciones:\n      - texto suelto")
    directorio = _directorio(tmp_path, **{"mart.yaml": roto})

    with pytest.raises(DiccionarioIlegible) as excinfo:
        cargar_diccionario(directorio)

    assert any("relación no es un mapa" in e.detalle for e in excinfo.value.errores)


def test_f006_r8_cargador_un_error_de_yaml_sin_posicion_tambien_es_legible() -> None:
    """No todos los errores de `yaml` traen marca de línea. El mensaje sigue
    teniendo que explicar qué pasa."""
    import yaml as yaml_lib

    from etl_sigrid.infrastructure.diccionario.cargador_yaml import _detalle_yaml

    detalle = _detalle_yaml(yaml_lib.YAMLError("algo raro"))

    assert "no parsea" in detalle


# ===========================================================================
# R5 · Vocabulario cerrado de `cardinalidad` (defecto 1 de la review)
#
# `cardinalidad: 1:1` SIN COMILLAS lo interpreta YAML como sexagesimal y vale
# 61. Ocho relaciones de `mart.yaml` y `cierre.yaml` se publicaron asi, y no lo
# vio nadie porque el campo se declaraba `str` y no se validaba contra nada.
# El vocabulario cerrado es la misma defensa que ya tenia `agregacion` (R7).
# ===========================================================================


def test_f006_r5_el_vocabulario_de_cardinalidad_es_exactamente_este() -> None:
    from etl_sigrid.domain.diccionario import CARDINALIDADES

    assert set(CARDINALIDADES) == {"1:1", "1:N", "N:1", "N:N"}


@pytest.mark.parametrize("cardinalidad", ["1:1", "1:N", "N:1", "N:N"])
def test_f006_r5_las_cardinalidades_del_vocabulario_validan(cardinalidad: str) -> None:
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad=cardinalidad,
                porque="Consigo misma, para la prueba.",
            ),
        )
    )

    assert validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS) == []


def test_f006_r5_el_61_de_yaml_se_caza_como_cardinalidad_invalida() -> None:
    """El caso exacto que se coló: `1:1` sin comillas parseado como 61."""
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad="61",
                porque="Lo que YAML entiende por `1:1` sin comillas.",
            ),
        )
    )

    errores = validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS)

    assert errores
    assert any("61" in e.detalle for e in errores)
    assert any("comillas" in e.detalle for e in errores), (
        "el mensaje tiene que decir COMO se arregla, no solo que esta mal"
    )


def test_f006_r5_una_cardinalidad_vacia_falla() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad="",
                porque="Sin cardinalidad no se sabe si el JOIN multiplica.",
            ),
        )
    )

    assert any(e.regla == "R5" for e in validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS))


def test_f006_r5_ninguna_relacion_real_publica_una_cardinalidad_de_yaml() -> None:
    """Sobre el diccionario REAL: ni un `61`, ni un numero, ni nada fuera del
    vocabulario. Es lo que llegaria al JSONB que consume el MCP."""
    from etl_sigrid.domain.diccionario import CARDINALIDADES

    for ficha in _global_real().fichas:
        for relacion in ficha.relaciones:
            assert relacion.cardinalidad in CARDINALIDADES, (
                f"{ficha.nombre} -> {relacion.a}: cardinalidad "
                f"{relacion.cardinalidad!r}"
            )


# ===========================================================================
# R5 · La cardinalidad no puede prometer unicidad que la clave no da
#      (defecto 2 de la review)
#
# Seis relaciones declaraban `N:1` o `1:N` sobre `obra_id` teniendo el destino
# muchas filas por obra. Un agente que se fie escribe un JOIN con FAN-OUT
# SILENCIOSO y duplica importes: es exactamente el error que
# `R-RETENCION-NO-JOIN-LINEAS` existe para castigar, cometido dentro del propio
# diccionario.
#
# El remedio no es revisar a mano: el diccionario YA declara la clave de
# negocio de cada objeto, asi que la unicidad es DERIVABLE. Un lado `1` exige
# que su columna sea, ella sola, la clave de negocio de esa ficha (o una clave
# sustituta, que es unica por definicion). Esto protege tambien a las 73 fichas
# que faltan.
# ===========================================================================


def _con_clave(objeto: str, clave, columnas) -> Ficha:
    return _ficha(
        objeto=objeto,
        clave_negocio=tuple(clave),
        columnas=tuple(_columna(c) for c in columnas),
    )


def test_f006_r5_un_lado_uno_sobre_una_clave_parcial_es_fan_out() -> None:
    """El caso real: `obra_id` hacia una tabla cuya clave es (obra, mes, concepto)."""
    from etl_sigrid.domain.diccionario import Relacion

    destino = _con_clave(
        "fact_cierre", ["obra_id", "anio_mes"], ["obra_id", "anio_mes"]
    )
    origen = _ficha(
        columnas=(_columna("obra_id"),),
        clave_negocio=("obra_id",),
        relaciones=(
            Relacion(
                de="obra_id",
                a="mart.fact_cierre.obra_id",
                cardinalidad="N:1",
                porque="Miente: el destino tiene muchas filas por obra.",
            ),
        ),
    )

    errores = validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS)

    assert errores
    assert any("fan-out" in e.detalle for e in errores)
    assert any("N:N" in e.detalle for e in errores), (
        "el mensaje tiene que decir que cardinalidad SI es cierta"
    )


def test_f006_r5_declarada_n_a_n_la_misma_relacion_vale() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    destino = _con_clave(
        "fact_cierre", ["obra_id", "anio_mes"], ["obra_id", "anio_mes"]
    )
    origen = _ficha(
        columnas=(_columna("obra_id"),),
        clave_negocio=("obra_id",),
        relaciones=(
            Relacion(
                de="obra_id",
                a="mart.fact_cierre.obra_id",
                cardinalidad="N:N",
                porque="Dice la verdad: hay que agregar antes de unir.",
            ),
        ),
    )

    assert validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS) == []


def test_f006_r5_el_lado_izquierdo_tambien_se_comprueba() -> None:
    """`1:N` promete que el ORIGEN es unico por esa columna."""
    from etl_sigrid.domain.diccionario import Relacion

    destino = _con_clave("dim_obra", ["obra_id"], ["obra_id"])
    origen = _ficha(
        columnas=(_columna("obra_id"), _columna("anio_mes")),
        clave_negocio=("obra_id", "anio_mes"),
        relaciones=(
            Relacion(
                de="obra_id",
                a="mart.dim_obra.obra_id",
                cardinalidad="1:N",
                porque="Miente por el lado del origen.",
            ),
        ),
    )

    errores = validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS)

    assert any("fan-out" in e.detalle for e in errores)


def test_f006_r5_una_clave_sustituta_si_da_unicidad() -> None:
    """`fact_id` no esta en la clave de negocio a proposito, pero es unica.

    Sin esta excepcion, las relaciones legitimas `1:1` entre una tabla de hecho
    y su vista aligerada saldrian marcadas como falsas.
    """
    from etl_sigrid.domain.diccionario import Relacion

    destino = _ficha(
        objeto="fact_base",
        clave_negocio=("obra_id", "anio_mes"),
        columnas=(
            _columna("fact_id", agregacion="clave_sustituta"),
            _columna("obra_id"),
            _columna("anio_mes"),
        ),
    )
    origen = _ficha(
        objeto="v_fact",
        clave_negocio=("obra_id", "anio_mes"),
        columnas=(
            _columna("fact_id", agregacion="clave_sustituta"),
            _columna("obra_id"),
            _columna("anio_mes"),
        ),
        relaciones=(
            Relacion(
                de="fact_id",
                a="mart.fact_base.fact_id",
                cardinalidad="1:1",
                porque="Es literalmente la misma fila.",
            ),
        ),
    )

    assert validar(_dicc(fichas=[origen, destino]), PASOS_NOCTURNOS) == []


def test_f006_r5_un_destino_todavia_pendiente_no_se_comprueba() -> None:
    """Sin ficha del destino no hay clave que mirar: se aplaza, no se inventa."""
    from etl_sigrid.domain.diccionario import Relacion

    origen = _ficha(
        columnas=(_columna("obra_id"),),
        clave_negocio=("obra_id",),
        relaciones=(
            Relacion(
                de="obra_id",
                a="stg.obras.obra_id",
                cardinalidad="N:1",
                porque="El destino aun no tiene ficha.",
            ),
        ),
    )

    assert validar(
        _dicc(fichas=[origen], pendientes=("stg.obras",)), PASOS_NOCTURNOS
    ) == []


def test_f006_r5_ninguna_relacion_real_promete_una_unicidad_falsa() -> None:
    """Sobre el diccionario REAL. Es el test que habria cazado el defecto 2."""
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    errores = [
        e
        for e in validar(_global_real(), pasos_del_pipeline_nocturno())
        if "fan-out" in e.detalle
    ]

    assert errores == [], "\n" + formatear_errores(errores)


# ===========================================================================
# Defensa (a) de la puerta · minimos de contenido (defecto 10)
#
# El reviewer escribio un `maestro.yaml` con `descripcion: x`, `grano: x`,
# `motivo_no_consumo: x` y una columna `obra_id: x`, saco el objeto de
# `pendientes` y **todo quedo en verde**. Escalado a las 31 fichas de `raw`, el
# trinquete cae de 73 a 42 sin una linea de conocimiento.
#
# El validador exigia que los campos EXISTIERAN, no que dijeran algo. En el
# bloque global si se exigian minimos desde el principio (`para_que_sirve >= 40`,
# `regla >= 40`, `motivo >= 30`); esto extiende el mismo criterio a las fichas.
# ===========================================================================


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("descripcion", "x"),
        ("grano", "x"),
    ],
)
def test_f006_r2_una_ficha_esqueletica_no_pasa(campo: str, valor: str) -> None:
    errores = validar(_dicc(fichas=[_ficha(**{campo: valor})]), PASOS_NOCTURNOS)

    assert errores, f"`{campo}: {valor}` tenía que fallar"
    assert any(campo in e.detalle and "caracteres" in e.detalle for e in errores)


def test_f006_r3_un_motivo_no_consumo_de_relleno_no_pasa() -> None:
    """Era la puerta trasera de R3: el motivo existía, pero no decía nada."""
    fuera = _ficha(
        consumo_recomendado=False,
        motivo_no_consumo="x",
        columnas=(),
        ejemplos_preguntas=(),
    )

    errores = validar(_dicc(fichas=[fuera]), PASOS_NOCTURNOS)

    assert any("motivo_no_consumo" in e.detalle and "caracteres" in e.detalle
               for e in errores)


def test_f006_r6_un_significado_de_relleno_no_pasa() -> None:
    ficha = _ficha(columnas=(_columna("obra_id", significado="x"),),
                   clave_negocio=("obra_id",))

    errores = validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS)

    assert any("obra_id" in e.detalle and "caracteres" in e.detalle for e in errores)


def test_f006_r40_un_ejemplo_de_pregunta_de_relleno_no_pasa() -> None:
    errores = validar(
        _dicc(fichas=[_ficha(ejemplos_preguntas=("x",))]), PASOS_NOCTURNOS
    )

    assert any("ejemplos_preguntas" in e.detalle for e in errores)


def test_f006_r2_el_diccionario_real_supera_los_minimos() -> None:
    """Las 25 fichas entregadas pasan los mínimos sin retocar nada."""
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    errores = [
        e for e in validar(_global_real(), pasos_del_pipeline_nocturno())
        if "caracteres" in e.detalle
    ]

    assert errores == [], "\n" + formatear_errores(errores)


# ===========================================================================
# R5 · La clave de JOIN que cita el `porque` tiene que existir en la ficha
#
# La correccion del fan-out anadio a cada `porque` la clave por la que hay que
# agregar antes de unir. En dos de las diez se colo una columna que la vista NO
# proyecta: `categoria` en `cierre.v_pbi_planif_vs_real` —ya colapsada en
# `concepto_cuadro`— y `ambito_id` en `mart.v_pbi_cp_tipologia`, donde ademas no
# es dimension sino un filtro constante.
#
# Es la misma clase de mentira que la relacion rota que R5 ya impedia, y ahora
# se comprueba igual: un agente que copie esa clave escribe un JOIN por una
# columna que no existe.
# ===========================================================================


def test_f006_r5_una_clave_de_join_inventada_en_el_porque_falla() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad="N:N",
                porque=(
                    "Hay que agregar antes de unir, por `(obra_codigo, categoria)`, "
                    "y `categoria` no es columna de esta ficha."
                ),
            ),
        )
    )

    errores = validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS)

    assert errores
    assert any("categoria" in e.detalle for e in errores)
    assert any(e.regla == "R5" for e in errores)


def test_f006_r5_una_clave_de_join_con_columnas_propias_valida() -> None:
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        columnas=(_columna("obra_codigo"), _columna("mes")),
        clave_negocio=("obra_codigo",),
        relaciones=(
            Relacion(
                de="obra_codigo",
                a="mart.fact_seguimiento_mensual.obra_codigo",
                cardinalidad="N:N",
                porque="Se agrega por `(obra_codigo, mes)` en los dos lados.",
            ),
        ),
    )

    assert validar(_dicc(fichas=[ficha]), PASOS_NOCTURNOS) == []


def test_f006_r5_una_ficha_sin_columnas_no_se_juzga() -> None:
    """`raw` va a nivel de objeto (DA-2): no hay columnas contra las que mirar."""
    from etl_sigrid.domain.diccionario import Relacion

    ficha = _ficha(
        esquema="raw",
        objeto="obrparpre",
        capa="origen",
        consumo_recomendado=False,
        motivo_no_consumo="Copia literal de Sigrid; su diccionario es sigrid_tablas.md",
        columnas=(),
        ejemplos_preguntas=(),
        paso_etl="ingest_raw",
        relaciones=(
            Relacion(
                de="ide",
                a="stg.obras.obra_id",
                cardinalidad="N:N",
                porque="Se une por `(ide, conide)`, que aqui no se documentan.",
            ),
        ),
    )

    assert validar(
        _dicc(fichas=[ficha], pendientes=("stg.obras",)), PASOS_NOCTURNOS
    ) == []


def test_f006_r5_ninguna_clave_de_join_real_esta_inventada() -> None:
    """Sobre el diccionario REAL: es el test que habría cazado los dos casos."""
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    errores = [
        e
        for e in validar(_global_real(), pasos_del_pipeline_nocturno())
        if "clave de JOIN" in e.detalle
    ]

    assert errores == [], "\n" + formatear_errores(errores)


# ===========================================================================
# R2 · Un objeto puede NO tener clave de negocio, y decirlo
#
# `retenciones.v_src_lineas_compra` es `SELECT docide, obride FROM raw.dcfpro`:
# una fila por linea, sin deduplicar. NO tiene clave de negocio, y la que traia
# —el par entero— era precisamente el que produce el fan-out que el fichero
# declara como la regla que mas dinero ha costado.
#
# Exigir una clave siempre obliga a inventarsela, que es peor que no tenerla. Se
# admite declararla vacia, pero **solo fuera de la superficie de consumo**: si
# un objeto se recomienda para consultar, quien lo consulte necesita saber que
# identifica una fila, y R3 ya obliga a escribir el motivo de no recomendarlo.
# ===========================================================================


def test_f006_r2_fuera_del_consumo_se_admite_no_tener_clave() -> None:
    sin_clave = _ficha(
        consumo_recomendado=False,
        motivo_no_consumo="Vista interna del build; no deduplica y no tiene clave.",
        clave_negocio=(),
        ejemplos_preguntas=(),
    )

    assert validar(_dicc(fichas=[sin_clave]), PASOS_NOCTURNOS) == []


def test_f006_r2_dentro_del_consumo_la_clave_sigue_siendo_obligatoria() -> None:
    errores = validar(_dicc(fichas=[_ficha(clave_negocio=())]), PASOS_NOCTURNOS)

    assert errores
    assert any("clave_negocio" in e.detalle for e in errores)


def test_f006_r2_las_dos_vistas_fuente_declaran_que_no_tienen_clave() -> None:
    """Sobre el diccionario REAL: preferir el hueco a la clave inventada."""
    for objeto in ("v_src_lineas_compra", "v_src_lineas_venta"):
        ficha = _global_real().por_nombre[f"retenciones.{objeto}"]

        assert ficha.clave_negocio == ()
        assert ficha.consumo_recomendado is False
