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

st.set_page_config(
    page_title="Crypto Scalper Dashboard", page_icon="🤖", layout="wide"
)

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


@st.cache_data(ttl=5)
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
  registros = []
  compras_memoria = {}

  for log in historial_raw:
    match_fecha = re.search(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]", log)
    if not match_fecha:
      continue
    fecha_dt = datetime.strptime(match_fecha.group(1), "%Y-%m-%d %H:%M:%S")

    match_ticker = re.search(r"([A-Z0-9]{2,10}-USD)", log)
    ticker = (
        match_ticker.group(1).replace("-USD", "")
        if match_ticker
        else "DESCONOCIDO"
    )

    val_matches = re.findall(r"(\d+(?:\.\d+)?)\s*€", log)
    valor = float(val_matches[-1]) if val_matches else 0.0

    if "COMPRA" in log:
      if ticker not in compras_memoria:
        compras_memoria[ticker] = []
      compras_memoria[ticker].append(valor)

      registros.append({
          "Fecha": fecha_dt,
          "Tipo": "COMPRA 🟢",
          "Ticker": ticker,
          "Valor (€)": valor,
          "PnL (€)": 0.0,
          "Log": log,
      })

    elif "VENTA" in log or "Vendido" in log or "ROTACIÓN" in log:
      pnl_eur = 0.0
      match_pnl = re.search(r"PnL:\s*([+-]?\d+(?:\.\d+)?)\s*€", log)

      if match_pnl:
        pnl_eur = float(match_pnl.group(1))
        if ticker in compras_memoria and compras_memoria[ticker]:
          compras_memoria[ticker].pop(0)
      else:
        if ticker in compras_memoria and compras_memoria[ticker]:
          coste_compra = compras_memoria[ticker].pop(0)
          pnl_eur = valor - coste_compra
        else:
          match_pct = re.search(r"\(([+-]?\d+(?:\.\d+)?)\%\)", log)
          if match_pct and valor > 0:
            pct = float(match_pct.group(1))
            base = valor / (1.0 + (pct / 100.0))
            pnl_eur = valor - base

      registros.append({
          "Fecha": fecha_dt,
          "Tipo": "VENTA 🔴",
          "Ticker": ticker,
          "Valor (€)": valor,
          "PnL (€)": round(pnl_eur, 2),
          "Log": log,
      })

  return pd.DataFrame(registros)


def aplicar_filtros_grafica(df, key_prefix):
  if df.empty:
    return df

  c1, c2, c3 = st.columns([2, 2, 4])
  with c1:
    opciones_fecha = [
        "Todo",
        "Hoy",
        "Ayer",
        "Esta semana",
        "Semana pasada",
        "Personalizado",
    ]
    sel_fecha = st.selectbox(
        "📅 Filtro de Fecha", opciones_fecha, key=f"f_fecha_{key_prefix}"
    )

  ahora = datetime.now()
  hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
  f_inicio = datetime(2020, 1, 1)
  f_fin = ahora + timedelta(days=2)

  with c2:
    if sel_fecha == "Personalizado":
      rango = st.date_input(
          "Rango manual",
          [hoy_inicio.date(), hoy_inicio.date()],
          key=f"f_rango_{key_prefix}",
      )
      if isinstance(rango, (list, tuple)) and len(rango) == 2:
        f_inicio = datetime.combine(rango[0], datetime.min.time())
        f_fin = datetime.combine(rango[1], datetime.max.time())
    else:
      st.write("")
      if sel_fecha == "Hoy":
        f_inicio = hoy_inicio
        f_fin = ahora + timedelta(days=1)
      elif sel_fecha == "Ayer":
        f_inicio = hoy_inicio - timedelta(days=1)
        f_fin = hoy_inicio - timedelta(seconds=1)
      elif sel_fecha == "Esta semana":
        f_inicio = hoy_inicio - timedelta(days=hoy_inicio.weekday())
        f_fin = ahora + timedelta(days=1)
      elif sel_fecha == "Semana pasada":
        lunes_esta = hoy_inicio - timedelta(days=hoy_inicio.weekday())
        f_inicio = lunes_esta - timedelta(days=7)
        f_fin = lunes_esta - timedelta(seconds=1)

  with c3:
    lista_cryptos = sorted(df["Ticker"].unique().tolist())
    sel_cryptos = st.multiselect(
        "🪙 Criptomonedas",
        options=lista_cryptos,
        default=lista_cryptos,
        key=f"f_crypto_{key_prefix}",
    )

  df_filtrado = df[(df["Fecha"] >= f_inicio) & (df["Fecha"] <= f_fin)]
  if sel_cryptos:
    df_filtrado = df_filtrado[df_filtrado["Ticker"].isin(sel_cryptos)]
  else:
    df_filtrado = df_filtrado.iloc[0:0]

  return df_filtrado


# --- ESTRUCTURA DEL DASHBOARD ---
cartera = cargar_cartera()
st.title("🤖 Dashboard Bot Trading Hiperactivo")

if cartera:
  efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
  total = round(float(cartera.get("total_cartera", 0.0)), 2)
  posiciones = cartera.get("posiciones_abiertas", {})
  historial_raw = cartera.get("historial_operaciones", [])

  df_historial_completo = parsear_historial(historial_raw)

  # 1. MÉTRICAS GLOBALES
  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Cartera Total", f"{total:.2f} €")
  col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
  col3.metric("Posiciones Abiertas", len(posiciones))
  col4.metric("Total Ops. Históricas", len(historial_raw))

  st.divider()

  # 2. VOLUMEN OPERADO (COMPRAS VS VENTAS)
  st.subheader("📊 Volumen Operado: Compras vs Ventas")
  df_grafica = aplicar_filtros_grafica(
      df_historial_completo, key_prefix="grafica_volumen"
  )

  if not df_grafica.empty:
    df_agrupado = (
        df_grafica.groupby(["Ticker", "Tipo"])["Valor (€)"].sum().reset_index()
    )
    fig_barras = px.bar(
        df_agrupado,
        x="Ticker",
        y="Valor (€)",
        color="Tipo",
        barmode="group",
        text_auto=".2f",
        color_discrete_map={"COMPRA 🟢": "#00CC96", "VENTA 🔴": "#EF553B"},
        template="plotly_dark",
    )
    fig_barras.update_layout(
        xaxis_title="",
        yaxis_title="Euros (€)",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(fig_barras, use_container_width=True)
  else:
    st.info("No hay datos de operaciones que coincidan con estos filtros.")

  st.divider()

  # 3. TABLA DE POSICIONES DETALLADA CON PNL REAL
  st.subheader("📌 Posiciones Actuales en Cartera")
  if posiciones:
    pos_tickers = list(posiciones.keys())
    precios_live = {}

    try:
      df_live = yf.download(
          pos_tickers, period="1d", interval="5m", progress=False
      )["Close"]
      tasa_eur = 0.92
      try:
        df_t = yf.Ticker("EUR=X").history(period="1d")
        if not df_t.empty:
          tasa_eur = float(df_t["Close"].iloc[-1])
      except Exception:
        pass

      for t in pos_tickers:
        try:
          if len(pos_tickers) == 1:
            val = float(df_live.dropna().iloc[-1])
          else:
            val = float(df_live[t].dropna().iloc[-1])
          precios_live[t] = val * tasa_eur
        except Exception:
          pass
    except Exception:
      pass

    filas_pos = []
    for ticker, pos in posiciones.items():
      cant = float(pos.get("cantidad", 0))
      p_ent = float(pos.get("precio_entrada", 0))
      p_act = precios_live.get(ticker, p_ent)

      tot_comprado = round(cant * p_ent, 2)
      tot_actual = round(cant * p_act, 2)
      diferencia = round(tot_actual - tot_comprado, 2)
      pct_pnl = ((p_act - p_ent) / p_ent * 100) if p_ent > 0 else 0.0

      filas_pos.append({
          "Activo": ticker.replace("-USD", ""),
          "Cantidad": cant,
          "Precio Entrada (€)": round(p_ent, 4),
          "Precio Total Comprado (€)": tot_comprado,
          "Precio Actual (€)": round(p_act, 4),
          "Precio Total Actual (€)": tot_actual,
          "Diferencia (€)": diferencia,
          "Porcentaje PnL (%)": f"{pct_pnl:+.2f}%",
          "Fecha Entrada": pos.get("timestamp_entrada", "N/A"),
      })

    st.dataframe(pd.DataFrame(filas_pos), use_container_width=True)
  else:
    st.info("No hay posiciones abiertas actualmente (100% liquidez).")

  st.divider()

  # 4. HISTORIAL DE OPERACIONES CON SCROLL
  st.subheader("📜 Historial de Operaciones")

  c1, c2 = st.columns([3, 3])
  with c1:
    opciones_fecha_h = [
        "Todo",
        "Hoy",
        "Ayer",
        "Esta semana",
        "Semana pasada",
        "Personalizado",
    ]
    sel_fecha_h = st.selectbox(
        "📅 Filtro de Fecha (Historial)",
        opciones_fecha_h,
        key="f_fecha_historial",
    )

  ahora = datetime.now()
  hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
  f_inicio_h = datetime(2020, 1, 1)
  f_fin_h = ahora + timedelta(days=2)

  with c2:
    if sel_fecha_h == "Personalizado":
      rango_h = st.date_input(
          "Rango manual (Historial)",
          [hoy_inicio.date(), hoy_inicio.date()],
          key="f_rango_historial",
      )
      if isinstance(rango_h, (list, tuple)) and len(rango_h) == 2:
        f_inicio_h = datetime.combine(rango_h[0], datetime.min.time())
        f_fin_h = datetime.combine(rango_h[1], datetime.max.time())
    else:
      st.write("")
      if sel_fecha_h == "Hoy":
        f_inicio_h = hoy_inicio
        f_fin_h = ahora + timedelta(days=1)
      elif sel_fecha_h == "Ayer":
        f_inicio_h = hoy_inicio - timedelta(days=1)
        f_fin_h = hoy_inicio - timedelta(seconds=1)
      elif sel_fecha_h == "Esta semana":
        f_inicio_h = hoy_inicio - timedelta(days=hoy_inicio.weekday())
        f_fin_h = ahora + timedelta(days=1)
      elif sel_fecha_h == "Semana pasada":
        lunes_esta = hoy_inicio - timedelta(days=hoy_inicio.weekday())
        f_inicio_h = lunes_esta - timedelta(days=7)
        f_fin_h = lunes_esta - timedelta(seconds=1)

  if not df_historial_completo.empty:
    df_texto = df_historial_completo[
        (df_historial_completo["Fecha"] >= f_inicio_h)
        & (df_historial_completo["Fecha"] <= f_fin_h)
    ]
  else:
    df_texto = pd.DataFrame()

  pnl_acumulado = df_texto["PnL (€)"].sum() if not df_texto.empty else 0.0
  ventas_cerradas = (
      len(df_texto[df_texto["Tipo"].str.contains("VENTA")])
      if not df_texto.empty
      else 0
  )

  col_m1, col_m2 = st.columns(2)
  col_m1.metric("💰 PnL Realizado en Rango", f"{pnl_acumulado:+.2f} €")
  col_m2.metric("🔄 Ventas Ejecutadas", ventas_cerradas)

  st.write("")

  if not df_texto.empty:
    df_tabla_historial = df_texto.sort_values(
        by="Fecha", ascending=False
    ).copy()
    df_tabla_historial["Fecha"] = df_tabla_historial["Fecha"].dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    st.dataframe(
        df_tabla_historial[[
            "Fecha",
            "Tipo",
            "Ticker",
            "Valor (€)",
            "PnL (€)",
            "Log",
        ]],
        column_config={
            "Fecha": st.column_config.TextColumn("Fecha / Hora"),
            "Tipo": st.column_config.TextColumn("Operación"),
            "Ticker": st.column_config.TextColumn("Activo"),
            "Valor (€)": st.column_config.NumberColumn(
                "Importe (€)", format="%.2f €"
            ),
            "PnL (€)": st.column_config.NumberColumn(
                "PnL (€)", format="%+.2f €"
            ),
            "Log": st.column_config.TextColumn(
                "Registro Completo", width="large"
            ),
        },
        hide_index=True,
        use_container_width=True,
        height=400,
    )
  else:
    st.info("No hay operaciones registradas en el rango de fecha seleccionado.")

  st.divider()

  # 5. GRÁFICA LINEAL TENDENCIA 24H
  st.subheader("📈 Fluctuación del Mercado (Últimas 24 Horas %)")
  seleccionadas_linea = st.multiselect(
      "🪙 Activos a comparar:",
      options=UNIVERSO_MERCADO,
      default=["BTC-USD", "ETH-USD", "SOL-USD", "AAVE-USD", "INJ-USD"],
      key="filtro_lineas",
  )

  if seleccionadas_linea:
    try:
      df_precios = yf.download(
          seleccionadas_linea, period="1d", interval="5m", progress=False
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
      st.caption("Gráfico temporalmente no disponible.")

else:
  st.warning("Recuperando datos desde GitHub...")
