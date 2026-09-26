<!-- progress/mutacion_F-066_reconciliar_columnas.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-08 12:20.

## Alcance

Origen del diff: **rama** (`79059f835a218ecc69ff6985baddf913591a164f` .. `feature/F-066-ingesta-raw-pendientes`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 180 |
| **Total** | **180** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 6 |
| Mutantes evaluados | 6 |
| Muertos | 6 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 2091.5 s |
| SHA de HEAD medido | `ca1d6b99e0f1e929545e2da1953d19419a048847` |
| Línea base (s) — `.` | 314.0 |
| Media por mutante evaluado (s) | 348.6 |
| Timeout efectivo por mutante (s) | 628 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


## Nota del implementer: cuatro lanzamientos, y por qué dos no valen

Esta campaña es del **arreglo del defecto de `ensure_raw_table`** (T17-T18,
`progress/impl_F-066_reconciliar_columnas.md`), no de F-066 entera: el
`--base 79059f8` la acota a las 180 líneas nuevas de `postgres_client.py` y
deja fuera la campaña de T12, que el humano ya firmó el 2026-09-06.

### 1.ª · sobre `1d9a075`, paralela — ABORTADA a propósito

16 mutantes. Llegó a 12/16 con **tres supervivientes**, y los tres caían en la
misma expresión: la aritmética de índices de `_tipo_normalizado`, que buscaba
los paréntesis del tipo con `str.find`.

```
[3/16]  superviviente postgres_client.py:109 [entero] if fin != -1:     -> if fin != -2:
[4/16]  superviviente postgres_client.py:107 [entero] if inicio != -1:  -> if inicio != -2:
[12/16] superviviente postgres_client.py:111 [entero] texto[fin + 1 :]  -> texto[fin + 2 :]
```

**Los tres son EQUIVALENTES**, y ahí estaba el problema. `str.find` devuelve
`-1` o un índice ≥ 0, nunca `-2`: comparar contra `-2` solo cambia el
comportamiento con un tipo que tenga `)` y no tenga `(`. Y `texto[fin + 2 :]`
solo se separa de `texto[fin + 1 :]` si detrás del paréntesis de cierre queda
algo — en `character varying(30)` cierra al final, y en
`timestamp(3) without time zone` el carácter que se pierde es el espacio, que
`.split()` se come igual.

**No se pidió exención: se quitó la aritmética.** Matarlos habría exigido
tests sobre cadenas que `format_type` no puede devolver, o sea afirmaciones
sobre basura y no sobre comportamiento; y firmarlos, como el `bold=True` de
T12, habría dejado el hueco en pie. `592e370` reescribe la función con
`str.partition`: el «no lo encontré» pasa a ser la cadena vacía del separador,
**no queda un solo literal entero en la función**, y los tres mutantes no es
que mueran, es que **dejan de existir**. El alcance baja de 16 mutantes a 6.
Comportamiento idéntico, comprobado sobre 24 tipos con 0 diferencias entre las
dos versiones.

### 2.ª · sobre `592e370`, paralela desde un worktree limpio — BASE ROJA

Error mío, y vale la pena dejarlo escrito. El árbol principal tenía cambios
del líder sin commitear y la campaña paralela exige árbol limpio, así que se
lanzó con `--raiz` sobre un `git worktree` recién creado. **Línea base roja: 79
tests de CLI caídos sin mutar nada**, y el arnés abortó sin escribir informe,
que es exactamente lo que debe hacer —sobre una base roja todo mutante saldría
«muerto» y el cero de supervivientes sería falso—.

La causa no es un fallo del arnés sino una decisión suya: **la campaña no copia
el `.env` al worktree**; lo vuelca al `os.environ` del coordinador desde la
**raíz**, para no dejar la configuración local en el temp del sistema (ver
`tests/test_mutacion_env_al_worktree.py`). Con la raíz apuntando a un worktree
que no tiene `.env`, no hay nada que volcar. La salida correcta era la que dice
el propio mensaje de error: `--workers 1`, que corre sobre el árbol principal y
no necesita worktree ni árbol limpio.

### 3.ª · sobre `592e370`, en serie — VÁLIDA, 1 superviviente

**6 mutantes, 5 muertos, 1 superviviente, 0 timeouts, 1.972,7 s.**

```
[6/6] superviviente postgres_client.py:967 [booleano] nullable=True, -> nullable=False,
```

Es el campo `nullable` de la línea de log `raw_columna_anadida`. Ningún test la
leía, así que se podía invertir sin que la suite se enterara. **Hueco real, no
mutante equivalente.**

Se cerró en `ca1d6b9` con un test que **no comprueba una constante**: ata las
dos mitades del cambio de esquema —lo que se **ejecuta** y lo que se **cuenta**
que se ejecutó—, de modo que si alguien pusiera el `ADD COLUMN` en `NOT NULL` y
dejara el log diciendo `nullable=True`, salta. El log es la única evidencia que
tendrá un humano leyendo la traza de la nocturna a las 00:00 UTC: una traza que
miente sobre un cambio de esquema en producción es peor que no tener traza.

Comprobado a mano antes de commitear, aplicando el mutante al fichero de
producción y devolviéndolo después (`git diff` vacío):

```
E           assert False is True
FAILED tests/test_f066_reconciliar_columnas.py::test_f066_r28_el_log_no_puede_mentir_sobre_como_nace_la_columna
1 failed, 28 passed in 1.36s
```

### 4.ª · sobre `ca1d6b9`, en serie — la que cuenta

Es la de la cabecera de este informe. **Ningún superviviente de las cuatro
pasadas se ha eximido por firma**: tres se hicieron desaparecer reescribiendo
la función y el cuarto se mató con un test.
