# tests/test_f052_cierre_excepciones.py
"""
F-052 · El cierre: que las excepciones declaradas **tapen lo que de verdad
salió**, no lo que creímos que iba a salir.

## Por qué existe este fichero y no basta con `test_f052_cobertura.py`

Aquel prueba el mecanismo —que `Excepcion.cubre` filtra por `tipo`, `ambito_id`,
código y patrón— con filas inventadas. Y el mecanismo estaba bien. Lo que estaba
mal era **el contenido del YAML**: varias excepciones declaraban
`filas_huerfanas` para obras que se manifiestan como **obra invisible**, así que
no tapaban nada. Diez declaraciones y ninguna apuntando al hallazgo de verdad.

Ese defecto no lo caza un test de mecanismo: sólo lo caza **replicar el veredicto
real**. Aquí va, como fixture, la línea base que el reviewer midió el 2026-09-02
con `python main.py check-cobertura --timeout 900` contra `psql-albaranes-rs9k2`
(informe `progress/review_F-052_fase2.md`): **20 obras invisibles en 43
combinaciones y 294 filas huérfanas en 13**.

De las 15 administrativas van **ocho representantes**, una por cada forma de
quedar fuera de `stg.obras` —lista negra de códigos y regla de los cinco dígitos
seguidos—, porque lo que hay que probar es que **cada patrón del YAML tapa las
dos manifestaciones**, no repetir quince veces el mismo caso. Las que sí van
enteras, obra a obra, son las que llevan nombre y apellidos en el review: 0613,
0618, 0578, 0585, 0670, 0687 y 0606.

## Qué prueba y qué no

Prueba que **con el YAML de hoy** ese veredicto sale limpio: cero hallazgos.
No prueba que hoy la base esté así —para eso está el comando contra la base—,
pero es lo único que se puede ejecutar sin conexión y en cada `init.sh`, y es
justo el error que se coló: un `tipo` equivocado no lo ve nadie hasta que la
consulta tarda un cuarto de hora en volver.

**El recuento de huérfanas de cada combinación es 1 a propósito.** La
clasificación depende de `huerfanas > 0`, no de cuántas: los totales reales
—0613 con 150, 0618 con 76, y 12 + 6 + 50 de las tres administrativas de código
de seis dígitos— viven en el informe de review y en el motivo de cada entrada
del YAML, que es donde se pueden leer.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.cobertura import FilaCobertura, veredicto
from etl_sigrid.infrastructure.cobertura_excepciones import cargar_excepciones

#: La línea base medida el 2026-09-02, obra a obra. Cada tupla es
#: `(obra_id, codigo_obra, nombre_obra, ambitos, invisible, con_huerfanas)`.
#:
#: Los `obra_id` de las obras que **no** tienen ficha en `stg.obras` son los de
#: `raw.con`; los de las que sí la tienen salen de `stg.obras`. Los dos se
#: consultaron contra la base el 2026-09-02 en solo lectura.
LINEA_BASE_2026_09_02 = (
    # --- Las dos obras de F-052 que conservan huérfanas: las «226 filas a
    # 0,00 EUR» que la propia spec anticipó como movimiento máximo fuera de la
    # 0599. 150 + 76 = 226.
    (1612629, "0613", "COLEGIO RICHMOND PARK (MADRID)", (3, 7, 8, 11), False, True),
    (1661978, "0618", "AMPL. COLEGIO INTERNACIONAL SOTOGRANDE(CADIZ)", (3, 8, 11), False, True),
    # --- Las cuatro obras ciegas SOLO en los ámbitos master (8 y 11). Tienen
    # ficha y publican en los ámbitos reales: pendientes de investigar (F-055).
    (1286520, "0578", "12 VIVIENDAS C/CANILLAS (MADRID)", (8, 11), True, False),
    (1314512, "0585", "REF. Y AMPLIACIÓN COLEGIO MAYOR ALCOR (MADRID)", (8, 11), True, False),
    (2153966, "0670", "CAMPO FUTBOL COLEGIO SANTILLANA (MADRID)", (8, 11), True, False),
    (2318773, "0687", 'CENTRO PRIMERA ACOGIDA DE MENORES "LA CANTUEÑA"', (8, 11), True, False),
    # --- 0606: el ide PERDIDO por el desempate `rn = 1` de stg/03_obras.sql.
    # No está en `stg.obras`, así que es invisible en los cuatro ámbitos Y todas
    # sus filas son huérfanas. Es F-053 quien decide cuál de los dos ide manda.
    (1581377, "0606", "PARQUE TEMÁTICO PUY DU FOU - LOTE 7 (TOLEDO)", (3, 7, 8, 11), True, True),
    # --- Las administrativas que `stg/03_obras.sql` excluye a propósito: por la
    # lista negra de códigos o por la regla `con.cod !~ '[0-9]{5,}'`. Al no tener
    # ficha en `stg.obras` son las DOS cosas a la vez, y ahí es donde el `tipo`
    # `filas_huerfanas` dejaba la mitad al descubierto.
    (1186269, "171104", "OBRA PRUEBA 4", (3, 7, 8, 11), True, True),
    (1263034, "180501", "OBRA PRUEBA 5", (3, 7, 8, 11), True, True),
    (870589, "POSTV", "POSTVENTA", (3, 7, 8, 11), True, True),
    (1659588, "POSTV2", "POSTVENTA 2", (3, 7, 8, 11), True, True),
    (870000, "VAR", "VARIOS", (3, 7, 8, 11), True, True),
    (939484, "150414", "REESTRUCTURACIÓN MERCADO PROSPERIDAD", (3, 7, 8, 11), True, True),
    (952304, "150703", "OBRA FORMACIÓN", (3, 7, 8, 11), True, True),
    (1359231, "181001", "OBRA CANILLAS", (3, 7, 8, 11), True, True),
)


def _filas_de_la_linea_base() -> tuple[FilaCobertura, ...]:
    filas = []
    for obra_id, codigo, nombre, ambitos, invisible, con_huerfanas in LINEA_BASE_2026_09_02:
        for ambito_id in ambitos:
            filas.append(
                FilaCobertura(
                    obra_id=obra_id,
                    codigo_obra=codigo,
                    nombre_obra=nombre,
                    ambito_id=ambito_id,
                    filas_stg=100,
                    filas_mart=0 if invisible else 100,
                    huerfanas=1 if con_huerfanas else 0,
                )
            )
    return tuple(filas)


def test_f052_cierre_la_linea_base_medida_queda_toda_declarada():
    """El veredicto del 2026-09-02, replicado: con el YAML de hoy no queda ni un
    hallazgo fuera de lo declarado.

    Si este test se pone rojo, la lectura es una de dos: apareció una obra que
    nadie ha declarado —y entonces hay que mirarla, no ampliarla— o alguien
    quitó una excepción sin cerrar su causa.
    """
    resultado = veredicto(_filas_de_la_linea_base(), cargar_excepciones())

    assert not resultado.obras_invisibles, (
        "quedan obras invisibles sin declarar: "
        + ", ".join(f.como_texto() for f in resultado.obras_invisibles)
    )
    assert not resultado.filas_huerfanas, (
        "quedan filas huérfanas sin declarar: "
        + ", ".join(f.como_texto() for f in resultado.filas_huerfanas)
    )
    assert resultado.codigo == 0


@pytest.mark.parametrize(
    ("codigo", "nombre"),
    [
        ("0606", "PARQUE TEMÁTICO PUY DU FOU - LOTE 7 (TOLEDO)"),
        ("171104", "OBRA PRUEBA 4"),
        ("POSTV", "POSTVENTA"),
        ("VAR", "VARIOS"),
    ],
)
def test_f052_cierre_las_administrativas_estan_declaradas_como_invisibles(
    codigo: str, nombre: str
) -> None:
    """El defecto exacto que el reviewer encontró, aislado.

    Las cuatro se manifiestan como **obra invisible**, y estaban declaradas
    `filas_huerfanas`. Una excepción que apunta al hallazgo equivocado es peor
    que no tenerla: ocupa sitio en el trinquete y no tapa nada.
    """
    fila = FilaCobertura(
        obra_id=999_999,
        codigo_obra=codigo,
        nombre_obra=nombre,
        ambito_id=11,
        filas_stg=100,
        filas_mart=0,
        huerfanas=0,
    )
    resultado = veredicto([fila], cargar_excepciones())
    assert not resultado.obras_invisibles, (
        f"{codigo} sigue saliendo como obra invisible: su excepción declara un "
        f"`tipo` que no es como se manifiesta"
    )


def test_f052_cierre_las_dos_obras_de_f052_con_residuo_estan_declaradas():
    """0613 y 0618 son dos de las SEIS obras de esta feature y conservan 226
    filas huérfanas a 0,00 EUR. `current.md` llegó a decir que ninguna de las
    294 era de F-052, y era falso."""
    codigos = {e.codigo_obra for e in cargar_excepciones() if e.codigo_obra}
    assert {"0613", "0618"} <= codigos


def test_f052_cierre_las_cuatro_ciegas_en_master_estan_acotadas_a_8_y_11():
    """Se declaran **con su ámbito**, no en general.

    Son ciegas sólo en master (8 y 11), que es donde el build elige la versión
    vigente y donde una obra sin master vigente puede no tener filas por diseño.
    Si mañana una de ellas desapareciera del ámbito 3 —coste real, dinero— eso
    sería un agujero nuevo y el guardián tiene que gritar.
    """
    por_codigo: dict[str, set[int | None]] = {}
    for e in cargar_excepciones():
        if e.codigo_obra in ("0578", "0585", "0670", "0687"):
            por_codigo.setdefault(e.codigo_obra, set()).add(e.ambito_id)

    assert set(por_codigo) == {"0578", "0585", "0670", "0687"}
    for codigo, ambitos in por_codigo.items():
        assert ambitos == {8, 11}, (
            f"la excepción de {codigo} no está acotada a los ámbitos master: "
            f"{ambitos}. Sin acotar taparía también el ámbito 3, que es dinero"
        )
