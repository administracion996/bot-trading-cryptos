import base64
from datetime import datetime, timedelta
import json
import re
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# 1. Configuración de la página
st.set_page_config(
    page_title="Dashboard de Trading", page_icon="📈", layout="wide"
)

# 2. Conexión con GitHub
REPO = "administracion996/bot-trading-dashboard"
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

    # --- SECCIÓN 2: GRÁFICO DE BARRAS AGRUPADAS (COMPRA VS VENTA POR ACCIÓN) ---
    st.subheader("📊 Volumen Operado por Acción (Compra vs Venta)")

    hoy = datetime.now().date()
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        fechas_seleccionadas = st.date_input(
            "Filtrar por rango de fechas:",
            value=(hoy, hoy),
        )
    with col_f2:
        activos_grafico = st.multiselect(
            "Filtrar por acción / criptomoneda:",
            options=universo_mercado,
            default=universo_mercado[:8],
        )

    historial_crudo = cartera.get("historial_operaciones", [])
    datos_barras = {t: {"Compra": 0.0, "Venta": 0.0} for t in activos_grafico}

    if isinstance(fechas_seleccionadas, (tuple, list)) and len(fechas_seleccionadas) == 2:
        f_inicio = pd.to_datetime(fechas_seleccionadas[0])
        f_fin = pd.to_datetime(fechas_seleccionadas[1]) + pd.Timedelta(days=1, microseconds=-1)
    elif isinstance(fechas_seleccionadas, (tuple, list)) and len(fechas_seleccionadas) == 1:
        f_inicio = pd.to_datetime(fechas_seleccionadas[0])
        f_fin = pd.to_datetime(fechas_seleccionadas[0]) + pd.Timedelta(days=1, microseconds=-1)
    else:
        f_inicio = pd.to_datetime(hoy)
        f_fin = pd.to_datetime(hoy) + pd.Timedelta(days=1, microseconds=-1)

    for op in historial_crudo:
        match_time = re.search(r"\[(.*?)\]", op)
        if not match_time:
            continue
        f_op = pd.to_datetime(match_time.group(1))

        if f_inicio <= f_op <= f_fin:
            for ticker in activos_grafico:
                ticker_base = ticker.split("-")[0]
                if ticker in op or ticker_base in op:
                    op_u = op.upper()
                    
                    is_buy = any(k in op_u for k in ["COMPRA", "DCA", "SALVAVIDAS", "INICIAL"]) and not any(k in op_u for k in ["VENTA", "STOP", "EMERGENCIA"])
                    is_sell = any(k in op_u for k in ["VENTA", "STOP", "EMERGENCIA"])

                    match_inv = re.search(r"(?:Invertido|Inversión):\s*([\d.]+)", op, re.IGNORECASE)
                    match_fee = re.search(r"([\d.]+)\s*€\s*inc\. fee", op, re.IGNORECASE)
                    match_neto = re.search(r"(?:Neto|Recuperado):\s*([\d.]+)\s*€", op, re.IGNORECASE)
                    match_pnl = re.search(r"Beneficio Neto:\s*([-0-9.]+)\s*€", op, re.IGNORECASE)

                    if is_buy:
                        if match_inv:
                            monto = float(match_inv.group(1))
                        elif match_fee:
                            monto = float(match_fee.group(1))
                        elif "INICIO:" in op_u or "ASIGNADOS 50€" in op_u:
                            monto = 50.0
                        else:
                            monto = 50.0
                        datos_barras[ticker]["Compra"] += monto

                    elif is_sell:
                        if match_neto:
                            monto = float(match_neto.group(1))
                        elif match_pnl:
                            monto = 50.0 + float(match_pnl.group(1))
                        else:
                            monto = 50.0
                        datos_barras[ticker]["Venta"] += monto

    df_barras = pd.DataFrame(datos_barras).T.reset_index()
    df_barras.columns = ["Activo", "Compra", "Venta"]

    if not df_barras.empty and (df_barras["Compra"].sum() > 0 or df_barras["Venta"].sum() > 0):
        fig_barras = go.Figure()

        fig_barras.add_trace(
            go.Bar(
                x=df_barras["Activo"],
                y=df_barras["Compra"],
                name="Compras (€)",
                marker_color="#27ae60",
                text=df_barras["Compra"].apply(lambda v: f"{v:.1f}€" if v > 0 else ""),
                textposition="outside",
            )
        )

        fig_barras.add_trace(
            go.Bar(
                x=df_barras["Activo"],
                y=df_barras["Venta"],
                name="Ventas (€)",
                marker_color="#e74c3c",
                text=df_barras["Venta"].apply(lambda v: f"{v:.1f}€" if v > 0 else ""),
                textposition="outside",
            )
        )

        max_val = max(df_barras["Compra"].max(), df_barras["Venta"].max(), 10)

        fig_barras.update_layout(
            barmode="group",
            xaxis_title="Criptomoneda / Activo",
            yaxis_title="Monto Acumulado (€)",
            yaxis=dict(range=[0, max_val * 1.25]),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            margin=dict(l=20, r=20, t=40, b=20),
            template="plotly_white",
        )
        st.plotly_chart(fig_barras, use_container_width=True)
    else:
        st.info("No se registraron operaciones para los activos y rango de fechas seleccionados.")

    st.markdown("---")

    # --- SECCIÓN 3: HISTORIAL Y BENEFICIOS NETOS ---
    st.subheader("📜 Historial y Beneficios Netos")

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

        match_pnl = re.search(
            r"(?:Beneficio Neto:|Neto:)\s*([-0-9.]+)\s*€", operacion
        )
        if match_pnl:
            beneficio = float(match_pnl.group(1))
            if "Rentabilidad:" not in operacion and "VENTA" in operacion:
                rentabilidad_calc = round((beneficio / 50.0) * 100, 2)
                texto_detalle = f"{operacion} | Rentabilidad: {rentabilidad_calc}%"

        tipo = "INFO"
        op_u = operacion.upper()
        if "SALVAVIDAS" in op_u or "DCA" in op_u:
            tipo = "🟢 DCA SALVAVIDAS"
        elif "COMPRA" in op_u or "INICIAL" in op_u or "INICIO:" in op_u:
            tipo = "🟢 COMPRA"
        elif "VENTA" in op_u:
            tipo = "🔴 VENTA"
        elif "EMERGENCIA" in op_u or "STOP" in op_u:
            tipo = "🛑 STOP-LOSS"

        datos_historial.append({
            "Fecha": fecha_obj,
            "Tipo": tipo,
            "Beneficio Neto (€)": beneficio,
            "Detalle": texto_detalle,
        })

    df_historial = pd.DataFrame(datos_historial)

    if not df_historial.empty:
        opcion_tiempo = st.selectbox(
            "Filtrar por intervalo de tiempo:",
            ["Hoy", "Esta Semana", "Este Mes", "Este Año", "Todo"],
        )
        ahora = pd.to_datetime("today")

        if opcion_tiempo == "Hoy":
            df_filtrado = df_historial[df_historial["Fecha"].dt.date == ahora.date()]
        elif opcion_tiempo == "Esta Semana":
            inicio_semana = (ahora - pd.Timedelta(days=ahora.dayofweek)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            df_filtrado = df_historial[df_historial["Fecha"] >= inicio_semana]
        elif opcion_tiempo == "Este Mes":
            df_filtrado = df_historial[
                (df_historial["Fecha"].dt.year == ahora.year)
                & (df_historial["Fecha"].dt.month == ahora.month)
            ]
        elif opcion_tiempo == "Este Año":
            df_filtrado = df_historial[df_historial["Fecha"].dt.year == ahora.year]
        else:
            df_filtrado = df_historial

        df_filtrado = df_filtrado.sort_values(by="Fecha", ascending=False)
        total_periodo = df_filtrado["Beneficio Neto (€)"].sum(skipna=True)

        st.metric(
            label=f"Balance Generado ({opcion_tiempo})", value=f"{total_periodo:.2f} €"
        )

        def color_beneficio(val):
            if pd.isna(val):
                return ""
            return (
                "color: green" if val > 0 else "color: red" if val < 0 else "color: gray"
            )

        st.dataframe(
            df_filtrado.style.map(
                color_beneficio, subset=["Beneficio Neto (€)"]
            ).format({
                "Beneficio Neto (€)": (
                    lambda x: f"{x:.2f} €" if pd.notna(x) else "-"
                ),
                "Fecha": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin registros de operaciones.")

    st.markdown("---")

    # --- SECCIÓN 4: POSICIONES ABIERTAS ---
    st.subheader("💼 Estado de las Posiciones (Comisiones descontadas)")
    posiciones = cartera.get("posiciones_abiertas", {})

    if posiciones:
        tabla_pos = []
        for ticker, info in posiciones.items():
            cantidad = info.get("cantidad", 0)
            precio_entrada = info.get("precio_entrada", 0)
            precio_actual = obtener_precio_actual(ticker, tasa_actual)

            inversion_inicial = cantidad * precio_entrada

            if precio_actual > 0:
                valor_actual = cantidad * precio_actual
                diferencia_eur = valor_actual - inversion_inicial
                rentabilidad_pct = (
                    (diferencia_eur / inversion_inicial) * 100
                    if inversion_inicial > 0
                    else 0
                )
            else:
                precio_actual = precio_entrada
                valor_actual = inversion_inicial
                diferencia_eur = 0.0
                rentabilidad_pct = 0.0

            tabla_pos.append({
                "Activo": ticker,
                "Cantidad": cantidad,
                "Precio Entrada (€)": precio_entrada,
                "Precio Actual (€)": precio_actual,
                "Valor Total Compra (€)": inversion_inicial,
                "Valor Total Actual (€)": valor_actual,
                "Diferencia (€)": diferencia_eur,
                "Rentabilidad (%)": rentabilidad_pct,
            })

        df_posiciones = pd.DataFrame(tabla_pos)

        def color_posiciones(val):
            return (
                "color: green" if val > 0 else "color: red" if val < 0 else "color: gray"
            )

        st.dataframe(
            df_posiciones.style.map(
                color_posiciones, subset=["Diferencia (€)", "Rentabilidad (%)"]
            ).format({
                "Precio Entrada (€)": "{:.6f}",
                "Precio Actual (€)": "{:.6f}",
                "Valor Total Compra (€)": "{:.2f} €",
                "Valor Total Actual (€)": "{:.2f} €",
                "Diferencia (€)": "{:.2f} €",
                "Rentabilidad (%)": "{:.2f} %",
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay posiciones abiertas en este momento.")

else:
    st.warning("Sincronizando con GitHub... Por favor, recarga en unos segundos.")
