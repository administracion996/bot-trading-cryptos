import json
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Configuración de la página en modo ancho
st.set_page_config(
    page_title="Bot de Trading - Dashboard", page_icon="📈", layout="wide"
)

# Conexión con GitHub
REPO = "administracion996/bot-trading-dashboard"
FILE_PATH = "cartera.json"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"

# Lista de activos rastreados
universo_mercado = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "ADA-USD",
    "AVAX-USD",
    "DOT-USD",
    "NEAR-USD",
    "ATOM-USD",
    "XRP-USD",
    "LTC-USD",
    "BCH-USD",
    "LINK-USD",
    "DOGE-USD",
    "SHIB-USD",
]


@st.cache_data(ttl=30)
def cargar_cartera_github():
    try:
        res = requests.get(RAW_URL)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
    return None


@st.cache_data(ttl=300)
def obtener_historial_comparativo():
    df_precios = pd.DataFrame()
    for ticker in universo_mercado:
        try:
            historia = yf.Ticker(ticker).history(period="2d", interval="15m")[
                "Close"
            ]
            if len(historia) > 0:
                # Normalización a variación porcentual desde el inicio del período
                df_precios[ticker] = (
                    (historia - historia.iloc[0]) / historia.iloc[0]
                ) * 100
        except Exception:
            pass
    return df_precios


# Encabezado principal
st.title("📈 Panel de Control - Bot de Trading Algorítmico")

cartera = cargar_cartera_github()

if cartera:
    # 1. Métricas clave de rendimiento
    col1, col2, col3 = st.columns(3)
    valor_total = cartera.get("total_cartera", 1000.0)
    efectivo = cartera.get("efectivo_disponible", 0.0)
    num_posiciones = len(cartera.get("posiciones_abiertas", {}))

    col1.metric("Capital Total", f"{valor_total:.2f} €")
    col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
    col3.metric("Posiciones Activas", f"{num_posiciones} / 14")

    st.markdown("---")

    # 2. Gráfico único comparativo de las 14 criptomonedas
    st.subheader("📊 Rendimiento Comparativo del Mercado (%)")
    df_comparativo = obtener_historial_comparativo()

    if not df_comparativo.empty:
        st.line_chart(df_comparativo)
    else:
        st.info("Cargando métricas de mercado desde Yahoo Finance...")

    st.markdown("---")

    # 3. Desglose de Posiciones Abiertas e Historial
    col_pos, col_hist = st.columns(2)

    with col_pos:
        st.subheader("💼 Posiciones Abiertas")
        posiciones = cartera.get("posiciones_abiertas", {})
        if posiciones:
            tabla_pos = []
            for ticker, info in posiciones.items():
                tabla_pos.append(
                    {
                        "Activo": ticker,
                        "Cantidad": info.get("cantidad", 0),
                        "Precio Entrada (€)": info.get("precio_entrada", 0),
                    }
                )
            st.dataframe(pd.DataFrame(tabla_pos), use_container_width=True)
        else:
            st.info("No hay posiciones abiertas en este momento.")

    with col_hist:
        st.subheader("📜 Historial de Operaciones")
        historial = cartera.get("historial_operaciones", [])
        if historial:
            for operacion in reversed(historial):
                st.write(operacion)
        else:
            st.info("Sin registros de operaciones recientes.")

else:
    st.warning("Sincronizando con GitHub... Por favor, recarga en unos segundos.")
