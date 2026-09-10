import json
import re
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Trading", page_icon="📈", layout="wide"
)

# Conexión con GitHub
REPO = "administracion996/bot-trading-dashboard"
FILE_PATH = "cartera.json"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/{FILE_PATH}"

universo_mercado = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "ADA-USD",
    "AVAX-USD",
    "DOT-USD",
    "NEAR-USD",
    "ATOM-USD",
    "XRP-USD",
    "LTC-USD",
    "BCH-USD",
    "LINK-USD",
    "DOGE-USD",
    "SHIB-USD",
]


@st.cache_data(ttl=30)
def cargar_cartera_github():
    try:
        res = requests.get(RAW_URL)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
    return None


@st.cache_data(ttl=600)
def obtener_tasa_usd_eur():
    """Descarga el tipo de cambio real de 1 Dólar a Euros"""
    try:
        df = yf.Ticker("EUR=X").history(period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except:
        pass
    return 0.92  # Respaldo


@st.cache_data(ttl=60)
def obtener_precio_actual(ticker, tasa_eur):
    """Obtiene el precio actual convertido a Euros reales"""
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
    # --- 1. MÉTRICAS GLOBALES ---
    col1, col2, col3 = st.columns(3)
    valor_total = cartera.get("total_cartera", 1000.0)
    efectivo = cartera.get("efectivo_disponible", 0.0)
    num_posiciones = len(cartera.get("posiciones_abiertas", {}))

    col1.metric("Capital Total (€)", f"{valor_total:.2f} €")
    col2.metric("Efectivo Libre (€)", f"{efectivo:.2f} €")
    col3.metric("Posiciones Activas", f"{num_posiciones} / {len(universo_mercado)}")
    st.markdown("---")

    # --- 2. GRÁFICO CON MARCADORES DE COMPRA EN TIEMPO REAL ---
    st.subheader("📊 Gráfico de Rendimiento (%) con Puntos de Compra 🟢")
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
                df_hist = yf.Ticker(ticker).history(
                    period="2d", interval="15m"
                )
                if not df_hist.empty:
                    # Eliminar zona horaria para coincidir limpiamente con las fechas del historial
                    df_hist.index = df_hist.index.tz_localize(None)

                    p0 = df_hist["Close"].iloc[0]
                    var_pct = ((df_hist["Close"] - p0) / p0) * 100

                    # Trazar la línea del activo
                    fig.add_trace(
                        go.Scatter(
                            x=df_hist.index,
                            y=var_pct,
                            mode="lines",
                            name=ticker,
                            line=dict(width=2),
                        )
                    )

                    # Buscar puntos de compra para este ticker en el historial
                    fechas_compra = []
                    valores_compra = []
                    textos_compra = []

                    for op in historial_crudo:
                        if ("COMPRA" in op or "INICIO" in op) and (
                            ticker in op or "INICIO" in op
                        ):
                            match_time = re.search(r"\[(.*?)\]", op)
                            if match_time:
                                f_str = match_time.group(1)
                                try:
                                    f_dt = pd.to_datetime(f_str)

                                    # Encontrar el timestamp más cercano en el dataframe
                                    idx_pos = df_hist.index.get_indexer(
                                        [f_dt], method="nearest"
                                    )[0]
                                    t_cercano = df_hist.index[idx_pos]
                                    val_cercano = var_pct.iloc[idx_pos]

                                    fechas_compra.append(t_cercano)
                                    valores_compra.append(val_cercano)
                                    textos_compra.append(
                                        f"🟢 COMPRA {ticker}<br>Fecha: {t_cercano.strftime('%H:%M:%S')}"
                                    )
                                except:
                                    pass

                    # Dibujar puntos verdes en las compras
                    if fechas_compra:
                        fig.add_trace(
                            go.Scatter(
                                x=fechas_compra,
                                y=valores_compra,
                                mode="markers",
                                name=f"Entradas {ticker}",
                                marker=dict(
                                    symbol="circle",
                                    size=11,
                                    color="green",
                                    line=dict(width=2, color="white"),
                                ),
                                hovertext=textos_compra,
                                hoverinfo="text",
                                showlegend=False,
                            )
                        )
            except Exception as e:
                pass

        fig.update_layout(
            xaxis_title="Fecha / Hora",
            yaxis_title="Rendimiento (%)",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            margin=dict(l=20, r=20, t=30, b=20),
            template="plotly_white",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Selecciona al menos un activo para ver el gráfico.")

    st.markdown("---")

    # --- 3. POSICIONES ABIERTAS (CON BENEFICIO EN TIEMPO REAL) ---
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
                rentabilidad_pct = (
                    (diferencia_eur / inversion_inicial) * 100
                    if inversion_inicial > 0
                    else 0
                )
            else:
                precio_actual = precio_entrada
                diferencia_eur = 0.0
                rentabilidad_pct = 0.0

            tabla_pos.append(
                {
                    "Activo": ticker,
                    "Cantidad": cantidad,
                    "Precio Entrada (€)": precio_entrada,
                    "Precio Actual (€)": precio_actual,
                    "Diferencia (€)": diferencia_eur,
                    "Rentabilidad (%)": rentabilidad_pct,
                }
            )

        df_posiciones = pd.DataFrame(tabla_pos)

        def color_positivo_negativo(val):
            color = "green" if val > 0 else "red" if val < 0 else "gray"
            return f"color: {color}"

        st.dataframe(
            df_posiciones.style.map(
                color_positivo_negativo,
                subset=["Diferencia (€)", "Rentabilidad (%)"],
            ).format(
                {
                    "Precio Entrada (€)": "{:.6f}",
                    "Precio Actual (€)": "{:.6f}",
                    "Diferencia (€)": "{:.2f} €",
                    "Rentabilidad (%)": "{:.2f} %",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay posiciones abiertas en este momento.")

    st.markdown("---")

    # --- 4. HISTORIAL ANALÍTICO CON FILTRO DE TIEMPO ---
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

        beneficio = 0.0
        if "Beneficio Neto:" in operacion or "Neto:" in operacion:
            match_pnl = re.search(r"Neto:\s*([-0-9.]+)€", operacion)
            if match_pnl:
                beneficio = float(match_pnl.group(1))
        elif "Resultado de la operación:" in operacion:
            match_pnl = re.search(
                r"Resultado de la operación:\s*([-0-9.]+)€", operacion
            )
            if match_pnl:
                beneficio = float(match_pnl.group(1))

        tipo = "INFO"
        if (
            "COMPRA" in operacion
            or "INICIAL" in operacion
            or "INICIO:" in operacion
        ):
            tipo = "🟢 COMPRA"
        elif "VENTA" in operacion:
            tipo = "🔴 VENTA"
        elif "EMERGENCIA" in operacion or "STOP" in operacion:
            tipo = "🛑 STOP-LOSS"

        datos_historial.append(
            {
                "Fecha": fecha_obj,
                "Tipo": tipo,
                "Beneficio Neto (€)": beneficio,
                "Detalle": operacion,
            }
        )

    df_historial = pd.DataFrame(datos_historial)

    if not df_historial.empty:
        opcion_tiempo = st.selectbox(
            "Filtrar por intervalo de tiempo:",
            ["Hoy", "Este Mes", "Este Año", "Todo"],
        )

        ahora = pd.to_datetime("today")
        if opcion_tiempo == "Hoy":
            df_filtrado = df_historial[
                df_historial["Fecha"].dt.date == ahora.date()
            ]
        elif opcion_tiempo == "Este Mes":
            df_filtrado = df_historial[
                (df_historial["Fecha"].dt.year == ahora.year)
                & (df_historial["Fecha"].dt.month == ahora.month)
            ]
        elif opcion_tiempo == "Este Año":
            df_filtrado = df_historial[
                df_historial["Fecha"].dt.year == ahora.year
            ]
        else:
            df_filtrado = df_historial

        df_filtrado = df_filtrado.sort_values(by="Fecha", ascending=False)
        total_periodo = df_filtrado["Beneficio Neto (€)"].sum()

        st.metric(
            label=f"Balance Generado ({opcion_tiempo})",
            value=f"{total_periodo:.2f} €",
        )

        st.dataframe(
            df_filtrado.style.map(
                lambda val: (
                    "color: green"
                    if val > 0
                    else "color: red"
                    if val < 0
                    else "color: gray"
                ),
                subset=["Beneficio Neto (€)"],
            ).format(
                {
                    "Beneficio Neto (€)": "{:.2f} €",
                    "Fecha": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sin registros de operaciones.")

else:
    st.warning("Sincronizando con GitHub... Por favor, recarga en unos segundos.")
