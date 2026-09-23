<!-- progress/spec_F-102.md -->
# F-102 · Spec escrita (spec-author, 2026-09-23)

Entregado `specs/F-102-obra-duplicada-empresa-28/` en la rama
`hotfix/F-102-obra-duplicada-empresa-28` (desde `main`, en worktree aislado:
F-101 se implementa en el arbol principal). Segunda pasada con las decisiones
del humano: requirements 150/150, design 248/250, 19 tareas (T0-T18).
Ficha: `sdd: true`, `spec_ready`.

## Lo que la spec propone, en cinco lineas

1. Una vista nueva, `stg.v_obra_fichas`, es la **unica** definicion de "ficha
   principal": la construye `stg/03_obras.sql`, de ella sale `stg.obras` y de
   ella leen `maestro.obras` y las vistas de consumo de `compras`. La marca
   casa con la deduplicacion por construccion. Principal = empresa 1 (D1).
2. `maestro.obras` gana al final `empresa_id`, `nombre_empresa`,
   `es_ficha_principal`, `num_fichas_codigo` y `obra_principal_id`, sin perder
   filas (922).
3. Nombre de empresa: ingerir `auxemp` (38 filas).
4. No se reescribe el `obra_id` de ningun hecho: se traduce al leer con
   `maestro.obras.obra_principal_id`, y una regla dura nueva
   (`R-OBRA-FICHA-PRINCIPAL`) lo explica con las cifras.
5. Las cinco vistas de consumo de `compras` con obra ganan `obra_principal_id`;
   las demas fichas con relacion a `maestro.obras.obra_id` explican la
   traduccion. Diccionario, `ARCHITECTURE.md` y `azure-apps`. Sin aviso a
   `facturas` (D4).

## Hallazgos que el lider no tenia (todos medidos, 2026-09-23)

- **`stg.obras` elige hoy la ficha equivocada en tres codigos**, y `mart` y
  `cierre` pierden esas obras enteras: **0720** (elige la copia vacia de la 28;
  la de la empresa 1 tiene 142 filas de plan que no llegan), **0252** (7.564) y
  **0517** (72.737), estas dos pares empresa 1 + UTE. Es el desempate por
  `tiemod` de F-053 cuando nadie tiene `conext.cod='15'`.
- **La empresa 28 es PORSAN E HIJOS CONSTRUCCIONES SL** (`auxemp`, Sigrid). Sus
  103 fichas: 0 con direccion, cliente, `conext` 15, presupuesto o cierres.
- `con.emp` + `con.cod` es unico: la identidad de una obra es el par. En 10
  codigos fuera del universo (0001-0005, CM, CP, GG, POSTV2, VAR) las fichas de
  distintas empresas **no son copias**, son obras distintas.
- **«obra_id menor» falla en la 0680** (la copia de la 28 tiene el `ide` menor).
- **`condir` SI se ingiere** (la ficha de F-102 decia que no) y **no aporta
  nada**: 0 de 922 fichas de obra tienen fila, tambien en Sigrid.
- Las cifras de Juan se reproducen exactas: 0672+ empresa 1, 57 / 48 con `dir1`
  y los nueve sin ella; en curso, 40 / 34; la 0715 sin CP ni municipio.
- Donde aparece el `obra_id` de una copia de la 28 dentro del universo: casi
  solo en `personal.partes_lineas` (14.079 lineas, 39 fichas, 1.677.332,46 €;
  la 0704 Siroco, 531 lineas, 2.563 h, 57.667,50 €), 3 lineas de compras
  (484 €) y el puente de centros de coste. Retenciones y contratos: 0. Tabla
  por objeto, con la regla del humano, en `design.md` §1.3.
- Fuera de alcance: 55 obras propias de Porsan (0006-0060) estan en
  `stg.obras` sin presupuesto ni seguimiento.

## Decisiones del humano (2026-09-23) y como quedan en la spec

- **D1 · Ranking: NO la opcion B.** Regla del humano: «la ficha principal es la
  de Construcciones Ruesma». Orden: **empresa 1** -> `conext 15` ->
  `num_cierres` DESC -> `tiemod` DESC -> `ide` DESC; sin ficha de la 1, o con
  varias, decide el resto (hoy: 5 codigos sin la 1, 0001-0005, fuera del
  universo; ninguno con dos). Medido sobre el mismo `raw`, en solo lectura:
  - Frente al `stg.obras` de hoy cambian **4 codigos**: 0720 (entra en `mart`),
    **0581** (UTE 27 -> empresa 1: de 20 cierres y 85.524 filas de plan y de
    `mart`, 76 de `cierre`, a una ficha con 0: **sale entera**), **0606** (UTE 31
    -> empresa 1: de 24 cierres, 279.817 de plan, 71.249 de `mart` y 92 de
    `cierre`, a 15 cierres y 1.097 de plan: **se reduce**) y 0671 (UTE 34 ->
    empresa 1: 1 cierre -> 0, sin efecto en `mart`, hoy 0).
  - Frente a la opcion B cambian 5: 0252, 0517, 0581, 0606, 0671.
  - **0252 y 0517 quedan como hoy**: ficha de la 1 sin cierres; sus 7.564 y
    72.737 filas de plan (fichas UTE) siguen sin llegar a `mart`.
  - Juan se reproduce igual: 0672+, 57 principales de la 1, 48 con `dir1`.
  - **RIESGO PENDIENTE DE ACEPTAR (T0 bloquea)**: 0581 y 0606 pasan a una ficha
    de la empresa 1 con menos datos. Alternativa: separar la eleccion de
    `stg.obras` de la marca de `maestro` (rompe «la marca casa con stg»).
  - Y un efecto en `compras`: los hechos de las 8 fichas UTE (83.375 lineas,
    31.171.472,60 € de FACTURA+ABONO) dejan de casar con `mart.v_pbi_dim_obra`
    por `obra_id`; por eso las vistas de consumo ganan `obra_principal_id`.
- **D2 (A) y D3 (ingerir `auxemp`)**: aprobadas como se recomendaron.
- **D4**: `facturas` (esquema `fase1`, repositorio aparte) es independiente: se
  quita la tarea de aviso. Entra en su lugar el **repaso de `compras` y de toda
  ficha con relacion a `maestro.obras.obra_id`**, objeto por objeto
  (`design.md` §1.3): las cinco vistas de consumo de `compras` con obra ganan
  `obra_principal_id` y su relacion; las cuatro tablas de `compras` con obra,
  `retenciones` (2) y `maestro.proveedores_obra`/`centros_coste` solo cambian de
  ficha (texto de traduccion con cifras). Sin obra y por tanto sin copias
  posibles (`information_schema`): `facturas`, `albaranes`, `contrato_lineas`,
  `vencimientos`, `v_facturas_pago`, `formas_pago`, `documento_texto`,
  `documento_comentarios`. `mart`, `cierre` y `stg.obras` leen `stg.obras`: solo
  principales por construccion. `personal` (2 fichas), despues de F-101.
  Copias de la 28 en `compras` confirmadas por objeto: 3 lineas de factura en
  `factura_lineas` y `fact_compras_linea` (484,00 €), 3 filas en
  `v_pbi_proveedor_obra`; 0 en contratos, albaranes y el resto.

## Como se midio

`raw` de la ingesta 2026-09-23 00:48 UTC, por `psycopg` con
`default_transaction_read_only=on` (un `CREATE TEMP VIEW` fue rechazado por la
sesion, que es la prueba de que era de solo lectura); Sigrid por
`SigridApiClient.leer_sql` (`auxemp`, `condir`, recuentos de `obr`/`con`);
`mart` y `cierre` por el MCP. Scripts en el scratchpad de la sesion, fuera del
repositorio. Consultas clave, para reproducir:

```
-- ranking R2 (el <cuerpo> de la vista, reducido)
WITH nf AS (SELECT obride, count(*) n FROM raw.obrfas GROUP BY obride),
f AS (SELECT o.ide, c.cod, c.emp, c.tiemod, COALESCE(nf.n,0) nf,
      EXISTS (SELECT 1 FROM raw.conext x WHERE x.conide=o.ide AND x.cod='15') cx
      FROM raw.obr o JOIN raw.con c ON c.ide=o.ide LEFT JOIN nf ON nf.obride=o.ide)
SELECT *, ROW_NUMBER() OVER (PARTITION BY cod ORDER BY cx DESC, nf DESC,
       (emp=1) DESC, tiemod DESC NULLS LAST, ide DESC) rn FROM f;
-- condir en Sigrid
SELECT COUNT(*) FROM condir d JOIN obr o ON o.ide = d.conide;   -- 0
```
