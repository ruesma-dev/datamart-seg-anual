<!-- progress/incidencia_nocturna_20260907.md -->
# La nocturna del 2026-09-07 falló por una base nueva en el servidor compartido

**Ejecución `caj-datamart-seg-dev-29812320`, arrancada a las 00:00:00 UTC del
lunes 07 y terminada en `Failed` a las 01:26.** Era la primera nocturna acotada
de F-025, la que tenía que dar T31b y T34.

## La causa, en una línea

Un inquilino nuevo del Postgres compartido, la base **`facturas`**, sobre la que
nuestro rol **no tiene privilegio `CONNECT`**, y la puerta de disco de F-019
suma el tamaño de **todas** las bases del servidor antes de cada tramo.

```
"motivo": "no se pudo medir la ocupación del disco antes del tramo 1/21:
           permission denied for database facturas. No se ejecuta a ciegas.",
"obras_reconstruidas": 0
```

## LA BASE ESTÁ INTACTA, y no por suerte

**La protección funcionó exactamente como se diseñó.** `medir_ocupacion_disco_pct`
propaga la excepción a propósito, y el build aborta **antes del tramo 1/21** en
vez de seguir a ciegas. Comprobado en la base a las 01:30 UTC:

| tabla | filas | lectura |
|---|---|---|
| `stg.plan_mensual` | 29.772.701 | intacta, las del sábado |
| `mart.fact_seguimiento_mensual` | 5.359.591 | intacta |
| `_meta.obra_build` | 920 obras | las congeladas se marcaron; **0 reconstruidas** |

`build_cierre`, `publicar_diccionario` y `apply_grants` quedaron `SKIPPED` por la
puerta de F-024, que impide construir sobre un `stage` fallido. **Lo que hay
publicado es el datamart del sábado 05**: no hay pérdida de dato, hay falta de
refresco.

El job reintentó una vez, por `replicaRetryLimit: 1`, y falló igual. Las dos
pasadas ingirieron `raw` entero, 20,1 M filas cada una, en 28 y 27 minutos.

## Por qué esto no había pasado antes

`postgres_client.py:68-72` lo dice con todas las letras, y era verdad cuando se
escribió:

> `pg_database_size` sobre otra base exige privilegio `CONNECT`; el rol del ETL
> lo tiene (frontera medida en F-005).

Ha dejado de serlo. El censo de bases del servidor, medido hoy:

| base | dueño | ¿podemos conectar? |
|---|---|---|
| `albaranes`, `partes`, `dedicacion` | `ruesmaadmin` | sí |
| `postventa` | `postventa_app` | sí |
| `sigrid_dm` | `sigrid_dm_etl` | sí |
| **`facturas`** | **`facturas_owner`** | **NO** |

`facturas` no aparece en `azure-apps/red_postgresql_compartido.md`, que sigue
hablando de cinco inquilinos. Es un proyecto nuevo del que este repositorio no
sabía nada, y ha tumbado nuestra nocturna sin tocarnos una tabla.

## Qué NO se ha hecho, y por qué

No se ha tocado ni una línea de código. La regla del arnés es no improvisar
workarounds ante un fallo inesperado: se anota y se para. Además la salida
correcta **no es evidente** y cruza la frontera del proyecto.

## Las tres salidas, para que decida el humano

1. **Pedir `CONNECT` sobre `facturas`** a quien administre el servidor. Una
   línea de SQL del admin. Deja la medición completa y correcta, que es lo que
   la puerta necesita. **Es la salida limpia**, pero depende de otro equipo y no
   la puede ejecutar este repositorio.
2. **Filtrar por permiso y avisar**: `... FROM pg_database WHERE
   has_database_privilege(current_user, datname, 'CONNECT')`, más un aviso con
   el nombre de las bases no medidas. La nocturna deja de morir, pero **la
   medición pasa a ser parcial y subestima la ocupación**, que es justo el
   riesgo que la puerta vigila: el 2026-08-09 el disco llegó al 93,4 % y el
   servidor entró en solo lectura. Si se elige esto, conviene bajar el umbral
   para compensar lo que no se ve.
3. **Las dos**: filtrar para que la nocturna no dependa de un tercero, y pedir
   el permiso para que la medición vuelva a ser completa.

**Recomendación del líder: la 3.** La 1 sola nos deja parados hasta que responda
otro equipo, y la 2 sola degrada en silencio una protección que ya salvó el
servidor una vez.

## Lo que esta avería deja pendiente

* **T31b y T34 de F-025 siguen sin medir.** La feature no se puede cerrar.
* **El datamart no se refresca** hasta que esto se arregle: fallará todas las
  noches, porque la causa es permanente.
* **`azure-apps/red_postgresql_compartido.md` miente**: cinco inquilinos donde
  hay seis. Hay que actualizarlo con `facturas` y con lo que se decida.
* **El comentario de `postgres_client.py:68-72`** afirma una frontera que ya no
  se cumple; se corrige con el arreglo, sea cual sea.

---

## RESUELTO el 2026-09-07 (y un segundo hallazgo, peor que el primero)

### 1. El permiso: `pg_read_all_stats`, no `CONNECT`

El humano concedió a `sigrid_dm_etl` el **rol predefinido
`pg_read_all_stats`**, que es mejor que la salida 1 de arriba:

* permite `pg_database_size` sobre **cualquier** base **sin `CONNECT`** y **sin
  dar acceso a los datos** de esa base;
* **cubre las bases que se creen en el futuro**, que es lo que de verdad falló.
  Pedir `CONNECT` sobre `facturas` habría arreglado el lunes y nos habría dejado
  esperando la próxima base nueva.

Verificado el mismo día: `pg_has_role('sigrid_dm_etl','pg_read_all_stats',
'member')` devuelve `t` y `SELECT SUM(pg_database_size(datname)) FROM
pg_database` devuelve las **nueve** bases del servidor sin error.

Así que **la salida 2 (filtrar por permiso) no se implementa**: habría dejado la
medición parcial y subestimando la ocupación, que es justo el riesgo que la
puerta vigila. El SQL de `SQL_OCUPACION_DISCO` se queda **tal cual**.

El comentario de `postgres_client.py` que afirmaba la frontera vieja ya está
reescrito con lo que hoy es cierto.

### 2. El hallazgo: la puerta medía contra un disco que no existe

Al comprobar el arreglo salió algo que nadie estaba buscando. El disco del
servidor **se amplió de 32 a 64 GB el 2026-08-29**, pero el job **no declaraba
`PG_DISCO_TOTAL_GB`**, así que la puerta usaba el defecto de
`config/settings.py`, que seguía diciendo 32.

| medida | contra 32 GB (lo que veía) | contra 64 GB (lo real) |
|---|---|---|
| 25.537.336.573 bytes ocupados | **74,32 %** | **37,16 %** |

El umbral al que la puerta **aborta el build** es el 80 %. Estaba a **menos de
seis puntos** de tumbar la nocturna todas las noches sin que nada estuviera mal,
y la ingesta de `raw` pendientes de F-066 añade ~0,9 GB, que la habría dejado en
el 77 % ficticio. Es decir: arreglado el permiso, la nocturna habría seguido
muriendo en semanas, por otra causa y con el mismo síntoma.

Arreglado en tres sitios, para que no vuelva a divergir:

* el defecto de `disco_total_gb` pasa a **64**, con nota fechada;
* `infra/env/dev.json` declara `discoTotalGb: 64` y **`80_create_job.ps1` la
  inyecta** como `PG_DISCO_TOTAL_GB` (antes no la pasaba nadie);
* un test nuevo ata las dos, igual que hace F-024 con el umbral de frescura.

De paso se corrigieron los sitios donde el repositorio afirmaba «32 GB» o «el
disco compartido con `albaranes` y `partes`»: hoy son **64 GB y seis
inquilinos**.

## Lo que sigue pendiente

* **Actualizar el job de Azure.** Nada de esto llega a producción hasta que se
  vuelva a pasar por `80_create_job.ps1` (o se fije la variable en el job):
  `85_update_job.ps1` solo cambia la imagen y **no toca el entorno**. Mientras
  tanto el job sigue midiendo contra 32 GB. Lo hace el humano; el implementer no
  ha ejecutado ningún `.ps1` ni ningún `az`.
* **`azure-apps/red_postgresql_compartido.md`** sigue hablando de cinco
  inquilinos donde hay seis, y no menciona `pg_read_all_stats`. Lo actualiza el
  líder: cruza la frontera de este repositorio.
* **T31b y T34 de F-025 siguen sin medir**: hacen falta una o dos nocturnas
  buenas con el job ya actualizado.
