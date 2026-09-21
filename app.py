import base64
from datetime import datetime
import json
import re
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# Configuración de página
st.set_page_config(
    page_title="Crypto Trading Dashboard", page_icon="🎯", layout="wide"
)

# Configuración GitHub (REPOS RUTA EXACTA)
REPO = "administracion996/bot-trading-cryptos"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

# OPTIMIZACIÓN: Precompilación de expresiones regulares para procesar los logs al instante
REGEX_FECHA = re.compile(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]")
REGEX_TICKER = re.compile(r"([A-Z0-9]{2,10}-USD)")
REGEX_VALOR = re.compile(r"(\d+(?:\.\d+)?)\s*€")
REGEX_SCORE = re.compile(r"Score Gemini:\s*(\d+)", re.IGNORECASE)
REGEX_PNL = re.compile(r"PnL:\s*([+-]?\d+(?:\.\d+)?)\s*€")


# --- FUNCIONES OPTIMIZADAS DE CARGA DE DATOS ---
@st.cache_data(ttl=5)
def cargar_cartera(file_path="cartera.json"):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}?v={int(datetime.now().timestamp())}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Cache-Control": "no-cache",
    } if GITHUB_TOKEN else {"Cache-Control": "no-cache"}

    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            content_b64 = res.json()["content"]
            return json.loads(base64.b64decode(content_b64).decode("utf-8"))
    except Exception:
        pass
    return None


@st.cache_data(ttl=60)
def obtener_precios_posiciones(pos_tickers_tuple):
    if not pos_tickers_tuple:
        return {}, 0.92

    precios_live = {}
    tasa_eur = 0.92
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
    for log in historial_raw:
        m_fecha = REGEX_FECHA.search(log)
        if not m_fecha:
            continue
        fecha_dt = datetime.strptime(m_fecha.group(1), "%Y-%m-%d %H:%M:%S")

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

        pnl_eur = 0.0
        m_pnl = REGEX_PNL.search(log)
        if m_pnl:
            pnl_eur = float(m_pnl.group(1))

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
    return pd.DataFrame(registros)


def color_rsi(val):
    if isinstance(val, (int, float)):
        if val <= 25:
            return 'background-color: #ff4b4b; color: white; font-weight: bold;'
        elif val <= 32:
            return 'background-color: #ffa500; color: black; font-weight: bold;'
    return ''


def color_rsi_short(val):
    if isinstance(val, (int, float)):
        if val >= 70:
            return 'background-color: #ff4b4b; color: white; font-weight: bold;'
        elif val >= 60:
            return 'background-color: #ffa500; color: black; font-weight: bold;'
    return ''


# ==========================================
# ESTRUCTURA DE PESTAÑAS (3 BOTS)
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
    st.title("🎯 Dashboard Crypto Sniper & Vault")

    if cartera:
        efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
        total_activo = round(float(cartera.get("total_cartera", 0.0)), 2)
        reserva = round(float(cartera.get("reserva_intocable", 0.0)), 2)
        meta_dia = round(float(cartera.get("meta_eur_dia", 0.0)), 2)

        posiciones = cartera.get("posiciones_abiertas", {})
        historial_raw = cartera.get("historial_operaciones", [])
        telemetria = cartera.get("telemetria", {})
        radar_rsi = cartera.get("radar_rsi", {})

        df_historial_completo = parsear_historial(historial_raw)

        ahora = datetime.now()
        hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

        pnl_realizado_hoy = 0.0
        if not df_historial_completo.empty:
            df_ventas_hoy = df_historial_completo[
                (df_historial_completo["Fecha"] >= hoy_inicio)
                & (df_historial_completo["Tipo"].str.contains("VENTA"))
            ]
            pnl_realizado_hoy = float(df_ventas_hoy["PnL (€)"].sum())

        pnl_flotante_posiciones = 0.0
        if posiciones:
            pos_tickers_tuple = tuple(posiciones.keys())
            precios_live, _ = obtener_precios_posiciones(pos_tickers_tuple)
            for t, pos in posiciones.items():
                p_ent = float(pos.get("precio_entrada", 0))
                p_act = precios_live.get(t, p_ent)
                cant = float(pos.get("cantidad", 0))
                pnl_flotante_posiciones += (p_act - p_ent) * cant

        pnl_hoy_total = round(pnl_realizado_hoy + pnl_flotante_posiciones, 2)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital Activo (Trabajo)", f"{total_activo:.2f} €")
        col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
        col3.metric("🏦 Reserva Intocable", f"{reserva:.2f} €")
        col4.metric(
            "🎯 Progreso Meta (+5%)", f"{pnl_hoy_total:+.2f} € / {meta_dia:.2f} €"
        )

        st.divider()

        st.subheader("📡 Telemetría y Radar")
        c_tel1, c_tel2 = st.columns(2)
        c_tel1.info(
            "⏱️ **Última actualización:**"
            f" {telemetria.get('ultima_actualizacion', 'N/A')}"
        )
        c_tel2.caption(
            f"🟢 **Estado:** {telemetria.get('estado', 'Vigilando Scalping 5m')}"
        )

        if radar_rsi:
            with st.expander("👁️ Radar Sniper (Sobreventa RSI)", expanded=True):
                df_radar = pd.DataFrame(
                    list(radar_rsi.items()), columns=["Activo", "RSI"]
                )
                df_radar = df_radar.sort_values(
                    by="RSI", ascending=True
                ).reset_index(drop=True)
                st.dataframe(
                    df_radar.style.map(color_rsi, subset=["RSI"]),
                    use_container_width=True,
                    height=200,
                )

        st.divider()

        st.subheader("📌 Posiciones Actuales en Cartera")
        if posiciones:
            filas_pos = []
            for ticker, pos in posiciones.items():
                cant = float(pos.get("cantidad", 0))
                p_ent = float(pos.get("precio_entrada", 0))
                p_act = precios_live.get(ticker, p_ent)
                tot_comprado = round(cant * p_ent, 2)
                tot_actual = round(cant * p_act, 2)
                pct_pnl = ((p_act - p_ent) / p_ent * 100) if p_ent > 0 else 0.0

                filas_pos.append({
                    "Activo": ticker.replace("-USD", ""),
                    "Cantidad": cant,
                    "Precio Entrada (€)": round(p_ent, 4),
                    "Precio Actual (€)": round(p_act, 4),
                    "PnL Flotante (€)": round(tot_actual - tot_comprado, 2),
                    "Porcentaje PnL (%)": f"{pct_pnl:+.2f}%",
                })
            st.dataframe(pd.DataFrame(filas_pos), use_container_width=True)
        else:
            st.info("No hay posiciones abiertas (100% liquidez).")

        st.divider()
        st.subheader("📜 Historial de Operaciones")
        if not df_historial_completo.empty:
            st.dataframe(
                df_historial_completo.sort_values(
                    by="Fecha", ascending=False
                ),
                use_container_width=True,
            )
    else:
        st.warning("Cargando datos de Francotirador...")

# ------------------------------------------
# TAB 2: BOT CAZADOR DE MEMECOINS
# ------------------------------------------
with tab2:
    cartera_c = cargar_cartera("cartera_cazador.json")
    st.title("⚡ Dashboard Bot Cazador de Memecoins")
    if cartera_c:
        efectivo_c = round(float(cartera_c.get("efectivo_disponible", 0.0)), 2)
        posiciones_c = cartera_c.get("posiciones", {})
        historial_c = cartera_c.get("historial", [])

        st.subheader("📊 Estado Global de la Cuenta")
        col1, col2 = st.columns(2)
        col1.metric("Liquidez Disponible", f"{efectivo_c:.2f} €")
        col2.metric("Posiciones Abiertas", len(posiciones_c))

        st.divider()
        st.subheader("📜 Historial de Caza")
        if historial_c:
            st.dataframe(pd.DataFrame(historial_c), use_container_width=True)
        else:
            st.info("Aún no hay presas cazadas.")
    else:
        st.warning("Cargando datos de Cazador...")

# ------------------------------------------
# TAB 3: BOT REAPER SHORT SCALPER
# ------------------------------------------
with tab3:
    cartera_r = cargar_cartera("cartera_reaper.json")
    st.title("💀 Dashboard Bot Reaper Short Scalper")
    st.caption(
        "Estrategia Inversa (Fade the Breakout): Gana dinero cuando el precio"
        " de la cripto cae."
    )

    if cartera_r:
        efectivo_r = round(float(cartera_r.get("efectivo_disponible", 0.0)), 2)
        total_r = round(float(cartera_r.get("total_cartera", 0.0)), 2)
        reserva_r = round(float(cartera_r.get("reserva_intocable", 0.0)), 2)
        posiciones_r = cartera_r.get("posiciones_abiertas", {})
        historial_r_raw = cartera_r.get("historial_operaciones", [])
        telemetria_r = cartera_r.get("telemetria", {})
        radar_r = cartera_r.get("radar_rsi", {})

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital Trabajo (Short)", f"{total_r:.2f} €")
        col2.metric("Liquidez Libre", f"{efectivo_r:.2f} €")
        col3.metric("🏦 Reserva Intocable", f"{reserva_r:.2f} €")
        col4.metric("Shorts Activos", len(posiciones_r))

        st.divider()

        st.subheader("📡 Telemetría y Radar de Agotamiento (Bull Traps)")
        t1, t2 = st.columns(2)
        t1.info(
            "⏱️ **Última sincro:**"
            f" {telemetria_r.get('ultima_actualizacion', 'N/A')}"
        )
        t2.caption(
            "🟢 **Estado Bot:**"
            f" {telemetria_r.get('estado', 'Escaneando sobrecompra 5m')}"
        )

        if radar_r:
            with st.expander("👁️ Radar Reaper (Sobrecompra RSI)", expanded=True):
                df_radar_r = pd.DataFrame(
                    list(radar_r.items()), columns=["Activo", "RSI"]
                )
                df_radar_r = df_radar_r.sort_values(
                    by="RSI", ascending=False
                ).reset_index(drop=True)
                st.dataframe(
                    df_radar_r.style.map(color_rsi_short, subset=["RSI"]),
                    use_container_width=True,
                    height=200,
                )

        st.divider()

        st.subheader("📌 Posiciones Cortas Activas (Shorts)")
        if posiciones_r:
            pos_tickers_tuple_r = tuple(posiciones_r.keys())
            precios_live_r, _ = obtener_precios_posiciones(pos_tickers_tuple_r)

            filas_r = []
            for ticker, pos in posiciones_r.items():
                cant = float(pos.get("cantidad", 0))
                p_ent = float(pos.get("precio_entrada", 0))
                p_act = precios_live_r.get(ticker, p_ent)

                inversion_ini = cant * p_ent
                pnl_eur_short = (p_ent - p_act) * cant
                pct_pnl_short = (
                    ((p_ent - p_act) / p_ent * 100) if p_ent > 0 else 0.0
                )

                filas_r.append({
                    "Activo": ticker.replace("-USD", ""),
                    "Unidades": cant,
                    "Entrada (€)": round(p_ent, 4),
                    "Actual (€)": round(p_act, 4),
                    "Inversión (€)": round(inversion_ini, 2),
                    "PnL Flotante (€)": round(pnl_eur_short, 2),
                    "Porcentaje PnL (%)": f"{pct_pnl_short:+.2f}%",
                    "Tipo": pos.get("tipo", "SHORT"),
                })

            st.dataframe(pd.DataFrame(filas_r), use_container_width=True)
        else:
            st.info(
                "Sin posiciones cortas abiertas en este momento. Esperando"
                " trampas alcistas..."
            )

        st.divider()

        st.subheader("📜 Historial de Operaciones Short")
        df_hist_r = parsear_historial(historial_r_raw, es_short=True)
        if not df_hist_r.empty:
            st.dataframe(
                df_hist_r.sort_values(by="Fecha", ascending=False),
                use_container_width=True,
            )
        else:
            st.info("Aún no hay historial de posiciones cortas cerradas.")
    else:
        st.warning("Recuperando datos de cartera_reaper.json...")
