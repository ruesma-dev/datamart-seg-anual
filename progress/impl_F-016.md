<!-- progress/impl_F-016.md -->
# F-016 · Refuerzo de tests para los huecos de riesgo alto de F-005 — Informe del implementer

**Rama:** `feature/F-016-refuerzo-tests-f005` · **Rigor:** `estandar` ·
**sdd:** false (los criterios son los `acceptance` de `harness/features.json`)
· **Fecha:** 2026-08-10 · **Commits:** 3, uno por frente.

**Resultado en una línea:** los **seis** mutantes de riesgo ALTO de F-005 pasan
de supervivientes a **muertos**, verificado relanzando la campaña completa;
**sin tocar una sola línea de código de producción**.

---

## 1. Qué resuelve esta feature

La línea base de mutación de F-005 (`progress/mutacion_F-005.md`, generada por
F-015) dejó **101 mutantes y 55 supervivientes (45,5 %)**, de los que **6 eran
de riesgo ALTO**. F-005 está declarada `critico` y no pasaba su propio nivel.
Esta feature cierra **solo esos 6**: lo que faltaba no era código, eran tests.

| # | Ubicación en la línea base (árbol de `c7500d4`) | Qué quedaba sin fijar |
|---|---|---|
| 1 | `config/settings.py:103` | valor por defecto de `auto_create_db` en la configuración |
| 2 | `postgres_client.py:78` | valor por defecto de `auto_create_db` en el cliente |
| 3 | `postgres_client.py:201` | la conexión administrativa se abre en autocommit |
| 4 | `fingerprint.py:334` | igualdad de valores de **texto** al comparar huellas |
| 5 | `fingerprint.py:405` | clasificación de una diferencia como **FALLO** |
| 6 | `main.py:388` | detección de un paso **fallido** del pipeline |

---

## 2. Ficheros tocados

| Fichero | Qué | Producción |
|---|---|---|
| `tests/test_f016_huecos_alto_f005.py` | **nuevo**, 8 tests: uno o dos por hueco ALTO | no |
| `tests/test_f005_grants.py` | barrido de secretos afinado + control negativo | no |
| `progress/mutacion_F-005_tras_refuerzo.md` | **nuevo**, campaña relanzada y 47 supervivientes analizados | no |
| `progress/mutacion_F-016.md` | **nuevo**, campaña propia (alcance 0) con su justificación escrita | no |
| `progress/impl_F-016.md`, `progress/current.md` | este informe y la memoria de sesión | no |

**Ni un fichero de producción.** Lo confirma el propio portero, que calcula el
alcance desde el diff contra `dev` y no desde lo que yo diga:

```
[OK] PUERTA COBERTURA: N/A (F-016 no cambia líneas Python de producción frente a dev)
```

La única excepción autorizada respecto a «no tocar tests de otras features» es
`tests/test_f005_grants.py`, y la autoriza el propio `acceptance` de F-016
(«Afinado el barrido de secretos de `test_f005_r21`…»). **Ningún otro test de
F-005 se ha tocado**, cosa que importa: los tests de F-005 son el objeto de la
medición y retocarlos falsearía la comparación con la línea base.

---

## 3. Decisiones de diseño

**D1 · El defecto de configuración se afirma sobre el campo, no sobre una
instancia.** `PostgresSettings` lee `.env`, y hoy `.env` apunta a producción
(con `PG_AUTO_CREATE_DB=false`, que es lo correcto contra el servidor
compartido). Un test que instanciara la clase sin más estaría midiendo el
`.env` del puesto, no el defecto del código, y saldría rojo o verde según quién
lo ejecute. Se afirma
`PostgresSettings.model_fields["auto_create_db"].default is True` y, además,
`PostgresSettings(_env_file=None)` con la variable de entorno retirada. Dos
afirmaciones del mismo hecho por dos caminos que no comparten fuente.

**D2 · El cliente Postgres se prueba por comportamiento, no por atributo
privado.** Comprobar `cliente._auto_create_db is True` habría matado el mutante
igual, pero no dice nada: lo que importa es qué **rama** toma el arranque. Los
tests sustituyen las tres ramas de `_auto_bootstrap` por testigos y afirman la
secuencia (`["crear", "schemas"]` frente a `["comprobar", "schemas"]`). Así el
test sigue valiendo si mañana el interruptor se lee de otro sitio.

**D3 · Los tests de `fingerprint` afirman el MOTIVO, no solo la gravedad.**
F-005 ya comprobaba que una diferencia salía como FALLO o como AVISO. Lo que no
comprobaba nadie es que el texto que la acompaña sea el suyo. No es cosmética:
un FALLO explicado como «diferencia en el periodo vivo, esperable» es
exactamente la frase con la que un humano archiva un problema real. Afirmar el
motivo es lo que mata el mutante de `fingerprint.py:405`, y de propina el de
`fingerprint.py:400`.

**D4 · El test del CLI afirma el código de salida exacto, no «distinto de
cero».** `apply-grants` sale con 1 ante un paso fallido; el test dice `== 1`.
Por eso muere también `main.py:389` (`sys.exit(1)` → `sys.exit(2)`), que la
línea base tenía como superviviente de riesgo MEDIO.

**D5 · El barrido de secretos se parte en dos criterios.** Los tres patrones
con **contexto de asignación** (la variable de entorno con un valor detrás, la
clave dentro de una cadena de conexión, y la forma literal de SQL) no dan
falsos positivos y no se tocan. El que se equivocaba es
el de clave generada, que no tiene contexto: `/` está en el alfabeto base64 y
también en cualquier ruta del árbol. El criterio nuevo descarta un candidato
solo si **parece una ruta**: dos barras o más **y** ni una mayúscula. Una clave
de 24 caracteres o más sin una sola mayúscula es un suceso de probabilidad
despreciable; una ruta del repositorio, la norma. El barrido pasa a ser la
función `buscar_secretos()` para poder someterlo a su propio test.

**D6 · La campaña se relanza sobre un worktree del merge, no sobre el árbol de
hoy.** Ver §5: es lo que hace comparables los dos informes.

---

## 4. Fase RED

En esta feature **el producto son los tests**, así que la fase RED se invierte:
no hay que demostrar que un test fallaba antes de existir el código, sino que
cada test nuevo **mata de verdad su mutante**. Se ha hecho aplicando cada una
de las seis mutaciones **al árbol de hoy** (línea a línea, restaurando siempre
el fichero) y ejecutando la suite nueva. Traza real, no resumen.

> **Nota sobre los números de línea.** Aquí las mutaciones se aplican sobre el
> árbol actual, donde `postgres_client.py` ha crecido desde el merge: el mismo
> mutante que la línea base sitúa en `:78` está hoy en `:133`, y el de `:201`
> en `:256`. `settings.py:103`, `fingerprint.py:334`/`:405` y `main.py:388` no
> se han movido. La comparación en las líneas ORIGINALES está en §5.

Comando común a los seis:

```
$ python -m pytest tests/test_f016_huecos_alto_f005.py -q --tb=short
```

### H1 · `config/settings.py:103` `True,` → `False,`

```
F.......                                                                 [100%]
================================== FAILURES ===================================
____ test_f016_h1_el_defecto_de_auto_create_db_en_la_configuracion_es_true ____
tests\test_f016_huecos_alto_f005.py:140: in test_f016_h1_el_defecto_de_auto_create_db_en_la_configuracion_es_true
    assert campo.default is True, (
E   AssertionError: el defecto declarado de auto_create_db ha cambiado; si es a propósito, hay que revisar el runbook de Azure y este test
E   assert False is True
E    +  where False = FieldInfo(annotation=bool, required=False, default=False, description='Si es False, el ETL nunca ejecuta CREATE DATABA...re conexión contra la BBDD admin. Obligatorio contra el servidor compartido de Azure, donde viven albaranes y partes.').default
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h1_el_defecto_de_auto_create_db_en_la_configuracion_es_true
1 failed, 7 passed in 0.84s
-> exit=1  VEREDICTO: MUERTO
```

### H2 · `postgres_client.py:133` `auto_create_db: bool = True,` → `False,`

```
.F......                                                                 [100%]
================================== FAILURES ===================================
____ test_f016_h2_el_defecto_de_auto_create_db_en_el_cliente_crea_la_base _____
tests\test_f016_huecos_alto_f005.py:170: in test_f016_h2_el_defecto_de_auto_create_db_en_el_cliente_crea_la_base
    assert llamadas == ["crear", "schemas"], (
E   AssertionError: por defecto el cliente asegura la base creándola; no se limita a comprobar que existe
E   assert ['comprobar', 'schemas'] == ['crear', 'schemas']
E
E     At index 0 diff: 'comprobar' != 'crear'
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h2_el_defecto_de_auto_create_db_en_el_cliente_crea_la_base
1 failed, 7 passed in 0.82s
-> exit=1  VEREDICTO: MUERTO
```

### H3 · `postgres_client.py:256` `autocommit=True` → `autocommit=False`

```
...F....                                                                 [100%]
================================== FAILURES ===================================
________ test_f016_h3_la_conexion_administrativa_se_abre_en_autocommit ________
tests\test_f016_huecos_alto_f005.py:219: in test_f016_h3_la_conexion_administrativa_se_abre_en_autocommit
    assert aperturas == [("dbname=admin_de_mentira", True)], (
E   AssertionError: la conexión administrativa se abre contra la BBDD admin y en autocommit; sin autocommit CREATE DATABASE falla
E   assert [('dbname=adm...tira', False)] == [('dbname=adm...ntira', True)]
E
E     At index 0 diff: ('dbname=admin_de_mentira', False) != ('dbname=admin_de_mentira', True)
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h3_la_conexion_administrativa_se_abre_en_autocommit
1 failed, 7 passed in 0.81s
-> exit=1  VEREDICTO: MUERTO
```

### H4 · `fingerprint.py:334` `return valor_a == valor_b` → `!=`

```
....F...                                                                 [100%]
================================== FAILURES ===================================
____ test_f016_h4_la_comparacion_de_textos_distingue_iguales_de_distintos _____
tests\test_f016_huecos_alto_f005.py:244: in test_f016_h4_la_comparacion_de_textos_distingue_iguales_de_distintos
    assert iguales == [], "dos valores de texto idénticos no son una diferencia"
E   AssertionError: dos valores de texto idénticos no son una diferencia
E   assert [Diferencia(e...alle='texto')] == []
E
E     Left contains one more item: Diferencia(esquema='mart', vista='v_fact', bloque='cerrado', metrica='sum_importe', valor_a='n/d', valor_b='n/d', gravedad='FALLO', detalle='texto')
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h4_la_comparacion_de_textos_distingue_iguales_de_distintos
1 failed, 7 passed in 0.89s
-> exit=1  VEREDICTO: MUERTO
```

### H5 · `fingerprint.py:405` `if gravedad == FALLO` → `!=`

```
.....F..                                                                 [100%]
================================== FAILURES ===================================
_____ test_f016_h5_el_detalle_de_la_diferencia_corresponde_a_su_gravedad ______
tests\test_f016_huecos_alto_f005.py:274: in test_f016_h5_el_detalle_de_la_diferencia_corresponde_a_su_gravedad
    assert "igualdad exacta" in fallo[0].detalle
E   AssertionError: assert 'igualdad exacta' in 'diferencia en el periodo vivo, esperable'
E    +  where 'diferencia en el periodo vivo, esperable' = Diferencia(esquema='mart', vista='v_fact', bloque='cerrado', metrica='count', valor_a='1000', valor_b='1001', gravedad='FALLO', detalle='diferencia en el periodo vivo, esperable').detalle
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h5_el_detalle_de_la_diferencia_corresponde_a_su_gravedad
1 failed, 7 passed in 0.83s
-> exit=1  VEREDICTO: MUERTO
```

Esta traza es, además, la mejor ilustración de por qué el hueco era de riesgo
ALTO: la huella detecta la diferencia, pero la explica como «esperable».

### H6 · `main.py:388` `if result.status == StepStatus.FAILED:` → `!=`

```
......FF                                                                 [100%]
================================== FAILURES ===================================
_________ test_f016_h6_un_paso_fallido_hace_salir_al_cli_con_codigo_1 _________
tests\test_f016_huecos_alto_f005.py:326: in test_f016_h6_un_paso_fallido_hace_salir_al_cli_con_codigo_1
    assert resultado.exit_code == 1, resultado.output
E   AssertionError: [FAILED ] apply_grants              rows=        0 duration=   0.0s
E   assert 0 == 1
E    +  where 0 = <Result okay>.exit_code
________ test_f016_h6_un_paso_correcto_hace_salir_al_cli_con_codigo_0 _________
tests\test_f016_huecos_alto_f005.py:336: in test_f016_h6_un_paso_correcto_hace_salir_al_cli_con_codigo_0
    assert resultado.exit_code == 0, resultado.output
E   AssertionError: [SUCCESS] apply_grants              rows=        0 duration=   0.0s
E   assert 1 == 0
E    +  where 1 = <Result SystemExit(1)>.exit_code
=========================== short test summary info ===========================
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h6_un_paso_fallido_hace_salir_al_cli_con_codigo_1
FAILED tests/test_f016_huecos_alto_f005.py::test_f016_h6_un_paso_correcto_hace_salir_al_cli_con_codigo_0
2 failed, 6 passed in 0.92s
-> exit=1  VEREDICTO: MUERTO
```

**RESUMEN: 6/6 mutantes ALTO muertos.** El árbol quedó restaurado (`git status`
limpio) y la suite completa volvió a verde tras el barrido.

### Fase RED del segundo frente: el falso positivo del barrido

Primero, **la reproducción del defecto** con el patrón vigente hasta hoy:

```
$ python -c "import re; ..."
frase : El lector de Excel vive en etl_sigrid/infrastructure/excel/ y no toca disco.
patron: [A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])
casa  : 'sigrid/infrastructure/excel/'
```

Es exactamente lo que puso `init.sh` en rojo en F-004 al añadir una frase a
`docs/ARCHITECTURE.md`.

Y después, **la prueba de que el afinado no se ha pasado de frenada**: se
relajó el criterio a `candidato.count("/") >= 1` (descartar cualquier cosa con
una barra) y el control negativo se puso rojo:

```
$ python -m pytest tests/test_f005_grants.py::test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta -q --tb=short
# con _parece_ruta relajado a count("/") >= 1
F                                                                        [100%]
tests\test_f005_grants.py:431: in test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta
    assert buscar_secretos("token AbCd/EfGh/IjKl/MnOpQrStUv") != []
E   AssertionError: assert [] != []
E    +  where [] = buscar_secretos('token AbCd/EfGh/IjKl/MnOpQrStUv')
1 failed in 0.87s
```

El control fija las dos mitades: sigue cazando cuatro claves de mentira
(asignación, cadena de conexión, `PASSWORD '…'` de SQL y base64 suelto) y ya
no caza la ruta. Es el mismo método que usó el implementer de F-005 al
inyectar una contraseña falsa en `.env.example`, sin tocar ningún fichero del
repositorio.

---

## 5. La campaña de mutación relanzada

Informe completo: **`progress/mutacion_F-005_tras_refuerzo.md`**. La línea base
`progress/mutacion_F-005.md` **no se ha sobrescrito ni retocado** (verificado
con `git status`).

**Cómo se reconstruyó el alcance, y por qué así.** Un `git worktree` desprendido
en el merge de F-005 (`c7500d4`), NO el árbol vivo. Dos motivos:

1. **Comparabilidad.** Los números de línea del informe nuevo coinciden con los
   de la línea base. En el árbol de hoy no coincidirían (`postgres_client.py`
   ha crecido) y la comparación exigiría traducir líneas a mano, que es
   justamente donde se cuelan los errores.
2. **Seguridad.** `.env` apunta a producción; mutar ficheros del árbol vivo
   mientras eso es cierto es un riesgo evitable. La campaña solo ejecuta
   pytest, que no abre red ni BBDD, pero el fichero mutado sí queda en disco
   mientras dura cada mutante.

La única variable que cambia respecto a la línea base es **la suite**: se copió
`tests/test_f016_huecos_alto_f005.py` al worktree (65 tests → 73, ambas
tandas en verde antes de mutar nada).

**Línea de comando literal** —la que pedía la observación 1 de
`progress/review_F-015.md`, que la línea base no dejó escrita—:

```bash
git worktree add --detach C:/Users/pgris/PycharmProjects/wt-f016-c7500d4 c7500d4
cp tests/test_f016_huecos_alto_f005.py C:/Users/pgris/PycharmProjects/wt-f016-c7500d4/tests/
python -m harness.mutacion --feature F-005 --base c7500d4 --rama __no_existe__ \
    --raiz C:/Users/pgris/PycharmProjects/wt-f016-c7500d4 \
    --salida progress/mutacion_F-005_tras_refuerzo.md
```

`--rama __no_existe__` no es un adorno: sin él, `resolver_refs` encuentra la
rama `feature/F-005-postgres-azure`, que todavía existe, resuelve por rama en
vez de por merge y devuelve **alcance vacío** —el fallo que el reviewer de
F-015 documentó y nadie había escrito cómo evitar—. Antes de lanzar la campaña
se comprobó el alcance por separado: **20 ficheros, 1.669 líneas**, idéntico al
de la línea base.

### Resultado

| Métrica | Línea base (F-015) | Tras el refuerzo | Δ |
|---|---|---|---|
| Mutantes generados | 101 | 101 | = |
| Muertos | 46 | **54** | **+8** |
| Supervivientes | 55 | **47** | **−8** |
| Puntuación de mutación | 45,5 % | **53,5 %** | **+8,0 pp** |
| Supervivientes de riesgo **ALTO** | **6** | **0** | **−6** |
| Tiempo de la campaña | 129,1 s | 134,6 s | +5,5 s |

Los seis de riesgo ALTO **no aparecen** en la lista de supervivientes del
informe nuevo. Además caen dos de riesgo MEDIO que nadie había pedido:

- `main.py:389` `sys.exit(1)` → `sys.exit(2)`: el test afirma el código
  exacto, no «distinto de cero» (D4).
- `fingerprint.py:400` `or` → `and`: con `and`, un `count` deja de ir por la
  rama de igualdad exacta y cae en la comparación numérica con tolerancia; la
  diferencia se sigue reportando, pero el motivo pasa a ser
  `diferencia 1.000000 (margen 0.010000)`, y el test afirma el motivo (D3).

### Deuda que queda viva (contabilizada, no tapada)

Los 47 supervivientes están **todos** analizados uno a uno en el informe nuevo;
**ninguno queda en `PENDIENTE`**. El análisis es el de la línea base —es
literalmente el mismo mutante sobre el mismo código— más una línea de estado
en F-016.

| Veredicto | Nº | Qué se hace |
|---|---|---|
| Equivalente en la práctica | 8 | Nada: `frozen`/`slots` no exponen comportamiento observable |
| Hueco real, riesgo MEDIO | 24 | Deuda contabilizada, fuera del alcance acordado |
| Hueco real, riesgo BAJO | 15 | Deuda contabilizada, ídem |
| Hueco real, riesgo **ALTO** | **0** | — |

**Discrepancia de recuento que conviene no ignorar.** La tabla resumen de la
línea base dice «27 MEDIO / 14 BAJO», pero contando sus **veredictos uno a
uno** salen 26 y 15. Es un desliz de aquella tabla resumen, no de la medición
(los 55 supervivientes y sus 55 veredictos están bien). Aquí se cuentan los
veredictos, que es lo auditable. **La línea base no se retoca**: se deja
constancia y ya.

**Lectura honesta del número.** 53,5 % no es una nota de aprobado, y F-005
sigue sin pasar el nivel `critico` que tiene declarado. Lo que sí ha cambiado
es que ya no queda ningún hueco de los que hacen que **una carga mala se dé
por buena** o que **un interruptor de seguridad se caiga sin que nadie se
entere**. El resto es deuda visible, contada y priorizable.

### Campaña de mutación de la propia F-016

Ejecutada, no marcada N/A a mano:

```
$ python -m harness.mutacion --feature F-016
F-016: 0 fichero(s), 0 línea(s) de producción (origen rama, 1e6ea1e..feature/F-016-refuerzo-tests-f005)
Sin líneas de producción en el alcance: nada que mutar.
0 mutantes evaluados, 0 muertos, 0 supervivientes, 0 timeouts en 0.0 s
```

El alcance es 0 porque F-016 es una feature de **solo tests** y
`harness.alcance` excluye `tests/` y `progress/` por diseño. Mutar los tests de
esta feature sería medir al revés: la pregunta «¿los tests cazan un cambio en
el código?» aquí se responde en `mutacion_F-005_tras_refuerzo.md`, que es
donde está el código que estos tests existen para vigilar. La justificación
escrita, que `CHECKPOINTS.md` exige para no dejar la puerta en blanco, está en
**`progress/mutacion_F-016.md`**.

---

## 6. Desviaciones respecto al plan aprobado

**Ninguna en el alcance.** Dos precisiones sobre cómo se ejecutó:

- **El plan dejaba abierto «árbol actual o worktree del merge».** Se eligió el
  worktree, por comparabilidad y por seguridad (§5). El árbol actual se usó
  igualmente, pero para la fase RED (§4), donde lo que importa es que los seis
  mutantes mueren **en el código de hoy**, no solo en el de 2026-08-08. Las dos
  vías, no una.
- **El plan pedía tests `test_f016_*` para el frente 1.** El control negativo
  del frente 2 vive en `tests/test_f005_grants.py`, junto a la función que
  prueba, y se llama `test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta`:
  el prefijo mantiene la trazabilidad a F-016 aunque el fichero sea de F-005.
  Importar una función de otro módulo de tests solo para respetar el nombre del
  fichero habría sido peor.

---

## 7. Defectos de producción encontrados

**Ninguno.** El plan preveía la posibilidad («si un test nuevo revela un
defecto REAL, NO lo arregles: anótalo») y no ha hecho falta usarla: los seis
huecos eran huecos de test. El código hacía lo correcto en los seis casos; lo
que no había era nadie que lo comprobara. Ni un `git diff` sobre `config/`,
`etl_sigrid/`, `main.py`, `infra/` ni SQL.

**Anécdota que vale la pena dejar escrita**: la primera versión de este mismo
informe puso `init.sh` en rojo. El barrido de secretos de F-003
(`test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec`) cazó una
asignación de contraseña **de ejemplo** que yo había escrito en §3 para
describir los patrones del barrido de F-005:

```
E   AssertionError: el repositorio contiene datos que no deben versionarse:
E     progress/impl_F-016.md: contraseña escrita -> '<REDACTADO: la palabra clave, un igual y un valor>'
```

(La traza va redactada a propósito: reproducirla literal vuelve a poner el
barrido en rojo, y ya lo intenté una segunda vez para comprobarlo.)

Falso positivo desde el punto de vista de la intención, verdadero positivo
desde el del barrido: era una asignación de contraseña escrita en un fichero
versionado, y distinguir «es un ejemplo» de «es real» no es trabajo de un
regex. **No se ha tocado el test**: se reformuló la frase, que es lo que hizo
F-004 en su momento y lo que corresponde. Sirve además de comprobación gratis
de que ese barrido está vivo.

## 8. Verificaciones MANUAL pendientes

**Ninguna.** Nada de esta feature toca red, BBDD ni Azure. No se ha ejecutado
`python main.py`, ni `check-pg`, ni `status`, ni comando alguno contra el
Postgres compartido, conforme a la restricción de la sesión (`.env` apunta a
producción).

## 9. Limpieza

El worktree `C:/Users/pgris/PycharmProjects/wt-f016-c7500d4` se retira al
cerrar (`git worktree remove --force`). La campaña restaura siempre los
ficheros mutados; se comprobó que no quedó ninguno mutado antes de retirarlo.

---

## 10. Evidencias

Números medidos, no estimados, y comparables con los de otras features.

| Evidencia | Valor | Cómo se obtuvo |
|---|---|---|
| **Tests ejecutados y resultado** | **388 passed**, 0 fallos, 3,63 s | `python -m pytest -q` dentro de `bash harness/init.sh` (bajo coverage) |
| Tests antes de esta feature | 379 | 388 − 8 nuevos de F-016 − 1 control del barrido |
| **Cobertura de las líneas cambiadas** | **N/A justificado** — `PUERTA COBERTURA: N/A (F-016 no cambia líneas Python de producción frente a dev)` | línea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados y supervivientes (F-016)** | 0 generados, 0 supervivientes | `python -m harness.mutacion --feature F-016` → `progress/mutacion_F-016.md`, con la justificación escrita del alcance vacío |
| **Mutantes generados y supervivientes (F-005, el objetivo real)** | 101 generados · **54 muertos** · **47 supervivientes** · 0 timeouts · **0 de riesgo ALTO** | `python -m harness.mutacion --feature F-005 --base c7500d4 --rama __no_existe__ --raiz <worktree> --salida progress/mutacion_F-005_tras_refuerzo.md` |
| Puntuación de mutación de F-005 | 45,5 % → **53,5 %** | ídem, contra la línea base |
| **Tiempo de ejecución de la suite** | **3,63 s** (388 tests, bajo coverage); 4,48 s sin coverage en la ejecución previa | salida de pytest |
| Tiempo de la campaña de mutación | 134,6 s (101 mutantes) | salida de `harness.mutacion` |
| `bash harness/init.sh` | **exit 0**, `ENTORNO LISTO` | ejecutado al cerrar la feature |
| Lint | `python -m ruff check` sin avisos en los dos ficheros tocados | `ruff check tests/test_f016_huecos_alto_f005.py tests/test_f005_grants.py` |

### Trazabilidad criterio → test

| `acceptance` de F-016 | Dónde se cumple |
|---|---|
| Tests nuevos que fijan los 6 huecos ALTO, sin red ni BBDD | `tests/test_f016_huecos_alto_f005.py` (8 tests) · §4 |
| Campaña relanzada: los 6 mutantes ALTO mueren; cómo se reconstruye el alcance, documentado | `progress/mutacion_F-005_tras_refuerzo.md` · §5 |
| Informe nuevo; la línea base NO se sobrescribe ni se retoca | `progress/mutacion_F-005.md` intacto (`git status` limpio) |
| Supervivientes MEDIO y BAJO contabilizados como deuda, no tapados | 24 + 15, analizados uno a uno en el informe nuevo |
| Barrido de `test_f005_r21` afinado (hallazgo de F-004) | `tests/test_f005_grants.py`: `buscar_secretos()` + `_parece_ruta()` + control negativo |
| `bash harness/init.sh` en verde | exit 0, 388 tests |
| PARADA 1 cumplida | plan aprobado por el humano el 2026-08-10; sin paradas adicionales |
