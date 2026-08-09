<!-- progress/mutacion_F-004.md -->
# F-004 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-004` el 2026-08-09 19:10.

## Alcance

Origen del diff: **rama** (`4741db17b8d82bc7faad094c1a66e9901fd625b9` .. `feature/F-004-etl-sin-dependencias-locales`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 34 |
| `etl_sigrid/application/steps/load_excel_aux_step.py` | 133 |
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | 215 |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | 145 |
| **Total** | **527** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 27 |
| Mutantes evaluados | 27 |
| Muertos | 25 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Tiempo total | 41.4 s |
| Muestreo | no: campaña completa |

**Puntuación de mutación: 25 / 27 = 92,6 %.**

## Cómo se obtuvo

- **Ejecutada sobre un `git worktree` aparte**, NO sobre el árbol vivo: el
  2026-08-09 hay una carga `run-all --full` corriendo contra Azure desde este
  mismo directorio, y la campaña escribe mutantes en disco sobre `etl_sigrid/`
  que ese proceso podría importar. Mismo motivo y mismo procedimiento que la
  línea base de F-005 (ver `progress/mutacion_F-005.md` § «Cómo se obtuvo»).
- **El worktree se crea CON RAMA, no en HEAD desacoplado**:

  ```bash
  git worktree add -b tmp/F-004-mutacion <ruta-temporal> HEAD
  cd <ruta-temporal> && python -m pytest -q          # suite base en verde
  # desde el repositorio principal:
  python -m harness.mutacion --feature F-004 --base dev \
      --rama feature/F-004-etl-sin-dependencias-locales --raiz <ruta-temporal>
  git worktree remove <ruta-temporal> && git branch -D tmp/F-004-mutacion
  ```

  Con `--detach`, `test_f015_r12_la_rama_actual_se_lee_de_git` falla (no hay
  rama que leer) y **la suite base sale en rojo**, con lo que TODO mutante se
  contaría como muerto y la medición no valdría nada. Queda anotado porque el
  informe de F-005 no lo dice y es una trampa silenciosa.
- **Suite de referencia verde antes de empezar**: 221 tests en 3,1 s en ese
  árbol, sin `.env`, sin red y sin BBDD.
- **Campaña completa, sin muestreo**: 27 mutantes en 41 s.

## Dos vueltas, y la segunda es el resultado interesante

| Vuelta | Mutantes | Muertos | Supervivientes | Puntuación |
|---|---|---|---|---|
| 1ª — con los tests escritos tarea a tarea | 27 | 21 | **6** | 77,8 % |
| 2ª — tras añadir tests contra los supervivientes | 27 | 25 | **2** | **92,6 %** |

Los cuatro mutantes que pasaron de vivos a muertos eran huecos reales que ni
la fase RED ni el 97,6 % de cobertura habían detectado:

1. **`load_workbook(..., read_only=True)` → `False`** y
2. **`data_only=True` → `False`**: ninguna aserción miraba los dos flags,
   porque hoy no cambian la salida del step (solo se listan los nombres de
   hoja). Pero son decisiones con consecuencias: `read_only` evita cargar un
   libro entero en la memoria contada de un contenedor, y `data_only` decide
   si el día que se lean celdas sale el valor calculado o el texto de la
   fórmula. Cazados con
   `test_f004_r11_el_libro_se_abre_en_solo_lectura_y_con_valores`.
3. **`@dataclass(frozen=True)` → `False`** y
4. **`slots=True` → `False`** en `AuxFileRef`: la referencia viaja del step al
   adaptador y nadie la puede reescribir por el camino; sin `__dict__`, un
   atributo mal escrito falla en el acto. Cazados con
   `test_f004_r2_la_referencia_es_inmutable_y_sin_diccionario`.

## Supervivientes (2), analizados

### 1. `etl_sigrid/infrastructure/excel/aux_file_source.py:81` [entero]

- Original: `return valor.split("?", 1)[0].split("#", 1)[0]`
- Mutado:   `return valor.split("?", 2)[0].split("#", 1)[0]`

**Por qué ningún test lo caza: es un mutante EQUIVALENTE, y no puede cazarlo
ninguno.** La función se queda con el elemento `[0]` del troceo, y el primer
elemento de `split(sep, n)` es idéntico para cualquier `n >= 1`: el separador
que importa es siempre el primero. `maxsplit=1` está puesto por eficiencia y
por decir «solo me interesa lo que va antes del `?`», no por corrección.

**Decisión: equivalente justificado, sin test nuevo.** Un test que lo cazara
tendría que afirmar el número de trozos intermedios que la función descarta,
es decir, congelar un detalle interno que nadie observa.

### 2. `etl_sigrid/infrastructure/excel/aux_file_source.py:81` [entero]

- Original: `return valor.split("?", 1)[0].split("#", 1)[0]`
- Mutado:   `return valor.split("?", 1)[0].split("#", 2)[0]`

**Mismo caso que el anterior**, sobre el fragmento (`#`) en vez de sobre la
query (`?`). Equivalente por la misma razón: se toma `[0]`.

**Decisión: equivalente justificado, sin test nuevo.**

Lo que sí está cazado en esa línea son las dos mutaciones que **cambian el
resultado**: `[0]` → `[1]` en los dos troceos murió en la primera vuelta, y es
justo la que filtraría el token SAS al mensaje de error (R6).
