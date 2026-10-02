# tests/test_f097_planificador.py
"""
F-097 · El dominio de los descompuestos, sin red ni base de datos.

Tres cosas puras que viven en `etl_sigrid/domain/descompuestos.py`:

1. `planificar_relectura` (R5-R7): que versiones del master se releen de Sigrid
   esta noche (nuevas, la vigente de cada obra, las de huella distinta), cuales
   se borran (las que Sigrid ya no tiene) y cuales se aplazan por el tope de MB.
2. `planificar_troceado` (R21): que versiones se retrocean en el build, en que
   lotes y cuales se aplazan por el mismo tope.
3. `trocear_des` (R13, R14, R19): el ESPEJO en Python del troceado que hace el
   SQL (`sql/descompuestos/01_troceado.sql`). Es el precedente de F-052
   (`domain/arbol_partidas.py`): la regla, ejecutable y probada sin base de
   datos. Que el SQL use las MISMAS posiciones lo fija
   `tests/test_f097_descompuestos.py` contra `POSICIONES`.

Los registros de ejemplo imitan el formato medido el 2026-09-27/28 en Sigrid
(solo lectura): 38 campos en la «Descomposicion» sincronizada con la
planificacion, 19 en la de Estudios, y el texto largo del campo 9 con saltos de
linea dentro. Los importes son inventados.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from etl_sigrid.domain.descompuestos import (
    MB,
    MOTIVO_CAMBIADA,
    MOTIVO_NUEVA,
    MOTIVO_VIGENTE,
    ORIGENES,
    POSICIONES,
    TIPO_DESCONOCIDO,
    TIPO_SIN_TIPO,
    TIPOS_ELEMENTO,
    PlanRelectura,
    Relectura,
    VersionCargada,
    VersionPendiente,
    VersionSigrid,
    cod_version_vigente,
    numero,
    planificar_relectura,
    planificar_troceado,
    tipo_elemento,
    trocear_des,
)

# ---------------------------------------------------------------------------
# Registros de ejemplo (formato real, cifras inventadas)
# ---------------------------------------------------------------------------

#: 38 campos (base 0: 0..37), como la «Descomposicion» de la 04.02 de la 0726:
#: codigo, descripcion, precio 10.5, cantidad total 3926.79, unidad M2,
#: rendimiento 1 en el 14 y el enlace a `dncpro` en el 36 a 0 (sin enlazar).
REG_38 = "~D|AS|REPERCUSION CASETONES|10.5|3926.79|M2|||||||||1||||||||||||||||||||||0|"

#: 38 campos ENLAZADO a la planificacion: campo 36 = dncpro.ide 265561, codigo
#: alternativo en el 7, naturaleza en el 11 y el 17, precio vacio (NULL).
REG_38_ENLAZADO = (
    "~D|SM370001|VERTIDO HA PILARES||234.72|M3||03.05.02||Texto largo||SB0401|0695|"
    "0695.CDSB04|1|||CARPINTERIA DE MADERA|||||||||||||||||||265561|"
)

#: 19 campos (base 0: 0..18), el formato de Estudios: tipo 8 (mano de obra).
REG_19_MO = "~D|O01OB170|OFICIAL 1A FONTANERO|17.34||H||O01OB170|||||||0.28||8||"

#: 19 campos, tipo 13 (porcentaje de medios auxiliares): el precio es la BASE y
#: el rendimiento el tanto por uno (0.02 = 2 %).
REG_19_PCT = "~D|%0200|MEDIOS AUXILIARES|12||%||%0200|||||||0.02||13||"

#: Un registro con el texto largo del campo 9 partido en varias lineas: el
#: troceado NO puede partir por cualquier salto (R13).
REG_CON_SALTOS = (
    "~D||HORM.LIMPIEZA HM-12,5|55.36|75.787|m3||04.01.01||Hormigon de limpieza:\n"
    "- Hormigon en masa\n- Fratasado liso\n~ nivelado a mano|||||1||||"
)


def _des(*registros: str) -> str:
    """Un `des` como lo guarda Sigrid: registros separados por salto de linea."""
    return "\n".join(registros) + "\n"


def _vs(obra: int, fas: int, mb: float = 0.1, filas: int = 10, huella: int | None = 7) -> VersionSigrid:
    return VersionSigrid(obra_id=obra, fase_num=fas, filas=filas, bytes=int(mb * MB), huella=huella)


def _vc(v: VersionSigrid, **cambios: object) -> VersionCargada:
    datos = {"obra_id": v.obra_id, "fase_num": v.fase_num, "filas": v.filas,
             "bytes": v.bytes, "huella": v.huella}
    datos.update(cambios)
    return VersionCargada(**datos)  # type: ignore[arg-type]


def _claves(relecturas: tuple[Relectura, ...]) -> list[tuple[int, int, str]]:
    return [(r.version.obra_id, r.version.fase_num, r.motivo) for r in relecturas]


# ===========================================================================
# R5 · que se relee y que se borra
# ===========================================================================


def test_f097_r5_las_no_cargadas_son_nuevas() -> None:
    plan = planificar_relectura([_vs(1, 0), _vs(1, 1)], [], {}, presupuesto_mb=300)
    assert _claves(plan.releer) == [(1, 0, MOTIVO_NUEVA), (1, 1, MOTIVO_NUEVA)]
    assert plan.borrar == () and plan.aplazadas == ()


def test_f097_r5_la_vigente_se_relee_aunque_su_huella_no_cambie() -> None:
    """La huella es ciega a un cambio en mitad de un `des` de mas de 16.000 bytes."""
    v = _vs(1, 3)
    plan = planificar_relectura([v, _vs(1, 2)], [_vc(v), _vc(_vs(1, 2))], {1: 3}, presupuesto_mb=300)
    assert _claves(plan.releer) == [(1, 3, MOTIVO_VIGENTE)]


@pytest.mark.parametrize("campo", ["filas", "bytes", "huella"])
def test_f097_r5_huella_distinta_se_relee(campo: str) -> None:
    """La huella de version es la terna (filas, bytes, huella): basta una."""
    v = _vs(2, 5)
    cargada = _vc(v, **{campo: (getattr(v, campo) or 0) + 1})
    plan = planificar_relectura([v], [cargada], {}, presupuesto_mb=300)
    assert _claves(plan.releer) == [(2, 5, MOTIVO_CAMBIADA)]


def test_f097_r5_huella_nula_frente_a_informada_cuenta_como_cambio() -> None:
    v = _vs(2, 5, huella=None)
    plan = planificar_relectura([v], [_vc(v, huella=11)], {}, presupuesto_mb=300)
    assert _claves(plan.releer) == [(2, 5, MOTIVO_CAMBIADA)]


def test_f097_r5_igual_y_no_vigente_no_se_relee() -> None:
    v = _vs(4, 1)
    plan = planificar_relectura([v], [_vc(v)], {4: 0}, presupuesto_mb=300)
    assert plan.releer == () and plan.aplazadas == () and plan.borrar == ()


def test_f097_r5_las_que_sigrid_ya_no_tiene_se_borran_en_orden() -> None:
    quedan = _vs(1, 0)
    plan = planificar_relectura(
        [quedan], [_vc(_vs(9, 2)), _vc(quedan), _vc(_vs(3, 7))], {}, presupuesto_mb=300
    )
    assert plan.borrar == ((3, 7), (9, 2))
    assert plan.releer == ()


def test_f097_r5_una_vigente_nueva_cuenta_como_vigente() -> None:
    plan = planificar_relectura([_vs(1, 4)], [], {1: 4}, presupuesto_mb=300)
    assert _claves(plan.releer) == [(1, 4, MOTIVO_VIGENTE)]


def test_f097_r5_la_vigente_de_otra_obra_no_cuenta() -> None:
    v = _vs(1, 4)
    plan = planificar_relectura([v], [_vc(v)], {2: 4}, presupuesto_mb=300)
    assert plan.releer == ()


def test_f097_r5_una_version_repetida_en_la_huella_no_se_planifica() -> None:
    with pytest.raises(ValueError, match="repetida"):
        planificar_relectura([_vs(1, 0), _vs(1, 0)], [], {}, presupuesto_mb=300)


def test_f097_r5_las_dataclasses_son_inmutables() -> None:
    v = _vs(1, 0)
    casos = [(v, "obra_id"), (_vc(v), "huella"), (Relectura(version=v, motivo=MOTIVO_NUEVA), "motivo"),
             (PlanRelectura(releer=(), aplazadas=(), borrar=()), "borrar"),
             (VersionPendiente(obra_id=1, fase_num=0, bytes=1, es_vigente=False), "bytes")]
    for objeto, campo in casos:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(objeto, campo, 3)
        assert not hasattr(objeto, "__dict__")


def test_f097_r5_la_clave_de_una_version_es_obra_y_fase() -> None:
    assert _vs(5, 2).clave == (5, 2)
    assert _vc(_vs(5, 2)).clave == (5, 2)


# ===========================================================================
# R6 · el tope de MB por noche
# ===========================================================================


def test_f097_r6_orden_vigentes_cambiadas_y_nuevas_por_obra_y_fase() -> None:
    cambiada = _vs(1, 1)
    sigrid = [_vs(3, 0), _vs(2, 9), cambiada, _vs(1, 0), _vs(5, 2)]
    cargadas = [_vc(cambiada, huella=99), _vc(_vs(5, 2))]
    plan = planificar_relectura(sigrid, cargadas, {5: 2, 2: 9}, presupuesto_mb=300)
    assert _claves(plan.releer) == [
        (2, 9, MOTIVO_VIGENTE), (5, 2, MOTIVO_VIGENTE),
        (1, 1, MOTIVO_CAMBIADA),
        (1, 0, MOTIVO_NUEVA), (3, 0, MOTIVO_NUEVA),
    ]


def test_f097_r6_lo_que_no_cabe_se_aplaza_y_se_corta_en_seco() -> None:
    """Corte ESTRICTO por orden: tras la primera que no cabe, todo se aplaza,
    aunque una posterior mas pequena cupiera. Asi la convergencia es por orden
    de (obra, fase) y no depende de los tamanos."""
    sigrid = [_vs(1, 0, mb=0.4), _vs(1, 1, mb=0.4), _vs(1, 2, mb=0.4), _vs(1, 3, mb=0.01)]
    plan = planificar_relectura(sigrid, [], {}, presupuesto_mb=1)
    assert [r.version.clave for r in plan.releer] == [(1, 0), (1, 1)]
    assert [r.version.clave for r in plan.aplazadas] == [(1, 2), (1, 3)]
    assert plan.bytes_releer == 2 * int(0.4 * MB)
    assert plan.bytes_aplazados == int(0.4 * MB) + int(0.01 * MB)


def test_f097_r6_el_ambito_3_consume_primero() -> None:
    """Lo que ya se ha leido esta noche (el ambito 3) se descuenta del tope."""
    sigrid = [_vs(1, 0, mb=0.4), _vs(1, 1, mb=0.4)]
    plan = planificar_relectura(sigrid, [], {}, presupuesto_mb=1, bytes_ya_usados=int(0.5 * MB))
    assert [r.version.clave for r in plan.releer] == [(1, 0)]
    assert [r.version.clave for r in plan.aplazadas] == [(1, 1)]


def test_f097_r6_justo_en_el_tope_cabe() -> None:
    sigrid = [_vs(1, 0, mb=0.5), _vs(1, 1, mb=0.5)]
    plan = planificar_relectura(sigrid, [], {}, presupuesto_mb=1)
    assert len(plan.releer) == 2 and plan.aplazadas == ()


def test_f097_r6_siempre_entra_al_menos_una_version() -> None:
    """Una version mayor que el tope entero no puede atascar la cola para siempre."""
    sigrid = [_vs(1, 0, mb=5), _vs(1, 1, mb=0.1)]
    plan = planificar_relectura(sigrid, [], {}, presupuesto_mb=1, bytes_ya_usados=2 * MB)
    assert [r.version.clave for r in plan.releer] == [(1, 0)]
    assert [r.version.clave for r in plan.aplazadas] == [(1, 1)]


def test_f097_r6_las_vigentes_tambien_se_aplazan_si_no_caben() -> None:
    sigrid = [_vs(1, 0, mb=0.6), _vs(2, 0, mb=0.6)]
    plan = planificar_relectura(sigrid, [], {1: 0, 2: 0}, presupuesto_mb=1)
    assert _claves(plan.releer) == [(1, 0, MOTIVO_VIGENTE)]
    assert _claves(plan.aplazadas) == [(2, 0, MOTIVO_VIGENTE)]


def test_f097_r6_el_borrado_no_gasta_presupuesto() -> None:
    plan = planificar_relectura([_vs(1, 0, mb=1)], [_vc(_vs(8, 8, mb=50))], {}, presupuesto_mb=1)
    assert plan.borrar == ((8, 8),)
    assert [r.version.clave for r in plan.releer] == [(1, 0)]


@pytest.mark.parametrize("presupuesto", [0, -1])
def test_f097_r6_un_tope_no_positivo_se_rechaza(presupuesto: float) -> None:
    with pytest.raises(ValueError, match="presupuesto"):
        planificar_relectura([_vs(1, 0)], [], {}, presupuesto_mb=presupuesto)


def test_f097_r6_el_mb_es_de_1024_por_1024() -> None:
    assert MB == 1024 * 1024


# ===========================================================================
# R7 · --sin-tope
# ===========================================================================


def test_f097_r7_sin_tope_lo_relee_todo() -> None:
    sigrid = [_vs(1, f, mb=100) for f in range(5)]
    plan = planificar_relectura(sigrid, [], {}, presupuesto_mb=1, sin_tope=True)
    assert len(plan.releer) == 5 and plan.aplazadas == ()


def test_f097_r7_sin_tope_no_mira_el_presupuesto() -> None:
    plan = planificar_relectura([_vs(1, 0)], [], {}, presupuesto_mb=0, sin_tope=True)
    assert len(plan.releer) == 1


# ===========================================================================
# R21 · el troceado del master, por lotes y dentro del tope
# ===========================================================================


def _vp(obra: int, fas: int, mb: float, vigente: bool = False) -> VersionPendiente:
    return VersionPendiente(obra_id=obra, fase_num=fas, bytes=int(mb * MB), es_vigente=vigente)


def test_f097_r21_troceado_vigentes_primero_y_luego_por_obra_y_fase() -> None:
    plan = planificar_troceado(
        [_vp(3, 0, 1), _vp(1, 5, 1), _vp(2, 2, 1, vigente=True), _vp(1, 0, 1)],
        presupuesto_mb=300,
    )
    assert plan.lotes == (((2, 2), (1, 0), (1, 5), (3, 0)),)
    assert plan.aplazadas == ()


def test_f097_r21_troceado_parte_en_lotes_por_mb() -> None:
    plan = planificar_troceado(
        [_vp(1, f, 40) for f in range(5)], presupuesto_mb=300, mb_por_lote=100
    )
    assert plan.lotes == (((1, 0), (1, 1)), ((1, 2), (1, 3)), ((1, 4),))


def test_f097_r21_una_version_mayor_que_el_lote_va_sola() -> None:
    plan = planificar_troceado([_vp(1, 0, 150), _vp(1, 1, 10)], presupuesto_mb=300, mb_por_lote=100)
    assert plan.lotes == (((1, 0),), ((1, 1),))


def test_f097_r21_troceado_respeta_el_tope_y_aplaza() -> None:
    plan = planificar_troceado([_vp(1, 0, 0.6), _vp(1, 1, 0.6)], presupuesto_mb=1)
    assert plan.lotes == (((1, 0),),)
    assert [p.clave for p in plan.aplazadas] == [(1, 1)]


def test_f097_r21_troceado_sin_tope_lo_trocea_todo() -> None:
    plan = planificar_troceado([_vp(1, f, 200) for f in range(3)], presupuesto_mb=1,
                               sin_tope=True, mb_por_lote=300)
    assert sum(len(lote) for lote in plan.lotes) == 3 and plan.aplazadas == ()


def test_f097_r21_troceado_sin_pendientes_no_tiene_lotes() -> None:
    plan = planificar_troceado([], presupuesto_mb=300)
    assert plan.lotes == () and plan.aplazadas == ()


def test_f097_r21_el_lote_no_positivo_se_rechaza() -> None:
    with pytest.raises(ValueError, match="lote"):
        planificar_troceado([_vp(1, 0, 1)], presupuesto_mb=300, mb_por_lote=0)


# ===========================================================================
# R13 · el troceado del `des` (espejo en Python del SQL)
# ===========================================================================


def test_f097_r13_registro_de_38_campos() -> None:
    (r,) = trocear_des(_des(REG_38))
    assert r.orden == 1
    assert r.codigo_elemento == "AS"
    assert r.descripcion == "REPERCUSION CASETONES"
    assert r.precio == Decimal("10.5")
    assert r.cantidad_total == Decimal("3926.79")
    assert r.unidad == "M2"
    assert r.rendimiento == Decimal("1")
    assert r.codigo_alternativo is None and r.naturaleza_codigo is None
    assert r.tipo_elemento_codigo is None and r.tipo_elemento == TIPO_SIN_TIPO
    assert r.dncpro_id is None and not r.es_enlazado, "campo 36 a 0: no enlazado"


def test_f097_r13_registro_enlazado_a_la_planificacion() -> None:
    (r,) = trocear_des(_des(REG_38_ENLAZADO))
    assert r.dncpro_id == 265561 and r.es_enlazado
    assert r.codigo_alternativo == "03.05.02"
    assert r.naturaleza_codigo == "SB0401"
    assert r.naturaleza == "CARPINTERIA DE MADERA"
    assert r.precio is None, "precio vacio es NULL"
    assert r.importe_unitario is None


def test_f097_r13_registro_de_19_campos_sin_enlace() -> None:
    (r,) = trocear_des(_des(REG_19_MO))
    assert (r.codigo_elemento, r.precio, r.unidad) == ("O01OB170", Decimal("17.34"), "H")
    assert r.cantidad_total is None, "campo 4 vacio"
    assert r.codigo_alternativo == "O01OB170"
    assert r.rendimiento == Decimal("0.28")
    assert (r.tipo_elemento_codigo, r.tipo_elemento) == ("8", "MANO_OBRA")
    assert r.dncpro_id is None, "19 campos: el 36 no existe"


def test_f097_r13_no_parte_por_cualquier_salto_de_linea() -> None:
    registros = trocear_des(_des(REG_38, REG_CON_SALTOS, REG_19_MO))
    assert [r.orden for r in registros] == [1, 2, 3]
    medio = registros[1]
    assert medio.codigo_elemento is None and medio.descripcion == "HORM.LIMPIEZA HM-12,5"
    assert medio.rendimiento == Decimal("1"), "el campo 14 sigue en su sitio tras el texto largo"
    assert registros[2].codigo_elemento == "O01OB170"


def test_f097_r13_retorno_de_carro_fuera() -> None:
    registros = trocear_des(REG_38 + "\r\n" + REG_19_MO + "\r\n")
    assert [r.codigo_elemento for r in registros] == ["AS", "O01OB170"]
    assert registros[1].unidad == "H"


def test_f097_r13_orden_desde_1_y_sin_basura_previa() -> None:
    registros = trocear_des("cabecera suelta\n" + _des(REG_19_MO, REG_19_PCT))
    assert [r.orden for r in registros] == [1, 2]


@pytest.mark.parametrize("des", [None, "", "\n", "texto sin registros"])
def test_f097_r13_des_vacio_no_da_registros(des: str | None) -> None:
    assert trocear_des(des) == ()


def test_f097_r13_posiciones_son_las_de_la_spec() -> None:
    assert POSICIONES == {
        "codigo_elemento": 1, "descripcion": 2, "precio": 3, "cantidad_total": 4,
        "unidad": 5, "codigo_alternativo": 7, "naturaleza_codigo": 11,
        "factor_rendimiento": 14, "tipo_elemento_codigo": 16, "naturaleza": 17,
        "dncpro_id": 36,
    }


def test_f097_r13_un_pipe_de_mas_desplaza_y_se_ve() -> None:
    """Un `|` dentro del texto largo desplaza los campos una posicion (riesgo
    del design): el rendimiento se pierde y el tipo cae en `naturaleza`. No se
    arregla —el formato no lo permite—, pero queda a la vista: sin rendimiento
    no hay importe, y el tipo no sale como MANO_OBRA."""
    desplazado = "~D|X|DESC|1||UD||||texto con | pipe|||||1||8||"
    (r,) = trocear_des(_des(desplazado))
    assert r.rendimiento is None and r.importe_unitario is None
    assert r.tipo_elemento == TIPO_SIN_TIPO and r.naturaleza == "8"
    campos = ["~D", "X", "DESC", "1", "", "UD"] + [""] * 8 + ["1", "", "ZZ", "", ""]
    assert campos[16] == "ZZ"
    (s,) = trocear_des(_des("|".join(campos)))
    assert s.tipo_elemento == TIPO_DESCONOCIDO, "un tipo que no es de la lista se ve"


# ===========================================================================
# R14 · un numero que no es numero se publica NULL
# ===========================================================================


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("10.5", Decimal("10.5")), (" 3 ", Decimal("3")), ("-0.345", Decimal("-0.345")),
     ("1e3", Decimal("1E+3")), (".5", Decimal("0.5")), ("7.", Decimal("7")),
     ("", None), (None, None), ("abc", None), ("1,5", None), ("1.2.3", None), ("--1", None),
     ("1e9999", None)],
)
def test_f097_r14_numero(texto: str | None, esperado: Decimal | None) -> None:
    assert numero(texto) == esperado


def test_f097_r14_precio_basura_no_rompe_el_troceado() -> None:
    (r,) = trocear_des(_des("~D|X|DESC|n/a|3|UD|||||||||1||10||"))
    assert r.precio is None and r.importe_unitario is None and r.importe_total is None
    assert r.cantidad_total == Decimal("3")


def test_f097_r14_enlace_no_numerico_o_cero_no_enlaza() -> None:
    campos = ["~D", "X"] + [""] * 34 + ["abc", ""]
    (r,) = trocear_des(_des("|".join(campos)))
    assert r.dncpro_id is None


# ===========================================================================
# R19 · importes, tipo y porcentajes
# ===========================================================================


def test_f097_r19_importes_redondeados_a_dos() -> None:
    (r,) = trocear_des(_des(REG_19_MO))
    assert r.importe_unitario == Decimal("4.86"), "17.34 x 0.28 = 4.8552"
    (s,) = trocear_des(_des(REG_38))
    assert s.importe_total == Decimal("41231.30"), "3926.79 x 10.5 = 41231.295"


def test_f097_r19_porcentaje_con_su_base() -> None:
    (r,) = trocear_des(_des(REG_19_PCT))
    assert r.es_porcentaje and r.tipo_elemento == "MEDIOS_AUXILIARES"
    assert r.porcentaje == Decimal("2.00") and r.base_porcentaje == Decimal("12")
    assert r.importe_unitario == Decimal("0.24")


def test_f097_r19_lo_que_no_es_porcentaje_no_lleva_base() -> None:
    (r,) = trocear_des(_des(REG_19_MO))
    assert not r.es_porcentaje and r.porcentaje is None and r.base_porcentaje is None


@pytest.mark.parametrize(
    ("codigo", "tipo"),
    [("8", "MANO_OBRA"), ("9", "MAQUINARIA"), ("10", "MATERIAL"), ("11", "SUBCONTRATA"),
     ("3", "OTROS"), ("4", "PORCENTAJE"), ("13", "MEDIOS_AUXILIARES"),
     (None, TIPO_SIN_TIPO), ("", TIPO_SIN_TIPO), ("7", TIPO_DESCONOCIDO), ("x", TIPO_DESCONOCIDO)],
)
def test_f097_r19_tipo_de_elemento(codigo: str | None, tipo: str) -> None:
    assert tipo_elemento(codigo) == tipo


def test_f097_r19_el_diccionario_de_tipos_es_el_de_d8() -> None:
    assert TIPOS_ELEMENTO == {
        "8": "MANO_OBRA", "9": "MAQUINARIA", "10": "MATERIAL", "11": "SUBCONTRATA",
        "3": "OTROS", "4": "PORCENTAJE", "13": "MEDIOS_AUXILIARES",
    }


def test_f097_r12_los_cinco_origenes() -> None:
    """F-123: el master 0 es Estudios y se llama MASTER_ESTUDIO (antes MASTER_INICIAL)."""
    assert ORIGENES == ("ESTUDIO", "PLANIF_JO", "MASTER_ESTUDIO", "MASTER_PRE_ABC", "MASTER_PLANIF_JO")


def test_f097_r17_cod_de_la_vigente_desde_business_rules() -> None:
    reglas = {"sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}}}
    assert cod_version_vigente(reglas) == "15"


@pytest.mark.parametrize("cod", ["15'; DROP", "", "1 5", None])
def test_f097_r17_cod_de_la_vigente_solo_digitos(cod: object) -> None:
    """El cod viaja como literal a un SQL compuesto: nada que no sean digitos."""
    reglas = {"sigrid": {"campos_extendidos": {"cod_version_master_vigente": cod}}}
    with pytest.raises(ValueError, match="cod"):
        cod_version_vigente(reglas)


# ===========================================================================
# Los cuatro supervivientes de la campana de mutacion (progress/mutacion_F-097.md)
# ===========================================================================


@pytest.mark.parametrize("n_campos", [15, 16, 17, 18])
def test_f097_r13_registro_cortado_justo_en_una_posicion(n_campos: int) -> None:
    """Un registro con EXACTAMENTE tantos campos como la posicion que se pide
    (17 campos: el 17 no existe) es NULL, no un `IndexError` que tumbe el build.
    Mata `posicion >= len(campos)` -> `>`."""
    campos = ["~D", "X", "DESC", "2", "", "UD"] + [""] * 8 + ["0.5", "", "8", "NAT"]
    (r,) = trocear_des(_des("|".join(campos[:n_campos])))
    assert r.codigo_elemento == "X"
    assert r.naturaleza == ("NAT" if n_campos > 17 else None)
    assert r.tipo_elemento_codigo == ("8" if n_campos > 16 else None)
    assert r.rendimiento == (Decimal("0.5") if n_campos > 14 else None)


@pytest.mark.parametrize(("n_campos", "enlace"), [(36, None), (37, 99)])
def test_f097_r13_registro_de_36_campos_no_tiene_enlace(n_campos: int, enlace: int | None) -> None:
    """36 campos (0..35): el 36 no existe y el registro no esta enlazado; con 37
    si. Mata `len(campos) > 36` -> `>=`."""
    campos = ["~D", "X"] + [""] * 34 + ["99"]
    (r,) = trocear_des(_des("|".join(campos[:n_campos])))
    assert r.dncpro_id == enlace


def test_f097_r21_un_lote_de_menos_de_un_mb_vale() -> None:
    """Mata `mb_por_lote <= 0` -> `<= 1`: medio MB es un lote legitimo."""
    plan = planificar_troceado([_vp(1, 0, 0.3), _vp(1, 1, 0.3)], presupuesto_mb=300, mb_por_lote=0.5)
    assert plan.lotes == (((1, 0),), ((1, 1),))


def test_f097_r21_el_tope_del_troceado_se_valida_solo_con_tope() -> None:
    """Mata `not sin_tope and presupuesto <= 0` -> `sin_tope and ...`: sin tope
    el presupuesto no se mira; con tope, uno no positivo se rechaza."""
    with pytest.raises(ValueError, match="presupuesto"):
        planificar_troceado([_vp(1, 0, 1)], presupuesto_mb=0)
    plan = planificar_troceado([_vp(1, 0, 1)], presupuesto_mb=0, sin_tope=True)
    assert plan.lotes == (((1, 0),),)


# ===========================================================================
# Review 1, cambio 1 · un numero fuera de rango no tumba el build
# ===========================================================================


@pytest.mark.parametrize("precio", ["1e300", "12345678901234567", "-99999999999999999"])
def test_f097_r14_importe_fuera_de_rango_es_null_sin_excepcion(precio: str) -> None:
    """`importe_unitario` e `importe_total` son NUMERIC(18,2) en la tabla: lo que
    no cabe (|x| >= 1e16 tras redondear) es NULL, en SQL y en el espejo, y el
    registro se publica igual con su precio."""
    (r,) = trocear_des(_des(f"~D|X|DESC|{precio}|1|UD|||||||||1||10||"))
    assert r.precio == Decimal(precio)
    assert r.importe_unitario is None and r.importe_total is None


def test_f097_r14_el_limite_del_importe_es_1e16_tras_redondear() -> None:
    """16 cifras enteras caben; lo que al redondear llega a 1e16, no."""
    (cabe,) = trocear_des(_des("~D|X|D|9999999999999999.99|||||||||||1||||"))
    assert cabe.importe_unitario == Decimal("9999999999999999.99")
    (no_cabe,) = trocear_des(_des("~D|X|D|9999999999999999.995|||||||||||1||||"))
    assert no_cabe.importe_unitario is None


# ===========================================================================
# Review 1, cambio 2 · un salto de linea pegado a un numero no lo hace numero
# ===========================================================================


def test_f097_r14_numero_seguido_de_salto_de_linea_es_null() -> None:
    """En PostgreSQL `$` es fin de cadena; en Python `re.match` con `$` casaba
    antes de un `\n` final. Con `fullmatch` el espejo dice lo mismo que el SQL."""
    assert numero("12\n") is None
    campos = ["~D", "X", "DESC", "12\n", "3", "UD"] + [""] * 30 + ["55\n", ""]
    (r,) = trocear_des(_des("|".join(campos)))
    assert r.precio is None and r.cantidad_total == Decimal("3")
    assert r.dncpro_id is None, "un enlace `55\n` no enlaza, como en fn_trocear"
    assert r.codigo_elemento == "X"


def test_f097_r17_cod_de_la_vigente_con_salto_de_linea_se_rechaza() -> None:
    reglas = {"sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15\n"}}}
    with pytest.raises(ValueError, match="cod"):
        cod_version_vigente(reglas)


def test_f097_r21_dos_pendientes_que_llenan_el_lote_justo_van_juntas() -> None:
    """Review 2, superviviente S1 (`> limite` -> `>=`): un lote que llega
    EXACTAMENTE a `mb_por_lote` no se parte en dos."""
    plan = planificar_troceado([_vp(1, 0, 0.5), _vp(1, 1, 0.5)], presupuesto_mb=300, mb_por_lote=1)
    assert plan.lotes == (((1, 0), (1, 1)),)
