<!-- progress/mutacion_F-080_modulos.md -->
# F-080 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-080` el 2026-09-14 22:14.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 176 |
| `etl_sigrid/domain/texto_comentarios.py` | 141 |
| **Total** | **317** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 27 |
| Mutantes evaluados | 27 |
| Muertos | 26 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3241.5 s |
| SHA de HEAD medido | `2ff8babc3a01a4a02c16d74e3607291358cf4896` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_m7unp1n3/wk_0` | 416.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_m7unp1n3/wk_1` | 417.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_m7unp1n3/wk_2` | 412.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_m7unp1n3/wk_3` | 421.8 |
| Media por mutante evaluado (s) | 120.1 |
| Timeout efectivo por mutante (s) | 844 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

> **QUÉ ES ESTA CAMPAÑA Y POR QUÉ EXISTE.** Es la SEGUNDA de F-080, dirigida
> con `--ficheros` a los dos módulos de Python que la feature toca, y **sin
> muestreo** (`--max-mutantes 0`): los 27 mutantes, evaluados todos. Existe
> porque la canónica (`progress/mutacion_F-080.md`) no dice nada sobre el
> código de F-080: su alcance son 3.789 líneas calculadas contra un `dev` con
> 242 commits de retraso, y el muestreo de 20 solo cogió **uno** de los 15
> mutantes que caen en `texto_comentarios.py` —que murió—, así que aquella
> campaña no dice casi nada sobre el código de esta feature.
> *Corregido el 2026-09-15, tras el review*: antes decia «no cogió ninguno».
>
> **PRUEBA DE CONTROL del cero de `build_compras_step.py`** (cálculo puro,
> `harness.mutacion.generar_mutantes`): sobre las **42 líneas que F-080 cambia
> ahí** el motor genera **0 mutantes**, y sobre el **fichero entero**, **12**.
> Es decir: el motor sabe mutar ese fichero; el cero viene del **alcance**, no
> de una avería. Lo que F-080 le añade es una tupla declarativa de `_SubStep`
> —solo cadenas— y este motor no muta cadenas. Esos 12 del fichero entero SÍ
> entran en esta campaña, y los 12 mueren.

### 1. `etl_sigrid/domain/texto_comentarios.py:103` [logico]

- Original: `if casado is None or fecha is None:`
- Mutado:   `if casado is None and fecha is None:`

#### Análisis

> **Por qué ningún test lo cazaba**: los dos operadores solo se distinguen
> cuando `casado` y `fecha` NO son las dos None a la vez. Una de las dos
> combinaciones es **inalcanzable** —si `casado` es None, la línea de arriba ya
> deja `fecha` a None—, así que todo se juega en la otra: **el sello casa con
> el patrón y su fecha no existe en el calendario** (`31/02/2026`). Con `or`,
> el sello no cuenta como reconocido (R25); con `and`, el bloque se publicaría
> con `sello_reconocido = True`, `fecha = NULL` y la hora y el usuario
> rellenos. `tests/test_f080_texto.py` no tenía ni una fixture con una fecha
> imposible: el caso estaba probado **en el SQL**
> (`test_f080_r25_una_fecha_imposible_no_cuenta_como_sello`, sobre el texto del
> fichero) y **no en el oráculo**, que es justo lo que esta campaña sirve para
> encontrar.
> **Decisión**: **hueco real, y es de F-080, así que se tapa aquí**. Se añade
> `test_f080_r25_una_fecha_que_no_existe_no_cuenta_como_sello`, parametrizado
> con `31/02`, `31/04`, `30/02` y `29/02` de 2026, que afirma
> `sello_reconocido is False`, la autoría a None y el cuerpo igual al bloque
> entero. **Comprobado que mata al mutante**: aplicándolo en una copia aislada
> —nunca en el árbol— `pytest tests/test_f080_texto.py` pasa de `29 passed` a
> `4 failed, 25 passed`, con
> `assert True is False ... sello_reconocido=True` y `fecha=None` en la traza.
> No se ha quitado ninguna guarda para matarlo (RM6 no aplica): se ha añadido
> un test.

## Después de tapar el hueco

El test nuevo entra en el commit `F-080 T25 (2/2)`, **posterior al SHA
`2ff8bab` con el que se midió esta campaña**. No se ha relanzado la campaña
entera —54 minutos— porque lo que había que demostrar es que ese mutante muere,
y eso está demostrado arriba mutante en mano. Con el test dentro, el recuento
que un reviewer debe esperar al repetirla es **27 generados, 27 evaluados, 27
muertos, 0 supervivientes**.
