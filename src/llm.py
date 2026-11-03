"""
llm.py
------
Capa de modelo de lenguaje intercambiable (requisito 4 del enunciado).

El resto del programa solo llama a  generar(prompt_sistema, prompt_usuario)  y recibe texto.
Qué modelo responde se decide con la variable LLM_PROVIDER del archivo .env:
    ollama  -> modelo local (corre en tu computador)
    groq    -> API externa de Groq (plan gratuito). Usa el formato "compatible con OpenAI",
               así que cambiando GROQ_BASE_URL también sirve para Gemini, OpenRouter, etc.
"""

import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def proveedor_actual():
    return os.getenv("LLM_PROVIDER", "ollama").lower()


def modelo_actual(proveedor=None):
    proveedor = proveedor or proveedor_actual()
    if proveedor == "groq":
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    return os.getenv("OLLAMA_MODEL", "mistral")


def _clave_valida(clave):
    return bool(clave) and not clave.lower().startswith(("your_", "pon_", "tu_"))


def _generar_ollama(sistema, usuario):
    import ollama

    cliente = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    respuesta = cliente.chat(
        model=modelo_actual("ollama"),
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        format="json",                 # obliga al modelo a responder con JSON válido
        options={"temperature": 0},    # respuestas lo más repetibles posible
    )
    return respuesta["message"]["content"]


def _generar_groq(sistema, usuario):
    """
    Llama a la API de Groq (formato /chat/completions de OpenAI).
    Configuración en .env:  GROQ_API_KEY, GROQ_MODEL y, opcionalmente, GROQ_BASE_URL.
    El plan gratuito limita las solicitudes por minuto: si el servicio responde "429"
    (demasiadas solicitudes) se espera y se reintenta automáticamente.
    """
    import requests

    base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    clave = os.getenv("GROQ_API_KEY", "")
    if not _clave_valida(clave):
        raise RuntimeError("Falta GROQ_API_KEY en el archivo .env (clave real, solo en .env).")

    cuerpo = {
        "model": modelo_actual("groq"),
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "temperature": 0,
    }
    cabeceras = {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}

    maximo = 6
    for intento in range(1, maximo + 1):
        r = requests.post(f"{base}/chat/completions", headers=cabeceras, json=cuerpo, timeout=120)
        if r.status_code == 429 and intento < maximo:
            try:
                espera = float(r.headers.get("retry-after", 0))
            except ValueError:
                espera = 0
            time.sleep(min(max(espera, 5 * intento), 65))   # esperar y reintentar
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Error {r.status_code} de la API: {r.text[:300]}")
        return r.json()["choices"][0]["message"]["content"]
    raise RuntimeError("La API sigue rechazando por límite de uso; espera unos minutos e inténtalo de nuevo.")


def obtener_generador(proveedor=None):
    """Devuelve la función generar(sistema, usuario) del proveedor elegido."""
    proveedor = (proveedor or proveedor_actual()).lower()
    if proveedor == "ollama":
        return _generar_ollama
    if proveedor == "groq":
        return _generar_groq
    raise ValueError(f"LLM_PROVIDER desconocido: {proveedor!r} (usa 'ollama' o 'groq')")
