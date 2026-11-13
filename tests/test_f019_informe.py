# tests/test_f019_informe.py
"""F-019 · El informe de una campaña con selección de tests, y su estado.

R24–R27: el PODADO separado del MEDIDO, el modo de la campaña y sus números,
la media de la suite entera para RM2 y el porqué de la asimetría. R28: el
estado incremental guarda el podado como superviviente y lee el de la 1.9.0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.alcance import Alcance
from harness.mutacion import (
    FILAS_DE_RELOJ,
    SIN_EJECUTAR,
    SUPERVIVIENTE,
    VERSION_ESTADO,
    InformeMutacion,
    Mutante,
    clave_de_orden,
    escribir_estado,
    escribir_informe,
    leer_estado,
    plan_incremental,
)


def _mutante(linea: int, operador: str = "aritmetico") -> Mutante:
    return Mutante(
        fichero="pkg/mod.py", linea=linea, col=11, operador=operador,
        original=f"return x + {linea}", mutado=f"return x - {linea}",
    )


PODADO = _mutante(11)
MEDIDO_1 = _mutante(2)
MEDIDO_2 = _mutante(7)
MUERTO_1 = _mutante(3)


def _informe(seleccion: str | None = "activa", **extra: object) -> InformeMutacion:
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"),
                      lineas={"pkg/mod.py": {2, 3, 7, 11}})
    informe = InformeMutacion(
        feature="F-019", alcance=alcance, generados=4, muertos=1,
        supervivientes=[MEDIDO_1, MEDIDO_2, PODADO],
        mutantes_evaluados=[MEDIDO_1, MUERTO_1, MEDIDO_2, PODADO],
        segundos=30.0, sha_head="abc123", workers=2,
        segundos_linea_base={"wk_0/arnes-base": 10.0, "wk_1/arnes-base": 12.0},
        timeout_efectivo=24, timeout_suelo=10,
        codigos={clave_de_orden(MEDIDO_1): "0", clave_de_orden(MEDIDO_2): "0",
                 clave_de_orden(PODADO): SIN_EJECUTAR},
    )
    if seleccion is not None:
        informe.seleccion = seleccion
    if seleccion in ("activa", "degradada"):
        informe.podados = [PODADO]
        informe.sha_mapa = "abc123"
        informe.segundos_mapa = {"arnes-base": 15.25}
        informe.tests_en_suite = {"arnes-base": 612}
        informe.tamanos_subconjunto = [2, 4, 3]
        informe.revalidados = 2
        informe.muertos_al_revalidar = 1
        informe.subconjuntos_descartados = 1
        informe.segundos_suite_entera = 22.0
        informe.juzgados_suite_entera = 2
    for clave, valor in extra.items():
        setattr(informe, clave, valor)
    return informe


def _texto(informe: InformeMutacion, tmp_path: Path, nombre: str = "m.md") -> str:
    ruta = tmp_path / nombre
    escribir_informe(informe, ruta)
    return ruta.read_text(encoding="utf-8")


# --- R24 ---------------------------------------------------------------------


def test_f019_r24_totales_separan_podados_de_medidos(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    assert "| Supervivientes | 3 (1 podados sin ejecutar, 2 medidos) |" in texto


def test_f019_r24_cada_superviviente_dice_si_es_podado_o_medido(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    bloques = texto.split("### ")
    del_11 = next(b for b in bloques if b.startswith("3. `pkg/mod.py:11`"))
    del_2 = next(b for b in bloques if b.startswith("1. `pkg/mod.py:2`"))
    assert "- Juicio: PODADO" in del_11
    assert "- Juicio: MEDIDO" in del_2


# --- R25 ---------------------------------------------------------------------


def test_f019_r25_declara_modo_mapa_y_sus_numeros(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    assert "| Selección de tests | activa" in texto
    assert "| SHA del mapa | `abc123` |" in texto
    assert "| Medición del mapa (s) | `arnes-base`: 15.2 |" in texto
    assert "| Tests en la suite | `arnes-base`: 612 |" in texto
    assert "| Tamaño medio del subconjunto | 3.0 tests (3 mutantes) |" in texto
    assert "| Revalidados con la suite entera | 2 (1 murieron al revalidar) |" in texto
    assert "| Subconjuntos descartados | 1 |" in texto
    assert "| Podados (sin ejecutar) | 1 |" in texto


def test_f019_r25_el_ahorro_de_la_poda_es_un_calculo_derivado(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    assert (
        "| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | 12.0 |"
        in texto
    ), "1 podado × la peor línea base medida (12 s)"


def test_f019_r25_degradada_dice_el_motivo_por_ejecutor(tmp_path: Path) -> None:
    informe = _informe("degradada", motivos_degradado={"servicios/a": "sin coverage"})

    texto = _texto(informe, tmp_path)

    assert "| Selección de tests | degradada — `servicios/a`: sin coverage |" in texto


def test_f019_r25_desactivada_dice_n_d_y_nunca_un_cero(tmp_path: Path) -> None:
    texto = _texto(_informe("desactivada", supervivientes=[MEDIDO_1, MEDIDO_2]), tmp_path)

    assert "| Selección de tests | desactivada (por defecto)" in texto
    assert "| Podados (sin ejecutar) | n/d |" in texto
    assert "| Revalidados con la suite entera | n/d |" in texto
    assert "| SHA del mapa | n/d |" in texto
    assert "| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | n/d |" in texto
    assert "seleccion" not in texto.splitlines()[3], "apagada es el defecto: no se escribe"


def test_f019_r25_sin_mapa_medido_tampoco_hay_ceros(tmp_path: Path) -> None:
    informe = _informe("degradada", podados=[], tests_en_suite={}, segundos_mapa={},
                       sha_mapa=None, tamanos_subconjunto=[], revalidados=0,
                       subconjuntos_descartados=0,
                       motivos_degradado={"arnes-base": "sin coverage"},
                       supervivientes=[MEDIDO_1, MEDIDO_2])

    texto = _texto(informe, tmp_path)

    assert "| Podados (sin ejecutar) | n/d |" in texto
    assert "| Tamaño medio del subconjunto | n/d |" in texto
    assert "| Supervivientes | 2 (todos medidos: sin mapa no se poda) |" in texto


# --- R26 ---------------------------------------------------------------------


def test_f019_r26_media_por_mutante_juzgado_con_la_suite_entera(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    assert "| Media por mutante juzgado con la suite entera (s) | 11.0 (2 mutantes) |" in texto


def test_f019_r26_las_filas_de_reloj_nuevas_no_se_comparan(tmp_path: Path) -> None:
    for prefijo in (
        "| Medición del mapa (s)",
        "| Tiempo ahorrado por la poda",
        "| Media por mutante juzgado con la suite entera (s)",
        "| Subconjuntos descartados",
    ):
        assert prefijo in FILAS_DE_RELOJ


# --- R27 ---------------------------------------------------------------------


def test_f019_r27_el_informe_explica_la_asimetria_y_el_timeout(tmp_path: Path) -> None:
    texto = _texto(_informe(), tmp_path)

    seccion = texto.split("## Cómo se juzgó", 1)[1].split("\n## ", 1)[0]
    assert "no se revalida" in seccion and "SIN mutar" in seccion
    assert "sí se revalida" in seccion and "suite entera" in seccion
    assert "línea base" in seccion and "timeout" in seccion.lower()
    assert "PODADO" in seccion and "justific" in seccion


# --- Compatibilidad: sin selección declarada, el informe de la 1.9.0 ----------


def test_f019_sin_seleccion_declarada_el_informe_es_el_de_siempre(tmp_path: Path) -> None:
    texto = _texto(_informe(None), tmp_path)

    assert "| Supervivientes | 3 |" in texto
    for ausente in ("Selección de tests", "Cómo se juzgó", "- Juicio:", "SHA del mapa",
                    "Media por mutante juzgado con la suite entera"):
        assert ausente not in texto


def test_f019_r24_el_analisis_de_un_podado_se_conserva_al_repetir(tmp_path: Path) -> None:
    ruta = tmp_path / "m.md"
    escribir_informe(_informe(), ruta)
    texto = ruta.read_text(encoding="utf-8")
    pendiente = "#### Análisis (PENDIENTE del implementer)"
    partes = texto.split(pendiente)
    assert len(partes) == 4
    escrito = partes[0] + pendiente + partes[1] + pendiente + partes[2] + (
        "#### Análisis\n\n> Equivalente: la línea 11 solo se ejecuta en producción."
    ) + partes[3].split("\n", 3)[-1]
    ruta.write_text(escrito, encoding="utf-8")

    escribir_informe(_informe(), ruta)

    assert "la línea 11 solo se ejecuta en producción" in ruta.read_text(encoding="utf-8")


# --- R28: el estado incremental ----------------------------------------------


def test_f019_r28_el_podado_se_guarda_como_superviviente_sin_subir_version(
    tmp_path: Path,
) -> None:
    ruta = tmp_path / "m.json"

    assert escribir_estado(_informe(), ruta)

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["version"] == VERSION_ESTADO == 1
    veredictos = {(e["linea"]): e["veredicto"] for e in datos["evaluados"]}
    assert veredictos[11] == SUPERVIVIENTE
    assert set(datos) == {"version", "criterio", "fiable", "feature", "sha", "nivel",
                          "regla", "semilla", "generados", "candidatos", "evaluados"}, (
        "el formato del estado no cambia"
    )


ESTADO_1_9_0 = {
    "version": 1, "criterio": "codigo_1", "fiable": True, "feature": "F-019",
    "sha": "abc123", "nivel": "critico", "regla": None, "semilla": 7,
    "generados": 2, "candidatos": None,
    "evaluados": [
        {"fichero": "pkg/mod.py", "linea": 2, "col": 11, "operador": "aritmetico",
         "original": "return x + 2", "mutado": "return x - 2", "veredicto": "superviviente"},
        {"fichero": "pkg/mod.py", "linea": 3, "col": 11, "operador": "aritmetico",
         "original": "return x + 3", "mutado": "return x - 3", "veredicto": "muerto"},
    ],
}


def test_f019_r28_un_estado_de_la_1_9_0_se_sigue_leyendo(tmp_path: Path) -> None:
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps(ESTADO_1_9_0), encoding="utf-8")

    estado = leer_estado(ruta)
    plan = plan_incremental(estado, None, 7, "critico", [MEDIDO_1, MUERTO_1],
                            control=(0.0, 0))

    assert not isinstance(plan, str), plan
    assert plan.reevaluar == [MEDIDO_1]
    assert plan.reutilizados == [MUERTO_1]


@pytest.mark.parametrize("seleccion", ["activa", "desactivada", None])
def test_f019_r28_estado_identico_con_y_sin_seleccion(tmp_path: Path, seleccion) -> None:
    """La misma campaña con y sin poda deja el mismo estado: mismos veredictos."""
    con = tmp_path / "con.json"
    sin = tmp_path / f"sin_{seleccion}.json"
    escribir_estado(_informe(), con)
    escribir_estado(_informe(seleccion), sin)

    assert json.loads(con.read_text(encoding="utf-8")) == json.loads(
        sin.read_text(encoding="utf-8")
    )


# --- T13 · R26: RM2 en el CHECKPOINTS.md del payload ----------------------------

CHECKPOINTS = Path(__file__).resolve().parents[1] / "CHECKPOINTS.md"


def test_f019_r26_rm2_usa_la_media_de_la_suite_entera_con_seleccion_activa() -> None:
    texto = CHECKPOINTS.read_text(encoding="utf-8")
    rm2 = texto.split("**RM2 ·", 1)[1].split("**RM5 ·", 1)[0]

    assert "Selección de tests" in rm2
    assert "Media por mutante juzgado con la suite entera (s)" in rm2


def test_f019_r26_el_podado_es_superviviente_y_exige_justificacion() -> None:
    texto = CHECKPOINTS.read_text(encoding="utf-8")
    bloque = texto.split("## C4 bis", 1)[1].split("## C4 ter", 1)[0]

    assert "PODADO" in bloque
    podado = next(parrafo for parrafo in bloque.split("- [ ]") if "PODADO" in parrafo)
    assert "superviviente" in podado and "justificación" in podado
