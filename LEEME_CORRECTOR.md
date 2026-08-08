# Corrector automático de exclude_columns

## Por qué

Llevamos tres iteraciones con el mismo error, una columna cada vez:

```
no existe la columna «med»    en la relación «ctrpro»
no existe la columna «eiotex» en la relación «dca»
no existe la columna «eittra» en la relación «dca»
```

Adivinar los nombres no funciona: `dca` tiene 142 columnas y varias son de
tipo texto/binario. La causa es que el ETL descarta esas columnas al CREAR la
tabla en Postgres pero las pide en el SELECT si no están en `exclude_columns`.

## La solución: que lo diga Sigrid

`scripts/fix_exclusiones_yaml.py` pregunta a Sigrid, tabla por tabla, qué
columnas son de tipo `text/ntext/image/xml/varbinary/binary` y actualiza el
YAML solo. Se acabaron las iteraciones.

```powershell
# 1. Ver qué haría (no toca nada)
python scripts\fix_exclusiones_yaml.py --dry-run

# 2. Aplicarlo
python scripts\fix_exclusiones_yaml.py

# 3. Continuar
python main.py ingest
python main.py build-compras
python main.py build-retenciones
```

## Garantías

- **No quita exclusiones**: hace la unión de lo que ya tenías con lo detectado.
- **Conserva comentarios**, tanto de bloque como en línea
  (`- ima    # imagen del concepto, binario pesado` se mantiene tal cual).
- **Conserva el orden**: las exclusiones existentes se quedan donde estaban y
  las nuevas se añaden al final, así el diff es mínimo.
- **Copia de seguridad** en `tables_sigrid.yaml.bak` antes de escribir.
- **Valida antes de guardar**: si el YAML resultante no fuese válido o se
  hubiera perdido alguna tabla, aborta sin tocar el archivo.
- **Protege las columnas necesarias**: lleva la lista de las que usan los SQL
  de compras y retenciones; si alguna fuese de tipo texto/binario avisaría en
  pantalla en vez de romper el módulo en silencio.

Probado contra tu `tables_sigrid.yaml` real: 19 tablas, 87 comentarios
conservados, diff compuesto solo por adiciones.

## También incluido

`config/tables_sigrid.yaml` con las 31 tablas (compras + retenciones) y las
exclusiones conocidas hasta ahora. Úsalo como base y luego lanza el corrector,
que completará lo que falte consultando a Sigrid.

## Nota sobre la causa de fondo

Esto es un parche a un comportamiento del ETL que sería mejor arreglar en
origen: `ingest_raw_step.py` debería construir el SELECT a partir de las
columnas que realmente ha creado en Postgres, no de todas las descubiertas
menos las excluidas. Así el `exclude_columns` del YAML volvería a ser lo que
dice su nombre —una preferencia de negocio, no una obligación técnica— y este
error no podría repetirse con ninguna tabla futura. Si me pasas
`etl_sigrid/application/steps/ingest_raw_step.py` y
`etl_sigrid/infrastructure/postgres/postgres_client.py`, lo dejo cerrado.
