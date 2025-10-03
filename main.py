from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from bson import ObjectId
import os
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta
from enum import Enum
import logging
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
import pytz

# Cargar variables de entorno
load_dotenv()

# 🆕 CONFIGURACIÓN PARA VENEZUELA (Caracas)
TIMEZONE = pytz.timezone('America/Caracas')  # UTC-4

def get_local_now():
    """Obtiene la fecha/hora actual en la zona horaria de Venezuela"""
    return datetime.now(TIMEZONE)

def get_utc_now():
    """Obtiene la fecha/hora actual en UTC"""
    return datetime.now(timezone.utc)

def local_to_utc(local_dt):
    """Convierte datetime local a UTC"""
    if local_dt.tzinfo is None:
        local_dt = TIMEZONE.localize(local_dt)
    return local_dt.astimezone(timezone.utc)

def utc_to_local(utc_dt):
    """Convierte datetime UTC a local"""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(TIMEZONE)

def make_naive(dt):
    """Convierte datetime aware a naive (sin timezone)"""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt

# Configuración de Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 🆕 DEBUG DETALLADO
print("=== CONFIGURACIÓN TELEGRAM ===")
print(f"Archivo .env cargado: {os.path.exists('.env')}")
print(f"TELEGRAM_BOT_TOKEN: {'✅' if TELEGRAM_BOT_TOKEN else '❌'} {'CONFIGURADO' if TELEGRAM_BOT_TOKEN else 'NO CONFIGURADO'}")
print(f"TELEGRAM_CHAT_ID: {'✅' if TELEGRAM_CHAT_ID else '❌'} {'CONFIGURADO' if TELEGRAM_CHAT_ID else 'NO CONFIGURADO'}")

if TELEGRAM_BOT_TOKEN:
    print(f"Token: {TELEGRAM_BOT_TOKEN[:8]}... (longitud: {len(TELEGRAM_BOT_TOKEN)})")
if TELEGRAM_CHAT_ID:
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
print("===============================")

# 🆕 SI NO SE CARGAN, USAR VALORES DIRECTOS TEMPORALMENTE
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("⚠️  Usando valores directos para Telegram...")
    TELEGRAM_BOT_TOKEN = "8289894192:AAGyCx4goxHsIRPfp0-RPn0GbjCcitMReSQ"
    TELEGRAM_CHAT_ID = "1000810125"
    print("✅ Valores directos configurados")

# 🆕 PROBAR CONEXIÓN CON TELEGRAM AL INICIAR
async def test_telegram_connection():
    """Probar la conexión con Telegram al iniciar la aplicación"""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        test_message = "🔔 <b>ASISTENTE INICIADO</b>\n\n¡Tu asistente virtual se ha iniciado correctamente! 🤖\n\nAhora recibirás notificaciones de recordatorios y reuniones por Telegram."
        success = await send_telegram_message(test_message)
        if success:
            print("✅ Prueba de Telegram: MENSAJE ENVIADO EXITOSAMENTE")
        else:
            print("❌ Prueba de Telegram: FALLÓ EL ENVÍO")
    else:
        print("❌ Prueba de Telegram: TOKENS NO CONFIGURADOS")

# Ejecutar la prueba al inicio
import asyncio
asyncio.create_task(test_telegram_connection())

async def send_telegram_message(message: str):
    """Envía un mensaje a través de Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("❌ Tokens de Telegram no configurados")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        print(f"📤 Enviando mensaje a Telegram: {message[:50]}...")
        
        # Configurar connector para evitar problemas de SSL en desarrollo
        connector = aiohttp.TCPConnector(verify_ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload, timeout=30) as response:
                if response.status == 200:
                    print("✅ Mensaje de Telegram enviado exitosamente")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Error Telegram API (HTTP {response.status}): {error_text}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ Timeout enviando mensaje a Telegram")
        return False
    except Exception as e:
        print(f"❌ Error de conexión Telegram: {e}")
        return False

def send_telegram_message_sync(message: str):
    """Versión síncrona para usar en funciones no async"""
    import requests
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Tokens de Telegram no configurados")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        print(f"📤 [SYNC] Enviando mensaje a Telegram: {message[:50]}...")
        response = requests.post(url, json=payload, timeout=10, verify=False)
        if response.status_code == 200:
            print("✅ [SYNC] Mensaje de Telegram enviado exitosamente")
            return True
        else:
            print(f"❌ [SYNC] Error Telegram API (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ [SYNC] Error de conexión Telegram: {e}")
        return False
    
# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReminderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"

class ReminderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class ReminderCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: ReminderPriority = ReminderPriority.MEDIUM
    tags: List[str] = []
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None  # "daily", "weekly", "monthly"

# Sistema de memoria de contexto
class ConversationContext:
    def __init__(self):
        self.last_intent = None
        self.pending_actions = []
        self.user_preferences = {}
    
    def update_context(self, intent: str, entities: Dict):
        self.last_intent = intent
        # Aquí agregaremos más lógica después
    
conversation_context = ConversationContext()

# Sistema de entidades (información extraída)
def extract_entities(user_input: str) -> Dict[str, Any]:
    """Extrae información importante del texto del usuario"""
    entities = {}
    input_lower = user_input.lower()
    
    # Extraer horas
    time_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm|hrs)?'
    time_matches = re.findall(time_pattern, input_lower)
    if time_matches:
        entities['time'] = time_matches[0][0] + ':00'
    
    # Extraer días
    days = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo', 'hoy', 'mañana']
    for day in days:
        if day in input_lower:
            entities['day'] = day
            break
    
    # Extraer tipos de eventos
    event_keywords = {
        'reunión': 'meeting',
        'reunion': 'meeting', 
        'llamada': 'call',
        'tarea': 'task',
        'recordatorio': 'reminder',
        'evento': 'event'
    }
    
    for keyword, event_type in event_keywords.items():
        if keyword in input_lower:
            entities['event_type'] = event_type
            break
    
    return entities

# Sistema de intenciones mejorado
def detect_intent(user_input: str) -> str:
    """Detecta la intención del usuario de manera más inteligente"""
    input_lower = user_input.lower()
    
    intent_patterns = {
        'greeting': ['hola', 'hi', 'buenos días', 'buenas tardes'],
        'schedule_meeting': ['reunión', 'reunion', 'meeting', 'programar reunión'],
        'create_reminder': ['recordar', 'recordatorio', 'reminder', 'no olvidar'],
        'create_task': ['tarea', 'task', 'pendiente', 'por hacer'],
        'ask_help': ['ayuda', 'help', 'qué puedes hacer'],
        'thank_you': ['gracias', 'thanks', 'thank you']
    }
    
    for intent, patterns in intent_patterns.items():
        if any(pattern in input_lower for pattern in patterns):
            return intent
    
    return 'unknown'


app = FastAPI(title="Virtual Assistant API")

# CORS para permitir Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión MongoDB Atlas - SEGURO
MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "virtual_assistant")

try:
    client = MongoClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    # Verificar conexión
    client.admin.command('ping')
    print("✅ Conectado a MongoDB Atlas exitosamente!")
except Exception as e:
    print(f"❌ Error conectando a MongoDB: {e}")
    raise e

class Interaction(BaseModel):
    user_input: str
    user_id: str = "default_user"

class LearningPattern(BaseModel):
    user_id: str
    pattern_type: str
    data: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "¡API del Asistente Virtual funcionando!", "database": "MongoDB Atlas"}

@app.post("/interact")
async def interact(interaction: Interaction):
    """Guarda interacción y responde inteligentemente"""
    
    try:
        logger.info(f"Procesando interacción: {interaction.user_input} para usuario: {interaction.user_id}")
        
        # Guardar en MongoDB
        interaction_data = {
            "user_id": interaction.user_id,
            "user_input": interaction.user_input,
            "timestamp": datetime.utcnow(),
            "processed": False
        }
        
        result = db.interactions.insert_one(interaction_data)
        logger.info(f"Interacción guardada con ID: {result.inserted_id}")
        
        # Lógica de respuesta mejorada
        response = generate_response_complete(interaction.user_input, interaction.user_id)
        logger.info(f"Respuesta generada: {response}")
        
        # Actualizar con respuesta
        db.interactions.update_one(
            {"_id": result.inserted_id},
            {"$set": {"assistant_response": response, "processed": True}}
        )
        
        return {
            "response": response,
            "interaction_id": str(result.inserted_id),
            "status": "success"
        }
    
    except Exception as e:
        logger.error(f"Error procesando interacción: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error procesando interacción: {str(e)}")

def generate_response_complete(user_input: str, user_id: str) -> str:
    """Lógica de respuesta completa con todas las intenciones"""
    try:
        logger.info(f"Generando respuesta para: {user_input}")
        
        intent = detect_intent(user_input)
        entities = extract_entities(user_input)
        
        logger.info(f"Intención detectada: {intent}, Entidades: {entities}")
        
        # Guardar el análisis para aprendizaje futuro
        save_interaction_analysis(user_id, user_input, intent, entities)
        
        # Manejo específico de recordatorios
        if intent == 'create_reminder':
            return handle_reminder_creation(user_input, user_id, entities)
        
        # Respuestas basadas en intención + entidades
        if intent == 'greeting':
            return "¡Hola! Soy tu asistente inteligente. Puedo ayudarte a programar reuniones, crear recordatorios, y aprender de tus rutinas. ¿En qué te puedo ayudar hoy?"
        
        elif intent == 'schedule_meeting':
            return handle_meeting_scheduling(user_input, user_id, entities)
        
        elif intent == 'create_task':
            return "📝 Anotado! He agregado esta tarea a tu lista. ¿Tiene alguna fecha límite específica?"
        
        elif intent == 'ask_help':
            return """🤖 **Puedo ayudarte con:**
• 📅 Programar reuniones y eventos
• 🔔 Crear recordatorios inteligentes  
• 📝 Gestionar tus tareas pendientes
• 🧠 Aprender de tus rutinas de trabajo
• ⏰ Predecir tus necesidades futuras

Solo dime qué necesitas en lenguaje natural!"""
        
        elif intent == 'thank_you':
            return "¡De nada! Estoy aquí para hacer tu día más productivo. ¿Hay algo más en lo que pueda ayudarte?"
        
        else:
            # Análisis de intención no reconocida para aprendizaje futuro
            learn_from_unknown_input(user_input, user_id)
            return "🤔 Interesante! Todavía estoy aprendiendo a entender solicitudes como esta. ¿Podrías reformularlo de otra manera? Por ejemplo: 'Programar reunión mañana a las 3 PM' o 'Recordarme llamar a Juan'."
    
    except Exception as e:
        logger.error(f"Error en generate_response_complete: {str(e)}", exc_info=True)
        return f"❌ Lo siento, hubo un error procesando tu solicitud. Por favor intenta de nuevo. Error: {str(e)}"

def handle_meeting_scheduling(user_input: str, user_id: str, entities: Dict) -> str:
    """Maneja específicamente la programación de reuniones"""
    try:
        time_info = entities.get('time', '')
        day_info = entities.get('day', '')

        logger.info(f"Programando reunión - Día: {day_info}, Hora: {time_info}")
        
        if time_info and day_info:
            # Parsear el tiempo natural para obtener datetime
            time_text_for_parsing = f"{day_info} a las {time_info}"
            meeting_time = parse_natural_time(time_text_for_parsing)
            
            if not meeting_time:
                return f"❌ No pude entender la fecha y hora '{time_text_for_parsing}'. ¿Podrías ser más específico? Ej: 'mañana a las 10 AM'"
            
            # Extraer título de la reunión
            meeting_title = extract_meeting_title(user_input)

            # Guardar en la base de datos como reunión programada
            save_scheduled_event(user_id, 'meeting', {
                'scheduled_time': time_info,
                'scheduled_day': day_info,
                'description': user_input,
                'scheduled_datetime': meeting_time,
                'title': meeting_title
            })
            
            # CREAR RECORDATORIO AUTOMÁTICO 15 MINUTOS ANTES
            reminder_time = meeting_time - timedelta(minutes=15)
            
            reminder_data = {
                "user_id": user_id,
                "title": f"Reunión: {meeting_title}",
                "description": f"Reunión programada: {user_input}",
                "due_date": reminder_time,
                "priority": ReminderPriority.MEDIUM.value,
                "tags": ["reunión", "automático"],
                "created_at": datetime.utcnow(),
                "status": ReminderStatus.PENDING.value
            }
            
            result = db.reminders.insert_one(reminder_data)
            logger.info(f"Reunión y recordatorio creados. Recordatorio ID: {result.inserted_id}")
            
            meeting_time_str = meeting_time.strftime("%A %d de %B a las %H:%M")
            reminder_time_str = reminder_time.strftime("%H:%M")
            
            return f"✅ **¡Reunión programada!**\n\n📅 **{meeting_title}**\n🕐 **Cuándo:** {meeting_time_str}\n🔔 **Recordatorio:** {reminder_time_str} (15 minutos antes)\n\n¡El recordatorio ya está en tu lista!"
        
        elif time_info:
            return f"🕐 Entendido, programar reunión a las {time_info}. ¿Para qué día sería?"
        
        elif day_info:
            return f"📅 Reunión programada para el {day_info}. ¿A qué hora?"
        
        else:
            return "📅 Veo que quieres programar una reunión. ¿Para qué día y hora te gustaría?\n\n**Ejemplos:**\n- 'Mañana a las 10 AM'\n- 'El viernes a las 3 PM'\n- 'Hoy a las 2 de la tarde'"
    
    except Exception as e:
        logger.error(f"Error en handle_meeting_scheduling: {str(e)}", exc_info=True)
        return f"❌ Error programando la reunión: {str(e)}"

def extract_meeting_title(user_input: str) -> str:
    """Extrae el título de la reunión del texto del usuario"""
    # Remover palabras de tiempo
    time_keywords = ['mañana', 'hoy', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 
                    'sábado', 'domingo', 'a las', 'las', 'pm', 'am', 'hrs', 'horas', 'reunión', 'reunion']
    
    title = user_input
    for keyword in time_keywords:
        title = title.replace(keyword, '')
    
    # Limpiar espacios extras
    title = ' '.join(title.split()).strip()
    
    return title if title else "Reunión importante"

def handle_reminder_creation(user_input: str, user_id: str, entities: Dict) -> str:
    """Maneja la creación de recordatorios"""
    try:
        # Extraer título del recordatorio
        title = extract_reminder_title(user_input)
        
        # Parsear tiempo natural
        due_date_naive = parse_natural_time(user_input)
        
        if not due_date_naive:
            return "❌ No pude entender la fecha y hora. ¿Podrías ser más específico? Ej: 'mañana a las 10 AM' o 'en 2 horas'"
        
        # 🆕 Convertir a UTC aware para cálculos
        due_date_utc = due_date_naive.replace(tzinfo=timezone.utc)
        now_utc = get_utc_now()
        
        # Determinar prioridad
        priority = detect_priority(user_input)
        
        # Extraer tags
        tags = extract_tags(user_input)
        
        # 🆕 Si es un recordatorio de reunión, agregar tag específico
        if any(word in user_input.lower() for word in ['reunión', 'reunion', 'meeting']):
            tags.append('reunión')
        
        # Crear recordatorio
        reminder_data = {
            "user_id": user_id,
            "title": title,
            "description": user_input,
            "due_date": due_date_naive,
            "priority": priority.value,
            "tags": tags,
            "created_at": datetime.utcnow(),
            "status": ReminderStatus.PENDING.value,
            "last_reminded": None,
            "immediate_notified": False,      # 🆕 Control de notificación inmediata
            "completed_at": None,             # 🆕 Se llenará cuando se complete
            "updated_at": datetime.utcnow()   # 🆕 Última actualización
        }
        
        # Guardar en base de datos
        result = db.reminders.insert_one(reminder_data)
        
        # 🆕 Calcular tiempo hasta el recordatorio (usando UTC aware)
        time_until = due_date_utc - now_utc
        total_seconds = time_until.total_seconds()
        
        # Convertir a texto legible
        if total_seconds < 60:
            time_info = "en menos de 1 minuto"
        elif total_seconds < 3600:
            minutes = int(total_seconds / 60)
            time_info = f"en {minutes} minutos"
        elif total_seconds < 86400:
            hours = int(total_seconds / 3600)
            time_info = f"en {hours} horas"
        else:
            days = int(total_seconds / 86400)
            time_info = f"en {days} días"
        
        # 🆕 Mostrar hora local en la respuesta
        due_date_local = utc_to_local(due_date_utc)
        due_date_str = due_date_local.strftime("%d/%m/%Y a las %H:%M")
                
        return f"🔔 **Recordatorio creado:** '{title}' para el {due_date_str} ({time_info}). ¡Te avisaré y se completará automáticamente!"
    
    except Exception as e:
        logger.error(f"Error en handle_reminder_creation: {str(e)}", exc_info=True)
        return f"❌ No pude crear el recordatorio. Error: {str(e)}"

def extract_reminder_title(user_input: str) -> str:
    """Extrae el título del recordatorio del texto del usuario"""
    # Remover palabras de tiempo para obtener el título
    time_keywords = ['mañana', 'hoy', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 
                    'sábado', 'domingo', 'a las', 'las', 'pm', 'am', 'hrs', 'horas']
    
    title = user_input
    for keyword in time_keywords:
        title = title.replace(keyword, '')
    
    # Limpiar espacios extras
    title = ' '.join(title.split())
    
    return title if title else "Recordatorio importante"

def detect_priority(user_input: str) -> ReminderPriority:
    """Detecta la prioridad basada en palabras clave"""
    input_lower = user_input.lower()
    
    if any(word in input_lower for word in ['urgente', 'importante', 'crítico', 'inmediato']):
        return ReminderPriority.URGENT
    elif any(word in input_lower for word in ['alto', 'prioridad', 'esencial']):
        return ReminderPriority.HIGH
    elif any(word in input_lower for word in ['bajo', 'cuando puedas', 'sin prisa']):
        return ReminderPriority.LOW
    else:
        return ReminderPriority.MEDIUM

def extract_tags(user_input: str) -> List[str]:
    """Extrae tags relevantes del texto"""
    tags = []
    input_lower = user_input.lower()
    
    category_keywords = {
        'trabajo': ['reunión', 'oficina', 'proyecto', 'cliente', 'jefe'],
        'personal': ['casa', 'familia', 'amigos', 'personal', 'cita'],
        'salud': ['doctor', 'médico', 'ejercicio', 'gimnasio', 'salud'],
        'compras': ['comprar', 'supermercado', 'tienda', 'mercado']
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in input_lower for keyword in keywords):
            tags.append(category)
    
    return tags

@app.get("/user/{user_id}/history")
async def get_history(user_id: str, limit: int = 10):
    """Obtiene historial de interacciones"""
    try:
        interactions = list(db.interactions.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(limit))
        
        for interaction in interactions:
            interaction["_id"] = str(interaction["_id"])
            # Asegurar formato de fecha
            if "timestamp" in interaction:
                interaction["timestamp"] = interaction["timestamp"].isoformat()
        
        return {"interactions": interactions, "count": len(interactions)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo historial: {str(e)}")

@app.get("/health")
async def health_check():
    try:
        # Verificar conexión a la base de datos
        client.admin.command('ping')
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "environment": "production"
    }

@app.get("/stats")
async def get_stats():
    """Estadísticas básicas de la base de datos"""
    try:
        total_interactions = db.interactions.count_documents({})
        user_interactions = db.interactions.count_documents({"user_id": "default_user"})
        total_reminders = db.reminders.count_documents({})
        pending_reminders = db.reminders.count_documents({"status": "pending"})
        
        return {
            "total_interactions": total_interactions,
            "user_interactions": user_interactions,
            "total_reminders": total_reminders,
            "pending_reminders": pending_reminders,
            "database": DATABASE_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo estadísticas: {str(e)}")

def save_interaction_analysis(user_id: str, user_input: str, intent: str, entities: Dict):
    """Guarda el análisis para aprendizaje futuro"""
    analysis_data = {
        "user_id": user_id,
        "user_input": user_input,
        "intent": intent,
        "entities": entities,
        "analysis_timestamp": datetime.utcnow(),
        "used_for_training": False
    }
    db.interaction_analysis.insert_one(analysis_data)

def save_scheduled_event(user_id: str, event_type: str, event_data: Dict):
    """Guarda eventos programados"""
    event = {
        "user_id": user_id,
        "event_type": event_type,
        "event_data": event_data,
        "scheduled_at": datetime.utcnow(),
        "status": "scheduled"
    }
    db.scheduled_events.insert_one(event)

def learn_from_unknown_input(user_input: str, user_id: str):
    """Aprende de inputs no reconocidos"""
    # Por ahora solo guardamos para análisis futuro
    db.unknown_inputs.insert_one({
        "user_id": user_id,
        "user_input": user_input,
        "timestamp": datetime.utcnow()
    })

def parse_natural_time(time_text: str) -> Optional[datetime]:
    """
    Convierte texto natural en datetime (en timezone local)
    """
    now_local = get_local_now()
    time_text = time_text.lower().strip()
    
    logger.info(f"Parseando tiempo natural: '{time_text}' (hora local: {now_local})")
    
    # Patrones de intervalo "en X minutos/horas"
    interval_patterns = [
        (r'en\s*(\d+)\s*minutos?\s*(?:a partir de ahora)?', lambda x: timedelta(minutes=int(x))),
        (r'en\s*(\d+)\s*horas?\s*(?:a partir de ahora)?', lambda x: timedelta(hours=int(x))),
        (r'en\s*(\d+)\s*días?\s*(?:a partir de ahora)?', lambda x: timedelta(days=int(x))),
        (r'en\s*(\d+)\s*semanas?\s*(?:a partir de ahora)?', lambda x: timedelta(weeks=int(x))),
    ]
    
    for pattern, delta_func in interval_patterns:
        matches = re.findall(pattern, time_text)
        if matches:
            amount = int(matches[0])
            time_delta = delta_func(amount)
            result_time = now_local + time_delta
            logger.info(f"Intervalo detectado: {amount} -> {result_time}")
            return make_naive(local_to_utc(result_time))  # 🆕 Convertir a UTC y hacer naive
    
    # Palabras clave para días (usando hora local)
    day_mappings = {
        'mañana': now_local + timedelta(days=1),
        'hoy': now_local,
        'ahora': now_local,
        'pasado mañana': now_local + timedelta(days=2),
        'lunes': get_next_weekday(0, now_local),
        'martes': get_next_weekday(1, now_local),
        'miércoles': get_next_weekday(2, now_local),
        'miercoles': get_next_weekday(2, now_local),
        'jueves': get_next_weekday(3, now_local),
        'viernes': get_next_weekday(4, now_local),
        'sábado': get_next_weekday(5, now_local),
        'sabado': get_next_weekday(5, now_local),
        'domingo': get_next_weekday(6, now_local),
    }
    
    # Buscar día
    target_date = now_local
    day_found = False
    for day_keyword, date_value in day_mappings.items():
        if day_keyword in time_text:
            target_date = date_value
            time_text = time_text.replace(day_keyword, '')
            day_found = True
            logger.info(f"Día detectado: {day_keyword} -> {target_date}")
            break
    
    # Buscar hora
    hour, minute = now_local.hour, now_local.minute
    
    # Si no se encontró día específico y no hay hora, usar 1 hora por defecto
    if not day_found and not any(time_keyword in time_text for time_keyword in ['a las', 'las', 'am', 'pm', 'hrs', 'horas', ':']):
        result_time = now_local + timedelta(hours=1)
        logger.info("Usando hora por defecto (1 hora desde ahora)")
        return make_naive(local_to_utc(result_time))
    
    # Patrones de hora
    time_pattern_1 = r'(\d{1,2}):(\d{2})\s*(am|pm)?'
    time_pattern_2 = r'(\d{1,2})\s*(am|pm)'
    time_pattern_3 = r'(?:a las|las)\s*(\d{1,2})'
    
    matches_1 = re.findall(time_pattern_1, time_text)
    matches_2 = re.findall(time_pattern_2, time_text) 
    matches_3 = re.findall(time_pattern_3, time_text)
    
    time_found = False
    
    if matches_1:
        match = matches_1[0]
        hour_str = match[0]
        minute_str = match[1]
        period = match[2] if len(match) > 2 else ''
        
        hour = int(hour_str)
        minute = int(minute_str) if minute_str else 0
        time_found = True
        
        # Manejar formato 12h
        if period:
            if 'pm' in period and hour < 12:
                hour += 12
            elif 'am' in period and hour == 12:
                hour = 0
        logger.info(f"Hora detectada (formato 1): {hour}:{minute}")
            
    elif matches_2:
        match = matches_2[0]
        hour_str = match[0]
        period = match[1] if len(match) > 1 else ''
        
        hour = int(hour_str)
        minute = 0
        time_found = True
        
        if period:
            if 'pm' in period and hour < 12:
                hour += 12
            elif 'am' in period and hour == 12:
                hour = 0
        logger.info(f"Hora detectada (formato 2): {hour}:00")
            
    elif matches_3:
        hour_str = matches_3[0]
        hour = int(hour_str)
        minute = 0
        time_found = True
        # Asumir PM si es temprano
        if hour < 8:
            hour += 12
        logger.info(f"Hora detectada (formato 3): {hour}:00")
    
    # Asegurar que la hora esté en rango válido
    hour = min(max(hour, 0), 23)
    minute = min(max(minute, 0), 59)
    
    # Crear datetime final en timezone local
    try:
        due_date_local = TIMEZONE.localize(datetime(
            year=target_date.year,
            month=target_date.month, 
            day=target_date.day,
            hour=hour,
            minute=minute
        ))
        
        # Si no se encontró hora específica y es hoy, usar 1 hora por defecto
        if not time_found and target_date.date() == now_local.date():
            due_date_local = now_local + timedelta(hours=1)
            logger.info("Usando hora por defecto (1 hora desde ahora)")
        
        # Si la fecha/hora ya pasó, mover al siguiente día
        if due_date_local <= now_local:
            due_date_local += timedelta(days=1)
            logger.info("Fecha/hora en pasado, moviendo al siguiente día")
            
        # 🆕 CONVERTIR A UTC y hacer naive para la base de datos
        due_date_utc = local_to_utc(due_date_local)
        due_date_naive = make_naive(due_date_utc)
        
        logger.info(f"Tiempo parseado - Local: {due_date_local}, UTC: {due_date_utc}, Naive: {due_date_naive}")
        return due_date_naive
        
    except Exception as e:
        logger.error(f"Error creando datetime: {e}")
        return None

def get_next_weekday(weekday: int, reference_date=None):
    """Obtiene la próxima ocurrencia de un día de la semana"""
    if reference_date is None:
        reference_date = get_local_now()
    
    days_ahead = weekday - reference_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return reference_date + timedelta(days=days_ahead)

@app.post("/reminders")
async def create_reminder(reminder: ReminderCreate):
    """Crea un nuevo recordatorio"""
    try:
        reminder_data = reminder.dict()
        reminder_data["created_at"] = datetime.utcnow()
        reminder_data["status"] = ReminderStatus.PENDING.value
        reminder_data["last_reminded"] = None
        
        result = db.reminders.insert_one(reminder_data)
        
        return {
            "id": str(result.inserted_id),
            "status": "success",
            "message": f"Recordatorio '{reminder.title}' creado exitosamente"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando recordatorio: {str(e)}")

@app.get("/reminders/{user_id}")
async def get_user_reminders(user_id: str, status: str = "pending"):
    """Obtiene recordatorios del usuario"""
    try:
        query = {"user_id": user_id}
        if status != "all":
            query["status"] = status
        
        reminders = list(db.reminders.find(query).sort("due_date", 1))
        
        for reminder in reminders:
            reminder["_id"] = str(reminder["_id"])
            # Convertir fechas a strings
            date_fields = ["due_date", "created_at", "completed_at", "updated_at", "last_reminded"]
            for field in date_fields:
                if field in reminder and reminder[field]:
                    reminder[field] = reminder[field].isoformat()
        
        return {
            "reminders": reminders,
            "count": len(reminders),
            "status": status
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo recordatorios: {str(e)}")

@app.put("/reminders/{reminder_id}")
async def update_reminder_status(reminder_id: str, status: ReminderStatus):
    """Actualiza el estado de un recordatorio"""
    try:
        result = db.reminders.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": {"status": status.value, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Recordatorio no encontrado")
        
        return {"status": "success", "message": f"Recordatorio actualizado a {status}"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando recordatorio: {str(e)}")

async def check_pending_reminders():
    """Verifica recordatorios pendientes y envía notificaciones"""
    try:
        now_utc = get_utc_now()
        now_utc_naive = make_naive(now_utc)
        
        logger.info(f"🔍 Verificando recordatorios - UTC: {now_utc}")
        
        # 🆕 Buscar recordatorios que vencen en los próximos 5 minutos (más específico)
        time_threshold = now_utc_naive + timedelta(minutes=5)
        
        pending_reminders = db.reminders.find({
            "status": ReminderStatus.PENDING.value,
            "due_date": {
                "$lte": time_threshold, 
                "$gt": now_utc_naive
            },
            "$or": [
                {"last_reminded": None},
                {"last_reminded": {"$exists": False}}
            ]
        })
        
        notified_count = 0
        for reminder in pending_reminders:
            due_date_naive = reminder.get("due_date")
            title = reminder.get("title", "Recordatorio")
            description = reminder.get("description", "")
            
            if due_date_naive:
                # Convertir a UTC aware para cálculos
                due_date_utc = due_date_naive.replace(tzinfo=timezone.utc)
                
                time_until = due_date_utc - now_utc
                minutes_until = int(time_until.total_seconds() / 60)
                
                # 🆕 NOTIFICAR SOLO SI ESTÁ ENTRE 1-2 MINUTOS (más preciso)
                if 1 <= minutes_until <= 2:
                    # Convertir a hora local para el mensaje
                    due_date_local = utc_to_local(due_date_utc)
                    
                    message = f"🔔 <b>RECORDATORIO PRÓXIMO</b>\n\n"
                    message += f"<b>{title}</b>\n"
                    if description:
                        message += f"📝 {description}\n"
                    message += f"\n⏰ <b>Hora:</b> {due_date_local.strftime('%d/%m/%Y a las %H:%M')}\n"
                    message += f"⏳ <i>Faltan {minutes_until} minutos</i>"
                    
                    logger.info(f"📤 Enviando notificación para: {title} (en {minutes_until} minutos)")
                    
                    # Enviar notificación
                    success = await send_telegram_message(message)
                    
                    if success:
                        # Marcar como notificado
                        db.reminders.update_one(
                            {"_id": reminder["_id"]},
                            {"$set": {"last_reminded": datetime.utcnow()}}
                        )
                        notified_count += 1
                        logger.info(f"✅ Notificación enviada: {title}")
        
        if notified_count > 0:
            logger.info(f"📨 Se enviaron {notified_count} notificaciones")
        
    except Exception as e:
        logger.error(f"❌ Error verificando recordatorios: {e}")

async def check_immediate_reminders():
    """Verifica recordatorios que están justo por vencer (0-1 minuto) y los COMPLETA"""
    try:
        now_utc = get_utc_now()
        now_utc_naive = make_naive(now_utc)
        
        # Buscar recordatorios que vencen en los próximos 0-1 minutos
        time_threshold = now_utc_naive + timedelta(minutes=1)
        
        immediate_reminders = db.reminders.find({
            "status": ReminderStatus.PENDING.value,
            "due_date": {
                "$lte": time_threshold, 
                "$gt": now_utc_naive
            },
            "immediate_notified": {"$ne": True}  # Solo los que no han sido notificados inmediatamente
        })
        
        completed_count = 0
        for reminder in immediate_reminders:
            due_date_naive = reminder.get("due_date")
            title = reminder.get("title", "Recordatorio")
            description = reminder.get("description", "")
            
            if due_date_naive:
                due_date_utc = due_date_naive.replace(tzinfo=timezone.utc)
                due_date_local = utc_to_local(due_date_utc)
                
                time_until = due_date_utc - now_utc
                seconds_until = int(time_until.total_seconds())
                
                # Notificar si está por vencer (0-60 segundos)
                if 0 <= seconds_until <= 60:
                    message = f"⏰ <b>RECORDATORIO INMEDIATO</b>\n\n"
                    message += f"<b>{title}</b>\n"
                    if description:
                        message += f"📝 {description}\n"
                    message += f"\n🕐 <b>Es ahora:</b> {due_date_local.strftime('%d/%m/%Y a las %H:%M')}"
                    message += f"\n\n✅ <i>Este recordatorio se ha completado automáticamente</i>"
                    
                    logger.info(f"🚨 Enviando notificación INMEDIATA y COMPLETANDO: {title}")
                    
                    success = await send_telegram_message(message)
                    
                    if success:
                        # 🆕 MARCAR COMO COMPLETADO INMEDIATAMENTE
                        db.reminders.update_one(
                            {"_id": reminder["_id"]},
                            {"$set": {
                                "status": ReminderStatus.COMPLETED.value,  # 🆕 COMPLETADO
                                "completed_at": datetime.utcnow(),         # 🆕 Fecha de completado
                                "immediate_notified": True,
                                "last_reminded": datetime.utcnow(),
                                "updated_at": datetime.utcnow()
                            }}
                        )
                        completed_count += 1
                        logger.info(f"✅ Notificación enviada y recordatorio COMPLETADO: {title}")
                    else:
                        logger.error(f"❌ Error enviando notificación, no se completó: {title}")
        
        if completed_count > 0:
            logger.info(f"📝 Se completaron {completed_count} recordatorios")
            
    except Exception as e:
        logger.error(f"❌ Error en check_immediate_reminders: {e}")

@app.post("/send-notification")
async def send_notification(message: str, reminder_id: Optional[str] = None):
    """Envía una notificación inmediata por Telegram"""
    try:
        success = await send_telegram_message(message)
        
        if success and reminder_id:
            # Marcar recordatorio como notificado
            db.reminders.update_one(
                {"_id": ObjectId(reminder_id)},
                {"$set": {"last_reminded": datetime.utcnow()}}
            )
        
        return {"status": "success" if success else "error"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error enviando notificación: {str(e)}")

async def background_reminder_checker():
    """Tarea en segundo plano para verificar recordatorios cada 30 segundos"""
    while True:
        try:
            await check_pending_reminders()     # Avisos 1-2 minutos antes
            await check_immediate_reminders()   # 🆕 Notificación FINAL + COMPLETAR
            await check_overdue_reminders()      # Recordatorios que se pasaron sin notificar
            # 🚫 Ya no llamamos a complete_expired_reminders()
            await asyncio.sleep(30)  # Verificar cada 30 segundos
        except Exception as e:
            logger.error(f"Error en background_reminder_checker: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    try:
        # Crear índices para mejor performance
        db.interactions.create_index([("user_id", 1), ("timestamp", -1)])
        db.interactions.create_index([("intent", 1)])
        db.reminders.create_index([("user_id", 1), ("due_date", 1)])
        db.reminders.create_index([("status", 1), ("due_date", 1)])
        
        # 🆕 INICIAR VERIFICADOR DE RECORDATORIOS EN SEGUNDO PLANO
        asyncio.create_task(background_reminder_checker())
        logger.info("✅ Aplicación iniciada - Verificador de recordatorios activado")
        
    except Exception as e:
        logger.error(f"Error en startup: {e}")

@app.get("/test-telegram-manual")
async def test_telegram_manual():
    """Endpoint para probar Telegram manualmente"""
    test_message = "🔔 <b>PRUEBA MANUAL</b>\n\n¡Esta es una prueba manual de Telegram! 🚀"
    
    print("🧪 Iniciando prueba manual de Telegram...")
    success = await send_telegram_message(test_message)
    
    return {
        "success": success,
        "message": "Prueba completada - revisa la terminal y Telegram"
    }

async def check_overdue_reminders():
    """Verifica recordatorios que ya vencieron pero están pendientes"""
    try:
        now = datetime.utcnow()
        
        overdue_reminders = db.reminders.find({
            "status": ReminderStatus.PENDING.value,
            "due_date": {"$lte": now},  # 🆕 Ya vencieron
            "last_reminded": None  # Y no han sido notificados
        })
        
        for reminder in overdue_reminders:
            title = reminder.get("title", "Recordatorio")
            description = reminder.get("description", "")
            
            message = f"🔔 <b>RECORDATORIO VENCIDO</b>\n\n"
            message += f"<b>{title}</b>\n"
            if description:
                message += f"{description}\n"
            message += f"\n⏰ <i>¡Este recordatorio ya venció!</i>"
            
            success = await send_telegram_message(message)
            
            if success:
                db.reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$set": {"last_reminded": now}}
                )
                logger.info(f"Notificación de vencimiento enviada: {title}")
        
    except Exception as e:
        logger.error(f"Error verificando recordatorios vencidos: {e}")

@app.post("/test-reminder-2min")
async def test_reminder_2min():
    """Crea un recordatorio de prueba para 2 minutos en el futuro"""
    try:
        due_date = datetime.utcnow() + timedelta(minutes=2)
        
        reminder_data = {
            "user_id": "test_user",
            "title": "PRUEBA - Recordatorio en 2 minutos",
            "description": "Este es un recordatorio de prueba programado para 2 minutos en el futuro",
            "due_date": due_date,
            "priority": ReminderPriority.MEDIUM.value,
            "tags": ["prueba"],
            "created_at": datetime.utcnow(),
            "status": ReminderStatus.PENDING.value,
            "last_reminded": None
        }
        
        result = db.reminders.insert_one(reminder_data)
        
        return {
            "success": True,
            "reminder_id": str(result.inserted_id),
            "due_date": due_date.isoformat(),
            "message": f"Recordatorio de prueba creado para {due_date}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando recordatorio de prueba: {str(e)}")

@app.get("/time-info")
async def time_info():
    """Muestra información de timezone"""
    now_utc = get_utc_now()
    now_local = get_local_now()
    
    return {
        "timezone": "America/Caracas (UTC-4)",
        "hora_utc_actual": now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
        "hora_local_actual": now_local.strftime('%Y-%m-%d %H:%M:%S'),
        "diferencia_horas": "UTC-4"
    }

@app.get("/test-timezone")
async def test_timezone():
    """Prueba la configuración de timezone"""
    now_local = get_local_now()
    now_utc = get_utc_now()
    test_time = parse_natural_time("en 5 minutos")
    
    return {
        "timezone": "America/Caracas",
        "hora_local": now_local.strftime('%Y-%m-%d %H:%M:%S %Z'),
        "hora_utc": now_utc.strftime('%Y-%m-%d %H:%M:%S %Z'),
        "test_5_minutos": test_time.strftime('%Y-%m-%d %H:%M:%S') if test_time else None,
        "diferencia": f"UTC-4"
    }

@app.get("/reminders-debug/{user_id}")
async def debug_reminders_status(user_id: str):
    """Endpoint de debug para ver todos los estados de recordatorios"""
    try:
        # Contar por estado
        pending_count = db.reminders.count_documents({
            "user_id": user_id, 
            "status": ReminderStatus.PENDING.value
        })
        
        completed_count = db.reminders.count_documents({
            "user_id": user_id, 
            "status": ReminderStatus.COMPLETED.value
        })
        
        # Obtener algunos ejemplos de cada estado
        pending_examples = list(db.reminders.find({
            "user_id": user_id,
            "status": ReminderStatus.PENDING.value
        }).limit(3))
        
        completed_examples = list(db.reminders.find({
            "user_id": user_id, 
            "status": ReminderStatus.COMPLETED.value
        }).limit(3))
        
        # Formatear para respuesta
        def format_reminder(reminder):
            return {
                "id": str(reminder["_id"]),
                "title": reminder.get("title"),
                "status": reminder.get("status"),
                "due_date": reminder.get("due_date").isoformat() if reminder.get("due_date") else None,
                "completed_at": reminder.get("completed_at").isoformat() if reminder.get("completed_at") else None
            }
        
        return {
            "counts": {
                "pending": pending_count,
                "completed": completed_count,
                "total": pending_count + completed_count
            },
            "pending_examples": [format_reminder(r) for r in pending_examples],
            "completed_examples": [format_reminder(r) for r in completed_examples]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en debug: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)