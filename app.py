import base64

from datetime import datetime, timedelta
import json
import re
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

# Configuración GitHub
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
    "BONK-USD",
    "FLOKI-USD",
    "FIL-USD",
    "ICP-USD",
]


@st.cache_data(ttl=10)
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
  except Exception:
    pass
  return None


def parsear_historial(historial_raw):
  """Transforma el historial de texto en un DataFrame estructurado para filtros."""
  registros = []
  for log in historial_raw:
    match_fecha = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", log)
    if not match_fecha:
      continue

    fecha_dt = datetime.strptime(match_fecha.group(1), "%Y-%m-%d %H:%M:%S")

    if "COMPRA" in log:
      match_ticker = re.search(r"COMPRA \d+(\.\d+)? de ([A-Z0-9\-]+)", log)
      match_val = re.search(r"\((\d+(\.\d+)?)€", log)

      ticker = (
          match_ticker.group(2).replace("-USD", "")
          if match_ticker
          else "OTRO"
      )
      valor = float(match_val.group(1)) if match_val else 0.0
      registros.append({
          "Fecha": fecha_dt,
          "Tipo": "COMPRA",
          "Ticker": ticker,
          "Valor (€)": valor,
          "Log": log,
      })

    elif "VENTA" in log:
      match_ticker = re.search(r"VENTA ([A-Z0-9\-]+)", log)
      match_neto = re.search(r"Neto: (\d+(\.\d+)?)€", log)

      ticker = (
          match_ticker.group(1).replace("-USD", "")
          if match_ticker
          else "OTRO"
      )
      valor = float(match_neto.group(1)) if match_neto else 0.0
      registros.append({
          "Fecha": fecha_dt,
          "Tipo": "VENTA",
          "Ticker": ticker,
          "Valor (€)": valor,
          "Log": log,
      })

  return pd.DataFrame(registros)


# --- CARGA DE DATOS ---
cartera = cargar_cartera()

st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
  total = round(float(cartera.get("total_cartera", 0.0)), 2)
  posiciones = cartera.get("posiciones_abiertas", {})
  historial_raw = cartera.get("historial_operaciones", [])

  df_historial = parsear_historial(historial_raw)

  # =========================================================
  # PANEL LATERAL: FILTROS GLOBALES
  # =========================================================
  st.sidebar.header("🔍 Filtros del Dashboard")

  opcion_fecha = st.sidebar.selectbox(
      "Rango de Fecha:",
      ["Todo", "Hoy", "Ayer", "Esta semana", "Semana pasada", "Personalizado"],
  )

  ahora = datetime.now()
  hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

  if opcion_fecha == "Hoy":
    f_inicio, f_fin = hoy_inicio, ahora
  elif opcion_fecha == "Ayer":
    f_inicio = hoy_inicio - timedelta(days=1)
    f_fin = hoy_inicio - timedelta(seconds=1)
  elif opcion_fecha == "Esta semana":
    f_inicio = hoy_inicio - timedelta(days=hoy_inicio.weekday())
    f_fin = ahora
  elif opcion_fecha == "Semana pasada":
    lunes_esta_semana = hoy_inicio - timedelta(days=hoy_inicio.weekday())
    f_inicio = lunes_esta_semana - timedelta(days=7)
    f_fin = lunes_esta_semana - timedelta(seconds=1)
  elif opcion_fecha == "Personalizado":
    rango = st.sidebar.date_input(
        "Seleccionar rango", [hoy_inicio.date(), hoy_inicio.date()]
    )
    if isinstance(rango, list) and len(rango) == 2:
      f_inicio = datetime.combine(rango[0], datetime.min.time())
      f_fin = datetime.combine(rango[1], datetime.max.time())
    else:
      f_inicio, f_fin = datetime(2020, 1, 1), ahora
  else:
    f_inicio, f_fin = datetime(2020, 1, 1), ahora

  # Aplicar filtro de fecha al historial
  if not df_historial.empty:
    df_filtrado = df_historial[
        (df_historial["Fecha"] >= f_inicio) & (df_historial["Fecha"] <= f_fin)
    ]
  else:
    df_filtrado = pd.DataFrame(
        columns=["Fecha", "Tipo", "Ticker", "Valor (€)", "Log"]
    )

  # Filtro por Cryptos
  lista_cryptos = (
      sorted(df_historial["Ticker"].unique().tolist())
      if not df_historial.empty
      else []
  )
  cryptos_seleccionadas = st.sidebar.multiselect(
      "Filtrar por Criptomoneda(s):",
      options=lista_cryptos,
      default=lista_cryptos,
  )

  if cryptos_seleccionadas and not df_filtrado.empty:
    df_filtrado = df_filtrado[
        df_filtrado["Ticker"].isin(cryptos_seleccionadas)
    ]

  # =========================================================
  # 1. MÉTRICAS CON FILTRO APLICADO
  # =========================================================
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{total:.2f} €")
  col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
  col3.metric("Posiciones Abiertas", len(posiciones))
  col4.metric("Operaciones en Rango", len(df_filtrado))

  st.divider()

  # =========================================================
  # 2. GRÁFICA DE BARRAS DOBLE (COMPRA VS VENTA POR CRYPTO)
  # =========================================================
  st.subheader(
      f"📊 Volumen Operado por Crypto: Compras vs Ventas ({opcion_fecha})"
  )

  if not df_filtrado.empty:
    df_agrupado = (
        df_filtrado.groupby(["Ticker", "Tipo"])["Valor (€)"].sum().reset_index()
    )

    fig_barras = px.bar(
        df_agrupado,
        x="Ticker",
        y="Valor (€)",
        color="Tipo",
        barmode="group",  # Barras dobles agrupadas por crypto
        text_auto=".2f",
        color_discrete_map={"COMPRA": "#00CC96", "VENTA": "#EF553B"},
        template="plotly_dark",
    )
    fig_barras.update_layout(
        xaxis_title="Criptomoneda",
        yaxis_title="Volumen (€)",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig_barras, use_container_width=True)
  else:
    st.info("No hay registros de operaciones en el rango de fecha elegido.")

  st.divider()

  # =========================================================
  # 3. TABLA DE POSICIONES EN CARTERA
  # =========================================================
  st.subheader("📌 Posiciones Abiertas Activas")
  if posiciones:
    df_pos = pd.DataFrame.from_dict(posiciones, orient="index")
    st.dataframe(df_pos, use_container_width=True)
  else:
    st.info("No hay posiciones abiertas actualmente (100% en Liquidez).")

  st.divider()

  # =========================================================
  # 4. HISTORIAL DE OPERACIONES FILTRADO POR FECHA Y CRYPTO
  # =========================================================
  st.subheader(f"📜 Historial Filtrado ({len(df_filtrado)} registros)")
  if not df_filtrado.empty:
    for _, fila in df_filtrado.sort_values(
        by="Fecha", ascending=False
    ).iterrows():
      st.caption(fila["Log"])
  else:
    st.caption("Sin operaciones en la selección actual.")

  st.divider()

  # =========================================================
  # 5. GRÁFICA LINEAL AL FINAL (TENDENCIA 24H)
  # =========================================================
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
  seleccionadas_grafica = st.multiselect(
      "Selecciona activo(s) para comparar tendencia:",
      options=UNIVERSO_MERCADO,
      default=["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
  )

  if seleccionadas_grafica:
    try:
      df_precios = yf.download(
          seleccionadas_grafica, period="1d", interval="15m", progress=False
      )["Close"]
      if not df_precios.empty:
        if isinstance(df_precios, pd.Series):
          df_precios = df_precios.to_frame()
        df_pct = (
            (df_precios - df_precios.iloc[0]) / df_precios.iloc[0]
        ) * 100.0

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
            margin=dict(l=20, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_lineas, use_container_width=True)
    except Exception:
      st.caption("Gráfica no disponible de forma temporal.")

else:
  st.warning("Cargando datos desde GitHub...")
