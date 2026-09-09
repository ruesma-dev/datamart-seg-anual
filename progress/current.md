<!-- progress/current.md -->
# Estado actual · 2026-09-09 (miercoles; F-025, F-068 y F-066 cerradas)

> **PURGADO tres veces.** C2 pide que este fichero describa **solo la sesion
> activa**. El 2026-09-06 bajo de 1.263 a 638 lineas; el 2026-09-09 (pasada 3
> del review de F-066) se le quitaron las 253 lineas de la fase 7 de F-025; y
> hoy, al cerrar F-066, se retiran sus tres secciones y la de la averia
> nocturna del 07, ya resuelta. **Nada se pierde**: F-025, F-068 y F-066 tienen
> su resumen en `progress/history.md`, y el detalle vive en los informes
> `impl_*`/`review_*`/`incidencia_*` de `progress/` y en las specs.

## POR DONDE SE SIGUE EN LA PROXIMA SESION (leer esto primero)

**F-025, F-068, F-066 y F-072 estan CERRADAS**, y **F-071 esta RETIRADA** (ver
su seccion abajo: no se borra nada). El censo de F-072 quedo `done` en
`e52c5f9`, y **su primer descendiente, F-074, esta en curso**. Lo abierto es el
backlog, mas F-052, que sigue `blocked` y ya no espera a nadie.

| Prioridad | Feature | Estado | Que es |
|---|---|---|---|
| 4 | **F-072** | `done` (`e52c5f9`) | El censo semantico: que hay dentro de las 31 tablas que se ingieren cada noche y no consume nadie. Entregable: `progress/explore_F-072_catalogo.md` + cuatro informes de bloque. **De aqui salen F-073 y F-074.** |
| 5 | **F-073** | `pending` | Construir con lo que el censo encontro: tablas procesadas nuevas y enriquecimiento de las actuales, **sin borrar ni filtrar nada**. |
| 6 | **F-074** | **en curso, implementacion entregada** | La ingesta que el censo destapa: **9 tablas** que faltan, la carga incremental falsa de `com`/`comlin`/`comprv` y el `tex` excluido de `prvcer`. Informe: `progress/impl_F-074.md`. |
| 7 | **F-070** | `pending`, spec escrita | Auditar la **calidad** de las fichas del diccionario, acotada a los ocho esquemas que el MCP lee. |
| 8 | **F-034** | `pending` | Power BI deja de leer de local y pasa a leer el datamart de Azure. |

Detras, F-057 (9) y F-056 (10), las dos ya sin ingesta dentro porque F-066 se
la llevo, y las dos **con su ficha corregida por el censo**.

**LO QUE F-074 DECIDIO, Y POR QUE NO ES LO QUE LA PROPUESTA DECIA.** La
propuesta que llego al implementer era «recarga completa nocturna de las cuatro
pequeñas (`cet`, `pro`, `reshor`, `emphis`) y carga por `ide` para las dos
grandes», porque **solo 3 de las 9 tienen `tiemod`** --`auxdpt`, `auxhor`,
`auxrestip`-- y se daba por hecho que las otras seis cargarian por `MAX(ide)` y
que **una fila modificada en el origen no volveria a bajar nunca**.

**Esa premisa es falsa, y esta comprobado en la fuente que gobierna el hecho.**
El `CMD` del `Dockerfile` arranca `run-all --full`, o sea `TRUNCATE` y recarga
entera de **todas** las tablas cada noche (`ingest_raw_step.py`, lineas 271-275).
`incremental_column` **no es un interruptor de modo de carga**: lo unico que
decide es si `copy_rows` rellena `_source_tiemod` con el sello del origen. La
carga por `MAX(ide)` solo ocurre lanzando `ingest` a mano **sin** `--full`.

Es el error exacto que F-006 cometio dos veces seguidas --su septima pasada lo
derivo de `tables_sigrid.yaml` y su octava de `ingest_raw_step.py`, y las dos
salieron falsas-- y para el que existe `tests/test_f006_fuente_que_gobierna.py`.

**Consecuencia**: no hace falta recarga completa por tabla, el ETL no sabe
hacerla y F-074 **no la inventa**. Las seis quedan con `incremental_column:
null` **declarado y explicado en el propio YAML**, no solo en un informe.

**Coste medido de las nueve**: 1.341.365 filas nuevas por noche, **+155 MB**
estimados sobre los 25 GB actuales (disco de 64 GB, +0,6 %) y **+3 a 6 min** de
ventana sobre las 3 h 45 de hoy. El 95 % de eso son `dcaprodes` (850.985) y
`ctrprodes` (424.475).

**F-052 sigue `blocked`** y su desbloqueo ya no depende de F-025. Ver su seccion
abajo: es volver a su rama y relanzar `check-cobertura` alli.

## LO QUE LAS TRES FEATURES CERRADAS DEJAN VIVO

Su resumen esta en `progress/history.md`. Aqui solo lo que sigue pendiente de
alguien:

1. **`infra/sql/02_roles.sql` no lo ejecuta ningun test** (de F-068): solo se
   comprueba su texto, y esta corregido en dos sitios que solo prueba `psql`.
   **Antes de volver a provisionar un rol desde cero, ejecutarlo contra una base
   de prueba.**
2. **La revocacion de datos personales del MCP es TEMPORAL** (F-068): vuelve en
   cuanto el MCP tenga control por usuario. Decision del humano, escrita en
   cinco sitios para que nadie la lea como permanente.
3. **El umbral de tolerancia de `check-raw-recuentos`** (F-066): 0,05 % de
   `obrparpre` son ~6.940 filas. **Revisarlo si baja `page_size` o aparece una
   tabla mayor.**
4. **F-069**, fichada: `harness/mutacion.py` no muta constantes `float` ni la
   division. Uno de los seis sitios ciegos es `TOLERANCIA_DERIVA_PCT = 0.05`, el
   numero del que depende entero el criterio de F-066.
5. **F-065** mide el bloat sostenido tras siete noches acotadas (de F-025, T33).
6. **Un superviviente de mutacion de F-025, aceptado y sin fichar todavia**
   (hallado por F-074, pasada 2): `main.py:543`, el `is_flag` de
   `--reconstruir-todo` en `run-all`. Sin el, click infiere `BOOL` y
   `run-all --reconstruir-todo` sale con **exit 2** —medido—; la nocturna
   (`run-all --full`) y el rebuild del domingo por antiguedad **no se enteran**.
   Lo dejan vivo sus propios tests, T15 de `tests/test_f025_cli.py`, que
   comprueban que la cadena salga en `--help` y que el callback la cablee, pero
   **no invocan la opcion por el parser de click**. El arreglo, tres lineas, esta
   escrito en `progress/mutacion_F-074.md` §8. **F-074 no lo tapa: no es su
   codigo ni su fichero de tests.** Decidir si se ficha o si entra en F-074.

**El diccionario del árbol está en 139 objetos, 822 columnas y 47 fichas de
consumo** tras las nueve fichas de `raw` que añade F-074, y el árbol declara
**versión 17**. Lo publicado en `_meta` sigue siendo la **versión 16** (hash
`9140b14dc991`, 2026-09-09 07:31 UTC, cobertura de columnas 100,0 %): publicar
contra Azure es una escritura y la autoriza el humano, no un agente. El commit de cierre del 04
se llevó por delante esta frase y dejó `init.sh` en rojo: el test
`test_f006_los_recuentos_de_current_son_los_de_hoy` existe justo para que estos
recuentos no envejezcan en silencio. **Si vuelves a reescribir la cabecera de
este fichero, los tres números se quedan.**

## VERIFICACIONES MANUAL (humano) PENDIENTES DE F-074

Ninguna la puede ejecutar un agente: **todas escriben contra Azure o dependen de
que la imagen nueva se haya desplegado y la nocturna haya corrido**. Van en este
orden, y la 2 no significa nada antes de la 1.

1. **Desplegar la imagen y dejar correr una nocturna.** Sin eso, las nueve
   tablas no existen en `raw` y las comprobaciones de abajo miden el mundo de
   ayer. Recordatorio de `progress/` : la nocturna llego a correr una imagen de
   diez dias antes sin que nadie lo notara, asi que **comprobar el tag de la
   imagen del job**, no solo que el repositorio este en verde.

2. **Que la ingesta trajo lo que debia**, con las nueve dentro:

       python main.py check-raw-recuentos

   Tiene que salir con **codigo 0**. Es el criterio 4 de `acceptance`. Manda 65
   consultas de recuento a Sigrid, nueve mas que antes.

3. **Que el rol del MCP NO lee la nomina.** Es el criterio 3, y **no vale
   suponerlo**: F-068 existe porque un `ALTER DEFAULT PRIVILEGES` reponia el
   permiso en silencio. Contra el Postgres de Azure, en solo lectura:

       SELECT table_name, grantee, privilege_type
       FROM information_schema.table_privileges
       WHERE table_schema = 'raw'
         AND table_name IN ('emp','res','reshor','emphis')
         AND grantee = 'mcp_sigrid_dm_ro';

   El resultado correcto es **cero filas**. Si aparece alguna, la revocacion no
   sobrevivio a la noche.

4. **Que el diccionario del arbol casa con el catalogo real:**

       python main.py check-diccionario

5. **Publicar el diccionario** (version 17, con las nueve fichas nuevas). Es una
   **escritura contra Azure**: la autoriza el humano, no un agente.

       python main.py publicar-diccionario

## Estado del servidor · sigue en B2s TEMPORALMENTE

`psql-albaranes-rs9k2`, **`Standard_B2s`** desde el 2026-09-05 a las 17:21 UTC.
**La bajada a `Standard_B1ms` sigue pendiente, con fecha limite 2026-09-20**
anotada en `azure-apps/` para preguntar si se olvido. Al bajar, el saldo de
creditos se resetea a 60.

**LOS 144 CREDITOS ERAN FALSOS** (corregido el 2026-09-05). La tabla oficial de
la serie Bv1 da para el `B1ms`: baseline 20 % de 1 vCPU, **12 creditos/hora** con
la CPU ociosa y **288 de tope**; el `B2s` da 24/h y **576**. La metrica lo
confirma: el servidor ha estado a 300 el 8-ago y 277 el 15-ago. Consecuencia:
cuando el saldo marca 57 no estamos al 40 % del deposito, sino al 20 %. **Todas
las cuentas de creditos anteriores al 05-sep estan hechas sobre un techo
equivocado.**

**Como se consulta el saldo de verdad**, que tambien costo descubrirlo: hay que
pedirlo con **`--interval PT1M`** y una ventana corta. Con `PT15M` la API
devuelve los primeros puntos del rango y parece que la metrica lleva 13 horas de
retraso; no es cierto, llega al minuto.

```bash
az monitor metrics list --resource psql-albaranes-rs9k2 --resource-group rg-albaranes-dev \
  --resource-type Microsoft.DBforPostgreSQL/flexibleServers \
  --metric cpu_credits_remaining --interval PT1M --aggregation Average \
  --start-time $(date -u -d '-50 minutes' +%Y-%m-%dT%H:%M:%SZ) -o tsv
```

**Que costaria tener mas** (precios reales de Spain Central, EUR, 730 h/mes,
consultados el 05-sep en la API de tarifas de Azure):

| via | que da | coste |
|---|---|---|
| esperar | ~12 creditos/h con el servidor ocioso; lleno en ~19 h | 0 € |
| **B2s** permanente | 2 vCPU, 4 GB · 24 creditos/h, tope 576 · IOPS 1.280 | 49,86 €/mes frente a 12,48 → **+37,38 €/mes** |
| B2s solo de noche | lo mismo durante la ventana | ~**+12,3 €/mes** |
| General Purpose D2ds_v5 | 2 vCPU, 8 GB, **sin creditos** | 132,86 €/mes → **+120,38 €/mes** |

En Spain Central **solo existen B1ms y B2s** en Burstable: el salto siguiente es
ya General Purpose. Y ojo con escalar: **reinicia el servidor** —compartido con
albaranes, partes, remesas, el portal y facturas— y **probablemente resetea el
saldo de creditos**; eso habria que medirlo antes de fiarse.

**El disco esta en 64 GB** desde el 2026-08-29, y el job lo declara desde el
07-sep (`PG_DISCO_TOTAL_GB`). Durante nueve dias la puerta de F-019 midio contra
32 GB y veia un 74,32 % donde la ocupacion real es del 37,16 %: aborta al 80 %,
asi que estaba a menos de seis puntos de tumbar la nocturna cada noche sin que
nada estuviera mal. Detalle en `progress/impl_disco_64gb.md` y
`progress/incidencia_nocturna_20260907.md`.

## F-052 · SIGUE BLOQUEADA, y el motivo REAL no era el que se penso

Su unico pendiente es certificar `check-cobertura` en verde. Lanzado el 04 sobre
`stg` ya completa: **58 combinaciones miradas, 37 cubiertas** —antes decia CERO,
asi que **el guardian ya no miente**, que era el bloqueo de verdad— pero sale
**KO** con 20 obras invisibles y 294 filas huerfanas.

**Y eso tiene explicacion, comprobada:** el `check-cobertura` se lanzo desde la
rama de F-025, que **NO contiene los cinco commits de cierre de F-052**
(`ec516bd`..`fa2312c`, que viven solo en `feature/F-052-partidas-huerfanas`).
El fichero de excepciones de esa rama es el viejo: **10 entradas y con los
`tipo` sin corregir**. En la rama de F-052 estan las 23 y los tipos arreglados.

**Como se cierra F-052:** volver a su rama, relanzar `check-cobertura
--timeout 900` **alli**, y si da codigo 0, al reviewer y a `done`. **No se
mezclan las dos ramas** sin decidirlo. Ojo con F-071 y F-053, que tocan
`stg.obras` y su desempate `rn=1`.

## F-072 · CERRADA · el censo semantico de las 31 tablas que nadie consume

**F-071 ESTA RETIRADA.** El humano la paro el 2026-09-09 al leer su spec:
«**no vamos a borrar nada de momento, vamos a seguir dejando todo. Quitamos
esta feature.**» Ya no esta en `harness/features.json`. Su carpeta
`specs/F-071-obras-sin-datos/` se conserva con un banner de RETIRADA, solo por
lo que costo medir. **No se implementa nada de ella.**

**Lo que NO se hace, y conviene que quede escrito para que nadie lo reproponga
dentro de tres meses:** no se borran las 472.890 filas huerfanas de
`stg.presupuesto` (390.028) y `stg.plan_mensual` (82.862); **no se acota el
censo de la ventana**, que era precisamente lo que las dejaba huerfanas; y no
se filtra ni se oculta ninguna obra en ninguna vista. El marcado de obras sin
datos sobrevive **como enriquecimiento**, no como filtro.

**EL HECHO QUE ABRE F-072**, medido el 2026-09-09 cruzando
`config/tables_sigrid.yaml` contra todo el SQL de
`etl_sigrid/infrastructure/postgres/sql/`:

| tablas ingeridas cada noche | las consume algun build | **no las consume nadie** |
|---|---|---|
| 56 | 25 | **31** |

Las 31: `apa`, `apu`, `asi`, `auxefp`, `auxobrtca`, `auxpag`, `auxpronat`,
`com`, `comlin`, `comprv`, `conact`, `conest`, `confir`, `ctrrec`, `cua`,
`dcarec`, `dcfprodes`, `dcfrec`, `dco`, `dcopro`, `dcorec`, `deffir`, `dnc`,
`dncpro`, `emp`, `hmo`, `hmores`, `obrprv`, `prvcer`, `prvobrpag`, `res`. Se
ingieren cada noche, ocupan disco y **la IA no las ve**, porque el MCP solo lee
las capas procesadas.

**EL PLAN, EN DOS FEATURES**, aprobado por el humano:

* **F-072 (`done`, prioridad 4)** — entender. Catalogo tabla por tabla: que
  es, grano, volumen, **% informado columna a columna**, por donde se une, y
  que preguntas de negocio permitiria responder que hoy no se pueden
  responder. **Solo lectura de principio a fin.** Cuatro bloques tematicos,
  un informe `progress/explore_F-072_*.md` por bloque, mas un catalogo que los
  une y los enruta a las features de construccion.
* **F-073 (pendiente, prioridad 5)** — construir. **Su contenido lo fija
  F-072.** Lo unico que ya se sabe que entra es la direccion de la obra en la
  capa de consumo y las marcas de obra con/sin datos. Buena parte del resto
  caera en features de dominio que YA existen en el backlog: F-055, F-056,
  F-057, F-058, F-067, F-038, F-037 y F-040.

**EL TOPE DE LA PASARELA ESTABA MAL EN MI CABEZA, y lo corrigio el humano.**
`azure-apps/sigrid_api.md` §4.1: la instancia `dev` tiene `MAX_ALLOWED_ROWS` en
**500.000**, no en 1.000 (ese es el tope por codigo, que dev sobreescribe), y
`MAX_QUERY_TIMEOUT_SECONDS` en **230**. Los 230 s **si** son un techo duro: es
el balanceador de Azure y subir el ajuste no da mas tiempo. El cliente es
`SigridApiClient.leer_sql(sql, parameters, max_rows)`.

**HALLAZGOS DE F-071 QUE SOBREVIVEN** (medidos, no supuestos): de los ocho
campos de direccion de `raw.obr`, **tres no son la direccion de la obra**
—`diride` es el **director de obra**, `perdir` su **persona de contacto** y
`entdiride` la direccion **del cliente**—; y los dos ejes de agrupacion que
faltaban, **municipio** y **provincia**, viven en `raw.auxmun` y `raw.auxpro`
via `obr.munide` y `obr.proide`. Lo demas, en
`specs/F-071-obras-sin-datos/design.md` §1.
