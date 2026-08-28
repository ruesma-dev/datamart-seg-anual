# tests/test_f047_guardian.py
"""
F-047 · El guardián: lo que el REPOSITORIO declara, contrastado contra la base.

Por qué hacía falta otro contraste habiendo ya dos. Los dos que existían miran
otra cosa:

* la puerta de `init.sh` compara **el SQL del repositorio contra las fichas**
  del diccionario. Es offline y no sabe nada de la base;
* `check-diccionario` compara **las fichas contra la base**. Ve que una ficha
  no tenga objeto, pero solo de lo que está fichado.

Por el hueco entre las dos se coló F-047 durante semanas: la nocturna
**destruía** `cierre.v_pbi_planif_vs_real` y nadie se enteraba, porque ninguna
de las dos comprueba *«lo que el SQL del repositorio dice que crea, ¿existe?»*.
Eso es lo que hace `evaluar_construccion`, y `run-all` lo ejecuta al terminar.

EL PATRÓN ES EL QUE YA USA EL DICCIONARIO, no uno nuevo: **objeto construido o
pendiente declarado**, con la lista en un fichero versionado y un trinquete que
solo baja. El cierre no está terminado (F-017, F-018), así que puede haber
objetos legítimamente sin construir; aplazarlos es válido, ignorarlos no.

Ningún test abre red ni BBDD: el catálogo se pasa como filas.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.inventario import ObjetoPublicado
from etl_sigrid.infrastructure.postgres.catalogo import (
    EvaluacionConstruccion,
    evaluar_construccion,
    formatear_construccion,
)


def _declarado(nombre: str, tipo: str = "vista", origen: str = "cierre/06.sql"):
    esquema, objeto = nombre.split(".")
    return ObjetoPublicado(esquema=esquema, objeto=objeto, tipo=tipo, origen=origen)


def _en_base(*nombres: str, tipo: str = "VIEW"):
    return [(n.split(".")[0], n.split(".")[1], tipo) for n in nombres]


# ---------------------------------------------------------------------------
# R5 · lo declarado y no construido rompe la puerta
# ---------------------------------------------------------------------------


def test_f047_r5_lo_declarado_y_no_construido_rompe_la_puerta() -> None:
    """EL CASO DE F-047, reproducido: el SQL la crea y la base no la tiene."""
    informe = evaluar_construccion(
        [
            _declarado("cierre.v_pbi_planif_vs_real"),
            _declarado("cierre.v_pbi_cierre_resumen"),
        ],
        _en_base("cierre.v_pbi_cierre_resumen"),
        (),
    )

    assert not informe.ok
    assert [o.nombre for o in informe.no_construidos] == ["cierre.v_pbi_planif_vs_real"]


def test_f047_r5_todo_construido_es_verde() -> None:
    informe = evaluar_construccion(
        [_declarado("cierre.v_pbi_cierre_resumen")],
        _en_base("cierre.v_pbi_cierre_resumen"),
        (),
    )

    assert informe.ok
    assert informe.no_construidos == ()
    assert (informe.declarados, informe.construidos) == (1, 1)


def test_f047_r5_lo_que_la_base_tiene_de_mas_no_es_asunto_de_esta_puerta() -> None:
    """LÍMITE DECLARADO, y es deliberado.

    Un objeto en la base que el repositorio ya no crea es un hallazgo real, pero
    lo denuncia `check-diccionario` como `PUBLICADO Y SIN FICHA`. Repetirlo aquí
    daría dos alarmas por el mismo hecho y, peor, obligaría a esta puerta a
    opinar sobre objetos que no salen de `sql/**` —los que crea otra
    herramienta— con la única información de que existen.
    """
    informe = evaluar_construccion(
        [_declarado("cierre.v_pbi_cierre_resumen")],
        _en_base("cierre.v_pbi_cierre_resumen", "cierre.v_de_alguien_a_mano"),
        (),
    )

    assert informe.ok


def test_f047_r5_un_tipo_que_no_casa_tambien_rompe() -> None:
    """El SQL dice tabla y la base tiene una vista: el build no hizo lo que el
    repositorio declara, aunque el nombre esté ocupado."""
    informe = evaluar_construccion(
        [_declarado("cierre.fact_cierre_mensual", tipo="tabla")],
        _en_base("cierre.fact_cierre_mensual", tipo="VIEW"),
        (),
    )

    assert not informe.ok
    assert informe.tipos_distintos == (
        ("cierre.fact_cierre_mensual", "tabla", "vista"),
    )


def test_f047_r5_el_tipo_del_catalogo_se_normaliza() -> None:
    """`information_schema` habla en inglés y en mayúsculas; el inventario, no.

    Sin esto TODA tabla saldría como tipo que no casa, que es la forma más
    ruidosa posible de romper una puerta nueva.
    """
    informe = evaluar_construccion(
        [_declarado("stg.obras", tipo="tabla")],
        _en_base("stg.obras", tipo="BASE TABLE"),
        (),
    )

    assert informe.ok


# ---------------------------------------------------------------------------
# R6 · el trinquete: pendiente declarado, y solo baja
# ---------------------------------------------------------------------------


def test_f047_r6_un_pendiente_declarado_se_tolera() -> None:
    """El cierre no está terminado (F-017, F-018): aplazar es legítimo."""
    informe = evaluar_construccion(
        [_declarado("cierre.v_futura")],
        _en_base(),
        ("cierre.v_futura",),
    )

    assert informe.ok
    assert informe.pendientes_declarados == ("cierre.v_futura",)


def test_f047_r6_un_pendiente_ya_construido_rompe_la_puerta() -> None:
    """El trinquete SOLO BAJA: dejarlo en la lista una vez construido la falsea,
    y con ella deja de protegerse ese objeto para siempre."""
    informe = evaluar_construccion(
        [_declarado("cierre.v_futura")],
        _en_base("cierre.v_futura"),
        ("cierre.v_futura",),
    )

    assert not informe.ok
    assert informe.pendientes_ya_construidos == ("cierre.v_futura",)


def test_f047_r6_un_pendiente_que_el_repositorio_no_declara_rompe_la_puerta() -> None:
    """Un pendiente fantasma infla el trinquete sin aplazar nada real."""
    informe = evaluar_construccion(
        [_declarado("cierre.v_pbi_cierre_resumen")],
        _en_base("cierre.v_pbi_cierre_resumen"),
        ("cierre.v_que_nadie_crea",),
    )

    assert not informe.ok
    assert informe.pendientes_fantasma == ("cierre.v_que_nadie_crea",)


# ---------------------------------------------------------------------------
# El informe, que es lo único que verá quien se lo encuentre en rojo
# ---------------------------------------------------------------------------


def _informe_con_todo() -> EvaluacionConstruccion:
    return evaluar_construccion(
        [
            _declarado("cierre.v_pbi_planif_vs_real", origen="cierre/06_views.sql"),
            _declarado("cierre.fact_cierre_mensual", tipo="tabla"),
            _declarado("cierre.v_futura"),
        ],
        _en_base("cierre.fact_cierre_mensual", tipo="VIEW") + _en_base("cierre.v_futura"),
        ("cierre.v_futura", "cierre.v_que_nadie_crea"),
    )


def test_f047_r7_el_informe_nombra_el_objeto_su_fichero_y_que_hacer() -> None:
    texto = formatear_construccion(_informe_con_todo())

    assert "KO" in texto
    assert "cierre.v_pbi_planif_vs_real" in texto
    assert "cierre/06_views.sql" in texto, "no dice qué SQL hay que mirar"
    assert "cierre.fact_cierre_mensual" in texto
    assert "cierre.v_que_nadie_crea" in texto
    assert "trinquete" in texto


def test_f047_r7_un_informe_limpio_lo_dice_y_cuenta_lo_comprobado() -> None:
    informe = evaluar_construccion(
        [_declarado("cierre.v_pbi_cierre_resumen")],
        _en_base("cierre.v_pbi_cierre_resumen"),
        (),
    )

    texto = formatear_construccion(informe)

    assert "OK" in texto
    assert "1" in texto


def test_f047_r7_verde_con_pendientes_lo_dice_con_la_cuenta_a_la_vista() -> None:
    """Aplazar tiene que poder verse verde, pero no en silencio."""
    informe = evaluar_construccion(
        [_declarado("cierre.v_futura")], _en_base(), ("cierre.v_futura",)
    )

    texto = formatear_construccion(informe)

    assert informe.ok
    assert "pendiente" in texto
    assert "1" in texto


def test_f047_r7_el_informe_es_determinista() -> None:
    """Un incidente que se repite tiene que producir el mismo texto."""
    declarados = [
        _declarado("cierre.v_una"),
        _declarado("compras.v_otra"),
        _declarado("mart.v_tercera"),
    ]

    uno = evaluar_construccion(declarados, _en_base(), ())
    dos = evaluar_construccion(list(reversed(declarados)), _en_base(), ())

    assert formatear_construccion(uno) == formatear_construccion(dos)


def test_f047_r7_la_evaluacion_es_inmutable() -> None:
    from dataclasses import FrozenInstanceError

    informe = evaluar_construccion([_declarado("cierre.v_una")], _en_base(), ())

    assert isinstance(informe, EvaluacionConstruccion)
    with pytest.raises(FrozenInstanceError):
        informe.no_construidos = ()  # type: ignore[misc]
