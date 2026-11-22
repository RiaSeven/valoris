#!/usr/bin/env python3
"""
Valoris V2 — Moteur de collecte, valorisation (Juste Valeur), scoring de santé
financière et suivi macroéconomique (Indices, Futures, Matières premières).

Marchés actions couverts : FR (SBF/CAC), DE (DAX), US (S&P 500), KR (KOSPI), JP (Nikkei/TOPIX).
Génère `data.json` et met à jour `history.json` (suivi des précédents gagnants).
"""

from __future__ import annotations

import json
import math
import time
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
    {"ticker": "^FCHI", "name": "CAC 40", "category": "Indices", "region": "France", "unit": "pts"},
    {"ticker": "^GDAXI", "name": "DAX 40", "category": "Indices", "region": "Allemagne", "unit": "pts"},
    {"ticker": "^STOXX50E", "name": "Euro Stoxx 50", "category": "Indices", "region": "Zone Euro", "unit": "pts"},
    {"ticker": "^GSPC", "name": "S&P 500", "category": "Indices", "region": "États-Unis", "unit": "pts"},
    {"ticker": "^NDX", "name": "Nasdaq 100", "category": "Indices", "region": "États-Unis", "unit": "pts"},
    {"ticker": "^N225", "name": "Nikkei 225", "category": "Indices", "region": "Japon", "unit": "pts"},
    {"ticker": "^KS11", "name": "KOSPI", "category": "Indices", "region": "Corée du Sud", "unit": "pts"},
    {"ticker": "ES=F", "name": "Future S&P 500", "category": "Futures", "region": "États-Unis", "unit": "pts"},
    {"ticker": "NQ=F", "name": "Future Nasdaq 100", "category": "Futures", "region": "États-Unis", "unit": "pts"},
    {"ticker": "YM=F", "name": "Future Dow Jones", "category": "Futures", "region": "États-Unis", "unit": "pts"},
    {"ticker": "RTY=F", "name": "Future Russell 2000", "category": "Futures", "region": "États-Unis", "unit": "pts"},
    {"ticker": "NKD=F", "name": "Future Nikkei 225", "category": "Futures", "region": "Japon", "unit": "pts"},
    {"ticker": "GC=F", "name": "Or (Gold)", "category": "Matières premières", "region": "Métaux précieux", "unit": "$/oz"},
    {"ticker": "SI=F", "name": "Argent (Silver)", "category": "Matières premières", "region": "Métaux précieux", "unit": "$/oz"},
    {"ticker": "BZ=F", "name": "Pétrole Brent", "category": "Matières premières", "region": "Énergie", "unit": "$/bbl"},
    {"ticker": "CL=F", "name": "Pétrole WTI", "category": "Matières premières", "region": "Énergie", "unit": "$/bbl"},
    {"ticker": "HG=F", "name": "Cuivre (Copper)", "category": "Matières premières", "region": "Métaux ind.", "unit": "$/lb"},
    {"ticker": "NG=F", "name": "Gaz naturel", "category": "Matières premières", "region": "Énergie", "unit": "$/MMBtu"},
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


def fetch_fx_rates() -> dict[str, float]:
    """Récupère les taux de change 1 EUR -> devise locale pour homogénéiser les capitalisations."""
    rates: dict[str, float] = {"EUR": 1.0}
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
        rates[code] = fallback
    return rates


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


def fetch_raw_universe() -> list[dict[str, Any]]:
    raw_items: list[dict[str, Any]] = []
    for market, cfg in UNIVERSES.items():
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
            time.sleep(0.12)
    return raw_items


def fetch_macro() -> list[dict[str, Any]]:
    """Collecte les indices, futures et matières premières avec performances et MM200."""
    print(f"--- Collecte Macro ({len(MACRO_ASSETS)} actifs) ---")
    results: list[dict[str, Any]] = []
    current_year = datetime.now(timezone.utc).year

    for asset in MACRO_ASSETS:
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

            results.append({
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
            })
        except Exception as exc:
            print(f"  [!] Macro ignoré {sym}: {exc}")
        time.sleep(0.10)

    return results


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


def update_history(stocks: list[dict[str, Any]], history_path: Path) -> list[dict[str, Any]]:
    """Suit les candidats éligibles et promeut ceux qui atteignent leur Juste Valeur."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = {"tracked": {}, "winners": []}

    tracked: dict[str, Any] = history.setdefault("tracked", {})
    winners: list[dict[str, Any]] = history.setdefault("winners", [])

    for s in stocks:
        sym = s["ticker"]
        price = s["price"]
        fv = s["fairValue"]

        if sym in tracked:
            entry = tracked[sym]
            if price >= entry["targetFairValue"]:
                perf = round(((price - entry["entryPrice"]) / entry["entryPrice"]) * 100.0, 1)
                winners.insert(0, {
                    "ticker": sym,
                    "name": s["name"],
                    "market": s["market"],
                    "currency": s["currency"],
                    "detectedDate": entry["entryDate"],
                    "reachedDate": today,
                    "entryPrice": entry["entryPrice"],
                    "exitPrice": price,
                    "gainPct": perf,
                    "healthScoreAtEntry": entry["healthScore"],
                })
                del tracked[sym]
                continue

        if (
            sym not in tracked
            and s["upside"] >= 20.0
            and s["marketCapB"] >= 1.0
            and s["healthScore"] >= 2.5
        ):
            tracked[sym] = {
                "entryDate": today,
                "entryPrice": price,
                "targetFairValue": fv,
                "healthScore": s["healthScore"],
            }

    history["winners"] = winners[:40]
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history["winners"]


def main() -> None:
    fx_rates = fetch_fx_rates()
    raw_items = fetch_raw_universe()
    sector_medians = compute_sector_medians(raw_items)
    stocks: list[dict[str, Any]] = []

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

        stocks.append({
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
            "analystConsensus": RECOMMENDATION_FR.get(rec_key, "Conserver"),
            "valueTrap": is_value_trap,
        })

    stocks.sort(key=lambda x: x["upside"], reverse=True)
    winners = update_history(stocks, Path("history.json"))
    macro = fetch_macro()

    payload = {
        "version": "2.0",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "fxRates": fx_rates,
        "count": len(stocks),
        "stocks": stocks,
        "macro": macro,
        "winners": winners,
    }
    Path("data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Terminé V2 : {len(stocks)} actions et {len(macro)} actifs macro enregistrés dans data.json.")


if __name__ == "__main__":
    main()
