<!-- progress/spec_F-102.md -->
# F-102 · Spec escrita (spec-author, 2026-09-23)

`specs/F-102-obra-duplicada-empresa-28/` en la rama
`hotfix/F-102-obra-duplicada-empresa-28` (desde `main`, worktree aislado).
**Quinta pasada, APROBADA por el humano**: requirements 150/150, design
242/250, 17 tareas (T1-T17). Ficha: `sdd: true`, `spec_ready`. Las
pasadas anteriores (opcion B; empresa 1 aplicada tambien a `stg.obras`) quedan
**sustituidas**: ver historial de commits de la rama.

## Decisiones finales del humano (2026-09-23)

**Modelo**: «las obras son por empresa. La UTE es una cosa y Ruesma otra [...] no
estamos consolidando. El codigo igual representa que es la misma obra, pero
desde la perspectiva de diferentes empresas. Lo mismo con Porsan».

- **Alcance**: solo identificadores. `obra_id` sigue siendo la clave tecnica;
  `maestro.obras` gana `empresa_id`, `nombre_empresa`, `clave_obra`
  (`'1-0581'`, `'27-0581'`), `num_fichas_codigo`, `es_ficha_principal` (ficha de
  la empresa 1; sin ella, `conext 15` -> cierres -> `tiemod` -> `ide`) y
  `obra_principal_id`. `personal.recursos` gana `empresa_id`, `nombre_empresa` y
  `clave_recurso`. El diccionario: por codigo se cruza siempre con la empresa o
  por la clave (regla `R-CODIGO-POR-EMPRESA`).
- **`stg.obras` no cambia** (ni 0720 ni ninguna): 0581 y 0606 no pierden datos.
  El seguimiento «solo Ruesma» y las demas empresas son **F-106**.
- **D2 (A)** no se reescribe ningun `obra_id`; **D3** se ingiere `auxemp`;
  **D4** `facturas` independiente, sin aviso, y en su lugar el repaso de
  `compras` y de toda ficha con relacion a `maestro.obras.obra_id`; **D5 (A)**
  sin marca de «misma persona en otra empresa».

## Como queda el diseno

- La definicion vive en **`maestro.v_obra_fichas`** (nueva, lee solo `raw`), no
  en `stg`: `stg.obras` no la usa, y en `stg` sugeriria que el seguimiento la
  sigue. `compras` la lee sin depender de `stg` (patron de F-094).
  `stg/03_obras.sql` queda identico a `main` (test por hash).
- `obra_principal_id` sale de la misma ventana que `es_ficha_principal`: ficha
  de Ruesma si el codigo la tiene, la propia si no.
- Las cinco vistas de consumo de `compras` con obra ganan `empresa_id` y
  `clave_obra` (no `obra_principal_id`): cada factura queda con SU empresa y
  nadie suma las de la UTE en la obra de Ruesma. `obra_principal_id` vive solo en
  `maestro.obras`, como referencia, y su ficha prohibe usarlo para agregar.
- `personal.recursos`: **depende de F-101 fusionado en `main`** (T14 bloquea;
  T1-T13 se entregan igual).

## Lo medido (todo en solo lectura, 2026-09-23)

- **Claves unicas**: `clave_obra` 922 para 922 fichas; `clave_recurso` 2.618
  para 2.618; 0 codigos vacios, 0 empresas a 0. Un test lo vigila por la
  construccion y `check-unicidad` en la base.
- Obras: 922 fichas, 846 codigos, 58 repetidos. Empresa 28 = PORSAN E HIJOS
  CONSTRUCCIONES SL: 103 fichas, 0 con direccion, cliente, presupuesto o cierres.
- Principal = ficha de Ruesma: 846 de 846; 64 de otra empresa (codigos sin ficha
  de la 1). `obra_principal_id` distinto en 59 fichas, 11 de ellas codigos
  administrativos (CM, CP, GG, POSTV2, VAR) que se advierten.
- **Difiere de `stg.obras` en 0581, 0606, 0671 y 0720** (F-106). 0252 y 0517
  coinciden.
- `compras`, lineas de fichas no Ruesma: 91.431 en `fact_compras_linea`
  (54.198.506,59 € de FACTURA+ABONO), de ellas **84.233 (31.770.036,29 €) con
  codigo compartido con una ficha de Ruesma** (las que se mezclarian agregando
  por codigo); en `v_pbi_proveedor_obra`, 1.880 y 1.066. Copias de la 28: solo 3
  lineas (484,00 €). 9.363 lineas sin obra. Sin columna
  de obra: `facturas`, `albaranes`, `contrato_lineas`, `vencimientos`,
  `v_facturas_pago`, `formas_pago`, `documento_texto`, `documento_comentarios`.
- Juan reproducido: 0672+, 57 principales de la 1, 48 con `dir1`; `condir` no
  aporta direcciones de obra (0 de 922, tambien en Sigrid).
- Recursos: 61 codigos repetidos, 0 dentro de una empresa; `MO/0009` en las
  empresas 1, 27, 18 y 28; 13 de 91 personas de fuera de la 1 comparten NIF con
  una de la 1; sus partes: 26.426 lineas, 3.226.523,83 €.
- «`obra_id` menor» falla en la 0680 (la copia de la 28 tiene el `ide` menor).

## APROBADA (humano, 2026-09-23)

Con la ultima decision incorporada: en `compras`, las cinco vistas de consumo
publican `empresa_id` y `clave_obra`, **no** `obra_principal_id`, porque el
humano no consolida y cada factura debe quedar con su empresa;
`obra_principal_id` queda solo en `maestro.obras` como referencia de cual es la
ficha de Ruesma. Sin decisiones abiertas. Condiciones para implementar: T1-T13
ya; T14-T15 cuando F-101 este en `main`. El lider crea la ficha **F-106**
(seguimiento por empresa: `stg.obras` «solo Ruesma» y las demas empresas).

## Como se midio

`raw` de la ingesta 2026-09-23 00:48 UTC por `psycopg` con
`default_transaction_read_only=on` (un `CREATE TEMP VIEW` fue rechazado: prueba
de que era de solo lectura); Sigrid por `SigridApiClient.leer_sql` (`auxemp`,
`condir`, recuentos); `mart` y `cierre` por el MCP. Scripts en el scratchpad de
la sesion, fuera del repositorio. Para reproducir:

```
-- el <cuerpo> de maestro.v_obra_fichas, reducido
WITH nf AS (SELECT obride, count(*) n FROM raw.obrfas GROUP BY obride),
f AS (SELECT o.ide, c.cod, c.emp, c.tiemod, COALESCE(nf.n,0) nf,
      EXISTS (SELECT 1 FROM raw.conext x WHERE x.conide=o.ide AND x.cod='15') cx
      FROM raw.obr o JOIN raw.con c ON c.ide=o.ide LEFT JOIN nf ON nf.obride=o.ide)
SELECT *, emp::text||'-'||cod AS clave, ROW_NUMBER() OVER (PARTITION BY cod
       ORDER BY (emp=1) DESC, cx DESC, nf DESC, tiemod DESC NULLS LAST, ide DESC) rn
FROM f;
SELECT count(*), count(DISTINCT c.emp::text||'-'||c.cod)
FROM raw.res r JOIN raw.con c ON c.ide = r.ide;                -- 2618 | 2618
SELECT COUNT(*) FROM condir d JOIN obr o ON o.ide = d.conide;  -- Sigrid: 0
```
