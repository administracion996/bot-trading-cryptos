import base64
from datetime import datetime, timedelta
import json
import math
import re
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
import pytz

# Configuración de página
st.set_page_config(
    page_title="Crypto Trading Dashboard", page_icon="🎯", layout="wide"
)

# Estilos CSS inyectados para compactar tablas, reducir márgenes y destacar pestañas
st.markdown(
    """
    <style>
        /* Reducir espacio superior y lateral global */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }
        
        /* Destacar visibilidad de las pestañas (Tabs) */
        button[data-baseweb="tab"] {
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            padding: 8px 20px !important;
        }
        
        /* Compactar fuentes y espaciado de las celdas en las tablas */
        [data-testid="stDataFrame"] div[role="grid"] {
            font-size: 0.85rem !important;
        }
        
        /* Ajustar contenedor de métricas */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.85rem !important;
        }
        
        hr {
            margin-top: 0.5rem !important;
            margin-bottom: 0.5rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# Configuración GitHub
REPO = "administracion996/bot-trading-cryptos"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
tz_madrid = pytz.timezone("Europe/Madrid")

# Expresiones regulares
REGEX_FECHA = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]")
REGEX_TICKER = re.compile(r"([A-Z0-9]{2,10}-USD)")
REGEX_VALOR = re.compile(r"(\d+(?:\.\d+)?)\s*€")
REGEX_SCORE = re.compile(r"Score Gemini:\s*(\d+)", re.IGNORECASE)
REGEX_PNL = re.compile(r"PnL:\s*([+-]?\d+(?:\.\d+)?)\s*€")

# Configuración de columnas con anchos ajustados al contenido
CONFIG_POSICIONES = {
    "Activo": st.column_config.TextColumn("Activo", width=90),
    "Unidades": st.column_config.NumberColumn("Unidades", width=110),
    "Entrada (€)": st.column_config.NumberColumn("Entrada (€)", width=110),
    "Actual (€)": st.column_config.NumberColumn("Actual (€)", width=110),
    "Inversión (€)": st.column_config.NumberColumn("Inversión (€)", width=110),
    "PnL Flotante (€)": st.column_config.NumberColumn("PnL Flotante (€)", width=120),
    "Rentabilidad (%)": st.column_config.TextColumn("Rentabilidad (%)", width=120),
    "⏱️ Time Stop": st.column_config.TextColumn("⏱️ Time Stop", width=100),
}

CONFIG_RADAR = {
    "Activo": st.column_config.TextColumn("Activo", width=100),
    "RSI": st.column_config.NumberColumn("RSI", width=100),
}

CONFIG_HISTORIAL = {
    "Fecha": st.column_config.TextColumn("Fecha", width=150),
    "Tipo": st.column_config.TextColumn("Tipo", width=110),
    "Ticker": st.column_config.TextColumn("Ticker", width=90),
    "Valor (€)": st.column_config.NumberColumn("Valor (€)", width=100),
    "PnL (€)": st.column_config.NumberColumn("PnL (€)", width=100),
    "Score_Gemini": st.column_config.TextColumn("Score Gemini", width=100),
    "Log": st.column_config.TextColumn("Log", width="large"),
}


# --- FUNCIONES DE SEGURIDAD Y EXTRACCIÓN ---
def safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except Exception:
        return default


def obtener_campo_num(diccionario, lista_claves, defecto=0.0):
    if not isinstance(diccionario, dict):
        return defecto
    for k in lista_claves:
        if k in diccionario and diccionario[k] is not None:
            val = safe_float(diccionario[k], None)
            if val is not None:
                return val
    return defecto


def obtener_sincro(cartera_data):
    if not isinstance(cartera_data, dict):
        return "Sin datos"
    claves = [
        "ultima_actualizacion",
        "timestamp",
        "fecha",
        "last_update",
        "fecha_actualizacion",
    ]
    tel = cartera_data.get("telemetria")
    if isinstance(tel, dict):
        for k in claves:
            val = tel.get(k)
            if val and str(val).strip():
                return str(val)
    for k in claves:
        val = cartera_data.get(k)
        if val and str(val).strip():
            return str(val)
    return "Sincronizado"


def obtener_estado(cartera_data, estado_defecto="Activo"):
    if not isinstance(cartera_data, dict):
        return estado_defecto
    tel = cartera_data.get("telemetria")
    if isinstance(tel, dict):
        est = tel.get("estado")
        if est and str(est).strip():
            return str(est)
    est = cartera_data.get("estado")
    if est and str(est).strip():
        return str(est)
    return estado_defecto


@st.cache_data(ttl=5)
def cargar_cartera(file_path="cartera.json"):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}?v={int(datetime.now().timestamp())}"
    headers = (
        {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Cache-Control": "no-cache",
        }
        if GITHUB_TOKEN
        else {"Cache-Control": "no-cache"}
    )
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            return json.loads(
                base64.b64decode(res.json()["content"]).decode("utf-8")
            )
    except Exception:
        pass
    return None


@st.cache_data(ttl=60)
def obtener_precios_posiciones(pos_tickers_tuple):
    if not pos_tickers_tuple:
        return {}, 0.92
    precios_live, tasa_eur = {}, 0.92
    try:
        df_live = yf.download(
            list(pos_tickers_tuple), period="1d", interval="5m", progress=False
        )["Close"]
        try:
            df_t = yf.Ticker("EUR=X").history(period="1d")
            if not df_t.empty:
                tasa_eur = float(df_t["Close"].iloc[-1])
        except Exception:
            pass

        for t in pos_tickers_tuple:
            try:
                val = (
                    float(df_live.dropna().iloc[-1])
                    if len(pos_tickers_tuple) == 1
                    else float(df_live[t].dropna().iloc[-1])
                )
                precios_live[t] = val * tasa_eur
            except Exception:
                pass
    except Exception:
        pass
    return precios_live, tasa_eur


def parsear_historial(historial_raw, es_short=False):
    registros = []
    if not isinstance(historial_raw, list):
        return pd.DataFrame(
            columns=[
                "Fecha",
                "Tipo",
                "Ticker",
                "Valor (€)",
                "PnL (€)",
                "Score_Gemini",
                "Log",
            ]
        )

    for log in historial_raw:
        try:
            if isinstance(log, dict):
                fecha_raw = (
                    log.get("fecha_salida")
                    or log.get("fecha_entrada")
                    or log.get("fecha")
                    or log.get("Fecha")
                    or log.get("timestamp")
                    or ""
                )
                try:
                    fecha_dt = datetime.fromisoformat(str(fecha_raw))
                except Exception:
                    try:
                        fecha_dt = datetime.strptime(
                            str(fecha_raw), "%Y-%m-%d %H:%M:%S"
                        )
                    except Exception:
                        fecha_dt = datetime.now(tz_madrid)

                ticker = str(
                    log.get("ticker")
                    or log.get("Ticker")
                    or log.get("moneda")
                    or "DESCONOCIDO"
                ).replace("-USD", "")
                valor = safe_float(
                    log.get("monto_invertido")
                    or log.get("valor")
                    or log.get("importe")
                    or log.get("monto")
                    or log.get("precio", 0.0)
                )

                pnl_eur = safe_float(
                    log.get("beneficio_neto")
                    or log.get("pnl")
                    or log.get("PnL (€)")
                    or log.get("pnl_eur")
                    or 0.0
                )

                score_gemini = (
                    log.get("confianza_gemini")
                    or log.get("score")
                    or log.get("score_gemini")
                )

                motivo = str(log.get("motivo_salida") or "").upper()
                tipo_bruto = str(log.get("tipo") or log.get("Tipo") or "").upper()

                if motivo:
                    tipo = "VENTA 🔴" if not es_short else "CIERRE SHORT 🟢"
                elif tipo_bruto:
                    if "COMPRA" in tipo_bruto:
                        tipo = "COMPRA 🟢"
                    elif "VENTA" in tipo_bruto:
                        tipo = "VENTA 🔴" if not es_short else "CIERRE SHORT 🟢"
                    elif "SHORT" in tipo_bruto:
                        tipo = "APERTURA SHORT 🔴"
                    else:
                        tipo = "OTRO ⚪"
                else:
                    tipo = "VENTA 🔴" if not es_short else "CIERRE SHORT 🟢"

                registros.append({
                    "Fecha": fecha_dt,
                    "Tipo": tipo,
                    "Ticker": ticker,
                    "Valor (€)": valor,
                    "PnL (€)": round(pnl_eur, 2),
                    "Score_Gemini": score_gemini,
                    "Log": str(motivo) if motivo else str(log),
                })
                continue

            if not isinstance(log, str):
                log = str(log)

            m_fecha = REGEX_FECHA.search(log)
            if not m_fecha:
                continue
            try:
                fecha_dt = datetime.strptime(
                    m_fecha.group(1), "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                fecha_dt = datetime.now(tz_madrid)

            m_ticker = REGEX_TICKER.search(log)
            ticker = (
                m_ticker.group(1).replace("-USD", "")
                if m_ticker
                else ("EUR" if "BARRIDO" in log else "DESCONOCIDO")
            )
            val_matches = REGEX_VALOR.findall(log)
            valor = float(val_matches[-1]) if val_matches else 0.0
            m_score = REGEX_SCORE.search(log)
            score_gemini = int(m_score.group(1)) if m_score else None
            m_pnl = REGEX_PNL.search(log)
            pnl_eur = float(m_pnl.group(1)) if m_pnl else 0.0

            tipo = "OTRO ⚪"
            if "COMPRA" in log:
                tipo = "COMPRA 🟢"
            elif "VENTA" in log and not es_short:
                tipo = "VENTA 🔴"
            elif "APERTURA SHORT" in log:
                tipo = "APERTURA SHORT 🔴"
            elif "CIERRE SHORT" in log:
                tipo = "CIERRE SHORT 🟢"

            registros.append({
                "Fecha": fecha_dt,
                "Tipo": tipo,
                "Ticker": ticker,
                "Valor (€)": valor,
                "PnL (€)": round(pnl_eur, 2),
                "Score_Gemini": score_gemini,
                "Log": log,
            })
        except Exception:
            continue

    if not registros:
        return pd.DataFrame(
            columns=[
                "Fecha",
                "Tipo",
                "Ticker",
                "Valor (€)",
                "PnL (€)",
                "Score_Gemini",
                "Log",
            ]
        )
    return pd.DataFrame(registros)


def calcular_metricas_live(
    efectivo, posiciones, df_historial, precios_live, es_short=False
):
    hoy = datetime.now(tz_madrid).date()
    pnl_realizado = 0.0
    if not df_historial.empty and "Fecha" in df_historial.columns:
        df_hoy = df_historial[df_historial["Fecha"].dt.date == hoy]
        if not df_hoy.empty:
            pnl_realizado = safe_float(df_hoy["PnL (€)"].sum())

    valor_posiciones_live = 0.0
    pnl_flotante_total = 0.0

    if isinstance(posiciones, dict):
        for t, pos in posiciones.items():
            if not isinstance(pos, dict):
                continue
            cant = safe_float(pos.get("cantidad") or pos.get("unidades") or 0)
            p_ent = safe_float(
                pos.get("precio_entrada")
                or pos.get("precio_compra")
                or pos.get("precio")
                or 0
            )
            p_act = precios_live.get(t, p_ent)
            inv_inicial = cant * p_ent

            if es_short:
                pnl_flotante = (p_ent - p_act) * cant
                valor_pos_live = inv_inicial + pnl_flotante
            else:
                pnl_flotante = (p_act - p_ent) * cant
                valor_pos_live = cant * p_act

            valor_posiciones_live += valor_pos_live
            pnl_flotante_total += pnl_flotante

    capital_activo_live = round(efectivo + valor_posiciones_live, 2)
    pnl_hoy_total = round(pnl_realizado + pnl_flotante_total, 2)

    return capital_activo_live, pnl_hoy_total


def generar_tabla_posiciones(posiciones, precios_live, es_short=False):
    filas = []
    if not isinstance(posiciones, dict):
        return pd.DataFrame(filas)

    ahora = datetime.now(tz_madrid)
    for ticker, pos in posiciones.items():
        if not isinstance(pos, dict):
            continue
        cant = safe_float(pos.get("cantidad") or pos.get("unidades") or 0)
        p_ent = safe_float(
            pos.get("precio_entrada")
            or pos.get("precio_compra")
            or pos.get("precio")
            or 0
        )
        p_act = precios_live.get(ticker, p_ent)
        inversion = cant * p_ent

        pnl_flotante = (
            (p_ent - p_act) * cant if es_short else (p_act - p_ent) * cant
        )
        pct_pnl = (
            ((p_ent - p_act) / p_ent * 100)
            if es_short and p_ent > 0
            else (
                ((p_act - p_ent) / p_ent * 100)
                if not es_short and p_ent > 0
                else 0.0
            )
        )

        t_restante = "N/A"
        timestamp = (
            pos.get("timestamp_entrada")
            or pos.get("fecha_entrada")
            or pos.get("fecha")
            or pos.get("timestamp")
        )
        if timestamp:
            try:
                f_ent = datetime.fromisoformat(str(timestamp))
                if f_ent.tzinfo is None:
                    f_ent = tz_madrid.localize(f_ent)
                mins = (ahora - f_ent).total_seconds() / 60
                mins_restantes = max(0, 240 - mins)
                t_restante = f"{int(mins_restantes)} min"
            except Exception:
                pass

        filas.append({
            "Activo": ticker.replace("-USD", ""),
            "Unidades": cant,
            "Entrada (€)": round(p_ent, 8) if p_ent < 0.01 else round(p_ent, 4),
            "Actual (€)": round(p_act, 8) if p_act < 0.01 else round(p_act, 4),
            "Inversión (€)": round(inversion, 2),
            "PnL Flotante (€)": round(pnl_flotante, 2),
            "Rentabilidad (%)": f"{pct_pnl:+.2f}%",
            "⏱️ Time Stop": t_restante,
        })
    return pd.DataFrame(filas)


def mostrar_historial_con_filtros(df_historial, key_prefix):
    if df_historial.empty:
        st.info("Aún no hay operaciones registradas.")
        return

    opciones = [
        "Todo",
        "Hoy",
        "Ayer",
        "Esta semana",
        "La semana pasada",
        "Este mes",
        "El mes pasado",
        "Personalizado",
    ]
    col_filtro, col_totales = st.columns([2, 1])
    seleccion = col_filtro.selectbox(
        "📅 Selecciona el periodo:",
        opciones,
        index=0,
        key=f"sel_{key_prefix}",
    )

    hoy = datetime.now(tz_madrid).date()
    df_filtrado = df_historial.copy()

    if seleccion == "Hoy":
        df_filtrado = df_historial[df_historial["Fecha"].dt.date == hoy]
    elif seleccion == "Ayer":
        df_filtrado = df_historial[
            df_historial["Fecha"].dt.date == (hoy - timedelta(days=1))
        ]
    elif seleccion == "Esta semana":
        df_filtrado = df_historial[
            df_historial["Fecha"].dt.date
            >= (hoy - timedelta(days=hoy.weekday()))
        ]
    elif seleccion == "La semana pasada":
        ini_sp = hoy - timedelta(days=hoy.weekday() + 7)
        df_filtrado = df_historial[
            (df_historial["Fecha"].dt.date >= ini_sp)
            & (df_historial["Fecha"].dt.date <= ini_sp + timedelta(days=6))
        ]
    elif seleccion == "Este mes":
        df_filtrado = df_historial[
            (df_historial["Fecha"].dt.month == hoy.month)
            & (df_historial["Fecha"].dt.year == hoy.year)
        ]
    elif seleccion == "El mes pasado":
        mp = hoy.replace(day=1) - timedelta(days=1)
        df_filtrado = df_historial[
            (df_historial["Fecha"].dt.month == mp.month)
            & (df_historial["Fecha"].dt.year == mp.year)
        ]
    elif seleccion == "Personalizado":
        c1, c2 = st.columns(2)
        f_min = (
            df_historial["Fecha"].min().date()
            if not df_historial.empty
            else hoy
        )
        f_max = (
            df_historial["Fecha"].max().date()
            if not df_historial.empty
            else hoy
        )
        f_inicio = c1.date_input("Desde", f_min, key=f"ini_{key_prefix}")
        f_fin = c2.date_input("Hasta", f_max, key=f"fin_{key_prefix}")
        df_filtrado = df_historial[
            (df_historial["Fecha"].dt.date >= f_inicio)
            & (df_historial["Fecha"].dt.date <= f_fin)
        ]

    total_pnl = (
        safe_float(df_filtrado["PnL (€)"].sum())
        if not df_filtrado.empty
        else 0.0
    )
    ops_cerradas = (
        len(df_filtrado[df_filtrado["PnL (€)"] != 0])
        if not df_filtrado.empty
        else 0
    )
    col_totales.metric(
        f"💰 Beneficio ({seleccion})",
        f"{total_pnl:+.2f} €",
        f"{ops_cerradas} cierres",
    )

    if df_filtrado.empty:
        st.warning("No hay operaciones en este rango de fechas.")
    else:
        df_chart = df_filtrado[df_filtrado["PnL (€)"] != 0]
        if not df_chart.empty:
            pnl_agrupado = (
                df_chart.groupby("Ticker")["PnL (€)"]
                .sum()
                .reset_index()
                .sort_values("PnL (€)", ascending=False)
            )
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=pnl_agrupado["Ticker"],
                        y=pnl_agrupado["PnL (€)"],
                        marker_color=[
                            "#2ecc71" if val > 0 else "#e74c3c"
                            for val in pnl_agrupado["PnL (€)"]
                        ],
                        text=[
                            f"{val:+.2f}€" for val in pnl_agrupado["PnL (€)"]
                        ],
                        textposition="auto",
                    )
                ]
            )
            fig.update_layout(
                title=f"📈 PnL por Crypto ({seleccion})",
                margin=dict(l=0, r=0, t=30, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
            )
            st.plotly_chart(fig, use_container_width=True)

        df_display = df_filtrado.copy()
        df_display["Fecha"] = df_display["Fecha"].dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        st.dataframe(
            df_display.sort_values(by="Fecha", ascending=False),
            use_container_width=True,
            column_config=CONFIG_HISTORIAL,
            hide_index=True,
        )


def color_rsi(val, inverso=False):
    if not isinstance(val, (int, float)):
        return ""
    if inverso:
        if val >= 70:
            return "background-color: #ff4b4b; color: white; font-weight: bold;"
        elif val >= 60:
            return "background-color: #ffa500; color: black; font-weight: bold;"
    else:
        if val <= 25:
            return "background-color: #ff4b4b; color: white; font-weight: bold;"
        elif val <= 32:
            return "background-color: #ffa500; color: black; font-weight: bold;"
    return ""


# ==========================================
# ESTRUCTURA DE PESTAÑAS PRINCIPALES
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "🎯 Bot 1: Francotirador",
    "⚡ Bot 2: Cazador Memecoins",
    "💀 Bot 3: Reaper Short",
])

# ------------------------------------------
# TAB 1: BOT FRANCOTIRADOR
# ------------------------------------------
with tab1:
    cartera = cargar_cartera("cartera.json")
    st.title("🎯 Dashboard Crypto Sniper")
    if cartera:
        efectivo = obtener_campo_num(
            cartera, ["efectivo_disponible", "efectivo", "saldo_disponible"], 0.0
        )
        reserva = obtener_campo_num(
            cartera, ["reserva_intocable", "reserva"], 0.0
        )
        meta_dia = obtener_campo_num(cartera, ["meta_eur_dia"], 5.0)
        posiciones = cartera.get("posiciones_abiertas", {})
        df_hist = parsear_historial(cartera.get("historial_operaciones", []))

        precios_live, _ = obtener_precios_posiciones(
            tuple(posiciones.keys()) if isinstance(posiciones, dict) else ()
        )
        total_live, pnl_hoy = calcular_metricas_live(
            efectivo, posiciones, df_hist, precios_live, es_short=False
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital Activo (Trabajo)", f"{total_live:.2f} €")
        c2.metric("Efectivo Libre", f"{efectivo:.2f} €")
        c3.metric("🏦 Beneficios Asegurados (Reserva)", f"{reserva:.2f} €")
        c4.metric(
            "📈 PnL Hoy (Abiertas + Cerradas)",
            f"{pnl_hoy:+.2f} €",
            f"Meta: {meta_dia:.2f}€",
        )
        st.divider()

        c_t1, c_t2 = st.columns(2)
        c_t1.info(f"⏱️ **Última sincro:** {obtener_sincro(cartera)}")
        c_t2.caption(
            f"🟢 **Estado:** {obtener_estado(cartera, 'Vigilando mercado')}"
        )

        radar = cartera.get("radar_rsi", {})
        if radar and isinstance(radar, dict):
            with st.expander(
                "👁️ Radar Sniper (Sobreventa RSI <= 25)", expanded=True
            ):
                df_radar = pd.DataFrame(
                    list(radar.items()), columns=["Activo", "RSI"]
                ).sort_values(by="RSI", ascending=True)
                st.dataframe(
                    df_radar.style.map(
                        lambda x: color_rsi(x, False), subset=["RSI"]
                    ),
                    use_container_width=False,
                    height=200,
                    column_config=CONFIG_RADAR,
                    hide_index=True,
                )

        st.divider()
        st.subheader("📌 Posiciones Actuales")
        if posiciones and isinstance(posiciones, dict):
            st.dataframe(
                generar_tabla_posiciones(posiciones, precios_live),
                use_container_width=False,
                column_config=CONFIG_POSICIONES,
                hide_index=True,
            )
        else:
            st.info("100% liquidez disponible.")

        st.divider()
        st.subheader("📜 Historial y Gráficos")
        mostrar_historial_con_filtros(df_hist, "sniper")
    else:
        st.warning("Cargando datos de Francotirador...")

# ------------------------------------------
# TAB 2: BOT CAZADOR
# ------------------------------------------
with tab2:
    cartera_c = cargar_cartera("cartera_cazador.json")
    st.title("⚡ Dashboard Bot Cazador")
    if cartera_c:
        efectivo_c = obtener_campo_num(
            cartera_c,
            ["efectivo_disponible", "efectivo", "saldo_disponible"],
            0.0,
        )
        reserva_c = obtener_campo_num(
            cartera_c, ["reserva_intocable", "reserva", "vault_reservado"], 0.0
        )
        posiciones_c = (
            cartera_c.get("posiciones_abiertas")
            or cartera_c.get("posiciones")
            or {}
        )

        raw_hist_c = (
            cartera_c.get("historial_operaciones")
            or cartera_c.get("historial")
            or []
        )
        df_hist_c = parsear_historial(raw_hist_c)

        precios_live_c, _ = obtener_precios_posiciones(
            tuple(posiciones_c.keys()) if isinstance(posiciones_c, dict) else ()
        )
        total_live_c, pnl_hoy_c = calcular_metricas_live(
            efectivo_c, posiciones_c, df_hist_c, precios_live_c, es_short=False
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital Activo (Trabajo)", f"{total_live_c:.2f} €")
        c2.metric("Efectivo Libre", f"{efectivo_c:.2f} €")
        c3.metric("🏦 Beneficios Asegurados (Reserva)", f"{reserva_c:.2f} €")
        c4.metric("📈 PnL Hoy (Abiertas + Cerradas)", f"{pnl_hoy_c:+.2f} €")
        st.divider()

        c_t1, c_t2 = st.columns(2)
        c_t1.info(f"⏱️ **Última sincro:** {obtener_sincro(cartera_c)}")
        c_t2.caption(
            f"🟢 **Estado:** {obtener_estado(cartera_c, 'Buscando oportunidades')}"
        )

        st.divider()
        st.subheader("📌 Posiciones Actuales")
        if posiciones_c and isinstance(posiciones_c, dict):
            st.dataframe(
                generar_tabla_posiciones(posiciones_c, precios_live_c),
                use_container_width=False,
                column_config=CONFIG_POSICIONES,
                hide_index=True,
            )
        else:
            st.info("100% liquidez disponible.")

        st.divider()
        st.subheader("📜 Historial y Gráficos")
        mostrar_historial_con_filtros(df_hist_c, "cazador")
    else:
        st.warning("Cargando datos de Cazador...")

# ------------------------------------------
# TAB 3: BOT REAPER SHORT
# ------------------------------------------
with tab3:
    cartera_r = cargar_cartera("cartera_reaper.json")
    st.title("💀 Dashboard Bot Reaper Short Scalper")
    if cartera_r:
        efectivo_r = obtener_campo_num(
            cartera_r,
            ["efectivo_disponible", "efectivo", "saldo_disponible"],
            100.0,
        )
        reserva_r = obtener_campo_num(
            cartera_r, ["reserva_intocable", "reserva"], 0.0
        )
        meta_dia_r = obtener_campo_num(cartera_r, ["meta_eur_dia"], 5.0)
        posiciones_r = cartera_r.get("posiciones_abiertas", {})
        df_hist_r = parsear_historial(
            cartera_r.get("historial_operaciones", []), es_short=True
        )

        precios_live_r, _ = obtener_precios_posiciones(
            tuple(posiciones_r.keys()) if isinstance(posiciones_r, dict) else ()
        )
        total_live_r, pnl_hoy_r = calcular_metricas_live(
            efectivo_r, posiciones_r, df_hist_r, precios_live_r, es_short=True
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital Activo (Trabajo)", f"{total_live_r:.2f} €")
        c2.metric("Efectivo Libre", f"{efectivo_r:.2f} €")
        c3.metric("🏦 Beneficios Asegurados (Reserva)", f"{reserva_r:.2f} €")
        c4.metric(
            "📈 PnL Hoy (Abiertas + Cerradas)",
            f"{pnl_hoy_r:+.2f} €",
            f"Meta: {meta_dia_r:.2f}€",
        )
        st.divider()

        c_t1, c_t2 = st.columns(2)
        c_t1.info(f"⏱️ **Última sincro:** {obtener_sincro(cartera_r)}")
        c_t2.caption(
            f"🟢 **Estado:** {obtener_estado(cartera_r, 'Escaneando Bull Traps 5m')}"
        )

        radar_r = cartera_r.get("radar_rsi", {})
        if radar_r and isinstance(radar_r, dict):
            with st.expander(
                "👁️ Radar Reaper (Sobrecompra RSI >= 60)", expanded=True
            ):
                df_radar_r = pd.DataFrame(
                    list(radar_r.items()), columns=["Activo", "RSI"]
                )
                df_radar_r = df_radar_r[df_radar_r["RSI"] >= 50].sort_values(
                    by="RSI", ascending=False
                )
                st.dataframe(
                    df_radar_r.style.map(
                        lambda x: color_rsi(x, True), subset=["RSI"]
                    ),
                    use_container_width=False,
                    height=200,
                    column_config=CONFIG_RADAR,
                    hide_index=True,
                )

        st.divider()
        st.subheader("📌 Posiciones Cortas Activas (Shorts)")
        if posiciones_r and isinstance(posiciones_r, dict):
            st.dataframe(
                generar_tabla_posiciones(
                    posiciones_r, precios_live_r, es_short=True
                ),
                use_container_width=False,
                column_config=CONFIG_POSICIONES,
                hide_index=True,
            )
        else:
            st.info("100% liquidez disponible.")

        st.divider()
        st.subheader("📜 Historial y Gráficos")
        mostrar_historial_con_filtros(df_hist_r, "reaper")
    else:
        st.warning("Cargando datos de Reaper...")
