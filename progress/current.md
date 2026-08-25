<!-- progress/current.md -->
# Estado actual · 2026-08-25

**Feature en curso: F-006 · MCP sobre el datamart.** Rama
`feature/F-006-mcp-azure`. `bash harness/init.sh` **en verde: 2025 tests,
cobertura 98,0 %**. Árbol limpio.

**Trabajo aparte, sin integrar: el arnés pasó de 1.5.1 a 1.7.4** en la rama
`chore/arnes-1.7.4`, con el portero **en verde: 2.278 tests (253 más, los del
arnés), cobertura 98,0 %** y las tres puertas cumplidas. Lee la sección
siguiente antes de retomar F-006: el papeleo de la feature cambió de sitio, y
esa rama **todavía no está integrada** en `dev` ni en `feature/F-006-mcp-azure`,
así que desde ellas no se ve nada de esto.

Esta sesión retomó la parada del 2026-08-22
(`progress/parada_2026-08-22_limite_gasto.md`, ya histórica: lo que describe
está hecho).

---

## El arnés, de 1.5.1 a 1.7.4 (2026-08-25, rama `chore/arnes-1.7.4`)

Actualización con el instalador de `arnes-base` en modo actualizar. Lo genérico
entró solo; `harness/init.sh` y `CHECKPOINTS.md` se **fusionaron a mano** para
no perder lo propio del proyecto (la cabecera de configuración y la sección 9
del primero; las trampas del dominio Sigrid y la regla del SQL por capas del
segundo). `CLAUDE.md`, `docs/CONVENTIONS.md` y `docs/referencia/README.md` se
conservaron: el payload solo traía la plantilla sin adaptar.

### Lo que cambia en el día a día

| Novedad | Qué significa |
|---|---|
| **Puerta de tamaño** (`python -m harness.tamano`) | El papeleo de la feature en curso tiene topes: requirements 150, design 250, impl 220, review 140 líneas. Pasarse pone el portero en **rojo**. Solo mide la feature abierta; lo `done` está amnistiado. |
| **`nivel_por_defecto` = `estandar`** | Antes, una feature sin `rigor` heredaba `critico`. Ya no: `critico` **se declara**. |
| **Campañas `estandar` muestreadas** | 20 mutantes con semilla fija `20260820`. **Sus números no son comparables** con los de campañas anteriores. `--max-mutantes 0` fuerza la campaña entera. |
| **El venv del proyecto manda** | El portero antepone `.venv` al PATH: se acabaron los veredictos distintos según cómo se abriera la terminal. |
| **Centinela de campaña** | Si queda un mutante aplicado en el árbol, el portero lo dice en vez de medir encima. |

### El papeleo de F-006 se partió en resumen + anexo

Lo exigía la puerta nueva (impl iba por 4.763 líneas contra un tope de 220). El
detalle **está intacto**, solo cambió de nombre:

| Se lee primero (resumen, medido) | Detalle íntegro (anexo, no medido) |
|---|---|
| `specs/F-006-mcp-azure/requirements.md` (132) | `requirements_detalle.md` (557) |
| `specs/F-006-mcp-azure/design.md` (191) | `design_detalle.md` (1.004) |
| `progress/impl_F-006.md` (197) | `impl_F-006_detalle.md` (4.763) |
| `progress/review_F-006.md` (125) | `review_F-006_detalle.md` (4.918) |

**Efecto colateral que conviene recordar:** tres tests de F-006
(`test_f006_fichas.py`, `test_f006_publicacion.py` ×2) leían `design.md` para
verificar el contrato **letra a letra** —los bloques YAML, el DDL de
`_meta.v_diccionario` y la §4.2—. Al resumir el diseño se pusieron rojos, y
ahora apuntan a `design_detalle.md`. Si algún día se parte más papeleo, mira
antes quién lo lee: `grep -rn "<fichero>" --include=*.py .`

Los resúmenes son **índices navegables**, no versiones cortas: están los 41
requisitos, las 43 tareas y el recorrido de checkpoints, cada uno con su enlace
al anexo. El veredicto vigente del reviewer sigue siendo **RECHAZADO** (pasada
decimosexta): la actualización del arnés no cambia nada de eso.

### Trece tests del proyecto iban por detrás de la herramienta

`tests/` no solo prueba el ETL: prueba también las herramientas del arnés, y
trece tests codificaban el comportamiento de la 1.5.1. Se adaptaron **sin
aflojar ninguna aserción** (`test_f015_mutacion.py` pasó de 92 a 97):

| Fichero | Qué codificaba de la versión vieja |
|---|---|
| `test_f006_fichas`, `test_f006_publicacion` | Leían el contrato letra a letra de `design.md`; ahora leen `design_detalle.md` |
| `test_f015_mutacion` (5) | La campaña sin línea base, sin código 3 y sin `stdout` en el proceso |
| `test_f020_mutacion` (7) | Campaña por servicios y códigos de error |
| `test_f015_rigor` (1) | «Sin rigor declarado se aplica el más exigente», la regla que derogó la 1.7.0 |
| `test_f020_genericidad` (2) | R17, gemela de R19; y una lista blanca de módulos estándar escrita a mano |

**R19 y R17 se afinaron, y esto conviene entenderlo antes de tocarlas.** R19
(en `test_f015_rigor.py`) y R17 (en `test_f020_genericidad.py`) son la misma
regla escrita dos veces en dos features distintas. Exigían que
ninguna herramienta de `harness/` mencionara palabras del datamart, barriendo
el texto entero. El arnés 1.7.4 trae 20 menciones que **no son dependencias**:
notas de procedencia («esto nació en `albaranes` F-038»), `mutacion_paralela.py`
citando este repositorio como su origen, y «cierre» en castellano llano («la
línea base de cierre EXPIRÓ»). Decisión del humano el 2026-08-25: **R19 vigila
el código ejecutable, no la prosa**. En concreto:

- el barrido usa `ast` para quitar comentarios y docstrings, y **conserva los
  literales**: un mensaje de error que nombre a Sigrid sigue atando igual;
- `\bcierre\b` pasa a `cierre\.\w`, el uso cualificado con el que se cita un
  esquema;
- la lista blanca de módulos estándar de R17, escrita a mano, se sustituye por
  `sys.stdlib_module_names`: envejecía en cada versión del arnés (la 1.7.x trajo
  `math`, `signal` y `contextlib`) y cada envejecimiento se leía como una
  violación que no lo era. Preguntar por la biblioteca estándar de verdad caza
  además cualquier dependencia de terceros, incluida la que nadie prohibió;
- `f-0\d\d` **se retira** —`tamano.py` lo usa de ejemplo en el `help` de
  `--feature` y no ata a nadie— y en su lugar entra una comprobación más
  fuerte: **ninguna herramienta importa `etl_sigrid`, `config`, `main`, `tests`
  ni `infra`**, que es la atadura de verdad. Verificado metiendo el import a
  propósito: el test se pone rojo.

Queda **propuesto para `arnes-base`**: que las herramientas genéricas lleven su
procedencia en el registro de versiones y no en el docstring del módulo.

### Dos cosas que hay que mirar antes de seguir

1. **F-041 puede haber encogido.** Denuncia que la campaña de mutación miente
   por timeouts y bytecode. El bytecode **ya está arreglado** río arriba (1.6.3:
   la campaña ejecuta con `PYTHONDONTWRITEBYTECODE=1`) y los timeouts ahora se
   derivan de la línea base medida (1.7.2), no de una constante. Lo que **sigue
   vivo** es que un mutante cuya suite no recoge ni un test sale
   `SUPERVIVIENTE` en vez de «no juzgado», así que **una campaña de una sola
   pasada aún no vale como evidencia**: contrasta con una segunda
   (`--workers 1`). Revisa la ficha de F-041 antes de trabajarla.
2. **Siete features siguen sin `rigor` declarado** (F-002, F-007, F-010, F-012,
   F-013, F-017, F-018). Decisión del humano el 2026-08-25: **se quedan así** y
   el nivel se decide al abrir cada una, cuando se conozca el alcance real. Que
   nadie lo lea como un descuido.

---

## Lo que hace F-006, en una línea

Publicar en `_meta` la **capa semántica** del datamart —qué significa cada
objeto y cada columna, y qué reglas hay que respetar para leerlo— para que
**cualquier agente conectado por MCP construya sus propios casos de uso**, no
solo los seis que el humano dio de ejemplo. Los seis casos son la **batería de
aceptación**, no la especificación.

## Dónde está

Diccionario en **versión 8**, publicado y verificado contra la base: **103
objetos** documentados, **798 columnas**, **46 de consumo recomendado**. (Estas
cifras las comprueba un test: si envejecen, la suite se pone roja. Ya caducaron
dos veces.)

Tres puertas que lo contrastan **contra el dato real**, no contra sí mismo:

| Comando | Qué comprueba |
|---|---|
| `check-diccionario` | biyección ficha ↔ objeto que existe en la base |
| `check-unicidad` | que la clave declarada sea de verdad única |
| `check-relaciones` | que el JOIN de cada relación declarada **devuelva filas** |

El lado consumidor (`C:\Users\pgris\PycharmProjects\mcp-bbdd`, repo aparte, ya
en git) consume `_meta` y sirve **los cinco bloques** de contexto.

---

## Lo que falta para cerrar F-006

### Nuestro
- **Bloque J, documentación** (T35-T37): `docs/runbook_postgres_azure.md`,
  sección de arquitectura, y actualizar `azure-apps/datamart_seg_anual.md`.
  T37 es **obligatoria**: cambió lo que este proyecto expone.
- **T28**: la regla en `docs/CONVENTIONS.md` (quien cambia un objeto publicado
  actualiza su ficha en el mismo trabajo).
- **T43**: decidir con el humano qué deuda declarada se paga y cuál viaja.
- **Cierre**: T41 (mutación) y T42 (`init.sh`), más el veredicto del reviewer
  contra `CHECKPOINTS.md`. Sin él, la feature **no se marca `done`**.

### Del humano, y ningún agente puede hacerlo
- **Probar el MCP dentro de Claude Escritorio.** Todo va por la misma fábrica y
  los mismos servicios, pero **el protocolo MCP no se ha ejercitado nunca**.
- **T32 🔏: verificar que Power BI no lee de `stg` ni de `raw`.** De eso depende
  si los `REVOKE` (T29-T31) se encienden aquí o se entregan a F-034. Hoy el rol
  `mcp_sigrid_dm_ro` **lo comparten el MCP y Power BI**, y por eso los REVOKE
  están **construidos y apagados**.

### El objetivo que todavía NO está cumplido
El humano pidió **«un MCP que pueda usar cualquier usuario desde cualquier
puesto»**. Hoy el MCP corre **en el puesto de pgris** apuntando a Azure. T38
(desplegar el entorno) está **bloqueada hasta que ese entorno exista**. Lo
construido es la capa semántica, que era el prerrequisito, no el despliegue.

---

## Lo que esta feature ha enseñado, y conviene no volver a aprender

1. **El defecto sobrevive «en el campo de al lado».** Ocurrió más de cinco
   veces: se corrige la cabecera y el aviso sigue mal en la columna; se arregla
   una vista y la hermana queda igual. En T40, «el centro de coste coincide con
   la obra» estaba en **cuatro fichas**, y `es_activa` mentía en **cinco
   sitios**. Corregir donde te lo señalan no es corregir.
2. **Un barrido de texto sobre el YAML crudo no ve las frases plegadas.**
   Rompió cuatro comprobaciones de esta feature, una de ellas el propio
   guardián escrito para evitarlo. Barre siempre sobre el diccionario
   **cargado**.
3. **Un test verde puede sostener una mentira.** Había un test exigiendo
   literalmente `assert "98" in obra.significado` — es decir, obligaba a que la
   ficha repitiera una afirmación falsa.
4. **Una relación puede resolver perfectamente y no unir nada.** El validador
   offline no puede verlo: los dos extremos existen y los tipos encajan. Lo que
   falla está en los datos. De ahí `check-relaciones`.
5. **Preguntarle al adaptador cuántos bloques hay es preguntarle al acusado.**
   El verificador de `mcp-bbdd` lee de la base por el pool, no por el código que
   se los estaba dejando.

---

## Deuda y decisiones abiertas

### Del humano
- **`CHECKPOINTS.md`**: el reviewer propone que C4 exija que los valores de un
  contrato declarativo pasen por un **vocabulario cerrado validado**, no solo
  que el campo exista. Es lo que habría cazado el `cardinalidad: 61` (YAML leyó
  `1:1` como sexagesimal), que ni la cobertura ni la mutación podían ver porque
  el valor venía del dato, no del código. **No aplicada.**
- **`harness/mutacion.py`**: que el veredicto sea `muertos == total` y que un
  timeout diga «SIN EVALUAR». En F-006 los cuatro timeouts **eran cuatro
  supervivientes**. Toca el arnés y cambiaría el veredicto de features ya
  cerradas; si se acepta, viaja a `arnes-base` en el mismo trabajo.

### Backlog nacido de esta feature
| Feature | Prio | Qué |
|---|---|---|
| **F-041** | 2 | **La puerta de mutación no comprueba nada.** Mientras no se arregle, **ningún número de mutación de este repositorio es evidencia**. Superviviente real conocido: `and`→`or` en `diccionario_sql.py:297`. |
| **F-042** | 2 | Clave rota del fact y **agregado doblado**: 39,07 M€ de más en 8 obras, alimentando tarjetas KPI de Power BI. |
| **F-045** | 2 | **Las retenciones no se pueden atribuir a una obra** (nace de T40). |
| **F-044** | 1 (tras el MCP) | Los cuatro `build-*` a la nocturna. Medido: **37,5 min**, el disco no se mueve. |
| F-036..F-040 | 2-6 | Huecos de dominio: oficios, tesorería, comparativos, vistas puente, ingresos. |

### Huecos de negocio declarados, sin resolver
- **El mayor proveedor de la empresa es la propia empresa** (intragrupo). Tumba
  silenciosamente cualquier ranking de «quién ha facturado más», que era uno de
  los seis casos de uso.
- **Los órdenes de magnitud** ya llegan al agente, pero cubrían solo
  `retenciones`; T40 los amplió a donde están los importes.

---

## Reglas vigentes que no se negocian

- Escritura autorizada **solo en el esquema `_meta`** de `sigrid_dm`. Todo lo
  demás, lecturas. `psql-albaranes-rs9k2` lo comparten `albaranes` y `partes`
  **en producción**: las puertas corren en transacción `READ ONLY` y con
  timeout.
- **Firewall**: regla **única y sin fecha** `datamart-puesto-pgris`, se reescribe
  con la IP del momento. No se crean reglas nuevas ni se tocan las ajenas.
  (`-n` es la REGLA; el servidor va en `--server-name`.)
- **No ampliar** los 32 GB del servidor; umbral de parada al **80 %** de disco
  (hoy 57,93 %).
- Nunca secretos en el repositorio. `.env` no se toca ni se sube.
- Sin `git push` ni PRs sin petición explícita.
- Commits **con rutas explícitas** (`git add <ruta>`, nunca `-A`): más de un
  agente sobre el mismo árbol, y ya se mezcló trabajo ajeno en un commit.
