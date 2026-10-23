# F-148 · Diagnóstico del «connection timeout expired» de la nocturna

> Redactado por el spec-author a partir del informe de exploración de la sesión
> del 2026-10-23 (solo lecturas: `_meta.etl_runs`, métricas de Azure Monitor del
> servidor, registro de actividad y Log Analytics del entorno del job). Sin IPs,
> identificadores de recurso, usuarios de BBDD ni secretos. Revisado con el
> humano el 2026-10-23, que eligió el enfoque 1 + 2 + 3 + 4.

## En un párrafo

El servidor no tiene la culpa. Durante los cortes tenía los créditos de CPU al
tope, la CPU al ~5 %, ~23 conexiones de 50, **cero** conexiones fallidas, y los
demás inquilinos conectaban con normalidad. Lo que ocurre es que **una conexión
nueva del job se queda colgada 130 s**, el `connect_timeout` POR DEFECTO de
psycopg 3, porque no configuramos ninguno, y no hay reintento. La ingesta abre
una conexión nueva por cada página de `sigrid-api` (~2.800 solo en `obrparpre`,
~3 por segundo al mismo destino). Las paradas de ~135 s existen desde el 24-09;
hasta el 16-10 se recuperaban solas; desde el 17-10 caen en la apertura y matan
`ingest_raw`. La causa de fondo no está demostrada; la hipótesis más fuerte es
la salida de red del entorno de consumo (SNAT compartido, sin VNet ni NAT).

## Hechos medidos

- **H1 · Código.** `IngestRawStep._ingest_one_table` llama a
  `PostgresClient.copy_rows` por página; `copy_rows` abre y cierra su conexión
  (TCP + TLS + SCRAM + `SET ROLE` + COPY + commit). `build_conninfo` no lleva
  `connect_timeout`; psycopg 3.3 aplica 130 s y lanza
  `ConnectionTimeout("connection timeout expired")`. Ningún reintento de
  conexión: la excepción sale del paso, `ingest_raw` queda FAILED, los build
  SKIPPED, el proceso sale con 1 y el job reintenta desde cero. El host resuelve
  a una sola dirección.
- **H2 · El 23-10.** Última página leída de `obrparpre` (p287) a las 00:04:42;
  `step_unhandled_exception` 130,05 s después, con la traza en
  `copy_rows → connection → _connect → psycopg.connect`. Tres segundos después
  otros pasos abren conexiones sin problema.
- **H3 · Noches con corte** (primer intento): 17, 18, 19, 22 y 23 de octubre;
  la página del cuelgue varía (287 a 1.670): no hay umbral fijo. Ningún
  «connection timeout expired» en `_meta.etl_runs` antes del 17-10.
- **H4 · No es la imagen ni el código.** La misma imagen pasó y falló en noches
  distintas; sin cambios en conexión ni ingesta desde septiembre.
- **H5 · No es el servidor.** Durante el cuelgue: créditos al tope, CPU ~5 %,
  21-27 conexiones activas de 50, `connections_failed` = 0, `is_db_alive` = 1,
  y las conexiones de los demás inquilinos (~14/min) siguen entrando. Sin
  operaciones de escritura sobre el servidor ni eventos de salud. El servidor no
  tiene categorías de log activadas: no hay logs suyos que leer.
- **H6 · El dato decisivo.** Huecos > 5 s entre páginas consecutivas de la misma
  tabla, 30 noches desde el 24-09 (~152.000 páginas): 12 huecos de **134,0 a
  135,5 s** que se recuperaron (dos de ellos el 21 y el 23-10) (en `obrparpre`, `dcopro`, `apu`, `dcaprodes`), y
  los 5 cortes. Fuera de eso, el mayor es de 36 s y la mediana 0,3-0,4 s.
  Ninguno del 9 al 16-10; desde el 17, alguno cada noche. Ni un reintento HTTP
  contra `sigrid-api` en todo el periodo.
- **H7.** Un único job de Container Apps en la suscripción (el nuestro); los
  entornos sin VNet y sin NAT Gateway.

Consulta de huecos (KQL, workspace de Log Analytics del entorno del job):

```
ContainerAppConsoleLogs_CL
| where Log_s has "sigrid_stream_page"
| extend j = parse_json(Log_s)
| project ts = todatetime(j.timestamp), page = toint(j.page), tabla = tostring(j.table), exec = ContainerGroupName_s
| order by exec asc, ts asc | serialize
| extend prev = prev(ts), prevexec = prev(exec), prevtabla = prev(tabla)
| where prevexec == exec and prevtabla == tabla
| extend gap_s = (ts - prev)/1s | where gap_s > 100
```

## Hipótesis

- **A (la más probable).** Un flujo TCP del job se queda sin tránsito ~130 s en
  la salida de red del entorno de consumo bajo el patrón de miles de conexiones
  cortas al mismo destino. Sin explicar: por qué no da el error de SYN de Linux
  y por qué desde el 17 caen en el connect.
- **B.** Las pausas que se recuperan son `sigrid-api` tardando; poco compatible
  con una duración tan constante. `sigrid-api` no tiene diagnóstico para
  contrastarlo.
- **Descartadas**: créditos/CPU/IOPS, mantenimiento o reinicio, `max_connections`,
  imagen/psycopg/código, DNS, firewall.

## Lo que falta medir (lo resuelve F-148 en parte)

1. Dónde se va el tiempo de cada página (`http_s`, `pg_connect_s`, `copy_s`) y
   psycopg en DEBUG en el connect: **dentro de F-148** (R14-R16).
2. Si el servidor llega a ver la conexión colgada: requiere activar sus logs,
   **escritura sobre el servidor compartido, decide el humano**.

## Opciones valoradas

1 conexión por tabla · 2 `connect_timeout` corto + reintento · 3 keepalives y
`tcp_user_timeout` con reintento de página · 4 reintento de tabla · 5 reanudar ·
6 subir `page_size` · 7 mover la hora (no recomendado) · 8 VNet + NAT Gateway
(desproporcionado de momento). Elegido por el humano: 1 + 2 + 3(+4 vía
reanudación) + 5 + instrumentación. Detalle en
`specs/F-148-robustez-nocturna/design.md`.
