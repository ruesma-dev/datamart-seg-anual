# etl_sigrid/domain/perfil_carga.py
"""
Perfil de una carga del pipeline: dónde se va el tiempo, medido y no estimado.

Es el bloque A de F-011, y su razón de ser es una regla del propio encargo:
**medir antes de optimizar**. La feature nace de la sospecha de que el cuello
de botella está en la extracción, y la primera carga completa medida en Azure
(2026-08-19) la contradice: ingesta 33 min de 165 (20 %), `build_stg` 111
(67 %), `build_mart` 21 (13 %). Este módulo es lo que convierte esa aritmética
en un comando repetible en vez de una cuenta a mano en un cuaderno.

Tres preguntas, tres funciones puras:

  * `perfil_de_carga`   — ¿cuánto tardó cada paso y cada tabla? (R1)
  * `techo_de_mejora`   — ¿cuánto duraría la carga si un paso costase cero? (R2)
  * `tablas_que_acumulan` — ¿cuántas tablas se llevan el 80 % de la ingesta? (R3)

Sin psycopg, sin click y sin reloj: recibe filas y devuelve datos. Quien las
lee de `_meta.etl_runs` es `PostgresClient.fetch_perfil_carga`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: Prefijo con el que la ingesta nombra la fila de cada tabla en
#: `_meta.etl_runs` (`ingest_raw.obrparpre`). Es el mismo que destripa
#: `_meta.v_raw_state` en el DDL de F-024; si cambia allí, cambia aquí.
PREFIJO_TABLA = "ingest_raw."

#: Porcentaje del tiempo de ingesta sobre el que se responde «¿cuántas tablas
#: se lo llevan?». Es el 80 % de R3, y está aquí y no en el formateador porque
#: es parte del requisito.
PCT_ACUMULADO_OBJETIVO = 80.0

SEGUNDOS_POR_MINUTO = 60.0


@dataclass(frozen=True, slots=True)
class FilaPerfil:
    """Una fila de `_meta.etl_runs` vista como medición de perfil."""

    stage: str
    step: str
    segundos: float
    filas: int
    status: str

    @property
    def es_paso(self) -> bool:
        """¿Es un paso de pipeline y no un sub-paso?

        Mismo criterio que `_meta.v_frescura`: el `step` de un paso no lleva
        punto. Los sub-pasos (`ingest_raw.con`, `build_plan_mensual.tramo_01`)
        sí, y sumarlos con los pasos contaría el mismo tiempo dos veces.
        """
        return "." not in self.step

    @property
    def tabla(self) -> str | None:
        """Nombre de la tabla si esta fila es de la ingesta; `None` si no."""
        if not self.step.startswith(PREFIJO_TABLA):
            return None
        return self.step[len(PREFIJO_TABLA) :]

    @property
    def filas_por_segundo(self) -> float:
        """Ritmo de proceso. 0 si el paso no llegó a medir tiempo."""
        if self.segundos <= 0:
            return 0.0
        return self.filas / self.segundos


@dataclass(frozen=True, slots=True)
class PerfilCarga:
    """El desglose completo de una carga, ya separado en pasos y tablas."""

    batch_id: str | None
    pasos: tuple[FilaPerfil, ...]
    tablas: tuple[FilaPerfil, ...]
    total_segundos: float

    @property
    def segundos_de_ingesta(self) -> float:
        """Suma de las filas por tabla. Es el denominador de R3."""
        return sum(t.segundos for t in self.tablas)

    def pct_del_total(self, fila: FilaPerfil) -> float:
        """Peso de una fila sobre la duración total de la carga, en %."""
        if self.total_segundos <= 0:
            return 0.0
        return fila.segundos / self.total_segundos * 100.0


@dataclass(frozen=True, slots=True)
class TechoPaso:
    """Cuánto duraría la carga si este paso costase cero (R2)."""

    paso: str
    segundos: float
    total_si_cero_s: float
    ahorro_min: float
    ahorro_pct: float


def perfil_de_carga(
    filas: Iterable[FilaPerfil], batch_id: str | None = None
) -> PerfilCarga:
    """
    Reparte las filas medidas en pasos de pipeline y tablas de la ingesta.

    `batch_id` se recibe aparte y no se deduce de las filas: la identidad de la
    carga la elige quien consulta (`fetch_perfil_carga`), y una lista de
    mediciones puede venir perfectamente de una base anterior a F-024, sin
    `batch_id` ninguno.

    El total es la suma de los PASOS. Es la única suma que significa «lo que
    tardó la carga»: sumar también los sub-pasos contaría el tiempo de las 31
    tablas dos veces, una en su fila y otra dentro de `ingest_raw`.
    """
    todas = list(filas)
    pasos = tuple(f for f in todas if f.es_paso)
    tablas = tuple(
        sorted(
            (f for f in todas if f.tabla is not None),
            key=lambda f: (-f.segundos, f.step),
        )
    )
    return PerfilCarga(
        batch_id=batch_id,
        pasos=pasos,
        tablas=tablas,
        total_segundos=sum(p.segundos for p in pasos),
    )


def techo_de_mejora(perfil: PerfilCarga) -> tuple[TechoPaso, ...]:
    """
    Techo de mejora por paso, ordenado de mayor a menor ahorro (R2).

    «Techo» es literal: supone que el paso pasa a costar CERO, que es
    imposible. Sirve para descartar, no para prometer. Si el techo de un paso
    no llega al umbral de DA-7 (≥ 20 min o ≥ 40 % del total), optimizarlo no
    puede llegar tampoco, y esa es la decisión que la feature necesita tomar
    antes de escribir una línea del bloque B.
    """
    total = perfil.total_segundos
    techos = [
        TechoPaso(
            paso=p.step,
            segundos=p.segundos,
            total_si_cero_s=total - p.segundos,
            ahorro_min=p.segundos / SEGUNDOS_POR_MINUTO,
            ahorro_pct=(0.0 if total <= 0 else p.segundos / total * 100.0),
        )
        for p in perfil.pasos
    ]
    return tuple(sorted(techos, key=lambda t: (-t.segundos, t.paso)))


def tablas_que_acumulan(perfil: PerfilCarga, pct: float) -> tuple[str, ...]:
    """
    Las tablas más lentas que juntas alcanzan `pct` % del tiempo de ingesta.

    El corte es inclusivo: en cuanto lo acumulado llega al objetivo, para. Y
    `pct` es un porcentaje de 0 a 100, no una fracción: pasar 0,8 creyendo que
    es «el 80 %» devolvería una sola tabla y nadie lo notaría, así que se
    rechaza en vez de responder algo plausible y falso.
    """
    if not 0 < pct <= 100:
        raise ValueError(
            f"pct debe ser un porcentaje en (0, 100]; recibido {pct!r}. "
            f"Para el 80 % se pasa 80.0, no 0.8."
        )

    objetivo = perfil.segundos_de_ingesta * pct / 100.0
    if objetivo <= 0:
        return ()

    acumulado = 0.0
    elegidas: list[str] = []
    for t in perfil.tablas:
        elegidas.append(t.tabla or t.step)
        acumulado += t.segundos
        if acumulado >= objetivo:
            break
    return tuple(elegidas)


# ---------------------------------------------------------------------------
# Formato para la consola
# ---------------------------------------------------------------------------

_CAB_PASOS = (
    f"{'etapa':<12} {'paso':<24} {'duración_s':>12} {'min':>8} "
    f"{'filas':>12} {'filas/s':>12} {'%_total':>8}  estado"
)
_CAB_TABLAS = (
    f"{'tabla':<24} {'duración_s':>12} {'min':>8} {'filas':>12} "
    f"{'filas/s':>12} {'%_ingesta':>10} {'%_acum':>8}  estado"
)
_CAB_TECHO = (
    f"{'paso':<24} {'si_costase_0_min':>18} {'ahorro_min':>12} {'ahorro_%':>10}"
)


def format_perfil(perfil: PerfilCarga, pct: float = PCT_ACUMULADO_OBJETIVO) -> str:
    """
    Las tres respuestas de R1, R2 y R3 en un solo texto, sin colores.

    Función pura y sin reloj: dos llamadas con el mismo perfil dan el mismo
    texto, lo que permite fijar el formato en un test. El comando de la CLI se
    limita a imprimir lo que salga de aquí.
    """
    if not perfil.pasos and not perfil.tablas:
        return (
            "Sin mediciones de carga en _meta.etl_runs. ¿Se ha ejecutado ya "
            "`python main.py run-all`?"
        )

    lineas: list[str] = [
        f"Carga medida: {perfil.batch_id or 'sin identidad de ejecución'}",
        f"Duración total (suma de pasos): {perfil.total_segundos:,.1f} s "
        f"= {perfil.total_segundos / SEGUNDOS_POR_MINUTO:,.1f} min",
        "",
        "=== Pasos del pipeline (R1) ===",
        _CAB_PASOS,
        "-" * len(_CAB_PASOS),
    ]
    for p in perfil.pasos:
        lineas.append(
            f"{p.stage:<12} {p.step:<24} {p.segundos:>12.1f} "
            f"{p.segundos / SEGUNDOS_POR_MINUTO:>8.1f} {p.filas:>12,} "
            f"{p.filas_por_segundo:>12,.0f} {perfil.pct_del_total(p):>8.1f}  {p.status}"
        )

    lineas.extend(["", "=== Techo de mejora por paso (R2) ===", _CAB_TECHO])
    lineas.append("-" * len(_CAB_TECHO))
    for t in techo_de_mejora(perfil):
        lineas.append(
            f"{t.paso:<24} {t.total_si_cero_s / SEGUNDOS_POR_MINUTO:>18.1f} "
            f"{t.ahorro_min:>12.1f} {t.ahorro_pct:>10.1f}"
        )

    lineas.extend(_bloque_de_tablas(perfil, pct))
    return "\n".join(lineas)


def _bloque_de_tablas(perfil: PerfilCarga, pct: float) -> Sequence[str]:
    """Desglose por tabla de la ingesta, ordenado, con el corte de R3 al pie."""
    if not perfil.tablas:
        return [
            "",
            "=== Ingesta por tabla (R1, R3) ===",
            "Sin filas `ingest_raw.<tabla>` en esta carga: no se puede repartir "
            "el tiempo de ingesta por tabla.",
        ]

    total_ingesta = perfil.segundos_de_ingesta
    lineas = ["", "=== Ingesta por tabla (R1, R3) ===", _CAB_TABLAS]
    lineas.append("-" * len(_CAB_TABLAS))

    acumulado = 0.0
    for t in perfil.tablas:
        acumulado += t.segundos
        pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0
        pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta * 100.0
        lineas.append(
            f"{t.tabla or t.step:<24} {t.segundos:>12.1f} "
            f"{t.segundos / SEGUNDOS_POR_MINUTO:>8.1f} {t.filas:>12,} "
            f"{t.filas_por_segundo:>12,.0f} {pct_ingesta:>10.1f} {pct_acum:>8.1f}"
            f"  {t.status}"
        )

    lineas.append("-" * len(_CAB_TABLAS))
    lineas.append(
        f"{'TOTAL INGESTA':<24} {total_ingesta:>12.1f} "
        f"{total_ingesta / SEGUNDOS_POR_MINUTO:>8.1f}"
    )

    cabeza = tablas_que_acumulan(perfil, pct)
    plural = "tabla" if len(cabeza) == 1 else "tablas"
    lineas.append("")
    lineas.append(
        f"R3: {len(cabeza)} {plural} de {len(perfil.tablas)} acumulan el "
        f"{pct:.0f} % del tiempo de ingesta: {', '.join(cabeza) or '-'}"
    )
    return lineas
