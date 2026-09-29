# tests/test_f025_settings.py
"""
F-025 · La configuración de la ventana: qué manda desde dónde (R5, T7).

Hay dos cosas distintas y conviene no mezclarlas, porque las cambian personas
distintas:

* **El CRITERIO** —qué estados congelan, el patrón de código, cuántos meses— es
  **regla de negocio** y vive en `config/business_rules.yaml`. Lo decide el
  humano con Negocio y cambiarlo no debe exigir tocar código ni redesplegar.
* **Los INTERRUPTORES** —encender la ventana, el día de la completa, el
  rescate— son de **operación** y viven en el entorno (`PG_VENTANA_*`).

El test que más importa aquí es el de **R5**: `PG_VENTANA_ACTIVA` nace en
`False`. Encender una feature que cambia lo que se reconstruye cada noche tiene
que ser una decisión explícita, no el efecto lateral de un despliegue.

Y el otro: que el bloque del YAML **cuadre con el censo del 2026-09-02**. Si
alguien edita esas tres reglas, el censo de 880 congeladas y 40 vivas deja de
ser cierto y la spec entera pasa a describir otra cosa.
"""

from __future__ import annotations

import pytest
import yaml

from config.settings import PostgresSettings
from etl_sigrid.domain.ventana import (
    BLOQUE_VENTANA,
    CLAVE_ESTADOS,
    CLAVE_MESES,
    CLAVE_PATRON,
    DOMINGO,
    Criterio,
    criterio_desde_reglas,
)

RUTA_REGLAS = "config/business_rules.yaml"


def reglas() -> dict:
    with open(RUTA_REGLAS, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# R5 · Los interruptores de operación
# ---------------------------------------------------------------------------


def test_f025_r5_la_ventana_nace_apagada() -> None:
    """**El test de R5.** «MIENTRAS la ventana esté desactivada, el
    comportamiento debe ser el de hoy: activarla es un interruptor explícito.»"""
    assert PostgresSettings.model_fields["ventana_activa"].default is False


def test_f025_r5_el_rescate_nace_apagado() -> None:
    """§3.1: la firma DENUNCIA, no rescata. Rescatar contradiría la decisión del
    humano de congelar 8 de las 48 obras con actividad reciente (R3)."""
    assert PostgresSettings.model_fields["ventana_rescate"].default is False


def test_f025_r25_el_dia_por_defecto_de_la_completa_es_DOMINGO() -> None:  # noqa: N802
    """DA-4, y la constante del dominio y el default de la configuración tienen
    que decir lo mismo: si divergen, la completa correría el día que no es y el
    «hasta 6 días» de R3 dejaría de cuadrar."""
    assert PostgresSettings.model_fields["ventana_dia_completa"].default == DOMINGO


def test_f025_r2_los_meses_por_defecto_son_doce() -> None:
    assert PostgresSettings.model_fields["ventana_meses"].default == 12


def test_f025_r2_un_numero_de_meses_no_positivo_se_rechaza() -> None:
    """Con cero meses la regla de actividad congelaría hasta la obra que cerró
    esta mañana. Se rechaza al construir la configuración, no en la nocturna."""
    with pytest.raises(ValueError):
        PostgresSettings(ventana_meses=0)


@pytest.mark.parametrize("dia", [-1, 7, 99])
def test_f025_r25_un_dia_de_la_semana_fuera_de_rango_se_rechaza(dia: int) -> None:
    """`date.weekday()` va de 0 a 6. Un 7 no dispararía nunca la completa, y eso
    es un silencio: las 880 obras congeladas para siempre."""
    with pytest.raises(ValueError):
        PostgresSettings(ventana_dia_completa=dia)


def test_f025_r5_los_cuatro_ajustes_llevan_el_prefijo_PG() -> None:  # noqa: N802
    """Van en `PostgresSettings`, cuyo `env_prefix` es `PG_`: son
    `PG_VENTANA_ACTIVA`, `PG_VENTANA_MESES`, `PG_VENTANA_DIA_COMPLETA` y
    `PG_VENTANA_RESCATE`, que es como los nombra la spec."""
    assert PostgresSettings.model_config["env_prefix"] == "PG_"

    for campo in (
        "ventana_activa",
        "ventana_meses",
        "ventana_dia_completa",
        "ventana_rescate",
    ):
        assert campo in PostgresSettings.model_fields


def test_f025_r5_ningun_ajuste_de_la_ventana_es_un_secreto() -> None:
    """Los cuatro son booleanos y enteros: nada que ocultar, y nada que pueda
    acabar en un log por descuido."""
    for campo in (
        "ventana_activa",
        "ventana_meses",
        "ventana_dia_completa",
        "ventana_rescate",
    ):
        assert PostgresSettings.model_fields[campo].annotation in (bool, int)


# ---------------------------------------------------------------------------
# El criterio, en business_rules.yaml
# ---------------------------------------------------------------------------


def test_f025_r2_el_yaml_declara_el_bloque_de_la_ventana() -> None:
    assert BLOQUE_VENTANA in reglas()


def test_f025_r2_el_criterio_del_yaml_es_EXACTAMENTE_el_que_decidio_el_humano() -> None:  # noqa: N802
    """**El censo de la spec depende de estas tres líneas.** 880 congeladas y 40
    vivas se midió con estos valores el 2026-09-02: si alguien los cambia, el
    censo deja de ser cierto y hay que volver a medirlo antes de decir nada."""
    criterio = criterio_desde_reglas(reglas())

    assert criterio.estados_que_congelan == frozenset({1, 11, 25})
    assert criterio.patron_codigo == "^[0-9]{6}$"
    assert criterio.meses_sin_actividad == 12


def test_f025_r2_el_patron_esta_anclado_por_los_DOS_extremos() -> None:  # noqa: N802
    """Sin el `$` congelaría los códigos de siete dígitos; sin el `^`,
    cualquiera que los contenga. Los dos anclajes son la regla, no estilo."""
    patron = criterio_desde_reglas(reglas()).patron_codigo

    assert patron.startswith("^")
    assert patron.endswith("$")


def test_f025_r2_los_meses_del_entorno_pueden_mandar_sobre_el_yaml() -> None:
    """`PG_VENTANA_MESES` ensancha la ventana una noche concreta sin cambiar la
    regla de Negocio ni hacer un commit."""
    assert criterio_desde_reglas(reglas(), meses=24).meses_sin_actividad == 24


def test_f025_r2_sin_meses_explicitos_manda_el_yaml() -> None:
    assert criterio_desde_reglas(reglas(), meses=None).meses_sin_actividad == 12


# ---------------------------------------------------------------------------
# Un YAML roto para antes de las 02:00, no a mitad del build
# ---------------------------------------------------------------------------


def test_f025_r2_un_yaml_sin_bloque_ventana_aborta_con_su_motivo() -> None:
    with pytest.raises(ValueError, match=BLOQUE_VENTANA):
        criterio_desde_reglas({"sigrid": {}})


def test_f025_r2_un_bloque_que_no_es_un_mapa_tampoco_cuela() -> None:
    with pytest.raises(ValueError, match=BLOQUE_VENTANA):
        criterio_desde_reglas({BLOQUE_VENTANA: [1, 11, 25]})


@pytest.mark.parametrize("clave", [CLAVE_ESTADOS, CLAVE_PATRON, CLAVE_MESES])
def test_f025_r2_una_clave_que_falta_se_nombra(clave: str) -> None:
    """Las tres reglas van en unión y ninguna es opcional. El mensaje dice cuál
    falta: quien edita el YAML no tiene por qué adivinarlo."""
    bloque = dict(reglas()[BLOQUE_VENTANA])
    del bloque[clave]

    with pytest.raises(ValueError, match=clave):
        criterio_desde_reglas({BLOQUE_VENTANA: bloque})


def test_f025_r2_una_lista_de_estados_que_no_son_enteros_se_rechaza() -> None:
    """Vienen de `conest` y son códigos numéricos. Un `"25"` con comillas no
    casaría nunca con el `estado_id` de la obra, y la ventana no congelaría
    nada **en silencio**."""
    bloque = dict(reglas()[BLOQUE_VENTANA], estados_que_congelan=["25"])

    with pytest.raises(ValueError, match=CLAVE_ESTADOS):
        criterio_desde_reglas({BLOQUE_VENTANA: bloque})


def test_f025_r2_una_lista_de_estados_vacia_es_legitima() -> None:
    """Quitar la regla de estados es una decisión de Negocio: quedan las otras
    dos. Lo que no es legítimo es que reviente en producción."""
    bloque = dict(reglas()[BLOQUE_VENTANA], estados_que_congelan=[])

    assert criterio_desde_reglas({BLOQUE_VENTANA: bloque}) == Criterio(
        estados_que_congelan=frozenset(),
        patron_codigo="^[0-9]{6}$",
        meses_sin_actividad=12,
    )


def test_f025_r2_los_booleanos_no_pasan_por_enteros() -> None:
    """`True` es subclase de `int` en Python, y `frozenset({True})` casaría con
    el estado 1 (EN ESTUDIO), que son 226 obras. Es el mismo cuidado que tiene
    el filtro de tramos de F-019."""
    bloque = dict(reglas()[BLOQUE_VENTANA], estados_que_congelan=[True])

    with pytest.raises(ValueError, match=CLAVE_ESTADOS):
        criterio_desde_reglas({BLOQUE_VENTANA: bloque})


def test_f025_r2_el_yaml_documenta_el_censo_y_la_contrapartida() -> None:
    """El bloque tiene que explicarse solo: quien lo edite dentro de un año
    tiene que ver ahí mismo el censo —880 congeladas y 40 vivas de 920— y que el
    humano rechazó el veto con el dato delante."""
    with open(RUTA_REGLAS, encoding="utf-8") as f:
        texto = f.read()

    bloque = texto[texto.index("LA VENTANA DE NEGOCIO") :]

    assert "880" in bloque and "40" in bloque, "el bloque no trae el censo"
    assert "6 dias" in bloque or "6 días" in bloque, (
        "el bloque no advierte de la contrapartida: hasta 6 dias de antiguedad"
    )
    assert "conest" in bloque, "el bloque no dice de donde sale el catalogo de estados"


# ---------------------------------------------------------------------------
# R5 · el tercer extremo: los interruptores, DECLARADOS EN EL DESPLIEGUE
#
# Un default en `settings.py` no llega a Azure por su cuenta. Hasta el
# 2026-09-04 ninguna `PG_VENTANA_*` figuraba en `80_create_job.ps1`, así que la
# ventana **no se podía encender en el job** más que con un `az ... --set-env-vars`
# suelto: un valor fuera del repositorio que desaparece sin ruido el día que
# alguien recrea el job, dejando la nocturna reconstruyendo las 920 obras otra
# vez. Es el modo de fallo de F-052 —algo que se degrada y nadie se entera—
# aplicado a la configuración, y agravado porque «apagada» es el comportamiento
# viejo y por tanto no llama la atención.
#
# Estos tres tests cierran el circuito nombre→valor→inyección. Los helpers de
# `infra/` se IMPORTAN de `test_f003_infra.py`, no se copian (F-024).
# ---------------------------------------------------------------------------

INTERRUPTORES = {
    "PG_VENTANA_ACTIVA": "ventanaActiva",
    "PG_VENTANA_MESES": "ventanaMeses",
    "PG_VENTANA_DIA_COMPLETA": "ventanaDiaCompleta",
    "PG_VENTANA_RESCATE": "ventanaRescate",
}


def test_f025_r5_el_job_inyecta_los_cuatro_interruptores_de_la_ventana() -> None:
    """Los cuatro `PG_VENTANA_*` se pasan al contenedor y **su valor sale del
    fichero de entorno**, no escrito a mano en el script."""
    from tests.test_f003_infra import _script

    texto = _script("80_create_job.ps1")

    for variable, clave in INTERRUPTORES.items():
        assert f'"{variable}=$($CFG.{clave})"' in texto, (
            f"80_create_job.ps1 no inyecta {variable} desde $CFG.{clave}: la "
            f"ventana no se puede configurar en el job sin un comando suelto"
        )


def test_f025_r5_el_entorno_declara_los_cuatro_y_la_ventana_NACE_APAGADA() -> None:  # noqa: N802
    """**El test de R5 en el despliegue.** `ventanaActiva` en `false` en TODOS
    los entornos: encenderla es una decisión explícita del humano, nunca el
    efecto lateral de crear el job.

    Booleanos como cadena, igual que `pgAutoCreateDb`: un `false` de JSON llega
    a PowerShell como `$false` y se interpolaría en el `--env-vars` como
    `False`, que no es lo que pydantic espera leer.
    """
    from tests.test_f003_infra import _config, _entornos

    for ruta in _entornos():
        cfg = _config(ruta.stem)
        faltan = sorted(set(INTERRUPTORES.values()) - set(cfg))
        assert not faltan, f"{ruta.name} no declara: {faltan}"
        assert cfg["ventanaActiva"] == "false", (
            f"{ruta.name} despliega la ventana ENCENDIDA; R5 dice que nace apagada"
        )
        assert cfg["ventanaRescate"] == "false", (
            f"{ruta.name} despliega el rescate encendido; §3.1: la firma denuncia"
        )


def test_f025_r5_el_entorno_y_el_codigo_no_divergen_en_lo_que_no_es_interruptor() -> None:  # noqa: N802
    """`ventanaMeses` y `ventanaDiaCompleta` no son interruptores que se enciendan:
    son **el criterio**, y el contenedor no lleva `dev.json`, así que el valor
    está duplicado. Si divergen, la nocturna corre con una ventana y todo lo que
    está escrito —spec, censo, `--help`— describe otra. Misma red que
    `test_f024_r19_umbral_por_defecto_coincide_con_dev_json`.

    `ventanaActiva` y `ventanaRescate` quedan FUERA a propósito: esos sí son
    interruptores y el día que el humano encienda la ventana, `dev.json` dirá
    `true` donde el código sigue diciendo `False`, que es justo lo que R5 quiere.
    """
    from tests.test_f003_infra import _config

    cfg = _config("dev")

    assert cfg["ventanaMeses"] == PostgresSettings.model_fields["ventana_meses"].default
    assert (
        cfg["ventanaDiaCompleta"]
        == PostgresSettings.model_fields["ventana_dia_completa"].default
        == DOMINGO
    )
