<!-- progress/spec_F-101.md -->
# F-101 · Spec escrita (spec-author)

HOTFIX de F-057. Rama `hotfix/F-101-cabecera-del-parte`. Rigor `estandar`.
Ficha cambiada a `sdd: true` y `status: spec_ready`; `BACKLOG.md` regenerado.

Entregado: `specs/F-101-cabecera-del-parte/` con `requirements.md` (137/150),
`design.md` (236/250) y `tasks.md` (13 tareas + 10 verificaciones MANUALES).

## Lo medido (2026-09-22/23, SOLO LECTURA)

Sigrid por `sigrid-api` (`leer_sql`); tamaños por `filas_solo_lectura` contra
el Postgres de desarrollo. Ninguna escritura, ningún build.

**Cabecera.** El parte es **`con.tip = 35`**, 6.886 documentos. `con.cod`
informado en las 6.886 pero **solo 6.258 distintos**: 569 códigos repetidos que
afectan a 1.197 partes, así que el código NO es clave. `con.res` (descripción)
6.883; `con.fec` 6.885; `con.fecbaj` ≠ 0 en 218; `con.tiemod` 6.885.
Estados de `conest` para `tip = 35`: **1 REG «En registro» (647), 3 CER
«Cerrado» (541), 10 IMP «Imputado» (5.698)**. De `hmo`: `obride` 6.845 (539
obras), `cenide` 6.839, `ano` 6.865 (**27 fuera de 1990-2030**: 0×21, 22, 211,
11226, 201311, 201403, 201831), `mes` 6.884 (2 fuera de 1-12). **`feccie`,
`cla` y `caaide` valen 0 en las 6.886** —la ficha del backlog daba `feccie` y
`cla` por aprovechables y no lo son— y `reside` solo en 6. `con.tex` en partes:
3 filas, 660 bytes; la descripción es `con.res`.

**La discrepancia que pide Juan**: **615 líneas en 14 partes** tienen obra
distinta de la de su cabecera (F-057 midió 769 el 18-09). **0 líneas sin
cabecera** de 330.941.

**`hmores.tex`**: informado en **13.390 de 330.941 (4,05 %)**, **284.080 bytes
(277 KiB)**, máximo 318 B, presente en 2.306 de los 6.873 partes con líneas.
`raw.hmores` pesa **111 MB** (101 MB de datos, 320,3 B/fila, 57 columnas): el
texto es **+0,27 %**. Un ejemplo del contenido es un nombre y dos apellidos —
texto libre con nombres de persona (el literal se redacto el 2026-09-23).

**`reshor`**: 8.959 filas, 2.063 recursos, 58 tipos. `pre` ≠ 0 en 2.037,
`preven` en **3**, `prenom` en 2, `candef` en 1.614, `caaide` en 3.198, `pos`
en 8.959. **`cuaide` y `proide` valen 0 en las 8.959.** **17 pares
(recurso, tipo de hora) repetidos**, 16 con el mismo precio y uno —recurso
947513, tipo 27— con dos distintos. 0 filas sin recurso, **3 sin tipo de hora
en `auxhor`**. 6.968 de las 8.959 son de recursos `cla = 1`.

**Tipo de hora por defecto: existe, es `res.horide`.** Informado en 2.035 de
2.618 recursos (77,7 %) y en 850 de 1.354 personas; 0 huérfanos contra
`auxhor`; **4 recursos** tienen un defecto sin fila en `reshor`.

**El desfase de precios, ya cuantificado**: de **279.034 líneas comparables**
(mismo recurso y tipo de hora con precio en los dos lados), **156.819 (56,2 %)
llevan un precio distinto del de la ficha**. Es exactamente lo que Juan
persigue con el caso de Jaime Rabadán, y confirma que `reshor` son los precios
de HOY: no tiene ninguna columna de fecha ni `tiemod`.

**`con.tiemod` es fecha serie con época 1899-12-30, verificada por dos vías**:
`MAX(con.tiemod)` global = 46287,88 → 2026-09-22, y el parte más antiguo,
39784,75 → 2008-11-21, cuyo `con.fec` es 20081130.

## Lo que NO se puede hacer, y hay que decirlo

**El usuario que crea el parte no existe en `con` ni en `hmo`.** `con` tiene 19
columnas (`ide, emp, tip, subtip, cod, res, fec, tex, cee, est, fecbaj, tiemod,
ico, delo, del, obr, doc, serie, hor`) y `hmo` 16: **ninguna de usuario**. Está
en **`dbo.log`** (8.472.098 filas, **35.684 de `tip = 35`**), tabla NO
ingerida, la misma que F-016 usó para las firmas de factura. Traerla es una
feature de ingesta con su propio coste de ventana y su propia conversación
sobre datos personales. Queda fuera del hotfix y declarado en la ficha.

## Decisiones que necesita validar el humano

1. **D-3 · ¿Se ingiere `hmores.tex`?** Recomendado **SÍ**: +277 KiB sobre 111
   MB (+0,27 %), +0,86 B/fila sobre 320,3. Es la mitad del punto 2 del correo
   de Juan. Riesgo: texto libre con nombres de persona, que queda dentro de
   `personal`, el esquema restringible. El coste de ventana se cronometra
   (`ingest --table hmores --full`, patrón medición B de F-080) como tarea
   MANUAL, no se supone. **Sin esta decisión, T9 no se ejecuta.**
2. **D-8 · El tipo de hora por defecto.** Opción A (recomendada, dentro del
   alcance): solo la bandera `es_por_defecto` en `recursos_tipos_hora`, con la
   ficha declarando los 4 recursos que se quedan sin marca. Opción B: añadir
   además `tipo_hora_defecto_id` a `personal.recursos`, que esta feature
   dejaba intacto.
3. **D-9 · `precio_venta` está informado en 3 de 8.959 filas.** Se publica
   igual, con el aviso en la ficha. Si el humano prefiere omitirlo, se quita
   una columna.
4. **Confirmar el vocabulario de D-1**: `obra_cabecera_id` y
   `centro_coste_cabecera_id`. F-093 sigue `pending` y no ha fijado todavía el
   sufijo para `compras`; conviene que las dos features usen el mismo, y esta
   llega antes.

## Lo que la spec deja explícitamente intacto

El veto de F-057 (`02_partes_lineas.sql` no nombra `raw.hmo`), `01_recursos.sql`
con su lista blanca de `raw.emp`, `config/objetos_pendientes.yaml` en `[]`,
los grants de F-087 (son por esquema) y la revocación de F-068 sobre
`raw.reshor`: lo que se abre es el objeto curado sin `prenom`.

`azure-apps/datamart_seg_anual.md` **sí cambia** (T12): hoy lista tres objetos
de `personal` y pasarán a cinco.

## APROBADA (humano, 2026-09-23)

Las cuatro decisiones, con la opcion recomendada: D-3 SI a `hmores.tex`; D-8
opcion A (solo `es_por_defecto`); D-9 se publica `precio_venta`; D-1
`obra_cabecera_id` / `centro_coste_cabecera_id`. D-6 (`dbo.log`) pasa a
**F-105**, prioridad 10.
