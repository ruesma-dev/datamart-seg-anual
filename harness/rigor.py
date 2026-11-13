# harness/rigor.py
"""Niveles de rigor del arnés: qué se le exige a cada feature.

No todas las features merecen la misma vigilancia. Una que solo toca
documentación no puede requerir mutación; una que toca infraestructura
compartida en producción debe exigir más que la media. El nivel se declara en
el campo `rigor` de cada entrada de `harness/features.json` y lo que exige
cada nivel vive en `harness/rigor.json`.

Regla dura: si una feature no declara nivel, se le aplica el
`nivel_por_defecto` de `harness/rigor.json`. Ese nivel exige evidencia real
(fase RED y cobertura, con la mutación como informativa), así que omitir el
campo no es la vía fácil para saltarse las puertas; lo que no hace es arrastrar
el modo más caro —cero supervivientes tolerados— a features que no lo
necesitan. `critico` se declara: no se hereda por descuido.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from harness.estados import feature_activa

#: Puertas que un nivel puede exigir o no.
PUERTAS: tuple[str, ...] = ("fase_red", "cobertura", "mutacion")

#: Puertas que un nivel PUEDE declarar (F-059). Ausentes, no se exigen: meterlas
#: en `PUERTAS` rompería cada `rigor.json` instalado, que no las declara.
PUERTAS_OPCIONALES: tuple[str, ...] = ("e2e",)

RUTA_RIGOR = Path("harness/rigor.json")
RUTA_FEATURES = Path("harness/features.json")


RUTA_RIGOR_LOCAL = Path("harness/rigor.local.json")


class CapaLocalInvalida(ValueError):
    """La capa local de rigor (o su fusión con `rigor.json`) no vale.

    Subclase de `ValueError` para que quien ya trata la configuración rota la
    trate igual; quien necesita distinguirla (la mutación, que ante un
    `ValueError` degrada a los valores por defecto) la captura antes.
    """


@dataclass(frozen=True)
class CapasRigor:
    """Resultado de cargar `rigor.json` con su capa local, si la hay."""

    rigor: dict
    ruta_local: Path | None
    claves_locales: tuple[str, ...]


def cargar_rigor(ruta: Path | str = RUTA_RIGOR) -> dict:
    """Carga y valida la configuración de niveles, con su capa local fusionada.

    Cualquier incoherencia es un `ValueError` con mensaje explícito: es
    preferible parar el arnés a trabajar con una configuración que nadie
    entiende. Los errores de la capa local son `CapaLocalInvalida`.
    """
    return cargar_capas(ruta).rigor


def cargar_capas(ruta: Path | str = RUTA_RIGOR) -> CapasRigor:
    """`rigor.json` validado y, si existe a su lado, `rigor.local.json` encima.

    Orden: (1) la base sola, con el error de siempre; (2) la capa contra la
    lista blanca; (3) la fusión, con la validación de siempre etiquetada como
    fusión. Sin capa, devuelve el mismo objeto que hoy: ni copia ni re-valida.
    """
    ruta = Path(ruta)
    datos = _leer_json(ruta)
    _validar_configuracion(datos, ruta.as_posix())

    ruta_local = ruta.with_name(RUTA_RIGOR_LOCAL.name)
    if not ruta_local.is_file():
        return CapasRigor(rigor=datos, ruta_local=None, claves_locales=())

    local = _leer_capa_local(ruta_local)
    fusion = fusionar(datos, local)
    try:
        _validar_configuracion(
            fusion, f"fusión {ruta.as_posix()} + {ruta_local.as_posix()}"
        )
    except ValueError as error:
        raise CapaLocalInvalida(str(error)) from error
    return CapasRigor(
        rigor=fusion, ruta_local=ruta_local, claves_locales=claves_locales(local, datos)
    )


def claves_locales(local: dict, base: dict) -> tuple[str, ...]:
    """Rutas punteadas de las hojas que trae la capa, ordenadas y sin `$doc`.

    Un nivel que solo existe en la capa sale una vez, como `niveles.<n> (nivel
    nuevo)`: lo que importa es que hay un nivel más, no cada clave suya.
    """
    niveles_base = base.get("niveles", {})
    claves: list[str] = []
    for clave, valor in local.items():
        if clave == "niveles" and isinstance(valor, dict):
            for nombre, definicion in valor.items():
                if nombre not in niveles_base:
                    claves.append(f"niveles.{nombre} (nivel nuevo)")
                else:
                    claves.extend(_hojas(definicion, f"niveles.{nombre}"))
        else:
            claves.extend(_hojas(valor, clave))
    return tuple(sorted(claves))


def _hojas(valor: object, camino: str) -> list[str]:
    if camino.rsplit(".", 1)[-1] == "$doc":
        return []
    if not isinstance(valor, dict):
        return [camino]
    hojas: list[str] = []
    for clave, hijo in valor.items():
        hojas.extend(_hojas(hijo, f"{camino}.{clave}"))
    return hojas


def _leer_json(ruta: Path) -> object:
    if not ruta.is_file():
        raise ValueError(f"No existe la configuración de rigor: {ruta.as_posix()}")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"{ruta.as_posix()} no es JSON válido: {error}") from error


def _leer_capa_local(ruta: Path) -> dict:
    """La capa local, leída y validada contra la lista blanca (R8-R10)."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as error:
        raise CapaLocalInvalida(f"{ruta.as_posix()} no es JSON válido: {error}") from error
    validar_capa_local(datos, ruta)
    return datos


def fusionar(base: dict, local: dict) -> dict:
    """La capa local sobre la base: objeto sobre objeto se fusiona clave a clave,
    a cualquier profundidad; cualquier otra cosa sustituye entera. Pura: no muta
    ninguna entrada (copia profunda).
    """
    fusion = copy.deepcopy(base)
    for clave, valor in local.items():
        if isinstance(valor, dict) and isinstance(fusion.get(clave), dict):
            fusion[clave] = fusionar(fusion[clave], valor)
        else:
            fusion[clave] = copy.deepcopy(valor)
    return fusion


def _validar_configuracion(datos: object, etiqueta: str) -> None:
    """La validación de siempre, con `etiqueta` como origen en cada mensaje."""
    if not isinstance(datos, dict):
        raise ValueError(f"{etiqueta} debe contener un objeto JSON")

    niveles = datos.get("niveles")
    if not isinstance(niveles, dict) or not niveles:
        raise ValueError(f"{etiqueta}: falta el objeto 'niveles'")

    for nombre, definicion in niveles.items():
        if not isinstance(definicion, dict):
            raise ValueError(f"{etiqueta}: el nivel '{nombre}' no es un objeto")
        for puerta in PUERTAS:
            if not isinstance(definicion.get(puerta), bool):
                raise ValueError(
                    f"{etiqueta}: el nivel '{nombre}' debe declarar "
                    f"'{puerta}' como true o false"
                )
        for puerta in PUERTAS_OPCIONALES:
            if puerta in definicion and not isinstance(definicion[puerta], bool):
                raise ValueError(
                    f"{etiqueta}: el nivel '{nombre}' declara '{puerta}', "
                    f"que debe ser true o false (o no declararse), y es "
                    f"{definicion[puerta]!r}"
                )
        _validar_nivel(nombre, definicion, etiqueta)

    _validar_control_incremental(datos, etiqueta)
    _validar_no_versionados(datos, etiqueta)
    _validar_seleccion(datos, etiqueta)

    por_defecto = datos.get("nivel_por_defecto")
    if por_defecto not in niveles:
        raise ValueError(
            f"{etiqueta}: 'nivel_por_defecto' debe ser uno de "
            f"{sorted(niveles)}, y es {por_defecto!r}"
        )


def _validar_nivel(nombre: str, definicion: dict, etiqueta: str) -> None:
    """Valida las claves OPCIONALES de un nivel: `informativas` y `limites`.

    Un nivel sin ellas pasa sin más: un `rigor.json` anterior no cambia.
    """
    prefijo = f"{etiqueta}: el nivel '{nombre}'"
    if "informativas" in definicion:
        informativas = definicion["informativas"]
        admitidas = PUERTAS + PUERTAS_OPCIONALES
        if not isinstance(informativas, list) or any(
            puerta not in admitidas for puerta in informativas
        ):
            raise ValueError(
                f"{prefijo}: 'informativas' debe ser una lista de {list(admitidas)}, "
                f"y es {informativas!r}"
            )
        for puerta in informativas:
            if definicion.get(puerta, False):
                raise ValueError(
                    f"{prefijo}: 'informativas' nombra '{puerta}', que el nivel "
                    "exige: una puerta se exige o se informa, no las dos cosas"
                )

    if "limites" in definicion:
        limites = definicion["limites"]
        if not isinstance(limites, dict):
            raise ValueError(f"{prefijo}: 'limites' debe ser un objeto, y es {limites!r}")
        for clave in ("ficheros", "lineas"):
            valor = limites.get(clave)
            if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
                raise ValueError(
                    f"{prefijo}: 'limites.{clave}' ('{clave}') debe ser un entero "
                    f"positivo, y es {valor!r}"
                )
        no_cuentan = limites.get("no_cuentan", [])
        if not isinstance(no_cuentan, list) or any(
            not isinstance(patron, str) for patron in no_cuentan
        ):
            raise ValueError(
                f"{prefijo}: 'limites.no_cuentan' ('no_cuentan') debe ser una lista "
                f"de textos, y es {no_cuentan!r}"
            )

    _validar_muestreo(prefijo, definicion)


def _es_fraccion(valor: object) -> bool:
    """¿Un número en (0, 1]? Un booleano no cuenta como número."""
    return (
        not isinstance(valor, bool)
        and isinstance(valor, (int, float))
        and 0 < valor <= 1
    )


def _es_entero_positivo(valor: object) -> bool:
    return not isinstance(valor, bool) and isinstance(valor, int) and valor >= 1


def _es_porcentaje(valor: object) -> bool:
    return not isinstance(valor, bool) and isinstance(valor, int) and 0 <= valor <= 100


def _validar_muestreo(prefijo: str, definicion: dict) -> None:
    """Claves de F-058: estrictas, porque son nuevas y lo raro es un error.

    Al revés que `max_mutantes` —que ya existía y se lee con manga ancha para no
    romper a nadie—, una clave nueva mal escrita es un error de quien edita, y
    `--validar` lo pone en rojo en vez de convertir la campaña en otra.
    """
    if "un_mutante_por_linea" in definicion and not isinstance(
        definicion["un_mutante_por_linea"], bool
    ):
        raise ValueError(
            f"{prefijo}: 'un_mutante_por_linea' debe ser true o false, y es "
            f"{definicion['un_mutante_por_linea']!r}"
        )
    if "fraccion_mutantes" in definicion and not _es_fraccion(
        definicion["fraccion_mutantes"]
    ):
        raise ValueError(
            f"{prefijo}: 'fraccion_mutantes' debe ser un número en (0, 1] (un "
            f"booleano no vale), y es {definicion['fraccion_mutantes']!r}"
        )
    if "min_mutantes" in definicion:
        suelo = definicion["min_mutantes"]
        if not _es_entero_positivo(suelo):
            raise ValueError(
                f"{prefijo}: 'min_mutantes' debe ser un entero mayor o igual que 1 "
                f"(un booleano no vale), y es {suelo!r}"
            )
        techo = definicion.get("max_mutantes")
        if _es_entero_positivo(techo) and suelo > techo:
            raise ValueError(
                f"{prefijo}: 'min_mutantes' ({suelo}) no puede pasar de "
                f"'max_mutantes' ({techo})"
            )
    if "umbral_cobertura" in definicion and not _es_porcentaje(
        definicion["umbral_cobertura"]
    ):
        raise ValueError(
            f"{prefijo}: 'umbral_cobertura' debe ser un entero entre 0 y 100 (un "
            f"booleano no vale), y es {definicion['umbral_cobertura']!r}"
        )


#: Muestra de control de la repetición incremental si `rigor.json` no la fija:
#: `max(CONTROL_MINIMO, ceil(CONTROL_FRACCION × muertos))` muertos reevaluados.
CONTROL_FRACCION = 0.1
CONTROL_MINIMO = 5


def _validar_control_incremental(datos: dict, etiqueta: str) -> None:
    """`mutacion.incremental` es OPCIONAL; si está, sus claves tienen que valer."""
    mutacion = datos.get("mutacion")
    if not isinstance(mutacion, dict) or "incremental" not in mutacion:
        return
    bloque = mutacion["incremental"]
    prefijo = f"{etiqueta}: 'mutacion.incremental'"
    if not isinstance(bloque, dict):
        raise ValueError(f"{prefijo} debe ser un objeto, y es {bloque!r}")
    if "control_fraccion" in bloque and not _es_fraccion(bloque["control_fraccion"]):
        raise ValueError(
            f"{prefijo}.control_fraccion debe ser un número en (0, 1] (un booleano "
            f"no vale), y es {bloque['control_fraccion']!r}"
        )
    if "control_minimo" in bloque and not _es_entero_positivo(bloque["control_minimo"]):
        raise ValueError(
            f"{prefijo}.control_minimo debe ser un entero mayor o igual que 1 (un "
            f"booleano no vale), y es {bloque['control_minimo']!r}"
        )


_UNIDAD = re.compile(r"^[A-Za-z]:")


def _ruta_relativa_valida(valor: object) -> bool:
    """Texto, relativo a la raíz y sin salir de ella (`..`), en cualquier SO."""
    if not isinstance(valor, str) or not valor.strip():
        return False
    if valor.startswith(("/", "\\")) or _UNIDAD.match(valor):
        return False
    return ".." not in re.split(r"[\\/]", valor)


def _validar_no_versionados(datos: dict, etiqueta: str) -> None:
    """`mutacion.ficheros_no_versionados` (F-023) es OPCIONAL; si está, vale."""
    mutacion = datos.get("mutacion")
    if not isinstance(mutacion, dict) or "ficheros_no_versionados" not in mutacion:
        return
    valor = mutacion["ficheros_no_versionados"]
    prefijo = f"{etiqueta}: 'mutacion.ficheros_no_versionados'"
    if not isinstance(valor, list):
        raise ValueError(f"{prefijo} debe ser una lista de rutas, y es {valor!r}")
    for ruta in valor:
        if not _ruta_relativa_valida(ruta):
            raise ValueError(
                f"{prefijo}: cada ruta tiene que ser un texto relativo a la raíz, sin "
                f"'..' ni unidad ni barra inicial, y {ruta!r} no lo es"
            )


def _validar_seleccion(datos: dict, etiqueta: str) -> None:
    """`mutacion.seleccion_de_tests` (F-019) es OPCIONAL; si está, es booleana."""
    mutacion = datos.get("mutacion")
    if not isinstance(mutacion, dict) or "seleccion_de_tests" not in mutacion:
        return
    valor = mutacion["seleccion_de_tests"]
    if not isinstance(valor, bool):
        raise ValueError(
            f"{etiqueta}: 'mutacion.seleccion_de_tests' debe ser true o false (o no "
            f"declararse), y es {valor!r}"
        )


def seleccion_de_tests(rigor: dict) -> bool:
    """¿La campaña de mutación enciende la selección de tests sin pedirla? (F-019)

    Clave OPCIONAL y apagada por defecto (opción «b» del humano, 2026-11-10): en
    la suite del propio arnés la selección costó más de lo que ahorró. Ausente,
    o con un `rigor.json` de la 1.9.0, es `False`.
    """
    bloque = rigor.get("mutacion", {})
    return isinstance(bloque, dict) and bloque.get("seleccion_de_tests") is True


def ficheros_no_versionados(rigor: dict) -> list[str]:
    """Rutas no versionadas que la suite necesita en cada worktree (F-023).

    Clave OPCIONAL: ausente (o ilegible, que ya rechaza `cargar_rigor`) es la
    lista vacía, y entonces solo llega el `.env`, volcado como variables.
    """
    bloque = rigor.get("mutacion", {})
    valor = bloque.get("ficheros_no_versionados", []) if isinstance(bloque, dict) else []
    return list(valor) if isinstance(valor, list) else []


def control_incremental(rigor: dict) -> tuple[float, int]:
    """`(fracción, mínimo)` de la muestra de control de `--incremental`.

    Las claves son opcionales y las valida `cargar_rigor`; aquí, como en los
    demás lectores, lo que no vale se trata como ausencia.
    """
    bloque = rigor.get("mutacion", {})
    bloque = bloque.get("incremental", {}) if isinstance(bloque, dict) else {}
    bloque = bloque if isinstance(bloque, dict) else {}
    fraccion = bloque.get("control_fraccion")
    minimo = bloque.get("control_minimo")
    return (
        fraccion if _es_fraccion(fraccion) else CONTROL_FRACCION,
        minimo if _es_entero_positivo(minimo) else CONTROL_MINIMO,
    )


def niveles_validos(rigor: dict) -> list[str]:
    return sorted(rigor["niveles"])


def nivel_de_feature(feature: dict, rigor: dict) -> str:
    """Nivel declarado por la feature; si falta o no vale, el nivel por defecto."""
    declarado = feature.get("rigor")
    if isinstance(declarado, str) and declarado in rigor["niveles"]:
        return declarado
    return rigor["nivel_por_defecto"]


def exige(nivel: str, puerta: str, rigor: dict) -> bool:
    """¿El nivel exige esa puerta? Lo desconocido se considera exigido.

    Salvo una puerta OPCIONAL (`PUERTAS_OPCIONALES`) que el nivel no declara: esa
    no se exige, porque su ausencia es la configuración de siempre.
    """
    definicion = rigor["niveles"].get(nivel)
    if definicion is None:
        return True
    if puerta in PUERTAS_OPCIONALES and puerta not in definicion:
        return False
    valor = definicion.get(puerta)
    if not isinstance(valor, bool):
        return True
    return valor


def informativa(nivel: str, puerta: str, rigor: dict) -> bool:
    """¿La puerta se mide en ese nivel sin bloquear? Lo no declarado, no."""
    declaradas = rigor["niveles"].get(nivel, {}).get("informativas")
    return isinstance(declaradas, list) and puerta in declaradas


def limites_nivel(nivel: str, rigor: dict) -> dict | None:
    """Límites del carril de ese nivel; `None` si no los declara."""
    return rigor["niveles"].get(nivel, {}).get("limites")


def supervivientes_maximos(nivel: str, rigor: dict) -> int | None:
    """Supervivientes admitidos sin justificación; `None` = los juzga el reviewer."""
    definicion = rigor["niveles"].get(nivel, {})
    valor = definicion.get("supervivientes_maximos")
    return valor if isinstance(valor, int) else None


#: De dónde sale el umbral de cobertura aplicado (R22).
UMBRAL_DEL_NIVEL = "nivel"
UMBRAL_GLOBAL = "global"


def umbral_cobertura(rigor: dict, nivel: str | None = None) -> int:
    """Porcentaje mínimo de cobertura de las líneas cambiadas.

    Con `nivel`, el `umbral_cobertura` propio del nivel si lo declara (F-058);
    sin él, o si el nivel no lo declara, el global de siempre.
    """
    return umbral_cobertura_con_origen(rigor, nivel)[0]


def umbral_cobertura_con_origen(rigor: dict, nivel: str | None = None) -> tuple[int, str]:
    """`(umbral, origen)`: el del nivel (`"nivel"`) o el global (`"global"`)."""
    propio = rigor.get("niveles", {}).get(nivel, {}).get("umbral_cobertura")
    if _es_porcentaje(propio):
        return (propio, UMBRAL_DEL_NIVEL)
    return (_umbral_global(rigor), UMBRAL_GLOBAL)


def umbrales_por_nivel(rigor: dict) -> dict[str, int]:
    """Los niveles que pisan el umbral global, con el suyo."""
    return {
        nombre: definicion["umbral_cobertura"]
        for nombre, definicion in sorted(rigor.get("niveles", {}).items())
        if isinstance(definicion, dict) and _es_porcentaje(definicion.get("umbral_cobertura"))
    }


def _umbral_global(rigor: dict) -> int:
    valor = rigor.get("cobertura", {}).get("umbral_lineas_cambiadas")
    if not isinstance(valor, int):
        raise ValueError(
            "Falta 'cobertura.umbral_lineas_cambiadas' en la configuración de "
            "rigor: el umbral vive en el fichero, no en el código."
        )
    return valor


def timeout_mutacion(rigor: dict) -> int:
    """SUELO de segundos que se le conceden a la suite por cada mutante.

    Suelo y no techo: `harness.mutacion` deriva el timeout efectivo de la línea
    base que mide antes de juzgar a nadie, y nunca concede menos que este valor.

    «Falta la clave» y «el valor no vale» son dos averías distintas y llevan
    mensajes distintos: cuando las dos decían «falta», quien leía el aviso se
    ponía a buscar una clave que tenía delante. Y un booleano NO es un timeout,
    aunque `isinstance(True, int)` diga que sí: con `true` la campaña concedía
    **1 segundo** por mutante y salía entera en «timeout».
    """
    bloque = rigor.get("mutacion", {})
    valor = bloque.get("timeout_por_mutante_s") if isinstance(bloque, dict) else None
    if valor is None:
        raise ValueError(
            "Falta 'mutacion.timeout_por_mutante_s' en la configuración de rigor."
        )
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ValueError(
            f"'mutacion.timeout_por_mutante_s' no vale: {valor!r}. Tiene que ser "
            "un entero estrictamente positivo (un booleano NO cuenta como "
            "entero aquí: 'true' daría 1 segundo por mutante)."
        )
    return valor


def workers_mutacion(rigor: dict) -> int | None:
    """Evaluadores concurrentes de la campaña de mutación, si se declaran.

    Al revés que el timeout, esta clave es OPCIONAL y su ausencia no es un
    error: `None` significa «decídelo tú», y quien llama aplica su valor por
    núcleos de la máquina. Cablear aquí un número lo haría viajar de máquina en
    máquina, que es justo lo que no queremos. Un valor absurdo (0, negativo, un
    texto) se trata como ausencia: mejor el default que una campaña rara.
    """
    valor = rigor.get("mutacion", {}).get("workers")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        return None
    return valor


def max_mutantes_nivel(nivel: str, rigor: dict) -> int | None:
    """Mutantes que se evalúan como mucho en ese nivel; `None` = sin tope.

    Clave OPCIONAL, como `workers_mutacion`: ausencia, `null`, un booleano o un
    entero absurdo (cero o negativo) se tratan como «sin tope». Un `rigor.json`
    anterior a esta clave sigue funcionando y mide la campaña entera, que es lo
    que hacía.
    """
    valor = rigor.get("niveles", {}).get(nivel, {}).get("max_mutantes")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        return None
    return valor


def semilla_nivel(nivel: str, rigor: dict) -> int | None:
    """Semilla del muestreo de ese nivel; `None` = la que decida quien llama.

    Fijarla en el fichero es lo que hace REPRODUCIBLE una campaña muestreada:
    dos reviewers que remidan la misma feature obtienen los mismos mutantes. A
    diferencia del tope, aquí el `0` es una semilla legítima.
    """
    valor = rigor.get("niveles", {}).get(nivel, {}).get("semilla")
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


#: Origen de una regla de muestreo: la declara el nivel o la fija la orden.
ORIGEN_NIVEL = "nivel"
ORIGEN_ORDEN = "orden"


@dataclass(frozen=True)
class ReglaMuestreo:
    """Cuántos mutantes se evalúan y cómo se eligen (F-058).

    `por_linea`: antes de sortear se deja UN mutante por (fichero, línea).
    `fraccion`: tope proporcional a los candidatos, `None` = tope fijo `techo`.
    `suelo` y `techo` acotan la fracción; `techo` `None` = sin techo.
    """

    por_linea: bool
    fraccion: float | None
    suelo: int | None
    techo: int | None
    origen: str

    def tope(self, candidatos: int) -> int | None:
        """`min(techo, max(suelo, ceil(fraccion × C)))`; sin fracción, el techo.

        El producto se hace con `Fraction`: en coma flotante 0,6 × 5 da
        3,0000000000000004 y `ceil` lo convertiría en 4.
        """
        if self.fraccion is None:
            return self.techo
        limite = math.ceil(Fraction(str(self.fraccion)) * candidatos)
        if self.suelo is not None:
            limite = max(self.suelo, limite)
        if self.techo is not None:
            limite = min(self.techo, limite)
        return limite

    def motivo(self, candidatos: int, nivel: str | None = None) -> str:
        """Por qué el tope es el que es, en palabras del informe (R10)."""
        if self.origen == ORIGEN_ORDEN:
            return "fijado a mano con `--max-mutantes`"
        if self.fraccion is None:
            return "tope fijo del nivel" + (f" `{nivel}`" if nivel else "")
        porcentaje = format(float(Fraction(str(self.fraccion)) * 100), "g")
        techo = "sin techo" if self.techo is None else self.techo
        return (
            f"{porcentaje} % de {candidatos} candidatos, acotado a "
            f"[{self.suelo or 0}, {techo}]"
        )

    def como_dict(self) -> dict:
        """Forma serializable, la que guarda el estado de una campaña."""
        return {
            "por_linea": self.por_linea,
            "fraccion": self.fraccion,
            "suelo": self.suelo,
            "techo": self.techo,
            "origen": self.origen,
        }


def regla_nivel(nivel: str, rigor: dict) -> ReglaMuestreo | None:
    """La regla de muestreo de un nivel; `None` = campaña entera, como hoy.

    Lee con la misma manga ancha que `max_mutantes_nivel`: este lector también
    se usa sobre configuraciones que nadie ha validado (las inyectadas en los
    tests), y un valor raro se trata como ausencia. La validación estricta de
    las claves nuevas vive en `cargar_rigor`.
    """
    definicion = rigor.get("niveles", {}).get(nivel, {})
    por_linea = definicion.get("un_mutante_por_linea") is True
    fraccion = definicion.get("fraccion_mutantes")
    fraccion = fraccion if _es_fraccion(fraccion) else None
    techo = max_mutantes_nivel(nivel, rigor)
    if not por_linea and fraccion is None and techo is None:
        return None
    suelo = definicion.get("min_mutantes")
    suelo = suelo if fraccion is not None and _es_entero_positivo(suelo) else None
    return ReglaMuestreo(
        por_linea=por_linea, fraccion=fraccion, suelo=suelo, techo=techo,
        origen=ORIGEN_NIVEL,
    )


#: Ficheros de papeleo que tienen tope de líneas, con su clave en `rigor.json`.
CLAVES_TAMANO: tuple[str, ...] = ("requirements", "design", "impl", "review")


def _topes_de(bloque: object) -> dict[str, int]:
    """Los topes legibles de un bloque `tamano`; el resto se descarta."""
    if not isinstance(bloque, dict):
        return {}
    topes: dict[str, int] = {}
    for clave in CLAVES_TAMANO:
        valor = bloque.get(clave)
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
            continue
        topes[clave] = valor
    return topes


def topes_tamano(rigor: dict, nivel: str | None = None) -> dict[str, int]:
    """Topes de líneas del papeleo de una feature, o `{}` si no se declaran.

    Bloque OPCIONAL: sin él, la puerta de tamaño se declara N/A con su motivo
    en vez de romper el arnés de un proyecto con configuración anterior. Los
    valores que no son un entero positivo se descartan uno a uno —incluido el
    `$doc` del propio bloque—: un tope de cero prohibiría escribir.

    Con `nivel`, su bloque `tamano` (también opcional) pisa los globales clave a
    clave.
    """
    definicion = rigor.get("niveles", {}).get(nivel, {})
    return {**_topes_de(rigor.get("tamano")), **_topes_de(definicion.get("tamano"))}


# --- Lista blanca de la capa local (F-063) ------------------------------------

#: Hoja del esquema: `(prueba, lo que se esperaba)`. El texto va al mensaje.
_Hoja = tuple  # (Callable[[object], bool], str)

_BOOLEANO: _Hoja = (lambda valor: isinstance(valor, bool), "true o false")
_TEXTO: _Hoja = (lambda valor: isinstance(valor, str), "un texto")
_PORCENTAJE: _Hoja = (_es_porcentaje, "un entero entre 0 y 100 (un booleano no vale)")
_POSITIVO: _Hoja = (_es_entero_positivo, "un entero mayor o igual que 1 (un booleano no vale)")
_FRACCION: _Hoja = (_es_fraccion, "un número en (0, 1] (un booleano no vale)")
_POSITIVO_O_NULL: _Hoja = (
    lambda valor: valor is None or _es_entero_positivo(valor),
    "un entero mayor o igual que 1 o null (un booleano no vale)",
)
_NO_NEGATIVO_O_NULL: _Hoja = (
    lambda valor: valor is None
    or (not isinstance(valor, bool) and isinstance(valor, int) and valor >= 0),
    "un entero mayor o igual que 0 o null (un booleano no vale)",
)
_ENTERO_O_NULL: _Hoja = (
    lambda valor: valor is None or (not isinstance(valor, bool) and isinstance(valor, int)),
    "un entero o null (un booleano no vale)",
)
_PUERTAS_ADMITIDAS = PUERTAS + PUERTAS_OPCIONALES
_LISTA_DE_PUERTAS: _Hoja = (
    lambda valor: isinstance(valor, list)
    and all(isinstance(puerta, str) and puerta in _PUERTAS_ADMITIDAS for puerta in valor),
    f"una lista de {list(_PUERTAS_ADMITIDAS)}",
)
_LISTA_DE_TEXTOS: _Hoja = (
    lambda valor: isinstance(valor, list) and all(isinstance(x, str) for x in valor),
    "una lista de textos",
)

#: Qué claves admite `harness/rigor.local.json` y qué valores. Un objeto anidado
#: es un objeto del fichero; una tupla, una hoja. `"*"` = cualquier nombre de
#: nivel. `$doc` (texto) se admite en todo objeto salvo en el mapa de niveles,
#: donde cada clave es un nivel. Más estricta que la lectura de `rigor.json`: la
#: capa es nueva y en ella lo raro es una errata de quien edita (R9, R10).
ESQUEMA_LOCAL: dict = {
    "nivel_por_defecto": _TEXTO,
    "cobertura": {"umbral_lineas_cambiadas": _PORCENTAJE},
    "mutacion": {
        "timeout_por_mutante_s": _POSITIVO,
        "workers": _POSITIVO,
        "incremental": {"control_fraccion": _FRACCION, "control_minimo": _POSITIVO},
        "ficheros_no_versionados": _LISTA_DE_TEXTOS,
        "seleccion_de_tests": _BOOLEANO,
    },
    "tamano": {clave: _POSITIVO for clave in CLAVES_TAMANO},
    "niveles": {
        "*": {
            **{puerta: _BOOLEANO for puerta in _PUERTAS_ADMITIDAS},
            "spec": _BOOLEANO,
            "un_mutante_por_linea": _BOOLEANO,
            "informativas": _LISTA_DE_PUERTAS,
            "supervivientes_maximos": _NO_NEGATIVO_O_NULL,
            "max_mutantes": _POSITIVO_O_NULL,
            "semilla": _ENTERO_O_NULL,
            "min_mutantes": _POSITIVO,
            "fraccion_mutantes": _FRACCION,
            "umbral_cobertura": _PORCENTAJE,
            "limites": {
                "ficheros": _POSITIVO,
                "lineas": _POSITIVO,
                "no_cuentan": _LISTA_DE_TEXTOS,
            },
            "tamano": {clave: _POSITIVO for clave in CLAVES_TAMANO},
        },
    },
}


def validar_capa_local(datos: object, ruta: Path) -> None:
    """Valida la capa local contra `ESQUEMA_LOCAL`; lanza `CapaLocalInvalida`.

    Cada mensaje nombra el fichero y la ruta punteada de la clave.
    """
    origen = Path(ruta).as_posix()
    if not isinstance(datos, dict):
        raise CapaLocalInvalida(f"{origen} debe contener un objeto JSON, y es {datos!r}")
    _validar_contra(datos, ESQUEMA_LOCAL, "", origen)


def _validar_contra(datos: dict, esquema: dict, prefijo: str, origen: str) -> None:
    for clave, valor in datos.items():
        camino = f"{prefijo}{clave}"
        if clave == "$doc" and "*" not in esquema:
            subesquema: object = _TEXTO
        else:
            subesquema = esquema.get(clave, esquema.get("*"))
        if subesquema is None:
            raise CapaLocalInvalida(
                f"{origen}: clave desconocida '{camino}' (¿una errata?); las "
                f"admitidas ahí son {sorted(esquema)}"
            )
        if isinstance(subesquema, dict):
            if not isinstance(valor, dict):
                raise CapaLocalInvalida(
                    f"{origen}: '{camino}' debe ser un objeto, y es {valor!r}"
                )
            _validar_contra(valor, subesquema, camino + ".", origen)
            continue
        prueba, esperado = subesquema
        if not prueba(valor):
            raise CapaLocalInvalida(
                f"{origen}: '{camino}' debe ser {esperado}, y es {valor!r}"
            )


# --- Inventario de features -------------------------------------------------


def cargar_features(ruta: Path | str = RUTA_FEATURES) -> list[dict]:
    ruta = Path(ruta)
    if not ruta.is_file():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    features = datos.get("features", [])
    return features if isinstance(features, list) else []


def validar_features(features: list[dict], rigor: dict) -> list[str]:
    """Devuelve los errores de los niveles declarados (lista vacía = todo bien).

    No declarar nivel NO es un error: se aplica el nivel por defecto. Declarar
    uno inexistente sí lo es: sería un rigor imaginario.
    """
    errores: list[str] = []
    for feature in features:
        if "rigor" not in feature or feature["rigor"] is None:
            continue
        declarado = feature["rigor"]
        if not isinstance(declarado, str) or declarado not in rigor["niveles"]:
            errores.append(
                f"{feature.get('id', '(sin id)')}: rigor {declarado!r} no válido; "
                f"usa uno de {niveles_validos(rigor)}"
            )
        elif feature.get("sdd") is True and rigor["niveles"][declarado].get("spec") is False:
            errores.append(
                f"{feature.get('id', '(sin id)')}: es sdd: true y el nivel "
                f"{declarado!r} no lleva spec (spec: false); pon sdd: false o "
                "sube el nivel"
            )
    return errores


def feature_de_rama(rama: str, features: list[dict]) -> dict | None:
    """Feature cuya rama declarada es `rama`; si no hay, la activa.

    «Activa» es cualquiera de `in_progress`, `in_review` o `human_review`
    (ver `harness/estados.py`): la feature sigue en curso mientras la revisa
    el reviewer o espera el OK del humano.
    """
    if rama:
        for feature in features:
            if feature.get("branch") == rama:
                return feature
    return feature_activa(features)


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """`python -m harness.rigor --validar`: 0 si todo cuadra, 1 si no."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.rigor",
        description="Valida la configuración de niveles de rigor del arnés.",
    )
    analizador.add_argument("--validar", action="store_true")
    analizador.add_argument("--config", default=str(RUTA_RIGOR))
    analizador.add_argument("--features", default=str(RUTA_FEATURES))
    opciones = analizador.parse_args(argv)

    try:
        capas = cargar_capas(opciones.config)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    rigor = capas.rigor
    errores = validar_features(cargar_features(opciones.features), rigor)
    if errores:
        for error in errores:
            print(error, file=sys.stderr)
        return 1

    propios = umbrales_por_nivel(rigor)
    pisan = (
        "; pisan el global: "
        + ", ".join(f"{nombre} {umbral}%" for nombre, umbral in propios.items())
        if propios
        else ""
    )
    print(
        f"    niveles: {', '.join(niveles_validos(rigor))}; por defecto "
        f"{rigor['nivel_por_defecto']}; umbral de cobertura "
        f"{umbral_cobertura(rigor)}%{pisan}"
    )
    if capas.ruta_local is not None:
        claves = ", ".join(capas.claves_locales) or "sin claves"
        print(f"    capa local ({capas.ruta_local.as_posix()}): {claves}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
