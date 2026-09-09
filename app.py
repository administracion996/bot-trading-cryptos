import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Bot Trading IA", page_icon="🤖", layout="wide")

st.title("🤖 Panel de Control - Bot de Trading con IA")
st.markdown("---")

# Métricas principales (Se actualizarán dinámicamente)
col1, col2, col3 = st.columns(3)
col1.metric("Capital Simulado Total", "1.000,00 €", "+0.00%")
col2.metric("Efectivo Libre", "1.000,00 €")
col3.metric("Posiciones Abiertas", "0")

st.markdown("---")

# Visualización de mercado ajustada
st.subheader("📊 Monitoreo del Mercado en Tiempo Real")
ticker = st.selectbox("Selecciona un activo para analizar:", ["BTC-USD", "ETH-USD", "NVDA", "AAPL", "MSFT"])

# Carga de datos
df = yf.Ticker(ticker).history(period="1d", interval="15m")

if not df.empty:
    # Ajuste para no empezar el eje Y en cero y ver las fluctuaciones reales
    precio_min = df['Close'].min() * 0.998
    precio_max = df['Close'].max() * 1.002
    
    st.line_chart(df['Close'], y_label="Precio ($)")

st.markdown("---")

st.subheader("📜 Registro de Operaciones")
st.info("Esperando sincronización de cartera desde Google Colab...")
