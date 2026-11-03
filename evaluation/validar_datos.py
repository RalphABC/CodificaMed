"""Valida que los casos ficticios solo usen códigos presentes en el catálogo."""
import csv
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

with open(RAIZ / "data" / "cie10_catalogo.csv", encoding="utf-8") as f:
    catalogo = {fila["codigo"] for fila in csv.DictReader(f)}

casos = json.loads((RAIZ / "data" / "casos_ficticios.json").read_text(encoding="utf-8"))

errores = []
for c in casos:
    for cod in c["codigos_confirmados"] + c["codigos_negados"]:
        if cod not in catalogo:
            errores.append((c["id"], cod))

print(f"Catálogo: {len(catalogo)} códigos | Casos: {len(casos)}")
print("Total de códigos confirmados:", sum(len(c["codigos_confirmados"]) for c in casos))
print("Total de códigos negados:", sum(len(c["codigos_negados"]) for c in casos))
print("Errores:", errores if errores else "ninguno")
