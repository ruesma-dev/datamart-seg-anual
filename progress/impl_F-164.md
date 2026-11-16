# F-164 · Informe del implementer (rigor `critico`, pasada principal)

Rama `feature/F-164-partes-firmados-restringidos`, checkout principal (con `.env`). Spec aprobada el
2026-11-16 (D1 c, D2-D5 a). La campaña de mutación (T7) NO va en esta pasada: tras el APPROVED.

## Qué cambió

- **Dominio** (`etl_sigrid/domain/postventa.py`, bloque nuevo tras R20): `GRATIPIDE_FOTOS_INCIDENCIA`
  (34), `GRATIPIDE_INFORMES` (37), `GRATIPIDE_FICHA_INMUEBLE` (39), `LISTA_ABIERTA` {(708,34),
  (707,39), (47,37)}, `PATRON_SENAL_FIRMA` y `PATRON_SENAL_CODIGO` (literales de la spec),
  `senal_parte_firmado(nombre, descripcion)` (S2 sobre nombre + ' ' + descripción, S3 solo nombre;
  `None` = '', bordes recortados como `BTRIM`) y `familia_publicada(tip, gratipide, nombre,
  descripcion)`. `familia_adjunto` y `ORIGEN_POR_FAMILIA` intactas.
- **SQL** (`sql/postventa/06_adjuntos.sql`): la expresión de F-156 sigue en la CTE como
  `familia_documento`; `familia` es un `CASE` seguro ante `NULL` (`(lista) IS TRUE AND (señales) IS
  FALSE THEN b.familia_documento ELSE 'REPARACION'`); `familia_documento` publicada justo detrás de
  `familia`. Cabecera (bloques FAMILIA_DOCUMENTO y FAMILIA) y `COMMENT ON TABLE` reescritos. PK,
  índices, guarda R21, `FROM`/`JOIN` y demás columnas, sin cambios.
- **Diccionario v79**: ficha `postventa.documento_adjuntos` (criterio, «parte firmado o posible
  parte», 2021-2023 sin clase, lo que NO VE, huérfanos de 707, columnas `familia` y
  `familia_documento`, `clase_grafico_id` nula = REPARACION), `postventa_restringida.contactos_incidencia`
  (los 8 huérfanos de 707), `raw.auxgra` (PV002 ya no es la única marca), `R-POSTVENTA-RESTRINGIDA`
  (`regla`; el `resumen` servido no cambia) y entrada de historial `# version 79 (F-164, ...)`.
- **`docs/ARCHITECTURE.md`**: párrafo de `postventa`, la regla, `familia_documento`, los huérfanos y
  «`mcp-bbdd` no cambia».
- **`tests/test_f156_ingesta_sql.py::test_f156_r20_...`**: espera `AS familia_documento`, con el
  motivo escrito en el propio test (D3).
- **`azure-apps/datamart_seg_anual.md`** §«La postventa»: párrafo F-164 SIN DESPLEGAR y la fila de la
  tabla de objetos. `git pull --rebase` antes (sin conflicto: «Current branch main is up to date»).

### Decisiones y desviaciones (justificadas)

1. **`familia_publicada(None, ...)` = REPARACION.** El design §3 decía «None si el tipo no es de
   postventa»; R4 dice «si el tipo o la clase llegan nulos, REPARACION» y el design §5 lista «todo con
   `None` en tipo o clase» entre los restringidos. Manda el requisito: tipo nulo → REPARACION; un tipo
   que no es de postventa (p. ej. 41) → `None`, como `familia_adjunto`. En el SQL no existe tipo nulo
   (el `JOIN` filtra `c.tip IN (47, 707, 708)`).
2. **El `CASE` de `familia` va en el `SELECT` final**, no en la CTE (design §4): envuelve
   `b.familia_documento` en vez de duplicar su expresión y lee `b.nombre_fichero`, `b.descripcion`
   (ya `NULLIF(BTRIM(...), '')`) y `b.clase_grafico_id` (ya `NULLIF(gratipide, 0)`). Mismo resultado:
   `gratipide` 0 o `NULL` no está en la lista → REPARACION, igual que en el dominio.
3. **Sandbox con base ICU `und`.** Medido en Azure (solo lectura, 2026-11-16): `en_US.utf8`, y su
   `upper('á…ñ…ó')` sube los acentos. Un clúster local en locale `C` NO los sube (medido:
   `upper('… confirmación')` = `… CONFIRMACIóN`). La sandbox crea la base con `LOCALE_PROVIDER icu
   ICU_LOCALE 'und'` para reproducir Azure. En un servidor en `C` la divergencia solo puede
   RESTRINGIR de más (una minúscula acentuada pegada a «FIRMA» contaría como no-letra), nunca abrir.

## Fase RED (evidencia pegada)

**1. Tests nuevos sobre el código de hoy** (HEAD `60ebf8d`, sin cambios en `etl_sigrid`, `config`,
`docs` ni `tests` respecto a `e818dc2`; comando `.venv/Scripts/python.exe -m pytest
tests/test_f164_dominio.py tests/test_f164_sql.py tests/test_f164_diccionario.py
tests/test_f164_sandbox.py -q -p no:cacheprovider`):

```
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[708-None-VIV 1 - RS24.11-0123.pdf-PARTE FIRMADO]
  (… los 7 de R8, uno por línea …)
E       AttributeError: module 'etl_sigrid.domain.postventa' has no attribute 'familia_publicada'
FAILED tests/test_f164_sql.py::test_f164_r9_la_lista_abierta_del_sql_es_la_del_dominio
E       AssertionError: falta el CASE de `familia` seguro ante NULL (design §4)
FAILED tests/test_f164_sql.py::test_f164_r11_columnas_y_orden - ValueError: 'familia_documento' is not in list
FAILED tests/test_f164_diccionario.py::test_f164_r12_columnas_familia_y_familia_documento
E       AssertionError: assert ['adjunto_id'...documento_id'] == ['adjunto_id'...ia_documento']
FAILED tests/test_f164_diccionario.py::test_f164_r13_architecture_describe_la_regla
FAILED tests/test_f164_diccionario.py::test_f164_r13_azure_apps_describe_la_regla
266 failed, 4 passed, 6 skipped in 16.15s
```

Los 4 que pasan son guardas de lo que NO debe cambiar (`familia_adjunto` intacta, la regla de hoy deja
abiertos a los 7, PK e índices, ficha = columnas del SQL); los 6 `skip`, la sandbox sin DSN.

**2. Ruptura deliberada del dominio ya escrito** (`familia_publicada` devolviendo la familia por
documento, la regla de F-156; copia de seguridad y restaurado):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f164_dominio.py -q -p no:cacheprovider -k "r8_los_siete"
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[708-None-VIV 1 - RS24.11-0123.pdf-PARTE FIRMADO]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[708-None-B1C - RS24.11-0456.pdf-PARTE FIRMADO]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[708-34-RS25.07 - 0321 FIRMADO.pdf-PARTE FIRMADO]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[708-None-0601 - RS26.10 - 0789 PARTE FIRMADO.pdf-None]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[707-35-VIV 2 - RS24.11-0124.pdf-PARTE FIRMADO]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[707-35-B2D - RS24.11-0457.pdf-PARTE FIRMADO]
FAILED tests/test_f164_dominio.py::test_f164_r8_los_siete_partes_quedan_en_reparacion[707-35-VIV 3 - RS24.12-0125.pdf-PARTE FIRMADO]
E       AssertionError: assert 'INCIDENCIA' == 'REPARACION'
7 failed, 243 deselected in 1.48s
```

**3. Sandbox (R10) contra el SQL de `e818dc2`** y contra una ruptura deliberada del `CASE` (la clase
nula de 708 abierta), Postgres 16 local desechable:

```
$ F164_SANDBOX_DSN=postgresql://postgres@127.0.0.1:55164/postgres .venv/Scripts/python.exe -m pytest tests/test_f164_sandbox.py -q -p no:cacheprovider
# con el 06_adjuntos.sql de e818dc2:
E           psycopg.errors.UndefinedColumn: column "familia_documento" does not exist
FAILED tests/test_f164_sandbox.py::test_f164_r10_cada_familia_es_la_del_oraculo   (y los otros 4)
# con `(b.clase_grafico_id = 34 OR b.clase_grafico_id IS NULL)` en la pareja de 708:
E       AssertionError: [(16, 708, 0, 'UNTITLED_1_2.pdf', None, 'INCIDENCIA', ...), (17, 708, None, 'foto.jpg', None, 'INCIDENCIA', ...), (22, 708, 0, 'imagen.jpg', '', 'INCIDENCIA', ...)]
FAILED tests/test_f164_sandbox.py::test_f164_r10_cada_familia_es_la_del_oraculo
1 failed, 5 passed in 3.99s
```

## Verde

- `pytest tests/test_f164_dominio.py tests/test_f156_dominio.py` → **323 passed**.
- `pytest tests/test_f164_sql.py tests/test_f156_ingesta_sql.py tests/test_f156_pipeline.py` →
  **63 passed** (tras T3).
- `pytest tests/test_f164_diccionario.py tests/test_f156_diccionario.py tests/test_f006_fichas.py` →
  R12 en verde tras T5; R13 (2) en verde tras T6 (`-k r13`: 2 passed).
- **Sandbox R10 (T4), ejecutada por el implementer** con un Postgres 16 local desechable (`initdb` en el
  scratchpad, puerto 55164, `trust`, ya parado): **6 passed in 3.84s**, sin `skip`. Para repetirla:
  `pg_ctl -D <scratchpad>/pg164 -o "-p 55164" start` y el comando de arriba.

## Previsión en Azure (solo lectura, 2026-11-16, `f164_prevision.py` del scratchpad)

El `CASE` literal del `06_adjuntos.sql` nuevo aplicado a la tabla publicada hoy (solo recuentos):

| antes | después | tipo | enlaces |
|---|---|---|---:|
| INCIDENCIA | INCIDENCIA | 708 | 6.729 |
| INCIDENCIA | **REPARACION** | 708 | 3.341 |
| REPARACION | REPARACION | 708 | 4.489 |
| TAREA | TAREA | 47 | 699 |
| UNIDAD | **REPARACION** | 707 | 8 |
| UNIDAD | UNIDAD | 707 | 822 |

**3.349 cambian** (3.341 + 8), exactamente la cifra de la spec; ninguno sale de REPARACION; 16.088
enlaces. Con el mismo motor (ARE de PostgreSQL 16.15 en Azure).

## Salida de `bash harness/init.sh`

**NO TERMINADA EN VERDE: T12 pendiente.** Dos ejecuciones de `bash harness/init.sh`, tal cual:

1. **Primera: ROJA**, por un fallo REAL que provocó F-164 y ya está arreglado:
   `test_f006_los_recuentos_de_current_son_los_de_hoy` («`current.md` no dice el número real de
   columnas (2743)»: `familia_documento` sube el diccionario de 2742 a 2743 columnas). Resultado:
   `1 failed, 675 passed, 1 skipped in 1695.19s` (pytest para en el primer fallo) y, por eso,
   `PUERTA COBERTURA: 45.8% de 24 líneas` (la suite solo llegó al 4 %; los tests de F-164 no
   corrieron). TAMAÑO, CARRIL (N/A, `critico`), CAPA E2E (N/A) y rama, en `[OK]`. Arreglo:
   `2f77308` (current.md con el recuento de v79); `pytest tests/test_f006_contexto.py -k recuentos`
   → 1 passed.
2. **Segunda: INTERRUMPIDA por Claude Code por falta de memoria del equipo** (no es un fallo de la
   puerta) al **85 % de pytest, sin ningún fallo hasta ahí**. Por la nota del sistema no la he
   relanzado. La tiene que relanzar el líder (o el humano) con el equipo despierto y con memoria:
   `bash harness/init.sh`, y dar por buenas las líneas `PUERTA COBERTURA` y `PUERTA CARRIL` de esa
   ejecución.

## Commits

| SHA | Mensaje |
|---|---|
| `b9ae8d7` | F-164 T1: tests R1-R13 en rojo (dominio, SQL, diccionario) y sandbox R10 con F164_SANDBOX_DSN |
| `5bcb810` | F-164 T2: dominio, lista abierta, señales de firma y código y familia_publicada |
| `5045a82` | F-164 T3: SQL, familia con la lista abierta y las señales, segura ante NULL, y familia_documento |
| `352c134` | F-164 T4: sandbox R10 con base ICU (upper con acentos, como Azure) |
| `4e63b8e` | F-164 T5: diccionario v79 (ficha, regla, contactos_incidencia, auxgra) |
| `0dab130` | F-164 T6: ARCHITECTURE.md (azure-apps f61570b, commit aparte, sin push) |
| `2f77308` | F-164: current.md con el recuento del diccionario v79 (2743 columnas) |
| **azure-apps `f61570b`** | F-164: datamart_seg_anual.md, los partes firmados siempre en REPARACION y familia_documento (SIN DESPLEGAR). `main` queda **ahead 2** de `origin/main`: uno ajeno (`3029b50`, F-100 de albaranes) y este. **Sin push**: el humano hace `git -C azure-apps pull` y después `push` |

## Pendiente (MANUAL y fuera de esta pasada)

- **T7, campaña de mutación** (`critico`): en la pasada de campaña, tras el APPROVED.
  `python -m harness.mutacion --feature F-164`; las líneas cambiadas de `domain/postventa.py`.
- **T8 / T10, huella antes y después** (líder, solo lectura): preparado, NO ejecutado,
  `<scratchpad>/f164_huella.py antes` (el día del despliegue, tras la nocturna) y `… despues` tras la
  ejecución puntual; escribe `f164_huella_{antes,despues}.csv` (solo `adjunto_id`, familias y md5) y
  saca R14 (mismo conjunto, md5 iguales, `familia_documento` = familia de antes, cambios por pareja) y
  R15 (consulta con los literales del dominio; esperado 0).
- **T9, despliegue** (humano): merge, `infra/70_build_image.ps1`, `infra/85_update_job.ps1 -Tag
  <nuevo>`, ejecución puntual sin ingesta `build-postventa && apply-grants && publicar-diccionario`;
  vuelta atrás `85_update_job.ps1 -Tag r20261116-1018`.
- **T11 / R16** (humano o sesión `mcp`): reiniciar `mcp-bbdd`, abrir un 708 y un 707 movidos con los
  cuatro perfiles, avisar para cerrar DH10 y de los 8 huérfanos de 707.
- **T12**: `bash harness/init.sh` en verde, SIN CUMPLIR (ver «Salida de init.sh»).

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados (suite) | Puerta del líder (2026-11-16, HEAD 4e5ef33): 13525 passed, 2532 skipped en 2 h 12 min. `ENTORNO LISTO` |
| Tests de F-164 | dominio 250, SQL 9, diccionario 11 (R13 azure-apps no `skip`: está al lado), sandbox 6 con DSN (6 `skip` sin él, en la puerta) |
| Cobertura de líneas cambiadas | `PUERTA COBERTURA: 100.0% de 24 líneas cambiadas cubiertas (24/24, umbral 90% del nivel critico)` (puerta del líder) |
| Mutantes generados / supervivientes | No en esta pasada: T7, pasada de campaña tras el APPROVED (nivel `critico`, exigida) |
| Tiempo de la suite | 1ª pasada: 1695 s hasta el primer fallo (4 %); la completa no terminó |
| Capa e2e | N/A (sin interfaz de navegador; ver línea `CAPA E2E` de la puerta) |
