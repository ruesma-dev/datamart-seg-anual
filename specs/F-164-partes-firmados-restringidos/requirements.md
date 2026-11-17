<!-- specs/F-164-partes-firmados-restringidos/requirements.md -->
# F-164 · Requisitos · Los partes firmados de postventa, siempre en la familia restringida

Origen: `mcp-bbdd` F-034, DH10, cerrada con riesgo aceptado; prioridad 1 del humano (2026-11-16).
Mediciones (Azure, solo lectura, 2026-11-16, 16.088 enlaces): `progress/spec_F-164.md`. Diseño y
decisiones: `design.md` (D1-D5, con la recomendada marcada). Los requisitos se escriben con las
**recomendadas**; si el humano elige otra, el líder ajusta R1-R4 y la huella de R13 antes del OK.

**Por qué no basta el texto.** El líder midió 7 ficheros «parte firmado» fuera de REPARACION. La
medición de la spec encuentra que los partes de 2021-2023 (anteriores a la convención PV002 de 2024)
cuelgan de la incidencia **sin clase de gráfico**: 3.338 ficheros 708 sin clase, 3.182 de ellos
subidos a ± 3 días de la resolución, muchos con nombre genérico (`UNTITLED_…`). El texto caza 1.680.

**Términos.**
- *Lista abierta*: las parejas (tipo de documento, clase de gráfico) que puede abrir cualquier perfil:
  (708, 34 PV001 «Fotos de incidencias»), (707, 39 PV006 «Ficha de inmueble»), (47, 37 PV004
  «Informes»).
- *Señal de firma* (S2): el nombre o la descripción, en mayúsculas, casan
  `(^|[^A-ZÁÉÍÓÚÑÜ])FIRMA(D|S?([^A-ZÁÉÍÓÚÑÜ]|$))` («FIRMADO», «FIRMADA», «FIRMADAS», «FIRMA»,
  «FIRMAS»; no «CONFIRMADO»).
- *Señal de código* (S3): el nombre, en mayúsculas, casa `RS\s*[0-9]{2}\.[0-9]{2}\s*[-/_. ]\s*[0-9]{3,5}`
  (el código de una incidencia, la convención de Posventa para nombrar los partes).
- *Familia por documento*: la regla de F-156 (`familia_adjunto(tip, gratipide)`), sin cambios.

## La regla

R1. El sistema debe asignar `familia = 'REPARACION'` a todo enlace de `postventa.documento_adjuntos`
cuya pareja (`tipo_documento_codigo`, `clase_grafico_id`) no esté en la lista abierta, sea cual sea su
tipo, su extensión, su nombre o su descripción. (capa: unit)

R2. CUANDO un enlace está en la lista abierta y da la señal de firma o la de código, el sistema debe
asignarle `familia = 'REPARACION'`. (capa: unit)

R3. MIENTRAS un enlace esté en la lista abierta y no dé ninguna señal, el sistema debe asignarle su
familia por documento (INCIDENCIA, UNIDAD o TAREA), como hoy. (capa: unit)

R4. SI el tipo o la clase llegan nulos, ENTONCES el enlace debe ir a REPARACION (la clase nula de los
3.338); SI el nombre o la descripción llegan nulos o vacíos, ENTONCES cuentan como texto vacío y la
señal del otro campo sigue valiendo (el parte de 2026-10 de la fixture, con descripción vacía y
«FIRMADO» en el nombre, es REPARACION). Ningún `NULL` del SQL abre un fichero. (capa: unit)

R5. CUANDO aparezca en Sigrid una clase de gráfico que no está en la lista abierta (una PV00x nueva,
o PV002 colgada de una unidad o de una tarea), el sistema debe asignar REPARACION sin cambiar código:
la lista es de lo que se abre, no de lo que se cierra. (capa: unit)

R6. La regla debe tratar igual un PDF, una imagen, un vídeo o un correo: la extensión y
`clase_fichero` no abren nada. (capa: unit)

R7. El sistema nunca debe sacar de REPARACION un enlace cuya familia por documento sea REPARACION
(708 + PV002). (capa: unit)

R8. Los 7 ficheros medidos por el líder el 2026-11-16, como fixture SINTÉTICA con su tipo, su clase,
la forma de su nombre y su descripción (tabla de `progress/spec_F-164.md` §3), deben quedar en
REPARACION, y el test debe estar en ROJO sobre el código de hoy. (capa: unit)

## El SQL y el dominio

R9. La regla vive UNA vez en el dominio (`etl_sigrid/domain/postventa.py`): la lista abierta, los dos
patrones y la función que decide. El `CASE` de `sql/postventa/06_adjuntos.sql` debe llevar
exactamente esos literales; un test compara el texto del SQL con las constantes del dominio, como
F-156 R13 hace con la máscara. (capa: unit)

R10. CUANDO el `06_adjuntos.sql` real se ejecuta sobre un `raw` mínimo con los tipos de la ingesta
(ids y `gratipide` `integer`, texto `character varying`) y una fixture que cubre R1-R8, cada enlace
debe salir con la familia que da la función del dominio (oráculo), incluidos los acentos de `upper()`
y los patrones en el ARE de PostgreSQL. Sin `F164_SANDBOX_DSN`, `skip`. (capa: integración)

R11. `postventa.documento_adjuntos` debe publicar una columna nueva `familia_documento`, la familia
por documento (D3), al lado de `familia`; el resto de columnas, su orden relativo, la clave
`adjunto_id`, los índices y el número de filas no cambian. Las columnas que lee `abrir_adjunto`
(F-145/F-034) no cambian de nombre ni de tipo. (capa: unit)

## Diccionario, documentación y ecosistema

R12. El diccionario debe decir el criterio y lo que no ve: la ficha de
`postventa.documento_adjuntos` en `config/diccionario/postventa.yaml` (familia REPARACION = «parte
firmado o posible parte»: lista abierta + señales; los partes de 2021-2023 sin clase; la columna
`familia_documento`; los 707 en REPARACION sin fila de origen), la regla `R-POSTVENTA-RESTRINGIDA` de
`00_global.yaml` (los adjuntos REPARACION son los reconocidos por F-164, no solo PV002), la ficha de
`postventa_restringida.contactos_incidencia` (huérfanos de 707) y `raw.auxgra`; versión del
diccionario +1. (capa: unit)

R13. `docs/ARCHITECTURE.md` (párrafo de `postventa`) y `azure-apps/datamart_seg_anual.md` (§«La
postventa», el contrato con `mcp-bbdd`) deben describir la regla, la columna nueva, los huérfanos de
707 y que `mcp-bbdd` no cambia; el documento del ecosistema, en commit aparte en `azure-apps`.
(capa: unit, lee el documento como F-161 R21; skip si `azure-apps` no está al lado)

## Verificación en Azure (después de desplegar)

R14. CUANDO se reconstruye `postventa` en Azure con la imagen nueva y SIN reingerir `raw`, la huella
antes/después de `postventa.documento_adjuntos` debe cumplir: el mismo conjunto de `adjunto_id`; las
demás columnas idénticas fila a fila (md5); `familia_documento` igual a la `familia` de antes en todas
las filas; y solo cambian de familia filas de INCIDENCIA o UNIDAD a REPARACION, ≈ 3.349 (3.341 de 708
y 8 de 707 con el dato del 2026-11-16; la cifra exacta, la del día). (capa: integración, MANUAL)

R15. Tras desplegar, ninguna fila fuera de REPARACION debe dar la señal de firma o la de código, ni
estar fuera de la lista abierta (consulta en Azure = 0 filas). (capa: integración, MANUAL)

R16. Tras desplegar, con `mcp-bbdd` sin cambios: abrir un adjunto movido de 708 y uno de 707 con el
perfil estándar y el restringido da `PERMISO_DENEGADO`; con postventa y total se abre (el de 707, con
el aviso de huérfano). Lo hace la sesión `mcp` o el humano; el líder le avisa al desplegar para que
cierre DH10. (capa: integración, MANUAL)

## Fuera de alcance

- `mcp-bbdd` (su regla va por familia; F-034 R7 fija las cuatro familias): no se toca.
- Leer el contenido de los ficheros (OCR, DNI dentro del PDF): el datamart no tiene el binario.
- Cambiar `documento_id`, `incidencia_id` o `unidad_id` de los 707 movidos para que tengan origen.
- Ocultar las FILAS del índice: las ven todos, como hoy; lo restringido es abrir el fichero.
- Los adjuntos de compras (`compras.documento_adjuntos`): ningún fichero es común (medido).
