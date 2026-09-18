import streamlit as st
import json
import pandas as pd
from datetime import datetime
import requests

# ==========================================
# 0. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Centro de Control - Bots", page_icon="🛡️", layout="wide")

st.title("🛡️ Centro de Control - Trading Bots")

# ==========================================
# 1. FUNCIÓN DE CONEXIÓN (MÉTODO RAW SIN DEPENDENCIAS EXTRA)
# ==========================================
@st.cache_data(ttl=60)  # Actualiza los datos como máximo cada 60 segundos
def cargar_datos(file_name):
    # Asumimos que la rama principal se llama 'main'. Si es 'master', cambia 'main' por 'master' en la URL.
    url = f"https://raw.githubusercontent.com/administracion996/bot-trading-dashboard/main/{file_name}"
    
    headers = {}
    # Si el repo es privado, usará el token de los Secrets de Streamlit
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"token {st.secrets['GITHUB_TOKEN']}"
        
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Error {response.status_code}: No se pudo acceder a {file_name}."}
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 2. INTERFAZ Y PESTAÑAS
# ==========================================
tab1, tab2 = st.tabs(["🎯 Bot 1: Francotirador", "⚡ Bot 2: Cazador Memecoins"])

# ------------------------------------------
# PESTAÑA 1: FRANCOTIRADOR
# ------------------------------------------
with tab1:
    datos_sniper = cargar_datos("cartera.json")
    
    if "error" in datos_sniper:
        st.warning(f"Esperando datos del Francotirador o error de conexión: {datos_sniper['error']}")
    else:
        efectivo = datos_sniper.get("efectivo_disponible", 0.0)
        posiciones = datos_sniper.get("posiciones", {})
        historial = datos_sniper.get("historial", [])
        
        capital_invertido = sum(p.get("coste_total", 0.0) for p in posiciones.values())
        capital_total = efectivo + capital_invertido
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital Total", f"{capital_total:.2f} €")
        col2.metric("Liquidez Disponible", f"{efectivo:.2f} €")
        col3.metric("Capital Invertido", f"{capital_invertido:.2f} €")
        col4.metric("Posiciones Abiertas", len(posiciones))
        
        st.markdown("---")
        
        st.subheader("📌 Posiciones Activas")
        if posiciones:
            df_pos = pd.DataFrame.from_dict(posiciones, orient="index")
            df_pos = df_pos.rename(columns={
                "unidades": "Unidades", 
                "precio_compra": "Precio Compra (€)", 
                "coste_total": "Inversión (€)", 
                "fecha_entrada": "Fecha de Entrada"
            })
            st.dataframe(df_pos, use_container_width=True)
        else:
            st.info("Sin posiciones abiertas en este momento.")

        st.subheader("📜 Historial de Operaciones")
        if historial:
            df_hist = pd.DataFrame(historial)
            st.dataframe(df_hist.sort_values(by="fecha_salida", ascending=False), use_container_width=True)
        else:
            st.info("No hay operaciones cerradas todavía.")

# ------------------------------------------
# PESTAÑA 2: CAZADOR DE MOMENTUM
# ------------------------------------------
with tab2:
    datos_cazador = cargar_datos("cartera_cazador.json")
    
    if "error" in datos_cazador:
        st.warning(f"Esperando datos del Cazador o error de conexión: {datos_cazador['error']}")
    else:
        efectivo_c = datos_cazador.get("efectivo_disponible", 0.0)
        posiciones_c = datos_cazador.get("posiciones", {})
        historial_c = datos_cazador.get("historial", [])
        vault = datos_cazador.get("vault_reservado", 0.0)
        meta_dia = datos_cazador.get("meta_eur_dia", 0.0)
        barrido = datos_cazador.get("barrido_realizado", False)
        
        capital_invertido_c = sum(p.get("coste_total", 0.0) for p in posiciones_c.values())
        capital_trabajo_c = efectivo_c + capital_invertido_c
        
        # Calcular PnL Cerrado del día de hoy
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        pnl_hoy_cerrado = sum(h.get("beneficio_neto", 0.0) for h in historial_c if h.get("fecha_salida", "").startswith(hoy_str))
        
        st.subheader("📊 Estado Global de la Cuenta")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital de Trabajo", f"{capital_trabajo_c:.2f} €")
        col2.metric("Liquidez Disponible", f"{efectivo_c:.2f} €")
        col3.metric("🏦 The Vault (Reserva)", f"{vault:.2f} €")
        col4.metric("Posiciones Abiertas", len(posiciones_c))
        
        st.markdown("---")
        st.subheader("🏦 Progreso Diario & The Vault")
        vc1, vc2, vc3 = st.columns(3)
        vc1.metric("Meta del Día (5%)", f"{meta_dia:.2f} €")
        vc2.metric("Beneficio Cerrado Hoy", f"{pnl_hoy_cerrado:+.2f} €")
        
        if barrido:
            vc3.success("✅ Barrido completado hoy. ¡Beneficios asegurados en The Vault!")
        else:
            restante = max(0.0, meta_dia - pnl_hoy_cerrado)
            vc3.info(f"Faltan {restante:.2f} € cerrados para activar el barrido.")
            
        st.markdown("---")
        
        st.subheader("📌 Posiciones Activas")
        if posiciones_c:
            df_pos_c = pd.DataFrame.from_dict(posiciones_c, orient="index")
            df_pos_c = df_pos_c.rename(columns={
                "unidades": "Unidades", 
                "precio_compra": "Precio Compra (€)", 
                "coste_total": "Inversión (€)", 
                "max_precio_alcanzado": "Máx Alcanzado (€)",
                "confianza_gemini": "IA Score",
                "fecha_entrada": "Fecha Entrada"
            })
            st.dataframe(df_pos_c, use_container_width=True)
        else:
            st.info("Sin posiciones abiertas en este momento.")

        st.subheader("📜 Historial de Caza")
        if historial_c:
            df_hist_c = pd.DataFrame(historial_c)
            columnas_orden = ["fecha_salida", "ticker", "motivo_salida", "monto_invertido", "beneficio_neto", "pnl_pct", "precio_entrada", "precio_salida"]
            columnas_mostrar = [c for c in columnas_orden if c in df_hist_c.columns]
            df_hist_c = df_hist_c[columnas_mostrar].sort_values(by="fecha_salida", ascending=False)
            st.dataframe(df_hist_c, use_container_width=True)
        else:
            st.info("No hay presas cazadas todavía.")

# Botón de refresco manual
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()
