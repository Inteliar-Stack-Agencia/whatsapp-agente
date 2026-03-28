# agent/memory.py — Memoria de conversaciones con SQLite
# Generado por AgentKit

"""
Sistema de memoria del agente. Guarda el historial de conversaciones
por número de teléfono usando SQLite (local) o PostgreSQL (producción).
"""

import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, select, Integer
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

# Obtener el agente activo
AGENTE_ACTIVO = os.getenv("AGENTE_ACTIVO", "default")

# Configuración de base de datos
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///./data/{AGENTE_ACTIVO}/agentkit.db")

# Crear el directorio de datos si no existe (para SQLite local)
if DATABASE_URL.startswith("sqlite"):
    data_dir = f"./data/{AGENTE_ACTIVO}"
    os.makedirs(data_dir, exist_ok=True)

# Si es PostgreSQL en producción, ajustar el esquema de URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Mensaje(Base):
    """Modelo de mensaje en la base de datos."""
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" o "assistant"
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Ticket(Base):
    """Modelo de ticket de soporte/reparación."""
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_numero: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    nombre_cliente: Mapped[str] = mapped_column(String(255))
    dispositivo: Mapped[str] = mapped_column(String(255))
    problema: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(50))  # "abierto", "en_progreso", "completado", "cerrado"
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notas: Mapped[str] = mapped_column(Text, default="")
    agente: Mapped[str] = mapped_column(String(50))  # para multi-agente


async def inicializar_db():
    """Crea las tablas si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_mensaje(telefono: str, role: str, content: str):
    """Guarda un mensaje en el historial de conversación."""
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow()
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    """
    Recupera los últimos N mensajes de una conversación.

    Args:
        telefono: Número de teléfono del cliente
        limite: Máximo de mensajes a recuperar (default: 20)

    Returns:
        Lista de diccionarios con role y content
    """
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()

        # Invertir para orden cronológico (los más recientes están primero)
        mensajes.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in mensajes
        ]


async def limpiar_historial(telefono: str):
    """Borra todo el historial de una conversación."""
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        mensajes = result.scalars().all()
        for msg in mensajes:
            session.delete(msg)
        await session.commit()


# ════════════════════════════════════════════════════════════
# FUNCIONES PARA TICKETS DE SOPORTE/REPARACIÓN
# ════════════════════════════════════════════════════════════

async def crear_ticket(telefono: str, nombre_cliente: str, dispositivo: str, problema: str, agente: str) -> str:
    """
    Crea un nuevo ticket de reparación.

    Returns:
        El número de ticket (ej: "MER-20260328-001")
    """
    async with async_session() as session:
        # Generar número de ticket único
        fecha = datetime.utcnow().strftime("%Y%m%d")
        agente_prefix = agente[:3].upper()

        # Contar tickets del agente hoy
        count_query = (
            select(Ticket)
            .where(Ticket.agente == agente)
            .where(Ticket.fecha_creacion >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
        )
        count_result = await session.execute(count_query)
        count = len(count_result.scalars().all()) + 1

        ticket_numero = f"{agente_prefix}-{fecha}-{str(count).zfill(3)}"

        ticket = Ticket(
            ticket_numero=ticket_numero,
            telefono=telefono,
            nombre_cliente=nombre_cliente,
            dispositivo=dispositivo,
            problema=problema,
            estado="abierto",
            agente=agente,
            notas=f"Ticket creado automáticamente"
        )
        session.add(ticket)
        await session.commit()
        return ticket_numero


async def consultar_ticket(ticket_numero: str) -> dict | None:
    """Busca un ticket por número y retorna sus detalles."""
    async with async_session() as session:
        query = select(Ticket).where(Ticket.ticket_numero == ticket_numero)
        result = await session.execute(query)
        ticket = result.scalar_one_or_none()

        if not ticket:
            return None

        return {
            "ticket_numero": ticket.ticket_numero,
            "nombre_cliente": ticket.nombre_cliente,
            "dispositivo": ticket.dispositivo,
            "problema": ticket.problema,
            "estado": ticket.estado,
            "fecha_creacion": ticket.fecha_creacion.isoformat(),
            "fecha_actualizacion": ticket.fecha_actualizacion.isoformat(),
            "notas": ticket.notas,
        }


async def buscar_tickets_por_telefono(telefono: str) -> list[dict]:
    """Busca todos los tickets de un cliente por su teléfono."""
    async with async_session() as session:
        query = (
            select(Ticket)
            .where(Ticket.telefono == telefono)
            .order_by(Ticket.fecha_creacion.desc())
        )
        result = await session.execute(query)
        tickets = result.scalars().all()

        return [
            {
                "ticket_numero": t.ticket_numero,
                "dispositivo": t.dispositivo,
                "estado": t.estado,
                "fecha_creacion": t.fecha_creacion.isoformat(),
                "problema": t.problema,
            }
            for t in tickets
        ]


async def actualizar_ticket(ticket_numero: str, estado: str, nota: str = "") -> bool:
    """
    Actualiza el estado de un ticket y agrega una nota.

    Args:
        ticket_numero: Número del ticket (ej: "MER-20260328-001")
        estado: Nuevo estado ("abierto", "en_progreso", "completado", "cerrado")
        nota: Nota adicional a agregar

    Returns:
        True si se actualizó, False si no existe
    """
    async with async_session() as session:
        query = select(Ticket).where(Ticket.ticket_numero == ticket_numero)
        result = await session.execute(query)
        ticket = result.scalar_one_or_none()

        if not ticket:
            return False

        ticket.estado = estado
        if nota:
            ticket.notas += f"\n[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {nota}"
        ticket.fecha_actualizacion = datetime.utcnow()

        session.add(ticket)
        await session.commit()
        return True
