# agent/brain.py — Cerebro del agente: conexión con Claude API
# Generado por AgentKit

"""
Lógica de IA del agente. Lee el system prompt de prompts.yaml
y genera respuestas usando la API de Anthropic Claude.
"""

import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Cliente de Anthropic
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Importar funciones de herramientas
from agent.tools import detectar_tipo_pregunta, consultar_precios


def obtener_agente_activo() -> str:
    """Retorna el nombre del agente activo desde variables de entorno."""
    return os.getenv("AGENTE_ACTIVO", "default")


def cargar_config_prompts() -> dict:
    """Lee toda la configuración desde config/{AGENTE_ACTIVO}/prompts.yaml."""
    agente = obtener_agente_activo()
    ruta = f"config/{agente}/prompts.yaml"
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"{ruta} no encontrado")
        return {}


def cargar_system_prompt() -> str:
    """Lee el system prompt desde config/prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente útil. Responde en español.")


def obtener_mensaje_error() -> str:
    """Retorna el mensaje de error configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    """Retorna el mensaje de fallback configurado en prompts.yaml."""
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?")


async def generar_respuesta(mensaje: str, historial: list[dict]) -> str:
    """
    Genera una respuesta usando Claude API.

    Args:
        mensaje: El mensaje nuevo del usuario
        historial: Lista de mensajes anteriores [{"role": "user/assistant", "content": "..."}]

    Returns:
        La respuesta generada por Claude
    """
    # Si el mensaje es muy corto o vacío, usar fallback
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()

    # Agregar fecha de hoy para que Claude pueda convertir "mañana", "próximo lunes", etc.
    from datetime import datetime, timedelta
    hoy = datetime.utcnow()
    mañana = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    system_prompt += f"\n\n## Información de contexto\nFecha de hoy: {hoy.strftime('%Y-%m-%d')} ({hoy.strftime('%A')})\nMañana será: {mañana}\nCuando el cliente mencione fechas relativas (mañana, pasado mañana, próximo lunes, etc.), CONVIERTE siempre a formato ISO (YYYY-MM-DD) para el tag [CITA]."

    # Detectar tipo de pregunta y enriquecer el system prompt
    tipo_pregunta, instruccion_extra = detectar_tipo_pregunta(mensaje)
    if instruccion_extra:
        system_prompt += f"\n\n## Instrucción especial para esta pregunta\nTipo detectado: {tipo_pregunta}\n{instruccion_extra}"
        logger.info(f"Sistema enriquecido con instrucción para pregunta tipo: {tipo_pregunta}")

    # Si la pregunta es sobre reparación o accesorios, inyectar catálogo de precios
    if tipo_pregunta in ["reparacion", "accesorios"]:
        precios = consultar_precios()
        if precios:
            # Convertir precios a formato legible para Claude
            precios_formateado = yaml.dump(precios, allow_unicode=True, default_flow_style=False)
            system_prompt += f"\n\n## CATÁLOGO DE PRECIOS DISPONIBLES\nUsados para responder consultas de precios:\n\n{precios_formateado}\n**IMPORTANTE:** Si el cliente pregunta por un precio que tienes en el catálogo, responde con el precio. Si no está en el catálogo, di que confirmamos el precio exacto al traer el dispositivo."
            logger.info(f"Catálogo de precios inyectado en system_prompt para pregunta tipo: {tipo_pregunta}")

    # Construir mensajes para la API
    mensajes = []
    for msg in historial:
        mensajes.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Agregar el mensaje actual
    mensajes.append({
        "role": "user",
        "content": mensaje
    })

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=mensajes
        )

        respuesta = response.content[0].text
        logger.info(f"Respuesta generada ({response.usage.input_tokens} in / {response.usage.output_tokens} out)")
        return respuesta

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
