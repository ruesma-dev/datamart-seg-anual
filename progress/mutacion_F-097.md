<!-- progress/mutacion_F-097.md -->
# F-097 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-097` el 2026-09-28 12:45.

## Alcance

Origen del diff: **rama** (`ee4c10a4dd5b37634d240f1cb6cb0db10d47583c` .. `feature/F-097-descompuestos-partidas`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 28 |
| `etl_sigrid/application/steps/build_descompuestos_step.py` | 270 |
| `etl_sigrid/application/steps/ingest_descompuestos_step.py` | 381 |
| `etl_sigrid/domain/descompuestos.py` | 432 |
| `etl_sigrid/domain/diccionario.py` | 4 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 112 |
| `main.py` | 94 |
| **Total** | **1321** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 175 |
| Mutantes evaluados | 20 |
| Muertos | 16 |
| Supervivientes | 4 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 4186.9 s |
| SHA de HEAD medido | `c1bf0bfb0ca4623ba99801b2d21584899a2a82a1` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-097_vo66fesk/wk_0` | 438.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-097_vo66fesk/wk_1` | 439.5 |
| Media por mutante evaluado (s) | 209.3 |
| Timeout efectivo por mutante (s) | 879 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | sí — 20 de 175 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/descompuestos.py:164` [comparacion]

- Original: `if posicion >= len(campos):`
- Mutado:   `if posicion > len(campos):`

#### Análisis del implementer

> Por qué ningún test lo caza: ningún registro de ejemplo tenía EXACTAMENTE
> tantos campos como una de las posiciones pedidas (15, 16 o 17); con `>` el
> campo que falta da `IndexError` y tumbaría el troceado de un registro cortado.
> Decisión: HUECO REAL. Test nuevo `test_f097_r13_registro_cortado_justo_en_una_posicion`
> (15 a 18 campos). Reproducido en una copia aislada: con la mutación, 2 fallos.

### 2. `etl_sigrid/domain/descompuestos.py:178` [comparacion]

- Original: `crudo = campos[POSICIONES["dncpro_id"]] if len(campos) > POSICIONES["dncpro_id"] else ""`
- Mutado:   `crudo = campos[POSICIONES["dncpro_id"]] if len(campos) >= POSICIONES["dncpro_id"] else ""`

#### Análisis del implementer

> Por qué ningún test lo caza: no había registro de EXACTAMENTE 36 campos (0..35),
> el único en que el campo 36 no existe y la mutación lee fuera de la lista.
> Decisión: HUECO REAL. Test nuevo `test_f097_r13_registro_de_36_campos_no_tiene_enlace`
> (36 y 37 campos). Reproducido en una copia aislada: con la mutación, 1 fallo.

### 3. `etl_sigrid/domain/descompuestos.py:409` [entero]

- Original: `if mb_por_lote <= 0:`
- Mutado:   `if mb_por_lote <= 1:`

#### Análisis del implementer

> Por qué ningún test lo caza: el único test del tamaño de lote usaba 0 (se
> rechaza con los dos operadores); ninguno usaba un lote entre 0 y 1 MB.
> Decisión: HUECO REAL (no equivalente: 0,5 MB es un lote legítimo que la
> mutación rechazaría). Test nuevo `test_f097_r21_un_lote_de_menos_de_un_mb_vale`.
> Reproducido en una copia aislada: con la mutación, 1 fallo.

### 4. `etl_sigrid/domain/descompuestos.py:411` [not]

- Original: `if not sin_tope and presupuesto_mb <= 0:`
- Mutado:   `if sin_tope and presupuesto_mb <= 0:`

#### Análisis del implementer

> Por qué ningún test lo caza: el presupuesto no positivo solo se probaba en
> `planificar_relectura`; en `planificar_troceado` ningún test lo pasaba a 0.
> Decisión: HUECO REAL. Test nuevo `test_f097_r21_el_tope_del_troceado_se_valida_solo_con_tope`
> (0 con tope se rechaza; 0 sin tope trocea). Reproducido en una copia aislada:
> con la mutación, 1 fallo.

## Tras la campaña

Los cuatro supervivientes eran huecos reales del dominio y los cuatro tienen
test nuevo en `tests/test_f097_planificador.py` (commit posterior al SHA medido).
Cada mutación se reprodujo sobre una COPIA del repositorio (nunca el árbol real):
con el test nuevo, cada una da al menos un fallo; sin mutar, 88 passed. Los
totales de arriba son los medidos y no se tocan: 16 de 20 muertos.
