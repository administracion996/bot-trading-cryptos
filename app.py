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

# Universo completo de mercado verificado
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
    st.error(f"Error cargando datos de GitHub: {e}")
  return None


@st.cache_data(ttl=60)
def obtener_precios_actuales():
  try:
    data = yf.download(
        UNIVERSO_MERCADO, period="1d", interval="15m", progress=False
    )["Close"]
    tasa_eur = float(
        yf.Ticker("EUR=X").history(period="1d")["Close"].iloc[-1]
    )
    precios = (data.iloc[-1] * tasa_eur).to_dict()
    return precios, data, tasa_eur
  except:
    return {}, pd.DataFrame(), 0.92


# --- CARGA DE DATOS ---
cartera = cargar_cartera()
precios_actuales, df_historico, tasa_eur = obtener_precios_actuales()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  posiciones = cartera.get("posiciones_abiertas", {})
  efectivo = cartera.get("efectivo_disponible", 0.0)

  # Calcular valor real de posiciones y PnL
  valor_posiciones_total = 0.0
  pnl_total_acumulado = 0.0

  datos_posiciones_tabla = []

  for ticker, pos in posiciones.items():
    precio_actual = precios_actuales.get(ticker, pos["precio_entrada"])
    valor_actual = pos["cantidad"] * precio_actual
    inversion = pos["cantidad"] * pos["precio_entrada"]
    pnl_eur = valor_actual - inversion
    pnl_pct = ((precio_actual - pos["precio_entrada"]) / pos["precio_entrada"]) * 100.0

    valor_posiciones_total += valor_actual
    pnl_total_acumulado += pnl_eur

    datos_posiciones_tabla.append({
        "Activo": ticker.replace("-USD", ""),
        "Cantidad": pos["cantidad"],
        "Precio Entrada (€)": round(pos["precio_entrada"], 4),
        "Precio Actual (€)": round(precio_actual, 4),
        "Valor Actual (€)": round(valor_actual, 2),
        "PnL (€)": round(pnl_eur, 2),
        "PnL (%)": f"{pnl_pct:+.2f}%",
    })

  total_cartera_calculado = round(efectivo + valor_posiciones_total, 2)

  # 1. MÉTRICAS PRINCIPALES DE CABECERA
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{total_cartera_calculado:.2f} €")
  col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
  col3.metric("Posiciones Abiertas", len(posiciones))
  col4.metric(
      "PnL No Realizado",
      f"{pnl_total_acumulado:+.2f} €",
      delta_color="normal",
  )

  st.divider()

  # 2. GRÁFICA INICIAL DE BARRAS (DISTRIBUCIÓN DE CAPITAL ORIGINAL)
  st.subheader("📊 Distribución de Capital en Cartera (€)")
  datos_barras = {"Activo": ["Efectivo Libre"], "Valor (€)": [efectivo]}
  for item in datos_posiciones_tabla:
    datos_barras["Activo"].append(item["Activo"])
    datos_barras["Valor (€)"].append(item["Valor Actual (€)"])

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

  # 3. TABLA DE POSICIONES DETALLADA
  st.subheader("📌 Posiciones Abiertas en Tiempo Real")
  if datos_posiciones_tabla:
    df_tabla = pd.DataFrame(datos_posiciones_tabla)
    st.dataframe(df_tabla, use_container_width=True)
  else:
    st.info("No hay posiciones abiertas actualmente (100% en Liquidez).")

  st.divider()

  # 4. HISTORIAL DE OPERACIONES
  st.subheader("📜 Historial de Operaciones")
  historial = cartera.get("historial_operaciones", [])
  if historial:
    for item in reversed(historial[-15:]):
      st.caption(item)
  else:
    st.caption("Sin operaciones registradas.")

  st.divider()

  # 5. NUEVA GRÁFICA DE LÍNEAS AL FINAL (FLUCTUACIÓN MERCADO 24H)
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
  seleccionadas = st.multiselect(
      "Selecciona activos para comparar su variación relativa:",
      options=UNIVERSO_MERCADO,
      default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "LINK-USD"],
  )

  if seleccionadas and not df_historico.empty:
    try:
      df_pct = (
          (df_historico[seleccionadas] - df_historico[seleccionadas].iloc[0])
          / df_historico[seleccionadas].iloc[0]
      ) * 100.0

      fig_lineas = go.Figure()
      for ticker in seleccionadas:
        if ticker in df_pct.columns:
          fig_lineas.add_trace(
              go.Scatter(
                  x=df_pct.index,
                  y=df_pct[ticker],
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
      st.warning(f"Calculando histórico... ({e})")

else:
  st.warning("Conectando con GitHub para recuperar el estado...")
