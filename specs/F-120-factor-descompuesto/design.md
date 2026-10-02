<!-- specs/F-120-factor-descompuesto/design.md -->
# F-120 · Diseño

Corrección del troceado de F-097 dentro del mismo esquema `descompuestos`. No
cambia la ingesta, ni el incremental, ni la regla del cuadre: cambia cómo se lee
UN campo, se publica una columna y se aprovecha el sello de F-097 para retrocear
lo ya cargado. Cifras y decisiones: `progress/spec_F-120.md`.

## 1. Lo medido que fija el diseño

- El campo 14 es `<factor>x<rendimiento>` cuando la línea tiene factor, y un
  número cuando no. En la 0713 / 400854 / v6 el texto `1.00021x1` es
  `dncpro.factip = 1, faccan = 1.00021, canren = 1` de la misma línea (campo 36
  = `dncpro.ide`): **el orden es factor x rendimiento**.
- Con `ROUND(precio x factor x rendimiento, 2)` línea a línea, la 400854 v6 suma
  **249,41 = su precio**: cuadra al céntimo (§3 de `spec_F-120.md`).
- El campo 4 (`cantidad_total`) YA lleva el factor (1091,5 x 1,00021 x 1 =
  1091,729). `importe_total` no cambia.
- `dncpro` guarda el factor aparte (`factip`, `faccan`) y `canren` es el
  rendimiento limpio: PLANIF_JO tenía el mismo defecto sin NULL a la vista
  (6.920 partidas NO_CUADRA que pasan a CUADRA, §4). Por eso entra (D5).
- Formas reales del campo 14 en 4,5 M registros: número, vacío, `a x b`, `a x`,
  con signo en cualquiera de los dos lados (`-1x1`, `1x-0.011`) y factor 0;
  ninguna `X` mayúscula, coma decimal, blanco interno ni tres factores. Solo 15
  registros raros, que salen NULL (D2, §2).

## 2. Ficheros a modificar

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/domain/descompuestos.py` | `PATRON_FACTOR_RENDIMIENTO`; `factor_rendimiento()`; `RegistroDes.factor`; `POSICIONES["rendimiento"]` pasa a `POSICIONES["factor_rendimiento"]` (misma posición 14); `trocear_des` con R1-R11 |
| `etl_sigrid/infrastructure/postgres/sql/descompuestos/01_troceado.sql` | `DROP FUNCTION IF EXISTS` + `CREATE`; columna `factor` en `RETURNS TABLE`; capa que parte el campo 14; `importe_unitario` con el factor; cabecera (formato y sello) |
| `.../descompuestos/02_lineas_coste.sql` | `factor NUMERIC` al final del DDL de `lineas` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS factor NUMERIC`; `factor` en los dos `INSERT` (ESTUDIO: `t.factor`; PLANIF_JO: R14-R16) |
| `.../descompuestos/03_lineas_master.sql` | `factor` en la lista de columnas y en el `SELECT` (`t.factor`) |
| `.../descompuestos/06_views.sql` | `factor` como ÚLTIMA columna de las tres vistas |
| `etl_sigrid/application/steps/build_descompuestos_step.py` | `FICHEROS_DEL_SELLO = ("00_setup.sql", "01_troceado.sql", "03_lineas_master.sql")` y su docstring |
| `config/diccionario/descompuestos.yaml` | fichas de `lineas`, `cuadre_partida`, las tres vistas y `fn_trocear` (R24, R25) |
| `config/diccionario/00_global.yaml` | `version` 38 -> 39 |
| `tests/test_f097_descompuestos.py` | `COLUMNAS_LINEAS` + `factor` al final; aserción de `importe_unitario`; test del sello con los tres ficheros |
| `docs/ARCHITECTURE.md` | sección F-097: el campo 14 es «factor x rendimiento»; `00_setup.sql` en el sello |
| `main.py` | ayuda de `build-descompuestos --sin-tope`: la duración medida (§6) en vez de «20-40 min sin medir» |
| `../azure-apps/datamart_seg_anual.md` | una línea: `lineas` publica `factor` (repo propio, commit propio) |

**Fichero a crear**: `tests/test_f120_factor.py` (§7).

## 3. Ficheros que NO se tocan

`ingest_descompuestos_step.py` (no se relee Sigrid), `00_setup.sql` (`fn_num`
sirve tal cual: cada lado de la `x` se convierte con ella), las tablas de estado
`_des_texto` y `_versiones_cargadas` (ni DDL ni datos fuera del sello),
`04_elementos.sql` y `05_cuadre.sql` (no leen rendimiento ni factor; el cuadre
suma `importe_unitario` y se corrige solo), `planificar_relectura` y
`planificar_troceado`, `config/settings.py` (sin flag nuevo, D3) y los esquemas
fuera de `descompuestos`.

## 4. Dominio (`etl_sigrid/domain/descompuestos.py`, capa domain)

```python
_CUERPO_NUMERO = r"[-+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]{1,3})?"
PATRON_NUMERO = rf"^{_CUERPO_NUMERO}$"            # el MISMO texto que hoy
PATRON_FACTOR_RENDIMIENTO = rf"^{_CUERPO_NUMERO}x({_CUERPO_NUMERO})?$"

def factor_rendimiento(texto: str | None) -> tuple[Decimal | None, Decimal | None]:
    """(factor, rendimiento) del campo 14: número -> (1, n); `a x b` -> (a, b);
    `a x` -> (a, None); vacío o raro -> (None, None)."""
```

- `PATRON_NUMERO` conserva su texto exacto (el test de F-097 lo compara con
  `fn_num`); un test nuevo comprueba que no cambió.
- `RegistroDes` gana `factor: Decimal | None`. `trocear_des` toma el campo con
  `_texto(campos, POSICIONES["factor_rendimiento"])` y llama a
  `factor_rendimiento`.
- `importe_unitario = _redondeo(precio x factor x rendimiento)`, multiplicando en
  un `decimal.localcontext()` de 60 dígitos (R11): con el contexto por defecto
  (28) un `2.05405405405405 x 384.721 x 0.0000005` largo podría redondear antes
  que el NUMERIC exacto. `porcentaje` sigue siendo `rendimiento x 100` (R8).

## 5. SQL (esquema `descompuestos`)

**`01_troceado.sql`.** `CREATE OR REPLACE` no puede cambiar las columnas de un
`RETURNS TABLE`: va `DROP FUNCTION IF EXISTS descompuestos.fn_trocear(TEXT);`
delante (R19). Nada depende de ella en el catálogo: es `LANGUAGE sql` sin `BEGIN
ATOMIC` y ninguna vista la usa (02, 03 y 05 la llaman en tiempo de ejecución). En
la subconsulta de campos, la posición 14 se lee como texto:

```sql
NULLIF(btrim(split_part(g.reg, '|', 15)), '') AS factor_rendimiento,
```

y una capa intermedia (subconsulta o `CROSS JOIN LATERAL`) la parte:

```sql
CASE WHEN descompuestos.fn_num(c.factor_rendimiento) IS NOT NULL THEN 1::NUMERIC
     WHEN c.factor_rendimiento ~ '<PATRON_FACTOR_RENDIMIENTO>'
         THEN descompuestos.fn_num(split_part(c.factor_rendimiento, 'x', 1))
END AS factor,
CASE WHEN descompuestos.fn_num(c.factor_rendimiento) IS NOT NULL
         THEN descompuestos.fn_num(c.factor_rendimiento)
     WHEN c.factor_rendimiento ~ '<PATRON_FACTOR_RENDIMIENTO>'
         THEN descompuestos.fn_num(split_part(c.factor_rendimiento, 'x', 2))
END AS rendimiento
```

`fn_num('')` ya es NULL, así que `a x` deja el rendimiento NULL (R3). El importe:
`CASE WHEN abs(ROUND(c.precio * c.factor * c.rendimiento, 2)) < 1e16 THEN
ROUND(c.precio * c.factor * c.rendimiento, 2)::NUMERIC(18,2) END`. El test de
posiciones de F-097 (`split_part ... AS nombre` frente a `POSICIONES`) sigue
valiendo con la clave renombrada.

**`02_lineas_coste.sql`.** DDL con `factor NUMERIC` al final (instalación nueva)
y, tras el `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE descompuestos.lineas ADD
COLUMN IF NOT EXISTS factor NUMERIC;` (base existente; sin `DEFAULT`: es solo
catálogo, instantáneo, y las filas aún no retroceadas quedan con `factor` NULL,
que es la verdad). PLANIF_JO:

```sql
CASE p.factip WHEN 1 THEN p.faccan::NUMERIC WHEN 0 THEN 1::NUMERIC END  -- factor
CASE WHEN abs(ROUND(p.pre::NUMERIC * <factor> * p.canren::NUMERIC, 2)) < 1e16
     THEN ROUND(p.pre::NUMERIC * <factor> * p.canren::NUMERIC, 2) END    -- importe_unitario
```

(`<factor>` repetido o en un `CROSS JOIN LATERAL`; lo decide el implementer.)

**`03_lineas_master.sql`** solo añade `factor`/`t.factor`. **`06_views.sql`**:
`factor` al final de cada `SELECT`, porque `CREATE OR REPLACE VIEW` solo admite
columnas nuevas al final (D8).

## 6. El retroceo (D3, D4)

**No hace falta mecanismo nuevo.** F-097 ya retrocea todo cuando cambia el sello
(hash de `01_troceado.sql` y `03_lineas_master.sql`): `sql_versiones_pendientes`
devuelve toda versión con `sello_troceado IS DISTINCT FROM` el vigente. Esta
feature cambia los dos ficheros y además añade `00_setup.sql` al sello (R21), así
que la primera ejecución con el código nuevo ve las 3.025 versiones pendientes.

- **Invalidar `atributos_troceado` NO serviría**: el paso 5 de `03` solo hace
  `UPDATE` de los flags de versión, no retrocea.
- **Un flag `--retrocear-todo` sobraría**: el sello lo hace solo y sin estado
  nuevo. Un `UPDATE ... SET sello_troceado = NULL` a mano tampoco hace falta.
- **Ritmo**: la nocturna lo haría a 300 MB por noche (~7 noches, vigentes
  primero), con el master MEZCLADO entre medias. Se propone hacerlo de una vez a
  mano, `python main.py build-descompuestos --sin-tope` + `apply-grants` (el
  `DROP FUNCTION` puede llevarse permisos), fuera de la nocturna y mirando antes
  los créditos de CPU. Coste estimado en §5 de `spec_F-120.md`: el troceado
  completo de la primera carga tardó 916,9 s (7 lotes, tabla vacía); con el
  `DELETE` de ~4,4 M líneas y su cuadre, 20-30 min, y ~2 GB de tuplas muertas en
  `lineas` hasta el autovacuum (base de 33 GB sobre 64).
- **El orden de despliegue importa**: si el retroceo corre con el código nuevo
  y la nocturna con la imagen vieja, la imagen vieja ve otro sello y retrocea
  hacia atrás, y su `CREATE OR REPLACE FUNCTION fn_trocear` falla contra la
  función nueva (otro tipo de retorno): `build_descompuestos` FAILED. Primero
  la imagen del job, luego el retroceo. Nunca al revés.

## 7. Tests (`tests/test_f120_factor.py`, sin red ni BBDD)

- Tabla parametrizada de formas medidas (§2 de `spec_F-120.md`): `0.41`,
  `1.00021x1`, `1.22x0.003`, `0.99765x-0.15`, `-1x1`, `-23.05x`, `0x1`,
  `1.1x`, `0x`, vacío, `-0.001`, los dos raros reales (`0678.CDMA15`,
  `1963589xF321886`) y sintéticos (`1X2`, `1,5`, `1x2x3`, `1 x 2`, `x2`, `abc`)
  -> `(factor, rendimiento)` (R1-R5, R9).
- La 400854 v6: 19 registros sintéticos de 38 campos con los valores de §3 de
  `spec_F-120.md` -> 9 con forma factor, línea 13 = 1,24, suma 249,41 (R13).
- Porcentaje con factor: `porcentaje` sin factor, importe con él (R8).
- Precisión: producto de muchos decimales igual al exacto (R11).
- Texto SQL: `PATRON_FACTOR_RENDIMIENTO` literal en 01, `fn_num` a cada lado,
  importe con `c.factor`, `DROP FUNCTION IF EXISTS` antes del `CREATE`, `factor`
  en `RETURNS TABLE`, el `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, el `CASE
  p.factip` de PLANIF_JO, `factor` último en las tres vistas, `03` lo inserta
  (R12, R14-R19). `PATRON_NUMERO` intacto.
- Sello: incluye `00_setup.sql` y difiere de `99f827a11969d59f` (R20, R21).
- Diccionario: `factor` en las fichas de `lineas` y las tres vistas; ESTUDIO
  avisa de la medición actual y de MASTER_INICIAL (R24, R25); versión 39.

**Contraste SQL frente a espejo** (como F-097): un PostgreSQL 16 desechable en
el scratchpad, con una muestra de `_des_texto` copiada en solo lectura (todas las
formas de §2, la 0713 entera y el ámbito 3): `fn_trocear` frente a `trocear_des`,
0 diferencias. Lo hace el implementer; nunca contra Azure.

## 8. Encaje y límites

Todo queda en `descompuestos`, módulo independiente (R26 de F-097: lee solo
`raw` y su esquema). No hay responsabilidad nueva fuera del ETL ni contacto con
`sigrid-api`: el retroceo no lee Sigrid. **Fuera de alcance**: las líneas con el
campo 14 VACÍO pero con cantidad y precio distintos de 0 (D10: al menos 95.000
de las ~461.000 que contó el líder; no tienen factor y la causa es otra), las
partidas que dejan de cuadrar porque sus líneas con factor parecen detalle de
otras (D10, 310 casi todas de una obra), y la «Planificación compras» como
fuente de la cantidad de Estudios (D7 solo documenta).

## 9. Riesgos y alternativas descartadas

- **Leer el factor de `dncpro` en el master por el enlace del campo 36**:
  descartado; `dncpro` es el estado ACTUAL y el master es una foto por versión
  (la 400854 v6 tiene `1.013x0.06` y hoy `dncpro` dice 1,0167 x 0,144).
- **`factor` DEFAULT 1**: descartado; diría «sin factor» de líneas aún no
  retroceadas.
- **Columna de texto con el campo 14 en bruto**: descartada; las formas raras
  se miden con una consulta, no con una columna para siempre (D2).
- **Riesgo**: una forma nueva que aparezca mañana sale NULL, como hoy; queda a la
  vista en el cuadre y en la consulta de §2 de `spec_F-120.md`, que se puede
  repetir.
