# Fix — columna `med` binaria rompía el ingest

## Qué pasaba

```
psycopg.errors.UndefinedColumn: no existe la columna «med» en la relación «ctrpro»
```

`ctrpro`, `dcapro` y `dcfpro` tienen una columna **`med`** (medición desglosada,
tipo `image` en SQL Server). El ETL la descarta al CREAR la tabla en Postgres
—no sabe mapear un binario— pero la pedía en el SELECT a Sigrid porque no
estaba en `exclude_columns`. La API devolvía esa columna de más y el `COPY`
fallaba.

Ese fallo cortó el ingest antes de llegar a `cob`, `pag` y `rec`, por eso
`build-retenciones` dijo "no existe raw.rec" y los `inspect` no encontraban las
vistas. Un único fallo, tres síntomas.

## Qué se ha cambiado

Solo `config/tables_sigrid.yaml`. Se añade `med` a las exclusiones de las tres
tablas de líneas:

| Tabla | exclude_columns |
|---|---|
| `ctrpro` | tex, **med**, desesp, texcom |
| `dcapro` | tex, **med**, desesp, texcom |
| `dcfpro` | tex, **med**, desesp, texcom, serdesdat |

`main.py` y los SQL NO cambian: siguen siendo válidos.

Las tablas de retenciones (`cob`, `pag`, `rec`) están libres de este problema:
el diagnóstico mostró que todas sus columnas son int/float/varchar.

## Cómo continuar

```powershell
# 1. Sustituye config/tables_sigrid.yaml
# 2. Relanza (ctrpro quedó vacía, se recargará entera)
python main.py ingest

# 3. Ahora sí
python main.py build-compras
python main.py build-retenciones

python main.py inspect-retenciones --obra 0707
python main.py inspect-retenciones-vencidas --sentido CLIENTE
```

## Preflight: detectar el problema antes de que ocurra

Si alguna otra tabla falla con el mismo error, es el mismo patrón. Esta
consulta contra Sigrid lista TODAS las columnas binarias o de texto ilimitado
de las tablas nuevas, para poder excluirlas de una vez:

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo'
  AND TABLE_NAME IN ('com','comlin','comprv','ctrpro','dca','dcapro',
                     'dcf','dcfpro','dcfprodes','cob','pag','rec')
  AND DATA_TYPE IN ('text','ntext','image','xml','varbinary','binary')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

Lánzala con tu script de diagnóstico o desde SSMS. Todo lo que salga ahí y no
esté ya en `exclude_columns` provocará el mismo error. Si aparece algo nuevo,
pásamelo y actualizo el YAML de una pasada.
