# progress/mediciones/F-097_comparar_huellas.py
"""
F-097 · T0: segunda toma de huellas del master y comparacion con la del
2026-09-27, version a version. SOLO LECTURA contra Sigrid (un `SELECT` por
`SigridApiClient.leer_sql`, la misma consulta que usa `ingest_descompuestos`).

Uso, desde la raiz del repositorio:

    python progress/mediciones/F-097_comparar_huellas.py

Imprime cuantas versiones cambian por grupo. **Si cambia alguna del primer
grupo (anterior a la vigente y no ultima), se PARA y se vuelve al humano**: el
incremental supone que las versiones cerradas no cambian.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from config.settings import get_settings  # noqa: E402
from etl_sigrid.application.steps.ingest_descompuestos_step import (  # noqa: E402
    abrir_api,
    leer_huellas,
)
from etl_sigrid.domain.descompuestos import cod_version_vigente  # noqa: E402

TOMA_1 = RAIZ / "progress" / "mediciones" / "F-097_huella_master_2026-09-27.csv"


def main() -> None:
    settings = get_settings()
    with abrir_api(settings) as api:
        versiones, vigentes = leer_huellas(
            api, cod_version_vigente(settings.business_rules), settings.sigrid_api.page_size
        )
    with TOMA_1.open(encoding="utf-8") as f:
        toma = {
            (int(r["obra_id"]), int(r["version"])): (int(r["filas"]), int(r["bytes"]), int(r["huella"]))
            for r in csv.DictReader(f, delimiter=";")
        }
    ultima: dict[int, int] = {}
    for v in versiones:
        ultima[v.obra_id] = max(ultima.get(v.obra_id, v.fase_num), v.fase_num)

    total, cambian = Counter(), Counter()
    for v in versiones:
        vigente = vigentes.get(v.obra_id)
        if v.clave not in toma:
            grupo = "4 nueva"
        elif vigente is None:
            grupo = "5 obra sin vigente"
        elif v.fase_num == vigente:
            grupo = "2 vigente"
        elif v.fase_num > vigente or v.fase_num == ultima[v.obra_id]:
            grupo = "3 posterior a la vigente, o la ultima"
        else:
            grupo = "1 anterior a la vigente y no ultima"
        total[grupo] += 1
        if grupo != "4 nueva" and toma[v.clave] != (v.filas, v.bytes, v.huella):
            cambian[grupo] += 1
    desaparecidas = len(set(toma) - {v.clave for v in versiones})

    print(f"versiones en Sigrid: {len(versiones)}; en la toma del 2026-09-27: {len(toma)}")
    for grupo in sorted(total):
        print(f"  {grupo:<40} {total[grupo]:>6} versiones, {cambian[grupo]:>5} cambian")
    print(f"  desaparecidas desde la toma 1: {desaparecidas}")
    if cambian["1 anterior a la vigente y no ultima"]:
        print("PARAR: han cambiado versiones cerradas. Volver al humano antes de la primera carga.")


if __name__ == "__main__":
    main()
