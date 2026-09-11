<!-- progress/impl_F-081.md -->
# F-081 · Informe de implementación

Rama `feature/F-081-deudas-review-F-073`. Rigor `estandar`. Sin spec (`sdd:
false`): el contrato son los **siete criterios `acceptance`** de la ficha.
Nacen de las «Observaciones» de `progress/review_F-073.md`.

`bash harness/init.sh` **antes de empezar**: exit 0, `ENTORNO LISTO`, 4.367
passed / 171 skipped en 954,53 s, PUERTA COBERTURA [OK] 93,6 % (791/845).

## T1 · La medición, en SOLO LECTURA y de primera mano (2026-09-11)

El Postgres compartido **no era alcanzable** desde esta máquina (`connection
timeout expired` contra `psql-albaranes-rs9k2`, dos intentos, con y sin
sandbox), así que la medición se hizo contra **la fuente que gobierna de
verdad**: Sigrid, por `sigrid-api` (`POST /api/sql/read`, de lectura por
construcción), con el cliente del ETL (`main._get_api().leer_sql`).

`SELECT COUNT(*), est NULL, est vacía, res sin valor FROM dbo.auxefp`:

| filas | `est` a NULL | `est` a `''` | `res` sin valor |
|---|---|---|---|
| **10** | **5** | **5** | **0** |

Las 10 filas, una a una: `est` es `''` en los `ide` 5-9 y `NULL` en los 10-14;
`res` trae `CHEQUE`, `EFECTIVO`, `PAGARÉ`, `RECIBO`, `TRANSFERENCIA`, `LETRA`,
`SÓLO CONFIRMING `, `CONFIRMING / PAGARÉ`, `COMPENSACIÓN SALDOS` y `TARJETA
CRÉDITO`. **El hecho queda confirmado por mi cuenta**: el nombre está en `res`
y `est` no dice nada de nadie.

## T2 · El barrido: la mentira se repite UNA vez más (criterio 2)

Barrido de los comentarios de `config/tables_sigrid.yaml` que atribuyen a una
tabla la columna del nombre legible, contrastados contra
`INFORMATION_SCHEMA.COLUMNS` de Sigrid (solo lectura, misma vía):

| Entrada | Lo que dice el YAML | Medido | Veredicto |
|---|---|---|---|
| `auxefp` | el nombre está en `est` | `est` NULL/vacía en las 10 | **falso** |
| `cen` | «basta con ide + **res** para mostrar el texto» | `cen` **no tiene `res`**: 68 columnas, y las que se le parecen son `reside` (int) y `resepifor1…` | **falso** |
| `auxpro` / `auxmun` | `res` = nombre de provincia / municipio | `res` existe y está informado en 96/96 y 56.054/56.054 | cierto |
| `auxpag` | `cod`, `res`, `formul` | `res` informado en 69/69 | cierto |
| `prv` | `cif`, `raz`, y el nombre también en `con.res` | las tres columnas existen | cierto |
| `obrprv` | trae `cod` y `res` | existen; la tabla tiene **0 filas** (ya declarado) | cierto |
| `rec` | «no tiene `cod` ni `res` propios» | ninguna de las dos existe | cierto |
| `cua` | «el código y el nombre salen de `con`, no de aquí» | ninguna de las dos existe | cierto |
| `cet` | «la `cod` que el documento atribuye NO EXISTE» | no existe; sí `res` (40 filas, 1 vacía) | cierto |

**`cen` es la misma mentira y es más grave**: atribuye a la tabla una columna
que **no existe en Sigrid**. Y es el error exacto que `test_f006_fuente_que_
gobierna.py` documenta en su cabecera —«un campo `res` atribuido a `cen` que en
realidad es de `cenrep`»—: quedó corregido en las fichas y **siguió vivo en el
YAML de la ingesta**, que es donde mira quien va a escribir el SQL.

**¿Lo creyó algún SQL o alguna ficha?** No, y está comprobado:

* `grep -rn "raw.cen" --include=*.sql`: dos usos, y ninguno lee `cen.res`.
  `maestro/04_centros_coste.sql` toma `cc.res` de **`raw.con`**;
  `cierre/05_views_cabecera.sql` solo usa `cen.ide`.
* `grep -rn "auxefp"` sobre `etl_sigrid/`: un único SQL,
  `compras/04_formas_pago.sql`, que ya usa `ef.res` (F-073 lo esquivó).
* Fichas: `grep -rn "cen\.res"` sobre `config/diccionario/` no devuelve nada, y
  atribuciones de ese tipo ya las veta `test_f006_r26_ninguna_ficha_atribuye_a_
  su_tabla_un_campo_no_derivado`. La ficha de `compras.formas_pago` describe
  `auxefp.res` y **denunciaba** la mentira del YAML (T4 la pone al día).

La conclusión que importa: **las fichas del diccionario tenían guardián y el
YAML de la ingesta no**. Eso es lo que arregla el criterio 3.

## T3 · Fase RED del test que impide deshacerlo (criterio 3)

`tests/test_f081_yaml_ingesta.py` no compara el YAML con otro documento —eso
es lo que produjo las dos mentiras de F-006— sino con **nuestro propio SQL**:
la columna de nombre que el YAML atribuye a una tabla tiene que estar entre las
que el SQL que la publica lee de verdad. Cinco entradas bajo vigilancia, tres
de ellas (`auxpag`, `auxpro`, `auxmun`) como **control positivo**.

Comando: `python -m pytest tests/test_f081_yaml_ingesta.py -q -p no:randomly`

```
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c3_el_yaml_solo_atribuye_el_nombre_a_una_columna_que_el_sql_lee[auxefp]
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c3_el_yaml_solo_atribuye_el_nombre_a_una_columna_que_el_sql_lee[cen]
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c1_el_yaml_dice_que_el_nombre_del_medio_de_pago_esta_en_res
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c1_el_yaml_deja_escrita_la_medicion_que_lo_respalda
4 failed, 7 passed in 0.23s
```

El detalle de los dos paramétricos, con el mensaje real del aserto:

```
E  AssertionError: config/tables_sigrid.yaml atribuye a `auxefp` ['est'] como
E  columna de nombre legible, y compras/04_formas_pago.sql -que es quien
E  gobierna el hecho- solo lee ['cla', 'ide', 'res'].
E  assert {'est'} <= {'cla', 'ide', 'res'}

E  AssertionError: config/tables_sigrid.yaml atribuye a `cen` ['res'] como
E  columna de nombre legible, y maestro/04_centros_coste.sql -que es quien
E  gobierna el hecho- solo lee ['ide'].
E  assert {'res'} <= {'ide'}
```

**El test encontró la segunda mentira él solo**: `cen` no estaba en el encargo.
