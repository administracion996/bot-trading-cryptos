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

# 1. CORTAR CACHÉ LARGO PARA ACTUALIZACIÓN INSTANTÁNEA
@st.cache_data(ttl=5)
def cargar_cartera():
  url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
  headers = (
      {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
  )
  try:
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      content_b64 = res.json()["content"]
      return json.loads(base64.b64decode(content_b64).decode("utf-8"))
  except Exception:
    pass
  return None


cartera = cargar_cartera()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if not cartera:
  st.warning(
      "Conectando con GitHub o esperando actualización de 'cartera.json'..."
  )
  st.stop()

# Extracción de valores base
efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
total = round(float(cartera.get("total_cartera", 0.0)), 2)
posiciones = cartera.get("posiciones_abiertas", {})
historial = cartera.get("historial_operaciones", [])

# =========================================================
# 1. MÉTRICAS PRINCIPALES DE CABECERA (ORIGINAL)
# =========================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Cartera Total", f"{total:.2f} €")
c2.metric("Efectivo Libre", f"{efectivo:.2f} €")
c3.metric("Posiciones Abiertas", len(posiciones))
c4.metric("Operaciones Registradas", len(historial))

st.divider()

# =========================================================
# 2. GRÁFICA INICIAL DE BARRAS: DISTRIBUCIÓN DE CAPITAL (ORIGINAL)
# =========================================================
st.subheader("📊 Distribución Actual de Capital (€)")
filas_barras = [{"Activo": "Efectivo Libre", "Valor (€)": efectivo}]

for ticker, pos in posiciones.items():
  cant = float(pos.get("cantidad", 0))
  p_in = float(pos.get("precio_entrada", 0))
  val = round(cant * p_in, 2)
  filas_barras.append({"Activo": ticker.replace("-USD", ""), "Valor (€)": val})

df_barras = pd.DataFrame(filas_barras)
fig_barras = px.bar(
    df_barras,
    x="Activo",
    y="Valor (€)",
    color="Activo",
    text_auto=".2f",
    template="plotly_dark",
)
fig_barras.update_layout(
    showlegend=False, height=350, margin=dict(l=20, r=20, t=20, b=20)
)
st.plotly_chart(fig_barras, use_container_width=True)

st.divider()

# =========================================================
# 3. TABLA DE POSICIONES ABIERTAS (ORIGINAL)
# =========================================================
st.subheader("📌 Posiciones en Cartera")
if posiciones:
  df_pos = pd.DataFrame.from_dict(posiciones, orient="index")
  st.dataframe(df_pos, use_container_width=True)
else:
  st.info("No hay posiciones abiertas actualmente (100% en Liquidez).")

st.divider()

# =========================================================
# 4. HISTORIAL DE OPERACIONES (ORIGINAL)
# =========================================================
st.subheader("📜 Historial de Operaciones")
if historial:
  for item in reversed(historial[-12:]):
    st.caption(item)
else:
  st.caption("Sin operaciones registradas.")

st.divider()

# =========================================================
# 5. GRÁFICA LINEAL DE FLUCTUACIÓN (NUEVA - AL FINAL Y AISLADA)
# =========================================================
st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
tickers_opciones = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "ADA-USD",
    "AVAX-USD",
    "DOGE-USD",
    "LINK-USD",
    "XRP-USD",
]
seleccionados = st.multiselect(
    "Selecciona criptomonedas para comparar:",
    options=tickers_opciones,
    default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
)

if seleccionados:
  try:
    data = yf.download(
        seleccionados, period="1d", interval="15m", progress=False
    )
    if not data.empty and "Close" in data:
      df_close = data["Close"]
      if isinstance(df_close, pd.Series):
        df_close = df_close.to_frame()
      df_pct = ((df_close - df_close.iloc[0]) / df_close.iloc[0]) * 100.0

      fig_lineas = go.Figure()
      for col in df_pct.columns:
        fig_lineas.add_trace(
            go.Scatter(
                x=df_pct.index,
                y=df_pct[col],
                mode="lines",
                name=str(col).replace("-USD", ""),
            )
        )
      fig_lineas.update_layout(
          xaxis_title="Hora",
          yaxis_title="Variación (%)",
          hovermode="x unified",
          template="plotly_dark",
          height=400,
          margin=dict(l=20, r=20, t=30, b=20),
      )
      st.plotly_chart(fig_lineas, use_container_width=True)
  except Exception:
    st.caption("Cargando gráfica de tendencia...")
