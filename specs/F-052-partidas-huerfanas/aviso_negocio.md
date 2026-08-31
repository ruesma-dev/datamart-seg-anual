<!-- specs/F-052-partidas-huerfanas/aviso_negocio.md -->
# Aviso · La obra 0599 TANATORIO MAJADAHONDA va a cambiar de cifras

**Fecha:** 2026-08-31 · **Estado:** pendiente de aplicar, se avisa **antes** de publicar

## Qué hemos encontrado

El datamart publica hoy, para la **0599 TANATORIO MAJADAHONDA**, una obra con
**4,07 M€ de venta y 0 € de coste directo**. Eso no es un dato: es un fallo
nuestro, y llevaba ahí desde el principio.

La causa está en cómo se tecleó esa obra en Sigrid. Su árbol de costes directos
no se montó por capítulos con código, sino **por fases** —«FASE 1 - MOVIMIENTO
TIERRAS Y CIMENTACIÓN», «FASE 2 - OBRA CIVIL», «FASE 2 - INSTALACIONES»— y esas
tres fases se dejaron **con el código en blanco**.

Nuestro proceso, al recorrer el árbol para saber a qué capítulo pertenece cada
partida, **se detiene al llegar a un nodo sin código** y descarta todo lo que
cuelga de él. En la 0599 eso son **1.323 partidas de 1.443**: solo llegan 117.
Y se descartaban **en silencio**, sin ningún aviso.

## Cuánto cambia

Cifras del último cierre de la obra (fase 28, abril–diciembre 2022):

| Concepto | Publicado hoy | Real | Diferencia |
|---|---|---|---|
| Coste directo | **0,00 €** | 2.624.793,46 € | oculto entero |
| Coste total | 1.369.592,67 € | 3.994.386,39 € | **×2,9** |
| Venta | 4.066.989,23 € | 4.066.989,23 € | sin cambio |
| **Margen** | **66,3 %** | **1,8 %** | **−64,5 puntos** |

**Cualquier informe, captura o Excel de la 0599 anterior a este cambio deja de
cuadrar.** No es que el datamart se haya roto: es que empieza a decir la verdad.

## A quién afecta

Solo a la **0599**, que está **cerrada desde diciembre de 2022**. Hay otras cinco
obras con el mismo tipo de dato mal metido (0613, 0618, 0630, 0565 y 0686), pero
en ellas el importe afectado es **0,00 €**: son comentarios sueltos («NO USAR»,
«SOBRECOSTE GRUPO ELECTRÓGENO»), no fases con dinero detrás.

**No está creciendo.** Es una forma de teclear de 2019-2021: de las ~120.000
partidas creadas después no hay ni un solo caso.

## Un efecto secundario que conviene saber

Al corregirlo, las partidas de la 0599 pasan a colgar directamente de COSTES
DIRECTOS. Es decir: **el desglose por fases de esa obra desaparece** del árbol de
Power BI. Los euros están todos y bien clasificados; lo que se pierde es poder
preguntar «cuánto costó la Fase 1» en esa obra concreta.

Si alguien usa hoy ese desglose, **decidlo antes de que apliquemos el cambio**:
hay una alternativa, pero obliga a inventarle un código a esas fases y hay que
acordarlo con vosotros.

## Lo que pedimos a quien administra Sigrid

1. **Prioritario — obra 0686 VALDEBEBAS (viva, última fase 31-07-2026):** tiene
   una partida que se apunta a sí misma como padre («LEGALIZACIÓN Y PUESTA EN
   MARCHA», creada en 2024). Hoy no mueve dinero, pero está en una obra en curso
   y mañana puede moverlo. **Conviene corregirlo en origen.**
2. **No prioritario:** los capítulos sin código de la 0599, 0613 y 0618, y el
   bucle de partidas de la 0565 y la 0630. Son obras cerradas entre 2020 y 2022;
   sanearlas en Sigrid ya no cambia nada.
3. **Norma hacia delante:** un capítulo de presupuesto **siempre con código**.
   Sin código, lo que cuelgue de él se pierde para el seguimiento.

El arreglo del datamart **no espera** a este saneamiento: protegemos el proceso
por nuestra cuenta, como ya hicimos en casos anteriores.

## Qué hacemos para que no vuelva a pasar

Añadimos una comprobación automática que, cada noche, **compara obra a obra lo
que entra con lo que sale** y avisa si una obra tiene datos de origen y no
aparece en el datamart. El fallo de la 0599 llevaba años sin detectarse porque
nadie estaba mirando eso.
