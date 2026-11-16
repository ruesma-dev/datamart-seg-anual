<!-- progress/mutacion_F-163.md -->
# F-163 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-163 --base main --workers 3 --con-seleccion` el 2026-11-15 20:40.

**Orden exacta lanzada** (2026-11-15 17:39 UTC, sobre `1122cc1`, tras el APPROVED de la pasada 2
sobre `f75357d`): `python -m harness.mutacion --feature F-163 --con-seleccion --timeout 5400 --workers 3`.
Nivel `estandar`: campaña **INFORMATIVA**, los supervivientes no se analizan. La herramienta no
admite elegir ficheros de test; su selección de tests (`--con-seleccion`, F-019) es la vía: mide
una vez el mapa línea -> tests y juzga cada mutante con los tests que ejecutan su línea (37 de
media), revalidando con la suite entera lo que no matan. `--timeout 5400` por la lección de F-161
(la suite entera tarda ~1.650 s por worktree): la línea base cupo con holgura y no hubo timeouts.
Sin mutantes aplicados en el árbol principal (`--estado`: «Sin campaña de mutación en curso»); los
worktrees `mutacion_F-163_*` los retiró la propia herramienta (`git worktree list` sin ellos).
Código de salida 1 = hay supervivientes (informativo, no bloquea).

## Alcance

Origen del diff: **rama** (`e086ee4ccbe6a7f2e6f8d3e15661248105d715d4` .. `feature/F-163-completa-fin-de-semana`).

| Fichero | Líneas en alcance | Mutantes generados |
|---|---|---|
| `config/settings.py` | 8 | 0 — sin mutantes |
| `etl_sigrid/application/steps/build_stg_step.py` | 3 | 0 — sin mutantes |
| `etl_sigrid/domain/reanudacion.py` | 4 | 1 |
| `etl_sigrid/domain/ventana.py` | 70 | 16 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 4 | 0 — sin mutantes |
| `etl_sigrid/infrastructure/postgres/ventana_sql.py` | 5 | 0 — sin mutantes |
| `main.py` | 12 | 0 — sin mutantes |
| **Total** | **106** | **17** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 17 |
| Mutantes evaluados | 11 |
| Muertos | 10 |
| Supervivientes | 1 (0 podados sin ejecutar, 1 medidos) |
| Timeouts | 0 |
| Indeterminados | 0 |
| Timeouts repasados en serie | 0: ningún mutante agotó el reloj |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 7268.1 s |
| SHA de HEAD medido | `1122cc1af39d58601e2889c65e7d7ba7a1dbc8cb` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-163_jihtlh26/wk_0` | 1654.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-163_jihtlh26/wk_1` | 1641.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-163_jihtlh26/wk_2` | 1666.0 |
| Media por mutante evaluado (s) | 660.7 |
| Timeout efectivo por mutante (s) | 5400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 5400 |
| Workers | 3 |
| Un mutante por línea | sí — 17 generados → 11 candidatos, uno por línea |
| Muestreo | no: campaña completa (11 candidatos ≤ tope 20 del nivel `estandar`) |
| Selección de tests | activa — mapa línea -> tests, poda y subconjuntos validados |
| SHA del mapa | `1122cc1af39d58601e2889c65e7d7ba7a1dbc8cb` |
| Medición del mapa (s) | `.`: 2323.7 |
| Tests en la suite | `.`: 15781 |
| Tamaño medio del subconjunto | 37.1 tests (9 mutantes) |
| Revalidados con la suite entera | 1 (0 murieron al revalidar) |
| Subconjuntos descartados | 0 |
| Podados (sin ejecutar) | 0 |
| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | 0.0 |
| Media por mutante juzgado con la suite entera (s) | 1356.1 (3 mutantes) |

## Cómo se juzgó

- **PODADO**: ningún proceso medido ejecuta la sentencia del mutante, así que no puede cambiar ninguna ejecución; es superviviente sin escribirlo ni correr nada. Un PODADO necesita la misma justificación escrita que uno medido. Riesgo residual: un subproceso que no hereda el entorno o usa otro intérprete no se mide, y sus líneas parecerían no ejecutadas; `--sin-seleccion` lo descarta.
- El **muerto** del subconjunto **no se revalida**: ese subconjunto se corrió antes SIN mutar y salió verde, así que el test que cae lo hace por el mutante, y ese test también está en la suite entera.
- Lo que el subconjunto no mata (superviviente, timeout, indeterminado) **sí se revalida** con la suite entera y el mutante aún aplicado: que no caiga ninguno de sus tests no prueba que no caiga ninguno de la suite, y el veredicto que cuenta es el de la suite entera.
- El **timeout** por mutante sigue saliendo de la **línea base** de la suite entera: es la única medida tomada con la contención de los W workers; un subconjunto no tiene base propia, medirla costaría más de lo que ahorra, y un mutante que cuelga cuelga igual con dos tests que con doscientos.


## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/ventana.py:660` [entero]

- Original: `if ultima.date() < hoy - timedelta(days=1):`
- Mutado:   `if ultima.date() < hoy - timedelta(days=2):`
- Juicio: MEDIDO

#### Análisis (nivel `estandar`: informativo, no se analiza)

> Nota sin análisis formal: el borde entre `days=1` y `days=2` es una completa registrada el
> VIERNES (solo posible con `--reconstruir-todo` o con la de D2) seguida de un domingo; los tests
> del domingo usan el domingo anterior (7 días) o el propio sábado. Lo cerraría un caso
> «viernes -> domingo dispara».

## No muertos: código de salida

| Fichero:línea | Operador | Veredicto | Código |
|---|---|---|---|
| `etl_sigrid/domain/ventana.py:660` | entero | superviviente | 0 |

## Ficheros sin mutantes

Cada uno tiene líneas en alcance y el generador no ha sacado de ellas ni un mutante: la campaña no las ha juzgado. Declara por qué no hay nada que mutar (solo declaraciones, cadenas, imports) o qué test de la fase RED cubre el cambio. El reviewer hace la prueba de control (`generar_mutantes` sin exclusión de alcance) y ninguna declaración puede quedarse en `PENDIENTE` al cerrar la feature.

### `config/settings.py` — 8 líneas en alcance, 0 mutantes

#### Declaración

> Solo el texto de `description` de `ventana_dia_completa` (cadena): nada que mutar. El defecto 6 no cambia y lo fija `test_f025_settings`.

### `etl_sigrid/application/steps/build_stg_step.py` — 3 líneas en alcance, 0 mutantes

#### Declaración

> Solo un comentario: nada que mutar.

### `etl_sigrid/infrastructure/postgres/postgres_client.py` — 4 líneas en alcance, 0 mutantes

#### Declaración

> Solo comentarios: nada que mutar.

### `etl_sigrid/infrastructure/postgres/ventana_sql.py` — 5 líneas en alcance, 0 mutantes

#### Declaración

> Docstring y la cadena del `detalle` de la firma divergente: nada que mutar con los operadores del generador.

### `main.py` — 12 líneas en alcance, 0 mutantes

#### Declaración

> Solo cadenas de `help` y del docstring de `check-ventana`: nada que mutar.

