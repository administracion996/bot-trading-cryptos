import base64
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Configuración de página
st.set_page_config(
    page_title="Crypto Scalper Dashboard", page_icon="🤖", layout="wide"
)

# Configuración de GitHub
REPO = "administracion996/bot-trading-dashboard"
FILE_PATH = "cartera.json"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

# Universo de criptomonedas sincronizado
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
    "MATIC-USD",
    "LTC-USD",
    "BCH-USD",
    "ETC-USD",
    "LINK-USD",
    "AAVE-USD",
    "INJ-USD",
    "FET-USD",
    "ALGO-USD",
    "XLM-USD",
    "TRX-USD",
    "DOGE-USD",
    "SHIB-USD",
    "PEPE24478-USD",
    "BONK-USD",
    "FLOKI-USD",
    "FIL-USD",
    "ICP-USD",
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


@st.cache_data(ttl=120)
def obtener_historico_fluctuacion():
  data = yf.download(
      UNIVERSO_MERCADO, period="1d", interval="15m", progress=False
  )["Close"]
  data_pct = ((data - data.iloc[0]) / data.iloc[0]) * 100
  return data_pct


# --- CARGA DE DATOS ---
cartera = cargar_cartera()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  # 1. MÉTRICAS PRINCIPALES
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{cartera.get('total_cartera', 0):.2f} €")
  col2.metric("Efectivo Libre", f"{cartera.get('efectivo_disponible', 0):.2f} €")
  col3.metric("Posiciones Abiertas", len(cartera.get("posiciones_abiertas", {})))
  col4.metric(
      "Operaciones Registradas", len(cartera.get("historial_operaciones", []))
  )

  st.divider()

  # 2. GRÁFICA DE BARRAS INICIAL (DISTRIBUCIÓN DE CAPITAL)
  st.subheader("📊 Distribución Actual de Capital (€)")
  posiciones = cartera.get("posiciones_abiertas", {})
  efectivo = cartera.get("efectivo_disponible", 0.0)

  datos_barras = {"Activo": ["Efectivo Libre"], "Valor (€)": [efectivo]}
  for ticker, pos in posiciones.items():
    valor_posicion = round(pos["cantidad"] * pos["precio_entrada"], 2)
    datos_barras["Activo"].append(ticker.replace("-USD", ""))
    datos_barras["Valor (€)"].append(valor_posicion)

  df_barras = pd.DataFrame(datos_barras)
  fig_barras = px.bar(
      df_barras,
      x="Activo",
      y="Valor (€)",
      color="Activo",
      text_auto=".2f",
      template="plotly_dark",
  )
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

  # 4. HISTORIAL DE OPERACIONES
  st.subheader("📜 Historial de Operaciones")
  historial = cartera.get("historial_operaciones", [])
  for item in reversed(historial[-15:]):
    st.caption(item)

  st.divider()

  # 5. GRÁFICA DE LÍNEAS AL FINAL (FLUCTUACIÓN 24H %)
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
  seleccionadas = st.multiselect(
      "Selecciona criptomonedas para comparar:",
      options=UNIVERSO_MERCADO,
      default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "LINK-USD"],
  )

  if seleccionadas:
    try:
      df_hist = obtener_historico_fluctuacion()
      fig_lineas = go.Figure()

      for ticker in seleccionadas:
        if ticker in df_hist.columns:
          fig_lineas.add_trace(
              go.Scatter(
                  x=df_hist.index,
                  y=df_hist[ticker],
                  mode="lines",
                  name=ticker.replace("-USD", ""),
              )
          )

      fig_lineas.update_layout(
          xaxis_title="Hora",
          yaxis_title="Variación (%)",
          hovermode="x unified",
          template="plotly_dark",
          margin=dict(l=20, r=20, t=30, b=20),
      )
      st.plotly_chart(fig_lineas, use_container_width=True)
    except Exception as e:
      st.warning(f"Cargando gráfico de precios... ({e})")

else:
  st.warning("Conectando con GitHub para obtener el estado actual...")
