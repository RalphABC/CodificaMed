"""
Evalúa la recuperación de candidatos (Paso 4) con Recall@K.

Recall@K = de todos los códigos que menciona la nota (confirmados + negados),
           ¿qué porcentaje aparece entre los candidatos recuperados?
Es la métrica clave aquí: si un código no está entre los candidatos, el modelo de
lenguaje del Paso 5 nunca podrá elegirlo.

Uso:
    python evaluation/evaluar_recuperacion.py                 # tfidf y embeddings
    python evaluation/evaluar_recuperacion.py --metodo tfidf
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from recuperacion import Recuperador  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--metodo", choices=["tfidf", "embeddings", "todos"], default="todos")
args = parser.parse_args()
metodos = ["tfidf", "embeddings"] if args.metodo == "todos" else [args.metodo]

casos = json.loads((RAIZ / "data" / "casos_ficticios.json").read_text(encoding="utf-8"))
VALORES_K = [1, 2, 3, 5]

for metodo in metodos:
    try:
        recuperador = Recuperador(metodo=metodo)
    except ImportError as e:
        print(f"[{metodo}] no disponible: {e}\n")
        continue
    except Exception as e:  # p. ej. el modelo no se pudo descargar
        print(f"[{metodo}] no se pudo iniciar: {type(e).__name__}: {e}\n")
        continue

    print(f"=== Método: {metodo} ===")
    print(f"{'K por fragmento':>16} | {'Recall@K':>9} | {'candidatos por nota (prom.)':>28}")
    for k in VALORES_K:
        hallados = esperados = total_candidatos = 0
        for c in casos:
            gold = set(c["codigos_confirmados"]) | set(c["codigos_negados"])
            candidatos = {x["codigo"] for x in recuperador.buscar(c["texto"], k=k)}
            hallados += len(gold & candidatos)
            esperados += len(gold)
            total_candidatos += len(candidatos)
        print(f"{k:>16} | {hallados / esperados:>9.3f} | {total_candidatos / len(casos):>28.1f}")

    # Códigos que se escapan con K=3 (para analizar errores)
    print("\nCódigos NO recuperados con K=3:")
    for c in casos:
        gold = set(c["codigos_confirmados"]) | set(c["codigos_negados"])
        candidatos = {x["codigo"] for x in recuperador.buscar(c["texto"], k=3)}
        perdidos = sorted(gold - candidatos)
        if perdidos:
            print(f"  {c['id']}: {perdidos}")
    print()
