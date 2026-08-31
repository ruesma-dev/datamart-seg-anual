# etl_sigrid/domain/cobertura.py
"""
F-052 · El veredicto de cobertura: lo que entra en `stg`, ¿sale en `mart`?
**Dominio puro** (R13 a R17, R28).

Nadie hacía esa pregunta. `check-unicidad` mira claves duplicadas,
`check-cierres` mira la regla de F-042 y `check-diccionario` mira que el catálogo
case con las fichas. Por ese hueco la obra 0599 TANATORIO MAJADAHONDA llevaba
desde 2022 publicando **4.066.989,23 € de venta y 0,00 € de coste directo** sin
que nada chirriara: un `INNER JOIN` que descarta 183.530 filas no se queja.

## Dos hallazgos, y son cosas distintas

* **Obra invisible (R14)** — la obra tiene filas en `stg.plan_mensual` para un
  ámbito y **cero** en `mart.fact_seguimiento_mensual` para ese mismo ámbito. Es
  presencia, no conteo: en los ámbitos master (8, 11) el build elige la versión
  vigente, así que muchísimas filas de `stg` no llegan al fact **por diseño** y
  comparar cantidades sería mentir.
* **Filas huérfanas (R15)** — filas de `stg.plan_mensual` sin ficha de partida o
  de obra. Es lo que los cuatro `INNER JOIN` de `mart/02_build_fact.sql` borran
  hoy sin decir nada.

Una obra puede ser las dos cosas a la vez, y por eso las dos viajan en la misma
`FilaCobertura`.

## Las excepciones, y por qué son un trinquete

Hay descartes que hoy son legítimos: las 12 partidas en ciclo de `raw.obrparpar`,
las obras administrativas que `stg/03_obras.sql` excluye a propósito y las tres
que dependen de F-053. Se declaran en `config/cobertura_excepciones.yaml` con su
motivo y la feature que las cerrará, y **la lista sólo puede bajar**: mismo
criterio que `config/objetos_pendientes.yaml`. Una excepción sin porqué se
convierte en permanente a la primera.

## El marcador

`check-cobertura` **avisa y no bloquea** (DA-4): la nocturna termina en verde, y
eso significa que la alerta de fallo existente **no se dispara**. La única vía
por la que este guardián se hace oír es una línea de log con un literal fijo que
una regla de consulta programada busca —`infra/96_create_alert_cobertura.ps1`—.
Si el literal del código y el del `.ps1` divergen, la alerta vigila un texto que
ya nadie escribe y **nadie se entera**, que es exactamente el modo de fallo que
esta feature existe para eliminar. Por eso vive aquí, en un solo sitio, y lo
cruza `tests/test_f052_marcador.py`.

Capa **domain**: funciones puras, sin BBDD ni ficheros. Leer la base es
`infrastructure/postgres/cobertura_sql.py`; leer el YAML,
`infrastructure/cobertura_excepciones.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: El literal que dispara la alerta. **Estable y buscable**: no lleva la fecha
#: ni el nombre de nadie, y no se toca aunque cambie el texto que lo acompaña.
MARCADOR_KO = "[F052-COBERTURA-KO]"

#: Los dos hallazgos, y el comodín que cubre los dos.
TIPO_OBRA_INVISIBLE = "obra_invisible"
TIPO_FILAS_HUERFANAS = "filas_huerfanas"
TIPO_AMBAS = "ambas"

TIPOS = (TIPO_OBRA_INVISIBLE, TIPO_FILAS_HUERFANAS, TIPO_AMBAS)


@dataclass(frozen=True, slots=True)
class FilaCobertura:
    """Una combinación (obra × ámbito) con lo que se sabe de ella.

    `codigo_obra` y `nombre_obra` pueden venir de `stg.obras` o, cuando la obra
    **no tiene ficha allí**, de `raw`. Sin eso la denuncia diría «obra 2824201» y
    nadie sabría cuál es ni podría declararla como excepción.
    """

    obra_id: int
    codigo_obra: str
    nombre_obra: str
    ambito_id: int
    #: Filas de `stg.plan_mensual` de esa obra y ese ámbito. Cero significa que
    #: la consulta B no trajo la combinación, no que `stg` esté vacía.
    filas_stg: int
    #: Filas de `mart.fact_seguimiento_mensual` de la misma combinación.
    filas_mart: int
    #: Filas de `stg.plan_mensual` sin ficha de partida o de obra.
    huerfanas: int

    @property
    def es_obra_invisible(self) -> bool:
        """Entra en `stg` y no sale en `mart`. **Presencia, no conteo.**"""
        return self.filas_stg > 0 and self.filas_mart == 0

    @property
    def tiene_huerfanas(self) -> bool:
        return self.huerfanas > 0

    def como_texto(self) -> str:
        nombre = f" {self.nombre_obra}" if self.nombre_obra else ""
        codigo = self.codigo_obra or "sin codigo"
        return f"{codigo}{nombre} (obra {self.obra_id}) · ambito {self.ambito_id}"


@dataclass(frozen=True, slots=True)
class Excepcion:
    """Un descarte aceptado, con su motivo y quién lo cerrará.

    Identifica a la obra **o** por `codigo_obra` **o** por `patron_nombre`. Lo
    segundo existe porque las obras administrativas no tienen ficha en
    `stg.obras` —las excluye a propósito la lista negra de `stg/03_obras.sql`— y
    su código no siempre se puede resolver.
    """

    tipo: str
    motivo: str
    codigo_obra: str | None = None
    patron_nombre: str | None = None
    #: `None` = cualquier ámbito.
    ambito_id: int | None = None
    #: La feature que la cerrará, cuando la haya. `None` = no depende de ninguna.
    feature: str | None = None

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(
                f"tipo de excepcion desconocido: {self.tipo!r}. Los validos son "
                f"{', '.join(TIPOS)}"
            )
        if bool(self.codigo_obra) == bool(self.patron_nombre):
            raise ValueError(
                "una excepcion identifica a la obra por `codigo_obra` O por "
                "`patron_nombre`, y exactamente por uno de los dos: sin ninguno "
                "las cubriria todas, y con los dos no se sabe cual manda"
            )
        if not self.motivo.strip():
            raise ValueError(
                "una excepcion sin motivo se convierte en permanente a la "
                "primera: escribe por que se acepta y que la cerrara"
            )

    def cubre(self, fila: FilaCobertura, tipo: str) -> bool:
        if self.tipo not in (tipo, TIPO_AMBAS):
            return False
        if self.ambito_id is not None and self.ambito_id != fila.ambito_id:
            return False
        if self.codigo_obra is not None:
            return fila.codigo_obra.strip().upper() == self.codigo_obra.strip().upper()
        return (self.patron_nombre or "").strip().upper() in fila.nombre_obra.upper()


@dataclass(frozen=True, slots=True)
class Veredicto:
    """Las **dos listas completas**, y lo que hace falta para leerlas.

    `cubiertas` va aquí porque «0 hallazgos» sobre una lista de excepciones que
    lo tapa todo es indistinguible de «0 hallazgos» de verdad, y sólo uno de los
    dos prueba algo.
    """

    obras_invisibles: tuple[FilaCobertura, ...]
    filas_huerfanas: tuple[FilaCobertura, ...]
    cubiertas: tuple[FilaCobertura, ...]
    #: Cuántas combinaciones (obra × ámbito) se han mirado. Un veredicto verde
    #: sobre cero filas no es un verde: es que no se ha comprobado nada.
    filas_miradas: int

    @property
    def hay_hallazgos(self) -> bool:
        return bool(self.obras_invisibles or self.filas_huerfanas)

    @property
    def codigo(self) -> int:
        """Distinto de 0 si algo cae **fuera de lo declarado** (R16)."""
        return 1 if self.hay_hallazgos else 0

    @property
    def obras_invisibles_distintas(self) -> int:
        return len({f.obra_id for f in self.obras_invisibles})

    @property
    def total_huerfanas(self) -> int:
        return sum(f.huerfanas for f in self.filas_huerfanas)

    @property
    def marcador(self) -> str:
        """La línea que dispara la alerta, o cadena vacía si no hay nada (R28).

        **En verde no se emite.** Un marcador que aparece todas las noches
        entrena a todo el mundo a ignorarlo, y entonces la alerta ya no vale.
        """
        if not self.hay_hallazgos:
            return ""
        return (
            f"{MARCADOR_KO} obras_invisibles={self.obras_invisibles_distintas} "
            f"filas_huerfanas={self.total_huerfanas}"
        )


def veredicto(
    filas: Iterable[FilaCobertura], excepciones: Sequence[Excepcion]
) -> Veredicto:
    """Clasifica cada fila en hallazgo o descarte declarado.

    **Qué demuestra un verde y qué no.** Demuestra que hoy no hay ninguna
    combinación (obra × ámbito) que entre en `stg` y no salga en `mart` fuera de
    lo declarado. No demuestra que las cifras publicadas sean correctas: para eso
    están `check-cierres` y la comparación de huellas.
    """
    invisibles: list[FilaCobertura] = []
    huerfanas: list[FilaCobertura] = []
    cubiertas: list[FilaCobertura] = []
    miradas = 0

    for fila in filas:
        miradas += 1
        tapada = False

        if fila.es_obra_invisible:
            if any(e.cubre(fila, TIPO_OBRA_INVISIBLE) for e in excepciones):
                tapada = True
            else:
                invisibles.append(fila)

        if fila.tiene_huerfanas:
            if any(e.cubre(fila, TIPO_FILAS_HUERFANAS) for e in excepciones):
                tapada = True
            else:
                huerfanas.append(fila)

        if tapada:
            cubiertas.append(fila)

    return Veredicto(
        obras_invisibles=tuple(invisibles),
        filas_huerfanas=tuple(huerfanas),
        cubiertas=tuple(cubiertas),
        filas_miradas=miradas,
    )


def formatear(resultado: Veredicto) -> str:
    """El informe, con **las listas enteras**: un `LIMIT` aquí es una forma
    elegante de no mirar."""
    lineas = [
        f"Cobertura stg -> mart · {resultado.filas_miradas} combinacion(es) "
        f"(obra x ambito) miradas, {len(resultado.cubiertas)} cubierta(s) por "
        f"una excepcion declarada.",
        "",
        _bloque_invisibles(resultado),
        "",
        _bloque_huerfanas(resultado),
        "",
    ]

    if resultado.hay_hallazgos:
        lineas.append(resultado.marcador)
        lineas.append(
            "KO   hay cobertura sin declarar. Lanzado a mano esto sale con "
            "codigo 1; dentro de `run-all` se registra y la nocturna termina en "
            "verde (DA-4), asi que la unica via por la que esto se hace oir es "
            "la regla de alerta de infra/96_create_alert_cobertura.ps1."
        )
    else:
        lineas.append(
            "OK   todo lo que entra en stg sale en mart, salvo lo declarado en "
            "config/cobertura_excepciones.yaml. No prueba que las cifras sean "
            "correctas: prueba que no falta ninguna obra."
        )

    return "\n".join(lineas)


def _bloque_invisibles(resultado: Veredicto) -> str:
    if not resultado.obras_invisibles:
        return "Obras invisibles (filas en stg, cero en mart): ninguna."
    lineas = [
        f"Obras invisibles (filas en stg, cero en mart): "
        f"{len(resultado.obras_invisibles)} combinacion(es) en "
        f"{resultado.obras_invisibles_distintas} obra(s)."
    ]
    lineas += [
        f"  {f.como_texto()}: {f.filas_stg} fila(s) en stg y 0 en el fact"
        for f in resultado.obras_invisibles
    ]
    return "\n".join(lineas)


def _bloque_huerfanas(resultado: Veredicto) -> str:
    if not resultado.filas_huerfanas:
        return "Filas huerfanas (sin ficha de partida o de obra): ninguna."
    lineas = [
        f"Filas huerfanas (sin ficha de partida o de obra): "
        f"{resultado.total_huerfanas} fila(s) en "
        f"{len(resultado.filas_huerfanas)} combinacion(es)."
    ]
    lineas += [
        f"  {f.como_texto()}: {f.huerfanas} fila(s) que el build descarta"
        for f in resultado.filas_huerfanas
    ]
    return "\n".join(lineas)
