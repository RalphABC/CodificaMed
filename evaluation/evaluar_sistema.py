"""
Paso 6: evalúa el sistema completo sobre los 30 casos y guarda los resultados.

Uso (ejemplos):
    python evaluation/evaluar_sistema.py --proveedor reglas                      # línea base sin LLM
    python evaluation/evaluar_sistema.py --proveedor ollama --modelo mistral
    python evaluation/evaluar_sistema.py --proveedor ollama --modelo llama3.2:3b
    python evaluation/evaluar_sistema.py --proveedor groq                         # API externa
    python evaluation/evaluar_sistema.py --proveedor ollama --modelo mistral --limite 3   # prueba rápida

Cada ejecución crea un archivo en evaluation/resultados/. Luego, con
comparar_resultados.py se genera la tabla comparativa para el informe.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from codificador import generador_reglas, sugerir_codigos  # noqa: E402
from llm import modelo_actual, obtener_generador  # noqa: E402
from recuperacion import Recuperador  # noqa: E402


def prf(tp, fp, fn):
    """Precisión, recall y F1 a partir de verdaderos positivos, falsos positivos y falsos negativos."""
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


parser = argparse.ArgumentParser()
parser.add_argument("--proveedor", choices=["ollama", "groq", "reglas"], required=True)
parser.add_argument("--modelo", help="nombre del modelo (si no se indica, se usa el del .env)")
parser.add_argument("--k", type=int, default=3, help="candidatos por fragmento (por defecto 3)")
parser.add_argument("--recuperador", choices=["embeddings", "tfidf"], default=None)
parser.add_argument("--limite", type=int, default=None, help="evaluar solo los primeros N casos")
args = parser.parse_args()

if args.modelo:
    os.environ[{"ollama": "OLLAMA_MODEL", "groq": "GROQ_MODEL"}[args.proveedor]] = args.modelo
nombre_modelo = "solo-reglas" if args.proveedor == "reglas" else modelo_actual(args.proveedor)
etiqueta = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{args.proveedor}_{nombre_modelo}")

casos = json.loads((RAIZ / "data" / "casos_ficticios.json").read_text(encoding="utf-8"))
if args.limite:
    casos = casos[: args.limite]

recuperador = Recuperador(metodo=args.recuperador)
generar_real = None if args.proveedor == "reglas" else obtener_generador(args.proveedor)

print(f"Evaluando: {etiqueta} | recuperador={recuperador.metodo} | K={args.k} | casos={len(casos)}\n")

registros = []
errores_seguidos = 0
inicio_total = time.time()
for c in casos:
    gold_conf, gold_neg = set(c["codigos_confirmados"]), set(c["codigos_negados"])
    generar = generador_reglas(c["texto"]) if args.proveedor == "reglas" else generar_real

    t0 = time.time()
    error = None
    try:
        r = sugerir_codigos(c["texto"], recuperador, generar, k=args.k)
    except Exception as e:  # p. ej. caída de red o modelo no encontrado
        r = {"sugerencias": [], "inventados": [], "respuesta_valida": False, "respuesta_cruda": ""}
        error = f"{type(e).__name__}: {e}"
    segundos = round(time.time() - t0, 2)

    pred_conf = {s["codigo"] for s in r["sugerencias"] if s["estado"] == "confirmado"}
    pred_neg = {s["codigo"] for s in r["sugerencias"] if s["estado"] == "negado"}
    registros.append({
        "id": c["id"], "esperado_confirmados": sorted(gold_conf), "esperado_negados": sorted(gold_neg),
        "pred_confirmados": sorted(pred_conf), "pred_negados": sorted(pred_neg),
        "inventados": r["inventados"], "respuesta_valida": r["respuesta_valida"],
        "n_revisar": sum(s["revisar"] for s in r["sugerencias"]),
        "segundos": segundos, "error": error,
    })
    estado = "ERROR" if error else ("JSON inválido" if not r["respuesta_valida"] else "ok")
    print(f"{c['id']}  {segundos:6.1f}s  {estado}  confirmados={sorted(pred_conf)}  negados={sorted(pred_neg)}")

    # Si el proveedor falla varias veces seguidas (sin crédito, sin red, modelo inexistente...),
    # se detiene: así no se guarda un resultado "0" que parece del modelo pero es un fallo técnico.
    errores_seguidos = errores_seguidos + 1 if error else 0
    if errores_seguidos >= 3:
        print(f"\nSE DETUVO: 3 errores seguidos. No se guardó ningún resultado.\nÚltimo error: {error}")
        sys.exit(1)

# ---- Métricas agregadas (micro-promedio sobre todos los casos) ----
tp = sum(len(set(x["pred_confirmados"]) & set(x["esperado_confirmados"])) for x in registros)
fp = sum(len(set(x["pred_confirmados"]) - set(x["esperado_confirmados"])) for x in registros)
fn = sum(len(set(x["esperado_confirmados"]) - set(x["pred_confirmados"])) for x in registros)
precision, recall, f1 = prf(tp, fp, fn)

neg_esperados = sum(len(x["esperado_negados"]) for x in registros)
neg_detectados = sum(len(set(x["pred_negados"]) & set(x["esperado_negados"])) for x in registros)
falsas_confirmaciones = sum(len(set(x["pred_confirmados"]) & set(x["esperado_negados"])) for x in registros)

metricas = {
    "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
    "tp": tp, "fp": fp, "fn": fn,
    "negaciones_esperadas": neg_esperados, "negaciones_detectadas": neg_detectados,
    "falsas_confirmaciones": falsas_confirmaciones,
    "respuestas_invalidas": sum(not x["respuesta_valida"] for x in registros),
    "codigos_inventados": sum(len(x["inventados"]) for x in registros),
    "sugerencias_a_revisar": sum(x["n_revisar"] for x in registros),
    "errores": sum(1 for x in registros if x["error"]),
    "segundos_por_nota": round(sum(x["segundos"] for x in registros) / len(registros), 2),
    "segundos_totales": round(time.time() - inicio_total, 1),
}

print("\n=== RESULTADOS (códigos confirmados) ===")
print(f"Precisión {precision:.3f} | Recall {recall:.3f} | F1 {f1:.3f}   (TP={tp} FP={fp} FN={fn})")
print(f"Negaciones detectadas: {neg_detectados}/{neg_esperados} | "
      f"Negados marcados como confirmados: {falsas_confirmaciones}")
print(f"Respuestas inválidas: {metricas['respuestas_invalidas']} | "
      f"Códigos inventados: {metricas['codigos_inventados']} | Errores: {metricas['errores']}")
print(f"Tiempo medio por nota: {metricas['segundos_por_nota']} s")

salida = RAIZ / "evaluation" / "resultados"
salida.mkdir(exist_ok=True)
if not args.limite:  # las pruebas rápidas no se guardan, para no ensuciar la comparación
    archivo = salida / f"{etiqueta}.json"
    archivo.write_text(json.dumps({
        "config": {"proveedor": args.proveedor, "modelo": nombre_modelo, "k": args.k,
                   "recuperador": recuperador.metodo, "casos": len(casos)},
        "metricas": metricas, "casos": registros}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en: {archivo}")
