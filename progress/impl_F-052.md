<!-- progress/impl_F-052.md -->
# F-052 · Implementación (FASE 1: todo lo que no necesita la base)

Rama `feature/F-052-partidas-huerfanas`. Spec aprobada con las **siete decisiones
cerradas**; línea base medida en `progress/explore_F-052.md`.

**Hechas:** T1-T12, T16-T19, T22-T30 (T20 ya venía hecha: F-053 fichada; T21
**exenta** por el humano el 2026-08-31).
**Sin hacer, a propósito:** T13, T14, T15 y los diez pasos de cierre. Son
escrituras contra el Postgres compartido **en producción** o lecturas de varios
GB, y **desde el puesto no hay conexión directa** (`connection timeout expired`
contra `psql-albaranes-rs9k2`). Nada de lo entregado se ha ejecutado contra la
base: **la 0599 sigue publicando hoy las cifras de siempre.**

## 1 · Qué cambió

**El arreglo (bloque B).** `sql/stg/04_partidas.sql`: la rama recursiva deja de
exigir `h.cod <> ''` y el filtro baja al `INSERT` (`WHERE publicable`), así que el
código vacío decide **qué se publica, no por dónde se desciende**. El capítulo en
blanco se atraviesa y se **colapsa**: `padre_publicado_id` resuelve el ancestro
publicado más cercano y `ruta_capitulos` / `nivel` sólo avanzan en nodos
publicables, con lo que se sostiene `cardinality(split(ruta)) = nivel + 1`, de lo
que vive `mart.v_pbi_dim_partida_niveles`. Corta-ciclos con `visitados BIGINT[]`
**y** `nivel_bruto < 40` (DA-3). La raíz **no se toca** (DA-1). Reescrita la
cabecera, que documentaba como intencionado el filtro que amputaba 1.323 partidas.

**La misma regla, ejecutable (bloque A).** `etl_sigrid/domain/arbol_partidas.py`
implementa R1-R5 **sin base de datos**, con las fixtures medidas del informe: es
lo que permitió probar el corta-ciclos antes de desplegarlo sobre 3 h 45.

**El guardián (bloque C).** `check-cobertura` contrasta lo que entra en `stg` con
lo que sale en `mart` por (obra × ámbito): **obra invisible** (filas en `stg`,
cero en el fact) y **filas huérfanas** (sin ficha de partida o de obra). Los
descartes correctos de hoy se declaran en `config/cobertura_excepciones.yaml`,
que es un **trinquete y sólo baja**. Lanzado a mano sale con código 1; dentro de
`run-all` registra y **la nocturna termina en verde** (DA-4).

**Que se haga oír (bloque C bis).** El marcador `[F052-COBERTURA-KO]` y
`infra/96_create_alert_cobertura.ps1`, la regla que lo busca en los logs del job
y notifica al grupo de acción existente. **Ninguna dirección de correo en el
repositorio** (R30). Despliegue **manual**.

**El diccionario (bloque E).** La ficha de `stg.partidas` dejaba de ser cierta;
`mart` y `cierre` avisan con fecha de que las cifras de la 0599 cambian; el
diccionario sube a **versión 12** y `pendientes` sigue vacía. `ARCHITECTURE.md`
recoge la semántica del capítulo sin código y la de los ciclos.

**La revisión de datos ampliada (bloque F bis), que es lo que sustituye a la
mutación.** Huella 2 baja a **categoría** (una partida recategorizada CI→CD no
mueve el total de la obra pero sí el desglose que Power BI dibuja); huella 3
nueva, de **dimensión**, que resume por obra el sitio de cada partida en el árbol
(`md5` sobre las seis columnas, ordenado por `partida_id`) y caza una partida que
**se mueva sin cambiar de importe**; huella 4 nueva, de **cierre**, la capa que
Negocio ve. `comparar-huellas` las reconoce **por su cabecera** y aplica
**tolerancia CERO** fuera de las obras esperadas.

## 2 · Ficheros

| Se crean | Qué es |
|---|---|
| `etl_sigrid/domain/arbol_partidas.py` | la regla del árbol, dominio puro |
| `etl_sigrid/domain/cobertura.py` | el veredicto del guardián y el marcador |
| `etl_sigrid/domain/huella_ampliada.py` | huellas 3 y 4: formato, comparación, veredicto |
| `etl_sigrid/infrastructure/cobertura_excepciones.py` | lector del YAML de excepciones |
| `etl_sigrid/infrastructure/postgres/cobertura_sql.py` | las dos consultas, sólo texto |
| `etl_sigrid/infrastructure/postgres/huella_ampliada.py` | las dos consultas nuevas + CSV |
| `config/cobertura_excepciones.yaml` | 10 excepciones declaradas (trinquete) |
| `infra/96_create_alert_cobertura.ps1` | la regla de alerta (despliegue manual) |
| 6 ficheros `tests/test_f052_*.py` | 122 tests |

| Se modifican | Qué cambia |
|---|---|
| `…/sql/stg/04_partidas.sql` | **el arreglo** + cabecera reescrita |
| `main.py` | `check-cobertura`, su enganche en `run-all`, `--desde dimension\|cierre`, `comparar-huellas` con formatos |
| `etl_sigrid/domain/huella.py` | `categoria` en `FilaHuella` y en su clave |
| `…/postgres/huella_obras.py` | `sql_huella_mart` agrupa por categoría; CSV de 9 columnas |
| `config/diccionario/stg.yaml`, `mart.yaml`, `cierre.yaml`, `00_global.yaml` | R20, R21, R22 |
| `infra/env/dev.json`, `infra/00_vars.ps1`, `infra/README.md` | la regla de alerta nueva |
| `tests/test_f042_huella.py` | la cabecera pasa de 8 a 9 columnas |

**No se ha tocado** `mart/02_build_fact.sql` (sus `INNER JOIN` son correctos),
`05b_view_dim_partida_niveles.sql`, `stg/03_obras.sql` (es F-053),
`08_plan_mensual.sql`, `cierre/02_build_fact.sql` ni `build_stg_step.py`.

## 3 · Decisiones de diseño y desviaciones

1. **`Arbol` tiene una CUARTA lista, `inalcanzables`**, que el diseño no pedía.
   Un nodo con padre inexistente no cabía en ninguna de las tres declaradas y
   habría vuelto a perderse en silencio, que es el modo de fallo que la feature
   existe para eliminar. Hoy mide **0 casos** (causas (a) y (c) del informe), y
   ese cero es un dato. Un test fija que **todo** nodo cae en una de las cuatro.
2. **`FilaCobertura` lleva `nombre_obra`** además de los seis campos del diseño.
   Las 19 obras sin ficha en `stg.obras` no tienen allí código ni nombre: sin
   bajar a `raw.con` a por ellos, la denuncia diría «obra 2824201». Y es el
   nombre lo que permite declararlas por patrón.
3. **Las excepciones se identifican por `codigo_obra` O por `patron_nombre`**:
   el informe nombra las administrativas como `OBRA PRUEBA` / `POSTVENTA`, que
   son nombres, y esas obras están fuera de `stg.obras` a propósito.
4. **No se declara tope de filas por excepción.** Habría que medirlo contra la
   base y no hay conexión; un tope inventado de más tapa y de menos da alarma
   falsa. **T15 (manual) fija la línea base y ahí se afina.**
5. **Las huellas 3 y 4 comparten mecanismo** (`FormatoHuella`) en vez de ser dos
   módulos calcados, y se comparan **como texto**: se escriben y se leen con el
   mismo código, así que la igualdad es exacta y no introduce redondeos que el
   build no tiene.
6. **`categoria` va la ÚLTIMA columna del CSV de F-042**, para no mover las ocho
   que ya había: esos CSV se abren en Excel y se comparan a mano.

## 4 · Fase RED (rigor `critico`) — trazas reales

Cinco tareas escribieron el test **antes** que el código; salida real pegada.

**T1 · `pytest tests/test_f052_arbol.py`**
```
tests\test_f052_arbol.py:31: in <module>
    from etl_sigrid.domain.arbol_partidas import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.arbol_partidas'
=========================== short test summary info ===========================
ERROR tests/test_f052_arbol.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.16s
```

**T4 · `pytest tests/test_f052_sql.py`** (el fichero SQL existía; lo que no
existía era el arreglo)
```
FAILED tests/test_f052_sql.py::test_f052_r1_la_rama_recursiva_ya_no_exige_codigo_no_vacio
FAILED tests/test_f052_sql.py::test_f052_r3_el_cte_propaga_las_tres_columnas_nuevas[publicable]
FAILED tests/test_f052_sql.py::test_f052_r3_el_padre_publicado_salta_el_nodo_colapsado
FAILED tests/test_f052_sql.py::test_f052_r2_el_insert_solo_publica_lo_publicable
FAILED tests/test_f052_sql.py::test_f052_r4_la_ruta_no_avanza_en_un_nodo_sin_codigo
FAILED tests/test_f052_sql.py::test_f052_r5_la_recursiva_no_vuelve_a_pisar_un_nodo_ya_visitado
FAILED tests/test_f052_sql.py::test_f052_r5_hay_tope_de_profundidad_y_es_el_del_dominio
13 failed, 3 passed in 0.65s
```
(seis de las trece; la lista entera, en el commit `0de4875`)

**T7 · `pytest tests/test_f052_cobertura.py`**
```
tests\test_f052_cobertura.py:32: in <module>
    from etl_sigrid.domain.cobertura import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.cobertura'
1 error in 0.93s
```

**T24 · `pytest tests/test_f052_marcador.py`**
```
E       FileNotFoundError: [Errno 2] No such file or directory:
        '...\infra\96_create_alert_cobertura.ps1'
FAILED tests/test_f052_marcador.py::test_f052_r28_el_marcador_del_ps1_es_el_MISMO_que_emite_el_codigo
FAILED tests/test_f052_marcador.py::test_f052_r28_el_marcador_llega_a_la_consulta_que_se_envia_de_verdad
FAILED tests/test_f052_marcador.py::test_f052_r29_el_script_lee_todo_de_cfg_y_no_cablea_ningun_nombre
FAILED tests/test_f052_marcador.py::test_f052_r29_dev_json_declara_el_nombre_y_la_ventana
15 failed, 2 passed in 1.57s
```
(lista recortada a cuatro de las quince por el tope de 220 líneas; la traza
entera está en el commit `48d992e`)

**T28 · `pytest tests/test_f052_huella_dimension.py`**
```
tests\test_f052_huella_dimension.py:29: in <module>
    from etl_sigrid.domain.huella_ampliada import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.huella_ampliada'
1 error in 0.19s
```

**T30 · `pytest tests/test_f052_comparar_huellas.py`** → `9 failed, 3 passed`
(`--desde dimension` y `--desde cierre` no existían; commit `344f2b2`).

**Sin fase RED propia, y queda dicho: T29.** El mecanismo que prueba
`test_f052_huella_cierre.py` es el **mismo** de la huella 3 y entró con ella tras
su RED; lo específico de aquí (el formato `cierre` y su consulta) viajó en el
módulo compartido. También está escrito en la cabecera de ese fichero.

## 5 · Lo que queda, y quién lo hace

**T13, T14, T15 y los diez pasos de cierre son del humano.** En particular:

1. **El aviso a Negocio (R27, DA-6) es BLOQUEANTE**: sin él no se publica.
2. **T14 antes de reconstruir**: las **cuatro** huellas del ANTES. El build pisa
   `stg.plan_mensual` y no hay vuelta atrás.
3. **T13**: medir el coste de `check-cobertura` contra la base antes de darlo por
   bueno en la nocturna. Las dos consultas barren `stg.plan_mensual` entera.
4. **R11 con las cuatro huellas** y `--obras-esperadas 0599,0613,0618,0630,0565,0686`.
   Cualquier diferencia fuera de esas seis **detiene la feature**.
5. **Desplegar `infra/96_create_alert_cobertura.ps1` y añadir el buzón al grupo
   de acción.** Sin ese paso **el guardián es mudo**, porque al no bloquear el
   job la alerta de fallo no se dispara. Probar de punta a punta.
6. `check-unicidad --timeout 300`, `check-cierres`, `check-diccionario`,
   `publicar-diccionario`, y el aviso a quien administra Sigrid (prioridad 0686).

**Riesgos vivos.** (a) El corta-ciclos está probado en dominio y sobre el texto
del SQL, **no ejecutado contra Postgres**: la sintaxis del `WITH RECURSIVE` con
`visitados` no se ha validado contra el motor. (b) La alerta sólo está probada
como texto y ejecutando su función de composición: **no hay correo recibido**.
(c) Los conteos de R7-R10 siguen siendo la simulación del líder.

## 6 · Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **2.977 passed, 130 skipped**, 0 failed (`bash harness/init.sh`) |
| De ellos, nuevos de F-052 | **122** en 6 ficheros, más 1 añadido a `test_f042_huella.py` |
| **Cobertura de las líneas cambiadas** | **100,0 % de 504** (504/504, umbral 80 %, nivel `critico`) — línea `PUERTA COBERTURA` de `init.sh` |
| **Tiempo de la suite** | **297,42 s** (4 min 57 s), el que imprime pytest dentro de `init.sh` |
| **Mutantes generados / supervivientes** | **N/A — EXENTA.** Decisión del humano del 2026-08-31, registrada en `tasks.md` (T21) y en la ficha de `harness/features.json`. En su lugar, T27-T30 |
| **Tamaño del papeleo** | `python -m harness.tamano --feature F-052`: dentro de los topes |
| **`bash harness/init.sh`** | **verde**, `ENTORNO LISTO. Puedes trabajar.` |

**El matiz que el reviewer debe tener presente al declarar T21 N/A:** la campaña
cubría los módulos **Python**; el bloque B es **SQL** y nunca estuvo cubierto por
ella, así que la exención rebaja la red del dominio, no la del SQL. Lo que la
sustituye —la revisión de datos ampliada— **sólo mide de verdad cuando el humano
ejecute T14 y los pasos de cierre**: hoy el mecanismo está entregado y probado, y
las huellas están sin capturar.

Los doce huecos de cobertura que quedaban tras T30 se cerraron a propósito
(commit `1a4e0be`): eran las ramas defensivas, justo lo que una campaña de
mutación habría atacado primero. Entre ellas faltaba el caso que más importa: un
**ciclo alcanzable desde una raíz**, el que de verdad colgaría la nocturna.
