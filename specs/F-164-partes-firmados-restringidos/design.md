<!-- specs/F-164-partes-firmados-restringidos/design.md -->
# F-164 · Diseño · Los partes firmados de postventa, siempre en la familia restringida

**Rigor: `critico`** (el de `harness/features.json`). Disparadores de `CHECKPOINTS.md` §«Niveles de
rigor»: **3, seguridad y datos personales** (quién abre un fichero con el DNI manuscrito del cliente:
`postventa.documento_adjuntos.familia` es la autorización de `abrir_adjunto`) y **4, contrato
público** (esa columna la consume `mcp-bbdd`).

Cifras: spec-author, Azure, solo lectura, 2026-11-16 09:55-10:15 UTC, 16.088 enlaces (último alta
2026-11-15). Detalle y consultas: `progress/spec_F-164.md`.

## 1. Encaje, límite y frontera

Todo cabe en este ETL: la familia la publica `build_postventa` (`sql/postventa/06_adjuntos.sql`) y el
MCP decide por ella. No hay ingesta nueva, ni tabla de `raw` nueva, ni permisos nuevos, ni llamada a
`sigrid-api`. No se propone extraer nada a otro servicio.

**Frontera: ¿cruza la frontera del proyecto? Sí, en lo publicado.** Cambia el VALOR de `familia` en
≈ 3.349 filas de `postventa.documento_adjuntos` (de INCIDENCIA/UNIDAD a REPARACION) y aparece la
columna `familia_documento`. Lo consume `mcp-bbdd`, que **no cambia** (§6). Documento del ecosistema:
`azure-apps/datamart_seg_anual.md` §«La postventa» (`git pull --rebase` antes, solo nuestro documento,
commit aparte, sin `push`). Imagen nueva en el ACR común `acralbaranesdev` (lo de siempre).

## 2. Ficheros

**Crear**
- `tests/test_f164_dominio.py`: R1-R8 sobre la función del dominio, con la fixture de los 7 (§5).
- `tests/test_f164_sql.py`: R9 y R11 (texto del SQL contra las constantes del dominio; columnas).
- `tests/test_f164_sandbox.py`: R10, patrón de `tests/test_f161_sandbox.py` (base nueva y desechable,
  `F164_SANDBOX_DSN`; sin él, `skip`).
- `tests/test_f164_diccionario.py`: R12 y R13 (fichas, regla, versión, `ARCHITECTURE.md`,
  `azure-apps`; el localizador de `azure-apps` como `tests/test_f161_diccionario.py::_azure_apps`).

**Modificar**
- `etl_sigrid/domain/postventa.py`, bloque «R20 · familias de los gráficos»: constantes y función
  nueva (§3). `familia_adjunto` y `ORIGEN_POR_FAMILIA` NO cambian.
- `etl_sigrid/infrastructure/postgres/sql/postventa/06_adjuntos.sql`: el `CASE` de §4, la columna
  `familia_documento`, la cabecera (bloque FAMILIA) y el `COMMENT ON TABLE`.
- `config/diccionario/postventa.yaml` (ficha `documento_adjuntos`: descripción, `familia`,
  `familia_documento`), `config/diccionario/postventa_restringida.yaml` (`contactos_incidencia`:
  huérfanos de 707), `config/diccionario/raw.yaml` (`auxgra`: PV002 ya no es la única marca),
  `config/diccionario/00_global.yaml` (`R-POSTVENTA-RESTRINGIDA` y `version` +1 con su entrada de
  historial; el número, el siguiente libre al integrar).
- `docs/ARCHITECTURE.md`, párrafo de `postventa` (líneas ~53-72).
- `tests/test_f156_ingesta_sql.py::test_f156_r20_familia_con_los_literales_del_dominio`: la expresión
  de F-156 pasa a `AS familia_documento`; se adapta con el motivo escrito en el propio test.
- Fuera del repositorio: `azure-apps/datamart_seg_anual.md` (R13), commit aparte.

**NO se tocan**
- `mcp-bbdd` entero (su `config.yaml`, su F-034): la regla va por familia y no cambia.
- `07_restringida.sql`: `contactos_incidencia` sigue con una fila por incidencia.
- `documento_id`, `incidencia_id`, `unidad_id`, `tarea_id` de ningún enlace (contrato de F-145/F-034).
- La ingesta (`config/tables_sigrid.yaml`: `rcg`, `gra`, `auxgra` ya traen lo necesario), `apply_grants`.
- `compras.documento_adjuntos` y su SQL.

## 3. Dominio (`etl_sigrid/domain/postventa.py`, capa domain, puro)

```python
GRATIPIDE_FOTOS_INCIDENCIA: Final[int] = 34   # PV001
GRATIPIDE_INFORMES: Final[int] = 37           # PV004
GRATIPIDE_FICHA_INMUEBLE: Final[int] = 39     # PV006
#: Lo ÚNICO que abre cualquier perfil (R1, R5): (tipo de documento, clase de gráfico).
LISTA_ABIERTA: Final[frozenset[tuple[int, int]]] = frozenset({
    (TIPO_INCIDENCIA, GRATIPIDE_FOTOS_INCIDENCIA),
    (TIPO_UNIDAD, GRATIPIDE_FICHA_INMUEBLE),
    (TIPO_TAREA, GRATIPIDE_INFORMES)})
#: Valen igual en Python (`re.search`) y en el ARE de PostgreSQL (`~`), sobre el texto en mayúsculas.
PATRON_SENAL_FIRMA: Final[str] = r"(^|[^A-ZÁÉÍÓÚÑÜ])FIRMA(D|S?([^A-ZÁÉÍÓÚÑÜ]|$))"
PATRON_SENAL_CODIGO: Final[str] = r"RS\s*[0-9]{2}\.[0-9]{2}\s*[-/_. ]\s*[0-9]{3,5}"

def senal_parte_firmado(nombre: str | None, descripcion: str | None) -> bool:
    """S2 sobre nombre + ' ' + descripción; S3 solo sobre el nombre (R2). None cuenta como ''."""

def familia_publicada(tip: int | None, gratipide: int | None,
                      nombre: str | None, descripcion: str | None) -> str | None:
    """La familia que se publica (R1-R7). None si el tipo no es de postventa, como familia_adjunto.
    Abierta solo si (tip, gratipide) está en LISTA_ABIERTA y no hay señal; si no, REPARACION."""
```

Nombre y descripción, tal y como los publica la tabla (`NULLIF(BTRIM(...), '')`). S3 no mira la
descripción: añadiría 1 foto de PV001 del día del alta con el código tecleado (falso positivo medido).

## 4. SQL (`sql/postventa/06_adjuntos.sql`, esquema `postventa`, mismo fichero y número)

En la CTE `base`, la expresión de F-156 se queda tal cual y pasa a llamarse `familia_documento`; la
nueva `familia` la envuelve, **segura ante `NULL`** (R4: solo `IS TRUE`/`IS FALSE` abren):

```sql
CASE WHEN c.tip = 707 THEN 'UNIDAD' WHEN c.tip = 47 THEN 'TAREA'
     WHEN g.gratipide = 35 THEN 'REPARACION' ELSE 'INCIDENCIA' END::TEXT   AS familia_documento,
CASE WHEN ((c.tip = 708 AND g.gratipide = 34) OR (c.tip = 707 AND g.gratipide = 39)
           OR (c.tip = 47 AND g.gratipide = 37)) IS TRUE
      AND (upper(COALESCE(NULLIF(BTRIM(g.nom), ''), '') || ' ' || COALESCE(NULLIF(BTRIM(g.res), ''), ''))
               ~ '<PATRON_SENAL_FIRMA>'
           OR upper(COALESCE(NULLIF(BTRIM(g.nom), ''), '')) ~ '<PATRON_SENAL_CODIGO>') IS FALSE
     THEN <la misma expresión de familia_documento> ELSE 'REPARACION' END::TEXT          AS familia,
```

Los literales `34/39/37`, `35`, `708/707/47` y los dos patrones, exactamente los del dominio (R9; el
test los extrae del SQL y los compara). En el `SELECT` final, `familia_documento` va justo detrás de
`familia`; el resto, igual. `PRIMARY KEY`, índices y guarda R21, sin cambios. El `COMMENT ON TABLE`
dice: «REPARACION = parte firmado o posible parte (F-164): todo lo que no es foto de incidencia (PV001),
ficha de inmueble (PV006) o informe de tarea (PV004), y lo que en ellas lleve FIRMA o el código de una
incidencia en el nombre».

## 5. Tests y fixture

- **Fixture de los 7** (sintética, `progress/spec_F-164.md` §3): tres 708 sin clase con nombres
  `VIV 1 - RS24.11-0123.pdf`, `B1C - RS24.11-0456.pdf` y `0601 - RS26.10 - 0789 PARTE FIRMADO.pdf`
  (este con descripción `None`); uno 708 PV001 `RS25.07 - 0321 FIRMADO.pdf` con «PARTE FIRMADO»;
  tres 707 PV002 con las formas `VIV 9 - RS9.9-9.pdf` y `B9X - RS9.9-9.pdf`. Ningún dato real.
- **Controles que deben quedar abiertos**: foto PV001 `20250312_101010.jpg` sin descripción; PV001 con
  «PARTE TRASERA» (la palabra «PARTE» sola no es señal); PV006 `0601_02_03_04_PRIMERA_HAB1.pdf`;
  PV004 de tarea `1_2_3_4_TAR_PRV_RCP.pdf`; texto «CONFIRMADO» en PV001.
- **Restringidos sin texto**: 708 sin clase `UNTITLED_1_2.pdf`; 708 con clase 38 (PV005, nueva en
  postventa); 47 con clase 35; 707 sin clase; imagen `.jpg` 708 sin clase; todo con `None` en tipo o
  clase.
- RED: `test_f164_dominio.py` y `test_f164_sql.py` fallan sobre `e818dc2` (la función y la columna no
  existen). La sandbox (R10) no tiene RED propia (skip sin DSN), como F-161.
- Mutación (`critico`): sobre las líneas cambiadas de `domain/postventa.py`; el SQL lo cubren R9/R10.

## 6. Destino: REPARACION, y lo que hace `mcp-bbdd` con él (leído, no tocado)

`abrir_adjunto` (F-023, `infrastructure/db/repositorio_postgres.py::leer_adjunto`) lee la familia de
la fila y hace `LEFT JOIN` a la tabla de origen de esa familia **por `documento_id`**, leyendo una
columna del origen: quien no lee `postventa_restringida` recibe `permission denied` haya filas o no.
Una familia sin origen en su `config.yaml` da `ErrorConfiguracion` a todos, también a postventa; F-034
R7 fija las cuatro de hoy. Por eso el destino es REPARACION (D2).
- 708 movidos (3.341): `documento_id` = incidencia, con fila en `contactos_incidencia` (3.341 de 3.341).
- 707 movidos (8): `documento_id` = unidad, SIN fila de origen → postventa y total los abren con el
  aviso de huérfano (`domain/adjuntos.py::avisos_de`); estándar y restringido, `PERMISO_DENEGADO`.
  Rompe una frase de F-034 (design §6: «REPARACION es 708 + PV002, así que su `documento_id` ES el
  `incidencia_id`»): va en el aviso a la sesión `mcp` (D4).

## 7. Despliegue, huella y vuelta atrás (MANUAL, el humano lanza; el líder lee)

1. **Huella ANTES** (líder, solo lectura, el mismo día y tras la nocturna): `SELECT adjunto_id,
   familia, md5((documento_id, tipo_documento_codigo, codigo_documento, incidencia_id, unidad_id,
   tarea_id, grafico_id, cod_repositorio, empresa_repositorio, nombre_fichero, extension,
   clase_fichero, clase_grafico_id, clase_grafico_codigo, clase_grafico, descripcion, fecha_alta,
   subido_por, posicion)::text) FROM postventa.documento_adjuntos ORDER BY 1` → CSV en el scratchpad.
2. Merge (`dev`, y `main` preguntando); imagen nueva `infra/70_build_image.ps1`;
   `infra/85_update_job.ps1 -Tag <nuevo>`; comprobar la imagen con `az containerapp job show`.
3. **Ejecución puntual SIN ingesta** (receta de la memoria «job puntual con `--yaml`»): `python main.py
   build-postventa && python main.py apply-grants && python main.py publicar-diccionario`. Minutos
   (`build_postventa` ~15 s); no solapar con la nocturna de las 00:00 UTC.
4. **Huella DESPUÉS** con la misma consulta + `familia_documento`; comparar (R14) y la consulta de R15
   (0 filas). Reiniciar `mcp-bbdd` (cachea el diccionario) y avisar a la sesión `mcp` (R16, DH10).
5. **Vuelta atrás**: `infra/85_update_job.ps1 -Tag r20261116-1018` (la imagen de hoy) y la misma
   ejecución puntual, o la nocturna: vuelve la regla de F-156 y su diccionario. Vuelve también la
   exposición de los ≈ 3.349: solo ante un fallo del build, nunca por los falsos positivos.

## 8. Riesgos y alternativas descartadas

- **Falsos positivos aceptados**: entre los 3.338 sin clase hay 93 imágenes, vídeos y correos y 127
  ficheros subidos en los 3 días del alta. El estándar y el restringido dejan de abrirlos; postventa y total
  no pierden nada. Es el precio de no depender del nombre.
- **Lo que no ve** (`progress/spec_F-164.md` §7): un parte fotografiado o escaneado con nombre genérico
  DENTRO de PV001 (cota: ≤ 33 ficheros subidos más de 3 días después del alta), o colgado como ficha
  PV006 o informe PV004 sin texto. Ni el contenido del fichero.
- **Descartadas**: la ventana de fechas (S6) como regla (depende de la resolución, que cambia al
  reabrir: la familia bailaría de una noche a otra); el login de quien sube (dato personal, y U2 sube
  también fichas); la extensión (los partes también son imágenes); una lista de lo que se CIERRA (una
  clase nueva quedaría abierta: R5).
- **Regex en dos motores**: los patrones evitan `\b`, `\m`, `\y` y clases POSIX; la sandbox (R10) lo
  comprueba.

## 9. Decisiones

| Decisión | Opciones | Recomendado | Decidido |
|---|---|---|---|
| D1 Criterio para reconocer un parte firmado | (a) solo el texto «parte firmado»: 7 cambian; (b) señales de texto (firma, código) + PV002 en cualquier tipo: 1.690; (c) **lista abierta** (PV001 en incidencia, PV006 en unidad, PV004 en tarea) **+ señales de texto**: 3.349, incluye los 3.338 partes sin clase de 2021-2023; (d) (c) + ventana de fechas sobre PV001: +2 fotos, inestable | (c) | |
| D2 Destino | (a) REPARACION, que `mcp-bbdd` ya restringe; (b) familia nueva (p. ej. `PARTE_FIRMADO`): exige cambiar `mcp-bbdd` (`origenes` y su R7) y, hasta entonces, nadie la abre, ni postventa | (a) | |
| D3 Trazabilidad | (a) columna `familia_documento` (la de F-156) al lado de `familia`; (b) sin columna: la huella vive solo en el CSV del despliegue; (c) (a) + `motivo_familia` (LISTA, FIRMA, CODIGO) | (a) | |
| D4 Los 8 de unidad (707) en REPARACION, huérfanos para el MCP | (a) aceptarlos: postventa y total los abren con aviso, el resto `PERMISO_DENEGADO`; (b) dejarlos en UNIDAD (3 dicen «parte firmado»: no); (c) feature en `mcp-bbdd` para cruzar por otra columna | (a) | |
| D5 Los 32 PDF de PV001 sin señal (nombre GUID, subidos en los 3 días del alta) | (a) abiertos: son del alta, no de una reparación; (b) restringir todo PDF de PV001 (+32) | (a) | |
