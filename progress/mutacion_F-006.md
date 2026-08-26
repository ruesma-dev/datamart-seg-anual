<!-- progress/mutacion_F-006.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-26 17:38.

> **Los 52 análisis de supervivientes están COMPLETADOS** (2026-08-27), y el
> criterio con el que se completaron es este, dicho aquí para que no haya que
> deducirlo: **el análisis de cada superviviente se hizo cuando se resolvió**, y
> vive con su traza de fase RED en `progress/impl_F-006_detalle.md`. Este
> fichero lo **genera la herramienta**; copiar aquí el razonamiento crearía dos
> versiones del mismo texto que divergen a la primera corrección, que es
> exactamente el defecto que ya quemó dos veces a esta feature. Así que cada
> sección lleva su **veredicto** y el **puntero exacto** (`L####`) a dónde vive
> su análisis y la traza que lo demuestra.
>
> **Resultado global: 52 de 52 resueltos — 49 muertos por tests nuevos** (ni una
> línea de producción tocada) **y 3 equivalentes**, con su demostración y la
> aprobación por escrito del humano del 2026-08-26. Reparto: **20** de
> `frozen`/`slots` (L5355), **11** de constantes (L5463), **16** de lógica y
> mensajes (L5136), **2** rezagados del reparto (L5626) y los **3**
> equivalentes (L5576).

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 |
| `etl_sigrid/domain/diccionario.py` | 1089 |
| `etl_sigrid/domain/inventario.py` | 288 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 468 |
| `etl_sigrid/infrastructure/postgres/catalogo.py` | 166 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 332 |
| `etl_sigrid/infrastructure/postgres/relaciones_sql.py` | 319 |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | 274 |
| **Total** | **3126** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 256 |
| Mutantes evaluados | 256 |
| Muertos | 204 |
| Supervivientes | 52 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 8368.3 s |
| SHA de HEAD medido | `99e23356a69a1bf79ac803a25fdf5a4f53393bf4` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_0` | 485.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_1` | 479.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_2` | 483.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_3` | 462.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_4` | 467.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_5` | 469.0 |
| Media por mutante evaluado (s) | 32.7 |
| Timeout efectivo por mutante (s) | 972 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 6 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/diccionario.py:200` [entero]

- Original: `"descripcion": 40,`
- Mutado:   `"descripcion": 41,`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `MINIMOS_FIJADOS` solo tenía 2 de las 5 entradas de `MINIMOS_TEXTO`, y este mínimo no estaba entre ellas.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_constantes_de_contrato.py` y la ampliación de `tests/test_f006_supervivientes.py`: `MINIMOS_FIJADOS` pasa a las **5** con `set(MINIMOS_FIJADOS) == set(MINIMOS_TEXTO)` exigido —un mínimo nuevo entra ahí o rompe la suite— más el **borde**: 40 caracteres valen y 39 no.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 2. `etl_sigrid/domain/diccionario.py:202` [entero]

- Original: `"motivo_no_consumo": 30,`
- Mutado:   `"motivo_no_consumo": 31,`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** igual que el mínimo de `descripcion`, este no estaba entre las 2 entradas que `MINIMOS_FIJADOS` cubría.
> **Decisión: MUERTO por test nuevo** — mismo mecanismo, sobre una ficha con `consumo_recomendado: false`, que es la puerta trasera que R3 cierra: rebajar este mínimo es la forma silenciosa de esquivar la cobertura de columnas. Con su borde: 30 caracteres valen y 29 no.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 3. `etl_sigrid/domain/diccionario.py:237` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 4. `etl_sigrid/domain/diccionario.py:253` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 5. `etl_sigrid/domain/diccionario.py:268` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 6. `etl_sigrid/domain/diccionario.py:299` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 7. `etl_sigrid/domain/diccionario.py:299` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 8. `etl_sigrid/domain/diccionario.py:314` [entero]

- Original: `orden: int = 0`
- Mutado:   `orden: int = 1`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** el defecto del campo `orden` se usaba al ordenar las reglas, pero ningún test fijaba cuál era.
> **Decisión: MUERTO por test nuevo** — una regla **sin** `orden` tiene que servirse ANTES que una con `orden: 1`. Los códigos del caso van al revés del alfabeto a propósito: si el defecto empatara en 1, el desempate alfabético cambiaría en silencio la prioridad con la que el agente lee las reglas duras.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 9. `etl_sigrid/domain/diccionario.py:317` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 10. `etl_sigrid/domain/diccionario.py:317` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 11. `etl_sigrid/domain/diccionario.py:341` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 12. `etl_sigrid/domain/diccionario.py:341` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 13. `etl_sigrid/domain/diccionario.py:774` [not]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if ficha.clave_negocio and not ficha.columnas:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** la guarda que **aplaza** el veredicto de fan-out solo se ejercitaba desde un cuadrante; con los otros tres sin probar, ni cambiar el `and` ni quitar un `not` rompía nada.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_logica.py`, un parametrizado con los **cuatro** cuadrantes (con/sin `clave_negocio` × con/sin `columnas`) ejercitado **a través de `validar`** y no de la función privada: lo observable es que el veredicto de fan-out se aplaza o se emite. Es donde estaba el hueco más peligroso: de esta guarda depende la detección de fan-out que dejó pasar F-042.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 14. `etl_sigrid/domain/diccionario.py:774` [logico]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if not ficha.clave_negocio or not ficha.columnas:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** la guarda que **aplaza** el veredicto de fan-out solo se ejercitaba desde un cuadrante; con los otros tres sin probar, ni cambiar el `and` ni quitar un `not` rompía nada.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_logica.py`, un parametrizado con los **cuatro** cuadrantes (con/sin `clave_negocio` × con/sin `columnas`) ejercitado **a través de `validar`** y no de la función privada: lo observable es que el veredicto de fan-out se aplaza o se emite. Es donde estaba el hueco más peligroso: de esta guarda depende la detección de fan-out que dejó pasar F-042.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 15. `etl_sigrid/domain/diccionario.py:774` [not]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if not ficha.clave_negocio and ficha.columnas:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** la guarda que **aplaza** el veredicto de fan-out solo se ejercitaba desde un cuadrante; con los otros tres sin probar, ni cambiar el `and` ni quitar un `not` rompía nada.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_logica.py`, un parametrizado con los **cuatro** cuadrantes (con/sin `clave_negocio` × con/sin `columnas`) ejercitado **a través de `validar`** y no de la función privada: lo observable es que el veredicto de fan-out se aplaza o se emite. Es donde estaba el hueco más peligroso: de esta guarda depende la detección de fan-out que dejó pasar F-042.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 16. `etl_sigrid/domain/inventario.py:69` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 17. `etl_sigrid/domain/inventario.py:69` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 18. `etl_sigrid/domain/inventario.py:146` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 19. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:50` [entero]

- Original: `| {f"com{i}" for i in range(1, 10)}`
- Mutado:   `| {f"com{i}" for i in range(2, 10)}`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `tests/test_f006_nombres_fichero.py` llevaba su **propia copia a mano** de `DISPOSITIVOS_RESERVADOS`, así que cambiar el conjunto del cargador no rompía ese fichero: un test que lee la constante se mueve con ella.
> **Decisión: MUERTO por test nuevo** — por el **borde de abajo**: `nombre_de_fichero("com1") == "com1_.yaml"`. MS-DOS numeró los dispositivos desde el **uno**.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 20. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:50` [entero]

- Original: `| {f"com{i}" for i in range(1, 10)}`
- Mutado:   `| {f"com{i}" for i in range(1, 11)}`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `tests/test_f006_nombres_fichero.py` llevaba su **propia copia a mano** de `DISPOSITIVOS_RESERVADOS`, así que cambiar el conjunto del cargador no rompía ese fichero: un test que lee la constante se mueve con ella.
> **Decisión: MUERTO por test nuevo** — por el **borde de arriba**: `nombre_de_fichero("com10") == "com10.yaml"`, la familia acaba en el **nueve**. Escapar de más tampoco es inocuo: el cargador exige que el nombre del fichero case con el esquema, y `com10_.yaml` no casaría con `com10`.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 21. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:51` [entero]

- Original: `| {f"lpt{i}" for i in range(1, 10)}`
- Mutado:   `| {f"lpt{i}" for i in range(2, 10)}`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `tests/test_f006_nombres_fichero.py` llevaba su **propia copia a mano** de `DISPOSITIVOS_RESERVADOS`, así que cambiar el conjunto del cargador no rompía ese fichero: un test que lee la constante se mueve con ella.
> **Decisión: MUERTO por test nuevo** — borde de abajo del otro dispositivo: `nombre_de_fichero("lpt1") == "lpt1_.yaml"`.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 22. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:51` [entero]

- Original: `| {f"lpt{i}" for i in range(1, 10)}`
- Mutado:   `| {f"lpt{i}" for i in range(1, 11)}`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `tests/test_f006_nombres_fichero.py` llevaba su **propia copia a mano** de `DISPOSITIVOS_RESERVADOS`, así que cambiar el conjunto del cargador no rompía ese fichero: un test que lee la constante se mueve con ella.
> **Decisión: MUERTO por test nuevo** — borde de arriba del otro dispositivo: `nombre_de_fichero("lpt10") == "lpt10.yaml"`.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 23. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:245` [logico]

- Original: `problema = getattr(exc, "problem", None) or "YAML mal formado"`
- Mutado:   `problema = getattr(exc, "problem", None) and "YAML mal formado"`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** bastaba con el texto de reserva. Ningún test comprobaba que el detalle real del parser (`exc.problem`) llegue al mensaje, así que un `and` que lo tira y deja `None` pasaba inadvertido.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_mensajes.py`: se exige el `problem` real del parser dentro del mensaje, y el texto de reserva solo cuando el parser no da ninguno.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 24. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [aritmetico]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line - 1}, columna {marca.column + 1}: {problema}"`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests comprobaban que el mensaje traía dos números, no que fueran los del editor (1-based): ninguno volvía al texto original a verificar dónde caen.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_mensajes.py` hace el **viaje de vuelta**: extrae los dos números con una regex, les resta uno, indexa el texto original y exige que caigan sobre el carácter exacto que el parser rechazó. Con dos YAML rotos en sitios distintos (línea 3 columna 13; línea 6 columna 6) para que ningún número acierte por casualidad.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 25. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [entero]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 2}, columna {marca.column + 1}: {problema}"`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests comprobaban que el mensaje traía dos números, no que fueran los del editor (1-based): ninguno volvía al texto original a verificar dónde caen.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_mensajes.py` hace el **viaje de vuelta**: extrae los dos números con una regex, les resta uno, indexa el texto original y exige que caigan sobre el carácter exacto que el parser rechazó. Con dos YAML rotos en sitios distintos (línea 3 columna 13; línea 6 columna 6) para que ningún número acierte por casualidad.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 26. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [aritmetico]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column - 1}: {problema}"`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests comprobaban que el mensaje traía dos números, no que fueran los del editor (1-based): ninguno volvía al texto original a verificar dónde caen.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_mensajes.py` hace el **viaje de vuelta**: extrae los dos números con una regex, les resta uno, indexa el texto original y exige que caigan sobre el carácter exacto que el parser rechazó. Con dos YAML rotos en sitios distintos (línea 3 columna 13; línea 6 columna 6) para que ningún número acierte por casualidad.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 27. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [entero]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 2}: {problema}"`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests comprobaban que el mensaje traía dos números, no que fueran los del editor (1-based): ninguno volvía al texto original a verificar dónde caen.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_supervivientes_mensajes.py` hace el **viaje de vuelta**: extrae los dos números con una regex, les resta uno, indexa el texto original y exige que caigan sobre el carácter exacto que el parser rechazó. Con dos YAML rotos en sitios distintos (línea 3 columna 13; línea 6 columna 6) para que ningún número acierte por casualidad.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 28. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:361` [comparacion]

- Original: `grano=cuerpo.get("grano") if cuerpo.get("grano") is None else _texto(cuerpo.get("grano")),`
- Mutado:   `grano=cuerpo.get("grano") if cuerpo.get("grano") is not None else _texto(cuerpo.get("grano")),`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** el condicional tiene las ramas escritas al revés de como se leen, así que el mutante **intercambia las dos** sin romper ningún tipo; con un `grano` ya escrito como texto las dos son indistinguibles. Se quedó fuera del reparto del líder por descuido, y la reevaluación **en serie** lo confirmó vivo: no es equivalente.
> **Decisión: MUERTO por test nuevo** — sección **13** de `tests/test_f006_supervivientes_logica.py`, con las dos ramas fijadas: presente → normalizado (entrada `grano: 2024`, un escalar donde el crudo `2024` y el normalizado `"2024"` **se distinguen**) y ausente → `None` y no `""`, que es la única forma de decir «esta ficha no declara grano».
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5638**.

### 29. `etl_sigrid/infrastructure/postgres/catalogo.py:35` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 30. `etl_sigrid/infrastructure/postgres/catalogo.py:35` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 31. `etl_sigrid/infrastructure/postgres/catalogo.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 32. `etl_sigrid/infrastructure/postgres/catalogo.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 33. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:142` [booleano]

- Original: `ensure_ascii=False,`
- Mutado:   `ensure_ascii=True,`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo caza:** `ensure_ascii` solo cambia cómo se escapan los acentos en el JSON que se publica. La columna de destino es **JSONB** en el DDL y Postgres decodifica los escapes al parsear, así que el valor almacenado y el que recupera el MCP son **idénticos** —comprobado contra la base real: Postgres los considera el mismo `jsonb`—. El único `sha256` de la publicación va sobre los bytes del YAML, no sobre este JSON.
> **Decisión: MUTANTE EQUIVALENTE**, demostrado y **aprobado por el humano el 2026-08-26**; premisas reverificadas por el reviewer contra el árbol en la 20ª pasada. Un test que fijara la cadena serializada ataría la suite a un detalle que no altera ningún comportamiento observable: `ensure_ascii=False` está puesto para que lo publicado sea legible **al depurar**, no por corrección.
> **Demostración:** `progress/impl_F-006_detalle.md` **L5599**.

### 34. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:160` [logico]

- Original: `ficha.motivo_no_consumo or None,`
- Mutado:   `ficha.motivo_no_consumo and None,`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** solo se ejercitaba la rama con texto presente, donde `or` y `and` no se distinguen a simple vista en el resultado publicado.
> **Decisión: MUERTO por test nuevo** — se cubren las **dos** ramas: con texto, el valor tiene que llegar entero a `_meta` (con `and` viaja `None`); vacío, tiene que publicarse `NULL` y no cadena vacía (con `and` viaja `""`). En SQL no es lo mismo: `WHERE motivo_no_consumo IS NULL` encuentra lo no documentado y `= ''` no.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 35. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:162` [logico]

- Original: `ficha.grano or None,`
- Mutado:   `ficha.grano and None,`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** mismo hueco que en `motivo_no_consumo`: solo se probaba la rama con texto presente.
> **Decisión: MUERTO por test nuevo** — las dos ramas de `grano`: con texto llega entero a `_meta`; vacío se publica `NULL` y no cadena vacía. `WHERE grano IS NULL` es la consulta con la que se encuentra lo que no está documentado.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 36. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:202` [entero]

- Original: `return round(100.0 * con_significado / len(de_consumo), 2)`
- Mutado:   `return round(100.0 * con_significado / len(de_consumo), 3)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** cualquier reparto redondo —la mitad, un cuarto— da el mismo número con dos decimales y con tres, y era lo único que se probaba.
> **Decisión: MUERTO por test nuevo** — por **un tercio**: 1 de 3 columnas documentadas da `33.33` a dos decimales y `33.333` a tres.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 37. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:239` [entero]

- Original: `"version": fila[1],`
- Mutado:   `"version": fila[2],`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `resumen_publicacion` se comprobaba con una tupla en la que unos índices valían por otros, así que un cruce de posiciones seguía dando el mismo diccionario.
> **Decisión: MUERTO por test nuevo** — tupla en la que **ningún** índice vale por otro (`"version-en-el-1"`, `"hash-en-el-2"`, 50/60/70/80.5), de forma que se ve **cualquier** cruce y no solo el que sobrevivió; más un segundo test que la contrasta contra la fila que `fila_publicacion` produce de verdad, con 2 fichas / 3 reglas / 5 columnas —los tres recuentos distintos— para que el mapeo no pueda ser internamente coherente y estar leyendo posiciones que la fila real no tiene ahí.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 38. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:277` [booleano]

- Original: `json.dumps(valor, ensure_ascii=False, default=str),`
- Mutado:   `json.dumps(valor, ensure_ascii=True, default=str),`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo caza:** `ensure_ascii` solo cambia cómo se escapan los acentos en el JSON que se publica. La columna de destino es **JSONB** en el DDL y Postgres decodifica los escapes al parsear, así que el valor almacenado y el que recupera el MCP son **idénticos** —comprobado contra la base real: Postgres los considera el mismo `jsonb`—. El único `sha256` de la publicación va sobre los bytes del YAML, no sobre este JSON.
> **Decisión: MUTANTE EQUIVALENTE**, demostrado y **aprobado por el humano el 2026-08-26**; premisas reverificadas por el reviewer contra el árbol en la 20ª pasada. Un test que fijara la cadena serializada ataría la suite a un detalle que no altera ningún comportamiento observable: `ensure_ascii=False` está puesto para que lo publicado sea legible **al depurar**, no por corrección.
> **Demostración:** `progress/impl_F-006_detalle.md` **L5599**.

### 39. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:326` [comparacion]

- Original: `if bloque == "ejes":`
- Mutado:   `if bloque != "ejes":`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** el bloque `ejes` no tenía test de su plantilla propia; con la comparación invertida el volcado genérico seguía saliendo y nadie miraba con qué formato.
> **Decisión: MUERTO por test nuevo** — se exige que `ejes` se formatee con **su** plantilla y que se vuelque entero.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 40. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:329` [comparacion]

- Original: `if bloque == "esquemas":`
- Mutado:   `if bloque != "esquemas":`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** mismo hueco que en `ejes`: el bloque `esquemas` no tenía test de su plantilla propia.
> **Decisión: MUERTO por test nuevo** — se exige que `esquemas` se formatee con **su** plantilla y que se vuelque entero.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 41. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:72` [entero]

- Original: `TAMANO_MUESTRA = 500`
- Mutado:   `TAMANO_MUESTRA = 501`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** la constante se usaba al construir el SQL, pero nadie comprobaba su valor ni el literal que acaba en la consulta.
> **Decisión: MUERTO por test nuevo** — por el `LIMIT 500` que aparece en el SQL generado y por `consulta.muestra == 500`. La cota existe para no barrer tablas de decenas de millones de filas.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 42. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 43. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 44. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:278` [comparacion]

- Original: `if cobertura < UMBRAL_AVISO_COBERTURA:`
- Mutado:   `if cobertura <= UMBRAL_AVISO_COBERTURA:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** `<` y `<=` coinciden en todo el dominio salvo en el valor **exactamente igual al umbral**, y no había ningún caso con cobertura 0.5 justa. También se quedó fuera del reparto, y la reevaluación **en serie** lo confirmó vivo.
> **Decisión: MUERTO por test nuevo** — sección **14** de `tests/test_f006_supervivientes_logica.py`: un test frontera parametrizado con tres pares que dan la misma fracción exacta (`1/2`, `250/500`, `5/10`) y que **afirma primero** que `casan / muestreados == UMBRAL_AVISO_COBERTURA` —si el umbral se mueve, el test deja de mentir en vez de fijar un número a mano—, más el contrapunto por debajo (249 de 500 → AVISO), sin el cual un `interpretar_relacion` que no avisara nunca dejaría verde la frontera.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5688**.

### 45. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:282` [entero]

- Original: `f"{int(UMBRAL_AVISO_COBERTURA * 100)} % desde el que esto avisa. La "`
- Mutado:   `f"{int(UMBRAL_AVISO_COBERTURA * 101)} % desde el que esto avisa. La "`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo caza:** está dentro del texto del aviso de cobertura escasa, y `UMBRAL_AVISO_COBERTURA` vale **0.5**: `int(0.5 * 100) = int(0.5 * 101) = 50`. Sale **el mismo texto, byte a byte**; no hay entrada que distinga las dos versiones, así que no existe test capaz de matarlo.
> **Decisión: MUTANTE EQUIVALENTE**, demostrado y **aprobado por el humano el 2026-08-26**; **reverificado por el reviewer** en la 20ª pasada aplicándolo con el propio mutador sobre 11 casos (8 por la rama `AVISO`): salidas idénticas. Aviso para quien cambie el umbral: si deja de ser 0.5 **puede volverse matable** —con 0.55 serían 55 y 55.5→55—; recalcúlalo en vez de dar por buena esta ficha.
> **Demostración:** `progress/impl_F-006_detalle.md` **L5584**.

### 46. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:62` [entero]

- Original: `TIMEOUT_POR_CONSULTA_S = 30`
- Mutado:   `TIMEOUT_POR_CONSULTA_S = 31`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** ningún test miraba las sentencias previas que se emiten antes de la consulta.
> **Decisión: MUERTO por test nuevo** — por el literal emitido: `SET LOCAL statement_timeout = '30s'`, junto a `SET LOCAL transaction_read_only = on`. Esto corre contra un Postgres **compartido con `albaranes` y `partes` en producción**: el timeout no es cosmético.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 47. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:65` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 48. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:65` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** los tests construían instancias y leían sus campos, y eso funciona igual con `frozen=False` o con `slots=False`. Ninguna de las 38 dataclasses del paquete tenía guarda **de comportamiento** sobre la inmutabilidad; la 1ª campaña ya lo sacó en `Columna` y `Relacion`, se tapó con dos casos escritos a mano, y el defecto sobrevivió en las doce clases de al lado.
> **Decisión: MUERTO por test nuevo** — `tests/test_f006_dataclasses_inmutables.py`, un **barrido** que descubre las 38 dataclasses con `pkgutil.walk_packages` en vez de listarlas, y ejercita el comportamiento (`FrozenInstanceError` al reasignar un campo; `AttributeError` al añadir un atributo que no lo es), no la bandera del decorador.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5355** (19ª pasada, grupo 1), mutante a mutante en **L5417**.

### 49. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:133` [logico]

- Original: `if ficha.tipo == "funcion" or not ficha.clave_negocio:`
- Mutado:   `if ficha.tipo == "funcion" and not ficha.clave_negocio:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** no había caso separado de función y de ficha sin `clave_negocio`; con un solo caso, `or` y `and` dan el mismo veredicto.
> **Decisión: MUERTO por test nuevo** — los dos casos negativos por separado (sin clave de negocio no hay consulta; una función no genera consulta) **junto al positivo**: «no genera consulta» lo cumpliría también una puerta que no comprueba nada.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 50. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:173` [booleano]

- Original: `dicc: Diccionario, *, solo_consumo: bool = True`
- Mutado:   `dicc: Diccionario, *, solo_consumo: bool = False`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** todas las llamadas de los tests pasaban el argumento explícito, así que el valor por defecto no se ejercitaba nunca.
> **Decisión: MUERTO por test nuevo** — llamando **sin** el argumento: el objeto fuera de consumo se salta **y lo dice** (`fuera de la superficie de consumo (usa --todos)`). Y la otra mitad, para que el test no valga por casualidad: `solo_consumo=False` lo levanta, no lo invierte.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5463** (19ª pasada, grupo 2: la tabla de los once, constante a constante), mutante a mutante en **L5497**.

### 51. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:189` [logico]

- Original: `elif solo_consumo and not ficha.consumo_recomendado:`
- Mutado:   `elif solo_consumo or not ficha.consumo_recomendado:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** no se ejercitaban a la vez el objeto dentro y fuera de la superficie de consumo, que es lo único que distingue `and` de `or` aquí.
> **Decisión: MUERTO por test nuevo** — dentro de la superficie no se salta nada, y con `--todos` deja de haber saltos.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

### 52. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:189` [not]

- Original: `elif solo_consumo and not ficha.consumo_recomendado:`
- Mutado:   `elif solo_consumo and ficha.consumo_recomendado:`

#### Análisis (completado 2026-08-27)

> **Por qué ningún test lo cazaba:** mismo hueco de la línea de al lado: faltaba el par de casos que distingue quitar el `not`.
> **Decisión: MUERTO por test nuevo** — fuera de la superficie se salta **diciéndolo**, y dentro no se salta nada.
> **Análisis y traza de fase RED:** `progress/impl_F-006_detalle.md` **L5136** (anexo de los bloques A y B), tabla de verificación mutante a mutante en **L5196**; traza completa en `progress/mutacion_F-006_supervivientes_17.txt`.

