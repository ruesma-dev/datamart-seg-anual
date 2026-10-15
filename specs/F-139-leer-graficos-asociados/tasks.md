<!-- specs/F-139-leer-graficos-asociados/tasks.md -->
# F-139 · Tareas (opción B recomendada; si D1 ≠ B, esta lista se rehace)

Solo valen tras la aprobación del humano. Con D7 recomendada, T1-T5 se hacen en una feature pequeña propia y F-139 queda `blocked` en T6; con la alternativa de D7, todo va en la rama `feature/F-139-leer-graficos-asociados`.

- [ ] T1: Escribir `tests/test_f139_limite.py` con un test por R1, R2, R3, R4 y R5 (fase RED: R1-R4 fallan, R5 pasa y se prueba con un caso de sabotaje que importa `pypdf` en un módulo temporal)  |  Verificación: `python -m pytest tests/test_f139_limite.py` con R1-R4 en rojo por la razón esperada
- [ ] T2: Ficha `documento_adjuntos` en `config/diccionario/compras.yaml`: `filename_columns: ["cod"]`, el 5,7 % (11.262) con HTTP 500 y que el contenido se lee fuera (R1, R2)  |  Verificación: `python -m pytest tests/test_f139_limite.py -k "r1 or r2"` en verde
- [ ] T3: `version` 52 → 53 en `config/diccionario/00_global.yaml` (R3)  |  Verificación: `python -m pytest tests/test_f139_limite.py -k r3` y los tests de diccionario existentes en verde
- [ ] T4: `docs/ARCHITECTURE.md`, subpunto «El fichero NO se replica» de F-090: el límite de F-139 y el aviso de `filename_columns` (R4)  |  Verificación: `python -m pytest tests/test_f139_limite.py -k r4` en verde
- [ ] T5: `azure-apps/datamart_seg_anual.md`: el aviso de `filename_columns` y el límite de F-139 en el párrafo de `documents/read`, commit local en `azure-apps` (R7)  |  Verificación: MANUAL (humano): `git -C C:\Users\pgris\PycharmProjects\azure-apps log -1 --stat` muestra el commit y `grep -n "filename_columns" datamart_seg_anual.md` lo encuentra
- [ ] T6: (líder, tras la aprobación) F-139 a `blocked` en `harness/features.json` con el motivo de R6 y la propuesta P1-P11 entregada al humano para el repositorio `facturas`; D6 como propuesta de feature para `sigrid-api`  |  Verificación: `BACKLOG.md` regenerado con F-139 en «Bloqueadas»
- [ ] T7: Ejecutar `bash harness/init.sh` en verde  |  Verificación: salida en verde (incluye pytest y la puerta de tamaño de esta spec)
