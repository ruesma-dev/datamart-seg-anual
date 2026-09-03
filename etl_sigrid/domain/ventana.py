# etl_sigrid/domain/ventana.py
"""
F-025 · La ventana de negocio: qué obras se reconstruyen esta noche y cuáles no.
**Dominio puro** (R1, R2, R16, R17, R18, R25, R26).

## Por qué existe

La nocturna del **2026-09-02 murió** por `replicaTimeout` en el tramo 5 de 60 y
dejó `stg.plan_mensual` truncada al **21,6 %**. El `Standard_B1ms` agotó sus 144
créditos de CPU a las 04:15 UTC y Azure lo capó al 20 % de un núcleo. Y se
reconstruían **920 obras** cada noche cuando solo **80** habían tenido actividad
en los últimos doce meses. Esto no es una mejora de rendimiento: es la
reparación de una avería.

En palabras del humano, el 2026-09-02: *«las obras que estén cerradas no se
actualizan»* y *«que no se reconstruyan, pero que **no se borren**, y que la
información esté **consultable**»*. Este módulo resuelve la primera mitad —quién
entra y quién no—; que no se borre es el borrado derivado de
`build_stg_step.py`, y que siga consultable, `_meta.v_frescura_obra`.

## El criterio, decidido por el humano (DA-1), no por esta spec

Se congela toda obra que cumpla **AL MENOS UNA** de estas tres, en unión:

1. su estado es **EN ESTUDIO (1)**, **NO PRESENTADA (11)** o **CERRADA (25)**;
2. su código son **seis dígitos** (222 obras administrativas, **ninguna llega al
   fact**);
3. **no tiene actividad** en los últimos doce meses.

Censo sobre las 920 obras del maestro: **880 congeladas, 40 vivas**. El catálogo
de estados está verificado contra `conest` tipo 42 (DA-1 bis): «25 = CERRADA»
**no es una suposición nuestra**.

Se le ofreció al humano la formulación **en positivo** —solo se actualizan las
EN CURSO (15) y las ADJUDICADAS DEFINITIVAMENTE (9)—, más robusta porque una
lista de estados que se actualizan es cerrada y una de estados que se congelan
hay que ir ampliándola. Respondió **«déjalo en negativo»**. Queda dicho por si
algún día se cambia.

## Los tres mecanismos que solo AÑADEN obras

Por encima del criterio hay tres cosas que pueden meter una obra en la
reconstrucción, y **ninguna puede sacar a ninguna**. Esa asimetría es
deliberada: equivocarse por exceso cuesta tiempo de CPU; equivocarse por defecto
deja un dato viejo publicado, que es el modo de fallo de F-052.

* **Reconstrucción completa** (R25) — los domingos entra todo.
* **Sello del SQL** (R17) — si `08_plan_mensual.sql` o `06_presupuesto.sql`
  cambian, se reconstruyen **todas**. Sin esto, un arreglo como el de F-052 solo
  alcanzaría a las 40 obras vivas y las otras 880 seguirían publicando lo de
  antes, en silencio.
* **Obra sin construir** (R18) — sin filas o sin registro. Completar no es
  actualizar.

## La firma DENUNCIA, no rescata (§3.1 del diseño)

La decisión del humano congela **40 obras con actividad reciente** —39 CERRADAS,
36 de ellas por el cierre anual de 2025-12, y 1 por código— y acepta hasta
**6 días** de antigüedad entre reconstrucciones completas. Por eso, cuando la
firma del origen de una obra congelada cambia, este módulo **la nombra y la deja
congelada**: reconstruirla por su cuenta contradiría la decisión que el humano
tomó con ese dato delante. El domingo la pone al día, y el interruptor
`PG_VENTANA_RESCATE` (default **off**) convierte la denuncia en reconstrucción
si algún día cambia de idea.

Capa **domain**: funciones puras, sin BBDD, sin ficheros y **sin reloj**. `hoy`
entra por parámetro. Leer la base es `infrastructure/postgres/`; componer el
build, `application/steps/build_stg_step.py`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

#: El literal que dispara la alerta del guardián. **Estable y buscable**: sin
#: fecha, sin nombres y sin espacios, porque la regla de Azure se escribe una
#: vez y se despliega a mano. Vive aquí, en un solo sitio, y lo cruza
#: `tests/test_f025_marcador.py` contra `infra/97_create_alert_ventana.ps1`.
MARCADOR_KO = "[F025-VENTANA-KO]"

#: Los cinco motivos por los que una obra acaba donde acaba. Se escriben tal
#: cual en `_meta.obra_build.motivo`, así que son parte del contrato publicado.
MOTIVO_COMPLETA = "completa"
MOTIVO_SELLO = "sello"
MOTIVO_SIN_FILAS = "sin_filas"
MOTIVO_FIRMA = "firma"
MOTIVO_VENTANA = "ventana"

MOTIVOS = (
    MOTIVO_COMPLETA,
    MOTIVO_SELLO,
    MOTIVO_SIN_FILAS,
    MOTIVO_FIRMA,
    MOTIVO_VENTANA,
)

#: Día de la reconstrucción completa, en la numeración de `date.weekday()`
#: (lunes = 0). **Domingo**, decidido por el humano (DA-4): es la noche que
#: puede permitirse volver a costar lo que cuesta hoy.
DOMINGO = 6

#: Tope de seguridad entre reconstrucciones completas. Es de donde sale el
#: «hasta 6 días» de R3: si un domingo se pierde —el job no corrió, o falló—,
#: la siguiente noche la completa entra igual por antigüedad. Sin este tope,
#: perder un domingo dejaría las 880 obras congeladas dos semanas.
DIAS_MAXIMOS_SIN_COMPLETA = 7

#: Caracteres de un `sha256` que se muestran al comparar dos sellos en un
#: mensaje. Ocho: suficientes para distinguirlos, pocos para que la frase se
#: lea. Los 64 completos harían ilegible el `detalle` que se publica en
#: `_meta.obra_build`.
LONGITUD_SELLO_CORTO = 8

#: Separador entre los textos SQL que entran en el sello. Un literal que no
#: puede aparecer dentro de un `.sql`: sin él, dos ficheros distintos podrían
#: concatenarse en la misma cadena que otros dos y dar el mismo sello.
SEPARADOR_DEL_SELLO = "\n--F025-SELLO--\n"


# ---------------------------------------------------------------------------
# El criterio, tal y como lo declara `config/business_rules.yaml`
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Criterio:
    """Las tres reglas de DA-1, como objeto validado.

    Sale de un YAML editable a mano, así que se valida **al construirlo**: un
    patrón que no compila tiene que fallar aquí y no a las 02:00, en mitad del
    build, con `stg.presupuesto` a medio escribir.
    """

    estados_que_congelan: frozenset[int]
    patron_codigo: str
    meses_sin_actividad: int

    def __post_init__(self) -> None:
        if self.meses_sin_actividad <= 0:
            raise ValueError(
                f"`meses_sin_actividad` debe ser un entero positivo y vale "
                f"{self.meses_sin_actividad}. Con cero o menos, la regla de "
                f"actividad congelaría hasta la obra que cerró esta mañana."
            )
        try:
            re.compile(self.patron_codigo)
        except re.error as error:
            raise ValueError(
                f"el patrón de código administrativo no compila: "
                f"{self.patron_codigo!r} ({error}). Sale de "
                f"config/business_rules.yaml, que se edita a mano."
            ) from error

    @property
    def regex_codigo(self) -> re.Pattern[str]:
        return re.compile(self.patron_codigo)


#: Nombre del bloque de `config/business_rules.yaml` que declara el criterio, y
#: de sus tres claves. Van como constantes porque el mensaje de error tiene que
#: poder nombrar la clave que falta sin que nadie la escriba dos veces.
BLOQUE_VENTANA = "ventana"
CLAVE_ESTADOS = "estados_que_congelan"
CLAVE_PATRON = "patron_codigo_administrativo"
CLAVE_MESES = "meses_sin_actividad"


def criterio_desde_reglas(
    business_rules: Mapping[str, object], meses: int | None = None
) -> Criterio:
    """Construye el `Criterio` desde `config/business_rules.yaml`.

    Es pura —recibe el diccionario ya leído, no abre el fichero— y por eso vive
    aquí: convertir el YAML en objeto validado es parte de la regla de negocio,
    no de la infraestructura que lo lee.

    `meses` permite que `PG_VENTANA_MESES` mande sobre el YAML **si se informa
    explícitamente**. La regla vive en el YAML, que es de Negocio; la variable de
    entorno existe para poder ensanchar la ventana una noche concreta sin
    cambiar la regla ni hacer un commit.

    Un bloque que falte o esté incompleto **aborta al construir**: es preferible
    a las 02:00, antes de escribir nada, que a mitad del build.
    """
    bloque = business_rules.get(BLOQUE_VENTANA)
    if not isinstance(bloque, Mapping):
        raise ValueError(
            f"config/business_rules.yaml no declara el bloque `{BLOQUE_VENTANA}:` "
            f"con el criterio de obra congelada. Sin el no se sabe que obras se "
            f"reconstruyen, y adivinarlo seria peor que parar."
        )

    faltan = [c for c in (CLAVE_ESTADOS, CLAVE_PATRON, CLAVE_MESES) if c not in bloque]
    if faltan:
        raise ValueError(
            f"al bloque `{BLOQUE_VENTANA}:` de config/business_rules.yaml le "
            f"faltan estas claves: {', '.join(faltan)}. Las tres reglas de DA-1 "
            f"van en union y ninguna es opcional."
        )

    estados = bloque[CLAVE_ESTADOS] or []
    if not all(isinstance(e, int) and not isinstance(e, bool) for e in estados):
        raise ValueError(
            f"`{CLAVE_ESTADOS}` debe ser una lista de enteros (los codigos de "
            f"`conest` tipo 42) y llego {estados!r}"
        )

    return Criterio(
        estados_que_congelan=frozenset(int(e) for e in estados),
        patron_codigo=str(bloque[CLAVE_PATRON]),
        meses_sin_actividad=int(bloque[CLAVE_MESES] if meses is None else meses),
    )


# ---------------------------------------------------------------------------
# Lo que se sabe de cada obra al empezar la noche
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObraCensada:
    """Una obra con todo lo que hace falta para decidir sobre ella.

    Lo reúne `postgres_client.fetch_censo_de_obras()` cruzando el maestro, las
    fases y `_meta.obra_build`; aquí no se consulta nada.
    """

    obra_id: int
    codigo_obra: str
    #: Estado de Sigrid (`conest` tipo 42). `None` = la obra no tiene ficha en
    #: el maestro, y entonces la regla 1 no la alcanza.
    estado_id: int | None = None
    #: Mes más reciente con fase cerrada. `None` = **ninguna fase**, que son 217
    #: obras del universo, y `None` NO es «reciente».
    ultima_actividad: date | None = None
    #: Tiene filas en `stg.plan_mensual` **y** en `stg.presupuesto` (R18).
    tiene_filas: bool = False
    #: Tiene fila en `_meta.obra_build`: «el registro la cubre» (R18).
    registrada: bool = False
    #: Sello del SQL con el que se construyó por última vez (R17).
    sello_registrado: str | None = None
    #: Firma del origen **de esta noche**, calculada sobre `raw` tras la ingesta.
    firma_origen: str | None = None
    #: Firma del origen **cuando se construyó**. Si difieren, algo se movió.
    firma_registrada: str | None = None

    @property
    def firma_divergente(self) -> bool:
        """El origen cambió desde la última construcción de esta obra.

        Con cualquiera de las dos firmas a `None` la respuesta es **False**: no
        se sabe, y «no se sabe» no es «cambió». Quien no tiene registro entra ya
        por R18, que es un camino más honesto que inventar una divergencia.
        """
        if self.firma_origen is None or self.firma_registrada is None:
            return False
        return self.firma_origen != self.firma_registrada


@dataclass(frozen=True, slots=True)
class Decision:
    """Qué se hace con una obra y **por qué**.

    `motivo` es uno de los cinco de `MOTIVOS` y viaja a
    `_meta.obra_build.motivo`; `detalle` es la frase que lee una persona.
    """

    obra_id: int
    codigo_obra: str
    reconstruir: bool
    motivo: str
    detalle: str
    firma_divergente: bool = False

    def como_texto(self) -> str:
        verbo = "RECONSTRUIR" if self.reconstruir else "CONGELAR  "
        aviso = "  [firma cambiada]" if self.firma_divergente else ""
        return (
            f"{verbo} {self.codigo_obra or 'sin codigo'} "
            f"(obra {self.obra_id}) · {self.motivo}: {self.detalle}{aviso}"
        )


@dataclass(frozen=True, slots=True)
class Plan:
    """Las dos listas, con el motivo de cada obra, y el sello con el que se hizo."""

    reconstruir: tuple[Decision, ...] = ()
    congelar: tuple[Decision, ...] = ()
    sello_vigente: str = ""
    #: Si la noche es de reconstrucción completa (R25). Viaja en el plan porque
    #: es lo que decide si se registra el hito y si se limpian las sobrantes.
    completa: bool = False

    @property
    def obras_a_reconstruir(self) -> tuple[int, ...]:
        return tuple(d.obra_id for d in self.reconstruir)

    @property
    def obras_congeladas(self) -> tuple[int, ...]:
        return tuple(d.obra_id for d in self.congelar)

    @property
    def denunciadas(self) -> tuple[Decision, ...]:
        """Obras congeladas cuyo origen ha cambiado. **Se nombran, no se
        rescatan** (§3.1): rescatarlas contradiría la decisión del humano."""
        return tuple(d for d in self.congelar if d.firma_divergente)

    @property
    def por_motivo(self) -> dict[str, int]:
        """Cuántas obras por motivo, para el log y para `_meta.etl_runs`."""
        cuenta: dict[str, int] = {}
        for decision in self.reconstruir + self.congelar:
            cuenta[decision.motivo] = cuenta.get(decision.motivo, 0) + 1
        return cuenta


# ---------------------------------------------------------------------------
# El criterio: por qué se congela una obra, o None si está viva
# ---------------------------------------------------------------------------


def meses_transcurridos(desde: date, hasta: date) -> int:
    """Meses enteros entre dos fechas, contando solo año y mes.

    **Se cuentan MESES, no días, y no es una simplificación perezosa: es lo que
    dice el dato.** La actividad de una obra sale de
    `MAX(make_date(f.anio, GREATEST(f.mes, 1), 1))` sobre `stg.fases`, así que
    siempre es el día 1 de un mes: el día no significa nada y compararlo sería
    inventarse una precisión que el origen no tiene.

    Antes esto restaba doce meses a la fecha de hoy y comparaba fechas, lo que
    obligaba a recortar el día al último del mes destino —31 de marzo menos un
    mes es el 28 de febrero—. Esa rama **nunca se ejecutaba** con el criterio
    real (restar 12 meses cae en el mismo mes, que tiene los mismos días) y la
    campaña de mutación de F-025 la delató: diez mutantes vivos, todos en cuatro
    líneas que ningún test podía alcanzar. Se quitó en vez de taparla con
    tests: el código que no se puede alcanzar no se prueba, se borra.
    """
    return (hasta.year - desde.year) * 12 + (hasta.month - desde.month)


def motivo_de_congelacion(
    obra: ObraCensada, criterio: Criterio, hoy: date
) -> str | None:
    """Por qué se congela esta obra, o `None` si está **viva**.

    Las tres reglas van en **UNIÓN** (DA-1): basta con que se cumpla una. Se
    evalúan en el orden en que las escribió el humano y se devuelve la primera
    que se cumple, porque el motivo que se guarda es el que explica la decisión,
    no la lista entera.

    El límite de los doce meses **no congela**: una obra cuya última fase es de
    hace exactamente doce meses cuenta como CON actividad. Se prefiere trabajar
    de más a dejar un dato viejo publicado.

    La comparación es **en meses enteros**, no en días: la actividad sale de
    `stg.fases` como el día 1 de un mes, así que el día no significa nada. Ver
    `meses_transcurridos`.
    """
    if obra.estado_id is not None and obra.estado_id in criterio.estados_que_congelan:
        return f"estado {obra.estado_id} en la lista de estados que congelan"

    if obra.codigo_obra and criterio.regex_codigo.match(obra.codigo_obra):
        return (
            f"codigo administrativo de seis digitos ({obra.codigo_obra}): "
            f"presupuestos y estudios que no llegan al fact"
        )

    if obra.ultima_actividad is None:
        return "sin ninguna fase cerrada: nunca ha tenido actividad"

    antiguedad = meses_transcurridos(obra.ultima_actividad, hoy)
    if antiguedad > criterio.meses_sin_actividad:
        return (
            f"sin actividad desde {obra.ultima_actividad.isoformat()}: "
            f"{antiguedad} meses, mas de {criterio.meses_sin_actividad}"
        )

    return None


def clasificar_obras(
    obras: Iterable[ObraCensada],
    criterio: Criterio,
    hoy: date,
    sello_vigente: str,
    *,
    completa: bool = False,
    rescate: bool = False,
) -> Plan:
    """El plan de la noche: qué se reconstruye, qué se congela y por qué.

    **Función pura**: mismas entradas, mismo plan, sin conexión y sin reloj.

    La precedencia, y el orden importa porque decide el motivo que queda
    escrito:

    1. **`completa`** — la noche del domingo entra todo, se mire lo que se mire.
    2. **`sin_filas`** — no está construida, o el registro no la cubre (R18).
       Va antes que el sello porque «no existe» explica mejor que «el sello no
       coincide», que es su consecuencia.
    3. **`sello`** — el SQL cambió (R17).
    4. **`firma`** — el origen cambió Y el rescate está activado (§3.1). Con el
       rescate apagado, que es el default, **no reconstruye**: denuncia.
    5. **`ventana`** — el criterio de DA-1.

    Ningún paso puede SACAR una obra de la lista: los cuatro primeros solo
    añaden. Equivocarse por exceso cuesta CPU; por defecto, un dato viejo.
    """
    reconstruir: list[Decision] = []
    congelar: list[Decision] = []

    for obra in obras:
        divergente = obra.firma_divergente
        motivo, detalle = _decidir(obra, criterio, hoy, sello_vigente, completa, rescate)

        if motivo is not None:
            reconstruir.append(
                Decision(
                    obra_id=obra.obra_id,
                    codigo_obra=obra.codigo_obra,
                    reconstruir=True,
                    motivo=motivo,
                    detalle=detalle,
                    firma_divergente=divergente,
                )
            )
        else:
            congelar.append(
                Decision(
                    obra_id=obra.obra_id,
                    codigo_obra=obra.codigo_obra,
                    reconstruir=False,
                    motivo=MOTIVO_VENTANA,
                    detalle=detalle,
                    firma_divergente=divergente,
                )
            )

    return Plan(
        reconstruir=tuple(reconstruir),
        congelar=tuple(congelar),
        sello_vigente=sello_vigente,
        completa=completa,
    )


def _decidir(
    obra: ObraCensada,
    criterio: Criterio,
    hoy: date,
    sello_vigente: str,
    completa: bool,
    rescate: bool,
) -> tuple[str | None, str]:
    """`(motivo_de_reconstruir | None, detalle)`. `None` = se congela."""
    if completa:
        return MOTIVO_COMPLETA, "reconstruccion completa semanal (domingo)"

    if not obra.tiene_filas:
        return MOTIVO_SIN_FILAS, "no tiene filas construidas: completar no es actualizar"
    if not obra.registrada:
        return (
            MOTIVO_SIN_FILAS,
            "sin fila en _meta.obra_build: no hay con que comparar nada",
        )

    if obra.sello_registrado != sello_vigente:
        return (
            MOTIVO_SELLO,
            f"el SQL cambio: construida con el sello "
            f"{_corto(obra.sello_registrado)} y el vigente es "
            f"{_corto(sello_vigente)}",
        )

    congelacion = motivo_de_congelacion(obra, criterio, hoy)

    if congelacion is None:
        return MOTIVO_VENTANA, "obra viva: no cumple ninguna de las tres reglas"

    if obra.firma_divergente and rescate:
        return (
            MOTIVO_FIRMA,
            f"el origen cambio y PG_VENTANA_RESCATE esta activado ({congelacion})",
        )

    return None, congelacion


def _corto(sello: str | None) -> str:
    """Un hash abreviado, que es lo que lee una persona.

    Los mensajes de `detalle` comparan dos sellos —«construida con X y el
    vigente es Y»— y viajan a `_meta.obra_build.detalle`, que se consulta por
    SQL. Meter ahí dos `sha256` de 64 caracteres hace la frase ilegible; ocho
    bastan para distinguirlos de un vistazo, y **los dos con la misma longitud**
    para poder compararlos sin contar caracteres.

    Se escribe con un `if` y no con `sello or "(ninguno)"` porque así el caso de
    «no hay sello» devuelve el literal ENTERO en vez de recortado a ocho, que
    era lo que salía antes: `(ninguno`, sin cerrar el paréntesis.
    """
    if not sello:
        return "(ninguno)"
    return sello[:LONGITUD_SELLO_CORTO]


# ---------------------------------------------------------------------------
# La firma del origen y el sello del SQL
# ---------------------------------------------------------------------------


def _canonico(valor: object) -> str:
    """Un valor como texto **determinista**.

    Todo lo que entra en un hash tiene que rendirse siempre igual o la firma
    cambiaría sola y denunciaría obras que no se han movido. Una firma que da
    falsos positivos se acaba ignorando, que es peor que no tenerla.

    `Decimal('1.10')` y `Decimal('1.1')` son el mismo número y tienen que dar el
    mismo texto: por eso el `normalize()`. Y `None` se rinde como cadena vacía,
    distinta de `'0'` y de `''` de verdad, porque en la práctica un agregado nulo
    (obra sin filas) y un cero (obra con filas que suman cero) son estados
    distintos que no deben colisionar.
    """
    if valor is None:
        return "~"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, Decimal):
        normalizado = valor.normalize()
        # `normalize()` deja notación científica en los enteros grandes
        # (1E+3): `format(..., 'f')` la deshace y devuelve siempre dígitos.
        return format(normalizado, "f")
    if isinstance(valor, float):
        return repr(valor)
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def firma_de_obra(agregados: Mapping[str, object]) -> str:
    """`sha256` de los agregados del origen de una obra.

    Los agregados salen de `SQL_FIRMA_ORIGEN`, sobre **`raw`** —lo único que la
    ingesta sigue trayendo completo cada noche (R34)—. Hashearlos aquí y no en
    SQL no es capricho: es lo que hace la firma **testable con fixtures** y lo
    que la pone bajo la campaña de mutación de DA-6.

    Las claves se ordenan, así que el orden de las columnas de la consulta no
    puede cambiar la firma. Y el nombre de cada clave entra en el hash: añadir
    un agregado nuevo cambia la firma de todas las obras, que es lo correcto —el
    significado de la firma ha cambiado— y lo que provoca una reconstrucción
    completa la primera noche.
    """
    partes = [f"{clave}={_canonico(agregados[clave])}" for clave in sorted(agregados)]
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def sello_sql(textos: Sequence[str], params: Mapping[str, object] | None = None) -> str:
    """`sha256` del SQL del build y de sus parámetros (R17).

    **Los finales de línea se normalizan a `\\n`**: un `git checkout` en Windows
    con `core.autocrlf` puede cambiar el CRLF de un `.sql` sin cambiar una coma
    de su lógica, y sin esto ese checkout reconstruiría las 920 obras esa noche
    creyendo que el SQL cambió. Se normaliza también el BOM, por lo mismo.

    Lo que **no** se normaliza es el espacio en blanco interior ni los
    comentarios: cambiar un comentario de `08_plan_mensual.sql` reconstruye todo,
    y es el lado correcto en el que equivocarse.
    """
    normalizados = [
        t.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n") for t in textos
    ]
    cuerpo = SEPARADOR_DEL_SELLO.join(normalizados)
    if params:
        cuerpo += SEPARADOR_DEL_SELLO + "|".join(
            f"{clave}={_canonico(params[clave])}" for clave in sorted(params)
        )
    return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# La reconstrucción completa semanal (R25, DA-4)
# ---------------------------------------------------------------------------


def toca_reconstruccion_completa(
    ultima: datetime | None,
    ahora: datetime,
    dia_semana: int = DOMINGO,
    dias_maximos: int = DIAS_MAXIMOS_SIN_COMPLETA,
) -> tuple[bool, str]:
    """`(toca, por qué)`. Se dispara **desde `run-all`**, no desde un cron nuevo.

    La razón de que no sea un cron es la lección de F-047 y del cron de F-052,
    que sigue desactivado: **un cron aparte es lo que se olvida**. Aquí la
    decisión se toma cada noche, con el registro delante.

    Tres motivos, en orden:

    1. **Nunca se ha hecho una completa.** No hay línea base: se hace.
    2. **Hoy es el día** y todavía no se ha hecho hoy.
    3. **Han pasado más de `dias_maximos`.** Es la red del domingo perdido: sin
       ella, un domingo que el job no corra dejaría las 880 obras congeladas dos
       semanas, y el «hasta 6 días» que el humano aceptó dejaría de ser cierto.
    """
    if ultima is None:
        return True, "no hay ninguna reconstruccion completa registrada"

    dias = (ahora - ultima).total_seconds() / 86400.0

    if ahora.weekday() == dia_semana and ultima.date() < ahora.date():
        return True, (
            f"hoy es el dia de la reconstruccion completa y la ultima fue el "
            f"{ultima.date().isoformat()}"
        )

    if dias >= dias_maximos:
        return True, (
            f"han pasado {dias:.1f} dias desde la ultima reconstruccion completa "
            f"({ultima.date().isoformat()}), mas del maximo de {dias_maximos}"
        )

    return False, (
        f"la ultima reconstruccion completa fue hace {dias:.1f} dias "
        f"({ultima.date().isoformat()})"
    )


# ---------------------------------------------------------------------------
# El guardián: qué se denuncia y cómo se lee (R26, R27)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HallazgoVentana:
    """Una obra que hay que nombrar, con lo que hace falta para entenderla."""

    tipo: str
    obra_id: int
    codigo_obra: str
    detalle: str

    def como_texto(self) -> str:
        return (
            f"  {self.codigo_obra or 'sin codigo'} (obra {self.obra_id}): "
            f"{self.detalle}"
        )


TIPO_FIRMA_DIVERGENTE = "firma_divergente"
TIPO_CONGELADA_SIN_FILAS = "congelada_sin_filas"
TIPO_SELLO_NO_VIGENTE = "sello_no_vigente"
TIPO_COMPLETA_VENCIDA = "completa_vencida"

TIPOS_DE_HALLAZGO = (
    TIPO_FIRMA_DIVERGENTE,
    TIPO_CONGELADA_SIN_FILAS,
    TIPO_SELLO_NO_VIGENTE,
    TIPO_COMPLETA_VENCIDA,
)


@dataclass(frozen=True, slots=True)
class VeredictoVentana:
    """Lo que el guardián ha visto, y **cuántas obras ha llegado a mirar**.

    `obras_miradas` va aquí por la misma razón que `filas_miradas` en
    `domain/cobertura.py`, y con el mismo arreglo del 2026-09-02: **un verde
    sobre cero obras no es un verde, es que no se ha comprobado nada**. La
    diferencia entre «no hay nada malo» y «no he podido mirar» es justo la que
    dejó F-052 bloqueada, y este guardián nace con ella resuelta.
    """

    hallazgos: tuple[HallazgoVentana, ...] = ()
    obras_miradas: int = 0
    #: Días desde la última reconstrucción completa, o `None` si no hay ninguna.
    dias_desde_completa: float | None = None
    resumen_extra: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hay_hallazgos(self) -> bool:
        return bool(self.hallazgos)

    @property
    def no_ha_mirado_nada(self) -> bool:
        """Cero obras miradas. **Es un KO**, no un OK."""
        return self.obras_miradas == 0

    @property
    def codigo(self) -> int:
        return 1 if (self.hay_hallazgos or self.no_ha_mirado_nada) else 0

    def de_tipo(self, tipo: str) -> tuple[HallazgoVentana, ...]:
        return tuple(h for h in self.hallazgos if h.tipo == tipo)

    @property
    def marcador(self) -> str:
        """La línea que dispara la alerta, o cadena vacía si no hay nada (R27).

        **En verde no se emite.** Un marcador que aparece todas las noches
        entrena a todo el mundo a ignorarlo, y entonces la alerta ya no vale.
        """
        if not self.codigo:
            return ""
        if self.no_ha_mirado_nada:
            return f"{MARCADOR_KO} obras_miradas=0 sin_comprobar=1"
        return " ".join(
            [MARCADOR_KO]
            + [f"{tipo}={len(self.de_tipo(tipo))}" for tipo in TIPOS_DE_HALLAZGO]
        )


def formatear_ventana(veredicto: VeredictoVentana) -> str:
    """El informe, con **las listas enteras**: un `LIMIT` aquí es una forma
    elegante de no mirar."""
    lineas = [
        f"Ventana de negocio · {veredicto.obras_miradas} obra(s) miradas, "
        f"{len(veredicto.hallazgos)} hallazgo(s).",
        "",
    ]

    for tipo in TIPOS_DE_HALLAZGO:
        lineas.append(_bloque(veredicto, tipo))
    lineas.append("")

    if veredicto.no_ha_mirado_nada:
        lineas.append(veredicto.marcador)
        lineas.append(
            "KO   no se ha mirado NI UNA obra. Esto no es un verde: es que no "
            "hay censo que comprobar, y un OK aqui seria indistinguible de "
            "«todo correcto» sin haber comprobado nada. Revisa que "
            "_meta.obra_build tenga filas y que `stg` este construido."
        )
    elif veredicto.hay_hallazgos:
        lineas.append(veredicto.marcador)
        lineas.append(
            "KO   hay obras congeladas que hay que mirar. Lanzado a mano esto "
            "sale con codigo 1; dentro de `run-all` se registra y la nocturna "
            "termina en verde (DA-5), asi que la unica via por la que esto se "
            "hace oir es la regla de infra/97_create_alert_ventana.ps1."
        )
    else:
        lineas.append(
            "OK   ninguna obra congelada ha cambiado en el origen, todas tienen "
            "sus filas y el sello vigente, y la reconstruccion completa esta al "
            "dia. No prueba que las cifras sean correctas: prueba que nada se "
            "ha quedado viejo en silencio."
        )

    return "\n".join(lineas)


_TITULOS = {
    TIPO_FIRMA_DIVERGENTE: (
        "Obras congeladas cuyo ORIGEN ha cambiado (se nombran, no se rescatan)"
    ),
    TIPO_CONGELADA_SIN_FILAS: "Obras congeladas SIN filas construidas",
    TIPO_SELLO_NO_VIGENTE: "Obras construidas con un SELLO de SQL que ya no es el vigente",
    TIPO_COMPLETA_VENCIDA: "Reconstruccion completa VENCIDA",
}


def _bloque(veredicto: VeredictoVentana, tipo: str) -> str:
    hallazgos = veredicto.de_tipo(tipo)
    if not hallazgos:
        return f"{_TITULOS[tipo]}: ninguna."
    lineas = [f"{_TITULOS[tipo]}: {len(hallazgos)}."]
    lineas += [h.como_texto() for h in hallazgos]
    return "\n".join(lineas)
