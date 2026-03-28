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
from datetime import datetime

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
