<!-- specs/F-070-auditoria-calidad-diccionario/requirements.md -->
# F-070 · Auditar la CALIDAD del diccionario: que falta y que sobra

Cobertura no es calidad, y una ficha completa puede haber dejado de ser verdad.
Medido en la **version 16** (2026-09-08): **130 objetos y 822 columnas**, solo
**47** de consumo, y `raw` con **56 tablas sin una columna documentada**. Las
dos mitades tienen evidencia: **28 medidas sumables sin `unidad`** y **cero
fichas** que digan que NO contiene el objeto (falta); **1.289 n-gramas de doce
palabras repetidos en dos o mas fichas** —el mismo puntero copiado en las 56 de
`raw`— y **30 parrafos con cifras de conducta sin fecha** (sobra o caduco).
Frontera: **F-054** escribe el dominio que no existe, **F-046** la regla del
total publicado, **F-067** los datos que faltan; F-070 **audita lo publicado**.

## Criterios y gravedad

R1. El sistema debe publicar en `docs/CALIDAD_DICCIONARIO.md` los criterios
`C1`..`C14` con: que exige, como se comprueba, gravedad por defecto y el fallo
real que lo motiva. Es la lista que aplica cualquiera sin depender del gusto.

R2. El sistema debe definir tres gravedades medidas por **cuanto cambia una
respuesta de la IA**: `grave` (otra cifra u otro objeto, y nada avisa), `serio`
(la cifra es correcta pero falta un limite o va al objeto vecino) y `menor` (no
cambia ninguna respuesta). El estilo nunca sube de `menor`.

R3. SI un hallazgo no lleva escrita la pregunta de negocio que se responde mal
por su culpa, ENTONCES debe clasificarse `menor` y no exigir correccion.

## Alcance: TODAS las tablas, con la profundidad declarada

R4. El sistema debe auditar **todos** los objetos del censo del dia —hoy 130—
asignando a cada uno un nivel declarado: **A** (consumo: los catorce criterios,
columna a columna), **B** (`stg`, `aux` y demas no recomendados: criterios de
objeto mas las columnas de clave y de relacion) y **C** (`raw`: de objeto).

R5. CUANDO un objeto sea de nivel C, su ficha debe decir que guarda esa tabla en
negocio, que NO es (copia literal de Sigrid, sin filtrar ni deduplicar), a que
objeto de consumo ir para preguntar por ello y cuales son sus columnas de union
y filtro. Pedir menos a `raw` que a una vista es legitimo; no explicarla no.

R6. El informe debe traer una fila **por cada objeto del censo** con su nivel y
su veredicto por criterio, y declarar el censo (objetos y columnas) de la pasada.

## El auditor (codigo)

R7. CUANDO se ejecuta `python main.py auditar-diccionario`, el sistema debe
recorrer todos los objetos y columnas **sin abrir conexion ni salir a la red** y
emitir un hallazgo por criterio incumplido con esquema, objeto, columna,
criterio y gravedad.

R8. CUANDO haya un hallazgo `grave`, el comando debe salir con codigo 1; si no,
con 0, listando igualmente los `serio` y el recuento de `menor`.

R9. El sistema debe admitir `--esquema`, `--gravedad`, `--nivel <A|B|C>` y
`--solo-consumo`, y por defecto auditar el censo entero con el nivel de cada uno.

R10. CUANDO una columna de nivel A declare `agregacion` en (`suma`, `promedio`,
`ultimo_valor`, `suma_solo_dentro_del_mes`) sin declarar `unidad`, hallazgo
`grave` de C3: sin unidad la IA mezcla euros con unidades de obra y conteos.

R11. CUANDO una ficha no declare que NO contiene el objeto —marcador
`**NO contiene:**`—, hallazgo `serio` de C5; y CUANDO el objeto este en el
ambito de una regla dura que exige filtrar y no declare el filtro —marcador
`**Filtro obligatorio:**` con el `WHERE` literal—, hallazgo `grave` de C4.

R12. CUANDO el `significado` de una columna de nivel A no anada al menos cuatro
palabras que no esten en su nombre, hallazgo de C1 `menor`, o `serio` si la
columna es una medida, un codigo o un estado.

R13. SI un fichero de `config/diccionario/` no carga, ENTONCES el comando debe
abortar nombrandolo, con el motivo, sin escribir nada y sin tocar la base.

## Lo que SOBRA (compite por la atencion del modelo)

R14. El informe debe separar **lo que falta** de **lo que sobra**, y lo que
sobra debe caer en una de cuatro clases, nunca de estilo: caducado (C11),
ejemplo que el objeto no puede responder (C12), repetido (C13), redundante (C14).

R15. CUANDO una ficha afirme una cifra de conducta —cuantas obras, cuantas
filas, cuanto tarda, cada cuanto se reconstruye— sin fecha de medicion y fuente
comprobable en el mismo parrafo, hallazgo `serio` de C11; y SI la cifra es un
CRITERIO de diseno y no una medicion, la ficha debe decirlo con esas palabras.

R16. CUANDO el SQL que construye un objeto haya cambiado despues de la fecha de
medicion mas reciente que cita su ficha, hallazgo `serio` de C11 pidiendo
revision de vigencia, con la fecha del ultimo cambio en git y sin tocar la base.

R17. El sistema debe tratar como `grave` la ficha que describa una conducta que
el codigo ya no tiene. Caso que lo motiva: hasta la v16 la ventana de F-025
contaba el CRITERIO (40 vivas / 880 congeladas) como CONDUCTA de una noche (592
rehechas / 328), de donde salia el consejo falso de «hasta 6 dias».

R18. CUANDO un `ejemplos_preguntas` no pueda responderse con un `SELECT` escrito
solo con columnas de su ficha, hallazgo `serio` de C12: o sobra el ejemplo o
falta la columna. `compras.contratos` pregunta por contratos «ABIERTOS» y no
publica estado.

R19. Una afirmacion que vale para varios objetos debe vivir en UN solo sitio —la
entrada de esquema o una regla dura, que el validador ya adjunta por ambito— en
vez de copiarse ficha a ficha (C13); y SI hay copias de la misma afirmacion que
**divergen**, ENTONCES el hallazgo es `grave`, porque una de las dos es falsa.

R20. CUANDO dos objetos de consumo respondan a la misma pregunta, sus fichas
deben declarar cual manda y para que va cada uno; y el que ya no deba
consultarse baja `consumo_recomendado` y nombra a su sucesor (C14).

R21. El sistema debe informar el **presupuesto de contexto**: caracteres
publicados por ficha y en total (hoy 223.603, mediana 1.498, maximo 7.746).

## Correccion y derivaciones

R22. CUANDO un hallazgo pertenezca a F-054, F-046 o F-067, el informe debe
derivarlo citando la feature y el sistema NO debe corregirlo aqui.

R23. El sistema debe corregir todos los hallazgos `grave` —de lo que falta y de
lo que sobra—, subir `version` en `00_global.yaml` y publicar en `_meta`. El
informe vive en `progress/auditoria_F-070.md`.

## La bateria contra el MCP real

R24. El sistema debe ampliar `preguntas_aceptacion` con los dos casos reales de
fallo —las cuatro carencias del correo de Compras del 2026-09-05 y la obra 0694
(34.523,22 EUR en 61 efectos)— y una de vigencia: «de cuando es el dato de X».

R25. Cada pregunta debe traer su `respuesta_correcta` escrita ANTES de la
pasada, y `estado` con `bloqueada_por` cuando la respuesta correcta sea que el
datamart todavia no lo tiene.

R26. CUANDO se pase la bateria contra el MCP real, la sesion que responde no
debe tener acceso a este repositorio —solo el conector— y el veredicto se decide
contra la `respuesta_correcta` escrita de antemano, no con el criterio del dia.

R27. El sistema debe registrar cada pasada en `docs/PRUEBAS_MCP.md`: fecha,
version del diccionario, veredicto por pregunta y causa de las que fallen.

## Que no se degrade en silencio

R28. MIENTRAS queden hallazgos `serio` sin corregir, deben declararse en
`config/calidad_pendientes.yaml` con objeto, criterio, motivo y fecha; esa lista
es un trinquete y **solo puede bajar**.

R29. CUANDO se ejecuta `bash harness/init.sh`, el sistema debe pasar la
auditoria en modo puerta —censo entero, gravedad `grave`— y ponerse en rojo si
aparece un `grave` o si el trinquete crece.

R30. El sistema debe dejar escrito en `docs/CALIDAD_DICCIONARIO.md` y en
`CHECKPOINTS.md` quien revisa lo no automatizable y cuando: el reviewer aplica
los criterios a las fichas que toque su feature, y el humano pasa la bateria
completa en cada subida de `version` del diccionario.
