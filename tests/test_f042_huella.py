# tests/test_f042_huella.py
"""
F-042 · La huella antes/después y su veredicto (R22 a R25).

Es **la prueba que decide**, por requisito del humano del 2026-08-29: «hay que
probar que el mensual y el acumulado de las obras no afectadas no cambie», «con
el mismo raw», «en los 4 ámbitos para estar seguro». No decide que los tests
pasen: decide que el dato de las obras que nadie tocó no se mueva ni un céntimo.

Aquí se prueban las tres piezas que se pueden probar sin base: la comparación,
el veredicto y el ida y vuelta del CSV. Ejecutarla contra `sigrid_dm` es T14 a
T17 y **lo hace el humano**.

Un detalle que no es cosmético: el veredicto tiene que **fallar por dos motivos
distintos** —que se mueva una obra que no estaba en la lista, y que se mueva
algo en los ámbitos 8 u 11—. El segundo es el que demuestra que el arreglo no se
desborda, porque esos dos ámbitos hoy no tienen ni una clave duplicada y su
resultado esperado es cero cambios.
"""

from __future__ import annotations

import re as _re
from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.application.steps.build_stg_step import DIRECTORIO_SQL_STG
from etl_sigrid.domain.huella import (
    AMBITOS_DE_LA_HUELLA,
    FilaHuella,
    comparar_huellas,
    veredicto,
)
from etl_sigrid.infrastructure.postgres.cierres_sql import PALABRAS_DE_ESCRITURA
from etl_sigrid.infrastructure.postgres.huella_obras import (
    MARCADOR_FILTRO_OBRAS,
    MARCADOR_FIN_REALES,
    MARCADOR_INICIO_REALES,
    HuellaAbortada,
    bloque_de_reales,
    construir_huella,
    escribir_csv,
    filtro_de_tramo,
    leer_csv,
    sql_huella_mart,
    sql_huella_propuesta,
    sql_huella_stg,
)

SQL_PLAN_MENSUAL = (DIRECTORIO_SQL_STG / "08_plan_mensual.sql").read_text(
    encoding="utf-8"
)

FEBRERO = date(2018, 2, 1)
ENERO = date(2018, 1, 1)


def _fila(
    obra_id: int = 584748,
    codigo: str = "0499",
    ambito: int = 3,
    periodo: date = FEBRERO,
    filas: int = 120,
    versiones: str = "21",
    importe_mes: str = "975249.98",
    importe_origen: str = "5688073.92",
) -> FilaHuella:
    return FilaHuella(
        obra_id=obra_id,
        codigo_obra=codigo,
        ambito_id=ambito,
        periodo=periodo,
        filas=filas,
        versiones=versiones,
        importe_mes=Decimal(importe_mes),
        importe_origen=Decimal(importe_origen),
    )


#: Una huella de juguete con las cuatro ámbitos y tres obras: la 0499 (afectada)
#: y dos que no lo están, una real y otra master.
ANTES = (
    _fila(versiones="20|21", filas=240, importe_origen="10753384.34"),
    _fila(periodo=ENERO, versiones="18|19", filas=240, importe_origen="8321104.83"),
    _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="1000.00"),
    _fila(obra_id=700001, codigo="0700", ambito=7, versiones="4", importe_origen="900.00"),
    _fila(obra_id=700001, codigo="0700", ambito=8, versiones="12", importe_origen="1100.00"),
    _fila(obra_id=700001, codigo="0700", ambito=11, versiones="12", importe_origen="1050.00"),
)

#: El mismo `raw`, con la regla aplicada: solo se mueve la 0499.
DESPUES = (
    _fila(versiones="21", filas=120, importe_origen="5688073.92"),
    _fila(periodo=ENERO, versiones="19", filas=120, importe_origen="4712823.94"),
    _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="1000.00"),
    _fila(obra_id=700001, codigo="0700", ambito=7, versiones="4", importe_origen="900.00"),
    _fila(obra_id=700001, codigo="0700", ambito=8, versiones="12", importe_origen="1100.00"),
    _fila(obra_id=700001, codigo="0700", ambito=11, versiones="12", importe_origen="1050.00"),
)


# ---------------------------------------------------------------------------
# R23 · las dos listas, completas
# ---------------------------------------------------------------------------


def test_f042_r23_dos_huellas_identicas_no_producen_ningun_cambio():
    comparacion = comparar_huellas(ANTES, ANTES)

    assert comparacion.numeracion == ()
    assert comparacion.importes == ()


def test_f042_r23_la_numeracion_que_cambia_se_lista_entera():
    """Las dos celdas de la 0499, no una muestra."""
    comparacion = comparar_huellas(ANTES, DESPUES)

    assert len(comparacion.numeracion) == 2
    assert {c.periodo for c in comparacion.numeracion} == {ENERO, FEBRERO}
    febrero = next(c for c in comparacion.numeracion if c.periodo == FEBRERO)
    assert febrero.antes == "20|21"
    assert febrero.despues == "21"
    assert febrero.codigo_obra == "0499"


def test_f042_r23_los_importes_que_cambian_se_listan_con_su_diferencia():
    comparacion = comparar_huellas(ANTES, DESPUES)

    febrero = next(
        c
        for c in comparacion.importes
        if c.periodo == FEBRERO and c.campo == "importe_origen"
    )
    assert febrero.antes == Decimal("10753384.34")
    assert febrero.despues == Decimal("5688073.92")
    assert febrero.diferencia == Decimal("-5065310.42")


def test_f042_r23_un_importe_mes_que_cambia_se_reporta_por_separado():
    """`importe_mes` e `importe_origen` son dos columnas con dos historias.

    El humano pidió las dos: el acumulado es lo que está doblado, y el mensual es
    lo que un desplazamiento mal hecho rompería. Confundirlas en un solo
    veredicto escondería justo el defecto que la renumeración evita.
    """
    despues = (_fila(importe_mes="1.00"), *ANTES[1:])

    comparacion = comparar_huellas(ANTES, despues)

    campos = {c.campo for c in comparacion.importes if c.periodo == FEBRERO}
    assert "importe_mes" in campos
    assert "importe_origen" in campos


def test_f042_r23_una_celda_que_aparece_o_desaparece_es_un_cambio():
    """Un mes que se esfuma no puede pasar por «sin diferencias»."""
    sin_enero = tuple(f for f in DESPUES if f.periodo != ENERO)

    comparacion = comparar_huellas(ANTES, sin_enero)

    desaparecidas = [c for c in comparacion.importes if c.periodo == ENERO]
    assert desaparecidas, "la celda de enero desaparece y no se ha reportado"
    assert comparacion.celdas_antes == 6
    assert comparacion.celdas_despues == 5


def test_f042_r23_la_comparacion_dice_que_ambitos_ha_visto():
    """Si una huella no trae los cuatro, la prueba no cubre lo que dice cubrir."""
    comparacion = comparar_huellas(ANTES, DESPUES)

    assert comparacion.ambitos == AMBITOS_DE_LA_HUELLA == (3, 7, 8, 11)


# ---------------------------------------------------------------------------
# R24 y R25 · el veredicto
# ---------------------------------------------------------------------------

ESPERADAS = ("0246", "0310", "0433", "0462", "0471", "0499", "0545", "0571", "0606")


def test_f042_r24_solo_se_mueve_lo_previsto_y_el_veredicto_sale_0():
    codigo, informe = veredicto(comparar_huellas(ANTES, DESPUES), ESPERADAS)

    assert codigo == 0, informe
    assert "0499" in informe


def test_f042_r24_los_ambitos_8_y_11_salen_con_cero_cambios():
    """La frase que el humano tiene que poder leer sin interpretarla."""
    _, informe = veredicto(comparar_huellas(ANTES, DESPUES), ESPERADAS)

    assert "8" in informe and "11" in informe
    assert "0 cambio" in informe or "cero cambio" in informe


def test_f042_r25_una_obra_fuera_de_la_lista_tumba_el_veredicto():
    despues = (
        *DESPUES[:2],
        _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="999.00"),
        *DESPUES[3:],
    )

    codigo, informe = veredicto(comparar_huellas(ANTES, despues), ESPERADAS)

    assert codigo != 0
    assert "0700" in informe


def test_f042_r24_un_cambio_en_el_ambito_8_tumba_el_veredicto_aunque_la_obra_este_en_la_lista():
    """El desbordamiento es un fallo distinto de «se movió una obra de más».

    Los ámbitos master no se tocan: su rama del SQL está fijada por hash y hoy no
    tienen ni una clave duplicada. Un cambio ahí significa que el arreglo se ha
    salido de su sitio, y eso no lo tapa una lista de obras esperadas.
    """
    despues = (
        *DESPUES[:4],
        _fila(obra_id=584748, codigo="0499", ambito=8, versiones="12", importe_origen="1.00"),
        *DESPUES[5:],
    )
    antes = (
        *ANTES[:4],
        _fila(obra_id=584748, codigo="0499", ambito=8, versiones="12", importe_origen="1100.00"),
        *ANTES[5:],
    )

    codigo, informe = veredicto(comparar_huellas(antes, despues), ESPERADAS)

    assert codigo != 0
    assert "8" in informe


def test_f042_r24_sin_los_cuatro_ambitos_el_veredicto_no_puede_ser_verde():
    """Una huella a la que le falte un ámbito prueba menos de lo que dice."""
    solo_reales = tuple(f for f in ANTES if f.ambito_id in (3, 7))

    codigo, informe = veredicto(comparar_huellas(solo_reales, solo_reales), ESPERADAS)

    assert codigo != 0
    assert "8" in informe and "11" in informe


def test_f042_r24_dos_huellas_identicas_con_los_cuatro_ambitos_salen_0():
    codigo, informe = veredicto(comparar_huellas(ANTES, ANTES), ESPERADAS)

    assert codigo == 0, informe


def test_f042_r23_el_informe_no_es_una_muestra():
    """Cien obras que se mueven se listan las cien: el humano pidió «la lista
    completa», y un `LIMIT 20` en un informe de no-regresión es una forma
    elegante de no mirar."""
    antes = tuple(
        _fila(obra_id=800000 + n, codigo=f"9{n:03d}", importe_origen="100.00")
        for n in range(100)
    )
    despues = tuple(
        _fila(obra_id=800000 + n, codigo=f"9{n:03d}", importe_origen="200.00")
        for n in range(100)
    )

    _, informe = veredicto(comparar_huellas(antes, despues), ESPERADAS)

    for n in range(100):
        assert f"9{n:03d}" in informe


# ---------------------------------------------------------------------------
# R22 · el CSV, fuera de la base
# ---------------------------------------------------------------------------


def test_f042_r22_el_csv_va_y_vuelve_sin_perder_un_centimo(tmp_path):
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)

    assert leer_csv(destino) == list(ANTES)


def test_f042_r22_el_csv_es_el_de_la_casa_utf8_bom_punto_y_coma_y_coma_decimal(tmp_path):
    """Convención de Ruesma: se abre en Excel ES sin tocar nada."""
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)
    crudo = destino.read_bytes()

    assert crudo.startswith(b"\xef\xbb\xbf")
    texto = crudo.decode("utf-8-sig")
    assert ";" in texto.splitlines()[0]
    assert "10753384,34" in texto
    assert "10753384.34" not in texto


def test_f042_r22_la_cabecera_nombra_las_ocho_columnas(tmp_path):
    destino = tmp_path / "huella.csv"

    escribir_csv(ANTES, destino)
    cabecera = destino.read_text(encoding="utf-8-sig").splitlines()[0]

    assert cabecera.split(";") == [
        "obra_id",
        "codigo_obra",
        "ambito_id",
        "periodo",
        "filas",
        "versiones",
        "importe_mes",
        "importe_origen",
    ]


def test_f042_r22_un_csv_vacio_se_lee_como_lista_vacia_y_no_como_verde(tmp_path):
    """Una huella vacía comparada con otra vacía da cero diferencias, y eso NO
    puede leerse como que nada cambió: el veredicto lo tiene que rechazar por no
    traer los cuatro ámbitos."""
    destino = tmp_path / "huella.csv"
    escribir_csv((), destino)

    assert leer_csv(destino) == []
    codigo, _ = veredicto(comparar_huellas([], []), ESPERADAS)
    assert codigo != 0


def test_f042_la_fila_de_huella_es_inmutable():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        _fila().filas = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# R22 · las consultas, y que la propuesta NO materializa nada
# ---------------------------------------------------------------------------

def _consultas() -> dict[str, str]:
    return {
        "stg": sql_huella_stg(),
        "mart": sql_huella_mart(),
        "propuesta": sql_huella_propuesta(SQL_PLAN_MENSUAL, (584748,)),
    }


@pytest.mark.parametrize("nombre", ("stg", "mart", "propuesta"))
def test_f042_r22_ninguna_consulta_de_la_huella_escribe(nombre: str):
    """El nivel 1 es de solo lectura por requisito, no por costumbre.

    `CREATE` está en la lista, así que un `CREATE TEMP TABLE` colado para
    «hacerlo más fácil» rompería este test antes de llegar a la base.
    """
    texto = _consultas()[nombre].upper()

    for palabra in PALABRAS_DE_ESCRITURA:
        assert not _re.search(rf"\b{palabra}\b", texto), (
            f"la huella {nombre} contiene {palabra}"
        )


@pytest.mark.parametrize("nombre", ("stg", "mart", "propuesta"))
def test_f042_r22_ninguna_consulta_de_la_huella_usa_temporales(nombre: str):
    texto = _consultas()[nombre].upper()

    assert "TEMP" not in texto
    assert "TEMPORARY" not in texto
    assert "INTO " not in texto


@pytest.mark.parametrize("nombre", ("stg", "mart"))
def test_f042_r22_la_huella_cubre_los_cuatro_ambitos(nombre: str):
    assert "ambito_id IN (3, 7, 8, 11)" in _consultas()[nombre]


def test_f042_r22_el_agregado_de_stg_lleva_los_mismos_join_que_mart():
    """Sin `stg.obras` y `stg.partidas` la huella contaría partidas que
    `mart/02_build_fact.sql` descarta, y dejaría de ser predictiva."""
    for texto in (sql_huella_stg(), sql_huella_propuesta(SQL_PLAN_MENSUAL, (1,))):
        assert "JOIN stg.obras" in texto
        assert "JOIN stg.partidas" in texto


def test_f042_r22_el_grano_es_obra_ambito_mes():
    for texto in (sql_huella_stg(), sql_huella_mart()):
        assert "GROUP BY" in texto
        assert "ambito_id, " in texto


def test_f042_r22_la_propuesta_reutiliza_el_texto_del_fichero_del_build():
    """El punto entero del bloque D: si fuera una copia de la lógica, la prueba
    que decide estaría midiendo un texto distinto del que va a correr."""
    bloque = bloque_de_reales(SQL_PLAN_MENSUAL)
    texto = sql_huella_propuesta(SQL_PLAN_MENSUAL, (584748,))

    for cte in ("reales_cierres AS (", "reales_vigente AS (", "reales_orden AS ("):
        assert cte in bloque and cte in texto
    assert "LAG(orden_fase) OVER w = orden_fase - 1" in texto
    assert texto.startswith("WITH")


def test_f042_r22_la_propuesta_sustituye_el_marcador_de_tramo():
    texto = sql_huella_propuesta(SQL_PLAN_MENSUAL, (584748, 950302))

    assert MARCADOR_FILTRO_OBRAS not in texto
    assert "ARRAY[584748, 950302]::BIGINT[]" in texto


def test_f042_r22_la_propuesta_solo_toca_los_ambitos_reales():
    """Los master se copian; su rama ni se menciona."""
    texto = sql_huella_propuesta(SQL_PLAN_MENSUAL, (1,))

    assert "ambito_id IN (3, 7)" in texto
    assert "master_" not in texto


def test_f042_sin_marcadores_la_propuesta_se_niega_a_construirse():
    """Antes que medir media rama —o SQL válido que mide otra cosa— se para."""
    with pytest.raises(ValueError, match="marcadores"):
        bloque_de_reales("SELECT 1")

    invertido = f"{MARCADOR_FIN_REALES} ... {MARCADOR_INICIO_REALES}"
    with pytest.raises(ValueError, match="marcadores"):
        bloque_de_reales(invertido)


def test_f042_el_filtro_de_tramo_no_admite_nada_que_no_sea_un_entero():
    """Misma regla dura que F-019: `bool` es subclase de `int` y `ARRAY[True]`
    no es una lista de obras."""
    assert filtro_de_tramo([7, 9]) == "ARRAY[7, 9]::BIGINT[]"

    with pytest.raises(ValueError):
        filtro_de_tramo([])
    with pytest.raises(TypeError):
        filtro_de_tramo([True])
    with pytest.raises(TypeError):
        filtro_de_tramo(["584748; DROP TABLE stg.plan_mensual"])


# ---------------------------------------------------------------------------
# La ejecución por tramos, con la puerta de disco delante
# ---------------------------------------------------------------------------


class PgHuellaFalso:
    """Sirve filas enlatadas y estalla si le piden cualquier escritura."""

    def __init__(self, ocupacion_pct: float = 29.0, pesos=None):
        self.ocupacion_pct = ocupacion_pct
        self._pesos = pesos or {584748: 10, 950302: 10}
        self.consultas: list[str] = []

    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        return dict(self._pesos)

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        return self.ocupacion_pct

    def filas_solo_lectura(self, sql_text: str, timeout_s: int):
        self.consultas.append(sql_text)
        obra = 584748 if "584748" in sql_text else 950302
        ambitos = (3, 7) if "reales_con_lag" in sql_text else (3, 7, 8, 11)
        return [
            (
                obra,
                "0499",
                amb,
                date(2018, 2, 1),
                1,
                "21",
                Decimal("1.00"),
                Decimal("2.00"),
            )
            for amb in ambitos
        ]

    def __getattr__(self, nombre: str):
        raise AssertionError(
            f"la huella es de solo lectura y ha llamado a pg.{nombre}"
        )


class AjustesFalsos:
    # Imita la forma de `config.settings`: `settings.postgres.<lo que sea>` y
    # `settings.logging.<lo que sea>`, que es lo que lee el grupo `cli`.
    class postgres:  # noqa: N801 - imita la forma de config.settings
        tramo_max_filas = 10
        disco_total_gb = 64
        disco_limite_pct = 85.0

    class logging:  # noqa: N801 - idem
        log_level = "WARNING"
        log_format = "console"


def test_f042_r22_la_huella_de_stg_va_por_tramos_y_no_escribe():
    pg = PgHuellaFalso()

    filas = construir_huella(pg, AjustesFalsos(), desde="stg", propuesta=False)

    assert {f.obra_id for f in filas} == {584748, 950302}
    assert {f.ambito_id for f in filas} == {3, 7, 8, 11}
    assert len(pg.consultas) == 2, "una consulta por tramo"


def test_f042_r22_la_propuesta_mezcla_reales_nuevos_con_master_copiados():
    """Los ámbitos 8 y 11 salen del agregado ACTUAL, no de reejecutar su rama."""
    pg = PgHuellaFalso()

    filas = construir_huella(
        pg,
        AjustesFalsos(),
        desde="stg",
        propuesta=True,
        sql_plan_mensual=SQL_PLAN_MENSUAL,
    )

    assert {f.ambito_id for f in filas} == {3, 7, 8, 11}
    con_reales = [c for c in pg.consultas if "reales_con_lag" in c]
    assert len(con_reales) == 2, "la rama de reales se reejecuta una vez por tramo"
    for consulta in con_reales:
        assert "8, 11" not in consulta, "la rama master no se reejecuta"


def test_f042_la_puerta_de_disco_para_la_huella_antes_de_pasarse():
    """La misma puerta de F-019, y por el mismo motivo: el disco es compartido."""
    pg = PgHuellaFalso(ocupacion_pct=91.0)

    with pytest.raises(HuellaAbortada, match="91"):
        construir_huella(pg, AjustesFalsos(), desde="stg", propuesta=False)


def test_f042_si_no_se_puede_medir_el_disco_la_huella_no_se_ejecuta_a_ciegas():
    class PgSinMedida(PgHuellaFalso):
        def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
            raise RuntimeError("pg_database no responde")

    with pytest.raises(HuellaAbortada, match="ciegas"):
        construir_huella(
            PgSinMedida(), AjustesFalsos(), desde="stg", propuesta=False
        )


def test_f042_la_huella_de_mart_se_lee_de_una_pasada():
    """24.684 filas y ninguna ventana: trocearla sería ceremonia sin motivo."""
    pg = PgHuellaFalso()

    construir_huella(pg, AjustesFalsos(), desde="mart", propuesta=False)

    assert len(pg.consultas) == 1


def test_f042_propuesta_desde_mart_no_tiene_sentido_y_se_rechaza():
    with pytest.raises(ValueError, match="propuesta"):
        construir_huella(
            PgHuellaFalso(), AjustesFalsos(), desde="mart", propuesta=True
        )


def test_f042_un_origen_desconocido_se_rechaza():
    with pytest.raises(ValueError, match="stg"):
        construir_huella(
            PgHuellaFalso(), AjustesFalsos(), desde="cierre", propuesta=False
        )


# ---------------------------------------------------------------------------
# Los dos comandos
# ---------------------------------------------------------------------------


def test_f042_r22_huella_obras_esta_registrado_con_sus_opciones():
    from click.testing import CliRunner as _CliRunner

    import main

    resultado = _CliRunner().invoke(main.cli, ["huella-obras", "--help"])

    assert resultado.exit_code == 0
    for opcion in ("--out", "--desde", "--propuesta"):
        assert opcion in resultado.output


def test_f042_r23_comparar_huellas_esta_registrado_con_sus_opciones():
    from click.testing import CliRunner as _CliRunner

    import main

    resultado = _CliRunner().invoke(main.cli, ["comparar-huellas", "--help"])

    assert resultado.exit_code == 0
    assert "--obras-esperadas" in resultado.output


def test_f042_r25_comparar_huellas_sale_distinto_de_0_si_se_mueve_otra_obra(tmp_path):
    from click.testing import CliRunner as _CliRunner

    import main

    antes = tmp_path / "antes.csv"
    despues = tmp_path / "despues.csv"
    escribir_csv(ANTES, antes)
    escribir_csv(
        (
            *DESPUES[:2],
            _fila(obra_id=700001, codigo="0700", versiones="4", importe_origen="1.00"),
            *DESPUES[3:],
        ),
        despues,
    )

    resultado = _CliRunner().invoke(
        main.cli,
        ["comparar-huellas", str(antes), str(despues), "--obras-esperadas", "0499"],
    )

    assert resultado.exit_code != 0
    assert "0700" in resultado.output


def test_f042_r24_comparar_huellas_sale_0_cuando_solo_cambia_lo_previsto(tmp_path):
    from click.testing import CliRunner as _CliRunner

    import main

    antes = tmp_path / "antes.csv"
    despues = tmp_path / "despues.csv"
    escribir_csv(ANTES, antes)
    escribir_csv(DESPUES, despues)

    resultado = _CliRunner().invoke(
        main.cli,
        ["comparar-huellas", str(antes), str(despues), "--obras-esperadas", "0499"],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "0 cambios, que es el resultado esperado" in resultado.output


def test_f042_una_huella_con_otra_cabecera_se_rechaza(tmp_path):
    """Leerla mal en silencio sería la peor forma de dar verde."""
    from etl_sigrid.infrastructure.postgres.huella_obras import leer_csv as _leer

    fichero = tmp_path / "otra.csv"
    fichero.write_text("obra;mes;importe\n1;2018-02-01;3\n", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="cabecera"):
        _leer(fichero)


# ---------------------------------------------------------------------------
# El comando `huella-obras` de punta a punta, con dobles
# ---------------------------------------------------------------------------
#
# Comprobar solo `--help` deja sin ejecutar el cuerpo del comando, que es donde
# vive lo que puede salir mal: leer el fichero del build, recorrer los tramos y
# volcar el CSV. Aqui se ejecuta entero contra un cliente falso que estalla si
# le piden escribir.


def test_f042_r22_el_comando_escribe_el_csv_y_no_toca_la_base_mas_que_para_leer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    import main

    pg = PgHuellaFalso()
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.setattr(main, "get_settings", AjustesFalsos)
    destino = tmp_path / "huella_antes.csv"

    from click.testing import CliRunner as _CliRunner

    resultado = _CliRunner().invoke(
        main.cli, ["huella-obras", "--out", str(destino), "--desde", "stg"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "SOLO LECTURA" in resultado.output
    filas = leer_csv(destino)
    assert len(filas) == 8, "dos obras x cuatro ambitos"
    assert {f.ambito_id for f in filas} == {3, 7, 8, 11}


def test_f042_r22_el_comando_avisa_si_la_huella_no_trae_los_cuatro_ambitos(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Una huella incompleta no puede salir sin que nadie lo diga: `comparar-
    huellas` la va a rechazar, y mejor enterarse ahora que dos horas despues."""
    import main

    class PgSoloReales(PgHuellaFalso):
        def filas_solo_lectura(self, sql_text: str, timeout_s: int):
            return [
                f for f in super().filas_solo_lectura(sql_text, timeout_s)
                if f[2] in (3, 7)
            ]

    pg = PgSoloReales()
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.setattr(main, "get_settings", AjustesFalsos)

    from click.testing import CliRunner as _CliRunner

    resultado = _CliRunner().invoke(
        main.cli, ["huella-obras", "--out", str(tmp_path / "h.csv")]
    )

    assert resultado.exit_code == 0
    assert "no trae los cuatro ambitos" in resultado.output


def test_f042_r22_la_propuesta_lee_el_sql_del_build_de_verdad(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """`--propuesta` tiene que ejecutar la rama de reales del fichero real."""
    import main

    pg = PgHuellaFalso()
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.setattr(main, "get_settings", AjustesFalsos)

    from click.testing import CliRunner as _CliRunner

    resultado = _CliRunner().invoke(
        main.cli,
        ["huella-obras", "--out", str(tmp_path / "h.csv"), "--propuesta"],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "sin materializar" in resultado.output
    assert any("reales_con_lag" in c for c in pg.consultas)
    assert any("LAG(orden_fase) OVER w = orden_fase - 1" in c for c in pg.consultas)


def test_f042_r22_un_bloque_de_reales_sin_marcador_de_tramo_se_rechaza():
    """Sin el filtro de F-019, la huella se ejecutaria de una pasada sobre la
    base entera: es justo lo que lleno el disco del servidor compartido el
    2026-08-09. Se para al construir el texto, antes de enviarlo."""
    sin_filtro = SQL_PLAN_MENSUAL.replace(MARCADOR_FILTRO_OBRAS, "ARRAY[1]::BIGINT[]")

    with pytest.raises(ValueError, match="una vez"):
        sql_huella_propuesta(sin_filtro, (1,))


def test_f042_r22_un_csv_sin_ni_cabecera_se_rechaza(tmp_path):
    """Un fichero de cero bytes no es una huella vacia: es un fichero que no se
    llego a escribir. Devolver `[]` lo haria pasar por «no cambio nada»."""
    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="cabecera"):
        leer_csv(vacio)
