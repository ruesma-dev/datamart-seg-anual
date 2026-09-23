<!-- specs/F-101-cabecera-del-parte/tasks.md -->
# F-101 · Tareas

Una tarea = un commit (`F-101 Tn: ...`). Rama `hotfix/F-101-cabecera-del-parte`
(ya creada y al día con `main`; **no cambiar de rama**). Nunca `git add -A`.

- [x] T1: Confirmar contra Sigrid, en SOLO LECTURA, las cifras que gobiernan el diseño antes de escribir SQL: `con.tip=35` (6.886), 6.258 códigos distintos, `conest` tip 35 (1/3/10), `hmo.feccie`/`cla`/`caaide` a 0, 17 pares repetidos en `reshor`, `cuaide`/`proide` a 0 | Verificación: las cifras reproducidas en `progress/impl_F-101.md`; si alguna no cuadra, PARAR y avisar
- [x] T2: Escribir `tests/test_f101_cabecera_parte.py` con los `test_f101_rN_*` de R1–R28 en fase RED (los SQL aún no existen) | Verificación: `pytest tests/test_f101_cabecera_parte.py` falla por los motivos esperados, y la traza RED va al informe
- [x] T3: Añadir a `sql/personal/00_setup.sql` la función `personal.fn_fecha_serie` y el DDL de `personal.partes` y `personal.recursos_tipos_hora` con sus índices (`CREATE ... IF NOT EXISTS`, sin `DROP`) | Verificación: `pytest -k "f101 and ddl"`
- [x] T4: Crear `sql/personal/03_partes.sql` (R1–R11) con los dos `LATERAL` y la obra/centro de cabecera nombrados `obra_cabecera_id` / `centro_coste_cabecera_id` | Verificación: `pytest -k "f101 and partes"`
- [x] T5: Crear `sql/personal/04_recursos_tipos_hora.sql` (R17–R23) con el `CASE medide` idéntico al de las líneas y sin `prenom`/`cuaide`/`proide` | Verificación: `pytest -k "f101 and tipos_hora"`
- [x] T6: Añadir `codigo_parte` a `sql/personal/02_partes_lineas.sql` por `raw.con` sobre `hmoide`, sin nombrar `raw.hmo`, y su columna en el DDL | Verificación: `pytest tests/test_f057_personal.py::test_f057_r12_obra_de_la_linea_no_de_la_cabecera` y `pytest -k "f101 and codigo_parte"`
- [x] T7: `git mv sql/personal/03_views.sql sql/personal/05_views.sql` y actualizar las constantes de ruta de `tests/test_f057_personal.py` | Verificación: `pytest tests/test_f057_personal.py`
- [x] T8: Ampliar `SUB_PASOS` de `build_personal_step.py` a seis entradas en el orden `setup, recursos, partes_lineas, partes, recursos_tipos_hora, views`, con `target_schema`/`target_table` en las dos nuevas | Verificación: `pytest tests/test_f057_personal.py -k r24` y `pytest -k "f101 and step"`
- [x] T9: **Solo si el humano aprueba D-3**: sacar `tex` de `exclude_columns` de `hmores` en `config/tables_sigrid.yaml` con las cifras en el comentario, y publicar `texto_linea` en `02_partes_lineas.sql` y en el DDL | Verificación: `pytest -k "f101 and texto"`
- [x] T10: Escribir las fichas de `partes` y `recursos_tipos_hora` y las columnas nuevas de `partes_lineas` en `config/diccionario/personal.yaml`, con `clave_negocio`, `relaciones`, `ejemplos_preguntas` y las trampas medidas (569 códigos repetidos, 27 años fuera de rango, sin histórico de precios, 56,2 % de desfase, `preven` en 3 filas, los 4 recursos sin fila de su defecto, el usuario en `dbo.log`) | Verificación: `pytest -k "f101 and ficha"` y `python scripts/check_yaml.py`
- [x] T11: Subir `version` de `config/diccionario/personal.yaml` (1 → 2) y de `config/diccionario/00_global.yaml` (26 → 27) | Verificación: `pytest -k "f101 and version"`
- [x] T12: Actualizar `azure-apps/datamart_seg_anual.md` (tabla de objetos de `personal` de 3 a 5 filas + las trampas nuevas) y hacer su commit en ESE repositorio | Verificación: `git -C ../azure-apps status` limpio tras el commit; revisión del reviewer
- [x] T13: Ejecutar `bash harness/init.sh` en verde | Verificación: salida del propio comando

## Verificación MANUAL (humano) — necesita BBDD y escribe en el datamart

- [ ] M1: `python main.py build-personal` y comprobar que los seis sub-pasos terminan `success` y que `partes` trae ~6.886 filas y `recursos_tipos_hora` ~8.959 | Verificación: MANUAL (humano)
- [ ] M2: Contraste de la cabecera — `SELECT COUNT(*), COUNT(DISTINCT codigo_parte) FROM personal.partes;` debe dar **6.886 / 6.258**, y `SELECT estado, COUNT(*) FROM personal.partes GROUP BY estado;` debe dar **En registro 647 / Cerrado 541 / Imputado 5.698** | Verificación: MANUAL (humano)
- [ ] M3: Contraste de la discrepancia — `SELECT COUNT(*) FROM personal.partes WHERE lineas_en_otra_obra > 0;` debe dar **14**, y `SELECT SUM(lineas_en_otra_obra) FROM personal.partes;` debe dar **615** | Verificación: MANUAL (humano)
- [ ] M4: Contraste del código en la línea — `SELECT COUNT(*) FROM personal.partes_lineas WHERE codigo_parte IS NULL;` debe dar **0** | Verificación: MANUAL (humano)
- [ ] M5: Contraste de los tipos de hora — `SELECT unidad, COUNT(*) FROM personal.recursos_tipos_hora GROUP BY unidad;` sin unidad nula, con 3 filas en `DESCONOCIDA`; `COUNT(*) FILTER (WHERE precio_coste <> 0)` = **2.037**, `precio_venta <> 0` = **3**, `es_por_defecto` cierto en ~2.031 | Verificación: MANUAL (humano)
- [ ] M6: El desfase que pidió Juan, ya contestable — cruzar `personal.partes_lineas` con `personal.recursos_tipos_hora` por `(recurso_id, tipo_hora_id)` y contar líneas con `precio` distinto de `precio_coste`: debe rondar **156.819 de 279.034 (56,2 %)**; mirar el caso de Jaime Rabadán (MO/0306) | Verificación: MANUAL (humano)
- [ ] M7: `python main.py check-declarados`, `check-unicidad` y `check-relaciones` en verde con los objetos nuevos y **sin añadir nada** a `config/objetos_pendientes.yaml` | Verificación: MANUAL (humano)
- [ ] M8: `python main.py check-diccionario` en biyección (fichas = objetos publicados) | Verificación: MANUAL (humano)
- [ ] M9: **Solo con D-3 aprobada**: coste de ventana de `hmores.tex` — cronometrar `python main.py ingest --table hmores --full` antes y después del cambio (patrón medición B de F-080) y anotar los dos tiempos | Verificación: MANUAL (humano)
- [ ] M10: `python main.py publicar-diccionario` (escritura contra Azure: la autoriza el humano, nunca un agente) | Verificación: MANUAL (humano)
