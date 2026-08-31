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

Se engancha en `run-all` **junto a `check-declarados`**, al final (R17).

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

## 5 · Decisiones abiertas (las cierra el humano al aprobar la spec)

**DA-1 · ¿Se relaja también la rama raíz (`04_partidas.sql:58`)?**
(a) Solo el descenso, línea 78. (b) Las dos, simétricamente.
**Recomendación: (a).** Medido: los 7 nodos con `cod = ''` son **todos
intermedios**, no hay ni una raíz sin código, así que (b) no recupera ni una
fila hoy. Y una raíz sin código no tiene `capitulo_raiz_cod` con el que
categorizar su subárbol: obligaría a inventar reglas para `capitulo_raiz_id` sin
un solo caso real que las valide. El día que aparezca una, la caza el guardián
de §3, que es exactamente para lo que se construye.

**DA-2 · ¿Qué reciben `ruta_capitulos` y `codigo_partida` de esos nodos?**
(a) Colapsarlos: no se publican, sus hijos cuelgan del ancestro publicado y la
ruta no gana segmento. (b) Publicarlos con `codigo_partida` NULL. (c) Publicarlos
con un código sintético (`ide`, `(sin código)`).
**Recomendación: (a)**, por §1: es lo único que no rompe la ficha del
diccionario, ni `05b`, ni la relación declarada, ni arriesga doble conteo.
**Contrapartida honesta que el humano debe aceptar:** «FASE 1 - MOVIMIENTO
TIERRAS Y CIMENTACIÓN» **desaparece del árbol de Power BI** de la 0599; su
información de fase se pierde como agrupador. Si Negocio la quiere ver, es (c) y
hay que decidir el código sintético con ellos.

**DA-3 · Corta-ciclos.** (a) Array de visitados en el CTE. (b) Tope de
profundidad. (c) Detectar y romper los ciclos antes del recorrido.
**Recomendación: (a) + (b) como respaldo.** (b) solo es arbitrario y trunca
ramas legítimas si alguna crece; (c) es un paso más que mantener. El array es
exacto y su coste es una decena de `bigint` por fila. Los 12 nodos en ciclo
**siguen sin publicarse** —no son alcanzables desde ninguna raíz—, pero ahora
quedan denunciados en vez de perdidos.

**DA-4 · Qué se instrumenta de los nueve puntos de descarte.**
(a) Solo el guardián post-build de §3. (b) Además, contadores dentro de
`mart/02_build_fact.sql`. (c) Instrumentar los nueve.
**Recomendación: (a).** Da el mismo veredicto sin tocar el camino caliente de
5,3 M de filas, y dos de los nueve (fase 0 y ámbitos no mirados) son descartes
**por diseño**: instrumentarlos sería ruido permanente. Falta que el humano
decida si `check-cobertura` **bloquea la nocturna** (código 1, como
`check-declarados` — es lo que recomendamos) o solo avisa.

**DA-5 · ¿La causa se lleva a Sigrid?**
**Recomendación: sí, pero sin esperar.** Como en F-050: aquí se protege el ETL y
se avisa a quien administra Sigrid de los 3 capítulos sin código y los 2
auto-bucles. Con un matiz de prioridad: 0599, 0613, 0618, 0630 y 0565 son obras
**cerradas** entre 2020 y 2022 que nadie va a volver a tocar, así que su
saneamiento es cosmético; el auto-bucle de la **0686 VALDEBEBAS está vivo**
(última fase 2026-07-31) y ese sí conviene corregirlo en origen.

**DA-6 · El aviso a Negocio (R27).** (a) Avisar antes de publicar, con la tabla
de la sección 3 del informe. (b) Publicar y avisar después. (c) Publicar con una
nota en el diccionario.
**Recomendación: (a) + (c).** El margen de la 0599 pasa de 66,3 % a 1,8 %:
cualquier informe o captura anterior deja de cuadrar, y quien lo mire sin aviso
va a pensar que el datamart se ha roto. La nota en la ficha (R21) es lo que
contesta esa pregunta dentro de seis meses.

**DA-7 · Alcance de F-053.** El desempate `rn = 1` de `03_obras.sql:125` deja
**tres obras más invisibles** (0517, 0252, 0720) por otra causa, ~10,65 M€ de
coste y 10,94 M€ de venta. **Recomendación: feature propia**, fichada en este
mismo trabajo y declarada como excepción en `config/cobertura_excepciones.yaml`
hasta que se cierre. Aquí solo se nombra (R24).

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
