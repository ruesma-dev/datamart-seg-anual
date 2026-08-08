# Integración COMPRAS en main.py y tables_sigrid.yaml (archivos completos)

Ambos archivos son TUS versiones reales de hoy + el módulo compras integrado.
Sustituyen directamente a los actuales.

## Contenido

```
main.py                                  ← COMPLETO (2.806 líneas, 38 comandos)
config/tables_sigrid.yaml                ← COMPLETO (28 tablas)
etl_sigrid/infrastructure/postgres/sql/compras/   ← los 4 SQL (sin cambios)
```

## Qué se añadió (y qué NO se tocó)

main.py: tus 33 comandos intactos (verificado por diff de decoradores:
build-cierre, build-maestros, inspect-todo*, find-obra, etc. — CERO perdidos).
Añadidos 5 al final, antes del if __name__:

    build-compras                  construye el schema compras (4 SQL)
    reset-compras                  DROP SCHEMA compras
    inspect-contrato-consumo       --codigo / --obra / --umbral 90
    inspect-proveedores-obra       --obra 0707 [--anio 2026]
    inspect-albaranes-sin-facturar [--obra] [--proveedor]

tables_sigrid.yaml: tus 19 tablas intactas. Añadidas 9 al final:
com, comlin, comprv, ctrpro, dca, dcapro (page_size 5000), dcf,
dcfpro (page_size 5000), dcfprodes.

## Ejecución

```powershell
python main.py ingest           # ahora sí trae las 9 tablas nuevas (~10-15 min)
python main.py build-compras
python main.py inspect-contrato-consumo --umbral 90
```

Nota: si ya ejecutaste scripts/compras_setup.py --all, las tablas raw ya
existen; el ingest normal las verá creadas con otro esquema de columnas
(el script no añade _source_tiemod). En ese caso, antes del primer ingest:

```sql
DROP TABLE IF EXISTS raw.com, raw.comlin, raw.comprv, raw.ctrpro,
    raw.dca, raw.dcapro, raw.dcf, raw.dcfpro, raw.dcfprodes CASCADE;
```

y deja que el ingest oficial las cree a su manera. El schema compras se
regenera después con build-compras.
