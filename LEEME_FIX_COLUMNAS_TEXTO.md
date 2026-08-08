# Fix definitivo — columnas de texto/binario que rompían el ingest

## El patrón del fallo

```
psycopg.errors.UndefinedColumn: no existe la columna «med» en la relación «ctrpro»
psycopg.errors.UndefinedColumn: no existe la columna «eiotex» en la relación «dca»
```

El ETL descubre las columnas por INFORMATION_SCHEMA, **descarta las de tipo
texto ilimitado o binario al CREAR la tabla** en Postgres (no sabe mapearlas),
pero **sí las pide en el SELECT** si no están en `exclude_columns`. Resultado:
la API devuelve una columna de más y el `COPY` falla.

Iba apareciendo de una en una (`med` en ctrpro, `eiotex` en dca, y habrían
seguido `dirtex`, `obs`…). Esta corrección lo cierra de raíz.

## La solución

Las 9 tablas de compras comparten ahora **la misma lista completa** de nombres
de columna texto/binario que usa Sigrid en documentos:

```
tex, med, des, obs, ima, emptex, dirtex, eiotex,
desesp, texcom, serdesdat, texobs, coestr
```

Excluir un nombre que la tabla no tiene es **inofensivo**: el ETL filtra por
nombre y simplemente no encuentra coincidencia. Por eso se aplica la lista
entera a todas en lugar de ir descubriéndolas por ensayo y error.

Verificado antes de empaquetar: **ninguna** de esas columnas la necesitan los
SQL del schema `compras` (se comprobó columna a columna contra las 9 tablas).

`cob`, `pag` y `rec` no se tocan: el diagnóstico volcó sus columnas completas
y todas son int/float/varchar.

Las 19 tablas originales tuyas quedan **exactamente igual** (verificado por
comparación con el YAML que subiste).

## Qué se entrega

Solo `config/tables_sigrid.yaml`. `main.py` y los SQL no cambian.

## Cómo continuar

```powershell
# Sustituye el YAML y relanza
python main.py ingest

python main.py build-compras
python main.py build-retenciones

python main.py inspect-contrato-consumo --umbral 90
python main.py inspect-retenciones --obra 0707
python main.py inspect-retenciones-vencidas --sentido CLIENTE
```

Las tablas que quedaron a medias (`ctrpro`, `dca`) se recargarán enteras: el
COPY hizo rollback, así que están vacías y el cursor incremental parte de cero.
