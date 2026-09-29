<!-- progress/mutacion_F-097.md -->
# F-097 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-097` el 2026-09-28 15:18.

> **Procedencia (review 2).** Campaña lanzada por el reviewer en la pasada 2 sobre
> `6ca684d` con 2 workers (`--salida` fuera de `progress/`) y copiada aquí tal
> cual, como permite RM1 mientras los commits posteriores toquen solo tests y
> `progress/`: `git diff --stat 6ca684d HEAD -- etl_sigrid main.py config` está
> vacío. Sustituye a la campaña de `c1bf0bf` (175 mutantes, 16 de 20 muertos),
> que el delta de la review 1 dejó caducada.

## Alcance

Origen del diff: **rama** (`ee4c10a4dd5b37634d240f1cb6cb0db10d47583c` .. `feature/F-097-descompuestos-partidas`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 28 |
| `etl_sigrid/application/steps/build_descompuestos_step.py` | 270 |
| `etl_sigrid/application/steps/ingest_descompuestos_step.py` | 381 |
| `etl_sigrid/domain/descompuestos.py` | 444 |
| `etl_sigrid/domain/diccionario.py` | 4 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 112 |
| `main.py` | 94 |
| **Total** | **1333** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 178 |
| Mutantes evaluados | 20 |
| Muertos | 18 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3945.6 s |
| SHA de HEAD medido | `6ca684d251cc162c262ba657a2ffadba49c800ed` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-097_u1_cg08j/wk_0` | 448.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-097_u1_cg08j/wk_1` | 448.5 |
| Media por mutante evaluado (s) | 197.3 |
| Timeout efectivo por mutante (s) | 898 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | sí — 20 de 178 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/descompuestos.py:437` [comparacion]

- Original: `if actual and acumulado + pendiente.bytes > limite:`
- Mutado:   `if actual and acumulado + pendiente.bytes >= limite:`

#### Análisis del implementer

> Por qué ningún test lo caza: ningún test del troceado caía justo en el límite
> del lote (el de la relectura sí: `r6_justo_en_el_tope_cabe`). Con `>=`, un lote
> que llega EXACTAMENTE a `mb_por_lote` se parte en dos.
> Decisión: HUECO REAL, no equivalente. Test nuevo
> `test_f097_r21_dos_pendientes_que_llenan_el_lote_justo_van_juntas` (R2-2).
> Pasa contra el código; con la mutación aplicada a mano en una copia:
> `assert (((1, 0),), ((1, 1),)) == (((1, 0), (1, 1)),)`, 1 failed.

### 2. `main.py:5140` [booleano]

- Original: `default=False,`
- Mutado:   `default=True,`

#### Análisis del implementer

> Por qué ningún test lo caza: `r25_comandos_sueltos_con_sin_tope` comprueba que
> la opción existe y que se pasa al paso, no su valor por defecto. Con
> `default=True`, `python main.py ingest-descompuestos` a secas haría la primera
> carga (2,14 GB, 1,5-2 h contra `sigrid-api`) sin avisar: el más serio.
> Decisión: HUECO REAL, no equivalente. Test nuevo por comportamiento
> `test_f097_r7_sin_la_opcion_no_hay_primera_carga` (R2-3), con `CliRunner` y el
> paso doblado, para `ingest-descompuestos` y `build-descompuestos`: a secas llega
> `sin_tope=False`, con la opción `True`. Pasa contra el código; con
> `default=True` aplicado a mano en una copia, en cualquiera de los dos comandos:
> `assert [True, True] == [False, True]`, 1 failed.

## Mutante equivalente anotado (fuera de la muestra; lo encontró el reviewer en el delta)

- `etl_sigrid/domain/descompuestos.py`, primera guarda de `_redondeo` (línea 178,
  la 179 del reviewer): `abs(valor) >= LIMITE_IMPORTE` -> `abs(valor) > LIMITE_IMPORTE`.
- **Equivalente.** Solo cambia el caso |valor| = 1e16 exacto, y ahí la segunda
  guarda (`abs(redondeado) >= LIMITE_IMPORTE`, dos líneas más abajo) devuelve NULL
  igual: 1e16 redondeado a céntimos sigue siendo 1e16, y `quantize` a 18 cifras
  cabe en la precisión de 28 del contexto, así que tampoco hay `InvalidOperation`.
  La primera guarda existe para no llamar a `quantize` con números enormes
  (`1e300`), no para decidir el borde. No se persigue.
