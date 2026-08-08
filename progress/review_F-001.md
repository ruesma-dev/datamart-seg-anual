<!-- progress/review_F-001.md -->
# Review F-001 — Comando 'version' en el CLI

**Veredicto: APROBADO.**

Revisión hecha por el agente principal, no por el subagente `reviewer`
(ver nota al final).

## Recorrido de CHECKPOINTS.md

### C1 — Arnés completo y en verde
- [x] `bash harness/init.sh` termina en 0. **22 tests** (15 previos + 7 nuevos).
- [x] Presentes CLAUDE.md, features.json, SPECS.md, current.md, history.md,
      ARCHITECTURE.md, CONVENTIONS.md.

### C2 — Estado coherente
- [x] Una sola feature `in_progress` durante el desarrollo (F-001).
- [x] Rama `feature/F-001-cli-version`, creada desde `dev` en b979b82.
- [x] `progress/current.md` solo describe esta sesión.
- [x] Resumen en `progress/history.md` al cerrar.

### C3 — Arquitectura y convenciones
- [x] Sin tocar dominio ni capas SQL. El cambio vive en `config/` y `main.py`.
- [x] Primera línea con ruta relativa en los ficheros nuevos/tocados.
- [x] Sin `print()`: la salida del comando usa `click.echo`, que es su
      producto, no traza de depuración.
- [x] Sin secretos. Sin dependencias nuevas: `platform` es stdlib.

### C4 — Verificación real
- [x] R1 → `test_f001_r1_etl_version_es_semver_no_vacio`
- [x] R2 → `test_f001_r2_version_sale_con_codigo_cero`,
      `test_f001_r2_version_no_carga_la_configuracion`,
      `test_f001_r2_version_aparece_en_la_ayuda`
- [x] R3 → `test_f001_r3_image_tag_desde_entorno`,
      `test_f001_r3_image_tag_local_si_no_hay_entorno`,
      `test_f001_r3_build_date_desde_entorno`
- [x] R4 → los siete usan `CliRunner`; ninguno abre socket ni conexión.
- [x] Sin verificaciones MANUAL pendientes.

### C5 — Cierre
- [x] `sdd=false`, luego no hay `tasks.md`. Un commit por tarea:
      T0 backlog y arranque, T1 comando, T2 tests, T3 sellado de imagen.
- [x] Árbol limpio, sin artefactos sueltos.
- [x] `features.json` marcado `done`.

## Comprobaciones adicionales

- **No regresión del CLI**: el atajo `ctx.invoked_subcommand == "version"`
  podía dejar sin configurar el resto de comandos. Comprobado que no:
  `python main.py check-pg` sigue cargando settings y conecta
  (`PostgreSQL 16.4`). `--help` lista los 30+ comandos sin cambios.
- **Ejecución real**: `python main.py version` → exit 0, `image: local`.
  Con `IMAGE_TAG`/`BUILD_DATE` en el entorno los refleja.

## Hallazgos fuera del alcance de F-001

Ninguno bloquea el cierre; quedan anotados para decidir aparte.

1. **Finales de línea de los `.ps1`**: los cinco ficheros de `infra/` están
   en LF en el árbol de trabajo, y `docs/CONVENTIONS.md` pide CRLF con BOM.
   Es preexistente (git normalizó al commitear, avisó con "CRLF will be
   replaced by LF"). Se arregla con un `.gitattributes`:
   `*.ps1 text eol=crlf`. Encaja mejor dentro de F-003.
2. **`main.py` empieza con dos líneas en blanco** antes de su comentario de
   ruta, lo que incumple C3 en sentido estricto. Preexistente; no lo toco
   para no mezclarlo con esta feature.
3. **`ruff` no está instalado** en el venv ni declarado en
   `requirements.txt`, pese a estar configurado en `pyproject.toml` y citado
   en las convenciones. `init.sh` no lo ejecuta, así que hoy el lint no se
   verifica en ningún sitio.

## Nota de proceso

El flujo del arnés prevé subagentes `implementer` y `reviewer` con informes
separados. En esta sesión la implementación y la revisión las hizo el agente
principal, por indicación de la configuración de sesión de no lanzar
subagentes sin petición explícita. El rastro documental (este informe,
`current.md`, commits por tarea) se mantiene igual.
