# agent/admin.py — Dashboard Admin para gestionar tickets
# Generado por AgentKit

"""
Interfaz web para que el dueño del negocio vea y actualice tickets de reparación.
Accesible en /admin (protegida con contraseña simple)
"""

import os
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from agent.memory import buscar_tickets_por_telefono, actualizar_ticket
from agent.memory import async_session, Ticket, select

logger = logging.getLogger("agentkit")

admin_router = APIRouter()

# Contraseña admin (cambiar en .env: ADMIN_PASSWORD)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def verificar_sesion(request: Request) -> bool:
    """Verifica si el usuario tiene sesión admin válida."""
    session_cookie = request.cookies.get("admin_session")
    return session_cookie == ADMIN_PASSWORD


async def obtener_todos_los_tickets() -> list[dict]:
    """Obtiene todos los tickets de la base de datos (con paginación simple)."""
    async with async_session() as session:
        query = select(Ticket).order_by(Ticket.fecha_creacion.desc()).limit(100)
        result = await session.execute(query)
        tickets = result.scalars().all()

        return [
            {
                "id": t.id,
                "ticket_numero": t.ticket_numero,
                "nombre_cliente": t.nombre_cliente,
                "telefono": t.telefono,
                "dispositivo": t.dispositivo,
                "problema": t.problema,
                "estado": t.estado,
                "fecha_creacion": t.fecha_creacion.strftime("%d/%m/%Y %H:%M"),
                "fecha_actualizacion": t.fecha_actualizacion.strftime("%d/%m/%Y %H:%M"),
                "notas": t.notas,
            }
            for t in tickets
        ]


def generar_html_dashboard(tickets: list[dict]) -> str:
    """Genera el HTML del dashboard."""

    estados = {
        "abierto": "🆕 Abierto",
        "en_progreso": "⚙️ En progreso",
        "completado": "✅ Completado",
        "cerrado": "✓ Cerrado",
    }

    filas_html = ""
    for t in tickets:
        estado_label = estados.get(t["estado"], t["estado"])
        notas_preview = t["notas"][:50] + "..." if len(t["notas"]) > 50 else t["notas"]

        filas_html += f"""
        <tr>
            <td class="numero">{t['ticket_numero']}</td>
            <td>{t['nombre_cliente']}</td>
            <td>{t['dispositivo']}</td>
            <td>{t['problema'][:30]}</td>
            <td>
                <select name="estado" onchange="cambiarEstado('{t['id']}', this.value)" class="estado-select {t['estado']}">
                    <option value="abierto" {'selected' if t['estado'] == 'abierto' else ''}>🆕 Abierto</option>
                    <option value="en_progreso" {'selected' if t['estado'] == 'en_progreso' else ''}>⚙️ En progreso</option>
                    <option value="completado" {'selected' if t['estado'] == 'completado' else ''}>✅ Completado</option>
                    <option value="cerrado" {'selected' if t['estado'] == 'cerrado' else ''}>✓ Cerrado</option>
                </select>
            </td>
            <td>{t['fecha_creacion']}</td>
            <td>
                <button onclick="abrirNotas('{t['id']}', '{t['ticket_numero']}')" class="btn-notas">Notas</button>
            </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin Dashboard — Tickets</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}

            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                overflow: hidden;
            }}

            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}

            .header h1 {{
                font-size: 28px;
                margin-bottom: 8px;
            }}

            .header p {{
                opacity: 0.9;
                font-size: 14px;
            }}

            .content {{
                padding: 30px;
            }}

            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}

            .stat-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }}

            .stat-card h3 {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                margin-bottom: 8px;
            }}

            .stat-card .number {{
                font-size: 32px;
                font-weight: bold;
                color: #667eea;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}

            th {{
                background: #f8f9fa;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                color: #333;
                font-size: 13px;
                text-transform: uppercase;
                border-bottom: 2px solid #e9ecef;
            }}

            td {{
                padding: 15px;
                border-bottom: 1px solid #e9ecef;
                font-size: 14px;
            }}

            tr:hover {{
                background: #f8f9fa;
            }}

            .numero {{
                font-weight: 600;
                color: #667eea;
            }}

            .estado-select {{
                padding: 6px 10px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-size: 13px;
                cursor: pointer;
                background: white;
            }}

            .estado-select.abierto {{
                border-color: #ffc107;
                color: #ff6b6b;
            }}

            .estado-select.en_progreso {{
                border-color: #17a2b8;
                color: #0c5460;
            }}

            .estado-select.completado {{
                border-color: #28a745;
                color: #155724;
            }}

            .estado-select.cerrado {{
                border-color: #6c757d;
                color: #383d41;
            }}

            .btn-notas {{
                background: #667eea;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                transition: background 0.2s;
            }}

            .btn-notas:hover {{
                background: #764ba2;
            }}

            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
            }}

            .modal-content {{
                background-color: white;
                margin: 5% auto;
                padding: 30px;
                border-radius: 8px;
                width: 90%;
                max-width: 500px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }}

            .modal-header {{
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 20px;
                color: #333;
            }}

            .modal-body {{
                margin-bottom: 20px;
            }}

            .modal-body textarea {{
                width: 100%;
                padding: 12px;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                font-family: monospace;
                font-size: 13px;
                resize: vertical;
                min-height: 120px;
            }}

            .modal-footer {{
                display: flex;
                gap: 10px;
                justify-content: flex-end;
            }}

            .btn {{
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s;
            }}

            .btn-primary {{
                background: #667eea;
                color: white;
            }}

            .btn-primary:hover {{
                background: #764ba2;
            }}

            .btn-secondary {{
                background: #e9ecef;
                color: #333;
            }}

            .btn-secondary:hover {{
                background: #dee2e6;
            }}

            .close {{
                color: #aaa;
                float: right;
                font-size: 28px;
                font-weight: bold;
                cursor: pointer;
            }}

            .close:hover {{
                color: #000;
            }}

            .loading {{
                display: none;
                text-align: center;
                padding: 20px;
                color: #666;
            }}

            .success-msg {{
                background: #d4edda;
                color: #155724;
                padding: 12px 20px;
                border-radius: 4px;
                margin-bottom: 20px;
                display: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📋 Dashboard de Tickets</h1>
                <p>Gestiona todas las reparaciones en un solo lugar</p>
            </div>

            <div class="content">
                <div class="success-msg" id="successMsg">✓ Cambio guardado correctamente</div>

                <div class="stats">
                    <div class="stat-card">
                        <h3>Total de Tickets</h3>
                        <div class="number">{len(tickets)}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Abiertos</h3>
                        <div class="number">{sum(1 for t in tickets if t['estado'] == 'abierto')}</div>
                    </div>
                    <div class="stat-card">
                        <h3>En Progreso</h3>
                        <div class="number">{sum(1 for t in tickets if t['estado'] == 'en_progreso')}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Completados</h3>
                        <div class="number">{sum(1 for t in tickets if t['estado'] == 'completado')}</div>
                    </div>
                </div>

                <div class="loading" id="loading">Guardando...</div>

                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Ticket</th>
                                <th>Cliente</th>
                                <th>Dispositivo</th>
                                <th>Problema</th>
                                <th>Estado</th>
                                <th>Creado</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Modal para notas -->
        <div id="notasModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="cerrarModal()">&times;</span>
                <div class="modal-header">Notas para <span id="ticketNum"></span></div>
                <div class="modal-body">
                    <textarea id="notasText" placeholder="Agrega notas sobre el estado de esta reparación..."></textarea>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="cerrarModal()">Cancelar</button>
                    <button class="btn btn-primary" onclick="guardarNotas()">Guardar</button>
                </div>
            </div>
        </div>

        <script>
            let ticketActual = null;

            async function cambiarEstado(ticketId, nuevoEstado) {{
                document.getElementById('loading').style.display = 'block';
                try {{
                    const response = await fetch('/admin/actualizar', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            ticket_id: ticketId,
                            estado: nuevoEstado
                        }})
                    }});

                    if (response.ok) {{
                        mostrarExito();
                        setTimeout(() => location.reload(), 1500);
                    }} else {{
                        alert('Error al guardar');
                    }}
                }} catch (e) {{
                    alert('Error: ' + e);
                }} finally {{
                    document.getElementById('loading').style.display = 'none';
                }}
            }}

            function abrirNotas(ticketId, ticketNum) {{
                ticketActual = ticketId;
                document.getElementById('ticketNum').textContent = ticketNum;
                document.getElementById('notasText').value = '';
                document.getElementById('notasModal').style.display = 'block';
            }}

            function cerrarModal() {{
                document.getElementById('notasModal').style.display = 'none';
                ticketActual = null;
            }}

            async function guardarNotas() {{
                const nota = document.getElementById('notasText').value;
                if (!nota.trim()) {{
                    alert('Escribe una nota');
                    return;
                }}

                document.getElementById('loading').style.display = 'block';
                try {{
                    const response = await fetch('/admin/actualizar', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            ticket_id: ticketActual,
                            nota: nota
                        }})
                    }});

                    if (response.ok) {{
                        cerrarModal();
                        mostrarExito();
                        setTimeout(() => location.reload(), 1500);
                    }} else {{
                        alert('Error al guardar');
                    }}
                }} catch (e) {{
                    alert('Error: ' + e);
                }} finally {{
                    document.getElementById('loading').style.display = 'none';
                }}
            }}

            function mostrarExito() {{
                const msg = document.getElementById('successMsg');
                msg.style.display = 'block';
                setTimeout(() => {{
                    msg.style.display = 'none';
                }}, 2000);
            }}

            window.onclick = function(event) {{
                const modal = document.getElementById('notasModal');
                if (event.target == modal) {{
                    cerrarModal();
                }}
            }}
        </script>
    </body>
    </html>
    """

    return html


@admin_router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Dashboard principal de admin."""
    if not verificar_sesion(request):
        # Mostrar página de login
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Admin Login</title>
            <style>
                body { font-family: sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .login-box { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
                h1 { text-align: center; color: #333; margin-bottom: 30px; }
                input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
                button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
                button:hover { background: #764ba2; }
                .error { color: #dc3545; text-align: center; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="login-box">
                <h1>🔐 Admin Dashboard</h1>
                <form method="POST" action="/admin/login">
                    <input type="password" name="password" placeholder="Contraseña" required>
                    <button type="submit">Entrar</button>
                </form>
            </div>
        </body>
        </html>
        """

    # Usuario autenticado — mostrar dashboard
    tickets = await obtener_todos_los_tickets()
    html = generar_html_dashboard(tickets)
    return HTMLResponse(content=html)


@admin_router.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Valida contraseña y crea sesión."""
    response = RedirectResponse(url="/admin", status_code=302)
    if password == ADMIN_PASSWORD:
        response.set_cookie(
            "admin_session",
            ADMIN_PASSWORD,
            max_age=86400 * 7,  # 7 días
            httponly=True,
        )
        return response
    else:
        # Login fallido — volver al login con error
        return RedirectResponse(url="/admin?error=1", status_code=302)


@admin_router.post("/admin/actualizar")
async def admin_actualizar(request: Request):
    """Actualiza estado o notas de un ticket."""
    if not verificar_sesion(request):
        raise HTTPException(status_code=401, detail="No autorizado")

    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="JSON inválido")

    ticket_id = body.get("ticket_id")
    estado = body.get("estado")
    nota = body.get("nota")

    if not ticket_id:
        raise HTTPException(status_code=400, detail="ticket_id requerido")

    # Obtener el ticket
    async with async_session() as session:
        query = select(Ticket).where(Ticket.id == ticket_id)
        result = await session.execute(query)
        ticket = result.scalar_one_or_none()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        if estado:
            ticket.estado = estado
            logger.info(f"Ticket {ticket.ticket_numero} estado cambiado a: {estado}")

        if nota:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            ticket.notas += f"\n[{timestamp}] {nota}"
            logger.info(f"Nota agregada a {ticket.ticket_numero}")

        ticket.fecha_actualizacion = datetime.utcnow()
        session.add(ticket)
        await session.commit()

    return {"status": "ok"}
