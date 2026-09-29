<!-- progress/review_F-078.md -->
# F-078 · Review · rigor `critico`

## Pasada 1 — CHANGES_REQUESTED (resumido aquí por el tope)

**Revisión completa** `git diff b208a59..4d1eb55`, 13 ficheros, HEAD `4d1eb55`.
**El código estaba bien y se verificó a fondo: ni un defecto que corregir.**
Faltaba EVIDENCIA: seis `acceptance` —2, 3, 4, 6, 7 y 8— sin resultado real, y
`critico` exige las MANUAL «con su comando exacto **y su resultado real**». Las
tres tablas ni existían en la base: el implementer **no** usó la autorización de
escritura caducada.

Verificado entonces y **sigue vigente**, porque no ha cambiado una línea de
código: **C1–C5 [x]** (C3 bis y C4 ter N/A justificados; 7 commits `F-078 Tn:`).
**C4 bis [x]**: fase RED con traza real; mutación **recalculada por mí** —548
líneas, **34 mutantes exactos**, cinco muertos muestreados con su texto
original→mutado—; prueba de control (0 en el alcance, 16 mutando el fichero
entero: el cero es legítimo); campaña **no reejecutada** y dicho así (3.047,4 s
≫ 60 s); **RM1** SHA `0b877f5` = HEAD~1, que solo toca `progress/`; **RM2**
358,5 s/mutante contra base 371,5–377,0 s, coherente con el `-x` y 34/34
muertos; **RM5/RM6** N/A. **La lógica de negocio no cambió, probado
mecánicamente**: los tres cuerpos del SQL viejo contra los tres `CREATE TABLE`
salen idénticos salvo la referencia vista→tabla. Y el comando **compara de
verdad**: recalcula desde `stg` sin tocar las tablas nuevas, y una tabla vacía
es `KO`.

---

## Pasada 2 — revisión incremental desde `4d1eb55`

`git diff 4d1eb55..3581d7d --stat` → **un solo fichero, `progress/current.md`,
+72 líneas**. Cero código. Así que todo lo de arriba se mantiene y esta pasada
juzga **solo la evidencia**. HEAD `3581d7d`, rama correcta, árbol limpio.

### VEREDICTO: APROBADO

**`bash harness/init.sh` en verde**, ejecutado entero y sin tuberías: **exit 0**,
**4.826 pasan**, 188 saltados, 479,58 s. `PUERTA COBERTURA 94.3 % de 955 líneas
(901/955, umbral 80, nivel critico)`. `PUERTA TAMAÑO` dentro. Criterio 10 [x].

### Los seis criterios: no me creí el informe, los verifiqué

| # | Anotado | Mi verificación **independiente** |
|---|---|---|
| 1 | 3 sub-pasos, 1.740 filas | `_meta.v_frescura`: `build_mart` SUCCESS, **filas 5.394.139** = suma exacta de los tres sub-pasos (5.367.594+24.805+1.740) |
| 3 | 1.740 filas, **0 diferencias** | **reejecuté la comparación yo** (abajo) |
| 4 | build 1.162,06 s; vista 0,81 s | build confirmado por `_meta`; **medí la vista: 3 ms** |
| 6 | 153/153, versión 22 | `check-diccionario` **por mí**, sin tubería: exit 0, biyección 153/153, «lo publicado ES lo del arbol (version 22, hash 89d29bab993c)» |
| 7 | 153/153, pendientes vacío | `check-declarados` **por mí**: exit 0, 153/153; `objetos_pendientes.yaml` con `pendientes: []` |
| 8 | dentro de los 30 s | **el propio MCP**: `count(*)` de las tres vistas en **10 ms** |

Y el 9, que la pasada 1 dejó sin ejecutar: lancé `inspect-cp-tipologia
--anio 2025` contra Azure → **exit 0** y datos reales por obra y tipología.

**Los tiempos del informe no son suyos: los escribió el ETL.** `_meta.v_frescura`
da `build_mart` 13:49:20→14:29:34 = **2.414 s** (anotado 2.414,6) y `build_cierre`
14:50:14→15:39:17 = **2.943 s**, 16.972 filas (anotado igual): coinciden al
segundo con una tabla que el implementer no escribe a mano.

### Criterio 3, el que manda: lo reproduje

La comparación completa cuesta 29 min y es justo el perfil que R-COSTE-CONSULTA
dice que molesta a `albaranes` y `partes` en producción, así que apliqué la
**tercera vía de RM4**: un subconjunto en vez de la campaña entera. Cinco obras,
todas `READ ONLY` y por mi mano:

- `--obra 650280` (la de la sonda anotada) → **23 filas y CERO diferencias**,
  salida idéntica carácter a carácter a la del informe.
- Las **cuatro obras mayores por importe** —2313811, 2409308, 2419057, 1990273—,
  donde un fallo se vería en dinero: 13/13/13/8 filas y **CERO diferencias las
  cuatro**. Y la tabla cuadra sola: 86.980.607,24 − 67.849.582,45 =
  **19.131.024,79**, exactamente la desviación que devuelve la vista.

### `build-cierre` fue DESPUÉS de `build-mart` [x]

Probado por `_meta`, no por el relato: `build_mart` terminó 14:29:34 y
`build_cierre` **empezó 14:50:14**, SUCCESS. Era obligatorio porque `mart` dropea
en cascada lo que el cierre lee. *Matiz sin consecuencia*: la comparación
(14:31:01→14:59:53) **se solapó** con `build_cierre` desde las 14:50, aunque el
informe los numera en secuencia; no afecta al resultado —`build_cierre` no toca
`stg.plan_mensual` ni `mart.fact_cp_tipologia`—, solo la hizo más lenta.

### ¿Encaja que el paso nuevo cueste casi lo que el hecho principal? Sí

1.162,06 s para 1.740 filas frente a 1.157,74 s para 5,37 M **no huele a otra
cosa**: es el perfil que la ficha ya había medido.

- **El coste está en leer, no en escribir.** `stg.plan_mensual` son 29,8 M filas
  y 11 GB, y el build la sigue recorriendo varias veces (ámbitos 8 y 11 para las
  versiones tipadas; 3 y 8 para real, plan y corte). Cuatro pasadas de 11 GB en
  un B2s caen justo en los ~1.100 s. Escribir 1.740 filas es ruido: `build_stg`
  escribió 44,15 M filas en 2.805 s en esta misma máquina.
- **Lo que la materialización quitó no es el escaneo, es el `WindowAgg` de
  11,8 M filas** —`master_vigente_anual` se calcula ya contra una tabla de
  4.415—, y por eso ahora **termina** en 19 min en vez de no terminar.
- **Segunda confirmación, en la dirección correcta**: `check-cp-tipologia`
  completo tardó **28 min 52 s** recalculando desde `stg` por el camino viejo,
  más que el build. Si el 1.162 fuera inventado a la baja, esto no cuadraría.

### Criterio 2: NO bloquea. Es la pregunta de juicio y la respondo

La mitad verificable está cerrada **al byte**, y cerré lo que la pasada 1 no:
nombres de vista intactos, 7 columnas en orden y —esto es nuevo— los **tipos
idénticos**: comparé los casts de `b208a59:…06_views_cp_tipologia.sql` contra
`06_cp_tipologia.sql` y los `::NUMERIC(18,2)` están en los **mismos cinco
sitios** y los `::INT` en los mismos; la base confirma `bigint, integer, text,
integer, numeric(18,2)×3`. El `.pq` no se tocó y navega a una vista de forma
idéntica que ahora responde en 3 ms.

Lo que falta **ningún agente puede hacerlo**: exige la máquina del humano, su
Power BI y su `.pbix` privado. Es un N/A **justificado por imposibilidad
estructural** —la misma clase que la puerta de cobertura en un proyecto no
Python—, no la excusa que mi protocolo prohíbe («no lancé la campaña»), la del
que pudo actuar y no actuó. Bloquear, además, sale al revés: el job apunta a la
imagen de ayer, así que **la nocturna vuelve a crear las tres vistas en su forma
cara**, pisa las nuevas y deja las tablas huérfanas. Rechazar para proteger una
comprobación que solo el humano puede hacer, al precio de volver a romperle
Power BI, no protege nada. **Apruebo con traspaso, no con deuda olvidada**: que
abra su informe y refresque `FactCPTipologia` sin tocar el `.pq`; si fallara
sería un defecto nuevo, no un error de lo revisado. Cuando lancé la sonda el
servidor marcaba **2026-09-15 23:10 UTC** y la nocturna arranca hacia las 08:22.

### Un aviso que NO es de F-078, para no dar por fallido el criterio 5

`contexto_bbdd()` y `describir_tabla()` del MCP **sirven todavía el diccionario
viejo** (anuncian versión 12 y 13 y 105 objetos cuando la base tiene la **22** y
**153**), y por eso `mart.v_pbi_cp_tipologia` aún sale con el cartel «NO SE PUEDE
CONSULTAR». **Lo publicado en `_meta` sí es lo correcto**, y lo leí por SQL: la
regla es «Dos vistas no se pueden consultar» y su ámbito ya son solo
`mart.v_fact_periodificado`, `cierre.v_pbi_cierre_indirectos_detalle` y
`stg.plan_mensual`. Es **caché del MCP**; se va al reconectar.

### Cambios requeridos

**Ninguno.** Queda el traspaso del `.pbix` y desplegar antes de la nocturna.

**Automejora (propuesta, no aplicada)**: `CHECKPOINTS.md` no distingue un N/A por
desidia de uno por **imposibilidad estructural** —una MANUAL que solo puede
ejecutar el humano en su máquina—. Propongo nombrarlo: se aprueba solo si la
parte mecánica está verificada y el traspaso queda escrito.
