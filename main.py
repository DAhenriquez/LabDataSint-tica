import asyncio  
import csv      
import os       
import random   
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import numpy as np 
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Inicializa la Api
app = FastAPI(title="Lab Data sintética")


# ----------------------------
# Constantes definidas en el problema


VENTANA_PH_HORAS = 72       # Guardar datos de PH de las últimas 72 hora
VENTANA_HUMEDAD_HORAS = 24  # Guardar datos de humedad de las últimas 24 horas
VENTANA_TEMPERATURA_HORAS = 24 # Guardar datos de temperatura de las últimas 24 horas

#Frecuencia con la que se generan nuevos datos (en segundos)
PERIODO_PH_S = 6 * 60 * 60          
PERIODO_HUMEDAD_S = 2 * 60 * 60     
PERIODO_TEMPERATURA_S = 5           

# Estas listas guardarán los datos mientras la api esté en ejecucion
historial_ph: List[Dict] = []
historial_humedad: List[Dict] = []
historial_temperatura: List[Dict] = []

# Evitan que dos procesos intenten modificar la misma lista de historial al mismo tiempo.
lock_ph = asyncio.Lock()
lock_humedad = asyncio.Lock()
lock_temperatura = asyncio.Lock()

#Configuración para guardar en archivos CSV 
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PH_CSV = os.path.join(DATA_DIR, "ph.csv")
HUM_CSV = os.path.join(DATA_DIR, "humedad.csv")
TEMP_CSV = os.path.join(DATA_DIR, "temperatura.csv")


#----------------------------------
# funciones auxiliares
def ts(dt: datetime) -> str:
    """Convierte un objeto datetime a un string en formato ISO 8601."""
    return dt.replace(microsecond=0).isoformat()

def parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Convierte un string de fecha/hora a un objeto datetime."""
    if not value: return None
    try: return datetime.fromisoformat(value)
    except ValueError:
        try: return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError: return None

def recortar_por_ventana_tiempo(data: List[Dict], ventana_horas: int, key: str = "hora"):
    """Elimina datos antiguos de una lista para que no crezca indefinidamente."""
    if not data: return
    limite = datetime.now() - timedelta(hours=ventana_horas)
    while data and datetime.fromisoformat(data[0][key]) < limite:
        data.pop(0)

def append_csv(path: str, row: Dict, header: List[str]):
    """Añade una nueva fila de datos a un archivo CSV."""
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if write_header: writer.writeheader()
        writer.writerow(row)

def guardar_historial_completo_csv(path: str, historial: List[Dict], header: List[str]):
    """Escribe una lista completa de datos a un CSV (usado para el guardado inicial)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(historial)
    print(f"INFO: Historial inicial guardado en {os.path.basename(path)}")



# Estas funciones generan datos parecidos a los de la realidad con numpy y funciones trigonométricas

def simular_ph(t: datetime) -> float:
    """Simula una lectura de pH con una oscilación suave."""
    hora = t.hour + t.minute / 60.0
    oscilacion = 0.8 * np.sin(hora * 0.2) + 0.5 * np.cos(hora * 0.3)
    ruido = random.uniform(-0.3, 0.3)
    ph = 6.5 + oscilacion + ruido
    return round(max(5.5, min(7.5, ph)), 2)

def simular_humedad(t: datetime) -> float:
    """Simula la humedad con un ciclo diario (más alta de noche)."""
    hora = t.hour + t.minute / 60.0
    ciclo = 15 * np.sin((hora - 10) * (2 * np.pi / 24))
    ruido = random.uniform(-4, 8)
    humedad = 75 + ciclo + ruido
    return round(max(60, min(90, humedad)), 2)

def simular_temperatura(t: datetime) -> float:
    """Simula la temperatura con un ciclo diario (más alta por la tarde)."""
    hora = t.hour + t.minute / 60.0
    ciclo = 7.5 * np.sin((hora - 6) * (2 * np.pi / 24))
    base = 22.5 + ciclo
    ruido = random.uniform(-2, 2)
    temp = base + ruido
    return round(max(15, min(30, temp)), 2)



def backfill():
#Precarga las listas de historial con datos simulados del pasado
#Esto asegura que cuando la API arranque, ya tenga datos para mostrar y puedan graficarse
#También guarda este historial inicial en los archivos CSV
    
    print("INFO: Iniciando backfill de datos históricos...")
    now = datetime.now().replace(second=0, microsecond=0)
    
    # Genera datos iniciales para pH, humedad y temperatura y los guarda.
    base_ph = now - timedelta(hours=VENTANA_PH_HORAS)
    for i in range(int(VENTANA_PH_HORAS / 6) + 1):
        t = base_ph + timedelta(hours=6 * i)
        historial_ph.append({"hora": ts(t), "ph": simular_ph(t)})
    guardar_historial_completo_csv(PH_CSV, historial_ph, ["hora", "ph"])

    base_h = now - timedelta(hours=VENTANA_HUMEDAD_HORAS)
    for i in range(int(VENTANA_HUMEDAD_HORAS / 2) + 1):
        t = base_h + timedelta(hours=2 * i)
        historial_humedad.append({"hora": ts(t), "humedad": simular_humedad(t)})
    guardar_historial_completo_csv(HUM_CSV, historial_humedad, ["hora", "humedad"])

    base_t = now - timedelta(hours=VENTANA_TEMPERATURA_HORAS)
    total_seg = VENTANA_TEMPERATURA_HORAS * 3600
    for s in range(0, total_seg + 1, PERIODO_TEMPERATURA_S):
        t = base_t + timedelta(seconds=s)
        historial_temperatura.append({"hora": ts(t), "temperatura": simular_temperatura(t)})
    guardar_historial_completo_csv(TEMP_CSV, historial_temperatura, ["hora", "temperatura"])
    
    print("INFO: Backfill y guardado inicial en CSV completado.")

# Ejecuta la función de backfill una vez, al iniciar la API.
backfill()


# -------------------------------------
# 6. Uso de async
# Estas tareas se ejecutan en segundo plano, generando nuevos datos a intervalos
# regulares sin bloquear el funcionamiento principal de la API

async def tarea_ph():
    """Bucle infinito que genera un nuevo dato de pH cada 6 horas."""
    while True:
        await asyncio.sleep(PERIODO_PH_S)
        dato = {"hora": ts(datetime.now()), "ph": simular_ph(datetime.now())}
        async with lock_ph:
            historial_ph.append(dato)
            recortar_por_ventana_tiempo(historial_ph, VENTANA_PH_HORAS)
        append_csv(PH_CSV, dato, ["hora", "ph"])

async def tarea_humedad():
    """Bucle infinito que genera un nuevo dato de humedad cada 2 horas."""
    while True:
        await asyncio.sleep(PERIODO_HUMEDAD_S)
        dato = {"hora": ts(datetime.now()), "humedad": simular_humedad(datetime.now())}
        async with lock_humedad:
            historial_humedad.append(dato)
            recortar_por_ventana_tiempo(historial_humedad, VENTANA_HUMEDAD_HORAS)
        append_csv(HUM_CSV, dato, ["hora", "humedad"])

async def tarea_temperatura():
    """Bucle infinito que genera un nuevo dato de temperatura cada 5 segundos."""
    while True:
        await asyncio.sleep(PERIODO_TEMPERATURA_S)
        dato = {"hora": ts(datetime.now()), "temperatura": simular_temperatura(datetime.now())}
        async with lock_temperatura:
            historial_temperatura.append(dato)
            recortar_por_ventana_tiempo(historial_temperatura, VENTANA_TEMPERATURA_HORAS)
        append_csv(TEMP_CSV, dato, ["hora", "temperatura"])

# Al arrancar la API, se inician estas tres tareas para que se ejecuten concurrentemente.
@app.on_event("startup")
async def on_startup():
    asyncio.create_task(tarea_ph())
    asyncio.create_task(tarea_humedad())
    asyncio.create_task(tarea_temperatura())


# --------------------------------------------
# 7. Endpoints
# Estas son las URLs que el dashboard puede consultar.

@app.get("/temperatura")
async def get_temperatura():
    """Devuelve la última lectura de temperatura y las últimas 10 mediciones."""
    async with lock_temperatura:
        # Devuelve una copia para evitar problemas de concurrencia.
        data = historial_temperatura[:] 
    ultima = data[-1] if data else None
    ultimas_10 = data[-10:]
    return {"ultima": ultima, "historial": ultimas_10}

@app.get("/humedad")
async def get_humedad():
    """Devuelve la última lectura de humedad y su historial completo de 24h."""
    async with lock_humedad:
        data = historial_humedad[:]
    ultima = data[-1] if data else None
    return {"ultima": ultima, "historial": data}

@app.get("/ph")
async def get_ph():
    """Devuelve el historial completo de pH (últimas 72 horas)."""
    async with lock_ph:
        data = historial_ph[:]
    return {"historial": data}


# -----------------------------------------------------
# Exportar como CSV

@app.get("/export/csv/{sensor}")
async def export_csv(sensor: str):
    """Permite descargar el historial completo de un sensor como un archivo CSV."""
    sensor = sensor.lower()
    path_map = {"ph": PH_CSV, "humedad": HUM_CSV, "temperatura": TEMP_CSV}
    path = path_map.get(sensor)
    if not path:
        return JSONResponse({"error": "sensor no reconocido"}, status_code=400)
