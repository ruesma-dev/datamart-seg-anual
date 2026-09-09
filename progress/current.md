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

**Las tres features de la sesion estan CERRADAS.** Lo abierto es el backlog,
mas F-052, que sigue `blocked` y ya no espera a nadie.

| Prioridad | Feature | Estado | Que es |
|---|---|---|---|
| 4 | **F-071** | spec en curso | La IA ve 583 obras cuando solo 349 tienen datos: marcarlas y declararlo, no borrarlas. Y **subir la direccion de la obra a la capa de consumo**, que hoy solo existe en `raw` y el MCP no lee `raw`. |
| 5 | **F-070** | `pending`, spec escrita | Auditar la **calidad** de las fichas del diccionario, acotada a los ocho esquemas que el MCP lee. |
| 6 | **F-034** | `pending` | Power BI deja de leer de local y pasa a leer el datamart de Azure. |

Detras, F-057 (7) y F-056 (8), las dos ya sin ingesta dentro porque F-066 se la
llevo.

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

**El diccionario del árbol está en 130 objetos, 822 columnas y 47 fichas de
consumo**, publicado en `_meta` como **versión 16** (hash `9140b14dc991`,
2026-09-09 07:31 UTC, cobertura de columnas 100,0 %). El commit de cierre del 04
se llevó por delante esta frase y dejó `init.sh` en rojo: el test
`test_f006_los_recuentos_de_current_son_los_de_hoy` existe justo para que estos
recuentos no envejezcan en silencio. **Si vuelves a reescribir la cabecera de
este fichero, los tres números se quedan.**

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
