import json
import os
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Bot Trading IA", page_icon="🤖", layout="wide")

st.title("🤖 Panel de Control - Bot de Trading con IA")
st.markdown("---")

# Cargar el estado real enviado desde Google Colab
if os.path.exists("cartera.json"):
    with open("cartera.json", "r") as f:
        cartera = json.load(f)
else:
    cartera = {
        "efectivo_disponible": 1000.0,
        "total_cartera": 1000.0,
        "posiciones_abiertas": {},
        "historial_operaciones": []
    }

# Métricas conectadas a los datos de Colab
col1, col2, col3 = st.columns(3)
col1.metric("Capital Simulado Total", f"{cartera.get('total_cartera', 1000.0):,.2f} €")
col2.metric("Efectivo Libre", f"{cartera.get('efectivo_disponible', 1000.0):,.2f} €")
col3.metric("Posiciones Abiertas", str(len(cartera.get('posiciones_abiertas', {}))))

st.markdown("---")

# Visualización del gráfico
st.subheader("📊 Monitoreo del Mercado en Tiempo Real")
ticker = st.selectbox("Selecciona un activo para analizar:", ["BTC-USD", "ETH-USD", "NVDA", "AAPL", "MSFT"])

data = yf.Ticker(ticker).history(period="1d", interval="15m")
if not data.empty:
    st.line_chart(data['Close'])

st.markdown("---")

# Historial de decisiones enviado por la IA
st.subheader("📜 Registro de Operaciones del Bot")
historial = cartera.get("historial_operaciones", [])
if historial:
    for op in reversed(historial):
        st.write(f"• {op}")
else:
    st.info("Sin operaciones registradas todavía.")
