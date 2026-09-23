<!-- progress/spec_F-102.md -->
# F-102 · Spec escrita (spec-author, 2026-09-23)

Entregado `specs/F-102-obra-duplicada-empresa-28/` en la rama
`hotfix/F-102-obra-duplicada-empresa-28` (desde `main`, en worktree aislado:
F-101 se implementa en el arbol principal). Tamanos: requirements 137/150,
design 250/250, 17 tareas (T0-T16). Ficha: `sdd: true`, `spec_ready`.

## Lo que la spec propone, en cinco lineas

1. Una vista nueva, `stg.v_obra_fichas`, es la **unica** definicion de "ficha
   principal": la construye `stg/03_obras.sql`, de ella sale `stg.obras` y de
   ella lee `maestro.obras`. La marca casa con la deduplicacion por construccion.
2. `maestro.obras` gana al final `empresa_id`, `nombre_empresa`,
   `es_ficha_principal`, `num_fichas_codigo` y `obra_principal_id`, sin perder
   filas (922).
3. Nombre de empresa: ingerir `auxemp` (38 filas).
4. No se reescribe el `obra_id` de ningun hecho: se traduce al leer con
   `maestro.obras.obra_principal_id`, y una regla dura nueva
   (`R-OBRA-FICHA-PRINCIPAL`) lo explica con las cifras.
5. Diccionario, `ARCHITECTURE.md`, `azure-apps` y aviso a `facturas`.

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
  completa en `design.md` §1.4.
- Fuera de alcance: 55 obras propias de Porsan (0006-0060) estan en
  `stg.obras` sin presupuesto ni seguimiento.

## Decisiones abiertas para el humano (`design.md` §8)

- **D1 · Ranking de la ficha principal.** Recomendada (B): `conext 15 ->
  num_cierres DESC -> empresa 1 -> tiemod -> ide`. Cambia `stg.obras` en 0252,
  0517 y 0720 (581 de 584 iguales) y **esas tres obras entran en `mart` y
  `cierre`**, con el `obra_id` de la 0720 cambiando en Power BI. (A) el ranking
  de hoy: cero cambio, pero la 0720 queda en la copia vacia. (C) solo arregla 0720.
- **D2 · Traducir el `obra_id` de las copias.** Recomendada (A): no reescribir;
  traducir al leer por `obra_principal_id`. (B) columna traducida en `personal`
  tras F-101, como feature aparte. (C) reescribir hechos: descartada.
- **D3 · Ingerir `auxemp`** para el nombre de la empresa. Recomendada: si.
- **D4 · Aviso a `facturas`.** Recomendada: texto listo en
  `progress/impl_F-102.md` que el humano lleva a esa sesion.

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
