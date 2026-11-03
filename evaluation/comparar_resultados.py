"""
Junta todos los archivos de evaluation/resultados/*.json en una tabla comparativa
(se imprime y se guarda como evaluation/resultados/comparacion.md).
Uso:  python evaluation/comparar_resultados.py
"""
import json
from pathlib import Path

CARPETA = Path(__file__).resolve().parent / "resultados"

filas = []
for archivo in sorted(CARPETA.glob("*.json")):
    d = json.loads(archivo.read_text(encoding="utf-8"))
    m, c = d["metricas"], d["config"]
    filas.append((c["proveedor"], c["modelo"], m))

if not filas:
    raise SystemExit("No hay resultados todavía. Ejecuta primero evaluar_sistema.py.")

encabezado = ("| Proveedor | Modelo | Precisión | Recall | F1 | Negaciones detectadas | "
              "Negados marcados como confirmados | Respuestas inválidas | Códigos inventados | s/nota |")
lineas = [encabezado, "|" + " --- |" * 10]
for proveedor, modelo, m in filas:
    lineas.append(
        f"| {proveedor} | {modelo} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | "
        f"{m['negaciones_detectadas']}/{m['negaciones_esperadas']} | {m['falsas_confirmaciones']} | "
        f"{m['respuestas_invalidas']} | {m['codigos_inventados']} | {m['segundos_por_nota']} |"
    )

tabla = "\n".join(lineas)
print(tabla)
(CARPETA / "comparacion.md").write_text(tabla + "\n", encoding="utf-8")
print(f"\nGuardada en: {CARPETA / 'comparacion.md'}")
