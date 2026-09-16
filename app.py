import base64
import json
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Configuración de página
st.set_page_config(
    page_title="Crypto Scalper Dashboard", page_icon="🤖", layout="wide"
)

# Configuration GitHub
REPO = "administracion996/bot-trading-dashboard"
FILE_PATH = "cartera.json"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

# Universo de 34 Cryptos
UNIVERSO_MERCADO = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "BNB-USD",
    "XRP-USD",
    "ADA-USD",
    "AVAX-USD",
    "DOT-USD",
    "NEAR-USD",
    "ATOM-USD",
    "POL-USD",
    "APT-USD",
    "SUI-USD",
    "OP-USD",
    "ARB-USD",
    "SEI-USD",
    "LINK-USD",
    "UNI-USD",
    "AAVE-USD",
    "INJ-USD",
    "FET-USD",
    "RENDER-USD",
    "DOGE-USD",
    "SHIB-USD",
    "PEPE-USD",
    "BONK-USD",
    "FLOKI-USD",
    "WIF-USD",
    "LTC-USD",
    "BCH-USD",
    "ETC-USD",
    "FIL-USD",
    "ICP-USD",
    "TIA-USD",
]


@st.cache_data(ttl=30)
def cargar_cartera():
  url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
  headers = (
      {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
  )
  try:
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
      content_b64 = res.json()["content"]
      return json.loads(base64.b64decode(content_b64).decode("utf-8"))
  except Exception as e:
    st.error(f"Error cargando cartera: {e}")
  return None


@st.cache_data(ttl=60)
def obtener_historico_fluctuacion():
  """Descarga precios de las últimas 24h y calcula la variación porcentual acumulada."""
  data = yf.download(
      UNIVERSO_MERCADO, period="1d", interval="15m", progress=False
  )["Close"]
  # Normalizar a variación porcentual desde el inicio del periodo (0%)
  data_pct = ((data - data.iloc[0]) / data.iloc[0]) * 100
  return data_pct


# --- Cargar Datos ---
cartera = cargar_cartera()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  # Métricas Principales
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{cartera.get('total_cartera', 0):.2f} €")
  col2.metric("Efectivo Libre", f"{cartera.get('efectivo_disponible', 0):.2f} €")
  col3.metric("Posiciones Abiertas", len(cartera.get("posiciones_abiertas", {})))
  col4.metric(
      "Operaciones Registradas", len(cartera.get("historial_operaciones", []))
  )

  st.divider()

  # Tabla de Posiciones Abiertas
  st.subheader("📌 Posiciones en Cartera")
  posiciones = cartera.get("posiciones_abiertas", {})
  if posiciones:
    df_pos = pd.DataFrame.from_dict(posiciones, orient="index")
    st.dataframe(df_pos, use_container_width=True)
  else:
    st.info("No hay posiciones abiertas actualmente (100% en Liquidez).")

  st.divider()

  # Historial Reciente
  st.subheader("📜 ÚLTIMOS MOVIMIENTOS")
  historial = cartera.get("historial_operaciones", [])
  for item in reversed(historial[-10:]):
    st.caption(item)

  st.divider()

  # --- NUEVA GRÁFICA LINEAL DE FLUCTUACIÓN ---
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")

  seleccionadas = st.multiselect(
      "Selecciona activo(s) para comparar en la gráfica:",
      options=UNIVERSO_MERCADO,
      default=[
          "BTC-USD",
          "ETH-USD",
          "SOL-USD",
          "DOGE-USD",
          "PEPE-USD",
      ],  # Selección inicial
  )

  if seleccionadas:
    df_hist = obtener_historico_fluctuacion()

    fig = go.Figure()
    for ticker in seleccionadas:
      if ticker in df_hist.columns:
        fig.add_trace(
            go.Scatter(
                x=df_hist.index,
                y=df_hist[ticker],
                mode="lines",
                name=ticker.replace("-USD", ""),
            )
        )

    fig.update_layout(
        xaxis_title="Hora",
        yaxis_title="Variación (%)",
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

else:
  st.warning("Cargando datos de GitHub o archivo no encontrado...")
