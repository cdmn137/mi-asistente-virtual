import streamlit as st
import requests
import json
from datetime import datetime
import time
import os  # 🆕 IMPORTANTE: agregar este import

# 🆕 URL dinámica para producción
BACKEND_URL = "https://mi-asistente-backend.onrender.com"

# Configuración de página
st.set_page_config(
    page_title="Mi Asistente Virtual",
    page_icon="🤖",
    layout="centered"
)

# Título principal
st.title("🎤 Mi Asistente Virtual Inteligente")
st.markdown("**Habla conmigo y aprenderé de tus rutinas**")

# Estado de la sesión
if 'history' not in st.session_state:
    st.session_state.history = []
if 'user_id' not in st.session_state:
    st.session_state.user_id = "usuario_principal"

# =============================================
# SIDEBAR MEJORADO (CON KEYS ÚNICOS)
# =============================================
with st.sidebar:
    st.header("⚙️ Configuración Avanzada")
    
    # ✅ KEY ÚNICA AGREGADA
    st.session_state.user_id = st.text_input(
        "Tu ID:", 
        value="usuario_principal", 
        key="user_id_input"  # ← ESTA LÍNEA NUEVA
    )
    
    # Selector de modo
    mode = st.selectbox(
        "Modo de Asistente:",
        ["🤖 Básico", "🧠 Inteligente", "🚀 Avanzado"],
        key="mode_selector"  # ← KEY ÚNICA
    )
    
    if st.button("🔄 Probar Conexión Backend", key="test_connection"):
        try:
            response = requests.get(f"{BACKEND_URL}/health")
            if response.status_code == 200:
                data = response.json()
                st.success(f"✅ Backend: {data['status']} | DB: {data['database']}")
            else:
                st.error("❌ Backend no responde")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# =============================================
# MÉTRICAS DEL SISTEMA
# =============================================
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Modo", mode)
with col2:
    try:
        stats = requests.get(f"{BACKEND_URL}/stats").json()
        st.metric("Interacciones", stats["total_interactions"])
    except:
        st.metric("Interacciones", "0")
with col3:
    st.metric("Usuario", st.session_state.user_id)

# =============================================
# ENTRADA PRINCIPAL
# =============================================
st.header("💬 Conversa con tu Asistente Inteligente")

# Ejemplos de comandos (CON KEYS ÚNICOS)
st.subheader("💡 Ejemplos de lo que puedes decir:")
examples = col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Programar reunión mañana 3 PM", key="example_meeting"):
        st.session_state.auto_input = "Programar reunión con el equipo mañana a las 3 de la tarde"
with col2:
    if st.button("Recordar llamar a Juan", key="example_reminder"):
        st.session_state.auto_input = "Recordarme llamar a Juan el viernes"
with col3:
    if st.button("Crear tarea importante", key="example_task"):
        st.session_state.auto_input = "Tarea: preparar presentación para el lunes"

# Input principal (CON KEY ÚNICA)
user_input = st.text_area(
    "Escribe tu mensaje o comando de voz:",
    value=st.session_state.get('auto_input', ''),
    placeholder="Ej: 'Programar reunión con el equipo mañana a las 10 AM' o 'Recordarme comprar café'",
    height=100,
    key="main_input"  # ← YA TENÍAS ESTA KEY, BIEN!
)

# =============================================
# BOTÓN DE ENVIAR MEJORADO
# =============================================
if st.button("🚀 Enviar al Asistente", type="primary", use_container_width=True, key="send_button"):
    if user_input.strip():
        with st.spinner("El asistente está procesando tu solicitud..."):
            try:
                payload = {
                    "user_input": user_input,
                    "user_id": st.session_state.user_id
                }
                
                response = requests.post(f"{BACKEND_URL}/interact", json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Agregar al historial
                    interaction = {
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "user_input": user_input,
                        "assistant_response": data["response"],
                        "intent": "processed"
                    }
                    
                    st.session_state.history.insert(0, interaction)
                    
                    # Mostrar respuesta con estilo
                    st.success(f"**🤖 Asistente:** {data['response']}")
                    
                    # Auto-limpiar después de éxito
                    if 'auto_input' in st.session_state:
                        del st.session_state.auto_input
                    st.rerun()
                else:
                    error_detail = "Error desconocido"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get('detail', 'Error en el servidor')
                    except:
                        error_detail = f"Error HTTP {response.status_code}"
                    
                    st.error(f"❌ Error del servidor: {error_detail}")
                    
            except requests.exceptions.Timeout:
                st.error("⏰ El servidor tardó demasiado en responder. Por favor intenta de nuevo.")
            except requests.exceptions.ConnectionError:
                st.error("🔌 No se pudo conectar con el servidor. Verifica que el backend esté ejecutándose.") 
                    
            except Exception as e:
                st.error(f"Error de conexión: {e}")
    else:
        st.warning("Por favor escribe un mensaje antes de enviar")

# =============================================
# HISTORIAL MEJORADO
# =============================================
if st.session_state.history:
    st.header("📜 Historial de Conversación")
    
    for i, interaction in enumerate(st.session_state.history[:10]):
        with st.container():
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.write(f"**{interaction['timestamp']}**")
            
            with col2:
                st.write(f"**👤 Tú:** {interaction['user_input']}")
                st.write(f"**🤖 Asistente:** {interaction['assistant_response']}")
            
            st.divider()

# =============================================
# PANEL DE APRENDIZAJE (NUEVO)
# =============================================
with st.expander("📊 Panel de Aprendizaje del Asistente"):
    try:
        stats = requests.get(f"{BACKEND_URL}/stats").json()
        st.write(f"**Total de interacciones:** {stats['total_interactions']}")
        st.write(f"**Tus interacciones:** {stats['user_interactions']}")
        st.write(f"**Base de datos:** {stats['database']}")
        
        # Botón para ver historial completo (CON KEY)
        if st.button("Ver mi historial completo", key="view_full_history"):
            response = requests.get(f"{BACKEND_URL}/user/{st.session_state.user_id}/history?limit=20")
            if response.status_code == 200:
                data = response.json()
                st.json(data)
    except:
        st.info("Conecta con el backend para ver estadísticas")

# =============================================
# MANTENER TU CÓDIGO ORIGINAL (si tenías más cosas)
# =============================================
st.markdown("---")
st.markdown("**✨ Características en desarrollo:**")
st.markdown("- 🎤 Reconocimiento de voz")
st.markdown("- 🧠 Aprendizaje automático de rutinas")
st.markdown("- ⏰ Sistema inteligente de recordatorios")
st.markdown("- 📊 Análisis predictivo de actividades")

# =============================================
# SISTEMA DE RECORDATORIOS (NUEVA SECCIÓN)
# =============================================
st.header("🔔 Mis Recordatorios")

# 🆕 BOTÓN DE ACTUALIZACIÓN MANUAL
col1, col2 = st.columns([3, 1])
with col1:
    st.write("")  # Espacio para alinear
with col2:
    if st.button("🔄 Actualizar", key="refresh_reminders"):
        st.rerun()

tab1, tab2, tab3 = st.tabs(["📋 Activos", "✅ Completados", "➕ Nuevo Recordatorio"])

with tab1:
    st.subheader("Recordatorios Pendientes")
    
    # 🆕 AGREGAR ACTUALIZACIÓN AUTOMÁTICA TAMBIÉN AQUÍ
    current_time = time.time()
    if 'last_pending_refresh' not in st.session_state:
        st.session_state.last_pending_refresh = 0
    
    if current_time - st.session_state.last_pending_refresh > 30:
        st.session_state.last_pending_refresh = current_time
        # No hacemos rerun automático aquí para no molestar al usuario
    
    try:
        reminders_response = requests.get(f"{BACKEND_URL}/reminders/{st.session_state.user_id}?status=pending")
        if reminders_response.status_code == 200:
            reminders_data = reminders_response.json()
            
            # 🆕 MOSTRAR CONTADOR
            st.write(f"**Pendientes:** {reminders_data.get('count', 0)}")
            
            if reminders_data["reminders"]:
                for reminder in reminders_data["reminders"]:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            due_date = reminder.get("due_date", "Sin fecha")
                            if due_date and due_date != "Sin fecha":
                                try:
                                    # 🆕 MEJOR MANEJO DE FECHAS
                                    if 'T' in due_date:
                                        due_date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                                    else:
                                        due_date_obj = datetime.fromisoformat(due_date)
                                    due_date_str = due_date_obj.strftime("%d/%m/%Y %H:%M")
                                    
                                    # 🆕 CALCULAR TIEMPO RESTANTE
                                    now = datetime.now()
                                    time_left = due_date_obj - now
                                    if time_left.total_seconds() > 0:
                                        hours_left = int(time_left.total_seconds() / 3600)
                                        if hours_left < 1:
                                            time_info = f"⏳ En {int(time_left.total_seconds() / 60)} min"
                                        elif hours_left < 24:
                                            time_info = f"⏳ En {hours_left} horas"
                                        else:
                                            days_left = hours_left // 24
                                            time_info = f"⏳ En {days_left} días"
                                    else:
                                        time_info = "⚠️ Vencido"
                                except Exception as e:
                                    due_date_str = due_date
                                    time_info = ""
                            else:
                                due_date_str = "Sin fecha específica"
                                time_info = ""
                            
                            st.write(f"**{reminder['title']}**")
                            if reminder.get('description'):
                                st.write(f"_{reminder['description']}_")
                            st.write(f"⏰ {due_date_str} {time_info}")
                            st.write(f"🏷️ {reminder.get('priority', 'medium').capitalize()}")
                        
                        with col2:
                            if st.button("✅", key=f"complete_{reminder['_id']}"):
                                response = requests.put(
                                    f"{BACKEND_URL}/reminders/{reminder['_id']}", 
                                    json={"status": "completed"}
                                )
                                if response.status_code == 200:
                                    st.success("¡Completado!")
                                    time.sleep(1)  # Pequeña pausa para ver el mensaje
                                    st.rerun()
                        
                        with col3:
                            if st.button("🔄", key=f"refresh_{reminder['_id']}"):
                                st.rerun()
                        
                        st.divider()
            else:
                st.info("🎉 No tienes recordatorios pendientes.")
        else:
            st.error("Error cargando recordatorios")
    except Exception as e:
        st.error(f"Error: {e}")

with tab2:
    st.subheader("Recordatorios Completados")
    
    # 🆕 CONTADOR DE TIEMPO PARA AUTO-REFRESCO
    current_time = time.time()
    if 'last_completed_refresh' not in st.session_state:
        st.session_state.last_completed_refresh = 0
    
    # Mostrar tiempo desde última actualización
    time_since_refresh = current_time - st.session_state.last_completed_refresh
    st.caption(f"Última actualización: {int(time_since_refresh)} segundos atrás")
    
    # Auto-refrescar cada 45 segundos
    if time_since_refresh > 45:
        st.session_state.last_completed_refresh = current_time
        st.rerun()
    
    try:
        # 🆕 AGREGAR PARÁMETRO DE DEBUG PARA VER MÁS INFORMACIÓN
        reminders_response = requests.get(
            f"{BACKEND_URL}/reminders/{st.session_state.user_id}?status=completed&include_debug=true"
        )
        
        if reminders_response.status_code == 200:
            reminders_data = reminders_response.json()
            
            # 🆕 INFORMACIÓN DE DEBUG (útil para troubleshooting)
            if reminders_data.get('debug'):
                with st.expander("🔍 Información técnica"):
                    st.json(reminders_data['debug'])
            
            count = reminders_data.get('count', 0)
            st.write(f"**📊 Total completados:** {count}")
            
            if count > 0:
                st.success(f"🎉 Tienes {count} recordatorio(s) completado(s)")
                
                for reminder in reminders_data["reminders"]:
                    with st.container():
                        col1, col2 = st.columns([4, 1])
                        
                        with col1:
                            title = reminder.get('title', 'Sin título')
                            description = reminder.get('description', '')
                            completed_at = reminder.get('completed_at')
                            due_date = reminder.get('due_date')
                            
                            # Formatear fecha de completado
                            if completed_at:
                                try:
                                    completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                                    completed_str = completed_date.strftime("%d/%m/%Y a las %H:%M")
                                except:
                                    completed_str = str(completed_at)
                            else:
                                completed_str = "Recientemente"
                            
                            # Mostrar información
                            st.write(f"✅ **{title}**")
                            if description:
                                st.write(f"📝 {description}")
                            
                            # Mostrar fecha programada original si existe
                            if due_date:
                                try:
                                    due_date_obj = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                                    original_str = due_date_obj.strftime("%d/%m/%Y %H:%M")
                                    st.write(f"📅 Programado originalmente: {original_str}")
                                except:
                                    pass
                            
                            st.write(f"🕐 **Completado:** {completed_str}")
                        
                        with col2:
                            # Opción para eliminar o archivar
                            if st.button("🗑️", key=f"delete_{reminder['_id']}"):
                                st.info("Función de eliminación en desarrollo")
                        
                        st.divider()
            else:
                st.info("📝 Aún no has completado recordatorios. Los recordatorios se mostrarán aquí automáticamente cuando se completen.")
                
        else:
            st.error("❌ Error cargando recordatorios completados")
            
    except requests.exceptions.ConnectionError:
        st.error("🔌 No se pudo conectar al servidor. Verifica que el backend esté ejecutándose.")
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")

with tab3:
    st.subheader("Crear Nuevo Recordatorio")
    
    with st.form("new_reminder_form"):
        title = st.text_input("📝 Título del recordatorio *", placeholder="Ej: Llamar al cliente importante")
        description = st.text_area("📄 Descripción (opcional)", placeholder="Detalles adicionales...")
        due_date = st.text_input("⏰ Fecha/Hora (opcional)", placeholder="Ej: mañana a las 3 PM, el viernes, hoy a las 14:30")
        priority = st.selectbox("🎯 Prioridad", ["medium", "high", "low", "urgent"])
        
        submitted = st.form_submit_button("🔔 Crear Recordatorio")
        
        if submitted:
            if title.strip():
                reminder_data = {
                    "user_id": st.session_state.user_id,
                    "title": title,
                    "description": description if description.strip() else None,
                    "priority": priority,
                    "tags": []
                }
                
                if due_date.strip():
                    # Enviar el texto de fecha natural al backend para parsing
                    reminder_data["due_date_text"] = due_date
                
                try:
                    response = requests.post(f"{BACKEND_URL}/reminders", json=reminder_data)
                    if response.status_code == 200:
                        st.success("¡Recordatorio creado exitosamente!")
                        st.rerun()
                    else:
                        st.error("Error creando el recordatorio")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
            else:

                st.warning("Por favor ingresa al menos un título para el recordatorio")
