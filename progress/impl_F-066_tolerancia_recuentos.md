<!-- progress/impl_F-066_tolerancia_recuentos.md -->
# F-066 · `check-raw-recuentos`: tolerancia con dirección

**2026-09-08 · rama `feature/F-066-ingesta-raw-pendientes` · rigor `critico`**
Commits `da965c8` (T1), `29f7c62` (T2), `4a3cd2c` (T3).

## 1 · Qué estaba mal

El comando comparaba el `COUNT(*)` de cada tabla en Sigrid con el de `raw` y
salía con **código 1 a la primera diferencia**. Ese criterio es inalcanzable
por diseño: Sigrid es un ERP que se sigue usando mientras el datamart es una
foto de un instante. La primera comparación real —ingesta de las 11:16-11:57
UTC, verificación unas cinco horas después— dio:

```
31 iguales · 25 distintas · 0 ausentes · 0 sin medir      -> código 1
```

y las 25 eran trabajo en el origen, no un fallo. La **firma** lo demuestra:
25 de 25 con Sigrid por encima de `raw` y **ninguna** al revés; 4.883 filas
sobre 25.287.500 (0,0193 %); peor tabla `obrparpre`, +3.969 sobre 13.884.933
(0,0286 %). Un guardián que se pone rojo todas las noches se deja de mirar.

## 2 · La regla nueva

| Caso | Antes | Ahora |
|---|---|---|
| Sigrid = `raw` | `OK` | `OK` |
| Sigrid **>** `raw`, dentro del umbral | `DISTINTA` → código 1 | `DERIVA`, conforme |
| Sigrid **>** `raw`, fuera del umbral | `DISTINTA` → código 1 | `FALTAN EN RAW` → 1 |
| Sigrid **<** `raw`, de una fila | `DISTINTA` → código 1 | `SOBRAN EN RAW` → 1 |
| tabla que no está en `raw` | `AUSENTE EN RAW` → 1 | igual |
| Sigrid no contestó | `SIN MEDIR` → 1 | igual |

El `DISTINTA` de antes se parte en tres, porque eran tres cosas distintas
metidas en el mismo montón.

## 3 · Las decisiones que había que tomar, y por qué

**(a) Umbral relativo POR TABLA, ni global ni absoluto.** Un umbral absoluto
trata igual 50 filas en `obrparpre` (13,9 M: ruido) que en un catálogo de 200
(un cuarto de la tabla). Un umbral **global** —sobre la suma de las 56— queda
dominado por `obrparpre`, que ella sola es el 55 % de las filas: perder un
catálogo entero no movería la cifra global ni un 0,001 %, así que sería un
umbral que solo vigila la tabla grande. **No he añadido un umbral global**
además del de tabla: no aporta ninguna señal que el de tabla no lleve ya, y
sí una segunda perilla que calibrar. Consecuencia buscada y deliberada: en una
tabla pequeña el 0,05 % no llega ni a una fila, o sea que se le sigue
exigiendo exactitud, que es lo correcto para un catálogo.

**(b) El valor por defecto: 0,05 %.** No es un número redondo elegido a ojo;
es lo único que cabe entre las dos cotas que lo aprietan:

* **Por abajo**, el peor día medido: `obrparpre` con 0,0286 % tras cinco horas
  de uso. Por debajo de eso el comando se pone rojo una mañana normal.
* **Por arriba**, una **página perdida** de la ingesta: 10.000 filas
  (`page_size` de sigrid-api), que en la tabla más grande del YAML son
  0,072 %. Por encima de eso el comando deja de ver justo aquello para lo que
  se escribió —una ingesta que se cortó a media tabla—.

0,05 % es 1,7 veces el peor día medido y queda por debajo de una página
perdida en **todas** las tablas declaradas (`obrparpre` es la única por encima
de 10 M filas; en las demás una página es un porcentaje mucho mayor). Los dos
bordes están fijados por un test —`..._cae_en_la_unica_ventana_util`— para que
nadie mueva la constante sin enterarse de qué rompe.

Es **configurable** con `--tolerancia-pct`, siguiendo el patrón del proyecto
(`--umbral-horas` de `check-frescura`): constante de módulo + opción de click
con `show_default`. Con `--tolerancia-pct 0` se recupera exactamente la regla
anterior, y hay un test que lo comprueba sobre el caso real.

**(c) Qué enseña la salida.** Cada línea lleva ahora su **desviación
relativa** y uno de los seis veredictos. Debajo de la tabla, y solo si los
hay, van **dos bloques separados**: primero el grave —`SIGRID TIENE MENOS
FILAS QUE raw`, con qué mirar— y después el de las que se pasan del umbral. El
resumen cuenta las seis categorías, dice el **umbral aplicado** (sin él un
verde no se puede interpretar), la **peor desviación** con su tabla, y termina
en `VEREDICTO: CONFORME` / `NO CONFORME`.

**(d) El tiempo desde la última ingesta: sí, y sale.** La deriva esperable es
proporcional a él, así que un 0,03 % cinco horas después de la ingesta es
normal y cinco minutos después no lo es; sin ese dato la cifra no se puede
juzgar. Es barato: `_meta.v_frescura` ya la lee `check-frescura`, y se usa su
columna `horas_desde_ultimo_ok` tal cual, sin recalcular nada. Es **contexto y
no criterio**: la excepción se traga entera y, si la vista no se puede leer, la
línea dice «hace un tiempo desconocido» y el veredicto no cambia. Lo que **no**
he hecho es convertir el tiempo en un multiplicador de la tolerancia: con una
sola medición de una sola tabla no hay con qué calibrar una tasa por hora, y
un umbral que se mueve solo es un umbral que nadie sabe explicar.

## 4 · Ficheros tocados

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/recuentos.py` | seis estados, `tolerancia_pct`, `diferencia`, `desviacion_pct`, `peor`, informe con `toleradas`/`faltantes`/`sobrantes`, formato nuevo |
| `main.py` | opción `--tolerancia-pct`, `_horas_desde_ultima_ingesta`, docstring del comando |
| `tests/test_f066_tolerancia_recuentos.py` | **nuevo**, 37 tests de la regla |
| `tests/test_f066_recuentos.py` | adaptado al contrato nuevo (7 tests) |
| `specs/.../requirements.md` | R15, R16 y R17 reformulados |
| `specs/.../design.md` | contrato de `InformeRecuentos` y el porqué del 0,05 % |
| `harness/features.json` + `BACKLOG.md` | criterio de aceptación nuevo |
| `docs/ARCHITECTURE.md` | párrafo del comando |
| `progress/current.md` | por dónde se sigue |

## 5 · Fase RED (obligatoria, rigor crítico)

**RED 1 · la regla no existía.** Tests escritos antes que el código:

```
$ python -m pytest tests/test_f066_tolerancia_recuentos.py -x -q
tests\test_f066_tolerancia_recuentos.py:37: in <module>
    from etl_sigrid.domain.recuentos import (
E   ImportError: cannot import name 'ESTADO_DERIVA' from
    'etl_sigrid.domain.recuentos'
1 error in 3.05s
```

**RED 2 · el dominio ya implementado, el comando todavía no.** Los tests que
hablan del CLI siguen en rojo, con fallo real y no de importación:

```
$ python -m pytest tests/test_f066_tolerancia_recuentos.py -q
E       assert 2 == 1
E        +  where 2 = <Result SystemExit(2)>.exit_code
E       AssertionError: assert '4,6 h' in '=== raw frente a Sigrid, ...
FAILED ...::test_f066_r15_la_tolerancia_se_puede_apretar_desde_la_linea_de_ordenes
FAILED ...::test_f066_r15_el_comando_cuenta_las_horas_desde_la_ultima_ingesta
2 failed, 33 passed in 1.24s
```

(El `SystemExit(2)` es click rechazando una opción que aún no existía.)

**RED 3 · el contrato viejo, al descubierto.** Al quitar `ESTADO_DISTINTA` la
suite antigua deja de compilar, que es la prueba de que el criterio viejo
estaba realmente afirmado en tests y no solo en el código:

```
tests\test_f066_recuentos.py:29: in <module>
E   ImportError: cannot import name 'ESTADO_DISTINTA' from
    'etl_sigrid.domain.recuentos'
```

**VERDE** tras implementar: `67 passed` en los dos ficheros.

Los dos casos que pidió el humano están escritos y verdes:
`test_f066_r15_el_dia_real_con_25_tablas_derivadas_sale_conforme` (las 25
tablas reales, 0,0193 %, código 0) y
`test_f066_r15_una_sola_tabla_con_menos_filas_en_sigrid_lo_tumba_todo` (mismo
día, una fila de menos en `apu` sobre 2,15 M, código 1). Un tercero,
`..._el_caso_real_..._tiene_las_cifras_que_se_midieron`, fija que el fixture
son de verdad las cifras medidas (56 tablas, 25 desviadas, 4.883 sobre
25.287.500) y no unos números cualesquiera.

## 6 · Lo que NO se ha hecho

* **No se ha ejecutado el comando contra Azure.** Sigue siendo verificación
  **MANUAL (humano)**, como R24. Todo lo de aquí son dobles: ni red ni BBDD.
* No se ha tocado la ingesta, ni el YAML de tablas, ni el diccionario: el
  comando no publica ningún objeto.
* No se ha añadido umbral global ni tolerancia proporcional al tiempo, con el
  argumento de §3(a) y §3(d).
* **Aviso de higiene**: el commit T1 arrastró los tres ficheros de
  `specs/F-070-auditoria-calidad-diccionario/` que estaban ya en el índice, y
  el T2 los cambios sin commitear de `harness/features.json` y `BACKLOG.md`
  (repriorización del backlog de la sesión anterior). No se ha perdido nada,
  pero no son míos y conviene saberlo al mirar el diff.

## 7 · Evidencias

| Evidencia | Medida |
|---|---|
| Tests ejecutados (suite completa) | **3.959 pasados, 159 saltados, 0 fallos** |
| Tiempo de la suite completa | **433,20 s** (7 min 13 s), sin carga |
| Tests de esta corrección | **67** (`test_f066_recuentos.py` 30 + `test_f066_tolerancia_recuentos.py` 37) |
| Cobertura de líneas cambiadas | **100 % (65/65)**, umbral 80 %, nivel crítico |
| Mutantes generados | PENDIENTE |
| Supervivientes | PENDIENTE |
| `bash harness/init.sh` | PENDIENTE |

La cobertura se midió con `python -m harness.cobertura --base <commit previo>`
sobre una pasada de coverage con **solo los dos ficheros de test de F-066**:
las 65 líneas de producción que introduce este cambio están cubiertas por sus
propios tests, no de rebote por la suite entera.
