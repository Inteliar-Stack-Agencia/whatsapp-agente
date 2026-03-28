# agent/main.py — Servidor FastAPI + Webhook de WhatsApp
# Generado por AgentKit

"""
Servidor principal del agente de WhatsApp.
Funciona con cualquier proveedor (Whapi, Meta, Twilio) gracias a la capa de providers.
"""

import os
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import generar_respuesta
from agent.memory import inicializar_db, guardar_mensaje, obtener_historial
from agent.providers import obtener_proveedor
from agent.tools import crear_evento_calendario, detectar_tipo_pregunta, crear_ticket_desde_cita, buscar_estado_reparacion

load_dotenv()

# Configuración de logging según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

# Proveedor de WhatsApp (se configura en .env con WHATSAPP_PROVIDER)
proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar el servidor."""
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — WhatsApp AI Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def health_check():
    """Endpoint de salud para Railway/monitoreo."""
    return {"status": "ok", "service": "agentkit"}


async def procesar_cita_si_existe(respuesta: str, telefono: str) -> str:
    """
    Detecta si la respuesta contiene un bloque [CITA]...[/CITA].
    Si existe, crea:
    1. Evento en Google Calendar
    2. Ticket de soporte/reparación en la base de datos
    Elimina el tag del texto visible.

    Formato esperado: [CITA]nombre|teléfono|dispositivo|YYYY-MM-DD|HH:MM[/CITA]
    """
    patron = r'\[CITA\](.*?)\[/CITA\]'
    match = re.search(patron, respuesta, re.DOTALL)

    if not match:
        return respuesta

    datos_raw = match.group(1).strip()
    partes = datos_raw.split("|")

    # Validar que tenemos los 5 datos esperados
    if len(partes) == 5:
        nombre, telefono_cita, dispositivo, fecha, hora = partes
        nombre = nombre.strip()
        telefono_cita = telefono_cita.strip()
        dispositivo = dispositivo.strip()
        fecha = fecha.strip()
        hora = hora.strip()

        # Crear evento en Google Calendar
        exito_cal = await crear_evento_calendario(nombre, telefono_cita, dispositivo, fecha, hora)
        if exito_cal:
            logger.info(f"Cita agendada en Google Calendar: {nombre}")

        # Crear ticket de soporte
        try:
            ticket_numero = await crear_ticket_desde_cita(nombre, telefono_cita, dispositivo, "Reparación agendada")
            logger.info(f"Ticket creado: {ticket_numero}")
        except Exception as e:
            logger.error(f"Error creando ticket: {e}")

    # Eliminar el tag del texto visible al cliente
    respuesta_limpia = re.sub(patron, "", respuesta, flags=re.DOTALL).strip()
    return respuesta_limpia


async def enriquecer_respuesta_soporte(respuesta: str, telefono: str, mensaje: str) -> str:
    """
    Si la pregunta es sobre soporte/estado de reparación,
    agrega el contexto de los tickets del cliente a la respuesta.
    """
    tipo_pregunta, _ = detectar_tipo_pregunta(mensaje)

    if tipo_pregunta != "soporte":
        return respuesta

    try:
        estado_tickets = await buscar_estado_reparacion(telefono, mensaje)
        # Agregar información de tickets al final de la respuesta
        respuesta += f"\n\n{estado_tickets}"
        logger.info(f"Respuesta enriquecida con información de tickets para {telefono}")
    except Exception as e:
        logger.error(f"Error enriqueciendo respuesta con tickets: {e}")

    return respuesta


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    """Verificación GET del webhook (requerido por Meta Cloud API, no-op para otros)."""
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Recibe mensajes de WhatsApp via el proveedor configurado.
    Procesa el mensaje, genera respuesta con Claude y la envía de vuelta.
    """
    try:
        # Parsear webhook — el proveedor normaliza el formato
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            # Ignorar mensajes propios o vacíos
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Obtener historial ANTES de guardar el mensaje actual
            # (brain.py agrega el mensaje actual, evitando duplicados)
            historial = await obtener_historial(msg.telefono)

            # Generar respuesta con Claude
            respuesta = await generar_respuesta(msg.texto, historial)

            # Procesar cita si existe en la respuesta (detectar tag [CITA] y crear en Google Calendar + Ticket)
            respuesta = await procesar_cita_si_existe(respuesta, msg.telefono)

            # Enriquecer respuesta si es pregunta de soporte (agregar estado de tickets)
            respuesta = await enriquecer_respuesta_soporte(respuesta, msg.telefono, msg.texto)

            # Guardar mensaje del usuario Y respuesta del agente en memoria
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)

            # Enviar respuesta por WhatsApp via el proveedor
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"Respuesta a {msg.telefono}: {respuesta}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
