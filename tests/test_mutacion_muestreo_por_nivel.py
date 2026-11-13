# tests/test_mutacion_muestreo_por_nivel.py
"""Cuánto cuesta una campaña lo decide el nivel de rigor.

Una campaña completa sobre una feature grande evalúa decenas de mutantes y
obliga a analizar por escrito cada superviviente, que es lo caro. El tope y la
semilla dejan de ser algo que hay que acordarse de teclear y pasan a vivir en
`harness/rigor.json`, por nivel: `estandar` muestreado y reproducible y, desde
F-058, `critico` con una regla proporcional (`test_f058_regla.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    InformeMutacion,
    _muestreo_configurado,
    resolver_muestreo,
)
from harness.rigor import cargar_rigor, max_mutantes_nivel, regla_nivel, semilla_nivel

#: Configuración INYECTADA en todos los tests de este fichero (F-038). Los
#: números son a propósito distintos de los del `harness/rigor.json` que
#: entrega el arnés: si un lector volviera a leer el fichero real en vez del
#: inyectado, estos tests caerían ya en el propio arnés, y no solo en el
#: proyecto que adapta su `rigor.json`.
TOPE_ESTANDAR = 13
SEMILLA_ESTANDAR = 4242

RIGOR = {
    "nivel_por_defecto": "estandar",
    "niveles": {
        "documental": {"fase_red": False, "cobertura": False, "mutacion": False},
        "estandar": {
            "fase_red": True,
            "cobertura": True,
            "mutacion": True,
            "max_mutantes": TOPE_ESTANDAR,
            "semilla": SEMILLA_ESTANDAR,
        },
        "critico": {
            "fase_red": True,
            "cobertura": True,
            "mutacion": True,
            "max_mutantes": None,
            "semilla": None,
        },
    },
}

#: Feature de ejemplo de los tests que necesitan una ficha en el backlog.
#:
#: «Guardián que pasa por casualidad» (2026-09-24). Hasta ese día estos tests
#: usaban "F-038" y `_muestreo_configurado` leía el `harness/features.json`
#: REAL del repositorio anfitrión. Pasaban solo porque allí F-038 no declaraba
#: `rigor` (o declaraba `estandar`): un proyecto le puso `"rigor": "critico"` a
#: SU F-038 y el arnés se puso en rojo sin que nada del arnés hubiera cambiado.
#: Un test del arnés no puede depender del backlog de quien lo instala: el id
#: es ficticio y la ficha se inyecta con `_backlog_con`.
FEATURE_FICTICIA = "F-990"


def _backlog_con(monkeypatch: pytest.MonkeyPatch, rigor: str) -> None:
    """El backlog que ve `harness.mutacion`: una sola ficha, con el nivel dado."""
    ficha = {"id": FEATURE_FICTICIA, "rigor": rigor}
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [ficha])


def _rigor_inyectado(
    monkeypatch: pytest.MonkeyPatch, directorio: Path, rigor: dict = RIGOR
) -> None:
    """La configuración que ven los lectores de `harness.mutacion`.

    La buscan en `harness/rigor.json` del directorio ACTUAL, así que se escribe
    en uno desechable y se trabaja desde allí. Misma lección que la de
    `FEATURE_FICTICIA`, aplicada al otro fichero (F-038): el `rigor.json` es
    del proyecto que instala el arnés, que lo adapta, y un test del arnés que
    leyera sus valores se pondría en rojo sin que nada del arnés cambiara.
    """
    (directorio / "harness").mkdir(parents=True, exist_ok=True)
    (directorio / "harness" / "rigor.json").write_text(json.dumps(rigor), encoding="utf-8")
    monkeypatch.chdir(directorio)


def test_el_nivel_estandar_declara_tope_y_semilla_en_rigor_json() -> None:
    assert max_mutantes_nivel("estandar", RIGOR) == TOPE_ESTANDAR
    assert semilla_nivel("estandar", RIGOR) == SEMILLA_ESTANDAR


def test_un_nivel_sin_tope_ni_regla_mide_la_campania_entera() -> None:
    """`None` es «sin tope»: sin claves de F-058 se evalúa todo lo generado.

    Hasta F-058 se llamaba `test_el_nivel_critico_no_tiene_tope_en_rigor_json`.
    El `critico` del payload ya lleva regla (uno por línea, 60 % en [100, 300]:
    `test_f058_textos.py`); aquí queda el MECANISMO, sobre la configuración
    inyectada: un nivel que no declara nada sigue midiendo entero.
    """
    assert max_mutantes_nivel("critico", RIGOR) is None
    assert semilla_nivel("critico", RIGOR) is None
    assert regla_nivel("critico", RIGOR) is None


def test_un_nivel_sin_las_claves_de_rigor_no_revienta() -> None:
    """Las claves son OPCIONALES: un `rigor.json` viejo sigue funcionando."""
    assert max_mutantes_nivel("documental", RIGOR) is None
    assert semilla_nivel("documental", RIGOR) is None


def test_un_nivel_que_no_existe_en_rigor_json_no_impone_tope() -> None:
    assert max_mutantes_nivel("inventado", RIGOR) is None
    assert semilla_nivel("inventado", RIGOR) is None


def test_un_tope_absurdo_del_rigor_json_se_trata_como_ausencia() -> None:
    """Misma doctrina que `workers_mutacion`: mejor el defecto que una campaña rara."""
    malos = {
        "niveles": {
            "cero": {"max_mutantes": 0},
            "negativo": {"max_mutantes": -3},
            "booleano": {"max_mutantes": True},
            "texto": {"max_mutantes": "20"},
        }
    }
    for nivel in malos["niveles"]:
        assert max_mutantes_nivel(nivel, malos) is None, nivel


def test_una_semilla_de_rigor_no_entera_se_trata_como_ausencia() -> None:
    malos = {"niveles": {"booleana": {"semilla": True}, "texto": {"semilla": "x"}}}
    for nivel in malos["niveles"]:
        assert semilla_nivel(nivel, malos) is None, nivel


def test_la_semilla_cero_es_una_semilla_valida_en_rigor_json() -> None:
    """A diferencia del tope, `0` no significa nada especial en una semilla."""
    assert semilla_nivel("cero", {"niveles": {"cero": {"semilla": 0}}}) == 0


# --- El `rigor.json` del proyecto: FORMA, no valores (F-038) ----------------
#
# Hasta F-038 estos dos tests fijaban los VALORES del fichero entregado (tope
# 20, semilla 20260820, `estandar` por defecto) y se ponían en rojo en cuanto
# un proyecto los adaptaba, que es justo para lo que existe el fichero. Ahora
# comprueban que lo declarado se puede leer: un tope o una semilla que el
# lector descartara en silencio (un "20" entre comillas, un 0, un booleano)
# convertiría la campaña muestreada en completa sin que nadie lo viera.


def test_el_rigor_json_del_proyecto_declara_tope_y_semilla_legibles() -> None:
    rigor = cargar_rigor()

    for nivel, definicion in rigor["niveles"].items():
        # Una campaña informativa (F-040) también se lanza: se vigila igual.
        if not definicion["mutacion"] and "mutacion" not in definicion.get("informativas", []):
            continue
        assert "max_mutantes" in definicion, f"{nivel}: falta 'max_mutantes'"
        assert "semilla" in definicion, f"{nivel}: falta 'semilla'"
        assert max_mutantes_nivel(nivel, rigor) == definicion["max_mutantes"], (
            f"{nivel}: el tope declarado no se puede leer y se ignoraría"
        )
        assert semilla_nivel(nivel, rigor) == definicion["semilla"], (
            f"{nivel}: la semilla declarada no se puede leer y se ignoraría"
        )


def test_el_nivel_por_defecto_del_rigor_json_del_proyecto_es_un_nivel_declarado() -> None:
    rigor = cargar_rigor()

    assert rigor["nivel_por_defecto"] in rigor["niveles"]


# --- R6, R7: precedencia de la orden sobre el nivel --------------------------


def test_lo_pedido_a_mano_gana_al_nivel() -> None:
    assert resolver_muestreo(5, 7, 20, 20260820) == (5, 7)


def test_sin_nada_pedido_manda_el_nivel() -> None:
    assert resolver_muestreo(None, None, 20, 20260820) == (20, 20260820)


def test_max_mutantes_cero_significa_sin_tope() -> None:
    """La única forma de anular desde la orden el tope que impone un nivel."""
    assert resolver_muestreo(0, None, 20, 20260820) == (None, 20260820)


def test_un_tope_negativo_tampoco_es_un_tope() -> None:
    assert resolver_muestreo(-1, None, 20, None) == (None, None)


def test_sin_nivel_ni_peticion_la_campania_es_completa() -> None:
    """Un `rigor.json` sin las claves nuevas mide todo, como hasta hoy."""
    assert resolver_muestreo(None, None, None, None) == (None, None)


def test_la_semilla_pedida_gana_sin_arrastrar_el_tope() -> None:
    assert resolver_muestreo(None, 1, 20, 20260820) == (20, 1)


@pytest.mark.parametrize(
    ("rigor", "esperado"),
    [
        ("estandar", (TOPE_ESTANDAR, SEMILLA_ESTANDAR, "estandar")),
        # El nivel que NO es el defecto: sin este caso, un `_muestreo_configurado`
        # que ignorase la ficha y aplicase siempre `nivel_por_defecto` pasaría.
        ("critico", (None, None, "critico")),
    ],
)
def test_el_muestreo_configurado_sale_del_nivel_de_la_feature(
    rigor: str, esperado: tuple, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _rigor_inyectado(monkeypatch, tmp_path)
    _backlog_con(monkeypatch, rigor)

    assert _muestreo_configurado(FEATURE_FICTICIA) == esperado


def test_una_feature_sin_ficha_cae_en_el_nivel_por_defecto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """R8: omitir el nivel aplica `nivel_por_defecto`, no el más caro.

    El caso que importa es que el defecto NO sea el primer nivel ni `critico`:
    por eso se inyecta uno cuyo defecto es `estandar`, entre los dos.
    """
    _rigor_inyectado(monkeypatch, tmp_path)
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [])

    assert _muestreo_configurado("F-999-no-existe") == (
        TOPE_ESTANDAR, SEMILLA_ESTANDAR, "estandar"
    )


def test_una_configuracion_ilegible_no_impone_muestreo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Misma red de seguridad que `_timeout_configurado`: se degrada, no se cae."""
    monkeypatch.chdir(tmp_path)

    assert _muestreo_configurado(FEATURE_FICTICIA) == (None, None, None)


# --- R6, R7 vistos desde el CLI ---------------------------------------------


def _campania_espia(capturado: dict):
    def falsa(alcance, ejecutor, **kwargs):
        capturado.update(kwargs)
        return InformeMutacion(feature=alcance.feature, alcance=alcance)

    return falsa


def _preparar_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capturado: dict
) -> list[str]:
    alcance = Alcance(
        feature=FEATURE_FICTICIA,
        origen="rama",
        ref_diff=("dev", f"feature/{FEATURE_FICTICIA}-ficticia"),
        lineas={"harness/mutacion.py": {1}},
    )
    _rigor_inyectado(monkeypatch, tmp_path)
    _backlog_con(monkeypatch, "estandar")
    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: alcance)
    monkeypatch.setattr(mutacion, "ejecutar_campania", _campania_espia(capturado))
    return [
        "--feature",
        FEATURE_FICTICIA,
        "--raiz",
        str(tmp_path),
        "--salida",
        str(tmp_path / "informe.md"),
    ]


def test_el_cli_sin_banderas_aplica_el_muestreo_del_nivel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    capturado: dict = {}

    mutacion.main(_preparar_cli(tmp_path, monkeypatch, capturado), ejecutor=object())

    assert capturado["max_mutantes"] == TOPE_ESTANDAR
    assert capturado["semilla"] == SEMILLA_ESTANDAR
    # Y se dice por pantalla: quien lanza la campaña tiene que ver que va
    # muestreada, o leerá 13 mutantes creyendo que son todos.
    assert (
        f"Muestreo: hasta {TOPE_ESTANDAR} mutantes, semilla {SEMILLA_ESTANDAR}"
        in capsys.readouterr().out
    )


def test_una_campania_completa_no_anuncia_muestreo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Sin tope no hay muestreo que anunciar: anunciarlo sería mentir."""
    capturado: dict = {}
    argv = _preparar_cli(tmp_path, monkeypatch, capturado) + ["--max-mutantes", "0"]

    mutacion.main(argv, ejecutor=object())

    assert "Muestreo:" not in capsys.readouterr().out


def test_el_cli_con_max_mutantes_cero_anula_el_tope_del_nivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capturado: dict = {}
    argv = _preparar_cli(tmp_path, monkeypatch, capturado) + ["--max-mutantes", "0"]

    mutacion.main(argv, ejecutor=object())

    assert capturado["max_mutantes"] is None, "0 = sin tope, no «cero mutantes»"


def test_un_tope_de_un_solo_mutante_es_un_tope_legitimo() -> None:
    """La frontera del `> 0`: pedir 1 mutante no puede leerse como «sin tope»."""
    assert resolver_muestreo(1, None, 20, 20260820) == (1, 20260820)


def test_un_nivel_de_rigor_puede_declarar_un_solo_mutante() -> None:
    """Misma frontera en el lector: `1` es un tope, no un valor absurdo."""
    assert max_mutantes_nivel("minimo", {"niveles": {"minimo": {"max_mutantes": 1}}}) == 1
