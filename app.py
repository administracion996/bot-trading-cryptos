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
def obtener_datos_mercado_seguros():
  precios = {}
  df_historico = pd.DataFrame()
  tasa_eur = 0.92

  try:
    df_tasa = yf.Ticker("EUR=X").history(period="1d")
    if not df_tasa.empty:
      tasa_eur = float(df_tasa["Close"].iloc[-1])
  except:
    pass

  try:
    data = yf.download(
        UNIVERSO_MERCADO, period="1d", interval="15m", progress=False
    )
    if not data.empty and "Close" in data:
      df_close = data["Close"]
      df_historico = df_close
      # Obtener el último precio en EUR para cada moneda disponible
      for col in df_close.columns:
        serie_valida = df_close[col].dropna()
        if not serie_valida.empty:
          precios[col] = float(serie_valida.iloc[-1]) * tasa_eur
  except:
    pass

  return precios, df_historico, tasa_eur


# --- CARGA Y PROCESAMIENTO ---
cartera = cargar_cartera()
precios_actuales, df_historico, tasa_eur = obtener_datos_mercado_seguros()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  posiciones = cartera.get("posiciones_abiertas", {})
  efectivo = float(cartera.get("efectivo_disponible", 0.0))

  valor_posiciones_total = 0.0
  pnl_total_acumulado = 0.0
  datos_posiciones_tabla = []

  for ticker, pos in posiciones.items():
    precio_entrada = float(pos["precio_entrada"])
    cantidad = float(pos["cantidad"])
    precio_actual = precios_actuales.get(ticker, precio_entrada)

    valor_actual = cantidad * precio_actual
    inversion = cantidad * precio_entrada
    pnl_eur = valor_actual - inversion
    pnl_pct = (
        ((precio_actual - precio_entrada) / precio_entrada) * 100.0
        if precio_entrada > 0
        else 0.0
    )

    valor_posiciones_total += valor_actual
    pnl_total_acumulado += pnl_eur

    datos_posiciones_tabla.append({
        "Activo": ticker.replace("-USD", ""),
        "Cantidad": cantidad,
        "Precio Entrada (€)": round(precio_entrada, 4),
        "Precio Actual (€)": round(precio_actual, 4),
        "Valor Actual (€)": round(valor_actual, 2),
        "PnL (€)": round(pnl_eur, 2),
        "PnL (%)": f"{pnl_pct:+.2f}%",
    })

  total_cartera_calculado = round(efectivo + valor_posiciones_total, 2)

  # 1. MÉTRICAS PRINCIPALES
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{total_cartera_calculado:.2f} €")
  col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
  col3.metric("Posiciones Abiertas", len(posiciones))
  col4.metric("PnL No Realizado", f"{pnl_total_acumulado:+.2f} €")

  st.divider()

  # 2. GRÁFICA DE BARRAS DE DISTRIBUCIÓN DE CAPITAL
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
    st.dataframe(pd.DataFrame(datos_posiciones_tabla), use_container_width=True)
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

  # 5. GRÁFICA LINEAL DE FLUCTUACIÓN 24H (AL FINAL)
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
  seleccionadas = st.multiselect(
      "Selecciona activos para comparar su variación relativa:",
      options=UNIVERSO_MERCADO,
      default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "LINK-USD"],
  )

  if seleccionadas and not df_historico.empty:
    try:
      # Filtrar columnas existentes y calcular %
      cols_validas = [c for c in seleccionadas if c in df_historico.columns]
      if cols_validas:
        sub_df = df_historico[cols_validas].dropna(how="all")
        df_pct = ((sub_df - sub_df.iloc[0]) / sub_df.iloc[0]) * 100.0

        fig_lineas = go.Figure()
        for ticker in cols_validas:
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
      st.caption(f"Esperando datos históricos de precios... ({e})")

else:
  st.warning("Conectando con GitHub para recuperar el estado...")
