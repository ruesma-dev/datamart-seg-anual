<!-- progress/control_mutacion_F-006.md -->
# F-006 · Control de la campaña de mutación (2026-08-26)

> Este fichero existe porque **la campaña miente un poco y hay que saber
> cuánto**. Lo escribió el líder tras encontrar una discrepancia entre dos
> campañas del mismo día. No sustituye a `progress/mutacion_F-006.md`, que es
> el informe de la campaña; lo acota.

## Lo que pasó

El mutante `etl_sigrid/domain/inventario.py:234 [not]` —quitarle el `not` a
`informe.avisos_columnas` en `formatear_cobertura`— recibió **dos veredictos
distintos el mismo día, sobre el mismo código**:

| Campaña | Workers | Veredicto |
|---|---|---|
| Prueba de las 15:08 (`99e2335`) | 2 | **superviviente** |
| Completa de las 15:18 (`99e2335`) | 6 | **muerto** (`[113/256]`) |

Entre los dos commits solo cambió un fichero de `progress/`. Mismo mutante,
mismo código de producción, veredicto opuesto.

## Cómo se resolvió, y un error por el camino

**Primer intento, equivocado.** Se aplicó el mutante en un `git worktree` y se
corrió la suite dos veces: código 1 las dos, «muerto». Falso: el worktree **no
tiene `.env`**, y con `-x` pytest paró en
`test_f006_t26_cli_dry_run_no_toca_la_base`, uno de los 23 que caen por
configuración ausente. **El rojo no era del mutante.** Es la misma trampa que
tumbó cuatro campañas de este repositorio: *un test rojo no dice por qué está
rojo*.

**Segundo intento, válido.** Mismo worktree, pero volcando el `.env` al entorno
con `harness.mutacion_paralela.volcar_variables()` —igual que hace la campaña
desde el arnés 1.7.7— y con `PYTHONDONTWRITEBYTECODE=1`:

```
pasada 1: codigo 0 -> SUPERVIVIENTE   2336 passed, 125 skipped en 216.35 s
pasada 2: codigo 0 -> SUPERVIVIENTE   2336 passed, 125 skipped en 268.63 s
```

**El mutante sobrevive.** Luego el veredicto falso fue el de la campaña de 6
workers: **un FALSO MUERTO**, que es la dirección peligrosa —un falso
superviviente cuesta un test de más; un falso muerto **esconde un superviviente
real**—.

## Cuánto de rota está: la muestra de control

Se reevaluaron **12 de los 204 muertos**, elegidos de forma determinista
(uno de cada 17 recorriendo la lista), **en serie y en limpio**, aplicándolos
con el propio mutador del arnés (`generar_mutantes` + `aplicar_mutante`), no
con sustitución de texto:

```
RESULTADO: 0 de 12 cambian de veredicto.
```

**Lectura honesta de ese cero:**

- El falso muerto **existe y está confirmado**, pero **no es un patrón masivo**:
  si uno de cada cinco muertos fuese falso, la probabilidad de que doce salieran
  todos bien sería del 7 %.
- Lo que doce casos **no** pueden descartar es una tasa baja. El techo
  estadístico razonable con 0 fallos en 12 ronda el 20 %, así que entre los 204
  pueden esconderse **unos pocos** supervivientes más.
- Por tanto: **52 supervivientes es un SUELO fiable**, no la lista cerrada.

## Qué se sospecha y qué no se ha demostrado

Las líneas base de los seis workers tardaron **462-486 s**, frente a **216-268 s**
sin carga: casi el doble. La hipótesis es que **bajo contención algún test cae**
y `-x` convierte esa caída en un «muerto» que nadie ha juzgado. **No está
demostrado**: no se ha identificado el test culpable. Alternativas no
descartadas: interferencia entre los seis worktrees (comparten el `.git` y el
mismo `.env`, que apunta a la misma base) o E/S de disco.

## Consecuencias

1. **La campaña sirve como evidencia con esta limitación declarada por
   escrito**, que es lo que el nivel `critico` exige. Sin este fichero, no.
2. **Va a F-041**, que ya documenta tres defectos de la campaña. Este es un
   **cuarto y nuevo**: los conocidos eran falsos muertos *por suite rota* (ya
   arreglado) y falsos verdes *por bytecode*. Este es un falso muerto **con la
   línea base verde y bajo paralelismo**, que ninguno de los tres cubre.
3. **Antes de cerrar F-006**, el reviewer debería exigir que los supervivientes
   que se declaren muertos por los tests nuevos se verifiquen **en serie**, no
   por una campaña paralela.
