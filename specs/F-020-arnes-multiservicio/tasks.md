<!-- specs/F-020-arnes-multiservicio/tasks.md -->
# F-020 · Arnés multi-servicio — Tareas

Reglas: cada tarea = un commit `F-020 Tn: ...` en la rama
`feature/F-020-arnes-multiservicio`. Fase RED con salida real pegada en
`progress/impl_F-020.md` para los requisitos centrales (R2, R3, R11, R13,
R15, R16). Ningún test toca red ni BBDD; las estructuras de monorepo son
fixtures en `tmp_path`.

- [ ] T1: `harness/servicios.py` — dataclass `Servicio`, `cargar_servicios`
      con validación completa, `servicio_de_ruta`, `interprete`, CLI
      `--validar`/`--shell`. Tests primero (RED).
      | Verificación: `pytest tests/ -k "f020_r1 or f020_r2 or f020_r3 or f020_r4 or f020_r5 or f020_r6_salida" -q`
- [ ] T2: `harness/alcance.py` — `es_produccion()` excluye
      `tests/specs/progress/docs` como segmento en cualquier nivel.
      | Verificación: `pytest tests/ -k "f020_r11 or f020_r12" -q` y
      `pytest tests/ -k f015 -q` (sin regresión)
- [ ] T3: `harness/cobertura.py` — `fusionar_coberturas()` y carga opcional
      de servicios en `main()`; sin servicios, camino idéntico al actual.
      | Verificación: `pytest tests/ -k "f020_r13 or f020_r14 or f020_r2_cobertura" -q`
- [ ] T4: `harness/mutacion.py` — `EjecutorPytest(cwd, ejecutable)`, factoría
      `ejecutor_para()`, exit 5 de pytest = SUPERVIVIENTE.
      | Verificación: `pytest tests/ -k "f020_r15 or f020_r16 or f020_r2_mutacion" -q`
- [ ] T5: `harness/init.sh` — sección multi-servicio condicionada a
      `harness/servicios.json`: validación KO, bucle por servicio con
      intérprete propio, avisos nominales, agregado y línea por servicio.
      | Verificación: `pytest tests/ -k "f020_r6 or f020_r7 or f020_r8 or f020_r9 or f020_r10" -q` y `bash harness/init.sh` en este repo (verde, sin sección multi-servicio ejecutada)
- [ ] T6: test de genericidad de las herramientas (sin Sigrid, capas del
      datamart, Azure ni nombres de apps).
      | Verificación: `pytest tests/ -k f020_r17 -q`
- [ ] T7: portado a `arnes-base`: `harness/*.py` e `init.sh` actualizados,
      `harness/servicios.ejemplo.json` nuevo en el payload, `VERSION` a
      1.3.0 con fecha, sección «monorepo multi-servicio» en
      `GUIA_INSTALACION.md`, commit local en ese repositorio (sin push).
      | Verificación: MANUAL (humano) — comandos exactos en R18 y R19 de
      `requirements.md`
- [ ] T8: prueba real: crear un monorepo temporal en el scratchpad (servicio
      Python con venv y tests + servicio no Python), instalarle el arnés con
      `instalar_arnes.ps1` desde Windows PowerShell 5.1, configurar su
      `servicios.json` y ejecutar `bash harness/init.sh` en verde; repetir
      con un test roto en el servicio Python para ver el KO agregado. Salida
      real de ambos casos pegada en `progress/impl_F-020.md`.
      | Verificación: MANUAL (humano) — comandos exactos en R20 de
      `requirements.md`
- [ ] T9: si `azure-apps/` documenta `arnes-base`, anotar allí la 1.3.0 y la
      capacidad multi-servicio (enlace, no duplicado). Si no existe el
      documento, dejar constancia en el informe y no crear nada.
      | Verificación: `grep -ri "1.3.0" C:/Users/pgris/PycharmProjects/azure-apps/ --include="*.md"` (o constancia escrita de N/A)
- [ ] T10: campaña de mutación de la propia feature, análisis de cada
      superviviente completado y sección «Evidencias» (tests, cobertura de
      líneas cambiadas, mutantes/supervivientes, tiempo) en
      `progress/impl_F-020.md`.
      | Verificación: `python -m harness.mutacion --feature F-020` e informe
      `progress/mutacion_F-020.md` sin análisis en PENDIENTE
- [ ] T11: Ejecutar `bash harness/init.sh` en verde.
      | Verificación: `bash harness/init.sh` termina con exit code 0
