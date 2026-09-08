<!-- docs/ARCHITECTURE.md -->
# Arquitectura · datamart-seg-anual

ETL Sigrid → PostgreSQL → Power BI para el seguimiento económico mensual de
obras. Microservicio único; se despliega como job programado en Azure.

## Hexagonal + pipeline

- `etl_sigrid/domain/` — entidades puras (TableSpec, ColumnSpec, StepResult,
  StepStatus). CERO imports de infraestructura.
- `etl_sigrid/application/` — `Orchestrator` ejecuta una lista de steps.
  Cada step hereda de `steps/base.py::PipelineStep` y recibe/enriquece un
  contexto. Steps actuales: ingest_raw, load_excel_aux, build_stg, build_mart,
  build_maestros, build_cierre.
- `etl_sigrid/infrastructure/` — adaptadores: `sigrid/sigrid_api_client.py`
  (HTTP a sigrid-api), `postgres/postgres_client.py`, SQL por capas en
  `postgres/sql/`, logging estructurado.
- Punto de entrada: `main.py` (click). El pipeline se compone en main, no
  dentro de los steps.

## Capas PostgreSQL (¡no existe capa en `public`!)

`raw` → `stg` → `mart` (+ `cierre` para cierres mensuales y planif vs real).
Módulos adicionales: `compras`, `maestro`, `retenciones`, `auxiliar`.
SQL numerado `NN_nombre.sql` y ejecutado en orden dentro de cada capa.

## Semántica Sigrid imprescindible (fuente de bugs si se ignora)

- Ámbitos: amb=3 Coste Real, amb=7 Venta Real, amb=8 Master Coste,
  amb=11 Master Venta.
- Master (amb 8/11): `fas` = número de VERSIÓN; planif explosionada.
- Reales (amb 3/7): `fas` = MES; fas=0 = Previsto (foto viva),
  fas=1..N cierres mensuales; planif NO explosionada;
  importe del mes = diferencia con la fase anterior.
- **DOS CIERRES EN UN MISMO MES: manda el moderno (F-042).** 22 obras tienen
  dos fases que Sigrid guarda con el mismo `ano` y el mismo `mes`. `stg`
  conserva **una sola**: la de `fas` más alto **entre las que tienen el
  acumulado distinto de cero** (si todas están a cero, la más alta). El cierre
  descartado sigue en `raw` y en `stg.fases`; lo que no tiene es fila en
  `stg.plan_mensual`. Dentro del build se renumera un orden interno —solo por
  los descartes, nunca con `dense_rank()`— para que el `LAG` de `importe_mes`
  siga viendo el cierre inmediatamente anterior; ese orden **no se publica**, y
  `version` conserva el número de fase original, con huecos en 9 obras.
- **UN CAPÍTULO PUEDE NO TENER CÓDIGO, Y ESO NO PUEDE CORTAR EL ÁRBOL
  (F-052).** En `raw.obrparpar` hay capítulos cuyo `cod` es la **cadena vacía**
  —no NULL: `length(cod) = 0`—, típicamente porque alguien montó el árbol por
  fases de obra y dejó el código en blanco. Hasta el 2026-08-31 el recorrido de
  `stg/04_partidas.sql` se negaba a **descender a través** de ellos y amputaba
  el subárbol entero: tres capítulos así en la obra 0599 se llevaron por delante
  **1.323 partidas**, 2.624.793,46 € de coste directo y el 100 % de su venta, y
  el datamart publicó durante años un margen del 66,3 % donde el real era del
  1,8 %. La regla es: **el código vacío decide QUÉ SE PUBLICA, no POR DÓNDE SE
  DESCIENDE**. El capítulo en blanco se atraviesa y se colapsa —sus hijos
  cuelgan del ancestro publicado más cercano, y ni `ruta_capitulos` ni `nivel`
  avanzan al pasar por él—, así que se mantiene el invariante
  `cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1`.
- **Y la cadena de `padide` puede dar vueltas.** Hay 12 partidas en ciclo vivas
  —dos auto-bucles y un bucle mutuo—, así que cualquier recorrido del árbol
  necesita corta-ciclos: array de visitados **más** tope de profundidad. Sin él,
  relajar el filtro de código vacío es un `WITH RECURSIVE` infinito dentro de
  una nocturna de 3 h 45.
- `obr.ide = con.ide` (obra hereda de concepto). El nombre legible está en
  `con.res`. `con.nom` NO existe.
- En `raw.obrfas` el campo de fase se llama `fasnum`; en `raw.obrparpre` se
  llama `fas`. No confundirlos.
- Versión de master vigente por obra: campo extendido `cod='15'` en `conext`.
- `importe_origen = round(can * round(precio, decp), deci)`;
  `importe_mes` = diferencia entre orígenes consecutivos.
  REGLA: `importe_mes` jamás se suma entre meses distintos en vistas para
  Power BI; `importe_origen` es acumulado.
- Fechas Sigrid: enteros YYYYMMDD; 0 = NULL.
- La ingesta nocturna SIEMPRE `--full` (el cursor incremental por `ide`
  pierde los UPDATE).
- Palabra reservada `real` en vistas de `cierre` → siempre entre comillas.

## Acceso a datos

- Sigrid solo vía sigrid-api (`POST /api/sql/read`), nunca conexión directa.
  Tope duro 10.000 filas/petición; timeout de red efectivo 230 s.
- Solo LECTURA de Sigrid desde este proyecto. Las escrituras del datamart van
  al PostgreSQL propio (local en dev, Flexible Server en Azure).
- **Los tres Excels auxiliares de Negocio (F-004)** se leen de una ruta del
  sistema de ficheros **o** de Azure Blob Storage, y lo decide la FORMA del
  valor de `AUX_EXCEL_*`: una URI
  `https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>` va a Blob
  Storage; cualquier otra cosa, al disco. No hay variable de modo que mantener
  coherente. La autenticación es `DefaultAzureCredential` —identidad
  gestionada en el job, sesión de `az` en el puesto—, con el rol
  `Storage Blob Data Reader` sobre la cuenta: **ni cadenas de conexión, ni
  claves, ni SAS** (una URI con query string se rechaza al arrancar el paso).
  El contenido se obtiene **en memoria**, sin ficheros temporales, porque el
  contenedor no tiene dónde escribirlos. Puerto y adaptadores en el paquete,
  bajo `infrastructure/excel/`; el step `load_excel_aux` no sabe de
  Azure. Hoy **lee y valida, no carga** a `aux.*`: las tablas destino y el
  esquema de los libros no están definidos todavía.

### Qué se copia de Sigrid: 56 tablas, y qué NO está ahí (F-066)

`config/tables_sigrid.yaml` declara **56 tablas** desde el 2026-09-06 (eran 31).
Las 25 que entraron ese día vienen en tres grupos, y ninguna se supuso: todo lo
que sigue se midió contra Sigrid ese día por `sigrid-api` en solo lectura.

- **Personal** — `res` (2.610 recursos), `emp` (1.352 empleados), `hmo` (6.850
  cabeceras de parte) y **`hmores` (328.760 líneas)**. Las horas están en
  `hmores`, no en `hmo`: en la cabecera el recurso viene informado en 6 filas de
  6.850. Es la corrección que hace posible «horas por obra».
- **Contabilidad** — `cua` (34.139 cuentas), `asi` (783.386 asientos), **`apu`
  (2.154.543 apuntes)** y `apa` (709.403 líneas de desglose). `apu` es la tabla
  más grande del datamart, por encima de `con`.
- **Compras y proveedor** — la cadena entera necesidad (`dnc`, `dncpro`) →
  comparativo (ya estaba) → oferta (`dco`, `dcopro`, `dcorec`) → contrato (ya
  estaba), más condiciones (`ctrrec`, `dcfrec`, `dcarec`, `auxpag`, `auxefp`),
  firmas (`confir`, `deffir`), estados (`conest`) y proveedor (`conact`,
  `auxpronat`, `prvcer`, `prvobrpag`).

**El mapa de `con.tip`**, verificado por recuento y necesario para leer `raw`:
5 proveedor, 12 oferta de compra, 14 albarán, 15 factura, 16 cuenta del plan,
20 asiento, 33 recurso, 42 obra, 43 empleado, 44 contrato, 46 comparativo.

**Ninguna de las cuatro tablas de contabilidad tiene columna de última
modificación**, así que la carga incremental por columna de corte no existe para
ellas: van enteras. Da igual en la práctica —la nocturna es `--full`— pero
importa si alguien intenta acortarla. `apu` se trae entera y sin filtro:
partirla por empresa ahorra ≤ 10 % y exige subconsulta, y por ejercicio, ≤ 15 %.

**`raw.emp` y `raw.res` llevan datos personales completos**, por decisión
explícita del humano del 2026-09-06 frente a la propuesta de excluir 72
columnas: DNI, número de la Seguridad Social, cuenta bancaria, domicilio,
contacto, fecha de nacimiento y credenciales de acceso. Solo se excluye lo
binario y el texto ilimitado, que es criterio técnico. **La ficha de cada una
declara qué contiene**.

**El MCP ya no las lee, y eso es TEMPORAL (F-068, 2026-09-07).** Hasta esa
fecha `mcp_sigrid_dm_ro` alcanzaba `raw` entero y las dos tablas eran legibles
por cualquier cuenta del tenant. El humano decidió quitarle el permiso —«de
momento quita el permiso. Cuando pongamos límites o guardarraíles por usuario,
habrá que volver a ponerlo para algunos usuarios»—, así que **no es una
prohibición permanente**: es un tapón mientras el MCP no distinga QUIÉN
pregunta, y su reversión ya está decidida para cuando exista ese control.

Cómo se sostiene, que es la parte que no se ve: `GRANT SELECT ON ALL TABLES IN
SCHEMA` no sabe saltarse una tabla, y `apply_grants` lo reaplica cada noche. Por
eso la revocación **no es una orden suelta contra la base** —esa duraría hasta
la nocturna siguiente— sino parte del propio paso: concede el esquema, revoca
las tablas de `PG_EXCLUDED_TABLES` y cambia el `ALTER DEFAULT PRIVILEGES` de
`raw` de `GRANT` a `REVOKE`, para que una tabla recreada tampoco nazca legible.
La lista es `DEFAULT_EXCLUDED_TABLES` en `config/settings.py`, y ahí está
escrita la condición para levantarla.

**Lo que Sigrid NO guarda**, medido dos veces y escrito aquí para que nadie
vuelva a buscarlo:

- **No hay histórico de cambios de estado** de contratos ni de facturas. La
  tabla de auditoría registra 1,5 M de cambios de forma de pago y de fecha de
  factura desde 2017, y **ni uno solo del campo de estado**. Lo que hay es el
  estado actual (`con.est`), su nombre **por tipo de documento** (`conest`: la
  misma cifra significa cosas distintas en un contrato y en una factura), el
  alta (`con.fec`) y la última modificación (`con.tiemod`, ya en
  `raw.con._source_tiemod`) como aproximación de su antigüedad. El histórico lo
  construye F-067 como foto diaria sobre `raw`, y empieza a contar el día que se
  despliegue.
- **Los contratos no pasan por el circuito de firma** (`confir`): sus 69.993
  firmas son de comparativos, facturas y obras, y las de factura vienen sin
  fecha. `PFfir` y `logfirdoc`, donde el backlog esperaba encontrarlo, están
  vacías, como otras 17 candidatas que por eso no se ingieren.
- **La penalización del contrato no existe como campo**, y la actividad del
  proveedor no es `act` (vacía) sino `conact` → `auxpronat`.

`python main.py check-raw-recuentos` compara, tabla a tabla y con el mismo
filtro, el `COUNT(*)` de Sigrid con el de `raw`. Es de solo lectura, va fuera de
`run-all` y sale con código 1 también cuando Sigrid **no pudo** contestar: «no
he podido mirar» no es «está bien».

**La tolerancia tiene dirección** (corregido el 2026-09-08, tras la primera
medición real). Exigir igualdad exacta era inalcanzable: Sigrid es un ERP vivo
y el datamart una foto, así que cinco horas después de la ingesta 25 de 56
tablas tenían filas de más —4.883 sobre 25.287.500, un 0,0193 %— y ninguna de
menos. Ahora las filas **de más** en Sigrid son deriva normal y se aceptan
mientras no pasen de `--tolerancia-pct` (0,05 % por defecto, relativo a cada
tabla); las filas de **menos** son alarma inmediata, sea de una fila, porque
eso no lo hace el paso del tiempo sino un borrado en origen, una ingesta
duplicada o una carga equivocada. `AUSENTE EN RAW` y `SIN MEDIR` siguen siendo
fallo con cualquier tolerancia.

### El datamart en Azure (F-005)

- **No hay servidor propio.** La base `sigrid_dm` vive dentro de
  `psql-albaranes-rs9k2.postgres.database.azure.com` (`rg-albaranes-dev`,
  PostgreSQL 16, `Standard_B1ms`, **64 GB** desde el 2026-08-29; antes 32), que
  ya sirve a `albaranes`, `partes`, `dedicacion`, `postventa` y `facturas`,
  **todas en uso** —la última apareció sola el 2026-09-07 y tumbó una
  nocturna—. Base propia y no esquema compartido: PostgreSQL
  no permite consultas entre bases, y esa es la frontera que impide que el rol
  de lectura vea `albaranes`.
- **Tres roles.** `sigrid_dm_etl` (grupo `NOLOGIN`) es el propietario de todo;
  `sigrid_dm_app` (login, contraseña en Key Vault) es el que usa el ETL y es
  miembro del grupo; `mcp_sigrid_dm_ro` (login) es de solo lectura, para el
  MCP. Autenticación por contraseña: habilitar Entra es una operación de
  servidor y se descartó para no tocar las otras dos bases. El modo
  `PG_AUTH_MODE=entra` existe en el código, probado, pero inactivo.
- **`PG_SET_ROLE=sigrid_dm_etl`** en cada sesión: los objetos deben tener
  siempre el mismo dueño, porque las vistas se recrean en cada ejecución y
  quien no es dueño no puede hacer `DROP`.
- **`PG_AUTO_CREATE_DB=false`** contra Azure: el ETL no ejecuta
  `CREATE DATABASE` ni abre la base admin en un servidor de producción
  compartido. La base la crea el humano con `infra/sql/`.
- **Los permisos de lectura se reaplican en cada ejecución** (paso
  `apply_grants` y comando `apply-grants`): siete ficheros SQL recrean vistas
  con `DROP VIEW ... CASCADE` y un `DROP` se lleva los `GRANT`.
- **La recuperación es volver a ejecutar el ETL, no restaurar**: el PITR es de
  servidor entero y arrastraría `albaranes` y `partes` al pasado.
- Procedimiento completo: `docs/runbook_postgres_azure.md`.

### El build de `stg.plan_mensual` va por tramos (F-019)

El 2026-08-09 ese build llenó el disco del servidor compartido: la explosión
del `planif` con `CROSS JOIN LATERAL unnest(...)` sobre 13,76 M filas derramó
16+ GB de temporales, la ocupación llegó al 93,4 % y Azure dejó el servidor en
solo-lectura diez minutos, con `albaranes` y `partes` en producción. En local
no pasaba porque sobra RAM.

Desde F-019, el sub-paso `build_plan_mensual` **no se ejecuta de una pasada**:

- **Corte por obra.** Ninguna ventana del SQL cruza obras (particionan por
  `presupuesto_id` o por la terna obra-partida-ámbito), así que ejecutar el
  mismo statement con un filtro de obras disjunto y completo da exactamente
  las mismas filas. La equivalencia es estructural, no casual.
- **Quién hace qué.** `domain/tramos.py` planifica (función pura: pesos por
  obra + tope), `build_stg_step` orquesta y `postgres_client` mide y ejecuta.
  El fichero SQL lleva un marcador que el step sustituye por las obras del
  tramo, **en las dos ramas** (master amb 8/11 y reales amb 3/7); filtrar solo
  una duplicaría la otra. **El vaciado de la tabla lo hacía el step una vez,
  antes del primer tramo; desde F-025 ya no existe** —ver la sección siguiente:
  cada tramo borra las obras que va a reinsertar, en su misma transacción—.
- **Una transacción por tramo**, para que el pico de temporales de un tramo no
  se apile con el del siguiente.
- **Puerta de disco antes de CADA tramo**: se mide la ocupación del servidor
  (suma de `pg_database_size` de todas las bases) y, si supera el límite, el
  build **para** y marca FAILED. Si la medición falla, también para: seguir a
  ciegas es lo que provocó el incidente. **Hasta F-025 el aborto además vaciaba
  la tabla**; ya no, porque vaciarla destruiría las 880 obras congeladas.
- **Tres settings**, todos con default y sin secretos: `PG_TRAMO_MAX_FILAS`
  (1 000 000), `PG_DISCO_TOTAL_GB` (64, el disco de hoy) y
  `PG_DISCO_LIMITE_PCT` (80). Un
  máximo enorme reproduce el comportamiento antiguo si alguna vez hiciera
  falta diagnosticar, sin conservar una rama de código con el arma cargada.
- Cada tramo deja su fila en `_meta.etl_runs`, así que `python main.py timings`
  desglosa el coste real tramo a tramo.

### La ventana de negocio: no todas las obras se reconstruyen (F-025)

La nocturna del **2026-09-02 murió** por `replicaTimeout` en el tramo 5 de 60 y
dejó `stg.plan_mensual` truncada al **21,6 %**. La causa, medida: el
`Standard_B1ms` es *burstable*, agotó sus 144 créditos de CPU a las 04:15 UTC y
Azure lo capó al 20 % de un núcleo; cada tramo pasó de **1,57 min** a **40,77**.
Y se reconstruían **920 obras** cada noche cuando solo **48** habían tenido
actividad en los últimos doce meses. Esto no fue una mejora de rendimiento: fue
la reparación de una avería.

Desde F-025, `06_presupuesto.sql` y `08_plan_mensual.sql` se construyen **solo
para las obras vivas**. Lo importante no es cuáles, sino **cómo se escribe**.

#### El borrado se DERIVA de lo que se escribe (y esto cambia una invariante)

El `TRUNCATE` global desapareció de las dos tablas. En su lugar, **cada tramo
borra exactamente las obras que va a reinsertar, en su misma transacción**:

```sql
DELETE FROM stg.plan_mensual WHERE obra_id = ANY (ARRAY[...]::BIGINT[]);
INSERT INTO stg.plan_mensual ... AND pp.obra_id = ANY (ARRAY[...]::BIGINT[]);
```

Las dos listas se componen **del mismo dato**, así que no pueden
desincronizarse: es imposible borrar una obra que luego no se reescriba. El
`DELETE` va por índice —`idx_plan_mensual_obra_amb` e `idx_pres_obra_amb`
empiezan los dos por `obra_id`, verificado contra `pg_indexes`—, así que no
barre la tabla.

**Eso invierte la invariante de aborto de F-019.** Allí, parar dejaba la tabla
**vacía**, porque una tabla a medias era indistinguible de una completa. Ya no
aplica: lo que queda tras un fallo no es media tabla, son **obras enteras con su
última versión buena**, y vaciarlas destruiría las 880 congeladas. Quien impide
que `build_mart` construya sobre un stage a medias sigue siendo **la puerta de
F-024**, que no se toca.

Y repara la avería de paso: la noche del 02-sep habría terminado con cinco obras
al día y el resto con el dato de anoche —coherente— en vez de con la tabla al
21,6 %. **Vale por sí solo aunque el acotado no ahorrase nada.**

#### Quién se congela, y quién decide

El criterio lo fijó el humano el 2026-09-02 y son **tres reglas en unión**:
estado **EN ESTUDIO (1), NO PRESENTADA (11) o CERRADA (25)**; código de **seis
dígitos**; o **sin actividad en 12 meses**. Censo: **880 congeladas, 40 vivas**.
Vive en `config/business_rules.yaml`, bloque `ventana:`, y se evalúa en dominio
puro (`domain/ventana.py`): cambiarlo no toca código.

Por encima hay tres mecanismos que **solo añaden** obras, nunca quitan:

- **Reconstrucción completa** (domingos, por antigüedad registrada desde
  `run-all`, no por un cron nuevo: un cron aparte es lo que se olvida).
- **Sello del SQL**: si `06`/`08` cambian, esa noche entran **todas**. Sin esto,
  un arreglo como el de F-052 solo alcanzaría a las 40 vivas y las otras 880
  seguirían publicando lo de antes, **en silencio**.
- **Obra sin construir**: sin filas o sin registro. Completar no es actualizar.

La asimetría es deliberada: equivocarse por exceso cuesta CPU una noche;
equivocarse por defecto deja un dato viejo publicado.

#### La firma DENUNCIA, no rescata

La decisión congela **8 obras con actividad reciente** —7 CERRADAS y 1 de seis
dígitos, de 48 con actividad; remedido el 2026-09-03— y acepta hasta **6 días**
de antigüedad. Cuando el origen de una obra congelada cambia, el sistema **la
nombra y la deja congelada**: rescatarla contradiría esa decisión. La firma se
calcula sobre **`raw`** —lo único que la ingesta sigue trayendo completo— en un
sub-paso propio tras `ingest_raw`, porque `stg.presupuesto` dejó de
reconstruirse entera y con ello dejó de servir como señal.

#### De cuándo es el dato de cada obra

`_meta.obra_build` (una fila por obra: firmas, sello, `batch_id`,
`construido_at`, motivo) y `_meta.v_frescura_obra`, hermana de `_meta.v_frescura`
pero al grano de obra. Es la respuesta consultable a *«¿de cuándo es esto?»*, y
la leen igual el MCP y Power BI. `construido_at` **solo se mueve cuando la obra
se reconstruye de verdad**: moverlo al congelar sería mentir sobre la frescura,
que es el dato por el que existe la vista.

#### El guardián

`check-ventana` corre al final de `run-all`, **avisa y no bloquea**, y mira las
cuatro maneras de que una obra congelada envejezca sin que nadie se entere:
firma divergente, congelada sin filas, sello no vigente y completa vencida.
Marcador `[F025-VENTANA-KO]`; **sin desplegar
`infra/97_create_alert_ventana.ps1` es mudo**, y ese es el precio declarado de
no bloquear.

**Un verde sobre cero obras es un KO.** Confundir «no hay nada malo» con «no he
podido mirar» es el modo de fallo exacto que estos guardianes existen para
eliminar, y le pasó de verdad a `check-cobertura` el 02-sep, con
`stg.plan_mensual` truncada: las dos consultas devolvieron cero filas y dijo OK.
Se arregló en F-025, y `check-ventana` nació con la regla puesta.

#### Cuatro ajustes, y la ventana nace apagada

`PG_VENTANA_ACTIVA` (**false** por defecto), `PG_VENTANA_MESES` (12),
`PG_VENTANA_DIA_COMPLETA` (6 = domingo) y `PG_VENTANA_RESCATE` (off). Mientras
esté apagada, el contenido publicado es exactamente el de hoy; lo que **no**
vuelve es el `TRUNCATE`, porque borrar y reescribir todas las obras deja el
mismo resultado y además sobrevive a un tramo que falle.

### Coherencia ante cargas truncadas (F-024)

El 2026-08-18 la primera carga real lanzada desde el job murió por
`DeadlineExceeded` a las dos horas justas, en el tramo 39/60 del stage. `mart`
no llegó a tocarse, así que las vistas siguieron enseñando el build anterior
completo; pero `_meta.etl_runs` se quedó con dos filas `RUNNING` huérfanas para
siempre y `stg.plan_mensual` a medias. Destapó tres huecos: una muerte externa
del proceso no deja rastro honesto, nada impide construir sobre un `raw`
MEZCLADO, y el consumidor no tiene forma de saber si lo que ve es de anoche o
de hace tres días.

**No se hace nada atómico.** Una transacción de tres horas en el `B1ms` es
exactamente lo que reventó el 09-ago, y F-019 la troceó a propósito. La
coherencia se garantiza por **verificación** y **visibilidad**:

- **Identidad de ejecución.** Todo comando que ESCRIBE genera un `batch_id`
  (`YYYYMMDDTHHMMSSZ-xxxxxx`, dominio puro en `domain/ejecucion.py`) y lo
  estampa en cada fila que deja en `_meta.etl_runs`. El formato se ordena
  cronológicamente **como texto**, así que un `ORDER BY batch_id` sale ordenado
  sin parsear nada. El histórico anterior queda con `batch_id` a `NULL`: la
  columna se **añade**, la tabla no se recrea.
- **Filas huérfanas → `ABORTED`.** Al arrancar, antes de ejecutar ningún paso,
  todo comando que escribe cierra las filas que siguen en `RUNNING` con el
  motivo, la ejecución que las marcó y la hora. Toda `RUNNING` que exista al
  arrancar es de otro proceso por definición. Si la marca falla, se avisa y se
  **continúa**: es contabilidad, y el paso siguiente fallará por sí mismo si la
  BBDD no está.
- **Dos puertas, ambas ANTES de escribir nada.** `build_stg` exige que TODAS
  las tablas declaradas en `tables_sigrid.yaml` provengan del **mismo** batch
  terminado en `SUCCESS`; `build_mart` exige que la fila más reciente de
  `build_stg%` sea el **paso** completo, no un sub-paso ni un tramo. El
  veredicto es dominio puro (`domain/coherencia.py`) y queda registrado en
  `_meta.etl_runs` (`build_stg.puerta_raw`, `build_mart.puerta_stg`) pase lo
  que pase. Que vayan primero no es un detalle de orden: `stg` empieza con
  `TRUNCATE` y `mart/01_ddl.sql` con un `DROP`, y eso no se deshace porque el
  step devuelva `FAILED` después.
- **`--sin-puerta`, solo en los comandos sueltos.** `stage` y `build-mart` la
  admiten; `run-all` **no**, porque a medianoche no hay nadie delante para
  valorar si saltársela es razonable. Con la opción, la puerta se evalúa
  igualmente y su fila queda `SKIPPED` con el veredicto dentro: lo que esa fila
  cuenta es que el build se hizo **sin** puerta, no lo que la puerta habría
  dictaminado.
- **Dos vistas en `_meta`**, derivadas de la tabla que ya escriben todos los
  pasos, sin tablas nuevas que mantener: `v_raw_state` (de qué carga viene cada
  tabla de `raw`) y `v_frescura` (último OK y último intento por paso, **por
  separado**: un `build_mart` que falló esta noche deja `mart` con lo de ayer y
  el consumidor necesita las dos noticias). Las leen por igual la puerta, el
  MCP y Power BI. Ninguna toca `raw`, `stg` ni `mart`: cero coste sobre el
  servidor compartido.
- **Diagnóstico y alerta.** `check-coherencia` y `check-frescura` son de solo
  lectura (`timings` también: ve las huérfanas y **avisa**, no las marca). Y
  `infra/95_create_alert_frescura.ps1` crea una regla de consulta programada
  que dispara si en `frescuraUmbralHoras` (30) no hay ninguna línea de log del
  job diciendo que `build_mart` terminó en `SUCCESS`. Vigila desde **fuera**
  del ETL, así que «el job no lo hizo» dispara igual que «el job murió».

**La ingesta hace commit por PÁGINA, no por tabla** (DA-8, confirmado leyendo
`copy_rows` el 2026-08-18). `truncate_table` y cada página de 10.000 filas
abren su propia conexión, y por tanto su propia transacción. Consecuencia para
cualquier post mortem futuro: una muerte a mitad de tabla la deja **truncada y
parcial**, no intacta. Donde se dijo «la ingesta es transaccional por tabla, lo
cargado se conserva» se dijo mal. La puerta de F-024 no depende de ello: la
marca de «tabla ingerida» solo se escribe cuando la tabla termina en `SUCCESS`,
así que una tabla parcial queda con su última fila en `RUNNING` → `ABORTED` y
la puerta la rechaza igual.

### El datamart se explica solo (F-006)

El datamart publica **su propia semántica dentro de la base**: qué significa
cada objeto y cada columna, qué grano tiene, qué trampas hay que respetar al
leerlo y qué preguntas de negocio contesta. No es documentación para personas:
es un **contrato de datos** que un agente conectado por MCP lee por SQL, sin
poder preguntarle a nadie si algo no encaja.

- **La fuente son los YAML de `config/diccionario/`**: uno por esquema —los
  nueve del datamart— más `00_global.yaml`, que lleva las reglas duras
  transversales, los ejes, las convenciones de nombre y la batería de preguntas
  de aceptación. Están en este repositorio a propósito: qué significa
  `mart.fact_seguimiento_mensual` lo sabe quien escribió el SQL que la
  construye, y cualquier otro sitio se desincroniza. Por eso la ficha se
  actualiza en el mismo trabajo que el objeto (`docs/CONVENTIONS.md`).
- **El paso `publicar_diccionario`** los carga, valida, deriva los avisos y los
  escribe. Va dentro de `run-all`, **entre los cuatro build de negocio y
  `apply_grants`**, y ese orden no es cosmético: `apply_grants` concede `SELECT` sobre lo que hay
  en `_meta` en ese instante, así que publicar después dejaría las tablas del
  contrato colgando solo de los privilegios por defecto. Suelto, el comando es
  `python main.py publicar-diccionario`.
- **El contrato en `_meta` son cuatro tablas y una vista.** `_meta.diccionario`
  (una fila por objeto documentado, con la ficha entera en `JSONB` y en
  columnas lo que se filtra barato); `_meta.diccionario_reglas` (las reglas
  duras que no son de ningún objeto en particular);
  `_meta.diccionario_contexto` (los bloques de contexto, que crecen **por
  filas**, no por columnas); y `_meta.diccionario_publicacion`, una única fila
  con `version`, `hash_fuente` y los recuentos. Encima, `_meta.v_diccionario`
  es la vista plana que consulta el cliente.
- **La publicación es atómica**: `DELETE` + `INSERT` dentro de UNA transacción,
  así que quien consulte mientras se publica ve el diccionario anterior
  completo o el nuevo completo, nunca uno a medias. **Nunca `DROP` ni
  `TRUNCATE`**, y nunca quitar o reordenar columnas de la vista: eso exige un
  `DROP VIEW`, y un `DROP` se lleva por delante los `GRANT` del rol de lectura.
  Las reglas de compatibilidad completas están en la cabecera de
  `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql`.
- **Quien lo consume es `mcp-bbdd`**, un servicio con su propio repositorio, y
  lo hace **por SQL** con el rol de solo lectura `mcp_sigrid_dm_ro`. No hay API
  que versionar ni fichero que exportar: la base es la interfaz, y por eso un
  cambio en esas cinco formas es un cambio de API.
- **Dónde está la línea**: el MCP sabe de transporte, permisos, auditoría y
  multi-base; el significado del dato es del dueño del dato. Por eso el
  diccionario vive aquí y el servidor MCP no. Y el diccionario describe lo que
  el dato **es**, no cómo se decide con él: un procedimiento de negocio es otro
  repositorio.
- **La frescura no se declara, se une.** El `paso_etl` de cada ficha casa con
  `_meta.v_frescura.paso` (F-024), así que el consumidor sabe de cuándo es lo
  que está mirando sin tener que creerse un texto escrito a mano.
- **Verificación**: `python main.py check-diccionario` contrasta el diccionario
  del árbol contra el catálogo real de la base en las dos direcciones —objeto
  publicado sin ficha, ficha sin objeto, tipo que no casa— y avisa si lo
  publicado va por detrás del repositorio. La puerta offline de
  `bash harness/init.sh` solo puede exigir ficha **o** pendiente declarado.

Lo que este proyecto **expone al ecosistema** y quién lo consume está en
`azure-apps/datamart_seg_anual.md`, y no se duplica aquí.

### La nocturna construye TODO el datamart, y lo demuestra (F-047)

Hasta el 2026-08-28 `run-all` construía `raw → stg → mart` y nada más.
`cierre`, `compras`, `maestro` y `retenciones` se lanzaban a mano y podían
estar desfasados semanas. Los diez pasos de hoy, en orden:

```
ingest_raw → load_excel_aux → build_stg → build_mart
           → build_maestros → build_compras → build_retenciones → build_cierre
           → publicar_diccionario → apply_grants
```

- **`build_cierre` va después de `build_mart`, y es una dependencia de
  DESTRUCCIÓN, no de datos.** `mart/03_agg_categoria.sql` dropea
  `mart.fact_seguimiento_categoria` con `CASCADE`, y
  `cierre.v_pbi_planif_vs_real` cuelga de esa tabla en `pg_depend`: la
  nocturna la **destruía** cada noche y nadie la recreaba. Está declarado en
  `BuildCierreStep.depends_on`, no confiado al orden de la lista: un
  comentario se borra, el orden topológico obedece.
- **`apply_grants` sigue siendo el último.** Los cuatro build recrean vistas
  con `DROP` + `CREATE` y un `DROP` se lleva los `GRANT`. Y **no** depende de
  ellos a propósito: si `build_cierre` falla una noche, los permisos del MCP
  se reaplican igual. El precio es que un esquema puede quedarse atrás sin
  tumbar la carga, y por eso la regla dura `R-FRESCURA` del diccionario manda
  citar la frescura DEL PASO, no la del pipeline.
- **Los cuatro registran paso** en `_meta.etl_runs` con el `batch_id` de la
  noche. `build-compras` y `build-retenciones` no lo hacían —ejecutaban SQL en
  línea, sin step—, así que su fecha de build no era consultable por SQL
  mientras el diccionario mandaba citarla.
- **Coste medido** (2026-08-21, con el disco vigilado): +37,5 min sobre 2 h 46,
  de los que `build_cierre` se lleva el 74 %. El disco no se movió (57,92 % →
  57,93 % sobre un límite del 80 %): estos cuatro reconstruyen desde `raw` y
  `stg`, no acumulan como `plan_mensual`.

**El guardián.** `run-all` termina contrastando **lo que el SQL del
repositorio declara crear** contra `information_schema`, y sale con código 1
si falta algo. Es la pregunta que no hacía nadie: la puerta de `init.sh`
compara el SQL contra las fichas y `check-diccionario` compara las fichas
contra la base, y por el hueco entre las dos se coló F-047 durante semanas.
Suelto es `python main.py check-declarados`, de solo lectura. Lo que
legítimamente aún no toca construir se declara en
`config/objetos_pendientes.yaml`, mismo patrón y mismo trinquete que
`pendientes` en el diccionario: **objeto construido o pendiente declarado**, y
la lista solo baja.

## Infra

- `Dockerfile` en raíz. `infra/` con scripts PowerShell 5.1 (UTF-8 BOM, CRLF)
  numerados por orden de ejecución. Procedimiento y datos están separados:
  **los nombres de recurso viven solo en `infra/env/<entorno>.json`** y ningún
  `.ps1` escribe uno. Montar `sta` o `pro` es copiar ese fichero y ejecutar con
  `-Entorno <nombre>`; `00_vars.ps1` lo carga, lo valida y aborta antes de la
  primera llamada a `az` si falta un valor. Lo verifican los tests
  `test_f003_r1..r11` sin tocar Azure.
- **Ni la suscripción ni ningún secreto están en el repositorio.** La
  suscripción sale de `$env:AZ_SUBSCRIPTION_ID` o del contexto de `az`.
- `infra/sql/` contiene la provisión de `sigrid_dm` (base, roles, diagnóstico).
  Se ejecuta a mano con `psql`, nunca desde el ETL: usa bloques `$$`, que el
  troceador de sentencias de `postgres_client.py` no sabe manejar.
- Destino: **Container Apps Job programado** (`0 0 * * *` UTC desde el
  2026-09-06, antes `0 2 * * *`; siempre
  `run-all --full`) en un resource group propio del datamart, región
  `spaincentral`, con entorno **sin integración de red virtual** — así tiene IP
  de salida estática, que es lo que se autoriza en el firewall del Postgres.
  Tags de imagen fechados (`rYYYYMMDD-HHmm`), nunca reescritos.
- **Sin contraseñas en el job.** Corre con una **identidad gestionada asignada
  por el usuario** que tiene exactamente tres permisos: bajar la imagen del
  registro, leer el único secreto (la clave de `sigrid-api`) del Key Vault del
  proyecto y leer los Excels auxiliares del blob. Esa misma identidad es la que
  `AZURE_CLIENT_ID` señala dentro del contenedor.
- Orden de ejecución, pasos que exigen autorización del humano y consulta de
  logs: `infra/README.md`.
