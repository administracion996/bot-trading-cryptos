import base64
import json
import re
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# 1. Configuración de la página
st.set_page_config(
    page_title="Dashboard de Trading", page_icon="📈", layout="wide"
)

# 2. Conexión con GitHub (¡CORREGIDO!)
REPO = "administracion996/bot-trading-cryptos"
FILE_PATH = "cartera.json"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"

universo_mercado = [
    "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD",
    "AVAX-USD", "DOT-USD", "NEAR-USD", "ATOM-USD",
    "XRP-USD", "LTC-USD", "BCH-USD", "LINK-USD",
    "DOGE-USD", "SHIB-USD",
]

@st.cache_data(ttl=5)
def cargar_cartera_github():
    try:
        res = requests.get(RAW_URL)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
    return None

@st.cache_data(ttl=300)
def obtener_tasa_usd_eur():
    try:
        df = yf.Ticker("EUR=X").history(period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except:
        pass
    return 0.92

@st.cache_data(ttl=30)
def obtener_precio_actual(ticker, tasa_eur):
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="15m")
        if not df.empty:
            return float(df["Close"].iloc[-1]) * tasa_eur
    except:
        pass
    return 0.0

st.title("📈 Panel de Control - Bot de Trading Algorítmico (Reales en €)")

cartera = cargar_cartera_github()
tasa_actual = obtener_tasa_usd_eur()

if cartera:
    # --- SECCIÓN 1: MÉTRICAS GLOBALES ---
    col1, col2, col3 = st.columns(3)
    valor_total = cartera.get("total_cartera", 1000.0)
    efectivo = cartera.get("efectivo_disponible", 0.0)
    num_posiciones = len(cartera.get("posiciones_abiertas", {}))

    col1.metric("Capital Total (€)", f"{valor_total:.2f} €")
    col2.metric("Efectivo Libre (€)", f"{efectivo:.2f} €")
    col3.metric("Posiciones Activas", f"{num_posiciones} / {len(universo_mercado)}")
    st.markdown("---")

    # --- SECCIÓN 2: GRÁFICO ---
    st.subheader("📊 Gráfico de Rendimiento (%) con Puntos de Entrada 🟢 y Salida 🔴")
    activos_seleccionados = st.multiselect(
        "Selecciona las criptomonedas que deseas comparar:",
        options=universo_mercado,
        default=["BTC-USD", "ETH-USD"],
    )

    if activos_seleccionados:
        fig = go.Figure()
        historial_crudo = cartera.get("historial_operaciones", [])

        for ticker in activos_seleccionados:
            try:
                df_hist = yf.Ticker(ticker).history(period="2d", interval="15m")
                if not df_hist.empty:
                    df_hist.index = df_hist.index.tz_localize(None)
                    p0 = df_hist["Close"].iloc[0]
                    var_pct = ((df_hist["Close"] - p0) / p0) * 100

                    fig.add_trace(go.Scatter(x=df_hist.index, y=var_pct, mode="lines", name=ticker, line=dict(width=2)))

                    fechas_compra, valores_compra, textos_compra = [], [], []
                    fechas_venta, valores_venta, textos_venta = [], [], []

                    for op in historial_crudo:
                        match_time = re.search(r"\[(.*?)\]", op)
                        if not match_time: continue
                        f_str = match_time.group(1)
                        try:
                            f_dt = pd.to_datetime(f_str)
                            idx_pos = df_hist.index.get_indexer([f_dt], method="nearest")[0]
                            t_cercano = df_hist.index[idx_pos]
                            val_cercano = var_pct.iloc[idx_pos]

                            if ("COMPRA" in op or "INICIO" in op) and (ticker in op or "INICIO" in op):
                                fechas_compra.append(t_cercano)
                                valores_compra.append(val_cercano)
                                textos_compra.append(f"🟢 COMPRA {ticker}<br>Hora: {t_cercano.strftime('%H:%M:%S')}")

                            elif ("VENTA" in op or "EMERGENCIA" in op or "STOP" in op) and ticker in op:
                                fechas_venta.append(t_cercano)
                                valores_venta.append(val_cercano)
                                
                                match_pnl = re.search(r"(?:Beneficio Neto:|Neto:)\s*([-0-9.]+)\s*€", op)
                                match_pct = re.search(r"Rentabilidad:\s*([-0-9.]+)\s*%", op)

                                pnl_val = float(match_pnl.group(1)) if match_pnl else None
                                pct_val = float(match_pct.group(1)) if match_pct else (round((pnl_val / 50.0) * 100, 2) if pnl_val is not None else None)

                                pnl_info = f"<br>Beneficio: {pnl_val:.2f}€" if pnl_val is not None else ""
                                pct_info = f"<br>Rentabilidad: {pct_val:.2f}%" if pct_val is not None else ""
                                tipo_label = "🔴 VENTA" if "VENTA" in op else "🛑 STOP-LOSS"
                                
                                textos_venta.append(f"{tipo_label} {ticker}<br>Hora: {t_cercano.strftime('%H:%M:%S')}{pnl_info}{pct_info}")
                        except:
                            pass

                    if fechas_compra:
                        fig.add_trace(go.Scatter(x=fechas_compra, y=valores_compra, mode="markers", name=f"Compras {ticker}", marker=dict(symbol="circle", size=11, color="green", line=dict(width=2, color="white")), hovertext=textos_compra, hoverinfo="text", showlegend=False))
                    if fechas_venta:
                        fig.add_trace(go.Scatter(x=fechas_venta, y=valores_venta, mode="markers", name=f"Ventas {ticker}", marker=dict(symbol="circle", size=11, color="red", line=dict(width=2, color="white")), hovertext=textos_venta, hoverinfo="text", showlegend=False))
            except:
                pass

        fig.update_layout(xaxis_title="Fecha / Hora", yaxis_title="Rendimiento (%)", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=20, r=20, t=30, b=20), template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Selecciona al menos un activo para ver el gráfico.")

    st.markdown("---")

    # --- SECCIÓN 3: HISTORIAL (ARRIBA) ---
    st.subheader("📜 Historial y Beneficios Netos")

    historial_crudo = cartera.get("historial_operaciones", [])
    datos_historial = []

    for operacion in historial_crudo:
        match_time = re.search(r"\[(.*?)\]", operacion)
        fecha_str = match_time.group(1) if match_time else ""
        try:
            fecha_obj = pd.to_datetime(fecha_str)
        except:
            fecha_obj = pd.to_datetime("today")

        beneficio = None
        texto_detalle = operacion  

        match_pnl = re.search(r"(?:Beneficio Neto:|Neto:)\s*([-0-9.]+)\s*€", operacion)
        if match_pnl:
            beneficio = float(match_pnl.group(1))
            if "Rentabilidad:" not in operacion and "VENTA" in operacion:
                rentabilidad_calc = round((beneficio / 50.0) * 100, 2)
                texto_detalle = f"{operacion} | Rentabilidad: {rentabilidad_calc}%"

        tipo = "INFO"
        if "COMPRA" in operacion or "INICIAL" in operacion or "INICIO:" in operacion:
            tipo = "🟢 COMPRA"
        elif "VENTA" in operacion:
            tipo = "🔴 VENTA"
        elif "EMERGENCIA" in operacion or "STOP" in operacion:
            tipo = "🛑 STOP-LOSS"

        datos_historial.append({
            "Fecha": fecha_obj,
            "Tipo": tipo,
            "Beneficio Neto (€)": beneficio,
            "Detalle": texto_detalle,
        })

    df_historial = pd.DataFrame(datos_historial)

    if not df_historial.empty:
        opcion_tiempo = st.selectbox("Filtrar por intervalo de tiempo:", ["Hoy", "Este Mes", "Este Año", "Todo"])
        ahora = pd.to_datetime("today")

        if opcion_tiempo == "Hoy": df_filtrado = df_historial[df_historial["Fecha"].dt.date == ahora.date()]
        elif opcion_tiempo == "Este Mes": df_filtrado = df_historial[(df_historial["Fecha"].dt.year == ahora.year) & (df_historial["Fecha"].dt.month == ahora.month)]
        elif opcion_tiempo == "Este Año": df_filtrado = df_historial[df_historial["Fecha"].dt.year == ahora.year]
        else: df_filtrado = df_historial

        df_filtrado = df_filtrado.sort_values(by="Fecha", ascending=False)
        total_periodo = df_filtrado["Beneficio Neto (€)"].sum(skipna=True)

        st.metric(label=f"Balance Generado ({opcion_tiempo})", value=f"{total_periodo:.2f} €")

        def color_beneficio(val):
            if pd.isna(val): return ""
            return "color: green" if val > 0 else "color: red" if val < 0 else "color: gray"

        st.dataframe(
            df_filtrado.style.map(color_beneficio, subset=["Beneficio Neto (€)"]).format({
                "Beneficio Neto (€)": lambda x: f"{x:.2f} €" if pd.notna(x) else "-",
                "Fecha": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Sin registros de operaciones.")

    st.markdown("---")

    # --- SECCIÓN 4: POSICIONES ABIERTAS (ABAJO) ---
    st.subheader("💼 Estado de las Posiciones (Comisiones descontadas)")
    posiciones = cartera.get("posiciones_abiertas", {})

    if posiciones:
        tabla_pos = []
        for ticker, info in posiciones.items():
            cantidad = info.get("cantidad", 0)
            precio_entrada = info.get("precio_entrada", 0)
            precio_actual = obtener_precio_actual(ticker, tasa_actual)

            if precio_actual > 0:
                valor_actual = cantidad * precio_actual
                inversion_inicial = cantidad * precio_entrada
                diferencia_eur = valor_actual - inversion_inicial
                rentabilidad_pct = ((diferencia_eur / inversion_inicial) * 100 if inversion_inicial > 0 else 0)
            else:
                precio_actual = precio_entrada
                diferencia_eur = 0.0
                rentabilidad_pct = 0.0

            tabla_pos.append({
                "Activo": ticker,
                "Cantidad": cantidad,
                "Precio Entrada (€)": precio_entrada,
                "Precio Actual (€)": precio_actual,
                "Diferencia (€)": diferencia_eur,
                "Rentabilidad (%)": rentabilidad_pct,
            })

        df_posiciones = pd.DataFrame(tabla_pos)

        def color_posiciones(val):
            return "color: green" if val > 0 else "color: red" if val < 0 else "color: gray"

        st.dataframe(
            df_posiciones.style.map(color_posiciones, subset=["Diferencia (€)", "Rentabilidad (%)"]).format({
                "Precio Entrada (€)": "{:.6f}",
                "Precio Actual (€)": "{:.6f}",
                "Diferencia (€)": "{:.2f} €",
                "Rentabilidad (%)": "{:.2f} %",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay posiciones abiertas en este momento.")

else:
    st.warning("Sincronizando con GitHub... Por favor, recarga en unos segundos.")
