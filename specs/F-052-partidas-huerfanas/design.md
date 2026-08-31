<!-- specs/F-052-partidas-huerfanas/design.md -->
# F-052 · Diseño

**La idea, en una frase:** el CTE recursivo de `stg/04_partidas.sql` pasa a
recorrer el árbol **entero** —con corta-ciclos— y el filtro de código vacío baja
al final, donde decide **qué se publica**; los capítulos sin código quedan
*colapsados*, no amputados.

Y para que esto no vuelva a pasar en silencio, un guardián de solo lectura
compara lo que entra en `stg` con lo que sale en `mart`, obra a obra.

---

## 1 · El cambio de fondo: `sql/stg/04_partidas.sql`

Capa **`stg`**. El fichero mantiene su número y su nombre. Tres cambios en el
CTE `arbol_partidas` y uno en el `INSERT`:

1. **La rama de descenso (líneas 76-79)** deja de exigir `h.cod <> ''`: solo
   `h.cod IS NOT NULL` (R1). Es el arreglo.
2. **Se añaden dos columnas propagadas**: `publicable` (`h.cod <> ''`) y
   `padre_publicado_id` — el `partida_id` del padre si el padre era publicable,
   y si no, el `padre_publicado_id` que el padre traía (R3). `capitulo_padre_id`
   del `INSERT` pasa a leer de ahí.
3. **`ruta_capitulos` y `nivel` solo avanzan en nodos publicables** (R3, R4):

   ```sql
   CASE WHEN h.cod <> '' THEN a.ruta_capitulos || ' > ' || h.cod
        ELSE a.ruta_capitulos END              AS ruta_capitulos,
   a.nivel + CASE WHEN h.cod <> '' THEN 1 ELSE 0 END AS nivel
   ```

   Así se mantiene el invariante `cardinality(split(ruta)) = nivel + 1`, que es
   de lo que vive `mart.v_pbi_dim_partida_niveles`.
4. **Corta-ciclos (R5)**: la CTE arrastra `visitados BIGINT[]` (`a.visitados ||
   h.ide`) y la rama recursiva añade `AND NOT (h.ide = ANY (a.visitados))`, más
   un tope duro `AND a.nivel_bruto < 40` como cinturón y tirantes. Profundidad
   real máxima medida: 5-6 niveles; el array nunca pasa de una decena de
   `bigint` por fila.
5. **El `INSERT` filtra `WHERE publicable`** (R2): los 7 nodos con `cod = ''`
   siguen sin publicarse, igual que hoy.

**Qué cambia en la 0599, en concreto.** Los 36 hijos directos de las tres
«FASE …» pasan a colgar de `CD` (`capitulo_padre_id` = 274277), heredan
`capitulo_raiz_cod = 'CD '` → `categoria = 'CD'`, y su ruta es `'CD > 01' …` sin
segmento en blanco. El efecto 3 del informe —`'CD >  > 01.01'` y un nivel vacío
en «Árbol Presupuesto»— **queda eliminado por construcción**, no parcheado.

**Por qué colapsar y no publicar el nodo vacío.** Publicarlo obligaría a darle un
`codigo_partida` NULL o sintético (rompiendo la ficha del diccionario y el
`GROUP BY obra_id, codigo_partida` de `05b`), y sobre todo **abriría la puerta a
doble conteo** si ese capítulo tuviera importes propios en `stg.plan_mensual`.
Colapsarlo deja la relación declarada `capitulo_padre_id → partida_id` intacta
—los 36 hijos apuntan a una fila que **sí** existe— y no añade ni un euro.

## 2 · La regla, en dominio puro

| Ruta | Capa | Qué es |
|---|---|---|
| `etl_sigrid/domain/arbol_partidas.py` | domain | `Nodo(ide, padide, cod, obra_id)`; `construir_arbol(nodos) -> Arbol` con `publicadas`, `descartadas_sin_codigo` y `en_ciclo`. Implementa R1-R5 **fuera de la base**, con la misma regla que el SQL. Cero imports de infraestructura. |
| `etl_sigrid/domain/cobertura.py` | domain | `FilaCobertura(obra, codigo_obra, ambito, filas_stg, filas_mart, huerfanas)`; `Excepcion`; `veredicto(filas, excepciones) -> Veredicto` con las dos listas completas (obras invisibles / filas huérfanas) y código distinto de 0 si algo cae fuera de lo declarado (R14, R15, R16). Puro. |
| `etl_sigrid/infrastructure/postgres/cobertura_sql.py` | infra | Construye el texto de las dos consultas con su `SET LOCAL statement_timeout`. **No abre conexión** (R18, R19), al estilo de `unicidad_sql.py`. |
| `config/cobertura_excepciones.yaml` | config | Las excepciones aceptadas con motivo y feature que las cerrará. **Trinquete: solo baja** (R16). |
| `tests/test_f052_arbol.py` · `test_f052_sql.py` · `test_f052_cobertura.py` | tests | Sin red ni BBDD. |

Es el patrón de F-042 (`domain/cierres.py` + `infrastructure/…/cierres_sql.py`):
la regla se puede probar con fixtures y el SQL se comprueba sobre su texto.

**Fixtures de `test_f052_arbol.py`**, tomadas del informe y no inventadas: el
subárbol `CD → 280353/280354/280356 (cod='') → hijos`, los dos auto-bucles
(310512 de la 0630 y 375474 de la 0686) y el bucle mutuo de la 0565
(279988 ↔ 279997 con sus 9 hermanos).

## 3 · El guardián: `check-cobertura`

Comando nuevo en `main.py`, hermano de `check-unicidad` / `check-cierres`
(`--timeout`, `--dry-run`, salida con código 1). Dos consultas:

- **A · Huérfanas (R15).** Filas de `stg.plan_mensual` cuyo `partida_id` no está
  en `stg.partidas` o cuyo `obra_id` no está en `stg.obras`, agrupadas por obra y
  ámbito. Hoy: 183.756 + 82.815. Después del arreglo: solo lo declarado.
- **B · Obra invisible (R14).** Obras con filas en `stg.plan_mensual` para un
  ámbito y **cero** en `mart.fact_seguimiento_mensual` para ese ámbito.

**En los ámbitos master (8, 11) B compara presencia, no conteo.** El build de
planificado no es un `JOIN` puro: `master_proyectado` elige la versión vigente,
así que muchísimas filas de `stg` no llegan al fact **por diseño** y contar sería
mentir. En los reales (3, 7) el build sí es `JOIN` puro y ahí se comparan filas.

### Se engancha sin bloquear, y avisa por correo (DA-4)

Se ejecuta al final de `run-all`, junto a `check-declarados`, pero **no hace
fallar el job**: registra el hallazgo y la nocturna termina en verde (R17).
Lanzado a mano fuera de `run-all` sí devuelve código distinto de 0, para poder
usarlo como puerta en una verificación manual.

**El aviso por correo no lleva código de correo nuevo**: el mecanismo ya existe
en este repositorio y se reutiliza tal cual.

| Pieza | Ya existe | Qué se añade |
|---|---|---|
| Grupo de acción `ag-datamart-seg-dev` (rg `rg-datamart-seg-dev`) | `infra/90_create_alert.ps1`, destinatarios por `-AlertEmail` | nada: se le suma el buzón que indique el humano |
| Regla de consulta programada sobre `log-datamart-seg-dev` | `infra/95_create_alert_frescura.ps1` | `infra/96_create_alert_cobertura.ps1`, hermano suyo |
| La línea que dispara la regla | — | un **marcador estable** que emite `check-cobertura` (R28) |

El marcador es el literal **`[F052-COBERTURA-KO]`**, seguido del recuento de
obras invisibles y de filas huérfanas. Vive en **dos sitios que no pueden
divergir** —el código que lo emite y el `.ps1` que lo busca—, así que lo protege
un test que cruza los dos extremos, exactamente como
`test_f024_r19_umbral_por_defecto_coincide_con_dev_json` protege el umbral de
frescura. Si divergen, la alerta vigila un texto que ya nadie escribe y **nadie
se entera**, que es el modo de fallo que esta feature existe para eliminar.

**Ninguna dirección de correo entra en el repositorio** (R30). Lo dice ya
`infra/90_create_alert.ps1`: los destinatarios se pasan con `-AlertEmail` en el
despliegue, que es manual y lo ejecuta el humano.

> **Riesgo declarado, y es el precio de no bloquear.** Al terminar el job en
> verde, la alerta de fallo existente (`alert-caj-datamart-seg-dev-failed`) **no
> se dispara**. La regla nueva pasa a ser la **única** vía por la que este
> guardián se hace oír: **si no se despliega, el guardián es mudo** — detecta la
> obra invisible, la escribe en el log y no se entera nadie.

**Coste, y por qué es un riesgo declarado.** A y B barren `stg.plan_mensual`
entera. Con el techo de 10 MiB/s del `B1ms` eso son minutos, sobre una nocturna
que ya cuesta **3 h 45** (F-044) y sobre un Postgres **compartido con `albaranes`
y `partes` en producción**. Por eso T13 lo **mide antes** de engancharlo, y por
eso lleva `statement_timeout`.

## 4 · Ficheros

**Se crean:** los cinco de la tabla de §2.

**Se modifican:**

| Ruta | Qué cambia |
|---|---|
| `sql/stg/04_partidas.sql` | §1. También la cabecera: hoy documenta el filtro como «descarta filas estructurales sin código», que es justo lo que hay que dejar de hacer al descender. |
| `main.py` | Comando `check-cobertura` y su enganche en `run-all`. |
| `config/diccionario/stg.yaml` | Ficha de `stg.partidas`: `codigo_partida`, `capitulo_padre_id`, `nivel`, `ruta_capitulos` (R20). |
| `config/diccionario/mart.yaml`, `cierre.yaml` | Aviso del cambio de cifras de la 0599 (R21). |
| `config/diccionario/00_global.yaml` | `version` (R22). |
| `docs/ARCHITECTURE.md` | Semántica Sigrid: capítulo sin código (R23). |
| `infra/96_create_alert_cobertura.ps1` *(nuevo)* | Regla de consulta programada que busca el marcador y notifica a `ag-datamart-seg-dev` (R29). Despliegue manual. |
| `tests/test_f052_marcador.py` *(nuevo)* | El marcador del código y el del `.ps1` no pueden divergir (R28). |

**Ficheros que NO se tocan** (los que tientan):

- `sql/mart/02_build_fact.sql` — sus cuatro `JOIN stg.partidas` **son
  correctos**: una fila de plan sin partida no tiene dimensión. El defecto no es
  el `JOIN`, es que `stg.partidas` llegaba incompleta y que nadie miraba el
  descarte. Convertirlos en `LEFT JOIN` metería filas sin categoría en el fact.
- `sql/mart/05b_view_dim_partida_niveles.sql` — no necesita cambio: al no haber
  segmentos vacíos (R4) los niveles salen bien, y `COALESCE(codigo_partida,'')`
  ya cubre lo demás.
- `sql/stg/03_obras.sql` — R24, es F-053.
- `sql/stg/08_plan_mensual.sql` y `sql/cierre/02_build_fact.sql` — se mueven
  solos al llegar las partidas; no hay nada que tocar en ellos.

## 5 · Decisiones tomadas por el humano el 2026-08-31

Las siete estaban abiertas al escribir esta spec. **Están cerradas.** El detalle
—la razón de cada una y lo que se descartó— vive en **`decisiones.md`**; aquí
queda lo que hay que saber para implementar.

| | Decisión |
|---|---|
| **DA-1** | Solo se relaja la **rama de descenso** (línea 78). La raíz no se toca |
| **DA-2** | **Colapsar**, con R11 como condición bloqueante: si se mueve una cifra de una obra fuera de las seis, **se para y se consulta** |
| **DA-3** | Array de visitados **+** tope de profundidad |
| **DA-4** | **Avisa, no bloquea** (§3), y avisa **por correo** |
| **DA-5** | Sí a Sigrid, sin esperar. Prioridad solo la **0686**, obra viva |
| **DA-6** | Aviso a Negocio **antes** de publicar (`aviso_negocio.md`) y nota en el diccionario |
| **DA-7** | Feature propia: **F-053**, prioridad 2 |

**Por qué R11 se espera limpio, y no por optimismo.** Cada partida tiene **un
solo padre**, luego un solo camino hasta su raíz. La que hoy se publica tiene ese
camino entero con código, y el algoritmo nuevo lo recorre igual: misma ruta, mismo
nivel, mismo padre. Relajar el filtro **solo añade** caminos. **El cambio es
estrictamente aditivo**, y para que una obra sana se moviera una de sus partidas
tendría que tener dos padres, cosa que el modelo no permite. Medido el
2026-08-31: fuera de la 0599 el movimiento máximo posible son **226 filas de
183.756**, a **0,00 €**; y la profundidad real máxima es de **7 niveles, cero
partidas de nivel 8 o más sobre 389.178**, así que el tope de 40 no trunca nada.
El argumento no sustituye a la prueba: R11 se verifica igualmente.

**Contrapartida aceptada (DA-2):** «FASE 1 - MOVIMIENTO TIERRAS Y CIMENTACIÓN» y
sus dos hermanas **desaparecen del árbol de Power BI** de la 0599 como agrupador.
Va en el aviso a Negocio para que puedan objetar antes de publicar.

### Bloqueo operativo conocido (2026-08-31)

**No hay conexión directa a la base desde el puesto** (`connection timeout
expired` contra `psql-albaranes-rs9k2`). La base responde por la vía de solo
lectura del MCP, pero **esa vía no expone `raw`**. Las verificaciones con huella
antes/después (T13-T16 y los pasos de cierre) **no se pueden ejecutar** hasta
restablecerlo. Bloquea la implementación, no el diseño.

## 6 · Riesgos

1. **Colgar el build.** Relajar el filtro sin corta-ciclos con 12 ciclos vivos
   es un `WITH RECURSIVE` infinito en una nocturna de 3 h 45. Mitigado por DA-3
   y probado en dominio (T2) **antes** de tocar la base.
2. **Doble conteo.** Si alguno de los 7 capítulos sin código tuviera importes
   propios en `stg.plan_mensual`, publicarlo los sumaría sobre los de sus hijos.
   Con DA-2(a) no se publica, así que el riesgo se cierra por construcción; T14
   lo verifica igualmente con la huella.
3. **Mover algo que no debía moverse.** Es lo que mata la feature: lo cubren R11
   y T14-T16, la comparación antes/después sobre el **mismo `raw`**.
4. **Coste del guardián** sobre un Postgres compartido en producción: §3, T13.
5. **`check-unicidad` con 183.756 filas nuevas**: R12, se ejecuta con
   `--timeout 300` (efecto 2 del informe).
