<!-- progress/impl_F-019.md -->
# F-019 · Build de `stg.plan_mensual` por tramos — Informe del implementer

Rama `feature/F-019-plan-mensual-por-tramos`. Rigor **`critico`**.
Spec: `specs/F-019-plan-mensual-por-tramos/` (requirements R1–R17, design con
DA-1..DA-4 aprobadas por el humano el 2026-08-10 tal cual se proponían).

> Este informe se escribe **según avanza el trabajo**, no al final.

## Regla de entorno que condiciona todo el trabajo

`.env` apunta a **`psql-albaranes-rs9k2`** (producción compartida). Este agente
**no ha abierto ninguna conexión** a BBDD ni a la API: ni `python main.py` en
ninguna forma, ni `psql`. Todos los requisitos `[MANUAL-local]` y
`[MANUAL-Azure]` (R1, R2, R13, R14, R15, R16) quedan **preparados como texto
ejecutable** y los lanza el humano. El guion está en `progress/current.md`
§F-019 y los comandos exactos, en `requirements.md`.

## Orden de tareas: desviación declarada (T1/T2 antes que T3)

`tasks.md` pone T1 (mediciones en local) y T2 (confirmar constantes) **antes**
que el código, y son tareas del **humano**: exigen un PostgreSQL con la carga
completa. No se han ejecutado todavía.

Se implementa T3–T10 con los **defaults propuestos y aprobados en la spec**
(`PG_TRAMO_MAX_FILAS=1_000_000`, `PG_DISCO_TOTAL_GB=32`,
`PG_DISCO_LIMITE_PCT=80`). La implementación **no depende de esos números**:
los tres son *settings* con default, cambiables por variable de entorno sin
tocar código ni tests (hay un test que lo demuestra,
`test_f019_r4_maximo_configurable_desde_settings`). Lo que T1/T2 pueden cambiar
es el **valor**, nunca el diseño.

**Condición de cierre que hereda el humano**: T1 y T2 deben ejecutarse y
anotarse **antes de T12** (la verificación contra Azure). Si T1 revelara una
obra con peso > `PG_TRAMO_MAX_FILAS` que domine el reparto (riesgo 3 del
design), hay que revisar la constante antes de lanzar nada contra el servidor
compartido.

---

# Fase RED (obligatoria en rigor `critico`)

Cada bloque trae el **comando exacto** y la **salida real** del fallo antes de
que existiera el código. No hay resúmenes: son las trazas pegadas.

## RED de T3 · `etl_sigrid/domain/tramos.py` (R3, R4, R5)

**Paso 1 — el módulo no existe todavía.** Los tests se escribieron primero:

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=short
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_f019_tramos.py __________________
ImportError while importing test module 'C:\...\tests\test_f019_tramos.py'.
Traceback:
tests\test_f019_tramos.py:16: in <module>
    from etl_sigrid.domain.tramos import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.tramos'
=========================== short test summary info ===========================
ERROR tests/test_f019_tramos.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

**Paso 2 — con las firmas puestas y SIN lógica** (`planificar_tramos` devuelve
`[]`), que es la RED que de verdad interesa: enseña que los tests miden el
comportamiento, no la existencia del import.

```
$ python -m pytest tests/test_f019_tramos.py -q --tb=line
     +    where [] = planificar_tramos({101: 900000, 102: 420000, 103: 380000, 104: 250000, ...}, 1000000)
tests\test_f019_tramos.py:75: assert 0 > 0
E   assert [] == [Tramo(indice...2), peso=100)]
      Right contains one more item: Tramo(indice=1, obras=(1, 2), peso=100)
tests\test_f019_tramos.py:83: assert [] == [Tramo(indice...2), peso=100)]
E   assert 0 == 1
     +  where 0 = len([])
tests\test_f019_tramos.py:93: assert 0 == 1
E   Failed: DID NOT RAISE ValueError
tests\test_f019_tramos.py:103: Failed: DID NOT RAISE ValueError
E   assert [] == [Tramo(indice...1), peso=900)]
      Right contains one more item: Tramo(indice=1, obras=(2, 3, 4, 1), peso=900)
tests\test_f019_tramos.py:123: assert [] == [Tramo(indice...1), peso=900)]
=========================== short test summary info ===========================
FAILED tests/test_f019_tramos.py::test_f019_r3_plan_de_tramos_particiona_las_obras
FAILED tests/test_f019_tramos.py::test_f019_r4_un_maximo_pequeno_produce_mas_tramos_igual_de_acotados
FAILED tests/test_f019_tramos.py::test_f019_r4_un_tramo_que_da_justo_el_maximo_no_se_parte
FAILED tests/test_f019_tramos.py::test_f019_r4_obra_gigante_va_en_tramo_unitario_con_warning
FAILED tests/test_f019_tramos.py::test_f019_r4_un_maximo_no_positivo_es_un_error_de_configuracion
FAILED tests/test_f019_tramos.py::test_f019_r5_las_obras_se_empaquetan_de_mayor_a_menor_peso
6 failed, 4 passed in 0.03s
```

**Honestidad sobre los 4 «passed»**: con la lista vacía, cuatro tests pasan
por vacuidad (recorren cero tramos). El plan de tramos real los pone a
trabajar; los seis que fallan son los que fijan el comportamiento. Se anota
porque un «4 passed» sin explicar induce a error.

**Verde tras implementar**: `10 passed in 0.06s`.

