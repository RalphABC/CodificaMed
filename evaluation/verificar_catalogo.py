"""
Compara los códigos de data/cie10_catalogo.csv con la lista oficial de la OMS (CIE-10, edición 2019).
Necesita una librería extra, solo para esta verificación:
    pip install simple-icd-10
Uso:  python evaluation/verificar_catalogo.py
"""
import csv
import sys
from pathlib import Path

try:
    import simple_icd_10 as icd
except ImportError:
    sys.exit("Falta la librería. Instálala con:  pip install simple-icd-10")

RAIZ = Path(__file__).resolve().parent.parent
with open(RAIZ / "data" / "cie10_catalogo.csv", encoding="utf-8") as f:
    filas = list(csv.DictReader(f))

no_existen = []
for fila in filas:
    codigo = fila["codigo"]
    if icd.is_valid_item(codigo):
        print(f"OK     {codigo:7} {fila['descripcion'][:52]:52} | OMS: {icd.get_description(codigo)}")
    else:
        no_existen.append(codigo)
        print(f"NO     {codigo:7} {fila['descripcion'][:52]:52} | no figura en la lista de la OMS")

print(f"\n{len(filas) - len(no_existen)} de {len(filas)} códigos coinciden con la OMS.")
if no_existen:
    print("No figuran:", no_existen)
    print("Nota: A90 y A91 (dengue) fueron reemplazados por A97.x en la edición de la OMS, "
          "pero siguen vigentes en la CIE-10 de EE. UU. y España (base de CodiEsp).")
