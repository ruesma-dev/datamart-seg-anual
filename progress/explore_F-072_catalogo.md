<!-- progress/explore_F-072_catalogo.md -->
# F-072 · El catálogo: qué hay en las 31 tablas que nadie consume

**Fecha**: 2026-09-09. **Cuatro exploradores en paralelo**, un bloque cada uno,
cruzando tres fuentes por tabla: `azure-apps/sigrid_tablas.md` (el significado
declarado), **sigrid-api contra el Sigrid vivo** (cómo funciona de verdad) y
mediciones de solo lectura sobre `raw`. Ni una escritura.

Los cuatro informes de detalle, que es donde vive cada ficha:

| bloque | fichero | tablas |
|---|---|---|
| Compras y proveedores | `explore_F-072_compras.md` | 8 |
| Documentos de coste | `explore_F-072_documentos_coste.md` | 9 |
| Producción y contabilidad | `explore_F-072_produccion.md` | 8 |
| Personal y contratos | `explore_F-072_personal_contratos.md` | 6 |

## 1 · El veredicto de las 31, de un vistazo

**Se construye con 19. Se descartan 6. El resto son catálogo puro** y valen
justamente por eso.

| tabla | veredicto | va a |
|---|---|---|
| `hmores` | **construir, lo primero** · 329 k líneas, 98,0 M€, engancha al 100 % con obras y al 100 % con partidas | F-057, F-061, F-036 |
| `conest` | **construir** · 193 filas que ponen nombre al estado de 165.539 facturas y 20.185 comparativos | F-067 |
| `auxpag` | **construir** · 69 filas, 99,95 % de cobertura sobre contratos y facturas ya publicados | F-067 |
| `auxefp` | **construir** · 10 filas, 99,99 % de uso; la forma de pago hoy no existe en ninguna capa | F-067 |
| `ctrrec`, `dcfrec`, `dcarec` | **construir juntas** · la REGLA de retención de proveedor: 6.257 contratos, base 460,3 M€, cuota 22,8 M€ | F-067 |
| `dnc`, `dncpro` | **construir** · 131,4 M€ de compra pendiente y la desviación referencia → adjudicado | F-067 |
| `com`, `comlin`, `comprv` | **construir** · 20.185 comparativos, 3.467 M€ ofertados frente a 1.160 M€ adjudicados | F-038, F-067 |
| `dco`, `dcopro` | **construir** · cierra la matriz oferta × línea y da la tasa de adjudicación por proveedor | F-067, F-038 |
| `apa` | **construir, con el puente** · 98,8 % de las filas caen en una obra concreta | F-058, F-061 |
| `apu`, `asi`, `cua` | **construir, pero solo juntas y dentro de F-056** · el mayor contable; 497 MB y 17 de 36 columnas vacías en `apu` | F-056 |
| `confir`, `deffir` | **construir** · plazo de aprobación y atasco por rol | F-055, F-038 |
| `conact`, `auxpronat` | **construir** · la actividad del proveedor, con familia por prefijo | F-055 |
| `res` | **construir despersonalizado** · pero ver §3: un recurso no es una persona en casi la mitad de los casos | F-057 |
| `emp` | **el último, y solo agregado** · 62 de 152 columnas vacías; es el mayor volumen de dato personal | F-057 |
| `prvcer` | **solo histórico, con advertencia** · 2.708 de 2.741 certificados caducaron antes de 2020 | F-055, baja |
| `obrprv` | **NO construir** · 0 filas en `raw` y **0 en Sigrid**; candidata a salir de `tables_sigrid.yaml` | — |
| `prvobrpag` | **NO construir** · 6 filas | — |
| `hmo` | **NO construir** · 4 columnas útiles, 7 vacías, nadie cierra los partes | — |
| `auxobrtca` | **NO construir** · catálogo de 3 filas, campo a cero en las 392.207 partidas | — |
| `dcorec` | **NO construir** · 751 filas, cubierta por sus hermanas | — |
| `dcfprodes` | **NO construir** · 276 abonos en 18 años | — |

## 2 · Lo que hay que ingerir ANTES de construir

Nueve tablas del origen que **no están en `tables_sigrid.yaml`** y sin las
cuales lo de arriba no se puede escribir. Siete de las nueve son diminutas.

| tabla | filas | por qué bloquea |
|---|---|---|
| `auxhor` | 60 | sin ella `hmores` es ilegible: no se puede separar hora de albañil de recibo de móvil |
| `auxrestip` | 37 | traduce la clase de recurso: persona, medio o consumo |
| `cet` | 40 | nombra el centro de trabajo (su columna `cod`, que el documento declara, **no existe** en Sigrid) |
| `auxdpt` | 7 | nombra el departamento |
| `pro` | por medir | hoy **el producto no tiene nombre** en el datamart, y lo referencian `dcopro` (99,9 %) y `dncpro` (95,4 %) |
| `reshor` | 8.949 | el precio de coste por recurso y tipo de hora: **el multiplicador que a F-061 le falta** para pasar de horas a euros |
| `emphis` | 1.633 | **el único sitio de Sigrid con histórico laboral**: 1.017 empleados, 1989 → 2026, tipo de contrato al 100 % |
| `dcaprodes` | 850.977 | trazabilidad línea a línea albarán → factura |
| `ctrprodes` | 424.454 | trazabilidad línea a línea contrato → albarán/factura |

`reshor` y `emphis` son **datos de nómina**: entran, si entran, con la misma
restricción que `emp` (F-068).

## 3 · Seis cosas que el catálogo desmiente, y que hay que corregir

1. **`res` no es el maestro de personal.** De sus filas, 1.353 son personas,
   1.157 son **consumos imputables** (móvil, caja de obra, gasoil, kilómetros) y
   106 son **medios** (vehículos, casetas, grúas). Y `auxhor` mezcla horas reales
   con «mes vehículo» y «consumos teléfono». **Sumar `hmores` sin cortar por
   `cla` da una cifra falsa**, que es justo lo que F-057 habría hecho.
2. **`apu` y `apa` no son análisis de precios unitarios**, sino apuntes
   contables y su desglose analítico. **El APU no existe como dato**: `catest`,
   `catpro` y `obrparres` tienen 0 filas en Sigrid vivo, `obrparpar.proide` está
   informado en 106 de 392.209, y la descomposición real vive dentro del blob
   `obrparpre.des`. **No prometer «de qué está hecho el precio de una partida»**:
   es un proyecto de parseo, no una tabla procesada.
3. **El punto 3 de F-036 no es implementable.** Se apoya en
   `obrparpar.tcaide` → `auxobrtca`: catálogo de 3 filas y campo a cero en las
   392.207 partidas. Corregir la ficha antes de que alguien lo intente.
4. **El proveedor del comparativo NO sale de `comprv.prvide`** (18,11 %
   informado) sino de **`dco.entide`** (99,86 %, 8.742 proveedores). Quien
   modele por el primero pierde el 82 % de las ofertas.
5. **`dncpro.pre` es mutable y Sigrid lo sobreescribe al adjudicar**: coincide
   con el precio del contrato en el 98,2 % de las líneas adjudicadas. **Calcular
   la desviación de compra con ese campo da cero.** La estimación original vive
   en `preref` (89,7 % de las adjudicadas).
6. **El documento miente sobre el estado de la oferta**: `dco.estped`,
   `estser` y `estfac` están a cero en 71.554 de 72.267. El estado real es
   `con.est` traducido por `conest`: 45.575 rechazadas (63 %) y 17.668 aceptadas
   (24 %).

Y dos más, menores pero medidas: **el contrato no se firma en Sigrid** (0 firmas
de tipo 44; lo que se firma es el comparativo previo, en orden jefe de obra →
jefe de grupo → dirección de compras, con enlace a la oferta adjudicada en el
99,65 %); y **el histórico de estados sigue sin existir**, así que la foto diaria
de F-067 hace falta y no hay atajo.

## 4 · Un defecto de configuración, encontrado de paso

`com`, `comlin` y `comprv` declaran `incremental_column: tiemod` en
`config/tables_sigrid.yaml` y **esa columna no existe en Sigrid** (error 42S22
verificado contra `INFORMATION_SCHEMA`). `_source_tiemod` está a NULL en las
tres y el ETL **degrada en silencio** (`ingest_raw_step.py:279`): la declaración
es falsa y oculta que esas **287.673 filas se recargan enteras cada noche**.

Y `prvcer` **excluye `tex` en la ingesta**, que es el único campo que dice de qué
es cada certificado: la tabla no tiene campo de tipo.

## 5 · El orden que propongo

**Primero, lo que no cuesta nada y evita construir sobre arena** (§3 y §4): las
seis correcciones de fichas del backlog y el arreglo de `tiemod`.

**Segundo, ampliar la ingesta** (§2). Las siete pequeñas son casi gratis; las
dos de trazabilidad suman 1,27 M de filas y merecen decisión aparte.

**Tercero, construir, por ratio valor/esfuerzo medido:**

1. **El puente centro de coste → obra.** Cuarenta líneas de SQL, 1:1 verificado
   sobre 683 pares sin una ambigüedad. **Resuelve F-045 en 261 de 261**, habilita
   F-061 y hace utilizable `apa`. El `cen.obride` que declara el documento está
   a cero en las 804 filas, y la aritmética `+1` que se suponía solo acierta el
   64 %: el puente real es «misma empresa y mismo código en `con`».
2. **Estados de documento** desde `conest`.
3. **Condiciones de pago** desde `auxpag` y `auxefp`, sobre objetos ya publicados.
4. **Horas y coste de mano de obra** desde `hmores` + `auxhor`.
5. **La regla de retención de proveedor** desde `ctrrec`, `dcfrec` y `dcarec`,
   con marca explícita de nivel para que nadie sume contrato, albarán y factura.
6. **La necesidad de compra** desde `dnc` y `dncpro`.
7. **El comparativo** desde `com`, `comlin`, `comprv`, `dco` y `dcopro`.
8. **El coste contable por obra** desde `apa`, ya con el puente.
9. **El mayor contable** (`apu`, `asi`, `cua`), solo dentro de F-056.
10. **Las firmas** (`confir` + `deffir`), publicando **solo** el circuito de
    comparativos: el de facturas nunca se usó y el de obras murió en 2020.
