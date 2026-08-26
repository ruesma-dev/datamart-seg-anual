# tests/test_f006_supervivientes_logica.py
"""
Los doce supervivientes de LÓGICA de la campaña de mutación de F-006.

La primera campaña válida de la feature cerró con **256 mutantes, 204 muertos,
52 supervivientes, 0 timeouts** (`progress/mutacion_F-006.md`). El nivel de
rigor de F-006 es `critico`, y `critico` exige cero: un superviviente es una
línea que se puede cambiar sin que ningún test se entere, o sea una línea cuyo
comportamiento nadie ha fijado.

Los doce de aquí son **defectos reales de cobertura**, no mutantes
equivalentes, y ninguno es un detalle cosmético:

* **El mapeo por índice de `resumen_publicacion`** (`fila[1] → fila[2]`). Lo que
  el CLI imprime y lo que queda en `_meta.etl_runs.metadata` tras publicar. Un
  índice corrido publica el hash como si fuera la versión y nadie lo nota hasta
  que alguien compara entornos.
* **`ficha.motivo_no_consumo or None` y `ficha.grano or None`** en las filas que
  se publican. Con `and`, los dos viajan SIEMPRE vacíos: el agente que lee el
  diccionario por SQL pierde el grano de cada objeto y el motivo por el que un
  objeto está fuera de la superficie de consumo. Es exactamente la información
  que F-006 existe para servir.
* **El formateo del contexto** (`bloque == "ejes"` / `== "esquemas"`). Es el
  texto que el MCP inyecta tal cual en el prompt.
* **La guarda de `_es_unica_por`** (`not clave and not columnas`), con sus TRES
  mutaciones vivas. Decide si una relación `1:1`/`N:1` se juzga o se aplaza. Si
  se aplaza cuando debía juzgarse, vuelve el fan-out que duplicaba importes en
  silencio; si se juzga cuando no se puede saber, las fichas de `raw` —que no
  documentan columnas— se llenan de errores falsos.
* **A quién comprueba la puerta de unicidad** (`tipo == "funcion" or not
  clave_negocio`). Con `and` entrarían fichas sin clave de negocio, y la
  consulta saldría con un `GROUP BY` vacío.
* **Por qué un objeto se declara saltado** (`solo_consumo and not
  consumo_recomendado`), con dos mutaciones vivas. Un informe que da un motivo
  que no es el real ya engañó dos veces en esta feature.
* **El mensaje «Cobertura del diccionario: OK»** que el humano lee en cada
  `bash harness/init.sh`. Confirmado superviviente dos veces.

Cada test fija el COMPORTAMIENTO observable, no repite la línea de código: los
cuatro cuadrantes de la guarda se ejercitan a través de `validar`, y el mapeo
por índice con una tupla en la que ningún índice vale por otro.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from etl_sigrid.domain.diccionario import (
    Columna,
    Diccionario,
    Ficha,
    Relacion,
    validar,
)
from etl_sigrid.domain.inventario import InformeCobertura, ObjetoPublicado, formatear_cobertura
from etl_sigrid.infrastructure.postgres.diccionario_sql import (
    fila_publicacion,
    filas_contexto,
    filas_diccionario,
    resumen_publicacion,
)
from etl_sigrid.infrastructure.postgres.unicidad_sql import (
    consultas_de_unicidad,
    objetos_saltados,
)

#: Posición de cada dato dentro de la tupla que devuelve `filas_diccionario`.
#: Va con nombre porque el test comprueba precisamente eso: que el valor esté
#: en su sitio. Un `fila[7]` suelto no diría contra qué se está comparando.
COL_MOTIVO_NO_CONSUMO = 5
COL_GRANO = 7

PASOS_NOCTURNOS = ("build_mart",)


def _ficha(**kwargs) -> Ficha:
    """Una ficha válida por defecto; cada test cambia solo lo que le importa."""
    base = dict(
        esquema="mart",
        objeto="ejemplo",
        tipo="tabla",
        capa="consumo",
        consumo_recomendado=True,
        descripcion="D" * 60,
        grano="Una fila por obra y mes, que es su clave.",
        clave_negocio=("obra_id", "anio_mes"),
        paso_etl="build_mart",
        refresco="nocturno",
        columnas=(
            Columna(nombre="obra_id", significado="S" * 40),
            Columna(nombre="anio_mes", significado="S" * 40),
        ),
        relaciones=(),
        ejemplos_preguntas=("Cuanto llevamos gastado en la obra X",),
    )
    base.update(kwargs)
    return Ficha(**base)


def _diccionario_con(*fichas: Ficha, **kwargs) -> Diccionario:
    base = dict(
        version="1",
        base="sigrid_dm",
        fichas=fichas,
        reglas=(),
        esquemas={},
        pendientes=(),
        global_raw={},
    )
    base.update(kwargs)
    return Diccionario(**base)


# ---------------------------------------------------------------------------
# 1 · `resumen_publicacion` lee cada dato de SU índice
# ---------------------------------------------------------------------------


def test_f006_t28_el_resumen_de_publicacion_no_cruza_ningun_campo() -> None:
    """Ningún valor de la tupla puede pasar por otro, así que un índice corrido
    se ve.

    Es lo que el CLI imprime al publicar y lo que queda en
    `_meta.etl_runs.metadata`. Con `version` leyendo el índice del hash, el
    informe de publicación diría que la versión del diccionario es un SHA-256, y
    la pregunta «¿lo publicado es lo del repositorio?» se responde comparando
    justo esos dos campos.
    """
    fila = (
        1,
        "version-en-el-1",
        "hash-en-el-2",
        "instante-en-el-3",
        "batch-en-el-4",
        50,
        60,
        70,
        80.5,
    )

    assert resumen_publicacion(fila) == {
        "version": "version-en-el-1",
        "hash_fuente": "hash-en-el-2",
        "n_objetos": 50,
        "n_reglas": 60,
        "n_columnas": 70,
        "cobertura_cols": 80.5,
    }


def test_f006_t28_el_resumen_describe_la_fila_que_de_verdad_se_publica() -> None:
    """El mapeo se comprueba contra `fila_publicacion`, no contra una tupla
    inventada.

    Sin este segundo test, `resumen_publicacion` podría ser internamente
    coherente y estar leyendo posiciones que la fila real no tiene ahí. Los tres
    recuentos se eligen DISTINTOS entre sí (2 fichas, 3 reglas, 5 columnas) para
    que cruzarlos se note.
    """
    dicc = _diccionario_con(
        _ficha(
            objeto="uno",
            columnas=(
                Columna(nombre="a", significado="S" * 40),
                Columna(nombre="b", significado="S" * 40),
                Columna(nombre="c", significado="S" * 40),
            ),
        ),
        _ficha(
            objeto="dos",
            columnas=(
                Columna(nombre="d", significado="S" * 40),
                Columna(nombre="e", significado="S" * 40),
            ),
        ),
        version="v-2026-08-26",
        reglas=(),
    )
    fila = fila_publicacion(
        dicc,
        hash_fuente="a" * 64,
        ahora=datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc),
        batch_id="lote-1",
        informe=InformeCobertura(),
    )

    resumen = resumen_publicacion(fila)

    assert resumen["version"] == "v-2026-08-26"
    assert resumen["hash_fuente"] == "a" * 64
    assert resumen["n_objetos"] == 2
    assert resumen["n_columnas"] == 5
    assert resumen["cobertura_cols"] == 100.0


# ---------------------------------------------------------------------------
# 2 y 3 · `motivo_no_consumo` y `grano` viajan a la fila publicada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("campo", "indice"),
    [
        ("motivo_no_consumo", COL_MOTIVO_NO_CONSUMO),
        ("grano", COL_GRANO),
    ],
)
def test_f006_r22_el_texto_presente_llega_a_la_fila_publicada(
    campo: str, indice: int
) -> None:
    """Lo que la ficha dice es lo que se publica, no un `NULL`.

    `grano` es «qué es una fila» y `motivo_no_consumo` es «por qué no mires
    aquí»: las dos las lee el agente por SQL desde `_meta`, y las dos viajan
    vacías si el `or None` se vuelve `and None`. Publicar el diccionario entero
    con el grano en blanco es publicar un diccionario que no responde a la
    primera pregunta que se le hace.
    """
    texto = f"Texto real de `{campo}` que tiene que llegar entero a _meta."
    (fila,) = filas_diccionario(_diccionario_con(_ficha(**{campo: texto})))

    assert fila[indice] == texto


@pytest.mark.parametrize(
    ("campo", "indice"),
    [
        ("motivo_no_consumo", COL_MOTIVO_NO_CONSUMO),
        ("grano", COL_GRANO),
    ],
)
def test_f006_r22_el_texto_vacio_se_publica_como_null(campo: str, indice: int) -> None:
    """La otra mitad del `or None`: vacío no es cadena vacía, es `NULL`.

    En SQL no es lo mismo: `WHERE grano IS NULL` encuentra lo que no está
    documentado; `WHERE grano = ''` no lo encuentra si alguien publicó una
    cadena vacía. La columna tiene que decir «no hay dato», no «el dato es la
    nada».
    """
    (fila,) = filas_diccionario(_diccionario_con(_ficha(**{campo: ""})))

    assert fila[indice] is None


# ---------------------------------------------------------------------------
# 4 y 5 · el contexto que se inyecta en el prompt, con el formato de su bloque
# ---------------------------------------------------------------------------


def _texto_del_contexto(dicc: Diccionario) -> dict[tuple[str, str], str]:
    """`(bloque, clave) -> texto` de lo que `filas_contexto` publica."""
    return {(f[0], f[1]): f[3] for f in filas_contexto(dicc)}


def test_f006_r28_cada_bloque_del_contexto_se_formatea_con_SU_plantilla() -> None:
    """`ejes` y `esquemas` tienen forma propia, y no es intercambiable.

    De `ejes` lo que importa son los **literales exactos** que el agente va a
    poner en un `WHERE`: si no salen enumerados, se los inventa y la consulta
    devuelve cero filas sin error. De `esquemas` importa el par «título — para
    qué sirve», que es lo que orienta antes de elegir dónde mirar.

    Se comprueban los DOS en el mismo test a propósito: cambiar cualquiera de
    los dos `==` por `!=` hace que un bloque se renderice con la plantilla del
    otro o con el volcado genérico `clave: valor`, y solo mirando los dos a la
    vez se ve que cada uno conserva la suya.
    """
    dicc = _diccionario_con(
        global_raw={
            "ejes": [
                {
                    "eje": "escenario",
                    "valores": ["CosteReal", "CostePrevisto"],
                    "significa": "Que version del coste se esta mirando.",
                }
            ],
            "esquemas": {
                "mart": {
                    "titulo": "Seguimiento anual",
                    "para_que_sirve": "Responder por obra y mes.",
                }
            },
        }
    )

    textos = _texto_del_contexto(dicc)

    assert textos[("ejes", "escenario")] == (
        "escenario: CosteReal, CostePrevisto. Que version del coste se esta mirando."
    )
    assert textos[("esquemas", "mart")] == (
        "mart — Seguimiento anual: Responder por obra y mes."
    )


def test_f006_r28_un_bloque_sin_plantilla_propia_se_vuelca_entero() -> None:
    """La rama por defecto: nada se pierde por no tener plantilla.

    Fija que el `else` genérico existe y qué produce. Sin este test, mover
    `esquemas` a esa rama (el mutante `!=`) no rompería nada: no habría ningún
    caso que enseñara en qué se diferencian las dos salidas.
    """
    dicc = _diccionario_con(
        global_raw={
            "convenciones": {
                "moneda": {"valor": "EUR", "nota": "sin IVA en compras"},
            }
        }
    )

    textos = _texto_del_contexto(dicc)

    assert textos[("convenciones", "moneda")] == "valor: EUR; nota: sin IVA en compras"


# ---------------------------------------------------------------------------
# 6, 7 y 8 · la guarda de `_es_unica_por`, en sus cuatro cuadrantes
# ---------------------------------------------------------------------------
#
# `_es_unica_por` devuelve `None` —«no se puede saber»— SOLO cuando la ficha no
# declara ni clave de negocio ni columnas, que es el caso de `raw`. En los otros
# tres cuadrantes hay con qué juzgar, así que se juzga. Se ejercita a través de
# `validar`, que es donde ese `None` se convierte en «aplazo el veredicto» y ese
# `False` en «esta cardinalidad promete una unicidad que no existe».


def _errores_de_fanout(destino: Ficha) -> list[str]:
    """Errores de cardinalidad que `validar` levanta contra `mart.destino`."""
    origen = _ficha(
        objeto="origen",
        clave_negocio=("obra_id",),
        relaciones=(
            Relacion(
                de="obra_id",
                a="mart.destino.obra_id",
                cardinalidad="N:1",
                porque="Cada fila de origen pertenece a una obra del destino.",
            ),
        ),
    )
    errores = validar(_diccionario_con(origen, destino), PASOS_NOCTURNOS)
    return [e.detalle for e in errores if "promete una unicidad que no existe" in e.detalle]


CUADRANTES = {
    # (clave_negocio, columnas) -> ¿se puede juzgar y sale mal?
    "con_clave_y_con_columnas": (
        ("obra_id", "anio_mes"),
        (Columna(nombre="obra_id", significado="S" * 40),),
        True,
    ),
    "con_clave_y_sin_columnas": (
        ("obra_id", "anio_mes"),
        (),
        True,
    ),
    "sin_clave_y_con_columnas": (
        (),
        (Columna(nombre="obra_id", significado="S" * 40),),
        True,
    ),
    "sin_clave_y_sin_columnas": (
        (),
        (),
        False,
    ),
}


@pytest.mark.parametrize(
    ("clave", "columnas", "se_denuncia"),
    list(CUADRANTES.values()),
    ids=list(CUADRANTES),
)
def test_f006_r5_el_fanout_solo_se_aplaza_cuando_no_hay_NADA_con_que_juzgarlo(
    clave: tuple[str, ...], columnas: tuple[Columna, ...], se_denuncia: bool
) -> None:
    """Los cuatro cuadrantes de la guarda, y por qué el borde importa.

    Un `N:1` promete que el destino tiene UNA fila por esa columna. Si el
    destino declara una clave compuesta, la promesa es falsa y el JOIN duplica
    importes en silencio — el incidente concreto que originó esta comprobación:
    seis relaciones publicadas como `N:1` sobre `obra_id` contra objetos con
    muchas filas por obra.

    El único cuadrante en el que el veredicto se aplaza es el de las fichas de
    `raw`: sin clave declarada y sin columnas documentadas (van a nivel de
    objeto, DA-2) no hay con qué decidir, e inventarse un «está mal» llenaría el
    informe de errores falsos que nadie podría arreglar.

    Ampliar la guarda (`or`, o quitar cualquiera de los dos `not`) hace que se
    aplacen juicios que sí se podían emitir; estrecharla hace que `raw` se
    denuncie sin motivo. Los cuatro casos, juntos, no dejan sitio a ninguna de
    las dos.
    """
    destino = _ficha(objeto="destino", clave_negocio=clave, columnas=columnas)

    denuncias = _errores_de_fanout(destino)

    if se_denuncia:
        assert denuncias, (
            "con clave declarada o con columnas documentadas SÍ se puede juzgar "
            "la unicidad del destino, y aquí no la tiene: el `N:1` tenía que "
            "denunciarse"
        )
        assert "`mart.destino` tiene varias filas por `obra_id`" in denuncias[0]
    else:
        assert denuncias == [], (
            "sin clave de negocio y sin columnas —las fichas de `raw`— no hay "
            "con qué juzgar: el veredicto se aplaza, no se inventa"
        )


# ---------------------------------------------------------------------------
# 9 · a quién comprueba la puerta de unicidad
# ---------------------------------------------------------------------------


def test_f006_t26_sin_clave_de_negocio_no_hay_consulta_de_unicidad() -> None:
    """No hay nada que agrupar, así que no se pregunta.

    Con la condición en `and`, esta ficha entraría en el bucle y `columnas`
    saldría cadena vacía: la consulta generada sería un `SELECT , count(*) …
    GROUP BY` que el motor rechaza. La puerta pasaría de comprobar a explotar.
    """
    dicc = _diccionario_con(_ficha(objeto="sin_clave", clave_negocio=()))

    assert consultas_de_unicidad(dicc) == []


def test_f006_t26_una_funcion_no_genera_consulta_de_unicidad() -> None:
    """Una función no tiene filas que agrupar por mucha clave que declare.

    Es la otra mitad del `or`: con `and`, una función con `clave_negocio` sí
    entraría, y se lanzaría un `GROUP BY` contra algo que no es una relación.
    """
    dicc = _diccionario_con(_ficha(objeto="f_algo", tipo="funcion"))

    assert consultas_de_unicidad(dicc) == []


def test_f006_t26_una_tabla_con_clave_si_genera_su_consulta() -> None:
    """El caso positivo, para que los dos anteriores signifiquen algo.

    Sin él, «no genera consulta» se cumpliría también con una puerta que no
    comprueba nada.
    """
    dicc = _diccionario_con(_ficha(objeto="con_clave"))

    (consulta,) = consultas_de_unicidad(dicc)
    assert consulta.objeto == "mart.con_clave"
    assert "GROUP BY obra_id, anio_mes" in consulta.sql


# ---------------------------------------------------------------------------
# 10 y 11 · por qué un objeto se declara saltado
# ---------------------------------------------------------------------------


def test_f006_t26_fuera_de_la_superficie_de_consumo_se_salta_diciendolo() -> None:
    """El motivo tiene que ser el real, y decir cómo forzarlo.

    Un informe que dice «todo correcto» sin decir sobre qué corrió invita a
    creer que cubrió más de lo que cubrió. Ya pasó dos veces en esta feature.
    """
    dicc = _diccionario_con(_ficha(objeto="interna", consumo_recomendado=False))

    assert objetos_saltados(dicc) == [
        ("mart.interna", "fuera de la superficie de consumo (usa `--todos`)")
    ]


def test_f006_t26_dentro_de_la_superficie_de_consumo_no_se_salta_nada() -> None:
    """Lo que sí se va a comprobar no puede aparecer como saltado.

    Con el `and` vuelto `or`, un objeto recomendado para consumo se declararía
    saltado «fuera de la superficie de consumo» y a la vez se le lanzaría la
    consulta: el informe diría lo contrario de lo que hizo.
    """
    dicc = _diccionario_con(_ficha(objeto="publica", consumo_recomendado=True))

    assert objetos_saltados(dicc) == []


def test_f006_t26_con_todos_deja_de_haber_objetos_saltados_por_consumo() -> None:
    """`--todos` es la pasada completa: ese motivo desaparece.

    Es lo que fija que `solo_consumo` mande de verdad. Si la condición ignorase
    el flag, `--todos` seguiría saltándose media base y el humano creería haber
    hecho la pasada completa.
    """
    dicc = _diccionario_con(_ficha(objeto="interna", consumo_recomendado=False))

    assert objetos_saltados(dicc, solo_consumo=False) == []


# ---------------------------------------------------------------------------
# 12 · el mensaje de cobertura que el humano lee en cada `init.sh`
# ---------------------------------------------------------------------------

LINEA_LIMPIA = "Cobertura del diccionario: OK. Todo objeto publicado tiene ficha."
LINEA_CON_PENDIENTES = "Cobertura del diccionario: OK con pendientes declarados."
LINEA_KO = "Cobertura del diccionario: KO."


def test_f006_r25_el_verde_limpio_solo_se_canta_sin_avisos_ni_pendientes() -> None:
    """«Todo objeto publicado tiene ficha» es una afirmación, no un saludo."""
    assert formatear_cobertura(InformeCobertura()) == LINEA_LIMPIA


def test_f006_r26_con_avisos_de_columnas_el_verde_deja_de_ser_limpio() -> None:
    """Hay columnas sin describir, aunque estén fuera de la superficie de
    consumo.

    El informe sigue en verde —R26 no las exige— pero no puede decir «todo
    objeto publicado tiene ficha» y punto: quien lo lea tiene que ver que queda
    trabajo, o el aviso no sirve de nada.
    """
    informe = InformeCobertura(avisos_columnas=("raw.obras.campo: sin significado",))

    salida = formatear_cobertura(informe)

    assert informe.ok, "un aviso de columna no tumba la puerta (R26)"
    assert salida.splitlines()[0] == LINEA_CON_PENDIENTES
    assert LINEA_LIMPIA not in salida


def test_f006_r27_con_pendientes_declarados_el_verde_deja_de_ser_limpio() -> None:
    """El trinquete solo baja, y para eso hay que verlo.

    Un pendiente declarado es deuda reconocida: legítima, pero visible. Si el
    informe dijera «todo objeto publicado tiene ficha» con pendientes vivos,
    estaría afirmando exactamente lo contrario de lo que el propio diccionario
    reconoce.
    """
    informe = InformeCobertura(pendientes_declarados=("stg.plan_mensual",))

    salida = formatear_cobertura(informe)

    assert informe.ok
    assert salida.splitlines()[0] == LINEA_CON_PENDIENTES
    assert LINEA_LIMPIA not in salida


def test_f006_r25_un_hueco_bloqueante_no_puede_salir_como_OK() -> None:
    """Publicado y sin ficha: el agente lo verá en el catálogo e inventará su
    significado.

    Es el caso que hace de esta línea una guarda y no una decoración: sin el
    `informe.ok`, un objeto sin ficha —el fallo bloqueante de R25— se anunciaría
    como «todo objeto publicado tiene ficha».
    """
    informe = InformeCobertura(
        sin_ficha=(
            ObjetoPublicado(
                esquema="mart",
                objeto="huerfano",
                tipo="tabla",
                origen="etl_sigrid/infrastructure/postgres/sql/mart/01_x.sql",
            ),
        )
    )

    salida = formatear_cobertura(informe)

    assert not informe.ok
    assert salida.splitlines()[0] == LINEA_KO
    assert LINEA_LIMPIA not in salida
