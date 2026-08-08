# CORRECCIÓN URGENTE — el corrector anterior excluía columnas esenciales

## Qué salió mal

La versión anterior de `fix_exclusiones_yaml.py` excluyó columnas que el
pipeline NECESITA. La más grave:

```
obrparpre    +1 nuevas: planif
```

**`planif` es la columna más crítica del proyecto**: la cadena de
planificación temporal de la que salen `stg.plan_mensual` (29 M de filas), el
mart y todo el cierre. Es de tipo `text` en SQL Server, así que el detector la
marcó como "problemática" y la excluyó.

También añadió exclusiones discutibles en `obr` (+21, incluida `res`),
`cen` (+8), `condir` (+`dir`) y `prv` (+7), que alimentan el schema `maestro`
y la cabecera del cierre.

Causa: el script tenía una lista de columnas protegidas, pero solo cubría las
tablas de compras/retenciones, y además **solo avisaba: no impedía la
exclusión**. Dos fallos en la misma función.

## PASO 1 — Restaurar (hazlo antes de nada)

```powershell
Copy-Item config\tables_sigrid.yaml.bak config\tables_sigrid.yaml -Force
```

## PASO 2 — Comprobar si el ingest llegó a hacer daño

```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema='raw' AND table_name='obrparpre' AND column_name='planif';
```

- **Devuelve `planif`** → no ha pasado nada. Sigue al paso 3.
- **No devuelve nada** → la tabla se recreó sin la columna. Recárgala:

```powershell
python main.py ingest --table obrparpre --full
python main.py stage
python main.py build-mart
python main.py reset-cierre
python main.py build-cierre
```

Conviene revisar también `obr`, `cen`, `condir` y `prv` con la misma consulta
si el ingest avanzó más allá de `con`.

## PASO 3 — Usar el script corregido

Sustituye `scripts/fix_exclusiones_yaml.py` por el de este ZIP.

```powershell
python scripts\fix_exclusiones_yaml.py --dry-run
python scripts\fix_exclusiones_yaml.py
python main.py ingest
```

## Qué cambia en el script

**1. Ámbito por defecto restringido.** Ahora solo procesa las 12 tablas nuevas
(compras + retenciones). Las 19 originales llevaban meses funcionando y no se
tocan. Para incluirlas hay que pedirlo con `--todas`, y aun así van
protegidas.

**2. La protección ahora protege de verdad.** Una columna de la lista NUNCA se
excluye, aunque Sigrid la declare como texto. Antes solo imprimía un aviso y
la excluía igualmente. Ahora se ve así:

```
obrparpre    [PROTEGIDA] planif es texto/binario pero el ETL la necesita: NO se excluye
condir       [PROTEGIDA] dir es texto/binario pero el ETL la necesita: NO se excluye
```

**3. Lista de protegidas ampliada** a todo el pipeline original: `planif`,
`can`, `pre`, `fas`, `amb` de `obrparpre`; `plafec`, `tex`, `res` de
`obrfasamb`; `cod`/`res`/`fec` de `con`; los decimales y fechas de `obr`; las
fechas y `coegar` de `obrctr`; `dir` y contacto de `condir`; `cif`/`raz` de
`prv`; y las de compras y retenciones que ya estaban.

Probado con la simulación de los tipos reales que devolvió tu Sigrid:
`planif` y `condir.dir` quedan protegidas, y por defecto solo se tocan
`dca` y `dcf` (las que faltaban).

## Verificación tras aplicar

```sql
-- planif debe seguir estando
SELECT column_name FROM information_schema.columns
WHERE table_schema='raw' AND table_name='obrparpre' AND column_name='planif';

-- y con datos
SELECT COUNT(*) FROM raw.obrparpre WHERE planif IS NOT NULL AND planif <> '';
```
