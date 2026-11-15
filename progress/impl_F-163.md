# F-163 · Informe del implementer (`estandar`, sdd=false)

La reconstrucción completa solo en las noches del fin de semana y techo del job de 14 h.

## Qué cambió

- **`toca_reconstruccion_completa`** (`etl_sigrid/domain/ventana.py`): el sábado dispara si no
  se hizo hoy; el domingo solo si no hay completa ni del sábado ni del domingo
  (`ultima.date() < hoy - 1 día`); de lunes a viernes **nunca**, aunque pasen 7, 8 o 20 días;
  sin ninguna registrada (`None`) dispara cualquier día (D2). Se quita el parámetro
  `dias_maximos`: la antigüedad ya no dispara. Motivos nuevos, en español, que nombran el día.
- **`DIAS_MAXIMOS_SIN_COMPLETA` = 7** se queda solo como umbral de «completa vencida» de
  `check-ventana` (`main.py:2026`, sin cambios de lógica; lo cubre
  `test_f025_r26_una_completa_vencida_se_denuncia`, en verde).
- Constantes `SABADO = 5` (nueva), `DOMINGO = 6` y `NOMBRES_DIA`.
- **`VENTANA_REANUDACION`** (`etl_sigrid/domain/reanudacion.py`): 8 h -> 15 h.
- **`infra/env/dev.json`**: `replicaTimeoutSeconds` 25200 -> 50400 y `$aviso_replicaTimeoutSeconds`
  con el porqué (2026-11-15, 14 h por decisión del humano, ligado a la ventana de 15 h).
  `85_update_job.ps1` NO aplica el techo (solo `80_create_job.ps1` lo usa al crear): en el
  despliegue hace falta `az containerapp job update --replica-timeout 50400` (lo lanza el humano).
- Textos: ayudas de `--reconstruir-todo` y de `check-ventana` en `main.py`, descripción de
  `ventana_dia_completa` (`config/settings.py`), comentarios de `build_stg_step.py`,
  `ventana_sql.py` (docstring y el `detalle` de la firma divergente: «la pone al dia la completa
  del fin de semana»), `infra/97_create_alert_ventana.ps1` (comentario) y `docs/ARCHITECTURE.md`.
- Diccionario **v77 -> v78**: `stg.yaml` (2 pasajes), `_meta.yaml` (3: motivo `completa`,
  `v_frescura_obra`, `firma_divergente`) y `00_global.yaml` (consulta de obras vivas + comentario
  de versión). Sin objetos ni columnas nuevos: 320 objetos, 2742 columnas, 157 de consumo.
- `progress/current.md`: nota de F-163 en curso.

## Decisión de diseño (desviación justificable, para el reviewer)

`PG_VENTANA_DIA_COMPLETA` (`ventana_dia_completa`, default 6) **pasa a ser el ÚLTIMO día de la
ventana**: la completa va la víspera (`(dia - 1) % 7`) y ese día solo como reserva. Motivo: el
job desplegado lleva `PG_VENTANA_DIA_COMPLETA=6` en su entorno y `85_update_job.ps1` no lo
reescribe; si el ajuste significara «el día principal» habría que cambiarlo a 5 en Azure, y con
el 6 heredado la completa caería el domingo y la reserva el LUNES (un laborable). Con esta
lectura el 6 ya desplegado da exactamente sábado + domingo sin tocar el entorno del job, y
`dev.json` (`ventanaDiaCompleta: 6`) y `test_f025_settings` siguen cuadrando. Se mantiene el
nombre del parámetro `dia_semana` (firma compatible con `build_stg_step.py:669`, que lo pasa
posicional).

## Fuera del alcance / pendiente

- Specs históricas de F-025 y F-148 (`specs/`) siguen diciendo domingo / 8 h: son historia.
- Los tests de `test_f025_build.py`/`test_f157_step.py` que usan un domingo con la última
  completa el 2026-09-01 siguen siendo válidos (domingo sin la del sábado dispara); no se tocan.
- **Despliegue (humano):** imagen nueva + `az containerapp job update --replica-timeout 50400`.
  Publicar el diccionario v78 con su imagen. Push de la rama y de `azure-apps`.

## Commits

| SHA | Mensaje |
|---|---|
| `1fe5344` | F-163 T1: la completa solo el sabado (y el domingo si falta la del sabado); entre semana nunca |
| `337f960` | F-163 T2: techo del job a 14 h (replicaTimeoutSeconds 50400) y ventana de reanudacion a 15 h |
| `cc567f1` | F-163 T3: textos, ayudas de la CLI y diccionario v78 con la completa del fin de semana |

**Ecosistema** (`C:\Users\pgris\PycharmProjects\azure-apps`, rama `main`, `git pull --rebase`
«Already up to date» antes de editar): commit **`006b293`** «F-163: datamart_seg_anual, la
completa solo en fin de semana y techo del job de 14 h». Solo `datamart_seg_anual.md`: la frescura
(«los domingos» -> sábado/domingo de reserva), la nota de despliegue de F-157 (desplegar en
viernes), la ventana de F-148 (15 h) y un párrafo nuevo del techo de 14 h. **Sin push.**

## Fase RED

Tests escritos antes del código (con solo `SABADO = 5` añadido para que el módulo importe; sin
esa constante el fallo era `ImportError: cannot import name 'SABADO'`). Comando:

```
python -m pytest tests/test_f025_precedencia.py tests/test_f148_reanudacion.py -q -k "f163 or ventana_de" -p no:cacheprovider
```

Salida real (extracto):

```
E       assert False is True
E       AssertionError: assert 'hoy' in 'la ultima reconstruccion completa fue hace 1.0 dias (2026-11-14)'
E       AssertionError: assert 'sabado' in 'hoy es el dia de la reconstruccion completa y la ultima fue el 2026-11-08'
E       assert True is False
E       AssertionError: assert 'fin de semana' in 'la ultima reconstruccion completa fue hace 6.0 dias (2026-11-10)'
E       assert 'dias_maximos' not in mappingproxy(OrderedDict({'ultima': ..., 'ahora': ..., 'dia_semana': <Parameter "dia_semana: 'int' = 6">, 'dias_maximos': <Parameter "dias_maximos: 'int' = 7">}))
E       assert 25200 == 50400
FAILED tests/test_f025_precedencia.py::test_f163_d1_el_sabado_toca - assert F...
FAILED tests/test_f025_precedencia.py::test_f163_d1_el_domingo_no_toca_si_la_del_sabado_quedo_registrada[ultima1]
FAILED tests/test_f025_precedencia.py::test_f163_entre_semana_nunca_toca_ni_con_la_completa_vencida[jue-8]
FAILED tests/test_f025_precedencia.py::test_f163_entre_semana_nunca_toca_ni_con_la_completa_vencida[jue-20]
FAILED tests/test_f025_precedencia.py::test_f163_el_tope_de_siete_dias_queda_solo_para_la_alerta
FAILED tests/test_f025_precedencia.py::test_f163_el_ultimo_dia_de_la_ventana_es_configurable
FAILED tests/test_f148_reanudacion.py::test_f148_dominio_ventana_de_quince_horas_y_mayor_que_el_techo_del_job
35 failed, 9 passed, 62 deselected in 1.73s
```

Los 9 que pasaban en rojo: `None` cualquier día (7, ya era así: D2 no cambia), domingo sin la del
sábado y el domingo que no repite la del propio domingo. Con el código: verde (abajo).

Un test existente ajustado: `test_f148_r18_sin_lote_previo_el_batch_lleva_el_sufijo_del_job`
tenía `timedelta(hours=8)` a mano; ahora usa `VENTANA_REANUDACION`.

## Tests por criterio de aceptación

| Criterio | Test(s) |
|---|---|
| Sábado dispara | `test_f163_d1_el_sabado_toca`, `..._aunque_la_ultima_fuera_ayer`, `..._no_se_repite_el_mismo_dia` |
| Domingo solo sin la del sábado | `test_f163_d1_el_domingo_toca_si_falta_la_del_sabado`, `..._no_toca_si_la_del_sabado_quedo_registrada` (00:00, 04:52, 23:59), `..._no_repite_la_del_propio_domingo` |
| Laborables nunca, ni con 7+ días | `test_f163_entre_semana_nunca_toca_ni_con_la_completa_vencida` (lun-vie x 1, 6, 7, 8, 20 días) |
| Sin completa: esa noche | `test_f163_d2_sin_ninguna_completa_registrada_toca_cualquier_dia` (7 días) |
| `check-ventana` avisa a los 7 días | `test_f163_el_tope_de_siete_dias_queda_solo_para_la_alerta`, `test_f025_r26_una_completa_vencida_se_denuncia` |
| Ventana 15 h > techo 50.400 | `test_f148_dominio_ventana_de_quince_horas_y_mayor_que_el_techo_del_job` |
| Ajuste configurable | `test_f163_el_ultimo_dia_de_la_ventana_es_configurable` |

Verde tras el código: `tests/test_f025_*`, `test_f148`, `test_f157_step` 215 passed; barrido
`-k "f006 or diccionario or f025 or f148 or f157"`: **4306 passed, 371 skipped** en 380 s.
`ruff`: 0 avisos nuevos en los ficheros tocados (main.py 71 antes y después, deuda previa).

## Salida de `init.sh`

`bash harness/init.sh` (2026-11-15, sobre `cc567f1` + este informe): **EXIT 0, «ENTORNO LISTO»**.

```
13253 passed, 2526 skipped, 2773 warnings in 2054.17s (0:34:14)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 17 líneas cambiadas cubiertas (17/17, umbral 80% (global), nivel estandar; diff desde e086ee4ccb, merge-base con main)
[OK] PUERTA TAMAÑO: F-163 dentro de los topes (impl 121/220)
[OK] PUERTA CARRIL: N/A (F-163 es de nivel estandar: no declara límites)
[OK] CAPA E2E: N/A (sin harness/servicios.json: declara el proyecto como servicio para usar la capa e2e)
```

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | 13.253 passed, 2.526 skipped, 0 failed (suite completa de `init.sh`) |
| Cobertura de líneas cambiadas | 100,0 % (17/17), `PUERTA COBERTURA` |
| Mutantes | Campaña no lanzada en esta pasada: va en la **pasada de campaña** tras el APPROVED (implementer.md) |
| Tiempo de la suite | 2.054 s (34 min 14 s) |
| Capa e2e | N/A (`CAPA E2E: N/A`, sin `harness/servicios.json`) |
