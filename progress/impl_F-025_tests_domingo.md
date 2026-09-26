# F-025 · Los cinco tests que fallaban los domingos (2026-09-06)

Tarea pequeña y acotada, aprobada por el humano el 2026-09-06. **Solo tests.**
No se ha tocado ni una línea de código de producción.

## El problema

`BuildStgStep._planificar_ventana` toma la fecha con `datetime.utcnow().date()`
(`etl_sigrid/application/steps/build_stg_step.py:542`) y `_toca_completa` hace lo
mismo con `datetime.utcnow()` (línea 599). Eso es **correcto en producción**: la
noche que corre el job decide con la fecha de esa noche.

El problema estaba en el fichero de tests. Cinco tests de
`tests/test_f025_build.py` daban por hecho un día laborable y no fijaban la
fecha, así que los domingos R25 (`etl_sigrid/domain/ventana.py`, `DOMINGO = 6`,
`toca_reconstruccion_completa`) mandaba reconstrucción completa, las tres obras
del censo entraban con motivo `completa` y las cuentas no cuadraban. Un día de
cada siete, `bash harness/init.sh` en rojo sin que nada estuviera roto.

## Evidencia RED (antes del arreglo)

`python -m pytest tests/test_f025_build.py -q`, hoy domingo 2026-09-06:

```
FAILED tests/test_f025_build.py::test_f025_r9_sin_obras_que_reconstruir_no_se_toca_nada
FAILED tests/test_f025_build.py::test_f025_r9_con_el_conjunto_vacio_las_congeladas_igual_se_registran
FAILED tests/test_f025_build.py::test_f025_r6_el_presupuesto_tambien_se_acota
FAILED tests/test_f025_build.py::test_f025_r30_el_paso_registra_cuantas_reconstruye_y_cuantas_congela
FAILED tests/test_f025_build.py::test_f025_r10_las_sobrantes_solo_se_miran_en_la_reconstruccion_completa
5 failed, 37 passed, 658 warnings in 1.57s
```

El detalle de uno de ellos, con la causa a la vista en el log del propio step
(reproducido sobre la versión de `HEAD` con
`python -m pytest ... -k "r30_el_paso_registra_cuantas"`):

```
>       assert resultado.metadata["obras_reconstruidas"] == 1
E       assert 3 == 1

tests\test_f025_red_tmp.py:656: AssertionError
--- Captured stdout call ---
... [info] ventana_plan completa=True denunciadas=[]
    motivo_completa='hoy es el dia de la reconstruccion completa y la ultima
    fue el 2026-09-01' obras_a_reconstruir=3 obras_congeladas=0
    por_motivo={'completa': 3} sello=9b45526c ventana_activa=True
```

## Qué cambió

Un solo fichero de código: **`tests/test_f025_build.py`**.

1. `reloj_parado(momento)` — devuelve una **subclase de `datetime`** cuyo
   `utcnow()` (classmethod) devuelve siempre `momento`. Subclase y no un doble
   suelto a propósito: el step usa `datetime` para más cosas que la fecha del
   plan (marcas de tiempo en `_meta`, restas para medir duraciones en las líneas
   365, 431, 448, 458, 467, 486, 599, 629, 661, 942 y 988), y con una subclase
   todo eso sigue funcionando igual. Se comprobó que el step **no** usa el
   constructor `datetime(...)` ni `isinstance` sobre él.
2. `congelar_fecha(monkeypatch, momento)` — hace el
   `monkeypatch.setattr(modulo, "datetime", ...)`. Auxiliar reutilizable, con la
   explicación de por qué existe.
3. `ejecutar(pg, monkeypatch, *, ahora=JUEVES_LABORABLE, **kwargs)` — congela la
   fecha en el **jueves 2026-09-03 02:00 UTC** por defecto, y acepta `ahora=` para
   pedir otro día. Las 40 llamadas existentes no cambian: heredan el jueves.
   Constantes nuevas `JUEVES_LABORABLE` y `DOMINGO_DE_COMPLETA` (2026-09-06 02:00).
4. Test nuevo `test_f025_r25_el_domingo_se_reconstruye_todo`: ejecuta el paso un
   domingo sobre el censo por defecto (que trae dos obras congeladas, una
   CERRADA y una administrativa) y comprueba que ese día entran las tres, que
   ninguna se congela y que el motivo escrito es `completa`. **R25 pasa de
   tumbar tests por accidente a estar cubierta a propósito.**

Y un fichero de documentación: `specs/F-025-ventana-negocio-build/mediciones.md`,
párrafo nuevo al final de la Fase 7 con el hallazgo y el arreglo.

## Resultado real

```
python -m pytest tests/test_f025_build.py -q -p no:warnings
43 passed in 1.35s
```

(42 antes → 43 ahora: los 5 que fallaban en verde, más el test nuevo.)

```
bash harness/init.sh
3322 passed, 134 skipped, 1230 warnings in 415.35s (0:06:55)
[OK] PUERTA COBERTURA: 91.9% de 640 líneas cambiadas cubiertas (588/640,
     umbral 80%, nivel critico)
[OK] PUERTA TAMAÑO: F-025 dentro de los topes
     (requirements 150/150, design 250/250, impl 220/220, review 121/140)
ENTORNO LISTO. Puedes trabajar.
```

Avisos preexistentes que **no** introduce este cambio: `ruff` con 211 avisos
(deuda previa, no bloquea) y el aviso de features en estado `blocked`
(F-025 y F-052).

## Qué quedó fuera (a propósito)

- **El step no se toca.** Sigue leyendo la fecha real; es lo correcto en
  producción y es la razón de que R25 funcione la noche del domingo.
- **No se ha barrido el resto de la suite** buscando otros tests dependientes
  del calendario. Solo se arreglaron los cinco reportados. `init.sh` completo en
  verde hoy, domingo, sugiere que no hay más en este mismo agujero, pero no se
  ha auditado fichero a fichero.
- **No se ha migrado `datetime.utcnow()` a `datetime.now(UTC)`** pese a los
  `DeprecationWarning` del step: es código de producción y sale del alcance.
- **No se ha ejecutado campaña de mutación**: es un arreglo de tests, sin
  código de producción nuevo que mutar, y la campaña cuesta más de dos horas.
- Estado de la feature intacto: F-025 sigue `blocked` en `features.json`.
- **`specs/F-066-ingesta-raw-pendientes/`** (sin seguimiento, lo escribe otro
  agente en paralelo) no se ha tocado, ni añadido, ni borrado.

## Ramas y commit

Commit `5fedc48` hecho en `feature/F-025-ventana-negocio-build` y traído a
`feature/F-066-ingesta-raw-pendientes` con `git merge --ff-only`. Ambas ramas
apuntan a `5fedc48`; HEAD queda en la de F-066. Sin `git push`.

**Un efecto colateral que conviene saber.** Mientras yo trabajaba con HEAD en la
rama de F-025, otro agente hizo su commit de backlog `1ce9985` («nace F-067…»,
`BACKLOG.md` + `harness/features.json`) y, como HEAD estaba ahí, **aterrizó en la
rama de F-025** en vez de en la de F-066. Mi commit quedó encima, y el
`--ff-only` ha llevado los dos a `feature/F-066-ingesta-raw-pendientes`. No se ha
perdido ni duplicado nada —ambas ramas contienen ahora los dos commits, y el de
backlog es bookkeeping compartido, no código—, pero explica por qué el
`git merge` avanza 5 ficheros y no los 3 de este trabajo. No se ha reescrito
historia para separarlos: no compensa el riesgo con dos agentes en paralelo.
