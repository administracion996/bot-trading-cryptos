import base64
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Crypto Scalper Dashboard", page_icon="🤖", layout="wide")

REPO = "administracion996/bot-trading-dashboard"
FILE_PATH = "cartera.json"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

UNIVERSO_MERCADO = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
    "DOT-USD", "NEAR-USD", "ATOM-USD", "MATIC-USD", "LTC-USD", "BCH-USD", "ETC-USD",
    "LINK-USD", "AAVE-USD", "INJ-USD", "FET-USD", "ALGO-USD", "XLM-USD", "TRX-USD",
    "DOGE-USD", "SHIB-USD", "BONK-USD", "FLOKI-USD", "FIL-USD", "ICP-USD"
]

@st.cache_data(ttl=10)
def cargar_cartera():
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content_b64 = res.json()["content"]
            return json.loads(base64.b64decode(content_b64).decode("utf-8"))
    except Exception:
        pass
    return None

cartera = cargar_cartera()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
    efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
    total = round(float(cartera.get("total_cartera", 0.0)), 2)
    posiciones = cartera.get("posiciones_abiertas", {})
    historial = cartera.get("historial_operaciones", [])

    # 1. MÉTRICAS
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cartera Total", f"{total:.2f} €")
    col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
    col3.metric("Posiciones Abiertas", len(posiciones))
    col4.metric("Operaciones Registradas", len(historial))

    st.divider()

    # 2. GRÁFICA DE BARRAS DE CAPITAL (ORIGINAL)
    st.subheader("📊 Distribución Actual de Capital (€)")
    datos_barras = {"Activo": ["Efectivo Libre"], "Valor (€)": [efectivo]}
    for ticker, pos in posiciones.items():
        cant = float(pos.get("cantidad", 0))
        precio_in = float(pos.get("precio_entrada", 0))
        datos_barras["Activo"].append(ticker.replace("-USD", ""))
        datos_barras["Valor (€)"].append(round(cant * precio_in, 2))

    df_barras = pd.DataFrame(datos_barras)
    fig_barras = px.bar(df_barras, x="Activo", y="Valor (€)", color="Activo", text_auto=".2f", template="plotly_dark")
    fig_barras.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_barras, use_container_width=True)

    st.divider()

    # 3. TABLA DE POSICIONES
    st.subheader("📌 Posiciones en Cartera")
    if posiciones:
        df_pos = pd.DataFrame.from_dict(posiciones, orient="index")
        st.dataframe(df_pos, use_container_width=True)
    else:
        st.info("No hay posiciones abiertas actualmente (100% en Liquidez).")

    st.divider()

    # 4. HISTORIAL
    st.subheader("📜 Historial de Operaciones")
    if historial:
        for item in reversed(historial[-15:]):
            st.caption(item)

    st.divider()

    # 5. GRÁFICA LINEAL AL FINAL
    st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
    seleccionadas = st.multiselect(
        "Selecciona activo(s) para comparar tendencia:",
        options=UNIVERSO_MERCADO,
        default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
    )

    if seleccionadas:
        try:
            df_precios = yf.download(seleccionadas, period="1d", interval="15m", progress=False)["Close"]
            if not df_precios.empty:
                if isinstance(df_precios, pd.Series):
                    df_precios = df_precios.to_frame()
                df_pct = ((df_precios - df_precios.iloc[0]) / df_precios.iloc[0]) * 100.0

                fig_lineas = go.Figure()
                for col in df_pct.columns:
                    fig_lineas.add_trace(go.Scatter(x=df_pct.index, y=df_pct[col], mode="lines", name=str(col).replace("-USD", "")))

                fig_lineas.update_layout(xaxis_title="Hora", yaxis_title="Variación (%)", hovermode="x unified", template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_lineas, use_container_width=True)
        except Exception:
            st.caption("Gráfica no disponible temporalmente.")

else:
    st.warning("Cargando datos desde GitHub...")
