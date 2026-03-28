# agent/tools.py — Herramientas del agente
# Generado por AgentKit

"""
Herramientas específicas del negocio.
Estas funciones extienden las capacidades del agente más allá de responder texto.
Claude Code genera las funciones según los casos de uso elegidos en la entrevista.
"""

import os
import yaml
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger("agentkit")


def obtener_agente_activo() -> str:
    """Retorna el nombre del agente activo desde variables de entorno."""
    return os.getenv("AGENTE_ACTIVO", "default")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde config/{AGENTE_ACTIVO}/business.yaml."""
    agente = obtener_agente_activo()
    ruta = f"config/{agente}/business.yaml"
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"{ruta} no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención del negocio."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
        "esta_abierto": True,  # TODO: calcular según hora actual y horario
    }


def buscar_en_knowledge(consulta: str) -> str:
    """
    Busca información relevante en los archivos de knowledge/{AGENTE_ACTIVO}.
    Retorna el contenido más relevante encontrado.
    """
    resultados = []
    agente = obtener_agente_activo()
    knowledge_dir = f"knowledge/{agente}"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                # Búsqueda simple por coincidencia de texto
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


def consultar_precios() -> dict:
    """
    Carga el catálogo de precios del agente activo desde precios.yaml.
    Retorna el diccionario completo con estructura de precios.
    """
    agente = obtener_agente_activo()
    ruta = f"config/{agente}/precios.yaml"

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            precios = yaml.safe_load(f) or {}
            logger.info(f"Catálogo de precios cargado para agente: {agente}")
            return precios
    except FileNotFoundError:
        logger.warning(f"Archivo de precios no encontrado: {ruta}")
        return {}


def detectar_tipo_pregunta(mensaje: str) -> tuple[str, str]:
    """
    Detecta el tipo de pregunta según los filtros configurados en prompts.yaml.
    Lee la configuración del agente activo y busca coincidencias con keywords.

    Retorna (tipo_detectado: str, instruccion_extra: str).
    Si no hay coincidencia, retorna ("general", "").
    """
    agente = obtener_agente_activo()
    ruta = f"config/{agente}/prompts.yaml"

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"No se pudo cargar {ruta} para detectar tipo de pregunta")
        return "general", ""

    # Obtener los filtros configurados para este agente
    filtros = config.get("filtros", {})
    if not filtros:
        return "general", ""

    mensaje_lower = mensaje.lower()

    # Buscar el primer tipo que coincida con los keywords
    for tipo, cfg in filtros.items():
        keywords = cfg.get("keywords", [])
        instruccion = cfg.get("instruccion_extra", "")

        # Verificar si alguna keyword está en el mensaje
        if any(k in mensaje_lower for k in keywords):
            logger.info(f"Tipo de pregunta detectado: {tipo}")
            return tipo, instruccion

    return "general", ""


async def crear_evento_calendario(nombre: str, telefono: str, dispositivo: str,
                                   fecha: str, hora: str) -> bool:
    """
    Crea un evento en Google Calendar para la cita del cliente.
    Requiere variables de entorno: GOOGLE_CALENDAR_CREDENTIALS y GOOGLE_CALENDAR_ID
    Retorna True si fue exitoso, False si no hay credenciales o hubo error.
    """
    credentials_json = os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID")

    if not credentials_json or not calendar_id:
        logger.warning("Google Calendar no configurado — cita no creada en calendario")
        return False

    try:
        # Importar Google libraries (solo si están configuradas)
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Parsear credenciales
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/calendar"]
        )

        # Construir cliente de Google Calendar
        service = build("calendar", "v3", credentials=credentials)

        # Crear timestamps
        inicio = f"{fecha}T{hora}:00"
        dt_inicio = datetime.fromisoformat(inicio)
        dt_fin = dt_inicio + timedelta(hours=1)
        fin = dt_fin.isoformat()

        # Obtener info del negocio para el evento
        agente = obtener_agente_activo()
        info = cargar_info_negocio()
        nombre_negocio = info.get("negocio", {}).get("nombre", agente)

        # Estructura del evento
        evento = {
            "summary": f"Cita - {dispositivo} ({nombre})",
            "description": (
                f"Cliente: {nombre}\n"
                f"Teléfono: {telefono}\n"
                f"Dispositivo: {dispositivo}\n"
                f"Agendado via {nombre_negocio} Bot"
            ),
            "start": {
                "dateTime": inicio,
                "timeZone": "America/Argentina/Buenos_Aires"
            },
            "end": {
                "dateTime": fin,
                "timeZone": "America/Argentina/Buenos_Aires"
            },
        }

        # Insertar evento en Google Calendar
        service.events().insert(calendarId=calendar_id, body=evento).execute()
        logger.info(f"Evento creado en Google Calendar: {nombre} - {fecha} {hora}")
        return True

    except Exception as e:
        logger.error(f"Error Google Calendar: {e}")
        return False


# ════════════════════════════════════════════════════════════
# Herramientas específicas para Mundo Electronico
# ════════════════════════════════════════════════════════════

def obtener_servicios_disponibles() -> list[str]:
    """Retorna la lista de servicios que ofrece el negocio."""
    return [
        "Reparación de celulares",
        "Reparación de tablets",
        "Reparación de notebooks",
        "Cambio de componentes",
        "Actualizaciones de software",
        "Venta de accesorios",
        "Punto Pickit",
        "Correo Argentino"
    ]


def validar_dispositivo(dispositivo: str) -> bool:
    """Valida si es un dispositivo que el negocio repara."""
    dispositivos_validos = ["celular", "smartphone", "teléfono", "tablet", "notebook", "laptop", "computadora portátil"]
    return any(d in dispositivo.lower() for d in dispositivos_validos)


def crear_resumen_cita(nombre: str, telefono: str, dispositivo: str, problema: str, horario: str) -> str:
    """Crea un resumen de cita para confirmar con el cliente."""
    return f"""
📋 **Resumen de tu cita:**
Nombre: {nombre}
Teléfono: {telefono}
Dispositivo: {dispositivo}
Problema: {problema}
Horario: {horario}

Te esperamos en nuestro local. ¡Gracias por tu confianza! 🙏
"""
