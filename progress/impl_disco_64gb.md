<!-- progress/impl_disco_64gb.md -->
# El disco del servidor compartido son 64 GB, y la puerta medía contra 32

Tarea acotada del 2026-09-07, aprobada por el humano a las 07:48 UTC. Rama
`feature/F-066-ingesta-raw-pendientes`. Cinco commits locales, ningún `push`.

## Qué estaba mal

El disco de `psql-albaranes-rs9k2` **se amplió de 32 a 64 GB el 2026-08-29**,
pero el job de Azure **no declaraba `PG_DISCO_TOTAL_GB`**, así que la puerta de
disco de F-019 usaba el defecto de `config/settings.py`, que seguía diciendo 32.

| medida del 2026-09-07 | contra 32 GB (lo que veía) | contra 64 GB (lo real) |
|---|---|---|
| 25.537.336.573 bytes ocupados | **74,32 %** | **37,16 %** |

La puerta aborta el build al **80 %**. Estaba a menos de seis puntos de tumbar
la nocturna todas las noches sin que nada estuviera mal, y la ingesta de F-066
suma ~0,9 GB, que la habría dejado en el 77 % ficticio.

## Qué cambió

**1. El defecto (`config/settings.py`).** `disco_total_gb` pasa de 32 a **64**,
con nota fechada en la `description`: cuándo se amplió, que este defecto es la
**última red** y no la configuración —el valor bueno lo inyecta el job—, y qué
pasó mientras divergieron. El valor **sigue viniendo de settings**: no se ha
cableado nada en la puerta.

**2. El comentario de la frontera (`postgres_client.py`).** Afirmaba que
`pg_database_size` sobre otra base exige `CONNECT` y que el rol del ETL lo tiene
«frontera medida en F-005». Eso tumbó la nocturna del 07. Reescrito con lo de
hoy: apareció `facturas` con dueño propio y sin `CONNECT`, y el humano concedió
el rol predefinido **`pg_read_all_stats`** a `sigrid_dm_etl`, que mide cualquier
base sin `CONNECT`, sin dar acceso a datos y **cubriendo las bases futuras** —que
es lo que de verdad falló—. Queda escrita la verificación: `pg_has_role(...)` da
`t` y la consulta devuelve las nueve bases.

**3. El barrido de los «32 GB».** Corregido en seis ficheros más. Lo histórico se
conserva **fechado** (el incidente del 2026-08-09 ocurrió sobre 32 GB de verdad):
se corrige lo que se afirma del presente, no el relato. `docs/referencia/` no se
ha tocado. El más peligroso era `infra/sql/03_diagnostico.sql`, donde el 32
entraba en el **cálculo** del espacio libre y lo dejaba corto en 32 GB enteros.
De paso, los inquilinos del disco pasan de los dos de F-005 a los **seis** de hoy
(`albaranes`, `partes`, `dedicacion`, `postventa`, `sigrid_dm`, `facturas`).

**4. La inyección (`infra/`).** `dev.json` declara `"discoTotalGb": 64` con su
`$aviso_`; `00_vars.ps1` la valida como clave obligatoria (falta → aborta antes
de llamar a la nube); `80_create_job.ps1` la pasa como `PG_DISCO_TOTAL_GB`, igual
que las `PG_VENTANA_*`. **No se ha ejecutado ningún `.ps1` ni ningún `az`.**

**5. Los tests.** Ver «Fase RED».

**6. La incidencia.** `progress/incidencia_nocturna_20260907.md` cierra con lo
resuelto (el `GRANT`, y por qué **se descarta la salida 2** —filtrar por permiso
dejaría la medición parcial y subestimando, que es el riesgo que la puerta
vigila—), el hallazgo del disco y lo que queda.

## Ficheros tocados

| fichero | qué |
|---|---|
| `config/settings.py` | defecto 32 → 64 + nota fechada |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | frontera `CONNECT` → `pg_read_all_stats`; «32 GB» de `BYTES_POR_GB` |
| `etl_sigrid/domain/tramos.py` | el porqué del troceo: disco y nº de inquilinos |
| `docs/ARCHITECTURE.md` | ficha del servidor + default de los settings de F-019 |
| `docs/runbook_postgres_azure.md` | cabecera, tabla del servidor, puerta de espacio |
| `infra/README.md` | relato del incidente, fechado |
| `infra/sql/03_diagnostico.sql` | el 32 entraba en el **cálculo**: 3 sitios |
| `infra/env/dev.json` | `discoTotalGb: 64` + `$aviso_` + el «32 GB» del aviso viejo |
| `infra/00_vars.ps1` | clave obligatoria |
| `infra/80_create_job.ps1` | `PG_DISCO_TOTAL_GB=$($CFG.discoTotalGb)` |
| `tests/test_f019_tramos.py` | defecto 64, override 128, **test nuevo** |
| `tests/test_f024_steps.py`, `tests/test_f025_build.py` | fixtures con el 32 |
| `progress/incidencia_nocturna_20260907.md` | sección de cierre |

## Decisiones de diseño

* **El defecto se sube, no se quita.** Se planteó dejarlo sin default para
  obligar a declararlo. Se descarta: `PostgresSettings` se instancia en tests y
  en local sin `.env`, y un campo obligatorio rompería eso. La red buena no es la
  ausencia de defecto, es el test que ata el defecto a `dev.json`.
* **`SQL_OCUPACION_DISCO` no se toca.** La salida 2 de la incidencia (filtrar por
  `has_database_privilege`) haría que la medición subestime en silencio, que es
  justo lo que la puerta existe para evitar. Con `pg_read_all_stats` no hace
  falta.
* **La clave va en `$clavesObligatorias` de `00_vars.ps1`.** Las `ventana*` no
  están y podrían haberse omitido igual, pero aquí el fallo es peor: sin la clave
  el job se crea sin la variable y vuelve al defecto **sin error**, que es
  exactamente lo que pasó estas dos semanas.
* **El override del test pasa de 64 a 128.** Con el defecto en 64, el test que
  comprobaba que `PG_DISCO_TOTAL_GB` se lee de verdad habría pasado sin leerla:
  un verde falso, la lección de F-025 T3.
* **Lo histórico se fecha, no se reescribe.** «Llenó el disco de 32 GB» era
  verdad el 2026-08-09; borrarlo perdería el porqué del troceo.

## Fase RED (evidencia)

Los dos tests se escribieron **antes** que el código. Salidas reales:

**R1 · el defecto es 64** — `python -m pytest tests/test_f019_tramos.py -k
"maximo_configurable_desde_settings" -p no:randomly --no-header -q`

```
        por_defecto = PostgresSettings(_env_file=None)
        assert por_defecto.tramo_max_filas == 1_000_000
>       assert por_defecto.disco_total_gb == 64
E       AssertionError: assert 32 == 64
E        +  where 32 = PostgresSettings(host='localhost', ..., disco_total_gb=32,
E                      disco_limite_pct=80.0, ...).disco_total_gb

tests\test_f019_tramos.py:171: AssertionError
1 failed, 39 deselected in 0.88s
```

**R2 · el defecto y `dev.json` no divergen** — `python -m pytest
tests/test_f019_tramos.py -k "disco_por_defecto_coincide" -p no:randomly
--no-header -q`

```
        dev = json.loads(
            (REPO_ROOT / "infra" / "env" / "dev.json").read_text(encoding="utf-8-sig")
        )
        assert (
>           dev["discoTotalGb"]
            == PostgresSettings.model_fields["disco_total_gb"].default
        ), (
E       KeyError: 'discoTotalGb'

tests\test_f019_tramos.py:204: KeyError
1 failed, 39 deselected in 0.86s
```

Los dos en verde tras el código: `39 passed` en `tests/test_f019_tramos.py`.

## Un tropiezo, contado

Al apartar temporalmente el test nuevo para no commitear un test en rojo, el
recorte se llevó por delante la cabecera de la sección R6 y su helper
`_sql_plan_mensual`, y dejó cuatro tests en `NameError`. Se detectó al ejecutar
la suite del fichero **después** del commit, se restauró el bloque y se enmendó
el commit (`89fe32d`). El historial queda limpio; se anota porque el error fue
mío y la lección es que un corte por índices de texto necesita verificación, no
confianza.

## Evidencias

| evidencia | valor |
|---|---|
| **Tests ejecutados** | **3872 passed, 159 skipped** (`bash harness/init.sh`). Eran 3871 antes: el test nuevo es el que suma |
| **Cobertura de líneas cambiadas** | **92,5 %** (662/716, umbral 80 %, nivel crítico) — línea `PUERTA COBERTURA` de `init.sh` |
| **Tiempo de la suite** | **282,54 s (4 min 42 s)**, medido por pytest en la pasada final |
| **Mutantes generados y supervivientes** | **No se lanza campaña, y el motivo:** el cambio de código ejecutable son **dos literales** (`32`→`64` en un default y en un cálculo SQL) y el resto son comentarios, documentación y JSON de despliegue. La mutación de `harness/mutacion` opera sobre el diff Python de una feature de `features.json`; esto no es una feature, y sobre un literal de configuración todo mutante sería equivalente o lo mataría el test de coherencia con `dev.json`. Dicho aquí en vez de omitirlo |

`bash harness/init.sh` termina en **`ENTORNO LISTO. Puedes trabajar.`**

## Verificaciones MANUAL pendientes (las hace el humano o el líder)

1. **Actualizar el job de Azure.** Nada de esto llega a producción hasta pasar
   por `80_create_job.ps1` o fijar la variable en el job: `85_update_job.ps1`
   solo cambia la imagen y **no toca el entorno**. Hasta entonces el job sigue
   midiendo contra 32 GB, aunque ahora el defecto del código ya diga 64 (así que
   una imagen nueva sin recrear el job **también** lo arregla).
2. **`azure-apps/red_postgresql_compartido.md`**: cinco inquilinos donde hay
   seis, y sin mención de `pg_read_all_stats`. Cruza la frontera del proyecto: lo
   actualiza el líder.
3. **T31b y T34 de F-025** siguen sin medir: hacen falta una o dos nocturnas
   buenas con el job ya actualizado.

## Fuera de alcance (no se ha hecho, a propósito)

`.env`, ejecutar `az` o cualquier `.ps1`, `azure-apps/`, y tocar la base mientras
corría la nocturna de las 07:48 UTC. La puerta de espacio libre del runbook
(«menos de 14 GB, PARA») se ha **dejado en 14** y anotado que ese margen se
calculó sobre los 32 GB de entonces: recalcularlo es una decisión de negocio, no
una corrección de un dato falso.
