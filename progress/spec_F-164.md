<!-- progress/spec_F-164.md -->
# F-164 · Mediciones de la spec (spec-author, 2026-11-16)

Azure, SOLO LECTURA: `filas_solo_lectura` (transacción `READ ONLY`, `statement_timeout` por
consulta) con `_bootstrap_done = True`, desde el checkout principal (su `.env`), entre las 09:55 y
las 10:15 UTC. Scripts en el scratchpad de la sesión (`f164_m1.py` a `f164_m12.py`). Aquí solo
recuentos: ni nombres de fichero, ni descripciones con datos, ni logins (los subidores van como
U1..U10 por volumen). Las «formas» de nombre llevan las cifras cambiadas por `9` y las letras sueltas
por `X`.

Dato medido: `postventa.documento_adjuntos` con **16.088 enlaces**, último `fecha_alta` 2026-11-15
(nocturna del 2026-11-16). Grupo = familia de hoy + clase de gráfico (`INC_SINCLASE` = documento
708 sin clase).

## 1. El reparto de hoy

| Grupo | Tipo | Clase (`gratipide`) | PDF | Imagen | Otro / correo | Total |
|---|---|---|---:|---:|---:|---:|
| INCIDENCIA | 708 | PV001 (34) Fotos de incidencias | 34 | 6.391 | 306 | 6.731 |
| INCIDENCIA | 708 | PV004 (37) Informes | 1 | 0 | 0 | 1 |
| INCIDENCIA | 708 | sin clase | 3.245 | 79 | 14 | 3.338 |
| REPARACION | 708 | PV002 (35) Fotos Reparaciones | 4.389 | 100 | 0 | 4.489 |
| TAREA | 47 | PV004 (37) | 699 | 0 | 0 | 699 |
| UNIDAD | 707 | PV006 (39) Ficha de inmueble | 822 | 0 | 0 | 822 |
| UNIDAD | 707 | PV002 (35) | 3 | 0 | 0 | 3 |
| UNIDAD | 707 | sin clase | 5 | 0 | 0 | 5 |

`raw.auxgra` tiene 48 clases; las de postventa son PV001-PV006 (ides 34-39). En uso solo 34, 35, 37 y
39. Ninguna lleva «PARTE» ni «FIRMA» en su nombre (lo midió el líder y se confirma).

## 2. Señales, una a una (cuántas atrapa, dónde)

«Verdad» disponible: en REPARACION, 3.944 PDF + 1 imagen con descripción «PARTE FIRMADO». El único
fichero de INC PV004 da S2 y S3.

| Señal | Verdad (3.945) | INC PV001 | INC sin clase | UNIDAD sin clase / PV002 | TAREA / UNIDAD PV006 |
|---|---:|---:|---:|---:|---:|
| S1 texto «parte…firmad» (nombre o descripción) | 3.945 | 1 PDF | 3 PDF | 0 / 3 | 0 / 0 |
| S2 «FIRMAD…», «FIRMA», «FIRMAS» como palabra | 3.945 | 2 PDF | 1.628 PDF + 38 img + 2 correo | 3 / 3 | 0 / 0 |
| S3 código de incidencia en el nombre (`RS99.99-9999` y variantes) | 3.939 | 2 PDF | 82 PDF + 1 img | 4 / 3 | 0 / 0 |
| S4 clase PV002 (35) en cualquier tipo | 3.945 | 0 | 0 | 0 / 3 | 0 / 0 |
| S5 documento 708 sin clase | 0 | 0 | 3.338 | — | — |
| S6 subido > 3 días tras el alta y a ± 3 días de la resolución | 1.258 | 2 img + 1 PDF | 3.059 | — | — |

- **Extensión**: no separa. Los partes son PDF casi siempre (3.944 de 3.945), pero también lo son
  los 822 de fichas de inmueble y los 699 informes de tarea; y hay partes en imagen (1 en REPARACION;
  en `INC_SINCLASE`, 38 imágenes con «FIRMA» en el nombre).
- **Metadatos de `raw.gra`** (`tip`, `tipocu`, `ori`, `anx`, `cla`, `texrev`, `mntide`, `graant`) y
  `raw.rcg.cla`: a 0 o vacíos en los 708; no distinguen nada. `nomori` repite el nombre.
- **Quién lo sube**: 10 logins en total, 2-6 por grupo. U2 sube 3.727 de REPARACION, pero también 393
  fichas de inmueble; U3 sube 3.026 de los 3.338 de `INC_SINCLASE` y nada en REPARACION. No es
  criterio (y es un dato personal que no conviene convertir en regla).
- **Clase de gráfico**: solo PV002 marca partes, y solo desde 2024.
- **Texto**: el patrón de Posventa desde 2024 es el código de la incidencia en el nombre
  (`RS9.9 - 9 FIRMADO.PDF` 2.071, `9 - RS9.9 - 9 PARTE FIRMADO.PDF` 735 —el de la aplicación
  `postventa-incidencias`—, `VIV 9 - RS9.9-9.PDF` 704, `B9X - RS9.9-9.PDF` ~760).

## 3. Los 7 del líder, uno a uno (todos PDF)

| Familia hoy | Tipo | Clase | Forma del nombre | Descripción | Alta |
|---|---|---|---|---|---|
| INCIDENCIA | 708 | sin clase | `VIV 9 - RS9.9-9.PDF` | PARTE FIRMADO | 2024-11 |
| INCIDENCIA | 708 | sin clase | `B9X - RS9.9-9.PDF` | PARTE FIRMADO | 2024-11 |
| INCIDENCIA | 708 | PV001 | `RS9.9 - 9 FIRMADO.PDF` | PARTE FIRMADO | 2025-07 |
| INCIDENCIA | 708 | sin clase | `9 - RS9.9 - 9 PARTE FIRMADO.PDF` | (vacía) | 2026-10 |
| UNIDAD | 707 | PV002 | `VIV 9 - RS9.9-9.PDF` | PARTE FIRMADO | 2024-11 |
| UNIDAD | 707 | PV002 | `B9X - RS9.9-9.PDF` | PARTE FIRMADO | 2024-11 |
| UNIDAD | 707 | PV002 | `VIV 9 - RS9.9-9.PDF` | PARTE FIRMADO | 2024-12 |

Los `adjunto_id` están en el script `f164_m11.py` del scratchpad (no son dato personal, pero la
fixture del test es SINTÉTICA con estas formas). Un parte con la descripción vacía (el de 2026-10)
desaparece de un filtro `NOT (… OR descripcion ILIKE …)`: `NULL` hace falso el `NOT`. Lo cazó la
primera versión de la medición (0 filas donde había 29): el SQL tiene que ser seguro ante `NULL`.

## 4. El hallazgo: los partes de 2021-2023 cuelgan SIN CLASE

| Grupo | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| INC sin clase | 1.815 | 1.211 | 243 | 24 | 15 | 30 |
| REPARACION (PV002) | 0 | 0 | 0 | 1.500 | 2.050 | 939 |

- De los 3.338 ficheros 708 sin clase, **3.182 se subieron a ± 3 días de la resolución** de su
  incidencia (mediana 0 días) y solo 127 en los 3 días del alta. Las fotos de PV001 son lo contrario:
  6.696 de 6.731 en los 3 días del alta.
- Incidencias con adjuntos: 3.111 + 107 tienen fichero sin clase y NINGUNO en REPARACION; 4.399 tienen
  REPARACION y ninguno sin clase; 13 tienen los dos. **El fichero sin clase es el documento de cierre
  de las incidencias anteriores a la convención PV002.**
- Formas: `P9.9X FIRMADA.PDF` ~1.350, `BLOQUE 9 PORTAL 9 PLANTA 9 LETRA X.PDF` ~700, `… TODAS LAS
  INCIDENCIAS FIRMADAS [SALVO RS…]` ~100, `RS9.9.PDF` 256, `9_9.PDF` 101, **`UNTITLED_9_9.PDF` 72**
  (escaneo con nombre genérico). 2.692 enlaces repiten nombre en ≥ 10 incidencias de la misma unidad:
  la hoja de la unidad, firmada, subida a cada incidencia.
- Con el texto (S1-S3) se cazan 1.680 (1.639 PDF, 39 imágenes, 2 correos); con la regla estructural
  (S5), los 3.338.

## 5. La regla propuesta (lista blanca + señal de texto) y la huella prevista

Abierta solo si (tipo, clase) está en la lista {(708, 34 PV001), (707, 39 PV006), (47, 37 PV004)}
**y** no da ni S2 (en el nombre o la descripción) ni S3 (solo en el nombre). Todo lo demás, REPARACION.
Patrones validados en PostgreSQL (`f164_m13.py`, sobre el texto en mayúsculas):
S2 `(^|[^A-ZÁÉÍÓÚÑÜ])FIRMA(D|S?([^A-ZÁÉÍÓÚÑÜ]|$))` (no casa «CONFIRMADO»: 0 en el índice) y S3
`RS\s*[0-9]{2}\.[0-9]{2}\s*[-/_. ]\s*[0-9]{3,5}`. Juntos dan 3.945 de 3.945 en la verdad. S3 sobre la
descripción añadiría 1 foto de PV001 del día del alta con el código tecleado en la descripción (falso
positivo): por eso S3 mira solo el nombre.

| Antes | Después | Tipo | Clase | Clase de fichero | Enlaces |
|---|---|---|---|---|---:|
| INCIDENCIA | INCIDENCIA | 708 | PV001 | imagen 6.391 · otro 306 · PDF 32 | 6.729 |
| INCIDENCIA | **REPARACION** | 708 | PV001 | PDF (S2/S3) | 2 |
| INCIDENCIA | **REPARACION** | 708 | PV004 | PDF | 1 |
| INCIDENCIA | **REPARACION** | 708 | sin clase | PDF 3.245 · imagen 79 · otro 12 · correo 2 | 3.338 |
| UNIDAD | **REPARACION** | 707 | PV002 / sin clase | PDF | 3 + 5 |
| REPARACION, TAREA, UNIDAD PV006 | sin cambio | | | | 4.489 · 699 · 822 |

**3.349 enlaces cambian** (3.341 de 708 en 3.234 incidencias, 8 de 707 en 6 unidades); ninguno sale
de REPARACION; los 7 caen en REPARACION. Alternativas medidas: solo texto «parte firmado» (S1), 7;
texto ampliado + código + PV002 en cualquier tipo (S1-S4), 1.690; con la ventana de fechas (S6), 3.148.

## 6. El destino, contra `mcp-bbdd` (leído en `feature/F-034-postventa`, sin tocarlo)

- `abrir_adjunto` lee la familia de la fila y hace `LEFT JOIN` a la tabla de origen de ESA familia
  **por `documento_id`**; sin origen en su `config.yaml` → `ErrorConfiguracion` (nadie abre, ni
  postventa). F-034 R7 fija exactamente INCIDENCIA, UNIDAD, TAREA y REPARACION →
  `postventa_restringida.contactos_incidencia.incidencia_id`. **Una familia nueva NO la acepta sin
  cambiar `mcp-bbdd`.**
- De los 3.341 de 708 que pasan a REPARACION, **3.341 tienen fila** en `contactos_incidencia` (es una
  fila por incidencia). Los **8 de 707** no: su `documento_id` es la unidad → el MCP los entrega a
  postventa y total con el aviso de huérfano (F-023 R8, `domain/adjuntos.py`), y al estándar y al
  restringido les responde `PERMISO_DENEGADO` igual (el `JOIN` lee la tabla restringida haya filas o
  no). Hoy las 4.489 REPARACION tienen su fila.
- No hay ficheros compartidos: ningún `grafico_id` cuelga de dos familias (solo TAREA repite 102
  gráficos en 518 enlaces), ninguna pareja (`empresa_repositorio`, `cod_repositorio`) tiene dos
  gráficos, y ninguno está en `compras.documento_adjuntos`.

## 7. Lo que la regla no ve (declarado)

- Un parte fotografiado o escaneado con nombre genérico **dentro de PV001**: de las 6.731, solo 35 se
  subieron más de 3 días después del alta (28 imágenes, 5 vídeos/heic, 2 PDF, ya cazados); las demás
  son del alta, antes de cualquier reparación. Cota: ≤ 33.
- Los 32 PDF de PV001 restantes: nombre GUID, subidos en los 3 días del alta (documentos del alta, no
  partes de reparación). Quedan abiertos (D5).
- TAREA (699): informes que genera Sigrid (`9_9_9_9_TAR_PRV_RCP.PDF` 649, `…_TAR_PARTE_DE_TRABAJOS.PDF`
  50), sin texto de firma y sin coincidir con la resolución (0 de 50 a ± 3 días). UNIDAD PV006 (822):
  fichas de inmueble con el código de la unidad. Ninguna señal.
- El contenido del fichero: el datamart no tiene el binario. Que las hojas de 2021-2023 lleven DNI
  manuscrito es una presunción (mismo momento y mismo papel que el parte); la regla las restringe
  igual.
