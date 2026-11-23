#!/usr/bin/env python3
"""
Valoris V3 — Moteur de collecte, valorisation (Juste Valeur), scoring de santé
financière, suivi macroéconomique et briefings automatisés Asie (matin) / Europe-US (soir).

Nouveautés V3 :
- Collecte par session (`asia`, `west`, `all`) avec fusion incrémentale dans `data.json`.
- Briefings automatisés Matin (Asie) et Soir (Europe & US) : hybride API Gemini
  (si `GEMINI_API_KEY` est défini) avec repli automatique sur moteur algorithmique Python.
- Sparklines 3 mois (actions et actifs macro) via téléchargement groupé.
- Radar "Nouvelles entrées", variation du potentiel sur 5 séances, dates de résultats (Earnings),
  rendement du dividende et Payout Ratio.
- Notifications push optionnelles (Telegram / Discord) via secrets GitHub.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import yfinance as yf

# =============================================================================
# 1. UNIVERS D'ACTIONS (FR, DE, US, KR, JP)
# =============================================================================
UNIVERSES: dict[str, dict[str, Any]] = {
    "FR": {
        "currency": "€",
        "fx": "EUR",
        "region": "west",
        "tickers": [
            "MC.PA", "OR.PA", "RMS.PA", "TTE.PA", "SAN.PA", "AIR.PA", "SU.PA", "AI.PA",
            "EL.PA", "BNP.PA", "CS.PA", "DG.PA", "SAF.PA", "SGO.PA", "BN.PA", "DSY.PA",
            "CAP.PA", "STMPA.PA", "ORA.PA", "PUB.PA", "RI.PA", "KER.PA", "ML.PA", "VIE.PA",
            "ACA.PA", "GLE.PA", "EN.PA", "LR.PA", "CA.PA", "RNO.PA", "STLAP.PA", "VIV.PA",
            "EDEN.PA", "TEP.PA", "BVI.PA", "ERF.PA", "HO.PA", "AC.PA", "ADP.PA", "AF.PA",
            "ALO.PA", "AM.PA", "BIM.PA", "BOL.PA", "COFA.PA", "COV.PA", "DIM.PA", "ENX.PA",
            "FGR.PA", "FR.PA", "GFC.PA", "GTT.PA", "IPN.PA", "DEC.PA", "LI.PA", "NEX.PA",
            "RCO.PA", "RF.PA", "RUI.PA", "SCR.PA", "SEB.PA", "SK.PA", "SOI.PA", "SPIE.PA",
            "SW.PA", "UBI.PA", "VK.PA", "MF.PA", "WLN.PA",
        ],
    },
    "DE": {
        "currency": "€",
        "fx": "EUR",
        "region": "west",
        "tickers": [
            "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "MBG.DE", "BMW.DE", "VOW3.DE", "BAS.DE",
            "BAYN.DE", "IFX.DE", "ADS.DE", "DHL.DE", "MUV2.DE", "RWE.DE", "EOAN.DE", "DB1.DE",
            "DBK.DE", "CBK.DE", "FRE.DE", "HEN3.DE", "MRK.DE", "MTX.DE", "RHM.DE", "SHL.DE",
            "SY1.DE", "VNA.DE", "ZAL.DE", "BEI.DE", "CON.DE", "HEI.DE", "HNR1.DE", "P911.DE",
            "ENR.DE", "QIA.DE",
        ],
    },
    "US": {
        "currency": "$",
        "fx": "USD",
        "region": "west",
        "tickers": [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY", "AVGO", "JPM",
            "V", "UNH", "XOM", "MA", "JNJ", "PG", "HD", "COST", "ABBV", "MRK", "CRM", "CVX",
            "BAC", "KO", "PEP", "AMD", "ADBE", "TMO", "WMT", "NFLX", "ORCL", "INTC", "CSCO",
            "DIS", "VZ", "PFE", "NKE", "QCOM", "TXN", "AMAT", "MU", "PYPL", "SBUX", "BA",
            "CAT", "GE", "IBM", "GS", "MS", "BLK",
        ],
    },
    "KR": {
        "currency": "₩",
        "fx": "KRW",
        "region": "asia",
        "tickers": [
            "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "000270.KS",
            "068270.KS", "105560.KS", "055550.KS", "035420.KS", "005490.KS", "051910.KS",
            "006400.KS", "035720.KS", "012330.KS", "028260.KS", "086790.KS", "032830.KS",
            "015760.KS", "066570.KS", "009150.KS", "034730.KS", "017670.KS", "030200.KS",
            "012450.KS",
        ],
    },
    "JP": {
        "currency": "¥",
        "fx": "JPY",
        "region": "asia",
        "tickers": [
            "7203.T", "6758.T", "8306.T", "6501.T", "6861.T", "9983.T", "8035.T", "9984.T",
            "6098.T", "4063.T", "8058.T", "8001.T", "8031.T", "8316.T", "8411.T", "9432.T",
            "9433.T", "4502.T", "4519.T", "4568.T", "7974.T", "7267.T", "6367.T", "6954.T",
            "6857.T", "6146.T", "7011.T", "7741.T", "8766.T", "2914.T",
        ],
    },
}

# =============================================================================
# 2. UNIVERS MACRO (INDICES, FUTURES, MATIÈRES PREMIÈRES)
# =============================================================================
MACRO_ASSETS: list[dict[str, str]] = [
    {"ticker": "^FCHI", "name": "CAC 40", "category": "Indices", "region": "France", "session": "west", "unit": "pts"},
    {"ticker": "^GDAXI", "name": "DAX 40", "category": "Indices", "region": "Allemagne", "session": "west", "unit": "pts"},
    {"ticker": "^STOXX50E", "name": "Euro Stoxx 50", "category": "Indices", "region": "Zone Euro", "session": "west", "unit": "pts"},
    {"ticker": "^GSPC", "name": "S&P 500", "category": "Indices", "region": "États-Unis", "session": "west", "unit": "pts"},
    {"ticker": "^NDX", "name": "Nasdaq 100", "category": "Indices", "region": "États-Unis", "session": "west", "unit": "pts"},
    {"ticker": "^N225", "name": "Nikkei 225", "category": "Indices", "region": "Japon", "session": "asia", "unit": "pts"},
    {"ticker": "^KS11", "name": "KOSPI", "category": "Indices", "region": "Corée du Sud", "session": "asia", "unit": "pts"},
    {"ticker": "ES=F", "name": "Future S&P 500", "category": "Futures", "region": "États-Unis", "session": "both", "unit": "pts"},
    {"ticker": "NQ=F", "name": "Future Nasdaq 100", "category": "Futures", "region": "États-Unis", "session": "both", "unit": "pts"},
    {"ticker": "YM=F", "name": "Future Dow Jones", "category": "Futures", "region": "États-Unis", "session": "west", "unit": "pts"},
    {"ticker": "RTY=F", "name": "Future Russell 2000", "category": "Futures", "region": "États-Unis", "session": "west", "unit": "pts"},
    {"ticker": "NKD=F", "name": "Future Nikkei 225", "category": "Futures", "region": "Japon", "session": "asia", "unit": "pts"},
    {"ticker": "GC=F", "name": "Or (Gold)", "category": "Matières premières", "region": "Métaux précieux", "session": "both", "unit": "$/oz"},
    {"ticker": "SI=F", "name": "Argent (Silver)", "category": "Matières premières", "region": "Métaux précieux", "session": "both", "unit": "$/oz"},
    {"ticker": "BZ=F", "name": "Pétrole Brent", "category": "Matières premières", "region": "Énergie", "session": "both", "unit": "$/bbl"},
    {"ticker": "CL=F", "name": "Pétrole WTI", "category": "Matières premières", "region": "Énergie", "session": "both", "unit": "$/bbl"},
    {"ticker": "HG=F", "name": "Cuivre (Copper)", "category": "Matières premières", "region": "Métaux ind.", "session": "both", "unit": "$/lb"},
    {"ticker": "NG=F", "name": "Gaz naturel", "category": "Matières premières", "region": "Énergie", "session": "both", "unit": "$/MMBtu"},
]

FX_PAIRS: dict[str, tuple[str, float]] = {
    "USD": ("EURUSD=X", 1.08),
    "JPY": ("EURJPY=X", 165.0),
    "KRW": ("EURKRW=X", 1500.0),
}

DEFAULT_SECTOR_MULTIPLES: dict[str, dict[str, float]] = {
    "Technology": {"pe": 25.0, "ev_ebitda": 16.0},
    "Healthcare": {"pe": 20.0, "ev_ebitda": 13.0},
    "Financial Services": {"pe": 11.0, "ev_ebitda": 0.0},
    "Consumer Cyclical": {"pe": 16.0, "ev_ebitda": 10.0},
    "Consumer Defensive": {"pe": 20.0, "ev_ebitda": 13.0},
    "Industrials": {"pe": 17.0, "ev_ebitda": 11.0},
    "Energy": {"pe": 10.0, "ev_ebitda": 5.5},
    "Utilities": {"pe": 15.0, "ev_ebitda": 9.5},
    "Communication Services": {"pe": 16.0, "ev_ebitda": 9.0},
    "Basic Materials": {"pe": 14.0, "ev_ebitda": 7.5},
    "Real Estate": {"pe": 16.0, "ev_ebitda": 15.0},
}

SECTOR_FR: dict[str, str] = {
    "Technology": "Technologie",
    "Healthcare": "Santé",
    "Financial Services": "Finance",
    "Consumer Cyclical": "Conso. cyclique",
    "Consumer Defensive": "Conso. défensive",
    "Industrials": "Industrie",
    "Energy": "Énergie",
    "Utilities": "Services publics",
    "Communication Services": "Télécoms & Médias",
    "Basic Materials": "Matériaux",
    "Real Estate": "Immobilier",
}

RECOMMENDATION_FR: dict[str, str] = {
    "strong_buy": "Achat fort",
    "buy": "Achat",
    "hold": "Conserver",
    "underperform": "Sous-performance",
    "sell": "Vente",
}


# =============================================================================
# 3. OUTILS MATHÉMATIQUES, VALORISATION & SCORING
# =============================================================================
def safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def clamp(val: float, low: float = 1.0, high: float = 5.0) -> float:
    return max(low, min(high, val))


def linear_score(val: float | None, low: float, high: float, invert: bool = False) -> float | None:
    """Projette linéairement une métrique sur l'intervalle [1.0 ; 5.0]."""
    if val is None:
        return None
    if high == low:
        return 3.0
    ratio = (val - low) / (high - low)
    if invert:
        ratio = 1.0 - ratio
    return clamp(1.0 + 4.0 * ratio, 1.0, 5.0)


def mean_valid(values: list[float | None], default: float = 3.0) -> float:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else default


def health_label(score: float) -> str:
    if score >= 4.5:
        return "Excellent"
    if score >= 3.5:
        return "Très bon"
    if score >= 2.5:
        return "Bon"
    if score >= 2.0:
        return "Passable"
    return "Faible"


def extract_dividend_yield_pct(info: dict[str, Any], price: float) -> float | None:
    """Calcule un rendement du dividende fiable en pourcentage."""
    rate = safe_float(info.get("dividendRate"))
    if rate is not None and rate > 0 and price > 0:
        pct = (rate / price) * 100.0
        if 0.0 < pct <= 25.0:
            return round(pct, 2)
    raw_y = safe_float(info.get("dividendYield"))
    if raw_y is not None and raw_y > 0:
        # yfinance renvoie parfois 0.045 (4.5 %) ou 4.5 selon les versions
        pct = raw_y if raw_y > 0.35 else raw_y * 100.0
        if 0.0 < pct <= 25.0:
            return round(pct, 2)
    return None


def extract_payout_ratio_pct(info: dict[str, Any]) -> float | None:
    pr = safe_float(info.get("payoutRatio"))
    if pr is None or pr < 0:
        return None
    pct = pr * 100.0 if pr <= 3.0 else pr
    return round(pct, 1) if pct <= 300.0 else None


def extract_earnings_info(info: dict[str, Any], now_utc: datetime) -> tuple[str | None, int | None]:
    """Extrait la prochaine date de résultats (YYYY-MM-DD) et le nombre de jours restants."""
    ts = safe_float(info.get("earningsTimestampStart")) or safe_float(info.get("earningsTimestamp"))
    if not ts or ts <= 0:
        return None, None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        days = (dt.date() - now_utc.date()).days
        if -1 <= days <= 180:
            return dt.strftime("%Y-%m-%d"), days
    except (OverflowError, OSError, ValueError):
        pass
    return None, None


def sample_sparkline(values: list[float], max_points: int = 16) -> list[float]:
    """Réduit une série de cours à max_points valeurs arrondies pour le rendu SVG."""
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if len(clean) < 2:
        return []
    if len(clean) <= max_points:
        return [round(v, 2) for v in clean]
    step = (len(clean) - 1) / (max_points - 1)
    return [round(clean[round(i * step)], 2) for i in range(max_points)]


def estimate_dcf(info: dict[str, Any], price: float) -> float | None:
    """Modèle DCF conservateur sur 5 ans + valeur terminale (WACC=9,5 %, g_inf=2,5 %)."""
    fcf = safe_float(info.get("freeCashflow"))
    shares = safe_float(info.get("sharesOutstanding"))
    if not fcf or fcf <= 0 or not shares or shares <= 0:
        return None

    rev_g = safe_float(info.get("revenueGrowth"))
    earn_g = safe_float(info.get("earningsGrowth"))
    if rev_g is not None and earn_g is not None:
        raw_g = (rev_g + earn_g) / 2.0
    elif rev_g is not None:
        raw_g = rev_g
    elif earn_g is not None:
        raw_g = earn_g
    else:
        raw_g = 0.04

    growth = max(0.01, min(0.12, raw_g))
    wacc = 0.095
    terminal_g = 0.025

    pv_fcf = 0.0
    projected = fcf
    for year in range(1, 6):
        projected *= (1.0 + growth)
        pv_fcf += projected / ((1.0 + wacc) ** year)

    terminal_val = (projected * (1.0 + terminal_g)) / (wacc - terminal_g)
    pv_terminal = terminal_val / ((1.0 + wacc) ** 5)

    cash = safe_float(info.get("totalCash")) or 0.0
    debt = safe_float(info.get("totalDebt")) or 0.0
    equity_value = pv_fcf + pv_terminal + cash - debt
    if equity_value <= 0:
        return None

    fair = equity_value / shares
    if fair < price * 0.25 or fair > price * 3.0:
        return None
    return round(fair, 2)


def estimate_multiples(
    info: dict[str, Any], price: float, sector_pe: float, sector_ev_ebitda: float
) -> float | None:
    """Valorisation par multiples sectoriels médians (PER + EV/EBITDA)."""
    estimates: list[float] = []

    eps = safe_float(info.get("forwardEps")) or safe_float(info.get("trailingEps"))
    if eps and eps > 0 and sector_pe > 0:
        val_pe = eps * sector_pe
        if price * 0.3 <= val_pe <= price * 2.8:
            estimates.append(val_pe)

    ebitda = safe_float(info.get("ebitda"))
    shares = safe_float(info.get("sharesOutstanding"))
    if ebitda and ebitda > 0 and shares and shares > 0 and sector_ev_ebitda > 0:
        cash = safe_float(info.get("totalCash")) or 0.0
        debt = safe_float(info.get("totalDebt")) or 0.0
        implied_eq = (ebitda * sector_ev_ebitda) + cash - debt
        if implied_eq > 0:
            val_ev = implied_eq / shares
            if price * 0.3 <= val_ev <= price * 2.8:
                estimates.append(val_ev)

    return round(sum(estimates) / len(estimates), 2) if estimates else None


def compute_health_scores(
    info: dict[str, Any], sector_pe: float, sector_ev_ebitda: float
) -> dict[str, float]:
    """Calcule les 5 piliers (1 à 5) et la note globale de santé financière."""
    roe = safe_float(info.get("returnOnEquity"))
    op_margin = safe_float(info.get("operatingMargins"))
    net_margin = safe_float(info.get("profitMargins"))
    profitability = mean_valid([
        linear_score(roe, 0.02, 0.22),
        linear_score(op_margin, 0.03, 0.25),
        linear_score(net_margin, 0.02, 0.18),
    ])

    rev_g = safe_float(info.get("revenueGrowth"))
    earn_g = safe_float(info.get("earningsGrowth"))
    growth = mean_valid([
        linear_score(rev_g, -0.05, 0.18),
        linear_score(earn_g, -0.10, 0.25),
    ])

    fcf = safe_float(info.get("freeCashflow"))
    rev = safe_float(info.get("totalRevenue"))
    net_inc = safe_float(info.get("netIncomeToCommon"))
    fcf_margin = (fcf / rev) if (fcf is not None and rev and rev > 0) else None
    fcf_conv = (fcf / net_inc) if (fcf is not None and net_inc and net_inc > 0) else None
    cashflow = mean_valid([
        linear_score(fcf_margin, -0.02, 0.18),
        linear_score(fcf_conv, 0.30, 1.20),
    ])

    debt = safe_float(info.get("totalDebt"))
    cash = safe_float(info.get("totalCash"))
    ebitda = safe_float(info.get("ebitda"))
    current_ratio = safe_float(info.get("currentRatio"))
    net_debt_ebitda = (
        ((debt - (cash or 0.0)) / ebitda)
        if (debt is not None and ebitda and ebitda > 0)
        else None
    )
    balance_sheet = mean_valid([
        linear_score(net_debt_ebitda, 0.0, 4.5, invert=True),
        linear_score(current_ratio, 0.8, 2.2),
    ])

    pe = safe_float(info.get("forwardPE")) or safe_float(info.get("trailingPE"))
    ev_eb = safe_float(info.get("enterpriseToEbitda"))
    rel_pe = (pe / sector_pe) if (pe and pe > 0 and sector_pe > 0) else None
    rel_ev = (ev_eb / sector_ev_ebitda) if (ev_eb and ev_eb > 0 and sector_ev_ebitda > 0) else None
    valuation = mean_valid([
        linear_score(rel_pe, 0.6, 1.6, invert=True),
        linear_score(rel_ev, 0.6, 1.6, invert=True),
    ])

    overall = (profitability + growth + cashflow + balance_sheet + valuation) / 5.0
    return {
        "overall": round(overall, 2),
        "profitability": round(profitability, 1),
        "growth": round(growth, 1),
        "cashflow": round(cashflow, 1),
        "balanceSheet": round(balance_sheet, 1),
        "valuation": round(valuation, 1),
    }


# =============================================================================
# 4. COLLECTE FX, SPARKLINES, ACTIONS & MACRO
# =============================================================================
def fetch_fx_rates(existing_fx: dict[str, float] | None = None) -> dict[str, float]:
    rates: dict[str, float] = dict(existing_fx or {})
    rates["EUR"] = 1.0
    print("--- Collecte des taux de change (base EUR) ---")
    for code, (pair, fallback) in FX_PAIRS.items():
        try:
            hist = yf.Ticker(pair).history(period="5d")
            if not hist.empty:
                val = safe_float(hist["Close"].dropna().iloc[-1])
                if val and val > 0:
                    rates[code] = round(val, 4)
                    print(f"  1 EUR = {rates[code]} {code}")
                    continue
        except Exception as exc:
            print(f"  [!] FX fallback pour {code}: {exc}")
        rates.setdefault(code, fallback)
    return rates


def fetch_sparklines_batch(tickers: list[str]) -> dict[str, tuple[list[float], float | None]]:
    """Télécharge en un bloc l'historique 3 mois pour construire les sparklines et variations 3M."""
    result: dict[str, tuple[list[float], float | None]] = {}
    if not tickers:
        return result
    print(f"--- Téléchargement groupé des sparklines 3M ({len(tickers)} titres) ---")
    chunk_size = 60
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        try:
            df = yf.download(
                chunk,
                period="3mo",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if df is None or df.empty:
                continue
            close_df = df["Close"] if "Close" in df else df
            if hasattr(close_df, "columns"):
                for sym in chunk:
                    if sym in close_df.columns:
                        vals = close_df[sym].dropna().tolist()
                        pts = sample_sparkline(vals, max_points=16)
                        chg3m = (
                            round(((pts[-1] - pts[0]) / pts[0]) * 100.0, 1)
                            if (len(pts) >= 2 and pts[0] > 0)
                            else None
                        )
                        result[sym] = (pts, chg3m)
            elif len(chunk) == 1:
                vals = close_df.dropna().tolist()
                pts = sample_sparkline(vals, max_points=16)
                chg3m = (
                    round(((pts[-1] - pts[0]) / pts[0]) * 100.0, 1)
                    if (len(pts) >= 2 and pts[0] > 0)
                    else None
                )
                result[chunk[0]] = (pts, chg3m)
        except Exception as exc:
            print(f"  [!] Sparklines lot {i} ignoré : {exc}")
    return result


def fetch_raw_universe(markets: list[str]) -> list[dict[str, Any]]:
    raw_items: list[dict[str, Any]] = []
    for market in markets:
        cfg = UNIVERSES[market]
        print(f"--- Collecte marché {market} ({len(cfg['tickers'])} titres) ---")
        for symbol in cfg["tickers"]:
            try:
                info = yf.Ticker(symbol).info
                price = safe_float(info.get("currentPrice")) or safe_float(info.get("regularMarketPrice"))
                mcap = safe_float(info.get("marketCap"))
                if not price or not mcap:
                    continue
                raw_items.append({
                    "market": market,
                    "currency": cfg["currency"],
                    "fx": cfg["fx"],
                    "symbol": symbol,
                    "info": info,
                    "price": price,
                    "marketCap": mcap,
                })
            except Exception as exc:
                print(f"  [!] Ignoré {symbol}: {exc}")
            time.sleep(0.10)
    return raw_items


def fetch_macro(session: str, existing_macro: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Collecte les indices, futures et matières premières pertinents pour la session."""
    by_ticker = {m["ticker"]: m for m in (existing_macro or [])}
    targets = [
        a for a in MACRO_ASSETS
        if session == "all" or a["session"] in (session, "both") or a["ticker"] not in by_ticker
    ]
    print(f"--- Collecte Macro session={session} ({len(targets)} actifs) ---")
    current_year = datetime.now(timezone.utc).year

    for asset in targets:
        sym = asset["ticker"]
        try:
            hist = yf.Ticker(sym).history(period="1y", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) < 5:
                continue

            last_price = float(closes.iloc[-1])

            def pct_from_offset(offset: int) -> float | None:
                if len(closes) <= offset:
                    return None
                ref = float(closes.iloc[-(offset + 1)])
                return round(((last_price - ref) / ref) * 100.0, 2) if ref else None

            chg_1d = pct_from_offset(1)
            chg_1w = pct_from_offset(5)
            chg_1m = pct_from_offset(21)

            ytd_series = closes[closes.index.year == current_year]
            if not ytd_series.empty and float(ytd_series.iloc[0]) > 0:
                ref_ytd = float(ytd_series.iloc[0])
                chg_ytd = round(((last_price - ref_ytd) / ref_ytd) * 100.0, 2)
            else:
                chg_ytd = None

            low_52w = float(closes.min())
            high_52w = float(closes.max())
            span = high_52w - low_52w
            pos_52w = round(((last_price - low_52w) / span) * 100.0, 1) if span > 0 else 50.0

            sma200_window = closes.tail(200)
            sma200 = float(sma200_window.mean()) if len(sma200_window) >= 50 else None
            dist_sma200 = (
                round(((last_price - sma200) / sma200) * 100.0, 2)
                if (sma200 and sma200 > 0)
                else None
            )
            trend = "Haussière" if (dist_sma200 is not None and dist_sma200 >= 0) else "Baissière"
            spark = sample_sparkline(closes.tail(63).tolist(), max_points=16)

            by_ticker[sym] = {
                "ticker": sym,
                "name": asset["name"],
                "category": asset["category"],
                "region": asset["region"],
                "unit": asset["unit"],
                "price": round(last_price, 2),
                "chg1d": chg_1d,
                "chg1w": chg_1w,
                "chg1m": chg_1m,
                "chgYtd": chg_ytd,
                "low52w": round(low_52w, 2),
                "high52w": round(high_52w, 2),
                "pos52w": pos_52w,
                "sma200": round(sma200, 2) if sma200 else None,
                "distSma200": dist_sma200,
                "trend": trend,
                "sparkline": spark,
            }
        except Exception as exc:
            print(f"  [!] Macro ignoré {sym}: {exc}")
        time.sleep(0.08)

    order = [a["ticker"] for a in MACRO_ASSETS]
    return [by_ticker[t] for t in order if t in by_ticker]


def compute_sector_medians(raw_items: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    pe_by_sector: dict[str, list[float]] = {}
    ev_by_sector: dict[str, list[float]] = {}

    for item in raw_items:
        info = item["info"]
        sector = info.get("sector") or "Industrials"
        pe = safe_float(info.get("forwardPE")) or safe_float(info.get("trailingPE"))
        ev_eb = safe_float(info.get("enterpriseToEbitda"))
        if pe and 3.0 <= pe <= 60.0:
            pe_by_sector.setdefault(sector, []).append(pe)
        if ev_eb and 2.0 <= ev_eb <= 40.0 and sector != "Financial Services":
            ev_by_sector.setdefault(sector, []).append(ev_eb)

    medians: dict[str, dict[str, float]] = {}
    for sector, defaults in DEFAULT_SECTOR_MULTIPLES.items():
        pe_list = pe_by_sector.get(sector, [])
        ev_list = ev_by_sector.get(sector, [])
        medians[sector] = {
            "pe": round(median(pe_list), 2) if len(pe_list) >= 3 else defaults["pe"],
            "ev_ebitda": round(median(ev_list), 2) if len(ev_list) >= 3 else defaults["ev_ebitda"],
        }
    return medians


# =============================================================================
# 5. HISTORIQUE : PRÉCÉDENTS GAGNANTS, NOUVELLES ENTRÉES & DELTA 5J
# =============================================================================
def is_valoris_candidate(stock: dict[str, Any]) -> bool:
    return (
        stock["upside"] >= 20.0
        and stock["marketCapB"] >= 1.0
        and stock["healthScore"] >= 2.5
        and not stock.get("valueTrap", False)
    )


def update_history_and_signals(
    stocks: list[dict[str, Any]],
    refreshed_markets: set[str],
    history_path: Path,
) -> list[dict[str, Any]]:
    """
    Met à jour `history.json` et enrichit chaque action avec :
    - `isNewEntry`: True si le titre vient de franchir les 3 critères Valoris aujourd'hui
    - `upsideDelta5d`: évolution du potentiel de hausse par rapport à il y a ~5 séances
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = {"tracked": {}, "winners": [], "upsideHistory": {}, "lastEligible": {}}

    tracked: dict[str, Any] = history.setdefault("tracked", {})
    winners: list[dict[str, Any]] = history.setdefault("winners", [])
    upside_hist: dict[str, list[dict[str, Any]]] = history.setdefault("upsideHistory", {})
    last_eligible: dict[str, list[str]] = history.setdefault("lastEligible", {})

    new_eligible_by_market: dict[str, list[str]] = {}

    for s in stocks:
        sym = s["ticker"]
        mkt = s["market"]
        price = s["price"]
        fv = s["fairValue"]
        eligible = is_valoris_candidate(s)

        if mkt in refreshed_markets:
            # 1. Historique du potentiel (pour delta 5 séances)
            series = upside_hist.setdefault(sym, [])
            if series and series[-1].get("d") == today:
                series[-1]["u"] = s["upside"]
            else:
                series.append({"d": today, "u": s["upside"]})
            upside_hist[sym] = series[-6:]

            # 2. Badge "Nouveau"
            prev_set = set(last_eligible.get(mkt, []))
            s["isNewEntry"] = bool(eligible and prev_set and sym not in prev_set)
            if eligible:
                new_eligible_by_market.setdefault(mkt, []).append(sym)

            # 3. Suivi des précédents gagnants
            if sym in tracked:
                entry = tracked[sym]
                if price >= entry["targetFairValue"]:
                    perf = round(((price - entry["entryPrice"]) / entry["entryPrice"]) * 100.0, 1)
                    winners.insert(0, {
                        "ticker": sym,
                        "name": s["name"],
                        "market": mkt,
                        "currency": s["currency"],
                        "detectedDate": entry["entryDate"],
                        "reachedDate": today,
                        "entryPrice": entry["entryPrice"],
                        "exitPrice": price,
                        "gainPct": perf,
                        "healthScoreAtEntry": entry["healthScore"],
                    })
                    del tracked[sym]
            elif eligible:
                tracked[sym] = {
                    "entryDate": today,
                    "entryPrice": price,
                    "targetFairValue": fv,
                    "healthScore": s["healthScore"],
                }

        # Calcul du delta 5 séances à partir de l'historique stocké
        series = upside_hist.get(sym, [])
        if len(series) >= 2:
            ref_u = series[0]["u"]
            s["upsideDelta5d"] = round(s["upside"] - ref_u, 1)
        else:
            s["upsideDelta5d"] = None

    for mkt in refreshed_markets:
        last_eligible[mkt] = new_eligible_by_market.get(mkt, [])

    history["winners"] = winners[:40]
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history["winners"]


# =============================================================================
# 6. BRIEFINGS AUTOMATISÉS (HYBRIDE GEMINI API + REPLI ALGORITHMIQUE)
# =============================================================================
def build_session_metrics(
    zone: str,
    stocks: list[dict[str, Any]],
    macro: list[dict[str, Any]],
    fx_rates: dict[str, float],
) -> dict[str, Any]:
    """Synthétise les chiffres clés de la zone (asia ou west) pour le briefing."""
    zone_markets = ["KR", "JP"] if zone == "asia" else ["FR", "DE", "US"]
    zone_stocks = [s for s in stocks if s["market"] in zone_markets]
    eligible = [s for s in zone_stocks if is_valoris_candidate(s)]
    traps = [s for s in zone_stocks if s.get("valueTrap")]
    new_entries = [s for s in eligible if s.get("isNewEntry")]

    # Classement composite (potentiel * santé) pour le Top 3
    top3 = sorted(
        eligible,
        key=lambda x: (x["upside"] * x["healthScore"]),
        reverse=True,
    )[:3]

    # Secteurs les plus représentés parmi les décotes saines
    sector_upside: dict[str, list[float]] = {}
    for s in eligible:
        sector_upside.setdefault(s["sector"], []).append(s["upside"])
    top_sectors = sorted(
        [(sec, len(vals), round(sum(vals) / len(vals), 1)) for sec, vals in sector_upside.items()],
        key=lambda x: (x[1], x[2]),
        reverse=True,
    )[:3]

    # Indices & macro pertinents
    macro_tickers = (
        {"^N225", "^KS11", "NKD=F", "GC=F", "BZ=F", "HG=F"}
        if zone == "asia"
        else {"^FCHI", "^GDAXI", "^STOXX50E", "^GSPC", "^NDX", "ES=F", "GC=F", "BZ=F"}
    )
    zone_macro = [m for m in macro if m["ticker"] in macro_tickers]
    bearish_indices = [m["name"] for m in zone_macro if m["category"] == "Indices" and m["trend"] == "Baissière"]
    upcoming_earnings = [
        f"{s['name']} (J-{s['daysToEarnings']})"
        for s in eligible
        if s.get("daysToEarnings") is not None and 0 <= s["daysToEarnings"] <= 14
    ][:4]

    fx_summary = (
        {"EUR/JPY": fx_rates.get("JPY"), "EUR/KRW": fx_rates.get("KRW")}
        if zone == "asia"
        else {"EUR/USD": fx_rates.get("USD")}
    )

    return {
        "zone": zone,
        "title": "Briefing Asie (Matin)" if zone == "asia" else "Briefing Europe & US (Soir)",
        "markets": zone_markets,
        "totalCount": len(zone_stocks),
        "eligibleCount": len(eligible),
        "trapCount": len(traps),
        "newEntries": [s["name"] for s in new_entries[:5]],
        "avgUpside": round(sum(s["upside"] for s in eligible) / len(eligible), 1) if eligible else 0.0,
        "avgHealth": round(sum(s["healthScore"] for s in eligible) / len(eligible), 2) if eligible else 0.0,
        "top3": [
            {
                "name": s["name"],
                "ticker": s["ticker"],
                "market": s["market"],
                "upside": s["upside"],
                "health": s["healthScore"],
                "pe": s["pe"],
                "divYield": s.get("dividendYield"),
            }
            for s in top3
        ],
        "topSectors": top_sectors,
        "macro": [
            {
                "name": m["name"],
                "price": m["price"],
                "chg1d": m["chg1d"],
                "chgYtd": m["chgYtd"],
                "trend": m["trend"],
            }
            for m in zone_macro
        ],
        "bearishIndices": bearish_indices,
        "upcomingEarnings": upcoming_earnings,
        "fx": fx_summary,
    }


def generate_algorithmic_briefing(metrics: dict[str, Any], now_iso: str) -> dict[str, Any]:
    """Générateur 100 % Python (gratuit, sans API externe) au format structuré."""
    macro_parts = []
    for m in metrics["macro"][:4]:
        if m["chg1d"] is not None:
            sign = "+" if m["chg1d"] >= 0 else ""
            macro_parts.append(f"{m['name']} ({sign}{m['chg1d']:.2f} % sur la séance, tendance {m['trend'].lower()})")
    fx_parts = [f"{k} à {v}" for k, v in metrics["fx"].items() if v]
    macro_text = (
        (", ".join(macro_parts) if macro_parts else "Données indices en cours d'actualisation")
        + (f". Côté changes : {', '.join(fx_parts)}." if fx_parts else ".")
    )

    if metrics["topSectors"]:
        sec_str = ", ".join(f"{sec} ({n} titres, +{u} % moy.)" for sec, n, u in metrics["topSectors"])
        sectors_text = f"{metrics['eligibleCount']} valeurs remplissent les critères Valoris (potentiel moyen +{metrics['avgUpside']} %, santé {metrics['avgHealth']}/5). Secteurs les plus décotés : {sec_str}."
    else:
        sectors_text = f"{metrics['eligibleCount']} valeurs sélectionnées sur {metrics['totalCount']} suivies dans la zone."

    if metrics["top3"]:
        top_str = " · ".join(
            f"{t['name']} (+{t['upside']} %, santé {t['health']}/5)"
            for t in metrics["top3"]
        )
        opp_text = f"Meilleurs couples décote/qualité : {top_str}."
        if metrics["newEntries"]:
            opp_text += f" Nouvelles entrées du jour : {', '.join(metrics['newEntries'])}."
    else:
        opp_text = "Aucune opportunité ne cumule aujourd'hui les trois seuils de sélection."

    vigilance_parts = []
    if metrics["trapCount"] > 0:
        vigilance_parts.append(f"{metrics['trapCount']} piège(s) de valeur filtré(s) automatiquement")
    if metrics["bearishIndices"]:
        vigilance_parts.append(f"indices sous MM200 : {', '.join(metrics['bearishIndices'])}")
    if metrics["upcomingEarnings"]:
        vigilance_parts.append(f"publications proches : {', '.join(metrics['upcomingEarnings'])}")
    vigilance_text = (
        " ; ".join(vigilance_parts).capitalize() + "."
        if vigilance_parts
        else "Aucune alerte majeure détectée sur la zone."
    )

    return {
        "title": metrics["title"],
        "updatedAt": now_iso,
        "engine": "Algo Python",
        "headline": f"{metrics['eligibleCount']} opportunités saines (+{metrics['avgUpside']} % moy.) sur {', '.join(metrics['markets'])}",
        "sections": {
            "macro": macro_text,
            "sectors": sectors_text,
            "opportunities": opp_text,
            "vigilance": vigilance_text,
        },
    }


def generate_gemini_briefing(metrics: dict[str, Any], now_iso: str, api_key: str) -> dict[str, Any] | None:
    """Appelle l'API REST Gemini (Flash) pour rédiger un briefing concis et structuré en JSON."""
    prompt = (
        "Tu es un analyste financier factuel et concis rédigeant en français pour un investisseur particulier. "
        "À partir des données JSON ci-dessous, produis UNIQUEMENT un objet JSON valide (sans bloc markdown) "
        "contenant exactement les clés suivantes : "
        '"headline" (titre synthétique <= 95 caractères), '
        '"macro" (2 phrases max sur indices, matières premières et devises), '
        '"sectors" (1 à 2 phrases sur les secteurs les plus décotés), '
        '"opportunities" (2 phrases max commentant le Top 3 et les nouvelles entrées), '
        '"vigilance" (1 à 2 phrases sur les pièges de valeur, indices sous MM200 et résultats proches). '
        "Ne donne aucun conseil d'achat personnalisé et appuie-toi uniquement sur les chiffres fournis.\n\n"
        f"Données : {json.dumps(metrics, ensure_ascii=False)}"
    )

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 550,
            "responseMimeType": "application/json",
        },
    }).encode("utf-8")

    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.strip("`").replace("json\n", "", 1).strip()
            parsed = json.loads(text)
            if all(k in parsed for k in ("headline", "macro", "sectors", "opportunities", "vigilance")):
                return {
                    "title": metrics["title"],
                    "updatedAt": now_iso,
                    "engine": f"Gemini ({model})",
                    "headline": str(parsed["headline"]),
                    "sections": {
                        "macro": str(parsed["macro"]),
                        "sectors": str(parsed["sectors"]),
                        "opportunities": str(parsed["opportunities"]),
                        "vigilance": str(parsed["vigilance"]),
                    },
                }
        except Exception as exc:
            print(f"  [!] Gemini {model} indisponible, fallback : {exc}")
    return None


def build_briefing(
    zone: str,
    stocks: list[dict[str, Any]],
    macro: list[dict[str, Any]],
    fx_rates: dict[str, float],
    now_iso: str,
) -> dict[str, Any]:
    metrics = build_session_metrics(zone, stocks, macro, fx_rates)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        ai_res = generate_gemini_briefing(metrics, now_iso, api_key)
        if ai_res:
            print(f"  Briefing {zone} rédigé via {ai_res['engine']}.")
            return ai_res
    print(f"  Briefing {zone} rédigé via moteur algorithmique Python.")
    return generate_algorithmic_briefing(metrics, now_iso)


# =============================================================================
# 7. NOTIFICATIONS OPTIONNELLES (TELEGRAM / DISCORD)
# =============================================================================
def send_notifications(briefing: dict[str, Any]) -> None:
    s = briefing["sections"]
    msg = (
        f"*{briefing['title']}* ({briefing['engine']})\n"
        f"{briefing['headline']}\n\n"
        f"• *Macro* : {s['macro']}\n"
        f"• *Secteurs* : {s['sectors']}\n"
        f"• *Opportunités* : {s['opportunities']}\n"
        f"• *Vigilance* : {s['vigilance']}"
    )

    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            data = json.dumps({"chat_id": tg_chat, "text": msg, "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=15).read()
            print("  Notification Telegram envoyée.")
        except Exception as exc:
            print(f"  [!] Échec notification Telegram : {exc}")

    discord_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if discord_url:
        try:
            data = json.dumps({"content": msg.replace("*", "**")[:1950]}).encode("utf-8")
            req = urllib.request.Request(discord_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=15).read()
            print("  Notification Discord envoyée.")
        except Exception as exc:
            print(f"  [!] Échec notification Discord : {exc}")


# =============================================================================
# 8. ORCHESTRATION PRINCIPALE
# =============================================================================
def resolve_session(arg_session: str, existing_data: dict[str, Any] | None) -> str:
    if not existing_data or not existing_data.get("stocks"):
        return "all"
    if arg_session in ("asia", "west", "all"):
        return arg_session
    # Mode auto selon l'heure UTC : matin (< 14h UTC) -> Asie, soir (>= 14h UTC) -> Occident
    hour_utc = datetime.now(timezone.utc).hour
    return "asia" if hour_utc < 14 else "west"


def main() -> None:
    parser = argparse.ArgumentParser(description="Valoris V3 — Collecte, Scoring & Briefings")
    parser.add_argument("--session", choices=["auto", "all", "asia", "west"], default="auto")
    args = parser.parse_args()

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    data_path = Path("data.json")
    existing = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else None

    session = resolve_session(args.session, existing)
    target_markets = (
        list(UNIVERSES.keys())
        if session == "all"
        else [m for m, cfg in UNIVERSES.items() if cfg["region"] == session]
    )
    print(f"=== Lancement Valoris V3 | session={session} | marchés={target_markets} ===")

    fx_rates = fetch_fx_rates(existing.get("fxRates") if existing else None)
    raw_items = fetch_raw_universe(target_markets)

    # Sparklines 3 mois en batch pour les titres rafraîchis
    spark_map = fetch_sparklines_batch([item["symbol"] for item in raw_items])
    sector_medians = compute_sector_medians(raw_items)

    refreshed_stocks: list[dict[str, Any]] = []
    for item in raw_items:
        info = item["info"]
        price = item["price"]
        fx_rate = fx_rates.get(item["fx"], 1.0)
        mcap_eur_b = round((item["marketCap"] / fx_rate) / 1e9, 2)

        sector_en = info.get("sector") or "Industrials"
        sec_mult = sector_medians.get(sector_en, {"pe": 16.0, "ev_ebitda": 10.0})

        dcf_val = estimate_dcf(info, price)
        mult_val = estimate_multiples(info, price, sec_mult["pe"], sec_mult["ev_ebitda"])
        analyst_val = safe_float(info.get("targetMeanPrice"))
        if analyst_val and (analyst_val < price * 0.3 or analyst_val > price * 3.0):
            analyst_val = None

        models = [v for v in (dcf_val, mult_val, analyst_val) if v is not None]
        if not models:
            continue

        fair_value = round(sum(models) / len(models), 2)
        upside = round(((fair_value - price) / price) * 100.0, 1)

        scores = compute_health_scores(info, sec_mult["pe"], sec_mult["ev_ebitda"])
        pe = safe_float(info.get("forwardPE")) or safe_float(info.get("trailingPE"))
        ev_ebitda = safe_float(info.get("enterpriseToEbitda"))
        rec_key = (info.get("recommendationKey") or "hold").lower()

        is_value_trap = (
            upside >= 20.0
            and (scores["overall"] < 2.5 or scores["cashflow"] < 2.0 or scores["balanceSheet"] < 2.0)
        )

        div_yield = extract_dividend_yield_pct(info, price)
        payout_ratio = extract_payout_ratio_pct(info)
        earnings_date, days_to_earnings = extract_earnings_info(info, now_utc)
        spark_pts, chg_3m = spark_map.get(item["symbol"], ([], None))

        refreshed_stocks.append({
            "ticker": item["symbol"],
            "name": info.get("shortName") or info.get("longName") or item["symbol"],
            "market": item["market"],
            "currency": item["currency"],
            "sector": SECTOR_FR.get(sector_en, sector_en),
            "price": round(price, 2),
            "fairValue": fair_value,
            "upside": upside,
            "marketCapB": mcap_eur_b,
            "healthScore": scores["overall"],
            "healthLabel": health_label(scores["overall"]),
            "scores": {
                "growth": scores["growth"],
                "profitability": scores["profitability"],
                "cashflow": scores["cashflow"],
                "balanceSheet": scores["balanceSheet"],
                "valuation": scores["valuation"],
            },
            "models": {
                "dcf": dcf_val,
                "multiples": mult_val,
                "analysts": round(analyst_val, 2) if analyst_val else None,
            },
            "pe": round(pe, 1) if pe and pe > 0 else None,
            "evEbitda": round(ev_ebitda, 1) if ev_ebitda and ev_ebitda > 0 else None,
            "dividendYield": div_yield,
            "payoutRatio": payout_ratio,
            "earningsDate": earnings_date,
            "daysToEarnings": days_to_earnings,
            "sparkline": spark_pts,
            "chg3m": chg_3m,
            "analystConsensus": RECOMMENDATION_FR.get(rec_key, "Conserver"),
            "valueTrap": is_value_trap,
            "isNewEntry": False,
            "upsideDelta5d": None,
        })

    # Fusion incrémentale : on conserve les marchés non rafraîchis sur cette session
    refreshed_set = set(target_markets)
    kept_stocks = [
        s for s in (existing.get("stocks", []) if existing else [])
        if s.get("market") not in refreshed_set
    ]
    all_stocks = refreshed_stocks + kept_stocks
    all_stocks.sort(key=lambda x: x["upside"], reverse=True)

    winners = update_history_and_signals(all_stocks, refreshed_set, Path("history.json"))
    macro = fetch_macro(session, existing.get("macro") if existing else None)

    # Génération des briefings (conserve l'autre zone intacte si session partielle)
    briefings = dict((existing.get("briefings") or {}) if existing else {})
    zones_to_brief = ["asia", "west"] if session == "all" else [session]
    for z in zones_to_brief:
        briefings[z] = build_briefing(z, all_stocks, macro, fx_rates, now_iso)
        if session != "all":
            send_notifications(briefings[z])

    payload = {
        "version": "3.0",
        "lastSession": session,
        "updatedAt": now_iso,
        "fxRates": fx_rates,
        "count": len(all_stocks),
        "briefings": briefings,
        "stocks": all_stocks,
        "macro": macro,
        "winners": winners,
    }
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Terminé V3 ({session}) : {len(all_stocks)} actions, {len(macro)} actifs macro et briefings enregistrés.")


if __name__ == "__main__":
    main()
