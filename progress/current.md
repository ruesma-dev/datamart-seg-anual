<!-- progress/current.md -->
# Estado actual · 2026-08-25

**Feature en curso: F-006 · MCP sobre el datamart.** Rama
`feature/F-006-mcp-azure`. `bash harness/init.sh` **en verde: 2025 tests,
cobertura 98,0 %**. Árbol limpio.

Esta sesión retomó la parada del 2026-08-22
(`progress/parada_2026-08-22_limite_gasto.md`, ya histórica: lo que describe
está hecho).

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
