# tests/test_f006_frescura.py
"""
F-006 · Tests de frescura del diccionario (R13, R14).

Por qué esto importa más de lo que parece. Hasta el 2026-08-28 `run-all`
construía `raw -> stg -> mart` y aplicaba los grants, y **`cierre`, `compras`,
`maestro` y `retenciones` NO estaban en el pipeline nocturno**: se construían
con comandos propios y podían estar arbitrariamente desfasados. F-047 metió los
cuatro dentro, así que la mentira que este fichero vigila **ha cambiado de
sentido**: ya no es declararse nocturno sin serlo, sino declararse `manual`
corriendo de noche, que hace que el agente desconfíe de un dato bueno y cite una
fecha que no hacía falta citar. Las dos direcciones se comprueban igual.

La lista de pasos nocturnos **no se copia a mano**: se lee de
`main.build_pipeline_steps`, la composición real. Esa decisión de diseño es lo
que hizo que el veredicto cambiara solo el día que `build-cierre` entró: ni el
validador ni estos tests tenían una lista escrita a mano que actualizar.

Ningún test de este fichero abre red ni BBDD: `build_pipeline_steps` solo
construye objetos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import main
from etl_sigrid.domain.diccionario import validar
from tests.test_f006_formato import _dicc, _ficha


def _settings_falso() -> SimpleNamespace:
    """Lo mínimo que miran los constructores de los steps del pipeline."""
    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )


def pasos_del_pipeline_nocturno() -> tuple[str, ...]:
    """Los pasos que corren de noche, leídos de la composición REAL.

    Es la única fuente admisible: una lista copiada aquí se desincronizaría el
    día que alguien cambie `run-all`, y el diccionario seguiría prometiendo una
    frescura que ya no existe.
    """
    return tuple(s.name for s in main.build_pipeline_steps(_settings_falso()))


PASOS_NOCTURNOS = pasos_del_pipeline_nocturno()

#: Los cuatro esquemas que se construían a mano y entraron en la nocturna con
#: F-047. Se conservan como grupo porque siguen siendo un caso aparte: su paso
#: no es dependencia de ningún otro, así que puede fallar sin tumbar la noche.
ESQUEMAS_QUE_ENTRARON = ("cierre", "compras", "maestro", "retenciones")


# ---------------------------------------------------------------------------
# La composición real del pipeline
# ---------------------------------------------------------------------------


def test_f006_r14_el_pipeline_nocturno_es_este_e_incluye_los_cuatro() -> None:
    """Si esto cambia, cambia el veredicto de R14, y así debe ser."""
    assert PASOS_NOCTURNOS == (
        "ingest_raw",
        "load_excel_aux",
        "build_stg",
        "build_mart",
        "build_maestros",
        "build_compras",
        "build_retenciones",
        "build_cierre",
        "publicar_diccionario",
        "apply_grants",
    )
    for paso in ("build_cierre", "build_maestros", "build_compras",
                 "build_retenciones"):
        assert paso in PASOS_NOCTURNOS


# ---------------------------------------------------------------------------
# R13 · `refresco` y `paso_etl` declarados
# ---------------------------------------------------------------------------


def test_f006_r13_sin_paso_etl_falla() -> None:
    errores = validar(_dicc(fichas=[_ficha(paso_etl=None)]), PASOS_NOCTURNOS)

    assert errores
    assert any("paso_etl" in e.detalle for e in errores)


def test_f006_r13_un_paso_etl_en_blanco_tampoco_vale() -> None:
    errores = validar(_dicc(fichas=[_ficha(paso_etl="   ")]), PASOS_NOCTURNOS)

    assert any("paso_etl" in e.detalle for e in errores)


def test_f006_r13_refresco_estatico_esta_exento_de_paso_etl() -> None:
    """Lo que no se reconstruye no tiene paso que citar."""
    estatica = _ficha(
        esquema="aux",
        objeto="periodificacion_partida",
        capa="preparacion",
        refresco="estatico",
        paso_etl=None,
        consumo_recomendado=False,
        motivo_no_consumo="Hoy se crea vacía por diseño: no periodifica nada.",
        columnas=(),
        ejemplos_preguntas=(),
    )

    assert validar(_dicc(fichas=[estatica]), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R14 · Nadie se declara nocturno sin estar en el pipeline nocturno
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("esquema", ESQUEMAS_QUE_ENTRARON)
def test_f006_r14_un_paso_que_no_corre_de_noche_no_puede_ser_nocturno(
    esquema: str,
) -> None:
    """Es la mentira que produce respuestas de hace semanas dadas con aplomo.

    Se prueba con un paso INVENTADO (`build_<esquema>_a_mano`) en vez de con el
    paso real, porque los cuatro reales ya corren de noche desde F-047. La
    dirección del error es la misma y sigue vigilada; lo que ya no se puede es
    ilustrarla con un esquema concreto del repositorio.
    """
    mentirosa = _ficha(
        esquema=esquema,
        objeto="un_objeto",
        refresco="nocturno",
        paso_etl=f"build_{esquema}_a_mano",
    )

    errores = validar(_dicc(fichas=[mentirosa]), PASOS_NOCTURNOS)

    assert errores, f"{esquema} declarándose nocturno tenía que fallar"
    assert any(e.regla == "R14" for e in errores)
    assert any(f"build_{esquema}_a_mano" in e.detalle for e in errores)


def test_f006_r14_declararse_manual_con_un_paso_nocturno_tambien_falla() -> None:
    """La mentira simétrica: `mart` se construye de noche y decir lo contrario
    haría que el agente citase una fecha de build que no hace falta citar."""
    mentirosa = _ficha(refresco="manual", paso_etl="build_mart")

    errores = validar(_dicc(fichas=[mentirosa]), PASOS_NOCTURNOS)

    assert errores
    assert any(e.regla == "R14" for e in errores)


def test_f006_r14_una_ficha_nocturna_con_paso_del_pipeline_valida() -> None:
    assert validar(_dicc(), PASOS_NOCTURNOS) == []


def test_f006_r14_una_ficha_manual_con_paso_fuera_del_pipeline_valida() -> None:
    correcta = _ficha(
        esquema="cierre",
        objeto="fact_cierre_mensual",
        refresco="manual",
        paso_etl="build_cierre_a_mano",
    )

    assert validar(_dicc(fichas=[correcta]), PASOS_NOCTURNOS) == []


def test_f006_r14_el_veredicto_sigue_al_pipeline_y_no_a_una_lista_copiada() -> None:
    """Y PASÓ DE VERDAD: el 2026-08-28 `build_cierre` entró en `run-all` y las
    doce fichas de `cierre` pasaron a valer sin tocar una línea del validador.

    Este test es la razón de que `pasos_nocturnos` se inyecte: comprueba que el
    validador obedece a la composición que le den, no a una constante suya. Se
    conserva con un paso que sigue fuera del pipeline, porque lo que fija es el
    mecanismo, no qué esquema está dentro esta semana.
    """
    ficha = _ficha(esquema="cierre", objeto="fact_cierre_mensual",
                   refresco="nocturno", paso_etl="build_cierre_a_mano")
    dicc = _dicc(fichas=[ficha])

    assert validar(dicc, PASOS_NOCTURNOS), "ese paso no corre de noche"
    assert validar(dicc, (*PASOS_NOCTURNOS, "build_cierre_a_mano")) == []


def test_f006_r14_refresco_estatico_no_se_cruza_con_el_pipeline() -> None:
    """Lo estático no participa: ni se exige paso, ni se compara contra nada."""
    estatica = _ficha(refresco="estatico", paso_etl=None)

    assert validar(_dicc(fichas=[estatica]), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R16 · El diccionario dice CÓMO se obtiene la fecha de build
# ---------------------------------------------------------------------------


def test_f006_r16_el_global_real_dice_como_citar_la_fecha_de_build() -> None:
    """No basta con decir «cita la fecha»: hay que decir de dónde se saca.

    Una instrucción que el agente no puede ejecutar es una instrucción que no se
    cumple, y el resultado es el mismo que no haberla escrito: un dato de hace
    semanas dado sin advertencia.
    """
    from pathlib import Path

    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(
        Path(__file__).resolve().parents[1] / "config" / "diccionario"
    )
    regla = next(r for r in dicc.reglas if r.codigo == "R-FRESCURA")

    assert "_meta.v_frescura" in regla.regla
    assert "SELECT" in regla.regla.upper()
    assert regla.severidad == "bloqueante"


def test_f006_r16_el_regimen_del_global_coincide_con_el_pipeline() -> None:
    """Lo que el bloque global promete tiene que ser lo que el pipeline hace."""
    from pathlib import Path

    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(
        Path(__file__).resolve().parents[1] / "config" / "diccionario"
    )

    for nombre, entrada in dicc.esquemas.items():
        pasos = entrada.get("pasos_etl") or []
        if entrada["refresco"] == "nocturno":
            assert pasos, f"{nombre}: se declara nocturno y no cita ningún paso"
            assert all(p in PASOS_NOCTURNOS for p in pasos), (
                f"{nombre}: cita pasos que no corren de noche: {pasos}"
            )
        elif entrada["refresco"] == "manual":
            assert all(p not in PASOS_NOCTURNOS for p in pasos), (
                f"{nombre}: se declara manual pero sus pasos corren de noche"
            )
