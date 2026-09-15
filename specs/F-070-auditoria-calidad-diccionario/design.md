<!-- specs/F-070-auditoria-calidad-diccionario/design.md -->
# F-070 · Diseno tecnico

## 1. Los catorce criterios (el corazon de la feature)

C1-C10 son **lo que falta**; C11-C14, **lo que sobra**. Salen de lo que hay
escrito en `config/diccionario/`, no de un ideal, y cada uno lleva su fallo
real. El texto completo —con ejemplo bueno y malo— lo escribe el implementer en
`docs/CALIDAD_DICCIONARIO.md`; aqui va el esqueleto que no puede cambiar.

| Id | Que exige la ficha | Comprobacion | Gravedad |
|---|---|---|---|
| C1 | Identidad: que es y para que se usa, en negocio, sin repetir el nombre | Auto (palabras nuevas) + humana | menor / serio |
| C2 | Grano: «una fila es ...» explicito y coherente con `clave_negocio` | Auto + humana | grave |
| C3 | Unidad y signo de cada medida; que significa el negativo | Auto (`agregacion` sumable => `unidad`) | grave |
| C4 | Filtro obligatorio con su `WHERE` literal si consultar sin el miente | Auto (regla dura en ambito => marcador) | grave |
| C5 | Que NO contiene: el limite del objeto | Auto (marcador) + humana | serio |
| C6 | Enrutamiento: a que objeto ir para cada tipo de pregunta | Humana | serio |
| C7 | Union: cada relacion con su clave de JOIN completa y su cardinalidad | Auto (R5 de F-006) + humana | grave |
| C8 | Trampas propias, con su consecuencia numerica y su fecha | Humana | serio |
| C9 | Vocabulario: estados y codigos con sus `valores`; `nulo_significa` | Auto + humana | serio |
| C10 | Verdad: no contradice al DDL ni al dato | `check-diccionario` + `check-unicidad` | grave |
| **C11** | **Vigencia**: toda cifra de conducta con fecha y fuente; criterio de diseno etiquetado como tal | Auto (cifra sin fecha; SQL cambiado despues) + humana | serio / **grave** si ya no es cierto |
| **C12** | **Ejemplo respondible**: cada `ejemplos_preguntas` se responde con un `SELECT` que use solo columnas de la ficha | Humana, con procedimiento objetivo | serio |
| **C13** | **Una sola casa**: lo que vale para varios objetos vive en la entrada de esquema o en una regla dura, no copiado | Auto (n-gramas) + humana | menor, **grave** si las copias divergen |
| **C14** | **Sin redundantes**: dos objetos que responden lo mismo declaran cual manda; el superado baja `consumo_recomendado` y nombra sucesor | Humana | serio |

Evidencia medida sobre la version 16 el 2026-09-08, que la primera pasada va a
levantar: **28 medidas sumables sin `unidad`** (C3), **47 fichas de consumo sin
el limite del objeto** (C5), `compras.contratos` preguntando por contratos
«abiertos» sin publicar estado (C12), **1.289 n-gramas de doce palabras
repetidos en dos o mas fichas**, con el puntero a `sigrid_tablas.md` copiado en
las **56** de `raw` (C13), y **30 parrafos con cifras de conducta sin fecha de
medicion** de los 55 que citan cifras (C11).

## 2. La escala de gravedad

Se mide por **cuanto cambia una respuesta de la IA**, nunca por el estilo:
`grave` (otra cifra u otro objeto, y nada avisa) se corrige aqui y la puerta no
admite ninguno; `serio` (falta un limite, o va al objeto vecino) se corrige o se
declara en el trinquete; `menor` se anota y **no se corrige**.

Regla de corte, que es lo que evita las 800 observaciones inutiles: **todo
hallazgo que suba de `menor` lleva escrita la pregunta de negocio concreta que
se responde mal por su culpa** (R3). Sin esa frase, es `menor`.

## 3. Alcance: los 130 objetos, en tres niveles

La ficha de la feature dice 103 objetos y 798 columnas; eso era la version 12.
El censo del 2026-09-08 es **130 objetos y 822 columnas**, y crece: la auditoria
se aplica a lo que haya el dia que se ejecute y **el informe declara su censo**.

| Nivel | Que entra | Cuanto (v16) | Criterios | Detalle |
|---|---|---|---|---|
| A | `consumo_recomendado: true` | 47 objetos, 625 columnas | C1-C14 | columna a columna |
| B | `stg`, `aux` y demas no recomendados | 27 objetos, 197 columnas | C1, C2, C5, C6, C10, C11, C13 | objeto + columnas de clave y relacion |
| C | `raw` | 56 objetos, 0 columnas hoy | C1, C5, C6, C11, C13 | objeto |

Por que se pide menos a `raw` y no cero: la IA tiene que entender **que hay en
cada tabla** aunque no deba consultarla. Nivel C exige cuatro cosas por ficha:
que guarda en negocio, que NO es (copia literal de Sigrid, sin filtrar ni
deduplicar), **a que objeto de consumo ir** para preguntar por ello, y sus
columnas de union y de filtro. Lo que NO se exige es describir las columnas una
a una: son cientos de campos de Sigrid, ya documentados en
`azure-apps/sigrid_tablas.md`, y copiarlos aqui es justo el C13 que la feature
persigue —el puntero, hoy repetido 56 veces, pasa a la entrada del esquema.

## 4. Como se audita sin que el coste se dispare

1. **La maquina primero, gratis.** `auditar-diccionario` pasa C1, C3, C4, C5,
   C7, C9, C11 y C13 sobre los 130 objetos leyendo YAML y `git log`: sin red,
   sin base, decimas de segundo.
2. **El nivel acota el trabajo caro.** La revision humana es columna a columna
   solo en los 47 objetos de nivel A; B y C son un parrafo por objeto.
3. **Cuatro lotes de esquema**, cada uno un subagente con contexto acotado —el
   YAML, el DDL de su capa y `docs/CALIDAD_DICCIONARIO.md`—: L1 `compras` +
   `maestro` (correo de Compras), L2 `retenciones` + `cierre` (obra 0694), L3
   `mart` + `stg` + `_meta` + `aux`, L4 `raw` (56 fichas, solo nivel C).

Ningun lote reescribe el YAML: primero se audita entero y luego se corrige.

## 5. Ficheros a crear

- `etl_sigrid/domain/calidad_diccionario.py` — **domain**, funciones puras (sin
  YAML, sin SQL, sin red, sin git). Recibe el `Diccionario` ya construido:
  - `GRAVEDADES`, `NIVELES = ("A","B","C")` y `CRITERIOS`: `C1..C14 -> (titulo,
    gravedad_por_defecto, niveles)`. Vocabulario cerrado, como `AGREGACIONES`.
  - `Hallazgo(esquema, objeto, columna, criterio, gravedad, detalle, pregunta)`,
    `frozen=True, slots=True`.
  - `nivel_de(ficha) -> str` — A si `consumo_recomendado`, C si `raw`, B si no.
  - `auditar(dicc, *, niveles=("A","B","C"), cambios_sql=None) -> list[Hallazgo]`
    — determinista y ordenada, como `validar`. `cambios_sql` es el mapa
    `paso_etl -> fecha del ultimo cambio` que **inyecta la infraestructura**: el
    dominio no llama a git (R8 de las convenciones).
  - `repeticiones(dicc, n=12) -> list[tuple[str, tuple[str, ...]]]` — n-gramas
    compartidos, base de C13; y `divergen(copias) -> bool` para el caso grave.
  - `cifras_sin_fecha(ficha) -> list[Hallazgo]` — base de C11.
  - `presupuesto(dicc) -> dict` — caracteres por ficha y total (R21).
  - `viola_trinquete(hallazgos, pendientes) -> list[str]`.
- `etl_sigrid/infrastructure/diccionario/cambios_sql.py` — lee la fecha del
  ultimo cambio de cada carpeta `sql/<capa>/` con `git log -1 --format=%cs`.
  Es infraestructura porque toca el sistema de ficheros; si git no responde,
  devuelve vacio y C11 degrada a su mitad automatica sin romper.
- `docs/CALIDAD_DICCIONARIO.md`, `docs/PRUEBAS_MCP.md`,
  `config/calidad_pendientes.yaml` (trinquete al estilo de
  `config/objetos_pendientes.yaml`), `progress/auditoria_F-070.md`.
- `tests/test_f070_criterios.py`, `tests/test_f070_auditoria.py`,
  `tests/test_f070_sobra.py`, `tests/test_f070_trinquete.py`,
  `tests/test_f070_bateria.py`, `tests/test_f070_docs.py` — nombres trazables
  `test_f070_rN_...`, ninguno toca red ni BBDD.

## 6. Ficheros a modificar

- `main.py` — comando `auditar-diccionario` (click), con la forma de
  `check-unicidad`: carga con `cargar_diccionario(DIR_DICCIONARIO)`, inyecta
  `cambios_sql`, llama al dominio, imprime por gravedad separando falta y sobra,
  y `SystemExit(1)` con `grave`. Opciones `--esquema`, `--gravedad`, `--nivel`,
  `--solo-consumo`. **No abre conexion nunca.**
- `harness/init.sh` — seccion 9, hoy vacia a proposito: la puerta (censo entero,
  gravedad `grave`) y el trinquete, degradando con aviso si no hay Python.
- `config/diccionario/*.yaml` — correcciones, el limite del objeto en las 47
  fichas de consumo, el nivel C de las 56 de `raw`, el puntero repetido movido a
  la entrada de esquema, y `version: 17` con su nota de cabecera.
- `config/diccionario/00_global.yaml` — `preguntas_aceptacion` crece con las
  cuatro del correo de Compras, la de la obra 0694 (34.523,22 EUR en 61
  efectos) y la de vigencia de la ventana de F-025.
- `docs/CONVENTIONS.md` (apunta a `docs/CALIDAD_DICCIONARIO.md`) y
  `CHECKPOINTS.md` (el reviewer aplica los criterios a las fichas que toque).

## 7. Ficheros que NO se tocan

- `etl_sigrid/domain/diccionario.py`: `validar()` es la puerta de PUBLICACION.
  Endurecerla con estos criterios dejaria el diccionario sin poder publicarse
  —y con el, la nocturna— hasta reescribir 47 fichas. La calidad va en modulo y
  comando aparte, con su propia severidad.
- `publicar_diccionario_step.py` y el DDL de `_meta`: **no se anaden claves
  nuevas al esquema de la ficha** (decision D1).
- `etl_sigrid/infrastructure/postgres/sql/**`: esta feature no cambia ni un
  objeto del datamart. `harness/features.json`, `.env`, `infra/**`.

## 8. Decisiones y alternativas descartadas

**D1. El limite, el filtro y la vigencia van en prosa con marcador, no como
claves YAML nuevas.** Anadir `no_contiene:` obliga a tocar dominio, cargador,
publicador, el DDL de `_meta.diccionario` y el contrato que lee `mcp-bbdd`: un
cambio de frontera entre proyectos para algo que la `descripcion` ya publica tal
cual. Con marcadores literales —`**NO contiene:**`, `**Filtro obligatorio:**`,
`**Medido el <fecha>, fuente <x>:**`— el texto viaja hoy al MCP sin tocar nada y
sigue siendo comprobable por maquina.

**D2. C11 se detecta por dos senales debiles, no por una fuerte.** No hay forma
automatica de saber si una frase sigue siendo verdad. Si hay dos proxies
baratos: cifra de conducta sin fecha (30 casos hoy) y SQL del objeto cambiado
despues de la fecha que la ficha cita. Los dos producen `serio` —«revisa esto»—
y solo el humano lo sube a `grave`. El caso de la version 16 los habria disparado
los dos: la cifra no tenia medicion detras y el build de F-025 acababa de cambiar.

**D3. C13 no prohibe repetir: exige una sola casa y copias identicas.** El MCP
sirve la ficha suelta, asi que algo de repeticion es util. Lo que no se sostiene
es el mismo parrafo en 56 fichas —eso es una entrada de esquema o una regla
dura, que el validador ya adjunta por ambito (R12 de F-006)— ni dos copias que
digan cosas distintas, que es un `grave` porque una de las dos miente.

**D4. C12 se comprueba escribiendo el `SELECT`.** Es lo que convierte un juicio
de estilo en una prueba: si el ejemplo no se puede responder con las columnas de
la ficha, sobra el ejemplo o falta la columna. Cuesta un minuto por ejemplo.

**D5. Trinquete en vez de umbral.** Un porcentaje de calidad invita a maquillar;
una lista nominal que solo baja, no. Mismo mecanismo que `pendientes`.

**D6. Quien responde la bateria no puede tener el repositorio delante**, y quien
juzga no es quien escribio la ficha: el veredicto se contrasta contra la
`respuesta_correcta` escrita ANTES (R25, R26). Las 18 preguntas P1-P18 ya existen
en `00_global.yaml` y no se publican a `_meta` a proposito.

## 9. Riesgos

- **La primera pasada saldra en rojo con decenas de graves.** La puerta de
  `init.sh` se activa al final (T13), cuando ya estan corregidos, para no
  bloquear a otras features a mitad de camino.
- **Publicar en `_meta` es una escritura contra Azure en produccion**: la lanza
  el humano, nunca un agente. Tarea MANUAL.
- **La nocturna puede estar corriendo**: la bateria se pasa fuera de esa ventana
  y solo con consultas agregadas.
- **Reescribir fichas puede introducir afirmaciones falsas.** Por eso C10 y C11,
  y por eso `check-diccionario` y `check-unicidad` entran antes de publicar.
- **El censo crece mientras se audita** (130 hoy, 103 en la ficha de la
  feature): el informe declara el suyo y el trinquete absorbe la diferencia.

## 10. Limite de microservicio

El diccionario es del dueno del dato y vive aqui. NO entra: cambiar el contrato
de lectura de `mcp-bbdd` (D1), construir los objetos que pide Compras (F-067) ni
escribir el conocimiento de dominio que falta (F-054). Si la auditoria concluye
que el MCP debe **presentar** la ficha de otra forma, se anota como peticion a
`mcp-bbdd` en el informe y no se implementa aqui.
