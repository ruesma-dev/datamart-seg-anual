<!-- progress/mutacion_F-120.md -->
# F-120 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-120` el 2026-10-02 00:30.

## Alcance

Origen del diff: **rama** (`af8114283498356df944bb5e95e6abc1b27d8cc2` .. `feature/F-120-factor-descompuesto`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_descompuestos_step.py` | 9 |
| `etl_sigrid/domain/descompuestos.py` | 65 |
| `main.py` | 9 |
| **Total** | **83** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 9 |
| Mutantes evaluados | 9 |
| Muertos | 8 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 2180.6 s |
| SHA de HEAD medido | `68e1223c4e09137459c649afe401366c8cec4d09` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-120_d38228ie/wk_0` | 370.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-120_d38228ie/wk_1` | 373.1 |
| Media por mutante evaluado (s) | 242.3 |
| Timeout efectivo por mutante (s) | 747 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/descompuestos.py:137` [entero]

- Original: `PRECISION_PRODUCTO = 60`
- Mutado:   `PRECISION_PRODUCTO = 61`

#### Análisis (implementer, 2026-10-02)

> Por qué ningún test lo caza: subir la precisión de 60 a 61 cifras solo
> cambia un importe si el producto EXACTO de precio, factor y rendimiento
> necesita exactamente 61 cifras significativas y su redondeo a 60 cruza el
> medio céntimo. Los números del `des` no se acercan: el producto más largo de
> §2 de `spec_F-120.md` (`2.05405405405405 x 384.721 x 0.0000005`) son 22
> cifras. Y la mutación va HACIA el NUMERIC exacto de PostgreSQL, no en contra:
> con 61 el espejo se parece más al SQL, no menos.
>
> Lo que sí vigila un test es la dirección peligrosa, bajar la precisión:
> `test_f120_r11_multiplica_sin_perder_precision` (un precio de 30 cifras,
> 0,0049...9) da 0,01 con 28 cifras y 0,00 con 31, 32, 60 y 61 (comprobado
> fijando `PRECISION_PRODUCTO` en un proceso aparte, sin tocar el árbol).
>
> Decisión: **mutante equivalente justificado, sin test nuevo.** Un test que
> distinguiera 60 de 61 fijaría como correcto el redondeo a 60 cifras, que es
> justo la desviación respecto al SQL exacto que R11 quiere evitar.

