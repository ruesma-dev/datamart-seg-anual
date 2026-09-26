<!-- progress/mutacion_F-066_tolerancia_recuentos.md -->
# F-066 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-066` el 2026-09-09 01:29.

**Esa línea de arriba la escribe el arnés y NO reproduce esta campaña** (es el
hallazgo 2 de F-069: el informe no imprime el `--base` resuelto). El mando real
de esta primera pasada fue:

```
python -m harness.mutacion --feature F-066 --base b3abcf4 --rama e2e2ad8     --workers 1 --salida progress/mutacion_F-066_tolerancia_recuentos.md
```

Con `--base dev` el alcance sería la rama entera —trabajo de F-025 y F-068
incluido— y no el diff de esta corrección.

## Alcance

Origen del diff: **rama** (`b3abcf48160ed0411712a1b30e7faf67c9e77b2e` .. `e2e2ad8`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/recuentos.py` | 195 |
| `main.py` | 46 |
| **Total** | **241** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 35 |
| Mutantes evaluados | 35 |
| Muertos | 29 |
| Supervivientes | 6 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 4264.1 s |
| SHA de HEAD medido | `f94fae66d08b50b3dab7e9901e8c451855d350f7` |
| Línea base (s) — `.` | 165.1 |
| Media por mutante evaluado (s) | 121.8 |
| Timeout efectivo por mutante (s) | 331 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/recuentos.py:129` [comparacion]

- Original: `if diferencia < 0:  # type: ignore[operator]`
- Mutado:   `if diferencia <= 0:  # type: ignore[operator]`

#### Análisis · MUTANTE EQUIVALENTE, no hay test que escribir

**Por qué ningún test lo caza:** porque no existe ninguno que pueda. La línea
129 solo se alcanza cuando `sigrid` no es `None` (si no, la 125 devolvió `SIN
MEDIR`), cuando `raw` no es `None` (si no, la 126 devolvió `AUSENTE EN RAW`)
—y de ahí que `diferencia` sea un `int`— y cuando `diferencia != 0`, porque el
cero ya salió por `return ESTADO_OK` en la 127. Sobre `{d ∈ ℤ : d ≠ 0}`,
`d < 0` y `d <= 0` son la misma función: no hay entrada que las distinga.

**Decisión: equivalente.** No se añade test. Uno que fijara «diferencia cero no
es SOBRAN» ya existe (`..._cada_tabla_lleva_su_estado`, caso `(10, 10) -> OK`) y
tampoco lo mataría, porque el mutante no cambia esa respuesta: sería test de
adorno. Lo que sostiene la equivalencia es la guarda de la 127, y esa guarda
**sí está probada**: sus dos mutantes murieron en esta campaña (nº 10 y 11). Si
alguien quitara el `return ESTADO_OK` del cero, este mutante dejaría de ser
equivalente y la campaña volvería a hablar.

### 2. `etl_sigrid/domain/recuentos.py:129` [entero]

- Original: `if diferencia < 0:  # type: ignore[operator]`
- Mutado:   `if diferencia < 1:  # type: ignore[operator]`

#### Análisis · MUTANTE EQUIVALENTE, no hay test que escribir

**Por qué ningún test lo caza:** el mismo argumento que el superviviente 1, con
la otra cota. En el dominio alcanzable —enteros distintos de cero— `d < 0` y
`d < 1` son la misma función: el único entero que las separaría es el 0, y el 0
no llega nunca a esta línea.

**Decisión: equivalente.** Mismo motivo y misma dependencia: la guarda del cero
de la línea 127, probada y con sus dos mutantes muertos.

### 3. `etl_sigrid/domain/recuentos.py:165` [logico]

- Original: `return max(medidas, key=lambda r: r.desviacion_pct or 0.0) if medidas else None`
- Mutado:   `return max(medidas, key=lambda r: r.desviacion_pct and 0.0) if medidas else None`

#### Análisis · HUECO REAL, muerto con test nuevo

**Por qué ningún test lo cazaba:** con `and`, la clave de ordenación vale `0.0`
para toda tabla de `medidas` (que son justamente las de desviación truthy), así
que `max` devuelve **la primera de la lista** en vez de la de más desviación. El
único fixture con varias tablas derivadas es el del día real, y en él la peor
—`obrparpre`— es la primera: el mutante acertaba por casualidad. Ningún test
afirmaba la identidad de `peor`. No es cosmético: `peor` existe para decirle al
de guardia qué tabla mirar primero, y señalar la equivocada es peor que no
señalar ninguna.

**Decisión: test nuevo,** con la peor puesta **la última** a propósito:
`test_f066_r15_la_peor_tabla_es_la_de_mas_desviacion_y_no_la_primera`.

### 4. `etl_sigrid/domain/recuentos.py:221` [comparacion]

- Original: `return _SIN_CIFRA if valor is None else f"{valor:+,}".replace(",", ".")`
- Mutado:   `return _SIN_CIFRA if valor is not None else f"{valor:+,}".replace(",", ".")`

#### Análisis · HUECO REAL, muerto con test nuevo

**Por qué ningún test lo cazaba:** `_diferencia` solo se usa dentro de
`_bloque`, y allí recibe `s - r` con las dos cifras ya medidas, nunca `None`.
Invertida la guarda, la función devuelve `—` para **todos** los valores reales:
los bloques de hallazgos seguirían saliendo, con su título y sus dos cifras,
pero sin decir cuántas filas bailan. Los tests miraban el título del bloque y el
veredicto, no la cifra.

**Decisión: test nuevo,** que fija la línea entera de los dos bloques, con su
diferencia y su signo:
`test_f066_r15_cada_bloque_dice_cuantas_filas_bailan_y_hacia_donde`.

### 5. `etl_sigrid/domain/recuentos.py:228` [aritmetico]

- Original: `f"  {tabla}: Sigrid {_cifra(s)}, raw {_cifra(r)} ({_diferencia(s - r)})"`
- Mutado:   `f"  {tabla}: Sigrid {_cifra(s)}, raw {_cifra(r)} ({_diferencia(s + r)})"`

#### Análisis · HUECO REAL, muerto con el mismo test nuevo

**Por qué ningún test lo cazaba:** el mismo agujero que el superviviente 4, por
el otro lado. Con `s + r` el bloque imprime la **suma** de las dos cifras en vez
de la diferencia: un número grande, con signo `+`, perfectamente creíble
—`(+4.309.087)` donde debía poner `(-1)`— que mandaría a buscar una avería que
no existe. Se leía igual de bien y por eso pasaba.

**Decisión: test nuevo,** el mismo del superviviente 4: afirma la línea
completa, así que caza tanto el «—» como la suma.

### 6. `main.py:1988` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis · HUECO REAL, muerto con test nuevo

**Por qué ningún test lo cazaba:** ninguno miraba el `--help`. Sin
`show_default`, la ayuda describe `--tolerancia-pct` como «un porcentaje» y no
dice cuál se aplica; es el mismo defecto que el cambio corrige en la salida
—«sin el umbral, un verde no se puede interpretar»— pero en la ayuda, que es
donde mira quien lanza el comando a mano.

**Decisión: test nuevo,** que comprueba que el valor por defecto sale impreso:
`test_f066_r15_la_ayuda_dice_con_que_tolerancia_se_va_a_ejecutar`.


## Segunda pasada · verificación

Con los tres tests nuevos del commit `ddcf8b2`, mismo alcance y mismo mando:

```
python -m harness.mutacion --feature F-066 --base b3abcf4 --rama e2e2ad8 \
    --workers 1 --salida progress/mutacion_F-066_verificacion.md
```

| Pasada | Mutantes | Muertos | Supervivientes | Timeouts | Sin veredicto | Tiempo |
|---|---|---|---|---|---|---|
| 1ª | 35 | 29 | 6 | 0 | 0 | 4.264,1 s |
| 2ª | 35 | **33** | **2** | 0 | 0 | 3.871,5 s |

Los cuatro huecos reales (nº 3, 4, 5 y 6 de arriba) están **muertos**. Los dos
que quedan son los equivalentes de `recuentos.py:129`, que ningún test puede
matar y cuyo argumento está escrito arriba. Salida cruda de esta pasada:
`progress/mutacion_F-066_verificacion.md`.

## Lo que esta campaña NO ha podido mirar

`harness/mutacion.py` no genera mutantes para las constantes `float` ni para la
división. En este alcance eso son **seis sitios ciegos**: `TOLERANCIA_DERIVA_PCT
= 0.05` (L75), el `0.0` y el `100.0` de `desviacion_pct` (L117 y L118), el `0.0`
de la clave de `peor` (L165) y el `/ self.sigrid` de L118. Con esos dos
operadores los 35 mutantes serían unos 41. Están probados por tests
—`..._cae_en_la_unica_ventana_util` fija las dos cotas del 0,05 % y
`..._la_desviacion_se_mide_contra_la_cifra_de_sigrid` fija la división—, pero
eso lo demuestran los tests y no esta campaña. Propuesta para F-069, junto a la
de `in` / `not in` que salió de F-068.
