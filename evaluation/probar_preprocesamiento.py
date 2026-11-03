"""
Prueba el preprocesamiento en dos partes:
  1) Oraciones cortas con la respuesta esperada (pruebas unitarias de negación).
  2) Los 30 casos ficticios, comparando contra 'codigos_negados'.
Uso:  python evaluation/probar_preprocesamiento.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))  # para poder hacer "import preprocesamiento"

from preprocesamiento import cargar_catalogo, detectar_menciones  # noqa: E402

catalogo = cargar_catalogo()

# ---------------- Parte 1: oraciones cortas ----------------
PRUEBAS = [
    ("niega fiebre y tos", {"R50.9": "negado", "R05": "negado"}),
    ("niega fiebre, pero presenta tos", {"R50.9": "negado", "R05": "confirmado"}),
    ("se descarta neumonía", {"J18.9": "negado"}),
    ("neumonía descartada", {"J18.9": "negado"}),
    ("paciente con neumonía", {"J18.9": "confirmado"}),
    ("afebril", {"R50.9": "negado"}),
    ("no presenta sibilancias", {"J45.9": "negado"}),
    ("sin signos de colecistitis, con colelitiasis", {"K81.0": "negado", "K80.2": "confirmado"}),
    ("tos seca y fiebre", {"R05": "confirmado", "R50.9": "confirmado"}),
    ("Dx: HTA y DM2", {"I10": "confirmado", "E11.9": "confirmado"}),
    ("sin embargo presenta cefalea", {"R51": "confirmado"}),
    ("No refiere fiebre ni rigidez de nuca", {"R50.9": "negado"}),
]

print("=== PARTE 1: oraciones cortas ===")
fallos = 0
for oracion, esperado in PRUEBAS:
    obtenido = {m["codigo"]: m["estado"] for m in detectar_menciones(oracion, catalogo)}
    if obtenido == esperado:
        print(f"OK     {oracion}")
    else:
        fallos += 1
        print(f"FALLA  {oracion}\n         esperado: {esperado}\n         obtenido: {obtenido}")
print(f"-> {len(PRUEBAS) - fallos}/{len(PRUEBAS)} pruebas correctas\n")

# ---------------- Parte 2: los 30 casos ----------------
casos = json.loads((RAIZ / "data" / "casos_ficticios.json").read_text(encoding="utf-8"))

neg_total = neg_halladas = 0
confirmados_negados_por_error = 0
print("=== PARTE 2: negaciones en los 30 casos ===")
for c in casos:
    menciones = detectar_menciones(c["texto"], catalogo)
    pred_neg = {m["codigo"] for m in menciones if m["estado"] == "negado"}
    gold_neg = set(c["codigos_negados"])
    gold_conf = set(c["codigos_confirmados"])

    neg_total += len(gold_neg)
    neg_halladas += len(gold_neg & pred_neg)
    error_grave = pred_neg & gold_conf  # un diagnóstico real marcado como negado
    confirmados_negados_por_error += len(error_grave)

    perdidas = gold_neg - pred_neg
    if perdidas or error_grave:
        print(f"{c['id']}: no detectadas={sorted(perdidas)}  marcadas negadas por error={sorted(error_grave)}")

print(f"\nNegaciones esperadas detectadas: {neg_halladas}/{neg_total}")
print(f"Diagnósticos confirmados marcados como negados por error: {confirmados_negados_por_error}")
