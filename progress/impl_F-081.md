<!-- progress/impl_F-081.md -->
# F-081 · Informe de implementación

Rama `feature/F-081-deudas-review-F-073`. Rigor `estandar`. Sin spec (`sdd:
false`): el contrato son los **siete criterios `acceptance`** de la ficha.
Nacen de las «Observaciones» de `progress/review_F-073.md`.

`bash harness/init.sh` **antes de empezar**: exit 0, `ENTORNO LISTO`, 4.367
passed / 171 skipped en 954,53 s, PUERTA COBERTURA [OK] 93,6 % (791/845).

## T1 · La medición, en SOLO LECTURA y de primera mano (2026-09-11)

El Postgres compartido **no era alcanzable** desde esta máquina (`connection
timeout expired`, dos intentos, con y sin sandbox), así que se midió contra la
fuente que gobierna de verdad: Sigrid, por `sigrid-api` (`POST /api/sql/read`,
de lectura por construcción), con `main._get_api().leer_sql`.

`SELECT COUNT(*), est NULL, est vacía, res sin valor FROM dbo.auxefp` da
**10 filas**: `est` a NULL en **5** y a `''` en las otras **5**, `res` sin valor
en **0**. Fila a fila: `est` es `''` en los `ide` 5-9 y `NULL` en los 10-14;
`res` trae `CHEQUE`, `EFECTIVO`, `PAGARÉ`, `RECIBO`, `TRANSFERENCIA`, `LETRA`,
`SÓLO CONFIRMING `, `CONFIRMING / PAGARÉ`… **Confirmado por mi cuenta**.

## T2 · El barrido: la mentira se repite UNA vez más (criterio 2)

Barrido de los comentarios de `config/tables_sigrid.yaml` que atribuyen a una
tabla la columna del nombre legible, contrastados contra
`INFORMATION_SCHEMA.COLUMNS` de Sigrid (solo lectura, misma vía):

| Entrada | Lo que dice el YAML | Medido | Veredicto |
|---|---|---|---|
| `auxefp` | el nombre está en `est` | `est` NULL/vacía en las 10 | **falso** |
| `cen` | «basta con ide + **res** para mostrar el texto» | `cen` **no tiene `res`**: de sus 68 columnas, las que se le parecen son `reside` (int) y `resepifor1…` | **falso** |

Las otras **siete afirmaciones de ese tipo son ciertas**, comprobadas una a una
contra `INFORMATION_SCHEMA`: `auxpro` y `auxmun` (`res` informado en 96/96 y
56.054/56.054), `auxpag` (69/69), `prv` (`cif`, `raz` y `tipsub` existen),
`obrprv` (`cod` y `res` existen; la tabla tiene 0 filas, ya declarado), `rec` y
`cua` (dicen que **no** tienen `cod` ni `res` propios, y no los tienen) y `cet`
(dice que la `cod` del documento de Sigrid **no existe**, y no existe).

**`cen` es la misma mentira y más grave**: atribuye a la tabla una columna que
**no existe en Sigrid**. Es el error que `test_f006_fuente_que_gobierna.py`
documenta en su cabecera —«un `res` atribuido a `cen` que en realidad es de
`cenrep`»—: corregido en las fichas y **vivo en el YAML de la ingesta**.

**¿Lo creyó algún SQL o alguna ficha?** No, comprobado con `grep`: de
`raw.cen` hay dos usos y ninguno lee `cen.res` —`04_centros_coste.sql` toma
`cc.res` de **`raw.con`** y `cierre/05_views_cabecera.sql` solo usa `cen.ide`—;
de `auxefp`, un único SQL, `compras/04_formas_pago.sql`, que ya usa `ef.res`.
En `config/diccionario/` no aparece `cen.res`, y esas atribuciones ya las veta
`test_f006_r26_ninguna_ficha_atribuye_a_su_tabla_un_campo_no_derivado`; la
ficha de `compras.formas_pago` **denunciaba** la mentira del YAML (T3 la pone
al día).

La conclusión: **las fichas tenían guardián y el YAML de la ingesta no**. Eso
es lo que arregla el criterio 3.

## T3 · Fase RED del test que impide deshacerlo (criterio 3)

`tests/test_f081_yaml_ingesta.py` no compara el YAML con otro documento —eso es
lo que produjo las dos mentiras de F-006— sino con **nuestro propio SQL**: la
columna de nombre que el YAML atribuye a una tabla tiene que estar entre las que
lee el SQL que la publica. Cinco entradas vigiladas, tres (`auxpag`, `auxpro`,
`auxmun`) como **control positivo**.

Comando: `python -m pytest tests/test_f081_yaml_ingesta.py -q -p no:randomly`

```
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c3_el_yaml_solo_atribuye_el_nombre_a_una_columna_que_el_sql_lee[auxefp]
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c3_el_yaml_solo_atribuye_el_nombre_a_una_columna_que_el_sql_lee[cen]
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c1_el_yaml_dice_que_el_nombre_del_medio_de_pago_esta_en_res
FAILED tests/test_f081_yaml_ingesta.py::test_f081_c1_el_yaml_deja_escrita_la_medicion_que_lo_respalda
4 failed, 7 passed in 0.23s
```

El mensaje real de los dos paramétricos, que es el que hace útil el fallo:

```
E  AssertionError: ... atribuye a `auxefp` ['est'] como columna de nombre
E  legible, y compras/04_formas_pago.sql -quien gobierna el hecho- solo lee
E  ['cla', 'ide', 'res'].            assert {'est'} <= {'cla','ide','res'}
E  AssertionError: ... atribuye a `cen` ['res'] ..., y
E  maestro/04_centros_coste.sql solo lee ['ide'].  assert {'res'} <= {'ide'}
```

**El test encontró la segunda mentira él solo**: `cen` no estaba en el encargo.

## T4 · Los dos supervivientes de mutación (criterios 4, 5 y 6)

`tests/test_f081_supervivientes.py`, 7 tests. **Ni `ventana_sql.py` ni
`build_stg_step.py` se tocan** (`git diff 87f4d84..HEAD` sobre los dos: vacío).
La fase RED aquí es la mutación —**vivo antes, muerto después**— con el mutante
que genera `harness.mutacion.generar_mutantes` (mismo fichero, línea, operador
y texto) y restauración verificada por `sha256`.

### 4a · `ventana_sql.py:215` — la denuncia muda

`codigo_obra=str(codigo or "")` → `str(codigo and "")`.

**Antes** (`tests/test_f025_cli.py` + `tests/test_f025_ventana.py`, los que
recorren ese camino):

```
MUTANTE: ventana_sql.py:215 [logico] codigo_obra=str(codigo or ""), -> codigo_obra=str(codigo and ""),
84 passed, 34 warnings in 2.85s
VEREDICTO: SUPERVIVIENTE (exit 0)
RESTAURADO: sha f5def9438b0b OK
```

**Después**, contra el fichero nuevo **y solo contra él**:

```
FAILED tests/test_f081_supervivientes.py::test_f081_c4_cada_denuncia_de_la_ventana_nombra_su_obra[sello_no_vigente-0806]
FAILED tests/test_f081_supervivientes.py::test_f081_c4_una_obra_sin_codigo_se_denuncia_igual_y_sin_reventar
2 failed, 5 passed in 1.75s
VEREDICTO: MUERTO (exit 1)
RESTAURADO: sha f5def9438b0b OK
```

El aserto que faltaba: que la denuncia **diga qué obra**.
`test_f025_r26_un_sello_viejo_se_denuncia` solo miraba la palabra `SELLO`. Los
otros dos tipos construyen el código igual y entran al paramétrico gratis.

### 4b · `build_stg_step.py:732` — **el superviviente era un FALSO POSITIVO**

`if self._plan and self._plan.completa:` → `... or ...`.

Medido antes de escribir nada, contra la **suite entera** y con los argumentos
del propio arnés (`-x -q --tb=no -p no:cacheprovider`):

```
FAILED tests/test_f025_build.py::test_f025_r10_las_sobrantes_solo_se_miran_en_la_reconstruccion_completa
1 failed, 2635 passed, 170 skipped in 157.70s
VEREDICTO: MUERTO (exit 1)
```

Ese test **ya existía byte a byte** en el commit que midió la campaña
(`git show b6eda79:tests/test_f025_build.py`) y ni él ni `build_stg_step.py`
han cambiado. La campaña declaró `Timeouts: 0` y `base rota: 0`: no fue ninguna
de las dos cosas, es un veredicto equivocado. Consulta al humano en
`progress/current.md`; auditar el mutador es otra feature.

El test se escribe igual: la única red que había era un aserto indirecto —una
lista de llamadas al doble— dentro de un test que mide otra cosa. `test_f081_c5_*`
ataca la guarda de frente en sus tres casos y mata al mutante **él solo**:

```
FAILED tests/test_f081_supervivientes.py::test_f081_c5_el_presupuesto_acotado_con_plan_PARCIAL_no_mira_las_sobrantes
1 failed, 6 passed in 1.38s
VEREDICTO: MUERTO (exit 1)
RESTAURADO: sha c33b27bd7c8a OK
```

Y el log del mutante enseña el daño exacto que la guarda evita: `[warning]
ventana_obras_sobrantes obras=[9] tabla=stg.presupuesto` en una noche acotada,
es decir, denunciar como sobrante una obra que solo está **congelada**.

**Segunda nota medida**: el sello de F-025 **no incluye `build_stg_step.py`**.
`sello_vigente_del_repositorio` pasa a `sello_sql` los dos `.sql` de
`FICHEROS_DEL_SELLO` más un parámetro, así que cambiar el texto del módulo no
movería el sello ni reconstruiría las 921 obras. No cambia nada de lo hecho
—no se ha tocado—, pero que nadie decida lo siguiente sobre esa premisa.

## T5 · La campaña de mutación (criterio 7)

`python -m harness.mutacion --feature F-081 --base 87f4d84`, acotada al diff de
**esta** feature: contra `dev` el alcance vuelven a ser las 3.617 líneas de
F-073 —`dev` no se ha movido—, y medir eso sería medir código ajeno otra vez.

```
ALCANCE VACÍO en F-081: ni una línea de producción que mutar (origen rama,
87f4d84..feature/F-081-deudas-review-F-073). No se ha juzgado NADA.
  No se escribe informe: un fichero en progress/ con un cero que nadie ha
  medido es peor que no tener fichero [...]
```

Por eso **no hay `progress/mutacion_F-081.md`**: lo decide la herramienta y
tiene razón. El cero es legítimo y la **prueba de control** sale sola: F-081 no
cambia ni una línea de Python de producción, así que no hay `.py` que mutar
entero. La campaña que sí mide algo es la **acotada de T4**: dos mutantes,
cuatro ejecuciones, vivos antes y muertos después. **Supervivientes: 0.**

## Ficheros tocados

**Producción** (ni una línea ejecutable): `config/tables_sigrid.yaml` —las dos
entradas que mentían, solo comentarios—, la cabecera de
`sql/compras/04_formas_pago.sql` y la ficha de `medio_pago` de
`config/diccionario/compras.yaml`, las dos en pasado, y `00_global.yaml`, que
sube a la **versión 20** con su changelog: republicar un texto distinto con la
etiqueta de ayer es como no republicarlo.

**Tests**: los dos nuevos (11 + 7). En `tests/test_f073_diccionario.py`, R28
pasa de `== "19"` a `>= 19`: nació como candado —la siguiente feature que
tocara una ficha tenía que elegir entre publicar con la etiqueta vieja o tocar
el test— y F-074 y F-079 ya lo comprobaban así. **Papeleo**: `current.md` (con
la consulta al humano) y este informe.

## Lo que NO se hace aquí

**No se audita `harness/mutacion.py`** por el superviviente falso: es el arnés
genérico, la corrección iría a `arnes-base` y la decide el humano (consulta en
`progress/current.md`). Y **no hay verificaciones MANUAL**: nada de lo cambiado
altera lo que corre de noche.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados y resultado | **4.385 passed / 171 skipped / 0 failed** (`bash harness/init.sh`, exit 0, `ENTORNO LISTO`). Eran 4.367: los **18 nuevos** son 11 + 7 |
| Cobertura de las líneas cambiadas | **93,6 % (791/845)**, umbral 80 %, nivel `estandar`. Misma cifra que antes de empezar: F-081 no añade ni una línea de producción ejecutable |
| Mutantes generados y supervivientes | **0 generados** por el diff de F-081 (`--base 87f4d84`: alcance vacío, la herramienta se niega a escribir informe). Campaña acotada de T4: **2 mutantes, 4 ejecuciones, 0 supervivientes** |
| Tiempo de ejecución de la suite | **1.191,96 s** (19:51) |
| Los tests nuevos no tocan red ni BBDD | `grep -n "psycopg\|httpx\|requests\|connect(\|build_postgres_client\|SigridApiClient\|filas_solo_lectura" tests/test_f081_*.py` → **vacío** |

Seis commits `F-081 Tn:`; los epígrafes de arriba van en orden de trabajo, no de
commit: T1 = medición + barrido + fase RED, T2 y T3 = la corrección, T4 = los
supervivientes, T5 = la versión 20, T6 = el papeleo.
