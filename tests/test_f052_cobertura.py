# tests/test_f052_cobertura.py
"""
F-052 · El guardián `check-cobertura` (R13 a R19, R28).

**Qué vigila y por qué no lo vigilaba nadie.** `check-unicidad` mira claves
duplicadas, `check-cierres` mira la regla de F-042 y `check-diccionario` mira
que el catálogo case con las fichas. Ninguno responde a la pregunta que habría
cazado esto el primer día: **lo que entra en `stg`, ¿sale en `mart`?** La obra
0599 llevaba desde 2022 publicando 4 M€ de venta y 0 € de coste directo y no
chirriaba nada.

Dos preguntas, y son distintas:

* **A · filas huérfanas (R15)** — filas de `stg.plan_mensual` sin ficha de
  partida o de obra, que los cuatro `INNER JOIN` de `mart/02_build_fact.sql`
  borran hoy sin decir nada. Hoy: 183.756 + 82.815.
* **B · obra invisible (R14)** — obra con filas en `stg.plan_mensual` para un
  ámbito y **cero** en `mart.fact_seguimiento_mensual` para ese mismo ámbito.

Aquí no se abre ninguna conexión: el cliente es un doble que sirve filas
enlatadas y **estalla si alguien intenta escribir**.
"""

from __future__ import annotations

import re

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.cobertura import (
    MARCADOR_KO,
    TIPO_AMBAS,
    TIPO_FILAS_HUERFANAS,
    TIPO_OBRA_INVISIBLE,
    Excepcion,
    FilaCobertura,
    formatear,
    veredicto,
)
from etl_sigrid.infrastructure.cobertura_excepciones import (
    YAML_EXCEPCIONES,
    cargar_excepciones,
)
from etl_sigrid.infrastructure.postgres.cobertura_sql import (
    AMBITOS_DEL_FACT,
    PALABRAS_DE_ESCRITURA,
    TIMEOUT_POR_CONSULTA_S,
    consultas_de_cobertura,
    filas_de_cobertura,
    sentencias_previas,
)

#: Cuántas excepciones hay declaradas HOY en `config/cobertura_excepciones.yaml`.
#: **Es un trinquete: sólo baja.** Igual que `PENDIENTES_MAX` para el diccionario
#: y `PENDIENTES_CONSTRUCCION_MAX` para `objetos_pendientes.yaml`, la constante
#: vive en el test a propósito: bajarla es parte de la tarea que cierra la
#: excepción, nunca un apaño posterior.
EXCEPCIONES_MAX = 10


def _fila(
    obra_id: int = 1442383,
    codigo_obra: str = "0599",
    nombre_obra: str = "TANATORIO MAJADAHONDA",
    ambito_id: int = 3,
    filas_stg: int = 100,
    filas_mart: int = 100,
    huerfanas: int = 0,
) -> FilaCobertura:
    return FilaCobertura(
        obra_id=obra_id,
        codigo_obra=codigo_obra,
        nombre_obra=nombre_obra,
        ambito_id=ambito_id,
        filas_stg=filas_stg,
        filas_mart=filas_mart,
        huerfanas=huerfanas,
    )


# ---------------------------------------------------------------------------
# R14, R15 · las dos preguntas, y el caso conforme
# ---------------------------------------------------------------------------


def test_f052_r13_un_caso_conforme_sale_con_codigo_0():
    """Todo lo que entra en `stg` sale en `mart` y no hay una sola huérfana."""
    resultado = veredicto([_fila(), _fila(ambito_id=7)], [])

    assert resultado.codigo == 0
    assert resultado.obras_invisibles == ()
    assert resultado.filas_huerfanas == ()
    assert not resultado.hay_hallazgos


def test_f052_r14_una_obra_invisible_se_denuncia_con_obra_y_ambito():
    """El caso de la 0599: filas en `stg` para el ámbito 7 y cero en el fact."""
    resultado = veredicto(
        [_fila(ambito_id=7, filas_stg=19_328, filas_mart=0)], []
    )

    assert resultado.codigo != 0
    assert len(resultado.obras_invisibles) == 1
    denuncia = formatear(resultado)
    assert "0599" in denuncia
    assert re.search(r"\bambito 7\b", denuncia), (
        "R14 exige nombrar obra Y ámbito: sin el ámbito no se sabe qué falta"
    )


def test_f052_r15_las_filas_huerfanas_se_cuentan_agrupadas_por_obra():
    """Es lo que los cuatro `INNER JOIN` del build borran hoy sin decir nada."""
    resultado = veredicto([_fila(huerfanas=183_530)], [])

    assert resultado.codigo != 0
    assert len(resultado.filas_huerfanas) == 1
    assert resultado.total_huerfanas == 183_530
    assert "183530" in formatear(resultado).replace(".", "")


def test_f052_r14_las_dos_listas_van_completas_y_no_son_una_muestra():
    """El humano pidió la lista entera en F-042 y aquí vale lo mismo: un `LIMIT`
    en un informe de cobertura es una forma elegante de no mirar."""
    filas = [
        _fila(obra_id=i, codigo_obra=f"07{i:02d}", filas_stg=10, filas_mart=0)
        for i in range(1, 31)
    ]

    resultado = veredicto(filas, [])
    informe = formatear(resultado)

    assert len(resultado.obras_invisibles) == 30
    for fila in filas:
        assert fila.codigo_obra in informe


# ---------------------------------------------------------------------------
# R16 · las excepciones declaradas
# ---------------------------------------------------------------------------


def test_f052_r16_una_excepcion_declarada_por_codigo_tapa_el_hallazgo():
    excepcion = Excepcion(
        tipo=TIPO_OBRA_INVISIBLE,
        codigo_obra="0517",
        motivo="el desempate rn=1 elige la ficha vacia",
        feature="F-053",
    )
    fila = _fila(codigo_obra="0517", nombre_obra="COLEGIO SESENA II", filas_mart=0)

    resultado = veredicto([fila], [excepcion])

    assert resultado.codigo == 0
    assert resultado.obras_invisibles == ()
    assert fila in resultado.cubiertas


def test_f052_r16_una_excepcion_declarada_por_patron_de_nombre_tapa_el_hallazgo():
    """Las obras administrativas no tienen ficha en `stg.obras` —las excluye a
    propósito la lista negra de `03_obras.sql`—, así que su código no siempre se
    puede resolver y lo que las identifica es el nombre."""
    excepcion = Excepcion(
        tipo=TIPO_FILAS_HUERFANAS,
        patron_nombre="OBRA PRUEBA",
        motivo="obra de prueba, excluida a proposito de stg.obras",
    )
    fila = _fila(codigo_obra="", nombre_obra="OBRA PRUEBA 3", huerfanas=42)

    assert veredicto([fila], [excepcion]).codigo == 0


def test_f052_r16_la_excepcion_no_tapa_un_tipo_distinto_del_declarado():
    """Declarar que una obra puede tener huérfanas NO autoriza a que además
    desaparezca entera del fact."""
    excepcion = Excepcion(
        tipo=TIPO_FILAS_HUERFANAS, codigo_obra="0630", motivo="una partida en ciclo"
    )
    fila = _fila(codigo_obra="0630", filas_mart=0, huerfanas=1)

    resultado = veredicto([fila], [excepcion])

    assert resultado.codigo != 0
    assert len(resultado.obras_invisibles) == 1
    assert resultado.filas_huerfanas == ()


def test_f052_r16_el_tipo_ambas_tapa_las_dos_caras():
    excepcion = Excepcion(
        tipo=TIPO_AMBAS, codigo_obra="0630", motivo="una partida en ciclo"
    )
    fila = _fila(codigo_obra="0630", filas_mart=0, huerfanas=1)

    assert veredicto([fila], [excepcion]).codigo == 0


def test_f052_r16_una_excepcion_acotada_a_un_ambito_no_cubre_los_demas():
    excepcion = Excepcion(
        tipo=TIPO_OBRA_INVISIBLE,
        codigo_obra="0599",
        ambito_id=7,
        motivo="acotada al ambito de venta",
    )

    assert veredicto([_fila(ambito_id=7, filas_mart=0)], [excepcion]).codigo == 0
    assert veredicto([_fila(ambito_id=3, filas_mart=0)], [excepcion]).codigo != 0


def test_f052_r16_una_excepcion_sin_identidad_se_rechaza_al_construirse():
    """Una excepción que no dice a quién cubre las cubriría a todas."""
    with pytest.raises(ValueError, match=r"codigo_obra|patron_nombre"):
        Excepcion(tipo=TIPO_OBRA_INVISIBLE, motivo="ninguna identidad")


def test_f052_r16_una_excepcion_con_un_tipo_inventado_se_rechaza():
    with pytest.raises(ValueError, match="tipo"):
        Excepcion(tipo="lo_que_sea", codigo_obra="0599", motivo="x")


def test_f052_r16_toda_excepcion_declara_motivo():
    """Una excepción sin porqué se convierte en permanente a la primera."""
    for excepcion in cargar_excepciones():
        assert excepcion.motivo.strip(), (
            f"la excepción de {excepcion.codigo_obra or excepcion.patron_nombre} "
            f"no dice por qué se acepta"
        )


def test_f052_r16_el_fichero_de_excepciones_declara_las_de_hoy():
    """Los tres grupos del informe: las obras con partidas en ciclo, las
    administrativas y las tres que dependen de F-053."""
    excepciones = cargar_excepciones()
    codigos = {e.codigo_obra for e in excepciones if e.codigo_obra}

    assert {"0565", "0630", "0686"} <= codigos, "faltan las obras con ciclos"
    assert {"0517", "0252", "0720"} <= codigos, "faltan las tres obras de F-053"
    assert any(e.feature == "F-053" for e in excepciones)


def test_f052_r16_el_trinquete_de_excepciones_solo_baja():
    """Mismo patrón que `objetos_pendientes.yaml` y que `pendientes` del
    diccionario: la lista no puede crecer sin que alguien mueva la constante."""
    assert len(cargar_excepciones()) <= EXCEPCIONES_MAX, (
        f"hay más excepciones que las {EXCEPCIONES_MAX} declaradas. El trinquete "
        f"SOLO BAJA: cerrar la causa es la tarea, no ampliar la lista"
    )


def test_f052_r16_la_constante_del_trinquete_vale_lo_que_hay():
    """Contraste del anterior: si alguien borra excepciones y no baja la
    constante, el trinquete deja de apretar sin que nadie se entere."""
    assert len(cargar_excepciones()) == EXCEPCIONES_MAX


def test_f052_r16_un_fichero_de_excepciones_ausente_no_se_traga():
    """Devolver «ninguna excepción» sería la dirección segura, pero convertiría
    «alguien borró la configuración» en «todo declarado». Mismo criterio que
    `cargar_pendientes_construccion`."""
    with pytest.raises(OSError):
        cargar_excepciones(YAML_EXCEPCIONES.parent / "no_existe_este_fichero.yaml")


# ---------------------------------------------------------------------------
# R28 · el marcador
# ---------------------------------------------------------------------------


def test_f052_r28_el_marcador_lleva_los_dos_recuentos():
    resultado = veredicto(
        [
            _fila(ambito_id=7, filas_mart=0, huerfanas=183_530),
            _fila(obra_id=2, codigo_obra="0618", huerfanas=180),
        ],
        [],
    )

    linea = resultado.marcador

    assert linea.startswith(MARCADOR_KO)
    assert "obras_invisibles=1" in linea
    assert "filas_huerfanas=183710" in linea


def test_f052_r28_sin_hallazgos_no_hay_marcador():
    """Un marcador emitido en verde entrenaría a todo el mundo a ignorarlo."""
    assert veredicto([_fila()], []).marcador == ""


# ---------------------------------------------------------------------------
# R18, R19 · el SQL sólo se construye, no se ejecuta
# ---------------------------------------------------------------------------


def _consultas():
    return {c.nombre: c for c in consultas_de_cobertura()}


def test_f052_r13_hay_exactamente_dos_consultas_y_son_las_del_diseno():
    assert set(_consultas()) == {"huerfanas", "invisibles"}


@pytest.mark.parametrize("nombre", ("huerfanas", "invisibles"))
def test_f052_r18_ninguna_consulta_escribe(nombre: str):
    texto = _consultas()[nombre].sql.upper()

    for palabra in PALABRAS_DE_ESCRITURA:
        assert not re.search(rf"\b{palabra}\b", texto), (
            f"la consulta {nombre} contiene {palabra}"
        )


@pytest.mark.parametrize("nombre", ("huerfanas", "invisibles"))
def test_f052_r18_ninguna_consulta_usa_temporales(nombre: str):
    texto = _consultas()[nombre].sql.upper()

    assert "TEMP" not in texto
    assert "TEMPORARY" not in texto


def test_f052_r18_construir_las_consultas_no_abre_ninguna_conexion(monkeypatch):
    """Al estilo de `unicidad_sql.py`: este módulo produce texto y nada más."""

    def revienta(*_a, **_k):
        raise AssertionError("cobertura_sql ha intentado abrir una conexión")

    monkeypatch.setattr(main, "_get_pg", revienta)

    assert consultas_de_cobertura()


@pytest.mark.parametrize("nombre", ("huerfanas", "invisibles"))
def test_f052_r19_cada_consulta_lleva_su_statement_timeout(nombre: str):
    """Corre contra `psql-albaranes-rs9k2`, compartido con `albaranes` y
    `partes` **en producción**: una consulta correcta que deje el servidor sin
    CPU no es aceptable."""
    consulta = _consultas()[nombre]
    previas = sentencias_previas(consulta.timeout_s)

    assert consulta.timeout_s == TIMEOUT_POR_CONSULTA_S
    assert any(
        f"statement_timeout = '{TIMEOUT_POR_CONSULTA_S}s'" in p for p in previas
    )
    assert any("transaction_read_only = on" in p for p in previas)


def test_f052_r14_la_consulta_de_invisibles_compara_stg_contra_el_fact():
    sql = _consultas()["invisibles"].sql

    assert "stg.plan_mensual" in sql
    assert "mart.fact_seguimiento_mensual" in sql
    assert f"ambito_id IN ({', '.join(str(a) for a in AMBITOS_DEL_FACT)})" in sql


def test_f052_r14_en_los_master_se_compara_presencia_y_no_conteo():
    """El build de planificado no es un `JOIN` puro: `master_proyectado` elige la
    versión vigente, así que muchísimas filas de `stg` no llegan al fact **por
    diseño** y contar sería mentir. La condición es «cero filas en el fact»."""
    sql = _consultas()["invisibles"].sql

    assert re.search(r"COALESCE\(\s*m\.filas\s*,\s*0\s*\)\s*=\s*0", sql), (
        "la consulta compara conteos en vez de presencia"
    )


def test_f052_r15_la_consulta_de_huerfanas_mira_las_dos_fichas():
    sql = _consultas()["huerfanas"].sql

    assert "stg.partidas" in sql
    assert "stg.obras" in sql
    assert "LEFT JOIN" in sql, (
        "con INNER JOIN la consulta perdería justo las filas que busca"
    )


def test_f052_r15_la_huerfana_recupera_el_nombre_de_una_obra_sin_ficha():
    """Una obra ausente de `stg.obras` no tiene código ni nombre allí. Sin
    recuperarlos de `raw`, la denuncia diría «obra 2824201» y nadie sabría cuál
    es ni podría declararla como excepción."""
    sql = _consultas()["huerfanas"].sql

    assert "raw.con" in sql
    assert "nombre_obra" in sql


def test_f052_las_dos_consultas_se_funden_por_obra_y_ambito():
    """Cada pregunta trae su mitad y el guardián necesita las dos en la misma
    fila: una obra puede ser invisible **y** tener huérfanas."""
    filas = filas_de_cobertura(
        huerfanas=[(1442383, "0599", "TANATORIO", 7, 183_530)],
        invisibles=[(1442383, "0599", "TANATORIO", 7, 19_328, 0)],
    )

    assert len(filas) == 1
    assert filas[0].huerfanas == 183_530
    assert filas[0].filas_stg == 19_328
    assert filas[0].filas_mart == 0


def test_f052_una_obra_con_huerfanas_pero_visible_tambien_llega_al_veredicto():
    filas = filas_de_cobertura(
        huerfanas=[(7, "0618", "SOTOGRANDE", 3, 180)], invisibles=[]
    )

    assert len(filas) == 1
    assert filas[0].huerfanas == 180
    assert filas[0].filas_mart == 0
    assert not filas[0].es_obra_invisible, (
        "sin fila en la consulta B no se puede afirmar que la obra sea invisible"
    )


# ---------------------------------------------------------------------------
# R13, R17 · el comando, dentro y fuera de `run-all`
# ---------------------------------------------------------------------------


class PgFalso:
    """Sirve filas enlatadas y estalla si le piden cualquier otra cosa."""

    def __init__(self, huerfanas=(), invisibles=()):
        self._huerfanas = list(huerfanas)
        self._invisibles = list(invisibles)
        self.consultas: list[str] = []
        self.timeouts: list[int] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        self.timeouts.append(timeout_s)
        if "fact_seguimiento_mensual" in sql_text:
            return self._invisibles
        return self._huerfanas

    def __getattr__(self, nombre: str):
        raise AssertionError(
            f"`check-cobertura` es de solo lectura y ha llamado a pg.{nombre}"
        )


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    def _con(pg):
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner()

    return _con


def test_f052_r13_el_comando_esta_registrado_con_sus_opciones():
    resultado = CliRunner().invoke(main.cli, ["check-cobertura", "--help"])

    assert resultado.exit_code == 0
    assert "--timeout" in resultado.output
    assert "--dry-run" in resultado.output


def test_f052_r18_dry_run_imprime_las_consultas_y_no_abre_conexion(monkeypatch):
    def revienta():
        raise AssertionError("--dry-run ha abierto una conexión")

    monkeypatch.setattr(main, "_get_pg", revienta)

    resultado = CliRunner().invoke(main.cli, ["check-cobertura", "--dry-run"])

    assert resultado.exit_code == 0
    assert "stg.plan_mensual" in resultado.output
    assert "mart.fact_seguimiento_mensual" in resultado.output


def test_f052_r17_lanzado_a_mano_sale_distinto_de_0_si_hay_hallazgos(cli):
    pg = PgFalso(
        huerfanas=[(1442383, "0599", "TANATORIO MAJADAHONDA", 3, 183_530)],
        invisibles=[(1442383, "0599", "TANATORIO MAJADAHONDA", 7, 19_328, 0)],
    )

    resultado = cli(pg).invoke(main.cli, ["check-cobertura"])

    assert resultado.exit_code == 1, "a mano tiene que servir de puerta"
    assert "0599" in resultado.output
    assert MARCADOR_KO in resultado.output


def test_f052_r13_el_comando_sale_0_cuando_todo_esta_declarado(cli):
    """Verde de verdad: se han mirado combinaciones y ninguna es un hallazgo.

    **Este test pasaba antes con `PgFalso()` a secas, sin ninguna fila**, y por
    eso no cazó el defecto que se arregló el 2026-09-03: el comando salía con 0
    habiendo mirado CERO combinaciones. Ahora se le da una combinación sana, que
    es lo que hacía falta para que el verde signifique algo.
    """
    pg = PgFalso(
        invisibles=[(1442383, "0599", "TANATORIO MAJADAHONDA", 7, 19_328, 19_328)]
    )

    resultado = cli(pg).invoke(main.cli, ["check-cobertura"])

    assert resultado.exit_code == 0
    assert MARCADOR_KO not in resultado.output


def test_f052_r13_sobre_CERO_combinaciones_el_comando_sale_KO(cli):  # noqa: N802
    """**El defecto arreglado el 2026-09-03, dentro de F-025.**

    No es una mejora teórica: pasó contra producción. `stg.plan_mensual` estaba
    truncada al 21,6 % por la avería del 02-sep, las dos consultas devolvieron
    cero filas y `check-cobertura` dijo OK. Un guardián que da verde cuando no ha
    podido mirar es peor que no tenerlo, porque entrena a quien lo lee a
    creerle. El propio módulo ya lo declaraba en el docstring de `Veredicto`
    —«un veredicto verde sobre cero filas no es un verde»— y el código no lo
    aplicaba.
    """
    resultado = cli(PgFalso()).invoke(main.cli, ["check-cobertura"])

    assert resultado.exit_code == 1
    assert MARCADOR_KO in resultado.output
    assert "no se ha comprobado nada" in resultado.output


def test_f052_r17_dentro_de_run_all_avisa_y_NO_tumba_el_job():  # noqa: N802
    """DA-4. Es el precio de no bloquear, y está declarado: al terminar el job en
    verde, la alerta de fallo existente no se dispara, así que la regla nueva de
    `infra/96_create_alert_cobertura.ps1` es la **única** vía por la que este
    guardián se hace oír."""
    pg = PgFalso(
        huerfanas=[(1442383, "0599", "TANATORIO MAJADAHONDA", 3, 183_530)],
        invisibles=[(1442383, "0599", "TANATORIO MAJADAHONDA", 7, 19_328, 0)],
    )

    resultado = main._guardian_de_cobertura(pg)

    assert resultado is not None
    assert resultado.codigo != 0, "el guardián sí ve el hallazgo…"
    assert main._guardian_de_cobertura.__doc__, "…y documenta que no lo escala"


def test_f052_r17_run_all_no_cuenta_la_cobertura_para_su_codigo_de_salida():
    """Fija el contrato en el código de `run-all`: `check-declarados` sí decide
    el código de salida y `check-cobertura` no."""
    import inspect

    # `run_all` está envuelto por click: la función de verdad es su `callback`.
    fuente = inspect.getsource(main.run_all.callback)

    assert "_guardian_de_cobertura" in fuente, "el guardián no corre en la nocturna"
    assert "not guardian_ok" in fuente
    assert "guardian_cobertura_ok" not in fuente, (
        "la cobertura ha entrado en el código de salida de run-all, y DA-4 dice "
        "que avisa y NO bloquea"
    )


def test_f052_un_fallo_leyendo_la_base_no_se_traga_dentro_de_run_all():
    """Callarlo dejaría una noche que termina en verde sin haber comprobado
    nada, que es el mismo agujero que cierra el guardián de F-047."""

    class PgQueFalla:
        def filas_solo_lectura(self, *_a, **_k):
            raise RuntimeError("la base no responde")

    assert main._guardian_de_cobertura(PgQueFalla()) is None


def test_f052_r16_una_excepcion_sin_motivo_se_rechaza_al_construirse():
    """Una excepción sin porqué se convierte en permanente a la primera: dentro
    de seis meses nadie sabrá si sigue haciendo falta."""
    with pytest.raises(ValueError, match="motivo"):
        Excepcion(tipo=TIPO_OBRA_INVISIBLE, codigo_obra="0599", motivo="   ")


def test_f052_r16_una_excepcion_con_las_DOS_identidades_se_rechaza():  # noqa: N802
    """Con código Y patrón no se sabe cuál manda, y una excepción ambigua tapa
    más de lo que alguien creyó declarar."""
    with pytest.raises(ValueError, match=r"codigo_obra|patron_nombre"):
        Excepcion(
            tipo=TIPO_OBRA_INVISIBLE,
            codigo_obra="0599",
            patron_nombre="TANATORIO",
            motivo="las dos cosas",
        )


def test_f052_r16_una_clave_que_nadie_lee_rompe_la_carga(tmp_path):
    """`motivos:` en vez de `motivo:` dejaría la excepción sin porqué y
    `yaml.safe_load` no diría nada. Falla al arrancar el comando, que es cuando
    hay alguien mirando."""
    fichero = tmp_path / "excepciones.yaml"
    fichero.write_text(
        "excepciones:\n"
        "  - codigo_obra: '0599'\n"
        "    tipo: obra_invisible\n"
        "    motivos: se escribio en plural\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="claves que nadie lee"):
        cargar_excepciones(fichero)


# ---------------------------------------------------------------------------
# El arreglo del 2026-09-03: cero combinaciones NO es un verde
#
# Se anade dentro de F-025 por acuerdo del humano. La razon de que entre ahi y
# no en una feature propia: F-025 construye su guardian con el MISMO patron
# -`check-ventana`, marcador estable, avisa y no bloquea- y no tenia sentido
# replicar el defecto en el guardian nuevo y dejar el viejo roto.
# ---------------------------------------------------------------------------


def test_f052_r16_un_veredicto_sobre_cero_filas_es_KO():  # noqa: N802
    """**Paso de verdad contra produccion el 2026-09-02.**

    `stg.plan_mensual` estaba truncada al 21,6 % por la averia, las dos
    consultas devolvieron cero filas y el veredicto salio en verde. "No hay nada
    malo" y "no he podido mirar" son cosas distintas y se parecen mucho en un
    informe: confundirlas es la definicion exacta del modo de fallo que esta
    feature existe para eliminar.
    """
    resultado = veredicto([], [])

    assert resultado.filas_miradas == 0
    assert resultado.no_ha_mirado_nada is True
    assert resultado.hay_hallazgos is False, "no hay hallazgos, y aun asi es KO"
    assert resultado.codigo == 1


def test_f052_r16_sobre_cero_filas_SI_se_emite_el_marcador():  # noqa: N802
    """La alerta tiene que dispararse tambien en este caso: si el guardian no
    puede mirar, alguien tiene que enterarse. Y el marcador lo dice: `sin
    comprobar`, no `hallazgos`."""
    resultado = veredicto([], [])

    assert MARCADOR_KO in resultado.marcador
    assert "combinaciones_miradas=0" in resultado.marcador
    assert "sin_comprobar=1" in resultado.marcador


def test_f052_r16_el_informe_explica_que_no_es_un_verde():
    texto = formatear(veredicto([], []))

    assert "no se ha comprobado nada" in texto
    assert "OK " not in texto


def test_f052_r16_una_sola_combinacion_sana_ya_es_un_verde_de_verdad():
    """El contraste. Con una combinacion mirada y limpia, el verde significa
    algo y el marcador NO se emite: un marcador que aparece todas las noches
    entrena a todo el mundo a ignorarlo."""
    sana = FilaCobertura(
        obra_id=1, codigo_obra="0710", nombre_obra="VIVA",
        ambito_id=3, filas_stg=100, filas_mart=100, huerfanas=0,
    )
    resultado = veredicto([sana], [])

    assert resultado.filas_miradas == 1
    assert resultado.no_ha_mirado_nada is False
    assert resultado.codigo == 0
    assert resultado.marcador == ""
