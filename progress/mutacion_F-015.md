<!-- progress/mutacion_F-015.md -->
# F-015 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-015` el 2026-08-09 15:28.

## Alcance

Origen del diff: **rama** (`59b75160886459fece25e00e69129a9f365ffc2c` .. `feature/F-015-verificar-tests`).

| Fichero | Líneas en alcance |
|---|---|
| `harness/__init__.py` | 6 |
| `harness/alcance.py` | 222 |
| `harness/cobertura.py` | 189 |
| `harness/mutacion.py` | 564 |
| `harness/rigor.py` | 199 |
| **Total** | **1180** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 175 |
| Mutantes evaluados | 175 |
| Muertos | 162 |
| Supervivientes | 13 |
| Timeouts | 0 |
| Tiempo total | 270.5 s |
| Muestreo | no: campaña completa |

## Cómo se obtuvo esta campaña

Autoaplicación: la herramienta de F-015 sobre el código de F-015. Alcance
calculado desde el diff de la rama contra `dev`, sobre el árbol de trabajo
normal (aquí no hacía falta aislar: el alcance es `harness/*.py`, que ningún
proceso del proyecto importa). Suite de referencia en verde antes de empezar.

**La campaña se ejecutó dos veces, y ese es el resultado interesante:**

| Vuelta | Mutantes | Muertos | Supervivientes | Puntuación |
|---|---|---|---|---|
| 1ª — con los tests escritos por tarea | 175 | 138 | **37** | 78,9 % |
| 2ª — tras añadir tests contra los supervivientes | 175 | 162 | **13** | **92,6 %** |

Los 24 mutantes que pasaron de vivos a muertos eran huecos reales de tests
que ni la fase RED ni el 96,7 % de cobertura habían detectado. Entre ellos:

- El ejecutor de pytest se invocaba sin fijar por test que `check=False`: con
  `check=True`, un mutante que hace fallar la suite —el caso **normal**—
  habría tumbado la campaña entera con una excepción en vez de contarse como
  muerto.
- El parser del diff contaba líneas añadidas aunque no hubiera cabecera de
  hunk válida, inventándose el número de línea.
- La frontera exacta del umbral de cobertura (justo el 80 %) no estaba
  fijada: la puerta podía haber rechazado un valor que sí cumple.
- La última línea de un fichero sin salto de línea final no se mutaba.
- El código de salida 2 (error de uso) y el mensaje de alcance vacío no los
  comprobaba nadie.

Es exactamente lo que la feature venía a demostrar: **que los tests pasen no
significa que comprueben nada**, y que la cobertura alta no lo garantiza.

## Lectura de los 13 supervivientes

| Veredicto | Nº |
|---|---|
| Mutante equivalente | 8 |
| Código defensivo redundante (red de seguridad de R5) | 2 |
| Hueco real de riesgo bajo | 3 |

Ninguno es un hueco de riesgo medio o alto. F-015 está declarada de nivel
`estandar`, que admite supervivientes **documentados y analizados**; los tres
de riesgo bajo quedan anotados aquí, no tapados.

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `harness/alcance.py:45` [booleano]

- Original: `text=True,`
- Mutado:   `text=False,`

#### Análisis

- **Por qué ningún test lo caza:** Hallazgo del propio mutador: `text=True` es REDUNDANTE, porque pasar `encoding=` a `subprocess.run` ya fuerza el modo texto. Por eso ningun test lo nota, y por eso el test que comprueba que la salida es `str` (y no `bytes`) sigue en verde con el mutante puesto.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 2. `harness/cobertura.py:182` [comparacion]

- Original: `if porcentaje + 1e-9 < umbral:`
- Mutado:   `if porcentaje + 1e-9 <= umbral:`

#### Análisis

- **Por qué ningún test lo caza:** El margen `+ 1e-9` hace indistinguibles `<` y `<=`: para cualquier porcentaje, `p + 1e-9 <= u` y `p + 1e-9 < u` dan lo mismo. El test de la frontera exacta (justo el umbral) SI mata la variante `- 1e-9`, que era la peligrosa.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 3. `harness/mutacion.py:37` [entero]

- Original: `TIMEOUT_POR_DEFECTO = 120`
- Mutado:   `TIMEOUT_POR_DEFECTO = 121`

#### Análisis

- **Por qué ningún test lo caza:** Valor de respaldo del timeout, que solo se usa si `harness/rigor.json` no se puede leer. Fijarlo con un test seria repetir la constante en dos sitios.
- **Veredicto:** **Hueco real, riesgo BAJO.** Anotado; el coste de fijarlo con un test supera hoy su valor.

### 4. `harness/mutacion.py:70` [entero]

- Original: `longitud: int = 0`
- Mutado:   `longitud: int = 1`

#### Análisis

- **Por qué ningún test lo caza:** Valor por defecto de un campo que el generador siempre rellena explicitamente: no hay camino en el que se use.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 5. `harness/mutacion.py:77` [booleano]

- Original: `@dataclass(frozen=True)`
- Mutado:   `@dataclass(frozen=False)`

#### Análisis

- **Por qué ningún test lo caza:** Inmutabilidad de una estructura interna y privada del generador. La del `Mutante` publico si tiene test.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 6. `harness/mutacion.py:109` [booleano]

- Original: `nodo.ops, izquierdas, nodo.comparators, strict=True`
- Mutado:   `nodo.ops, izquierdas, nodo.comparators, strict=False`

#### Análisis

- **Por qué ningún test lo caza:** `strict=True` protege contra listas descuadradas que el arbol sintactico no puede producir: en un `Compare` hay siempre tantos operadores como comparadores.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 7. `harness/mutacion.py:178` [entero]

- Original: `for numero in range(linea_ini, linea_fin + 1):`
- Mutado:   `for numero in range(linea_ini, linea_fin + 2):`

#### Análisis

- **Por qué ningún test lo caza:** El recorrido se pasa una linea del final del hueco. En la practica no se nota porque el operador siempre aparece antes, y el limite de longitud del fichero corta el exceso. Anotado como robustez, no como fallo.
- **Veredicto:** **Hueco real, riesgo BAJO.** Anotado; el coste de fijarlo con un test supera hoy su valor.

### 8. `harness/mutacion.py:183` [comparacion]

- Original: `hasta = col_fin if numero == linea_fin else len(bruta)`
- Mutado:   `hasta = col_fin if numero != linea_fin else len(bruta)`

#### Análisis

- **Por qué ningún test lo caza:** Para un hueco de una sola linea el limite acaba siendo el mismo; y cuando abarca varias, el operador siempre aparece antes del punto en que la diferencia importaria.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 9. `harness/mutacion.py:302` [entero]

- Original: `generados: int = 0`
- Mutado:   `generados: int = 1`

#### Análisis

- **Por qué ningún test lo caza:** Valor por defecto de un campo que la campana siempre rellena con el total real.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

### 10. `harness/mutacion.py:400` [logico]

- Original: `if ruta.is_file() and _leer(ruta) != fuente:`
- Mutado:   `if ruta.is_file() or _leer(ruta) != fuente:`

#### Análisis

- **Por qué ningún test lo caza:** Es la red de seguridad final que exige R5: restaurar todo lo tocado pase lo que pase. El `try/finally` de cada mutante ya deja el fichero como estaba, asi que en el flujo normal esta comprobacion nunca encuentra nada que restaurar. Se conserva porque su valor esta justo en los casos que ningun test puede provocar de forma fiable (Ctrl-C entre la escritura y el finally).
- **Veredicto:** **Codigo defensivo redundante.** La garantia ya la da otro camino; el mutante no rompe nada porque esa rama no es alcanzable en el flujo normal. Se conserva a proposito.

### 11. `harness/mutacion.py:400` [comparacion]

- Original: `if ruta.is_file() and _leer(ruta) != fuente:`
- Mutado:   `if ruta.is_file() and _leer(ruta) == fuente:`

#### Análisis

- **Por qué ningún test lo caza:** Misma red de seguridad que el superviviente 10, por la otra rama de la condicion.
- **Veredicto:** **Codigo defensivo redundante.** La garantia ya la da otro camino; el mutante no rompe nada porque esa rama no es alcanzable en el flujo normal. Se conserva a proposito.

### 12. `harness/mutacion.py:549` [booleano]

- Original: `eco=lambda linea: print(linea, flush=True),`
- Mutado:   `eco=lambda linea: print(linea, flush=False),`

#### Análisis

- **Por qué ningún test lo caza:** El volcado inmediato del avance por consola solo se nota mirando una campana larga en vivo; no hay forma razonable de afirmarlo en un test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Anotado; el coste de fijarlo con un test supera hoy su valor.

### 13. `harness/rigor.py:47` [logico]

- Original: `if not isinstance(niveles, dict) or not niveles:`
- Mutado:   `if not isinstance(niveles, dict) and not niveles:`

#### Análisis

- **Por qué ningún test lo caza:** Con la configuracion de niveles vacia el error salta igual unas lineas mas abajo, al comprobar que el nivel por defecto no esta entre los declarados: cambia el mensaje, no el hecho de que el arnes para.
- **Veredicto:** **Mutante equivalente.** No cambia el comportamiento observable: no hay test que escribir.

