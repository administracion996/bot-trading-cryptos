import base64
from datetime import datetime, timedelta
import json
import re
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Crypto Trading Dashboard", page_icon="🎯", layout="wide")

REPO = "administracion996/bot-trading-dashboard"
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

UNIVERSO_MERCADO = (
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
    "DOT-USD", "NEAR-USD", "ATOM-USD", "MATIC-USD", "LTC-USD", "BCH-USD", "ETC-USD",
    "LINK-USD", "AAVE-USD", "INJ-USD", "FET-USD", "ALGO-USD", "XLM-USD", "TRX-USD",
    "DOGE-USD", "SHIB-USD", "BONK-USD", "FLOKI-USD", "FIL-USD", "ICP-USD"
)

@st.cache_data(ttl=5)
def cargar_cartera(file_path="cartera.json"):
    url = f"https://api.github.com/repos/{REPO}/contents/{file_path}?v={int(datetime.now().timestamp())}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"} if GITHUB_TOKEN else {"Cache-Control": "no-cache"}
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
    for log in historial_raw:
        match_fecha = re.search(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]", log)
        if not match_fecha:
            continue
        fecha_dt = datetime.strptime(match_fecha.group(1), "%Y-%m-%d %H:%M:%S")

        match_ticker = re.search(r"([A-Z0-9]{2,10}-USD)", log)
        ticker = match_ticker.group(1).replace("-USD", "") if match_ticker else ("EUR" if "BARRIDO" in log else "DESCONOCIDO")

        val_matches = re.findall(r"(\d+(?:\.\d+)?)\s*€", log)
        valor = float(val_matches[-1]) if val_matches else 0.0

        # Extracción de la nota de Gemini directamente desde los logs formateados
        match_score = re.search(r"Score Gemini:\s*(\d+)", log, re.IGNORECASE)
        score_gemini = int(match_score.group(1)) if match_score else None

        if "COMPRA" in log:
            registros.append({
                "Fecha": fecha_dt, "Tipo": "COMPRA 🟢", "Ticker": ticker,
                "Valor (€)": valor, "PnL (€)": 0.0, "Score_Gemini": score_gemini, "Log": log
            })
        elif "VENTA" in log or "Vendido" in log:
            pnl_eur = 0.0
            match_pnl = re.search(r"PnL:\s*([+-]?\d+(?:\.\d+)?)\s*€", log)
            if match_pnl:
                pnl_eur = float(match_pnl.group(1))

            registros.append({
                "Fecha": fecha_dt, "Tipo": "VENTA 🔴", "Ticker": ticker,
                "Valor (€)": valor, "PnL (€)": round(pnl_eur, 2), "Score_Gemini": score_gemini, "Log": log
            })

    return pd.DataFrame(registros)

tab1, tab2 = st.tabs(["🎯 Bot 1: Francotirador", "⚡ Bot 2: Cazador Memecoins"])

with tab1:
    cartera = cargar_cartera("cartera.json")
    st.title("🎯 Dashboard Crypto Sniper & Vault")

    if cartera:
        efectivo = round(float(cartera.get("efectivo_disponible", 0.0)), 2)
        posiciones = cartera.get("posiciones_abiertas", {})
        historial_raw = cartera.get("historial_operaciones", [])
        radar_rsi = cartera.get("radar_rsi", {})
        
        df_historial_completo = parsear_historial(historial_raw)

        # 1. MÉTRICAS Y CABECERA
        st.subheader("📊 Resumen Operativo")
        c1, c2, c3 = st.columns(3)
        c1.metric("Efectivo Libre", f"{efectivo:.2f} €")
        c2.metric("Posiciones Abiertas", len(posiciones))
        c3.metric("Última Sincronización", cartera.get("telemetria", {}).get("ultima_actualizacion", "N/A"))

        st.divider()

        # 2. ANALÍTICA QUANT Y FILTRO GEMINI
        st.subheader("📊 Analítica Avanzada Quant")
        if not df_historial_completo.empty:
            df_ventas = df_historial_completo[df_historial_completo["Tipo"].str.contains("VENTA")].copy()
            if not df_ventas.empty:
                total_ops = len(df_ventas)
                ganadoras = df_ventas[df_ventas["PnL (€)"] > 0]
                perdedoras = df_ventas[df_ventas["PnL (€)"] < 0]

                win_rate = (len(ganadoras) / total_ops * 100) if total_ops > 0 else 0.0
                avg_win = ganadoras["PnL (€)"].mean() if len(ganadoras) > 0 else 0.0
                avg_loss = perdedoras["PnL (€)"].mean() if len(perdedoras) > 0 else 0.0

                sum_wins = ganadoras["PnL (€)"].sum()
                sum_losses = abs(perdedoras["PnL (€)"].sum())
                profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else sum_wins

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Nº Operaciones", total_ops)
                m2.metric("% Ganadoras", f"{win_rate:.1f}%")
                m3.metric("Ganancia Media", f"{avg_win:+.2f} €")
                m4.metric("Pérdida Media", f"{avg_loss:+.2f} €")
                m5.metric("Profit Factor", f"{profit_factor:.2f}")

                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.caption("📌 PnL Acumulado por Activo (€)")
                    pnl_activo = df_ventas.groupby("Ticker")["PnL (€)"].sum().sort_values(ascending=False)
                    st.bar_chart(pnl_activo)

                with col_g2:
                    st.caption("🧠 Rendimiento por Puntuación Gemini")
                    df_gemini = df_ventas.dropna(subset=["Score_Gemini"])
                    if not df_gemini.empty:
                        pnl_gemini = df_gemini.groupby("Score_Gemini")["PnL (€)"].sum()
                        st.bar_chart(pnl_gemini)
                    else:
                        st.info("Las operaciones pasadas no tenían el formato nuevo. La gráfica se rellenará en las próximas compras.")
            else:
                st.info("Aún no hay ventas para calcular analíticas.")
        st.divider()

        # 3. TABLA HISTORIAL
        st.subheader("📜 Historial de Operaciones")
        if not df_historial_completo.empty:
            st.dataframe(df_historial_completo.sort_values(by="Fecha", ascending=False), use_container_width=True)
