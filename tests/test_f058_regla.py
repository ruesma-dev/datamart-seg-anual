# tests/test_f058_regla.py
"""F-058: qué mutantes se eligen, según el nivel de rigor y el tamaño.

Funciones puras salvo las que pasan por `ejecutar_campania`, que usan un
fuente de juguete en `tmp_path` y un ejecutor falso: ni suite real ni red.
"""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    PYTEST_OK,
    Mutante,
    ResultadoSuite,
    _muestreo_configurado,
    _regla_configurada,
    ejecutar_campania,
    generar_mutantes,
    reducir_por_linea,
    resolver_muestreo,
    resolver_regla,
    seleccionar,
)
from harness.mutacion_paralela import ejecutar_campania_paralela, generar_y_muestrear
from harness.rigor import (
    ReglaMuestreo,
    cargar_rigor,
    max_mutantes_nivel,
    regla_nivel,
    semilla_nivel,
    umbral_cobertura,
)
from harness.rigor import main as rigor_main

#: El `rigor.json` publicado antes de F-058, literal: el dato de R26.
PUBLICADO = cargar_rigor(Path(__file__).with_name("f058_rigor_publicado.json"))

FICHERO = "app/juguete.py"


def _fuente(lineas: int = 30) -> str:
    """Un módulo con varios operadores mutables en cada línea."""
    cuerpo = [f"# {FICHERO}"]
    for i in range(1, lineas + 1):
        cuerpo.append(f"v{i} = ({i} + 2 - 3) * 4 if {i} == 2 or {i} < 5 else 0")
    return "\n".join(cuerpo) + "\n"


def _clave(mutante: Mutante) -> tuple:
    return (mutante.fichero, mutante.linea, mutante.col, mutante.operador)


class _EjecutorMuerto:
    """Todo mutante muere; no hay suite ni línea base que correr."""

    raiz = "."

    def ejecutar(self, timeout_s: int) -> str:
        return "muerto"


def _campania(tmp_path: Path, lineas: int = 30, **kwargs) -> tuple[list[Mutante], object]:
    """Corre `ejecutar_campania` sobre el juguete y devuelve (generados, informe)."""
    fuente = _fuente(lineas)
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / FICHERO).write_text(fuente, encoding="utf-8", newline="")
    numeros = set(range(2, lineas + 2))
    alcance = Alcance(
        feature="F-990", origen="ficheros", ref_diff=("", ""), lineas={FICHERO: numeros}
    )
    informe = ejecutar_campania(
        alcance,
        _EjecutorMuerto(),
        raiz=str(tmp_path),
        comprobar_arbol=False,
        comprobar_base=False,
        **kwargs,
    )
    return generar_mutantes(fuente, numeros, FICHERO), informe


# --- R26: un rigor.json sin claves nuevas resuelve lo de hoy -----------------


def test_f058_r26_el_rigor_publicado_resuelve_tope_semilla_y_umbral_de_hoy() -> None:
    assert max_mutantes_nivel("estandar", PUBLICADO) == 20
    assert semilla_nivel("estandar", PUBLICADO) == 20260820
    assert max_mutantes_nivel("critico", PUBLICADO) is None
    assert semilla_nivel("critico", PUBLICADO) is None
    assert umbral_cobertura(PUBLICADO) == 80


def test_f058_r26_la_campania_estandar_elige_los_mutantes_de_hoy(tmp_path: Path) -> None:
    """Oráculo: el sorteo de hoy escrito aparte, `Random(semilla).sample`."""
    generados, informe = _campania(
        tmp_path,
        max_mutantes=max_mutantes_nivel("estandar", PUBLICADO),
        semilla=semilla_nivel("estandar", PUBLICADO),
    )
    esperado = sorted(random.Random(20260820).sample(generados, 20), key=_clave)

    assert len(generados) > 20
    assert informe.mutantes_evaluados == esperado
    assert informe.muestreado is True


def test_f058_r26_la_campania_critico_publicada_es_entera(tmp_path: Path) -> None:
    generados, informe = _campania(
        tmp_path, max_mutantes=max_mutantes_nivel("critico", PUBLICADO)
    )

    assert informe.mutantes_evaluados == generados
    assert informe.muestreado is False


# --- R3–R6: la regla del nivel (rigor.py) -------------------------------------

#: Base válida sobre la que cada caso de R6 rompe una sola clave.
BASE = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": False},
        "critico": {
            "fase_red": True,
            "cobertura": True,
            "mutacion": True,
            "un_mutante_por_linea": True,
            "fraccion_mutantes": 0.6,
            "min_mutantes": 100,
            "max_mutantes": 300,
            "semilla": 20261030,
        },
    },
}


def _con(nivel: str = "critico", **claves) -> dict:
    datos = json.loads(json.dumps(BASE))
    for clave, valor in claves.items():
        if valor is _QUITAR:
            datos["niveles"][nivel].pop(clave, None)
        else:
            datos["niveles"][nivel][clave] = valor
    return datos


_QUITAR = object()


def test_f058_r3_la_fraccion_se_acota_entre_suelo_y_techo() -> None:
    regla = regla_nivel("critico", BASE)

    assert regla == ReglaMuestreo(
        por_linea=True, fraccion=0.6, suelo=100, techo=300, origen="nivel"
    )
    assert regla.tope(50) == 100      # 30 → suelo
    assert regla.tope(167) == 101     # 100,2 → techo de la fracción, por arriba
    assert regla.tope(200) == 120
    assert regla.tope(500) == 300     # 300 justo
    assert regla.tope(1000) == 300    # 600 → techo


def test_f058_r3_el_redondeo_es_exacto_y_hacia_arriba() -> None:
    """0,6 × 5 en coma flotante es 3,0000000000000004: `ceil` daría 4."""
    regla = ReglaMuestreo(por_linea=False, fraccion=0.6, suelo=None, techo=None,
                          origen="nivel")

    assert regla.tope(5) == 3
    assert regla.tope(7) == 5
    assert regla.tope(10) == 6
    assert regla.tope(1) == 1


def test_f058_r3_sin_techo_ni_suelo_la_fraccion_manda_sola() -> None:
    regla = regla_nivel("critico", _con(max_mutantes=None, min_mutantes=_QUITAR))

    assert regla.techo is None and regla.suelo is None
    assert regla.tope(1000) == 600


def test_f058_r4_sin_fraccion_el_tope_es_fijo_y_el_suelo_se_ignora() -> None:
    regla = regla_nivel("critico", _con(fraccion_mutantes=_QUITAR, max_mutantes=20,
                                        min_mutantes=10))

    assert regla.fraccion is None and regla.suelo is None
    assert regla.tope(5) == 20
    assert regla.tope(1000) == 20


def test_f058_r4_sin_fraccion_ni_tope_ni_por_linea_no_hay_regla() -> None:
    assert regla_nivel("estandar", BASE) is None
    assert regla_nivel("inventado", BASE) is None
    assert regla_nivel("critico", PUBLICADO) is None


def test_f058_r4_uno_por_linea_sin_tope_es_regla_sin_tope() -> None:
    regla = regla_nivel("estandar", _con("estandar", un_mutante_por_linea=True))

    assert regla.por_linea is True
    assert regla.tope(10_000) is None


def test_f058_r4_el_tope_fijo_publicado_es_regla_de_tope_fijo() -> None:
    regla = regla_nivel("estandar", PUBLICADO)

    assert regla == ReglaMuestreo(por_linea=False, fraccion=None, suelo=None,
                                  techo=20, origen="nivel")


def test_f058_r2_uno_por_linea_false_es_como_no_declararlo() -> None:
    regla = regla_nivel("critico", _con(un_mutante_por_linea=False))

    assert regla.por_linea is False


@pytest.mark.parametrize(
    ("clave", "valor"),
    [
        ("fraccion_mutantes", 0),
        ("fraccion_mutantes", -0.1),
        ("fraccion_mutantes", 1.5),
        ("fraccion_mutantes", True),
        ("fraccion_mutantes", "0.6"),
        ("fraccion_mutantes", None),
        ("min_mutantes", 0),
        ("min_mutantes", 1.5),
        ("min_mutantes", True),
        ("min_mutantes", "100"),
        ("min_mutantes", 301),
        ("un_mutante_por_linea", "si"),
        ("un_mutante_por_linea", 1),
        ("un_mutante_por_linea", None),
    ],
)
def test_f058_r6_una_clave_nueva_rara_es_error_con_nivel_y_clave(
    clave: str, valor: object, tmp_path: Path
) -> None:
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(_con(**{clave: valor})), encoding="utf-8")
    features = tmp_path / "features.json"
    features.write_text('{"features": []}', encoding="utf-8")

    with pytest.raises(ValueError) as error:
        cargar_rigor(ruta)
    assert "'critico'" in str(error.value) and clave in str(error.value)
    assert rigor_main(["--validar", "--config", str(ruta),
                       "--features", str(features)]) == 1


@pytest.mark.parametrize(
    "claves",
    [
        {"fraccion_mutantes": 1},
        {"fraccion_mutantes": 1.0},
        {"fraccion_mutantes": 0.01},
        {"min_mutantes": 1},
        {"min_mutantes": 300},
        {"max_mutantes": None, "min_mutantes": 5000},
        {"un_mutante_por_linea": False},
    ],
)
def test_f058_r6_los_valores_legitimos_pasan(claves: dict, tmp_path: Path) -> None:
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(_con(**claves)), encoding="utf-8")

    assert cargar_rigor(ruta)["niveles"]["critico"]


def test_f058_r6_sin_claves_nuevas_cargar_rigor_no_cambia() -> None:
    assert cargar_rigor(Path(__file__).with_name("f058_rigor_publicado.json")) == PUBLICADO


# --- R1, R2, R5: reducción por línea y selección (mutacion.py) ---------------


def _generados(lineas: int = 30) -> list[Mutante]:
    return generar_mutantes(_fuente(lineas), set(range(2, lineas + 2)), FICHERO)


def _regla(**campos) -> ReglaMuestreo:
    base = {"por_linea": False, "fraccion": None, "suelo": None, "techo": None,
            "origen": "nivel"}
    return ReglaMuestreo(**{**base, **campos})


def test_f058_r1_reducir_deja_uno_por_linea_y_de_esa_linea() -> None:
    generados = _generados()
    reducidos = reducir_por_linea(generados, random.Random(7))

    assert len(generados) > 3 * len(reducidos)
    assert [m.linea for m in reducidos] == sorted({m.linea for m in generados})
    for mutante in reducidos:
        assert mutante in generados


def test_f058_r1_el_elegido_de_cada_linea_sale_de_la_semilla() -> None:
    generados = _generados()

    uno = reducir_por_linea(generados, random.Random(7))
    assert uno == reducir_por_linea(generados, random.Random(7))
    assert uno != reducir_por_linea(generados, random.Random(8))
    # No es siempre el primero de la línea: hay sorteo de verdad.
    primeros = {m.linea: m for m in reversed(generados)}
    assert uno != [primeros[m.linea] for m in uno]


def test_f058_r1_seleccionar_reduce_antes_de_contar_candidatos() -> None:
    generados = _generados()

    elegidos, candidatos, limite = seleccionar(generados, _regla(por_linea=True), 7)

    assert candidatos == 30 and limite is None
    assert elegidos == reducir_por_linea(generados, random.Random(7))


def test_f058_r1_la_reduccion_distingue_ficheros() -> None:
    a = generar_mutantes(_fuente(3), {2, 3, 4}, "app/a.py")
    b = generar_mutantes(_fuente(3), {2, 3, 4}, "app/b.py")

    reducidos = reducir_por_linea(a + b, random.Random(1))

    assert [(m.fichero, m.linea) for m in reducidos] == [
        ("app/a.py", 2), ("app/a.py", 3), ("app/a.py", 4),
        ("app/b.py", 2), ("app/b.py", 3), ("app/b.py", 4),
    ]


def test_f058_r2_sin_por_linea_los_candidatos_son_todos() -> None:
    generados = _generados()

    elegidos, candidatos, limite = seleccionar(generados, _regla(techo=10_000), 7)

    assert candidatos == len(generados) and limite == 10_000
    assert elegidos == generados


def test_f058_r2_sin_por_linea_el_sorteo_es_el_de_hoy() -> None:
    generados = _generados()

    elegidos, _, _ = seleccionar(generados, _regla(techo=20), 20260820)

    assert elegidos == sorted(random.Random(20260820).sample(generados, 20), key=_clave)


def test_f058_r5_con_pocos_candidatos_se_evaluan_todos_sin_sortear() -> None:
    generados = _generados(30)
    regla = _regla(por_linea=True, fraccion=0.6, suelo=100, techo=300)

    elegidos, candidatos, limite = seleccionar(generados, regla, 3)

    assert (candidatos, limite) == (30, 100)
    assert elegidos == reducir_por_linea(generados, random.Random(3))


def test_f058_r5_justo_en_el_tope_tampoco_se_sortea() -> None:
    generados = _generados(20)

    elegidos, candidatos, limite = seleccionar(generados, _regla(por_linea=True, techo=20), 3)

    assert candidatos == limite == 20
    assert elegidos == reducir_por_linea(generados, random.Random(3))


def test_f058_r3_con_muchos_candidatos_se_sortea_la_fraccion() -> None:
    generados = _generados(400)
    regla = _regla(por_linea=True, fraccion=0.6, suelo=100, techo=300)

    elegidos, candidatos, limite = seleccionar(generados, regla, 3)

    assert (candidatos, limite) == (400, 240)
    assert len(elegidos) == 240
    assert elegidos == sorted(elegidos, key=_clave)
    reducidos = reducir_por_linea(generados, random.Random(3))
    assert set(elegidos) <= set(reducidos)
    # Mismo `Random`: el sorteo sigue a la reducción, no vuelve a sembrar.
    rng = random.Random(3)
    reducir_por_linea(generados, rng)
    assert elegidos == sorted(rng.sample(reducidos, 240), key=_clave)


def test_f058_r26_seleccionar_con_la_regla_publicada_es_el_sorteo_de_hoy() -> None:
    generados = _generados()
    regla = regla_nivel("estandar", PUBLICADO)

    elegidos, candidatos, limite = seleccionar(generados, regla, 20260820)

    assert (candidatos, limite) == (len(generados), 20)
    assert elegidos == sorted(random.Random(20260820).sample(generados, 20), key=_clave)


# --- R7, R27: la orden frente al nivel ----------------------------------------

CRITICO = _regla(por_linea=True, fraccion=0.6, suelo=100, techo=300)


def test_f058_r7_sin_peticion_manda_el_nivel() -> None:
    assert resolver_regla(None, CRITICO) is CRITICO
    assert resolver_regla(None, None) is None


def test_f058_r7_un_tope_pedido_es_fijo_y_conserva_el_uno_por_linea() -> None:
    regla = resolver_regla(30, CRITICO)

    assert regla == _regla(por_linea=True, techo=30, origen="orden")
    assert regla.tope(1000) == 30
    assert regla.motivo(1000, "critico") == "fijado a mano con `--max-mutantes`"


def test_f058_r7_cero_es_sin_tope_conservando_el_uno_por_linea() -> None:
    assert resolver_regla(0, CRITICO) == _regla(por_linea=True, origen="orden")
    assert resolver_regla(-4, CRITICO) == _regla(por_linea=True, origen="orden")


def test_f058_r7_cero_sin_uno_por_linea_es_la_campania_entera() -> None:
    assert resolver_regla(0, _regla(techo=20)) is None
    assert resolver_regla(0, None) is None


def test_f058_r7_un_tope_pedido_sin_regla_del_nivel() -> None:
    assert resolver_regla(1, None) == _regla(techo=1, origen="orden")


def test_f058_r7_la_semilla_se_sigue_resolviendo_aparte() -> None:
    assert resolver_muestreo(30, None, None, 20261030) == (30, 20261030)
    assert resolver_muestreo(None, 5, 20, 20261030) == (20, 5)


def _configurar(monkeypatch: pytest.MonkeyPatch, directorio: Path, rigor: dict,
                nivel: str) -> None:
    (directorio / "harness").mkdir(parents=True, exist_ok=True)
    (directorio / "harness" / "rigor.json").write_text(json.dumps(rigor), encoding="utf-8")
    monkeypatch.chdir(directorio)
    ficha = {"id": "F-990", "rigor": nivel}
    monkeypatch.setattr(mutacion, "cargar_features", lambda *a, **k: [ficha])


def test_f058_r27_la_regla_configurada_sale_del_nivel_de_la_feature(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configurar(monkeypatch, tmp_path, BASE, "critico")

    assert _regla_configurada("F-990") == (CRITICO, 20261030, "critico")
    # Y la firma de hoy no cambia: tope fijo (techo) y semilla del nivel.
    assert _muestreo_configurado("F-990") == (300, 20261030, "critico")


def test_f058_r27_sin_regla_en_el_nivel_la_configurada_es_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configurar(monkeypatch, tmp_path, BASE, "estandar")

    assert _regla_configurada("F-990") == (None, None, "estandar")


def test_f058_r27_una_configuracion_ilegible_se_degrada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    assert _regla_configurada("F-990") == (None, None, None)


# --- R8: la misma muestra en serie y en paralelo ------------------------------


class _Doble:
    """Ejecutor falso con línea base verde: todo mutante muere."""

    def __init__(self, raiz: str = ".") -> None:
        self.raiz = raiz

    def identidad(self) -> tuple[str, str]:
        return (self.raiz, "doble")

    def ejecutar(self, timeout_s: int) -> str:
        return "muerto"

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        return ResultadoSuite(codigo=PYTEST_OK)


def _repo(tmp_path: Path, lineas: int) -> Alcance:
    (tmp_path / "app").mkdir()
    (tmp_path / FICHERO).write_text(_fuente(lineas), encoding="utf-8", newline="")
    for orden in (["init", "-q"], ["config", "user.email", "arnes@ejemplo.invalid"],
                  ["config", "user.name", "Arnes"], ["add", "-A"],
                  ["commit", "-q", "-m", "base"]):
        subprocess.run(["git", "-C", str(tmp_path), *orden], capture_output=True, check=True)
    return Alcance(feature="F-990", origen="ficheros", ref_diff=("", ""),
                   lineas={FICHERO: set(range(2, lineas + 2))})


def test_f058_r8_serie_y_paralela_eligen_los_mismos_mutantes(tmp_path: Path) -> None:
    alcance = _repo(tmp_path, 60)
    regla = _regla(por_linea=True, fraccion=0.5, suelo=10, techo=40)

    serie = ejecutar_campania(alcance, _Doble(str(tmp_path)), raiz=str(tmp_path),
                              regla=regla, semilla=11)
    paralela = ejecutar_campania_paralela(
        alcance, servicios=[], timeout_s=5, raiz=str(tmp_path), workers=2,
        regla=regla, semilla=11, fabrica=lambda _f, raiz: _Doble(raiz),
    )

    assert serie.candidatos == paralela.candidatos == 60
    assert serie.max_mutantes == paralela.max_mutantes == 30
    assert serie.muestreado is paralela.muestreado is True
    assert serie.regla == paralela.regla == regla
    assert serie.generados == paralela.generados > 60
    assert sorted(serie.mutantes_evaluados, key=_clave) == paralela.mutantes_evaluados
    assert len(paralela.mutantes_evaluados) == 30


def test_f058_r8_generar_y_muestrear_con_regla_es_seleccionar(tmp_path: Path) -> None:
    alcance = _repo(tmp_path, 60)
    regla = _regla(por_linea=True, techo=25)

    elegidos, generados, muestreado = generar_y_muestrear(
        alcance, str(tmp_path), semilla=11, regla=regla
    )

    assert (generados, muestreado) == (len(_generados(60)), True)
    assert elegidos == seleccionar(_generados(60), regla, 11)[0]


def test_f058_r8_sin_regla_generar_y_muestrear_es_el_de_hoy(tmp_path: Path) -> None:
    alcance = _repo(tmp_path, 10)

    elegidos, _, muestreado = generar_y_muestrear(alcance, str(tmp_path), 5, 3)

    assert (len(elegidos), muestreado) == (5, True)
    assert elegidos == sorted(random.Random(3).sample(_generados(10), 5), key=_clave)


def test_f058_r8_la_paralela_acepta_una_lista_de_mutantes_dada(tmp_path: Path) -> None:
    alcance = _repo(tmp_path, 10)
    dados = _generados(10)[:4]

    informe = ejecutar_campania_paralela(
        alcance, servicios=[], timeout_s=5, raiz=str(tmp_path), workers=2,
        mutantes=dados, fabrica=lambda _f, raiz: _Doble(raiz),
    )

    assert informe.mutantes_evaluados == sorted(dados, key=_clave)
    assert (informe.generados, informe.muertos, informe.muestreado) == (4, 4, False)


def test_f058_r8_sin_regla_la_campania_en_serie_no_cambia(tmp_path: Path) -> None:
    _, informe = _campania(tmp_path)

    assert informe.regla is None and informe.candidatos is None


# --- T19: supervivientes de la campaña de F-058 ---------------------------------
# «Muestreado» es lo que decide la fila «Muestreo» y la cota de la regla del tres:
# con todos los candidatos evaluados NO es una muestra, tampoco justo en el tope.


def test_f058_t19_con_regla_y_todos_los_candidatos_no_es_muestra(tmp_path: Path) -> None:
    _, informe = _campania(tmp_path, lineas=10, regla=_regla(por_linea=True, techo=10),
                           semilla=3)

    assert (informe.candidatos, informe.evaluados) == (10, 10)
    assert informe.muestreado is False


def test_f058_t19_sin_regla_un_tope_igual_a_los_generados_no_es_muestra(
    tmp_path: Path,
) -> None:
    generados = _generados(3)

    _, informe = _campania(tmp_path, lineas=3, max_mutantes=len(generados), semilla=1)

    assert informe.evaluados == len(generados)
    assert informe.muestreado is False


def test_f058_t19_generar_y_muestrear_sin_sorteo_no_es_muestra(tmp_path: Path) -> None:
    alcance = _repo(tmp_path, 10)

    elegidos, _, muestreado = generar_y_muestrear(
        alcance, str(tmp_path), semilla=11, regla=_regla(por_linea=True, techo=10)
    )

    assert (len(elegidos), muestreado) == (10, False)


def test_f058_t19_la_paralela_con_todos_los_candidatos_no_es_muestra(
    tmp_path: Path,
) -> None:
    alcance = _repo(tmp_path, 10)

    informe = ejecutar_campania_paralela(
        alcance, servicios=[], timeout_s=5, raiz=str(tmp_path), workers=2,
        regla=_regla(por_linea=True, techo=10), semilla=11,
        fabrica=lambda _f, raiz: _Doble(raiz),
    )

    assert (informe.candidatos, informe.evaluados) == (10, 10)
    assert informe.muestreado is False


def test_f058_t19_la_regla_es_inmutable() -> None:
    regla = _regla(por_linea=True, techo=10)

    with pytest.raises(AttributeError):
        regla.techo = 20  # type: ignore[misc]


def test_f058_t19_el_anuncio_sin_suelo_dice_suelo_cero() -> None:
    linea = mutacion.anuncio_de_regla(_regla(por_linea=True, fraccion=0.5, techo=40), 7,
                                      "critico")

    assert "50 % de los candidatos, suelo 0, techo 40" in linea
