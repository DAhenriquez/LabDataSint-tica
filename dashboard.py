import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# URL de la API
BASE_URL = "http://127.0.0.1:8000"

# Se config. la metadata
# layout="wide" hace que el contenido ocupe todo el ancho de la pantalla
st.set_page_config(
    page_title="Dashboard de Sensores IoT",
    layout="wide"
)

# --------------------------------------
# título del streamlit
st.title("Dashboard de Sensores IoT en Tiempo Real")
st.text("Por: Diego Henríquez y Carlos Márquez")

# Inicializamos las variables en el estado
if 'last_ph_update' not in st.session_state:
    st.session_state.last_ph_update = datetime.min # Una fecha muy antigua para forzar la primera actualización.
    st.session_state.ph_data = None # Aquí guardaremos los datos de pH

if 'last_hum_update' not in st.session_state:
    st.session_state.last_hum_update = datetime.min # Lo mismo para la humedad
    st.session_state.hum_data = None # Aquí guardaremos los datos de humedad

# Creamos contenedores vacíos
# el contenido de estos contenedores para dar la sensación de actualización en tiempo real
temp_placeholder = st.empty()
hum_placeholder = st.empty()
ph_placeholder = st.empty()


# --------------------------
# Este bucle infinito del dashboard, se ejecuta, duerme 5 segundos, y se repite
while True:
    try:
        now = datetime.now()

        # Para el pH, solo hacemos una petición a la api si han pasado 6 horas
        if (now - st.session_state.last_ph_update) > timedelta(hours=6):
            print("INFO: Actualizando datos de pH desde la API...")
            st.session_state.ph_data = requests.get(f"{BASE_URL}/ph").json()
            st.session_state.last_ph_update = now # Guardamos la hora 

        # Para la humedad, dsp de 2 horas
        if (now - st.session_state.last_hum_update) > timedelta(hours=2):
            print("INFO: Actualizando datos de humedad desde la API...")
            st.session_state.hum_data = requests.get(f"{BASE_URL}/humedad").json()
            st.session_state.last_hum_update = now

        # La temperatura se pide en cada ciclo del bucle 
        data_temp = requests.get(f"{BASE_URL}/temperatura").json()

# -------------------------------------------------------------------------
        #Interfaz

        # temperatura contenedor
        with temp_placeholder.container():
            st.subheader("Temperatura")
            if data_temp.get("historial"):
                # Convertimos la lista de datos JSON en un DataFrame de Pandas
                df_temp = pd.DataFrame(data_temp["historial"])
                st.write("Última lectura:", data_temp["ultima"])
                # Dibujamos un gráfico de líneas
                st.line_chart(df_temp.set_index("hora")["temperatura"])
            else:
                st.warning("Esperando datos de temperatura...")

        # Contenedor Humedad
        with hum_placeholder.container():
            st.subheader(f"Humedad (actualizado a las {st.session_state.last_hum_update.strftime('%H:%M:%S')})")
            # Usamos los datos del historial
            if st.session_state.hum_data and st.session_state.hum_data.get("historial"):
                df_hum = pd.DataFrame(st.session_state.hum_data["historial"])
                st.write("Última lectura:", st.session_state.hum_data["ultima"])
                st.line_chart(df_hum.set_index("hora")["humedad"])
            else:
                st.warning("Esperando datos de humedad...")

        # Contenedor PH
        with ph_placeholder.container():
            st.subheader(f"pH (actualizado a las {st.session_state.last_ph_update.strftime('%H:%M:%S')})")
            if st.session_state.ph_data and st.session_state.ph_data.get("historial"):
                df_ph = pd.DataFrame(st.session_state.ph_data["historial"])
                st.line_chart(df_ph.set_index("hora")["ph"])
            else:
                st.warning("Esperando datos de pH...")
        
        # Pausamos la ejecución por 5 segundos (hasta la sgte ejecucion)
        time.sleep(5)

    # excepciones: si la API no está disponible por ej
    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con la API: {e}. Reintentando en 10 segundos.")
        time.sleep(10)
    # Captura de cualquier otro error inesperado
    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
        time.sleep(10)