# agent/supabase_client.py — Cliente centralizado de Supabase
# Maneja todas las operaciones con la base de datos centralizada

import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("agentkit")

# Inicializar cliente de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("SUPABASE_URL o SUPABASE_KEY no configurados — usando SQLite local")
    supabase_client: Client = None
else:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Cliente de Supabase inicializado correctamente")
    except Exception as e:
        logger.error(f"Error inicializando Supabase: {e}")
        supabase_client = None


def is_supabase_enabled() -> bool:
    """Retorna True si Supabase está disponible."""
    return supabase_client is not None


async def obtener_config_cliente(client_id: str) -> dict:
    """
    Lee la configuración del bot desde la tabla ai_prompts en Supabase.

    Args:
        client_id: UUID del cliente en Supabase

    Returns:
        Dict con system_prompt, tone, business_type, objective
    """
    if not is_supabase_enabled():
        return {}

    try:
        result = supabase_client.table("ai_prompts").select("*").eq("client_id", client_id).limit(1).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return {}
    except Exception as e:
        logger.error(f"Error obteniendo config del cliente {client_id}: {e}")
        return {}


async def obtener_cliente_por_telefono(telefono: str) -> dict:
    """
    Busca el cliente por su número de teléfono en la tabla clients.

    Args:
        telefono: Número de teléfono del cliente

    Returns:
        Dict con datos del cliente (id, name, business_type, etc.) o empty dict
    """
    if not is_supabase_enabled():
        return {}

    try:
        result = supabase_client.table("clients").select("*").eq("whatsapp", telefono).limit(1).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return {}
    except Exception as e:
        logger.error(f"Error buscando cliente con teléfono {telefono}: {e}")
        return {}


async def guardar_mensaje_supabase(client_id: str, telefono: str, role: str, content: str):
    """
    Guarda un mensaje en la tabla conversations.

    Args:
        client_id: UUID del cliente
        telefono: Número de teléfono
        role: "user" o "assistant"
        content: Contenido del mensaje
    """
    if not is_supabase_enabled():
        return

    try:
        supabase_client.table("conversations").insert({
            "client_id": client_id,
            "telefono": telefono,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        logger.error(f"Error guardando mensaje en Supabase: {e}")


async def obtener_historial_supabase(client_id: str, telefono: str, limite: int = 20) -> list[dict]:
    """
    Obtiene el historial de conversaciones de un cliente.

    Args:
        client_id: UUID del cliente
        telefono: Número de teléfono
        limite: Máximo de mensajes a recuperar

    Returns:
        Lista de mensajes ordenados por fecha (más antiguos primero)
    """
    if not is_supabase_enabled():
        return []

    try:
        result = supabase_client.table("conversations").select("*").eq(
            "client_id", client_id
        ).eq(
            "telefono", telefono
        ).order("created_at", desc=False).limit(limite).execute()

        if result.data:
            return [
                {"role": msg["role"], "content": msg["content"]}
                for msg in result.data
            ]
        return []
    except Exception as e:
        logger.error(f"Error obteniendo historial de {telefono}: {e}")
        return []


async def crear_ticket_supabase(client_id: str, ticket_numero: str, nombre_cliente: str,
                                telefono: str, dispositivo: str, problema: str, agente: str = None) -> bool:
    """
    Crea un ticket en la tabla tickets.

    Args:
        client_id: UUID del cliente
        ticket_numero: Número único del ticket (ej: MUN-20260328-001)
        nombre_cliente: Nombre del cliente
        telefono: Número de teléfono
        dispositivo: Dispositivo a reparar
        problema: Descripción del problema
        agente: Nombre del agente (opcional)

    Returns:
        True si fue exitoso, False si falló
    """
    if not is_supabase_enabled():
        return False

    try:
        supabase_client.table("tickets").insert({
            "client_id": client_id,
            "ticket_numero": ticket_numero,
            "nombre_cliente": nombre_cliente,
            "telefono": telefono,
            "dispositivo": dispositivo,
            "problema": problema,
            "estado": "abierto",
            "agente": agente
        }).execute()
        logger.info(f"Ticket creado en Supabase: {ticket_numero}")
        return True
    except Exception as e:
        logger.error(f"Error creando ticket en Supabase: {e}")
        return False


async def obtener_tickets_cliente(client_id: str, telefono: str) -> list[dict]:
    """
    Obtiene todos los tickets de un cliente por teléfono.

    Args:
        client_id: UUID del cliente
        telefono: Número de teléfono

    Returns:
        Lista de tickets
    """
    if not is_supabase_enabled():
        return []

    try:
        result = supabase_client.table("tickets").select("*").eq(
            "client_id", client_id
        ).eq(
            "telefono", telefono
        ).order("fecha_creacion", desc=True).execute()

        if result.data:
            return result.data
        return []
    except Exception as e:
        logger.error(f"Error obteniendo tickets de {telefono}: {e}")
        return []


async def actualizar_ticket_supabase(ticket_numero: str, estado: str = None, notas: str = None) -> bool:
    """
    Actualiza el estado o notas de un ticket.

    Args:
        ticket_numero: Número del ticket
        estado: Nuevo estado (opcional)
        notas: Nuevas notas (opcional)

    Returns:
        True si fue exitoso
    """
    if not is_supabase_enabled():
        return False

    try:
        update_data = {}
        if estado:
            update_data["estado"] = estado
        if notas:
            update_data["notas"] = notas

        if update_data:
            supabase_client.table("tickets").update(update_data).eq(
                "ticket_numero", ticket_numero
            ).execute()

        return True
    except Exception as e:
        logger.error(f"Error actualizando ticket {ticket_numero}: {e}")
        return False
