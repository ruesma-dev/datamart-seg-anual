# tests/test_f079_stg_consultable.py
"""
F-079 · Todo lo expuesto es para consulta: `stg` deja de estar desaconsejado.

El humano, el 2026-09-09: «parece que en el diccionario se indica que no se
recomienda para consulta `stg`, eso borralo, todo lo expuesto es para consulta».

El diccionario tenía **27 objetos fuera de `raw`** con `consumo_recomendado:
false`, y los tres grupos no son lo mismo:

* **GRUPO A · los 7 de `stg` que no son funciones.** Sus `motivo_no_consumo`
  decían «capa intermedia» o «para consultar partidas está
  `mart.v_pbi_dim_partida`»: **preferencias de enrutado**. El MCP tiene `stg`
  entre sus esquemas autorizados, así que desaconsejarlos solo conseguía que el
  agente no mirase donde sí hay dato —el ámbito de certificación, por ejemplo,
  vive en `stg.presupuesto` y en ningún sitio aguas abajo—.
* **GRUPO B · las 11 funciones SQL.** Una función no se consulta: se llama desde
  el SQL del build. «Todo lo expuesto es para consulta» no las alcanza.
* **GRUPO C · los 9 objetos rotos, vacíos o de instrumentación.** Ahí el aviso
  **es un hecho, no una preferencia**: recomendarlos haría que el agente los
  consultase y fallara. **Hoy son 8**: F-078 materializó
  `mart.v_pbi_cp_tipologia` el 2026-09-15 y con ello dejó de ser un hecho que
  no se pudiera consultar. Un aviso que era cierto y deja de serlo se retira,
  porque apartar al agente de una vista que ya funciona hace el mismo daño que
  mandarle a una que no.

**El riesgo de esta feature no es el booleano: es lo que se borra con él.**
Dentro de esos `motivo_no_consumo` había **advertencias de corrección**, y si
desaparecen el agente da cifras infladas. Este fichero es el que impide que se
pierdan: comprueba que cada una sigue llegando al agente **y desde dónde**.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from tests._texto import contiene, normalizado

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: GRUPO A · los 7 de `stg` que no son funciones. Es lo que el humano manda
#: quitar, y la lista se escribe entera a propósito: si mañana nace un objeto
#: nuevo en `stg`, el test de abajo que barre el esquema lo caza.
GRUPO_A = (
    "stg.plan_mensual",
    "stg.presupuesto",
    "stg.partidas",
    "stg.obras",
    "stg.fases",
    "stg.version_master_vigente",
    "stg.ambitos",
)

#: GRUPO B · las once funciones SQL. **Inventariadas, no tocadas.**
GRUPO_B_FUNCIONES = (
    "cierre.fn_parse_mes_fase",
    "cierre.fn_mes_de_fase",
    "cierre.fn_mes_de_version_master",
    "compras.fn_tipo_documento",
    "compras.fn_serie",
    "compras.fn_sigrid_date",
    # F-084 (2026-09-16): la traduccion del estado por la pareja (tipo,
    # estado), factorizada fuera de `01_documentos.sql` para que
    # `compras.contratos` y `compras.facturas` la compartan. Entra aqui por lo
    # mismo que las otras tres: se llama desde el SQL del build, y las dos
    # tablas ya publican el estado traducido en sus columnas.
    "compras.fn_estado_documento",
    "maestro.fn_fecha",
    # F-057 (2026-09-18): la copia local de la conversion de fecha del esquema
    # `personal`. Entra por lo mismo que las demas, y la copia es deliberada:
    # es lo que permite construir ese esquema sin depender de ningun otro.
    "personal.fn_fecha",
    # F-101 (2026-09-23): la conversion de la FECHA SERIE de Sigrid (la ultima
    # modificacion del parte), local a `personal` por el mismo motivo.
    "personal.fn_fecha_serie",
    "retenciones.fn_sigrid_date",
    "stg.fn_master_fecha_efectiva",
    "stg.fn_master_mes_representado",
    "stg.fn_sigrid_date_to_date",
)

#: GRUPO C · los rotos, vacíos o de instrumentación, con el HECHO que justifica
#: que sigan fuera de la superficie de consulta. Nacieron nueve y hoy son OCHO:
#: `mart.v_pbi_cp_tipologia` salió el 2026-09-15 al materializarla F-078.
GRUPO_C = {
    "cierre.v_pbi_cierre_indirectos_detalle": "no se puede ejecutar hoy",
    "mart.v_fact_periodificado": "hoy no periodifica nada",
    "aux.periodificacion_partida": "se crea vacia por diseno",
    "retenciones.v_src_lineas_venta": "siempre vacia en Ruesma",
    "retenciones.v_src_lineas_compra": "vista interna del build",
    "_meta.etl_runs": "log crudo del ETL",
    "_meta.diccionario": "log crudo del ETL",
    "_meta.obra_build": "log crudo del ETL",
}

#: GRUPO D · las piezas de preparacion de F-095 que la spec APROBADA por el
#: humano (design §Ficheros a modificar) deja fuera de la superficie a
#: proposito: la pregunta se responde desde `retenciones.saldo_contable` y sus
#: dos vistas. Cada una con el HECHO que lo justifica.
GRUPO_D_F095 = {
    "retenciones.cuentas_proveedor": "no trae importes",
    "retenciones.apuntes_contables": "sumar sin filtrar la clase multiplica el saldo",
    "retenciones.fin_obra": "la pregunta la responde v_retencion_contable_obra",
}


def _dicc():
    return cargar_diccionario(DIR_DICCIONARIO)[0]


def _ficha(nombre: str):
    return _dicc().por_nombre[nombre]


def _publicado(ficha) -> str:
    """Todo lo que de esta ficha llega al agente por `_meta.diccionario`."""
    trozos = [ficha.descripcion or "", ficha.grano or "", ficha.motivo_no_consumo or ""]
    trozos += list(ficha.ejemplos_preguntas)
    for c in ficha.columnas:
        trozos += [c.significado or "", c.nulo_significa or ""]
    for r in ficha.relaciones:
        trozos.append(r.porque or "")
    return normalizado(" ".join(trozos))


# ---------------------------------------------------------------------------
# A1 · los siete de `stg` son superficie de consulta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", GRUPO_A)
def test_f079_r1_los_siete_de_stg_son_consumo_recomendado(nombre: str) -> None:
    """El criterio literal del humano, objeto a objeto."""
    ficha = _ficha(nombre)

    assert ficha.consumo_recomendado is True, (
        f"{nombre} sigue desaconsejado para consulta: `stg` está entre los "
        f"esquemas que el MCP puede leer, y desaconsejarlo solo consigue que el "
        f"agente no mire donde sí hay dato"
    )
    assert not (ficha.motivo_no_consumo or "").strip(), (
        f"{nombre} conserva `motivo_no_consumo`: un objeto recomendado no puede "
        f"llevar el campo que explica por qué no se consulta"
    )


def test_f079_r1_no_queda_ningun_objeto_de_stg_desaconsejado_salvo_funciones() -> None:
    """Barrido del esquema entero, para que un objeto nuevo no se cuele.

    La lista escrita a mano envejece; esto no. Lo único que puede quedar fuera
    de la superficie de consulta en `stg` son las funciones, que no se
    consultan: se llaman desde el SQL del build.
    """
    fuera = [
        f.nombre
        for f in _dicc().fichas
        if f.esquema == "stg" and not f.consumo_recomendado and f.tipo != "funcion"
    ]

    assert fuera == [], f"objetos de `stg` todavía desaconsejados: {fuera}"


def test_f079_r1_el_esquema_stg_del_global_ya_no_dice_que_no_se_consulta() -> None:
    """La entrada de `esquemas` es lo PRIMERO que lee el agente para decidir
    dónde buscar. Dejarla en `false` haría inútil arreglar las siete fichas."""
    entrada = _dicc().esquemas["stg"]

    assert entrada["consumo_recomendado"] is True
    texto = normalizado(entrada["para_que_sirve"])
    assert "NO es superficie de consulta" not in texto, (
        "el bloque global sigue apartando al agente de `stg` en la primera "
        "línea que lee"
    )


@pytest.mark.parametrize("nombre", GRUPO_A)
def test_f079_r1_los_siete_cumplen_lo_que_el_validador_exige_al_recomendado(
    nombre: str,
) -> None:
    """R40 (`ejemplos_preguntas`), R6 (`columnas`) y R2 (`clave_negocio`).

    Subir el booleano activa tres exigencias del validador que antes no
    aplicaban. Se comprueban aquí, y no solo a través de `validar()`, para que
    el fallo diga qué falta y en qué objeto.
    """
    ficha = _ficha(nombre)

    assert ficha.ejemplos_preguntas, "R40: sin `ejemplos_preguntas` no hay enrutado"
    assert ficha.columnas, "R6: la superficie de consulta se describe entera"
    assert ficha.clave_negocio, "R2: quien consulta necesita saber qué es una fila"


# El validador entero sobre el diccionario real ya lo corre
# `test_f006_formato.py::test_f006_r2_el_diccionario_global_real_valida_entero`,
# con los pasos nocturnos leídos del pipeline. No se duplica aquí: lo que sí es
# de esta feature es qué exigencias NUEVAS activa subir el booleano, y eso lo
# comprueba objeto a objeto el test de arriba.


# ---------------------------------------------------------------------------
# A2 · ninguna advertencia de CORRECCIÓN se pierde por el camino
#
# Cuatro, no dos. El encargo nombraba las de `stg.plan_mensual` y
# `stg.obras.activa`; repasando los siete motivos frase a frase aparecen otras
# dos de la misma clase —`stg.version_master_vigente` y
# `stg.ambitos.uso_seguimiento`—, que también dan respuestas falsas y también
# viajaban dentro del campo que esta feature borra.
# ---------------------------------------------------------------------------


def test_f079_r2_la_trampa_de_las_versiones_master_sigue_en_la_ficha() -> None:
    """La más grave: sin filtrar versión, los importes se MULTIPLICAN.

    Vivía en el `motivo_no_consumo` de `stg.plan_mensual`. Al quitarlo tiene que
    quedarse en la `descripcion`, con las mismas palabras y el mismo peso.
    """
    ficha = _ficha("stg.plan_mensual")
    texto = normalizado(ficha.descripcion)

    assert contiene(texto, "TODAS las versiones master"), (
        "la advertencia se ha perdido al quitar `motivo_no_consumo`"
    )
    assert "multiplica" in texto.lower(), "no dice qué pasa: que los importes se inflan"
    assert contiene(texto, "sin filtrar version"), "no dice cuándo ocurre"
    assert "mart.fact_seguimiento_mensual" in texto, "no dice dónde está resuelta"


def test_f079_r2_la_trampa_de_las_versiones_master_es_ademas_regla_dura() -> None:
    """El segundo sitio desde donde llega, y por eso el riesgo es menor.

    `R-VERSION-MASTER` es `bloqueante` y su `ambito` incluye
    `stg.plan_mensual`, así que el aviso baja a la ficha aunque nadie lo
    escriba: el agente no se queda sin ella ni en el peor caso.
    """
    dicc = _dicc()
    regla = next(r for r in dicc.reglas if r.codigo == "R-VERSION-MASTER")

    assert regla.severidad == "bloqueante"
    assert "stg.plan_mensual" in regla.ambito
    assert contiene(regla.titulo, "conviven TODAS las versiones master")
    assert contiene(regla.regla, "multiplica los importes")


def test_f079_r2_la_columna_activa_de_stg_obras_sigue_avisando() -> None:
    """`stg.obras.activa` no significa nada: la escribe el SQL como constante.

    Estaba en el `motivo_no_consumo` («ademas su columna `activa` no significa
    nada»). Tiene que quedarse en la `descripcion`, y además sigue en el
    `significado` de la propia columna y en la regla `R-OBRA-ACTIVA`.
    """
    ficha = _ficha("stg.obras")

    assert contiene(ficha.descripcion, "`activa` no significa nada"), (
        "la advertencia de `activa` se ha perdido al quitar `motivo_no_consumo`"
    )

    activa = next(c for c in ficha.columnas if c.nombre == "activa")
    assert "NO SIGNIFICA NADA" in (activa.significado or "").upper()

    regla = next(r for r in _dicc().reglas if r.codigo == "R-OBRA-ACTIVA")
    assert "stg.obras" in regla.ambito


def test_f079_r2_version_master_vigente_avisa_de_que_es_global() -> None:
    """La tercera advertencia, que el encargo no nombraba.

    Su `motivo_no_consumo` decía que resuelve la versión de forma GLOBAL y que
    usarla para «qué plan rige» **no coincide con `mart`** en los meses
    anteriores a la última versión. Eso es corrección, no enrutado.
    """
    texto = normalizado(_ficha("stg.version_master_vigente").descripcion)

    assert "GLOBAL" in texto, "no dice que la resolución es global, una por obra"
    assert contiene(texto, "MES A MES"), "no dice que `mart` la elige mes a mes"
    assert contiene(texto, "no coincide"), (
        "no dice la consecuencia: que la respuesta difiere de la de `mart` en "
        "los meses anteriores a la última versión"
    )


def test_f079_r2_ambitos_avisa_de_que_uso_seguimiento_esta_desfasado() -> None:
    """La cuarta. Filtrar por `uso_seguimiento` da una respuesta INCOMPLETA."""
    ficha = _ficha("stg.ambitos")

    assert contiene(ficha.descripcion, "`uso_seguimiento`"), (
        "la advertencia de `uso_seguimiento` se ha perdido"
    )
    assert contiene(ficha.descripcion, "DESFASAD") or contiene(
        ficha.descripcion, "desfasad"
    )

    columna = next(c for c in ficha.columnas if c.nombre == "uso_seguimiento")
    assert "DESFASADO" in (columna.significado or "").upper()


def test_f079_r2_el_presupuesto_conserva_sus_dos_trampas_sin_motivo() -> None:
    """`stg.presupuesto` es el objeto que MÁS gana con esta feature —el ámbito
    de certificación solo está aquí— y el que más trampas tiene.

    Las dos multiplican importes y las dos estaban ya en la `descripcion`; lo
    que faltaba y viajaba en el `motivo_no_consumo` es que la columna de importe
    **se elige según el ámbito**.
    """
    ficha = _ficha("stg.presupuesto")
    texto = normalizado(ficha.descripcion + " " + (ficha.grano or ""))

    assert contiene(texto, "ACUMULADO A ORIGEN"), "trampa 1: el acumulado"
    assert contiene(texto, "conviven TODAS las versiones"), "trampa 2: las versiones"
    assert contiene(texto, "columna de importe"), (
        "no dice que la columna de importe se elige según el ámbito, que era lo "
        "único que vivía solo en `motivo_no_consumo`"
    )


@pytest.mark.parametrize("nombre", GRUPO_A)
def test_f079_r2_ninguna_ficha_de_stg_se_queda_sin_decir_a_donde_ir(
    nombre: str,
) -> None:
    """Quitar la preferencia de enrutado no es quitar la navegación.

    Los `motivo_no_consumo` llevaban punteros útiles («la misma información con
    etiquetas listas está en `mart.v_pbi_dim_partida`»). Dejar de desaconsejar
    no puede significar dejar al agente sin saber qué hay aguas abajo: cada
    ficha tiene que seguir citando al menos un objeto de otro esquema.
    """
    texto = _publicado(_ficha(nombre))
    otros = [e for e in ("mart.", "cierre.", "maestro.", "_meta.") if e in texto]

    assert otros, (
        f"{nombre} ya no cita ningún objeto aguas abajo: al borrar el motivo se "
        f"ha ido también el puntero que ayudaba a navegar"
    )


# ---------------------------------------------------------------------------
# A3 · los grupos B y C quedan como estaban, y eso se comprueba
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", GRUPO_B_FUNCIONES)
def test_f079_r3_las_funciones_siguen_fuera_de_la_superficie(nombre: str) -> None:
    """Una función no se consulta: se llama desde el SQL del build.

    «Todo lo expuesto es para consulta» no las alcanza, y recomendarlas metería
    once entradas inútiles en el enrutado del agente.
    """
    ficha = _ficha(nombre)

    assert ficha.tipo == "funcion"
    assert ficha.consumo_recomendado is False
    assert (ficha.motivo_no_consumo or "").strip(), "R3: sin motivo no pasa la puerta"


@pytest.mark.parametrize("nombre", sorted(GRUPO_C))
def test_f079_r3_los_rotos_y_vacios_siguen_fuera_de_la_superficie(nombre: str) -> None:
    """Aquí el aviso es un HECHO, no una preferencia.

    Marcarlos recomendados haría que el agente los consultase y fallara, que es
    justo el defecto que F-006 arregló con `mart.v_pbi_cp_tipologia` y
    `cierre.v_pbi_cierre_indirectos_detalle`.
    """
    ficha = _ficha(nombre)

    assert ficha.consumo_recomendado is False, GRUPO_C[nombre]
    assert (ficha.motivo_no_consumo or "").strip(), "R3: sin motivo no pasa la puerta"


def test_f079_r3_el_inventario_de_lo_que_no_se_toca_esta_completo() -> None:
    """Fuera de `raw` no puede quedar ningún desaconsejado sin inventariar.

    El recuento de partida fue 27 = 7 (grupo A) + 11 funciones + 9 rotos, y hoy
    son 19 = 11 funciones + 8 rotos, porque F-078 subió
    `mart.v_pbi_cp_tipologia` a la superficie de consulta. Si aparece uno nuevo
    que no está en ninguna de las dos listas, este test lo saca: o se documenta
    aquí, o se sube a la superficie de consulta.
    """
    fuera = {
        f.nombre
        for f in _dicc().fichas
        if not f.consumo_recomendado and f.esquema != "raw"
    }

    inventario = set(GRUPO_B_FUNCIONES) | set(GRUPO_C) | set(GRUPO_D_F095)
    assert fuera == inventario, (
        f"sin inventariar: {sorted(fuera - inventario)}; "
        f"inventariado y ya no está: "
        f"{sorted(inventario - fuera)}"
    )


def test_f079_r3_los_desaconsejados_de_grupo_c_dicen_el_hecho_no_la_preferencia() -> (
    None
):
    """La distinción que sostiene toda la feature, escrita donde se lee.

    Un motivo que dice «capa intermedia» es una preferencia y se va. Uno que
    dice «no devuelve una sola fila» es un hecho y se queda. Los del grupo C
    tienen que ser de los segundos: ninguno puede apoyarse en «capa intermedia»
    como razón única.
    """
    flojos = [
        nombre
        for nombre in GRUPO_C
        if normalizado(_ficha(nombre).motivo_no_consumo or "").strip().lower()
        in ("capa intermedia.", "capa intermedia")
    ]

    assert flojos == [], (
        f"estos siguen justificándose con una preferencia de enrutado, no con "
        f"un hecho: {flojos}"
    )


# ---------------------------------------------------------------------------
# A5 · la versión del diccionario sube (publicar es cosa del humano)
# ---------------------------------------------------------------------------


def test_f079_r5_la_version_del_diccionario_sube() -> None:
    """Sin subirla, `publicar-diccionario` republica un contenido nuevo con la
    etiqueta vieja y nadie ve que cambió. El árbol venía de la 17."""
    assert int(_dicc().version) >= 18, (
        "la versión del diccionario no ha subido: lo que el MCP lea seguirá "
        "pareciendo lo de antes"
    )


def test_f079_r5_el_changelog_del_global_explica_la_version_nueva() -> None:
    """La versión es lo que lee una PERSONA, y sin entrada de changelog no
    dice nada. Cada versión anterior tiene la suya en la cabecera."""
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    # La cabecera es todo lo anterior a la CLAVE `version:`, y la clave es la
    # que empieza en columna cero. Partir por la primera aparición del texto
    # «version:» cortaba dentro de la prosa —la entrada de F-078 escribe «es la
    # mitad importante de esta version:»— y dejaba fuera el changelog de la
    # versión siguiente, así que el test fallaba con la entrada escrita y
    # delante (F-083, 2026-09-16).
    cabecera = normalizado(re.split(r"^version:", texto, maxsplit=1, flags=re.M)[0])

    assert f"version {_dicc().version}" in cabecera, (
        "la cabecera de `00_global.yaml` no explica qué cambió en esta versión"
    )
    assert "F-079" in cabecera
