import streamlit as st
import pandas as pd
import yfinance as yf

# Configuración de la página
st.set_page_config(page_title="Bot Trading IA", page_icon="🤖", layout="wide")

st.title("🤖 Panel de Control - Bot de Trading con IA")
st.markdown("---")

# Métricas principales
col1, col2, col3 = st.columns(3)
col1.metric("Capital Simulado Total", "1.000,00 €", "+0.00%")
col2.metric("Efectivo Libre", "1.000,00 €")
col3.metric("Posiciones Abiertas", "0")

st.markdown("---")

# Visualización de mercado
st.subheader("📊 Monitoreo del Mercado en Tiempo Real")
ticker_seleccionado = st.selectbox("Selecciona un activo para analizar:", ["BTC-USD", "ETH-USD", "NVDA", "AAPL", "MSFT"])

data = yf.Ticker(ticker_seleccionado).history(period="1d", interval="15m")
if not data.empty:
    st.line_chart(data['Close'])

st.markdown("---")

# Historial simulado
st.subheader("📜 Registro de Operaciones")
st.info("El bot está recopilando datos en Google Colab. Pronto conectaremos este panel para actualizar automáticamente las decisiones de la IA.")
