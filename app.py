import base64
from datetime import datetime, timedelta
import json
import re
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Configuración de página
st.set_page_config(
    page_title="Crypto Trading Dashboard", page_icon="🎯", layout="wide"
)

# Configuración GitHub
REPO = "administracion996/bot-trading-dashboard"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

UNIVERSO_MERCADO = (
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
    "DOT-USD", "NEAR-USD", "ATOM-USD", "MATIC-USD", "LTC-USD", "BCH-USD", "ETC-USD",
    "LINK-USD", "AAVE-USD", "INJ-USD", "FET-USD", "ALGO-USD", "XLM-USD", "TRX-USD",
    "DOGE-USD", "SHIB-USD", "BONK-USD", "FLOKI-USD", "FIL-USD", "ICP-USD",
)

# --- DESCARGA ANTI-CACHÉ EN TIEMPO REAL POR BASE64 ---
@st.cache_data(ttl=5)
def cargar_cartera(file_path="cartera.json"):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}?v={int(datetime.now().timestamp())}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Cache-Control": "no-cache"
    } if GITHUB_TOKEN else {"Cache-Control": "no-cache"}
    
    try:
        res = requests.get(url, headers=headers)
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
                if len(pos_tickers_tuple) == 1:
                    val = float(df_live.dropna().iloc[-1])
                else:
                    val = float(df_live[t].dropna().iloc[-1])
                precios_live[t] = val * tasa_eur
            except Exception:
                pass
    except Exception:
        pass

    return precios_live, tasa_eur

def calcular_rsi_serie(df_close, period=14):
    delta = df_close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=60)
def obtener_rsi_historico(tickers_tuple, periodo="5d"):
    if not tickers_tuple:
        return pd.DataFrame()
    try:
        intervalo = "5m" if periodo in ["1d", "5d"] else "1h"
        periodo_dl = "5d" if periodo in ["1d", "5d"] else "1mo"
        
        df = yf.download(
            list(tickers_tuple), period=periodo_dl, interval=intervalo, progress=False
        )
        if df.empty:
            return pd.DataFrame()
          
        if "Close" in df:
            df_close = df["Close"]
        else:
            df_close = df

        if isinstance(df_close, pd.Series):
            df_close = df_close.to_frame(name=tickers_tuple[0])
        
        df_rsi = pd.DataFrame(index=df_close.index)
        for col in df_close.columns:
            df_rsi[col] = calcular_rsi_serie(df_close[col])
        
        df_rsi = df_rsi.dropna(how="all")

        if periodo == "1d":
            df_rsi = df_rsi.tail(288)   # 24h x 12 velas de 5m = 288 velas
        elif periodo == "5d":
            df_rsi = df_rsi.tail(1440)  # 5d x 288 velas = 1440 velas

        return df_rsi
    except Exception:
        return pd.DataFrame()

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
            else ("EUR" if "BARRIDO" in log else "DESCONOCIDO")
        )

        val_matches = re.findall(r"(\d+(?:\.\d+)?)\s*€", log)
        valor = float(val_matches[-1]) if val_matches else 0.0

        # Intentar extraer puntuación de Gemini si existe en el log
        match_score = re.search(r"(?:Confianza|Score|Gemini):\s*(\d+)", log, re.IGNORECASE)
        score_gemini = int(match_score.group(1)) if match_score else None

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
                "Score_Gemini": score_gemini,
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
                "Score_Gemini": score_gemini,
                "Log": log,
            })

        elif "BARRIDO" in log:
            registros.append({
                "Fecha": fecha_dt,
                "Tipo": "BARRIDO 🏦",
                "Ticker": ticker,
                "Valor (€)": valor,
                "PnL (€)": 0.0,
                "Score_Gemini": None,
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

# --- PESTAÑAS DEL DASHBOARD ---
tab1, tab2 = st.tabs(["🎯 Bot 1: Francotirador", "⚡ Bot 2: Cazador Memecoins"])

# ==========================================
# TAB 1: BOT FRANCOTIRADOR
# ==========================================
with tab1:
    cartera = cargar_cartera("cartera.json")
    st.title("🎯 Dashboard Crypto Sniper & Vault")

    if cartera:
        efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
        total_activo = round(float(cartera.get("total_cartera", 0.0)), 2)
        reserva = round(float(cartera.get("reserva_intocable", 0.0)), 2)
        
        meta_dia = round(float(cartera.get("meta_eur_dia", 0.0)), 2)
        barrido = cartera.get("barrido_realizado", False)
        
        posiciones = cartera.get("posiciones_abiertas", {})
        historial_raw = cartera.get("historial_operaciones", [])
        telemetria = cartera.get("telemetria", {})
        radar_rsi = cartera.get("radar_rsi", {})

        df_historial_completo = parsear_historial(historial_raw)

        # --- CÁLCULO UNIFICADO DE PNL HOY ---
        ahora = datetime.now()
        hoy_inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        
        pnl_realizado_hoy = 0.0
        if not df_historial_completo.empty:
            df_ventas_hoy = df_historial_completo[
                (df_historial_completo["Fecha"] >= hoy_inicio) & 
                (df_historial_completo["Tipo"].str.contains("VENTA"))
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

        # 1. MÉTRICAS GLOBALES
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital Activo (Trabajo)", f"{total_activo:.2f} €")
        col2.metric("Efectivo Libre", f"{efectivo:.2f} €")
        col3.metric("🏦 Reserva Intocable", f"{reserva:.2f} €")
        
        if barrido:
            col4.metric("🎯 Progreso Diario", "✅ Conseguido")
        else:
            if meta_dia > 0:
                col4.metric("🎯 Progreso Meta (+5%)", f"{pnl_hoy_total:+.2f} € / {meta_dia:.2f} €")
            else:
                col4.metric("🎯 Progreso Meta (+5%)", "Esperando cierre...")

        st.divider()

        # 2. TELEMETRÍA Y ESTADO DE CONSOLA
        st.subheader("📡 Telemetría y Estado de Consola")
        hora_ultimo_escaneo = telemetria.get("ultima_actualizacion", "N/A")
        
        if hora_ultimo_escaneo == "N/A" and historial_raw:
            ultimo_log = historial_raw[-1]
            match_hora_log = re.search(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]", ultimo_log)
            if match_hora_log:
                hora_ultimo_escaneo = match_hora_log.group(1)
        
        restante_barrido = round(max(0.0, meta_dia - pnl_hoy_total), 2) if not barrido else 0.0

        t1, t2, t3 = st.columns(3)
        t1.info(f"⏱️ **Último escaneo sincronizado:** {hora_ultimo_escaneo}")
        if barrido:
            t2.success("🏦 **Estado Hucha:** ¡Barrido diario completado!")
        else:
            t2.warning(f"📊 **Beneficio hoy:** {pnl_hoy_total:+.2f} € | **Falta para barrido:** {restante_barrido:.2f} €")
        t3.caption(f"🟢 **Estado Bot:** {telemetria.get('estado', 'Vigilando Scalping 5m')}")

        # RADAR INSTANTÁNEO
        if radar_rsi:
            st.write("")
            with st.expander("👁️ Radar Sniper (Niveles RSI actuales 5m)", expanded=True):
                df_radar = pd.DataFrame(list(radar_rsi.items()), columns=["Activo", "RSI"])
                df_radar = df_radar.sort_values(by="RSI", ascending=True).reset_index(drop=True)
                st.dataframe(
                    df_radar.style.map(color_rsi, subset=['RSI']),
                    use_container_width=True, 
                    height=200
                )
                st.caption("🔴 Rojo: Zona de compra (RSI <= 25) | 🟠 Naranja: Acercándose (RSI <= 32)")

        st.divider()

        # 3. EVOLUCIÓN HISTÓRICA DEL RSI
        st.subheader("📉 Evolución Histórica del RSI (5 Minutos)")
        
        c_rsi1, c_rsi2 = st.columns([6, 2])
        with c_rsi1:
            sel_rsi_cryptos = st.multiselect(
                "🪙 Criptomonedas a analizar:",
                options=list(UNIVERSO_MERCADO),
                default=["ETH-USD", "XLM-USD", "TRX-USD", "ICP-USD"],
                key="filtro_rsi_historico"
            )
        with c_rsi2:
            periodo_rsi = st.selectbox(
                "📅 Rango de tiempo:",
                options=["1d", "5d", "1mo"],
                index=0,
                key="periodo_rsi"
            )

        if sel_rsi_cryptos:
            df_rsi_hist = obtener_rsi_historico(tuple(sel_rsi_cryptos), periodo=periodo_rsi)
            if not df_rsi_hist.empty:
                fig_rsi = go.Figure()
                for col in df_rsi_hist.columns:
                    fig_rsi.add_trace(
                        go.Scatter(
                            x=df_rsi_hist.index,
                            y=df_rsi_hist[col],
                            mode="lines",
                            name=str(col).replace("-USD", ""),
                        )
                    )
                
                fig_rsi.add_hline(
                    y=25, line_dash="dash", line_color="#EF553B", 
                    annotation_text="🎯 Gatillo Sniper (25)", annotation_position="bottom right"
                )
                fig_rsi.add_hline(
                    y=30, line_dash="dot", line_color="#FFA500", 
                    annotation_text="Sobreventa (30)", annotation_position="top right"
                )

                fig_rsi.update_layout(
                    xaxis_title="Fecha / Hora",
                    yaxis_title="Índice RSI (5m)",
                    yaxis=dict(range=[10, 90]),
                    hovermode="x unified",
                    template="plotly_dark",
                    margin=dict(l=20, r=20, t=30, b=20),
                )
                st.plotly_chart(fig_rsi, use_container_width=True)
            else:
                st.caption("Sin datos para las criptomonedas seleccionadas.")

        st.divider()

        # 4. TABLA DE POSICIONES DETALLADA
        st.subheader("📌 Posiciones Actuales en Cartera")
        if posiciones:
            pos_tickers_tuple = tuple(posiciones.keys())
            precios_live, _ = obtener_precios_posiciones(pos_tickers_tuple)
            ahora_dt = datetime.now()

            filas_pos = []
            for ticker, pos in posiciones.items():
                cant = float(pos.get("cantidad", 0))
                p_ent = float(pos.get("precio_entrada", 0))
                p_act = precios_live.get(ticker, p_ent)

                tot_comprado = round(cant * p_ent, 2)
                tot_actual = round(cant * p_act, 2)
                diferencia = round(tot_actual - tot_comprado, 2)
                pct_pnl = ((p_act - p_ent) / p_ent * 100) if p_ent > 0 else 0.0

                f_ent_str = pos.get("timestamp_entrada", "")
                tiempo_str = "N/A"
                if f_ent_str:
                    try:
                        f_ent = datetime.strptime(f_ent_str, "%Y-%m-%d %H:%M:%S")
                        mins = round((ahora_dt - f_ent).total_seconds() / 60, 1)
                        tiempo_str = f"{mins}m / 240m"
                    except Exception:
                        pass

                rsi_actual = radar_rsi.get(ticker, "N/A")

                filas_pos.append({
                    "Activo": ticker.replace("-USD", ""),
                    "Cantidad": cant,
                    "Precio Entrada (€)": round(p_ent, 4),
                    "Precio Total Comprado (€)": tot_comprado,
                    "Precio Actual (€)": round(p_act, 4),
                    "Precio Total Actual (€)": tot_actual,
                    "Diferencia (€)": diferencia,
                    "Porcentaje PnL (%)": f"{pct_pnl:+.2f}%",
                    "RSI Actual": rsi_actual,
                    "Tiempo en Cartera": tiempo_str,
                })

            st.dataframe(pd.DataFrame(filas_pos), use_container_width=True)
        else:
            st.info("No hay posiciones abiertas actualmente (100% liquidez).")

        st.divider()

        # 5. MÓDULO DE ANALÍTICA CUANTITATIVA AVANZADA
        st.subheader("📊 Analítica Avanzada Quant (Bot Francotirador)")
        if not df_historial_completo.empty:
            df_ventas = df_historial_completo[df_historial_completo["Tipo"].str.contains("VENTA")].copy()
            if not df_ventas.empty:
                total_ops = len(df_ventas)
                ganadoras = df_ventas[df_ventas["PnL (€)"] > 0]
                perdedoras = df_ventas[df_ventas["PnL (€)"] < 0]

                n_wins = len(ganadoras)
                n_losses = len(perdedoras)
                win_rate = (n_wins / total_ops * 100) if total_ops > 0 else 0.0

                avg_win = ganadoras["PnL (€)"].mean() if n_wins > 0 else 0.0
                avg_loss = perdedoras["PnL (€)"].mean() if n_losses > 0 else 0.0

                sum_wins = ganadoras["PnL (€)"].sum()
                sum_losses = abs(perdedoras["PnL (€)"].sum())
                profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else (sum_wins if sum_wins > 0 else 0.0)

                # Drawdown Máximo
                df_ventas_sorted = df_ventas.sort_values(by="Fecha").copy()
                df_ventas_sorted["PnL_Acumulado"] = df_ventas_sorted["PnL (€)"].cumsum()
                df_ventas_sorted["Peak"] = df_ventas_sorted["PnL_Acumulado"].cummax()
                df_ventas_sorted["Drawdown"] = df_ventas_sorted["PnL_Acumulado"] - df_ventas_sorted["Peak"]
                max_dd = df_ventas_sorted["Drawdown"].min() if not df_ventas_sorted.empty else 0.0

                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Nº Operaciones", total_ops)
                m2.metric("% Ganadoras", f"{win_rate:.1f}%")
                m3.metric("Ganancia Media", f"{avg_win:+.2f} €")
                m4.metric("Pérdida Media", f"{avg_loss:+.2f} €")
                m5.metric("Profit Factor", f"{profit_factor:.2f}")
                m6.metric("Max Drawdown", f"{max_dd:.2f} €")

                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.caption("📌 PnL Acumulado por Activo (€)")
                    pnl_activo = df_ventas.groupby("Ticker")["PnL (€)"].sum().sort_values(ascending=False)
                    st.bar_chart(pnl_activo)

                with col_g2:
                    st.caption("🧠 Rendimiento por Puntuación Gemini")
                    if df_ventas["Score_Gemini"].notnull().any():
                        pnl_gemini = df_ventas.dropna(subset=["Score_Gemini"]).groupby("Score_Gemini")["PnL (€)"].sum()
                        st.bar_chart(pnl_gemini)
                    else:
                        st.info("No hay datos de puntuación Gemini registrados en los logs del historial.")
            else:
                st.info("Aún no hay ventas registradas para calcular analíticas cuant de rendimiento.")
        else:
            st.info("Aún no hay historial de operaciones disponible.")

        st.divider()

        # 6. HISTORIAL DE OPERACIONES
        st.subheader("📜 Historial de Operaciones y Movimientos")

        c1, c2 = st.columns([3, 3])
        with c1:
            opciones_fecha_h = [
                "Todo", "Hoy", "Ayer", "Esta semana", "Semana pasada", "Personalizado",
            ]
            sel_fecha_h = st.selectbox(
                "📅 Filtro de Fecha (Historial)",
                opciones_fecha_h,
                key="f_fecha_historial",
            )

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
        col_m1.metric("💰 PnL Realizado en Rango (Trading)", f"{pnl_acumulado:+.2f} €")
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

    else:
        st.warning("Recuperando datos desde GitHub (cartera.json)...")

# ==========================================
# TAB 2: BOT CAZADOR DE MEMECOINS
# ==========================================
with tab2:
    cartera_c = cargar_cartera("cartera_cazador.json")
    st.title("⚡ Dashboard Bot Cazador de Memecoins & Vault")

    if cartera_c:
        efectivo_c = round(float(cartera_c.get("efectivo_disponible", 0.0)), 2)
        posiciones_c = cartera_c.get("posiciones", {})
        historial_c = cartera_c.get("historial", [])
        vault_c = round(float(cartera_c.get("vault_reservado", 0.0)), 2)
        meta_dia_c = round(float(cartera_c.get("meta_eur_dia", 0.0)), 2)
        barrido_c = cartera_c.get("barrido_realizado", False)

        coste_pos_c = sum(float(p.get("coste_total", 0.0)) for p in posiciones_c.values())
        capital_trabajo_c = round(efectivo_c + coste_pos_c, 2)

        # Beneficio cerrado hoy
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        pnl_cerrado_c_hoy = sum(
            float(h.get("beneficio_neto", 0.0)) 
            for h in historial_c 
            if str(h.get("fecha_salida", "")).startswith(hoy_str)
        )

        # 1. MÉTRICAS GLOBALES CAZADOR
        st.subheader("📊 Estado Global de la Cuenta")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Capital de Trabajo", f"{capital_trabajo_c:.2f} €")
        col2.metric("Liquidez Disponible", f"{efectivo_c:.2f} €")
        col3.metric("🏦 The Vault (Reserva)", f"{vault_c:.2f} €")
        col4.metric("Posiciones Abiertas", len(posiciones_c))

        st.divider()

        # 2. PROGRESO Y VAULT
        st.subheader("🏦 Progreso Diario & The Vault")
        vc1, vc2, vc3 = st.columns(3)
        vc1.metric("Meta del Día (5%)", f"{meta_dia_c:.2f} €")
        vc2.metric("Beneficio Cerrado Hoy", f"{pnl_cerrado_c_hoy:+.2f} €")

        if barrido_c:
            vc3.success("✅ Barrido completado hoy. Beneficios asegurados en The Vault.")
        else:
            restante_c = max(0.0, meta_dia_c - pnl_cerrado_c_hoy)
            vc3.info(f"Faltan {restante_c:.2f} € cerrados para activar el barrido.")

        st.divider()

        # 3. POSICIONES ACTIVAS CAZADOR
        st.subheader("📌 Posiciones Activas")
        if posiciones_c:
            filas_c = []
            ahora_dt = datetime.now()
            for ticker, pos in posiciones_c.items():
                unidades = float(pos.get("unidades", 0))
                p_compra = float(pos.get("precio_compra", 0))
                coste = float(pos.get("coste_total", 0))
                max_p = float(pos.get("max_precio_alcanzado", p_compra))
                score_ia = pos.get("confianza_gemini", "N/A")
                
                f_ent_str = pos.get("fecha_entrada", "")
                tiempo_str = "N/A"
                if f_ent_str:
                    try:
                        f_ent = datetime.fromisoformat(f_ent_str)
                        mins = round((ahora_dt - f_ent.replace(tzinfo=None)).total_seconds() / 60, 1)
                        tiempo_str = f"{mins}m / 120m"
                    except Exception:
                        pass

                filas_c.append({
                    "Activo": ticker,
                    "Unidades": unidades,
                    "Precio Compra (€)": f"{p_compra:.8f} €",
                    "Inversión (€)": f"{coste:.2f} €",
                    "Máx Alcanzado (€)": f"{max_p:.8f} €",
                    "Score IA": score_ia,
                    "Tiempo Transcurrido": tiempo_str
                })
            st.dataframe(pd.DataFrame(filas_c), use_container_width=True)
        else:
            st.info("Sin posiciones abiertas en este momento.")

        st.divider()

        # 4. ANALÍTICA CUANT CAZADOR
        st.subheader("📊 Analítica Avanzada Quant (Bot Cazador)")
        if historial_c:
            df_hist_c = pd.DataFrame(historial_c)
            if not df_hist_c.empty:
                # Normalizar columna de PnL
                if "beneficio_neto" in df_hist_c.columns:
                    df_hist_c["pnl_val"] = df_hist_c["beneficio_neto"].astype(float)
                elif "pnl_eur" in df_hist_c.columns:
                    df_hist_c["pnl_val"] = df_hist_c["pnl_eur"].astype(float)
                else:
                    df_hist_c["pnl_val"] = 0.0

                n_ops_c = len(df_hist_c)
                wins_c = df_hist_c[df_hist_c["pnl_val"] > 0]
                losses_c = df_hist_c[df_hist_c["pnl_val"] < 0]

                win_rate_c = (len(wins_c) / n_ops_c * 100) if n_ops_c > 0 else 0.0
                avg_win_c = wins_c["pnl_val"].mean() if len(wins_c) > 0 else 0.0
                avg_loss_c = losses_c["pnl_val"].mean() if len(losses_c) > 0 else 0.0

                tot_win_c = wins_c["pnl_val"].sum()
                tot_loss_c = abs(losses_c["pnl_val"].sum())
                pf_c = (tot_win_c / tot_loss_c) if tot_loss_c > 0 else (tot_win_c if tot_win_c > 0 else 0.0)

                # Max Drawdown
                df_hist_c["pnl_acum"] = df_hist_c["pnl_val"].cumsum()
                df_hist_c["peak"] = df_hist_c["pnl_acum"].cummax()
                df_hist_c["dd"] = df_hist_c["pnl_acum"] - df_hist_c["peak"]
                max_dd_c = df_hist_c["dd"].min() if not df_hist_c.empty else 0.0

                mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
                mc1.metric("Nº Operaciones", n_ops_c)
                mc2.metric("% Ganadoras", f"{win_rate_c:.1f}%")
                mc3.metric("Ganancia Media", f"{avg_win_c:+.2f} €")
                mc4.metric("Pérdida Media", f"{avg_loss_c:+.2f} €")
                mc5.metric("Profit Factor", f"{pf_c:.2f}")
                mc6.metric("Max Drawdown", f"{max_dd_c:.2f} €")

                col_cg1, col_cg2 = st.columns(2)
                with col_cg1:
                    st.caption("📌 PnL Acumulado por Memecoin (€)")
                    if "ticker" in df_hist_c.columns:
                        pnl_c_activo = df_hist_c.groupby("ticker")["pnl_val"].sum().sort_values(ascending=False)
                        st.bar_chart(pnl_c_activo)
                    elif "activo" in df_hist_c.columns:
                        pnl_c_activo = df_hist_c.groupby("activo")["pnl_val"].sum().sort_values(ascending=False)
                        st.bar_chart(pnl_c_activo)

                with col_cg2:
                    st.caption("🧠 Rendimiento por Puntuación Gemini")
                    if "confianza_gemini" in df_hist_c.columns:
                        pnl_c_gemini = df_hist_c.groupby("confianza_gemini")["pnl_val"].sum()
                        st.bar_chart(pnl_c_gemini)
                    else:
                        st.info("Sin datos de confianza Gemini en el historial estructurado.")

        st.divider()

        # 5. HISTORIAL DE CAZA
        st.subheader("📜 Historial de Caza")
        if historial_c:
            df_hist_c_tabla = pd.DataFrame(historial_c)
            if not df_hist_c_tabla.empty and "fecha_salida" in df_hist_c_tabla.columns:
                df_hist_c_tabla = df_hist_c_tabla.sort_values(by="fecha_salida", ascending=False)
            st.dataframe(df_hist_c_tabla, use_container_width=True)
        else:
            st.info("No hay presas cazadas todavía.")

    else:
        st.warning("Recuperando datos desde GitHub (cartera_cazador.json)...")
