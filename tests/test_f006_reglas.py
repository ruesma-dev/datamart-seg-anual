# tests/test_f006_reglas.py
"""
F-006 · Tests de las reglas duras del diccionario (R9-R12) y de la batería de
aceptación (R39).

Las reglas duras son **la pieza de más valor por línea de toda la feature**: son
lo que impide que un agente devuelva un número plausible y falso. Casi todas
están escritas a partir de un error real —el que multiplicaba por nueve, el que
dio 38,9 M€ en una sola obra siendo esa la cifra de toda la empresa— y por eso
el validador exige `motivo` además de `regla`.

Ningún test de este fichero abre red ni BBDD.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain.diccionario import (
    CODIGOS_REGLAS_OBLIGATORIAS,
    SEVERIDADES,
    derivar_avisos,
    validar,
)
from tests.test_f006_formato import (  # reutiliza las fábricas de fixtures
    PASOS_NOCTURNOS,
    _dicc,
    _ficha,
    _regla,
)


def _codigos(errores) -> set[str]:
    return {e.regla for e in errores}


# ---------------------------------------------------------------------------
# R9 · Las doce reglas duras
# ---------------------------------------------------------------------------


def test_f006_r9_son_doce_reglas_y_estas() -> None:
    """La lista es cerrada y explícita: si mañana se añade una, se ve en el diff."""
    assert len(CODIGOS_REGLAS_OBLIGATORIAS) == 12
    assert set(CODIGOS_REGLAS_OBLIGATORIAS) == {
        "R-FRESCURA-MANUAL",
        "R-IMPORTE-MES",
        "R-UNIVERSO-OBRA",
        "R-OBRA-ACTIVA",
        "R-VERSION-MASTER",
        "R-FAS-AMBIGUO",
        "R-CLAVE-SUSTITUTA",
        "R-ABONO-NEGATIVO",
        "R-LINEA-ID-NO-UNICA",
        "R-RETENCION-NO-JOIN-LINEAS",
        "R-COMPRAS-SIN-IVA",
        "R-COMPRAS-TIPO-DOC",
    }


@pytest.mark.parametrize("codigo", CODIGOS_REGLAS_OBLIGATORIAS)
def test_f006_r9_falta_una_regla_obligatoria_y_falla(codigo: str) -> None:
    """Quitar una regla del YAML deja al agente sin esa defensa. Es bloqueante."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS if c != codigo]

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert errores, f"faltando {codigo} tenía que fallar"
    assert any(codigo in e.detalle for e in errores), (
        f"el error no nombra la regla que falta: {errores}"
    )


def test_f006_r9_las_doce_completas_no_producen_error() -> None:
    assert validar(_dicc(), PASOS_NOCTURNOS) == []


@pytest.mark.parametrize("campo", ["titulo", "regla", "motivo"])
def test_f006_r9_una_regla_sin_texto_falla(campo: str) -> None:
    """`motivo` es obligatorio: una regla sin porqué se desobedece a la primera."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], **{campo: "  "})

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any(campo in e.detalle for e in errores), errores


def test_f006_r9_una_regla_sin_ambito_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], ambito=())

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("ambito" in e.detalle for e in errores)


@pytest.mark.parametrize("severidad", SEVERIDADES)
def test_f006_r9_las_severidades_del_vocabulario_validan(severidad: str) -> None:
    reglas = [_regla(c, severidad=severidad) for c in CODIGOS_REGLAS_OBLIGATORIAS]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


def test_f006_r9_una_regla_duplicada_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas.append(_regla(CODIGOS_REGLAS_OBLIGATORIAS[0]))

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("duplicad" in e.detalle.lower() for e in errores)


# ---------------------------------------------------------------------------
# R11 · Un ámbito que apunta a la nada no protege nada
# ---------------------------------------------------------------------------


def test_f006_r11_una_regla_bloqueante_con_objeto_inexistente_falla() -> None:
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        CODIGOS_REGLAS_OBLIGATORIAS[0],
        severidad="bloqueante",
        ambito=("mart.objeto_que_no_existe",),
    )

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert errores
    assert any("mart.objeto_que_no_existe" in e.detalle for e in errores)
    assert "R11" in _codigos(errores)


def test_f006_r11_un_esquema_inexistente_en_el_ambito_tambien_falla() -> None:
    """`tesoreria` no existe todavía (es F-037): protegerlo sería protegar humo."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(CODIGOS_REGLAS_OBLIGATORIAS[0], ambito=("tesoreria",))

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("tesoreria" in e.detalle for e in errores)


def test_f006_r11_tambien_se_exige_a_las_reglas_de_aviso() -> None:
    """R11 solo obliga a las `bloqueante`; aquí se es más estricto a propósito.

    No hay ningún caso legítimo en el que una regla de aviso deba apuntar a un
    objeto inexistente, y dejarlo pasar convertiría `severidad: aviso` en la
    forma de colar un ámbito roto.
    """
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        CODIGOS_REGLAS_OBLIGATORIAS[0],
        severidad="aviso",
        ambito=("mart.objeto_que_no_existe",),
    )

    errores = validar(_dicc(reglas=reglas), PASOS_NOCTURNOS)

    assert any("mart.objeto_que_no_existe" in e.detalle for e in errores)


def test_f006_r11_un_ambito_de_esquema_valido_resuelve() -> None:
    reglas = [_regla(c, ambito=("mart", "cierre")) for c in CODIGOS_REGLAS_OBLIGATORIAS]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


def test_f006_r11_un_ambito_de_objeto_existente_resuelve() -> None:
    reglas = [
        _regla(c, ambito=("mart.fact_seguimiento_mensual",))
        for c in CODIGOS_REGLAS_OBLIGATORIAS
    ]

    assert validar(_dicc(reglas=reglas), PASOS_NOCTURNOS) == []


# ---------------------------------------------------------------------------
# R12 · Los avisos se DERIVAN, no se escriben
# ---------------------------------------------------------------------------


def test_f006_r12_una_regla_de_esquema_alcanza_a_todas_sus_fichas() -> None:
    """El agente que solo consulte la ficha de un objeto ve sus trampas igual."""
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla("R-IMPORTE-MES", ambito=("mart",))

    derivado = derivar_avisos(_dicc(reglas=reglas))

    ficha = derivado.por_nombre["mart.fact_seguimiento_mensual"]
    assert "R-IMPORTE-MES" in ficha.avisos


def test_f006_r12_una_regla_de_objeto_solo_alcanza_a_ese_objeto() -> None:
    otra = _ficha(objeto="fact_seguimiento_categoria")
    reglas = [_regla(c, ambito=("cierre",)) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        "R-IMPORTE-MES", ambito=("mart.fact_seguimiento_mensual",)
    )

    derivado = derivar_avisos(_dicc(fichas=[_ficha(), otra], reglas=reglas))

    assert "R-IMPORTE-MES" in derivado.por_nombre["mart.fact_seguimiento_mensual"].avisos
    assert "R-IMPORTE-MES" not in derivado.por_nombre["mart.fact_seguimiento_categoria"].avisos


def test_f006_r12_los_avisos_salen_ordenados_y_sin_repetir() -> None:
    """Determinismo: la misma ficha publica siempre la misma lista de avisos."""
    reglas = [
        _regla(c, ambito=("mart", "mart.fact_seguimiento_mensual"))
        for c in CODIGOS_REGLAS_OBLIGATORIAS
    ]

    avisos = derivar_avisos(_dicc(reglas=reglas)).por_nombre[
        "mart.fact_seguimiento_mensual"
    ].avisos

    assert list(avisos) == sorted(set(avisos))
    assert len(avisos) == len(CODIGOS_REGLAS_OBLIGATORIAS)


def test_f006_r12_derivar_no_muta_el_diccionario_original() -> None:
    """Las entidades son inmutables: `derivar_avisos` devuelve uno nuevo."""
    dicc = _dicc()

    derivado = derivar_avisos(dicc)

    assert dicc.por_nombre["mart.fact_seguimiento_mensual"].avisos == ()
    assert derivado is not dicc


def test_f006_r12_derivar_conserva_el_resto_de_la_ficha() -> None:
    dicc = _dicc()

    derivado = derivar_avisos(dicc)

    antes = dicc.por_nombre["mart.fact_seguimiento_mensual"]
    despues = derivado.por_nombre["mart.fact_seguimiento_mensual"]
    assert despues.descripcion == antes.descripcion
    assert despues.columnas == antes.columnas
    assert despues.relaciones == antes.relaciones


def test_f006_r12_escribir_avisos_a_mano_es_un_error() -> None:
    """El autor de la ficha no tiene que acordarse; tampoco puede inventárselos."""
    a_mano = _ficha(avisos=("R-IMPORTE-MES",))

    errores = validar(_dicc(fichas=[a_mano]), PASOS_NOCTURNOS)

    assert errores
    assert any("avisos" in e.detalle for e in errores)
    assert "R12" in _codigos(errores)


def test_f006_r12_derivar_es_idempotente() -> None:
    """Publicar dos veces el mismo YAML tiene que dar exactamente lo mismo."""
    dicc = _dicc()

    una = derivar_avisos(dicc)
    dos = derivar_avisos(una)

    assert una.fichas == dos.fichas


# ===========================================================================
# El bloque global REAL de `config/diccionario/00_global.yaml`
#
# Estos tests no usan fixtures: leen lo que de verdad se va a publicar en la
# base. Son la diferencia entre «el validador sabe exigir doce reglas» y «las
# doce reglas están escritas».
# ===========================================================================

from pathlib import Path  # noqa: E402

from etl_sigrid.infrastructure.diccionario.cargador_yaml import (  # noqa: E402
    cargar_diccionario,
)

DIR_DICCIONARIO = Path(__file__).resolve().parents[1] / "config" / "diccionario"


def _diccionario_real():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def test_f006_r9_el_global_real_declara_las_doce_reglas() -> None:
    dicc = _diccionario_real()

    declaradas = {r.codigo for r in dicc.reglas}
    faltan = set(CODIGOS_REGLAS_OBLIGATORIAS) - declaradas
    assert not faltan, f"faltan reglas en 00_global.yaml: {sorted(faltan)}"


def test_f006_r9_cada_regla_real_dice_que_hacer_y_por_que() -> None:
    """Una regla sin motivo se desobedece a la primera. Y sin ámbito no llega
    a ninguna ficha, que es la vía por la que el agente la va a leer."""
    dicc = _diccionario_real()

    for regla in dicc.reglas:
        assert len(regla.regla.strip()) >= 40, f"{regla.codigo}: `regla` demasiado corta"
        assert len(regla.motivo.strip()) >= 30, f"{regla.codigo}: `motivo` demasiado corto"
        assert regla.ambito, f"{regla.codigo}: sin `ambito`"
        assert regla.severidad in SEVERIDADES, f"{regla.codigo}: severidad inválida"


def test_f006_r9_las_reglas_reales_son_bloqueantes_salvo_las_que_avisan() -> None:
    """La mayoría son bloqueantes: no son consejos, son la diferencia entre un
    número correcto y uno plausible y falso."""
    dicc = _diccionario_real()

    bloqueantes = [r.codigo for r in dicc.reglas if r.severidad == "bloqueante"]

    assert len(bloqueantes) >= 10, f"solo {len(bloqueantes)} reglas bloqueantes"


def test_f006_r10_el_global_real_trae_ordenes_de_magnitud() -> None:
    """Para que el agente detecte una cifra absurda antes de darla por buena.

    Es lo que hizo el prototipo y funcionó: el error real de retenciones daba
    38,9 M€ en UNA obra siendo esa la cifra de toda la empresa.
    """
    dicc = _diccionario_real()

    ordenes = dicc.global_raw.get("ordenes_de_magnitud") or []

    assert len(ordenes) >= 3
    for orden in ordenes:
        assert orden.get("concepto")
        assert isinstance(orden.get("valor_aproximado"), (int, float))
        assert orden.get("unidad")


def test_f006_r11_los_ambitos_reales_apuntan_a_algo_que_existe() -> None:
    """Cada `ambito` es un esquema del datamart o un objeto que el repositorio
    publica de verdad. Se comprueba contra el inventario, no contra las fichas:
    mientras un bloque no esté escrito, su objeto está en `pendientes`."""
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART
    from tests.test_f006_cobertura import _inventario_del_repositorio

    dicc = _diccionario_real()
    publicados = {o.nombre for o in _inventario_del_repositorio()}

    for regla in dicc.reglas:
        for destino in regla.ambito:
            existe = (
                destino in publicados
                if "." in destino
                else destino in ESQUEMAS_DEL_DATAMART
            )
            assert existe, f"{regla.codigo}: el ámbito `{destino}` no existe"


def test_f006_r9_el_diccionario_real_no_tiene_reglas_de_mas_sin_codigo() -> None:
    dicc = _diccionario_real()

    for regla in dicc.reglas:
        assert regla.codigo.startswith("R-"), f"código raro: {regla.codigo!r}"


# --- Reglas concretas que no pueden faltar por su contenido ---------------
#
# No basta con que el código esté: lo que protege es el TEXTO. Estos tests
# fijan el contenido mínimo de las tres reglas que nacieron de un número falso
# real, para que un refactor bienintencionado no las diluya.


def test_f006_r9_importe_mes_dice_lo_que_no_se_puede_hacer() -> None:
    dicc = _diccionario_real()
    regla = next(r for r in dicc.reglas if r.codigo == "R-IMPORTE-MES")

    texto = (regla.regla + " " + regla.motivo).lower()

    assert "importe_origen" in texto
    assert "importe_mes" in texto
    assert "mart.fact_seguimiento_mensual" in regla.ambito


def test_f006_r9_retencion_no_join_lineas_cita_el_incidente() -> None:
    dicc = _diccionario_real()
    regla = next(r for r in dicc.reglas if r.codigo == "R-RETENCION-NO-JOIN-LINEAS")

    assert "38,9" in regla.motivo or "38.9" in regla.motivo
    assert "retenciones.movimientos" in regla.ambito


def test_f006_r9_frescura_manual_nombra_los_cuatro_esquemas() -> None:
    dicc = _diccionario_real()
    regla = next(r for r in dicc.reglas if r.codigo == "R-FRESCURA-MANUAL")

    assert set(regla.ambito) >= {"cierre", "compras", "maestro", "retenciones"}
    assert "_meta.v_frescura" in regla.regla


# ===========================================================================
# El trinquete de `pendientes` también vale para los ámbitos y las relaciones
# ===========================================================================


def test_f006_r11_un_ambito_declarado_pendiente_se_tolera() -> None:
    """Mientras el bloque no esté escrito, la regla ya puede apuntar a su objeto.

    Es lo que permite escribir las doce reglas ANTES que las ochenta fichas, que
    es el orden correcto: las reglas son la pieza de más valor por línea.
    Cuando `pendientes` quede vacía, la comprobación vuelve a ser estricta.
    """
    reglas = [_regla(c) for c in CODIGOS_REGLAS_OBLIGATORIAS]
    reglas[0] = _regla(
        CODIGOS_REGLAS_OBLIGATORIAS[0], ambito=("compras.fact_compras_linea",)
    )

    sin_declarar = _dicc(reglas=reglas)
    declarado = _dicc(reglas=reglas, pendientes=("compras.fact_compras_linea",))

    assert validar(sin_declarar, PASOS_NOCTURNOS)
    assert validar(declarado, PASOS_NOCTURNOS) == []


# ===========================================================================
# La batería de aceptación (T11 · R39, R41)
#
# Es el criterio de éxito de F-006, escrito dentro del propio diccionario para
# que el agente pueda leerlo: **13 preguntas bien respondidas y 5 bien
# rechazadas**. Un «no puedo responderlo con esta base, y este es el motivo» es
# una respuesta correcta; inventarse una cifra, no.
# ===========================================================================

ESTADOS_BATERIA = ("respondible", "parcial", "bloqueada")

#: El recuento honesto de `requirements.md` §9: de 18 preguntas, 13 se
#: responden hoy, 3 se responden a medias y 2 no se pueden responder.
PARCIALES = {"P3", "P5", "P14"}
BLOQUEADAS = {"P4", "P17"}


def _bateria():
    return _diccionario_real().global_raw["preguntas_aceptacion"]


def test_f006_r39_bateria_estan_las_dieciocho_preguntas() -> None:
    ids = [p["id"] for p in _bateria()]

    assert ids == [f"P{n}" for n in range(1, 19)], ids


def test_f006_r39_bateria_cada_pregunta_dice_que_seria_correcto() -> None:
    """Sin `respuesta_correcta` la batería no es un criterio, es una lista de
    temas: dos personas la darían por superada con respuestas distintas."""
    for pregunta in _bateria():
        assert len(pregunta["pregunta"].strip()) >= 20, pregunta["id"]
        assert len(pregunta["respuesta_correcta"].strip()) >= 60, pregunta["id"]
        assert pregunta["estado"] in ESTADOS_BATERIA, pregunta["id"]


def test_f006_r41_bateria_el_recuento_honesto_es_trece_tres_y_dos() -> None:
    """Si el criterio de cierre se lee como «responde los seis casos del
    humano», F-006 no puede cerrar. Se cierra con este recuento."""
    por_estado: dict[str, set[str]] = {}
    for pregunta in _bateria():
        por_estado.setdefault(pregunta["estado"], set()).add(pregunta["id"])

    assert por_estado["parcial"] == PARCIALES
    assert por_estado["bloqueada"] == BLOQUEADAS
    assert len(por_estado["respondible"]) == 13


def test_f006_r41_bateria_lo_no_respondible_dice_que_feature_lo_desbloquea() -> None:
    """Un «no se puede» sin dueño se convierte en un «no se puede» para siempre."""
    for pregunta in _bateria():
        if pregunta["estado"] == "respondible":
            assert "bloqueada_por" not in pregunta, pregunta["id"]
        else:
            assert pregunta.get("bloqueada_por"), pregunta["id"]


def test_f006_r41_bateria_las_features_que_bloquean_existen_de_verdad() -> None:
    """Apuntar a una feature inventada es peor que no apuntar a ninguna."""
    import json
    from pathlib import Path

    features = json.loads(
        (Path(__file__).resolve().parents[1] / "harness" / "features.json").read_text(
            encoding="utf-8"
        )
    )["features"]
    existentes = {f["id"] for f in features}

    for pregunta in _bateria():
        bloqueante = pregunta.get("bloqueada_por")
        if bloqueante:
            assert bloqueante in existentes, f"{pregunta['id']} -> {bloqueante}"


def test_f006_r39_bateria_los_objetos_esperados_existen_en_el_repositorio() -> None:
    """Enrutar a un objeto que no existe manda al agente a inventarse el SQL."""
    from tests.test_f006_cobertura import _inventario_del_repositorio

    publicados = {o.nombre for o in _inventario_del_repositorio()}

    for pregunta in _bateria():
        for objeto in pregunta.get("objetos_esperados") or []:
            assert objeto in publicados, f"{pregunta['id']}: {objeto} no existe"


def test_f006_r41_bateria_las_imposibles_no_esperan_ningun_objeto() -> None:
    """P4 (tesorería) y P17 (clientes) se responden con un «no lo tenemos».

    Si la ficha les diera objetos, el agente buscaría ahí y acabaría dando una
    cifra parecida a la pedida pero de otra cosa.
    """
    por_id = {p["id"]: p for p in _bateria()}

    for identificador in BLOQUEADAS:
        assert not (por_id[identificador].get("objetos_esperados") or []), identificador
        assert "no" in por_id[identificador]["respuesta_correcta"].lower()


def test_f006_r39_bateria_las_cuatro_trampas_estan_marcadas() -> None:
    """P9, P10, P11 y P16 son preguntas trampa deliberadas: si el agente cae en
    alguna, la ficha correspondiente está mal escrita."""
    por_id = {p["id"]: p for p in _bateria()}

    for identificador in ("P9", "P10", "P11", "P16"):
        assert por_id[identificador].get("es_trampa") is True, identificador


def test_f006_r39_bateria_cada_trampa_nombra_la_regla_que_la_evita() -> None:
    """La trampa y su antídoto van juntos: es lo que permite comprobar, al
    ejecutar la batería, si el fallo fue del agente o de la ficha."""
    codigos = {r.codigo for r in _diccionario_real().reglas}
    por_id = {p["id"]: p for p in _bateria()}

    for identificador in ("P9", "P10", "P11", "P16"):
        reglas = por_id[identificador].get("reglas_implicadas") or []
        assert reglas, identificador
        assert set(reglas) <= codigos, f"{identificador}: {reglas}"


# ===========================================================================
# R10 · Los ordenes de magnitud (defecto 4 de la review)
#
# Su unica funcion es que el agente detecte una cifra absurda ANTES de darla
# por buena. Mezclar dos criterios sin decirlo la invierte: llamar «total de la
# empresa» a un saldo VIVO hace que un agente que sume todos los movimientos
# concluya que su numero esta mal cuando esta bien.
# ===========================================================================

CRITERIOS_MAGNITUD = ("saldo_vivo", "total")


def test_f006_r10_cada_orden_de_magnitud_declara_su_criterio() -> None:
    for orden in _diccionario_real().global_raw["ordenes_de_magnitud"]:
        assert orden.get("criterio") in CRITERIOS_MAGNITUD, orden["concepto"]


def test_f006_r10_las_cifras_de_retencion_son_de_saldo_vivo_y_lo_dicen() -> None:
    """34,7 M€ y 21,9 M€ son saldo VIVO, no el total practicado nunca."""
    por_concepto = {
        o["concepto"]: o for o in _diccionario_real().global_raw["ordenes_de_magnitud"]
    }

    vivos = [o for o in por_concepto.values() if o["valor_aproximado"] in (34700000, 21900000)]

    assert len(vivos) == 2
    for orden in vivos:
        assert orden["criterio"] == "saldo_vivo"
        assert "vivo" in orden["concepto"].lower(), (
            f"{orden['concepto']}: el concepto tiene que decir que es saldo vivo, "
            f"no solo el campo `criterio`"
        )


def test_f006_r10_la_fuente_es_un_documento_que_existe_en_el_repositorio() -> None:
    """Una medición sin fuente comprobable envejece sin que nadie lo note."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]

    for orden in _diccionario_real().global_raw["ordenes_de_magnitud"]:
        fuente = orden.get("fuente", "")
        candidatos = (t.strip("`,.;:()") for t in fuente.split())
        ficheros = [c for c in candidatos if c.endswith(".md")]
        assert ficheros, f"{orden['concepto']}: la fuente no cita ningún documento"
        for fichero in ficheros:
            assert (raiz / fichero).exists(), (
                f"{orden['concepto']}: `{fichero}` no existe en el repositorio"
            )


def test_f006_r10_los_recuentos_de_efectos_van_por_sentido() -> None:
    """Con un solo total y dos importes por sentido, los criterios no casan y
    no se puede contrastar ninguna cifra contra su recuento."""
    conceptos = [
        o["concepto"].lower()
        for o in _diccionario_real().global_raw["ordenes_de_magnitud"]
        if o["unidad"] == "filas"
    ]

    assert any("proveedor" in c for c in conceptos)
    assert any("cliente" in c for c in conceptos)


# ===========================================================================
# Las reglas no pueden mandar consultar lo que no existe (defecto 6)
#
# `R-FRESCURA-MANUAL` mandaba usar `_meta.v_diccionario`, que la crea el bloque
# E y hoy no existe. Una instruccion que el agente no puede ejecutar es una
# instruccion que no se cumple, y el resultado es el mismo que no haberla
# escrito: un dato de hace semanas dado sin advertencia.
# ===========================================================================

_OBJETO_CITADO = re.compile(
    r"\b(_meta|mart|cierre|compras|maestro|retenciones|stg|aux|raw)\.([a-z_][a-z0-9_]*)"
)


def _objetos_citados(texto: str) -> set[str]:
    return {f"{e}.{o}" for e, o in _OBJETO_CITADO.findall(texto or "")}


def test_f006_r9_las_reglas_no_citan_objetos_que_no_existen() -> None:
    from tests.test_f006_cobertura import _inventario_del_repositorio

    publicados = {o.nombre for o in _inventario_del_repositorio()}

    for regla in _diccionario_real().reglas:
        citados = _objetos_citados(regla.regla) | _objetos_citados(regla.motivo)
        fantasmas = sorted(citados - publicados)
        assert not fantasmas, f"{regla.codigo} cita {fantasmas}, que no existen"


def test_f006_r39_la_bateria_tampoco_cita_objetos_que_no_existen() -> None:
    from tests.test_f006_cobertura import _inventario_del_repositorio

    publicados = {o.nombre for o in _inventario_del_repositorio()}

    for pregunta in _diccionario_real().global_raw["preguntas_aceptacion"]:
        citados = _objetos_citados(pregunta["respuesta_correcta"])
        fantasmas = sorted(citados - publicados)
        assert not fantasmas, f"{pregunta['id']} cita {fantasmas}, que no existen"


def test_f006_r16_frescura_manual_cita_la_vista_que_si_existe_hoy() -> None:
    regla = next(
        r for r in _diccionario_real().reglas if r.codigo == "R-FRESCURA-MANUAL"
    )

    assert "_meta.v_frescura" in regla.regla
    assert "_meta.v_diccionario" not in regla.regla, (
        "esa vista la crea el bloque E; hasta entonces la regla mandaría ejecutar "
        "una consulta que revienta"
    )


# ===========================================================================
# R-CLAVE-SUSTITUTA solo vale para lo que se reconstruye (defecto 7)
#
# La regla metia `aux.periodificacion_partida` en su ambito y declaraba
# `regla_id` entre las claves que «se reasignan enteras en cada build», con el
# motivo «las tablas se recrean con DROP + CREATE». Esa tabla se crea con
# `CREATE TABLE IF NOT EXISTS` y ningun build la reconstruye: `regla_id` es
# ESTABLE. El error es conservador —no produce numeros falsos— pero es un dato
# falso dentro de una regla dura, y las reglas duras se respetan por ser
# exactas.
#
# Comprobable: un objeto cuya clave se reasigna tiene que aparecer en algun
# `DROP`, `TRUNCATE` o `truncate_table(...)` del repositorio.
# ===========================================================================


def _se_reconstruye(nombre: str) -> bool:
    from pathlib import Path

    esquema, objeto = nombre.split(".", 1)
    raiz = Path(__file__).resolve().parents[1]
    fuentes = [
        *(raiz / "etl_sigrid" / "infrastructure" / "postgres" / "sql").rglob("*.sql"),
        *(raiz / "etl_sigrid" / "application" / "steps").rglob("*.py"),
    ]
    patrones = (
        re.compile(rf"DROP\s+(TABLE|VIEW|MATERIALIZED\s+VIEW)[^\n;]*\b{esquema}\.{objeto}\b",
                   re.IGNORECASE),
        re.compile(rf"TRUNCATE[^\n;]*\b{esquema}\.{objeto}\b", re.IGNORECASE),
        re.compile(rf"truncate_table\(\s*[\"']{esquema}[\"']\s*,\s*[\"']{objeto}[\"']"),
    )
    for fuente in fuentes:
        texto = fuente.read_text(encoding="utf-8")
        if any(p.search(texto) for p in patrones):
            return True
    return False


def test_f006_r9_el_ambito_de_clave_sustituta_solo_lleva_lo_que_se_reconstruye() -> None:
    regla = next(
        r for r in _diccionario_real().reglas if r.codigo == "R-CLAVE-SUSTITUTA"
    )

    estables = [
        destino
        for destino in regla.ambito
        if "." in destino and not _se_reconstruye(destino)
    ]

    assert not estables, (
        f"{estables} no se reconstruyen en ningún build: su clave es estable y la "
        f"regla miente al meterlos en su ámbito"
    )


def test_f006_r9_el_control_del_detector_de_reconstruccion() -> None:
    """Si el detector diera siempre True, el test de arriba pasaría en falso."""
    assert _se_reconstruye("mart.fact_seguimiento_mensual") is True
    assert _se_reconstruye("stg.plan_mensual") is True, "se trunca desde Python"
    assert _se_reconstruye("aux.periodificacion_partida") is False


# ===========================================================================
# R-IMPORTE-MES tiene que alcanzar a TODO lo que tiene la trampa (defecto 8)
#
# El ambito listaba objetos de `mart` y `stg`, pero el motivo cita el bug de la
# Tanda 1.4 **del cierre**, el que multiplicaba por unas nueve veces. `cierre`
# tiene la misma trampa con otros nombres: `ejecutado_origen` es el acumulado y
# `ejecutado_mes` el parcial. Un agente que lea la regla y no la ficha repite el
# error original.
#
# Comprobable sin auditar nada: un objeto que documente A LA VEZ una columna en
# euros `suma_solo_dentro_del_mes` y otra en euros `ultimo_valor` tiene por
# definicion el par parcial/acumulado, y la regla debe alcanzarlo.
# ===========================================================================


def _objetos_con_par_parcial_acumulado() -> list[str]:
    encontrados = []
    for ficha in _diccionario_real().fichas:
        parciales = {
            c.nombre
            for c in ficha.columnas
            if c.agregacion == "suma_solo_dentro_del_mes" and c.unidad == "EUR"
        }
        acumuladas = {
            c.nombre
            for c in ficha.columnas
            if c.agregacion == "ultimo_valor" and c.unidad == "EUR"
        }
        if parciales and acumuladas:
            encontrados.append(ficha.nombre)
    return sorted(encontrados)


def test_f006_r9_importe_mes_alcanza_a_todo_lo_que_tiene_la_trampa() -> None:
    from etl_sigrid.domain.diccionario import alcanza

    regla = next(r for r in _diccionario_real().reglas if r.codigo == "R-IMPORTE-MES")
    por_nombre = _diccionario_real().por_nombre

    fuera = [
        nombre
        for nombre in _objetos_con_par_parcial_acumulado()
        if not alcanza(regla, por_nombre[nombre])
    ]

    assert not fuera, (
        f"{fuera} tienen el par parcial/acumulado en euros y R-IMPORTE-MES no "
        f"los alcanza: el agente que lea la regla y no la ficha repite el ≈9x"
    )


def test_f006_r9_el_control_del_detector_del_par() -> None:
    """Si el detector no encontrara nada, el test de arriba pasaría en falso."""
    detectados = _objetos_con_par_parcial_acumulado()

    assert "mart.fact_seguimiento_mensual" in detectados
    assert "cierre.fact_cierre_mensual" in detectados
    assert len(detectados) >= 8


def test_f006_r9_importe_mes_nombra_las_columnas_del_cierre() -> None:
    """El agente busca por nombre de columna: `importe_mes` no le dice nada
    cuando está mirando `cierre`."""
    regla = next(r for r in _diccionario_real().reglas if r.codigo == "R-IMPORTE-MES")

    assert "ejecutado_origen" in regla.regla
    assert "ejecutado_mes" in regla.regla
