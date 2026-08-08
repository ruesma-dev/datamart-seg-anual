<!-- progress/current.md -->
# Trabajo en curso

## F-001 — Comando 'version' en el CLI

- Estado: `in_progress`
- Rama: `feature/F-001-cli-version` (desde `dev` en b979b82)
- Modo: `sdd=false`. Los criterios `acceptance` de `harness/features.json`
  hacen de mini-spec; se trazan como R1..R4.

### Requisitos (de acceptance)

- **R1** — Existe constante `ETL_VERSION` en `config/settings.py`.
- **R2** — `python main.py version` imprime la versión y sale con código 0.
- **R3** — La salida incluye el tag de imagen leído de `IMAGE_TAG` cuando
  está definida, y `local` cuando no.
- **R4** — Test en `tests/` que valida la salida con `CliRunner`, sin tocar
  red ni BBDD.

### Decisión de diseño

El callback del grupo `cli()` llama a `get_settings()`, que exige
`SIGRID_API_BASE_URL` y `SIGRID_API_FUNCTION_KEY`. Sin `.env` aborta, así
que *cualquier* comando falla en un contenedor mal configurado — incluido
`version`, que es justo el que necesitas para diagnosticar ese caso. Por eso
`version` se salta la carga de settings vía `ctx.invoked_subcommand`.

### Verificaciones MANUAL (humano)

Ninguna pendiente: R1–R4 se verifican con pytest. La comprobación del tag
real de imagen llega con F-003, al desplegar:

    az containerapp job start -g rg-seguimiento-dev -n caj-datamart-seg
    # y revisar en logs la línea 'image:' del arranque
