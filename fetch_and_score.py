#!/usr/bin/env python3
"""
Valoris — Moteur de collecte, valorisation (Juste Valeur) et scoring de santé financière.
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
# 1. UNIVERS D'ACTIONS (FR = SBF 120 / CAC, DE = DAX 40, US = S&P 500 sélection)
# =============================================================================
UNIVERSES: dict[str, dict[str, Any]] = {
    "FR": {
        "currency": "€",
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
        "tickers": [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY", "AVGO", "JPM",
            "V", "UNH", "XOM", "MA", "JNJ", "PG", "HD", "COST", "ABBV", "MRK", "CRM", "CVX",
            "BAC", "KO", "PEP", "AMD", "ADBE", "TMO", "WMT", "NFLX", "ORCL", "INTC", "CSCO",
            "DIS", "VZ", "PFE", "NKE", "QCOM", "TXN", "AMAT", "MU", "PYPL", "SBUX", "BA",
            "CAT", "GE", "IBM", "GS", "MS", "BLK",
        ],
    },
}

# Multiples sectoriels par défaut si l'échantillon d'un secteur est trop petit
DEFAULT_SECTOR_MULTIPLES: dict[str, dict[str, float]] = {
    "Technology": {"pe": 25.0, "ev_ebitda": 16.0},
    "Healthcare": {"pe": 20.0, "ev_ebitda": 13.0},
    "Financial Services": {"pe": 11.0, "ev_ebitda": 0.0},  # EV/EBITDA non pertinent
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
# 2. OUTILS DE SCORING & VALORISATION
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
    """Projette linéairement une métrique entre 1.0 et 5.0."""
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


def estimate_dcf(info: dict[str, Any], price: float) -> float | None:
    """DCF conservateur sur 5 ans + valeur terminale."""
    fcf = safe_float(info.get("freeCashflow"))
    shares = safe_float(info.get("sharesOutstanding"))
    if not fcf or fcf <= 0 or not shares or shares <= 0:
        return None

    rev_g = safe_float(info.get("revenueGrowth")) or 0.04
    earn_g = safe_float(info.get("earningsGrowth"))
    raw_g = (rev_g + earn_g) / 2 if earn_g is not None else rev_g
    growth = max(0.01, min(0.12, raw_g))  # Plafonné entre 1 % et 12 %

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
    # Garde-fou contre les anomalies de données
    if fair < price * 0.25 or fair > price * 3.0:
        return None
    return round(fair, 2)


def estimate_multiples(
    info: dict[str, Any], price: float, sector_pe: float, sector_ev_ebitda: float
) -> float | None:
    """Valorisation par multiples sectoriels (PER + EV/EBITDA)."""
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
    """Calcule les 5 piliers (sur 5) et le score global de santé financière."""
    # 1. Rentabilité
    roe = safe_float(info.get("returnOnEquity"))
    op_margin = safe_float(info.get("operatingMargins"))
    net_margin = safe_float(info.get("profitMargins"))
    profitability = mean_valid([
        linear_score(roe, 0.02, 0.22),
        linear_score(op_margin, 0.03, 0.25),
        linear_score(net_margin, 0.02, 0.18),
    ])

    # 2. Croissance
    rev_g = safe_float(info.get("revenueGrowth"))
    earn_g = safe_float(info.get("earningsGrowth"))
    growth = mean_valid([
        linear_score(rev_g, -0.05, 0.18),
        linear_score(earn_g, -0.10, 0.25),
    ])

    # 3. Flux de trésorerie
    fcf = safe_float(info.get("freeCashflow"))
    rev = safe_float(info.get("totalRevenue"))
    net_inc = safe_float(info.get("netIncomeToCommon"))
    fcf_margin = (fcf / rev) if (fcf is not None and rev and rev > 0) else None
    fcf_conv = (fcf / net_inc) if (fcf is not None and net_inc and net_inc > 0) else None
    cashflow = mean_valid([
        linear_score(fcf_margin, -0.02, 0.18),
        linear_score(fcf_conv, 0.3, 1.2),
    ])

    # 4. Solidité du bilan
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

    # 5. Valorisation relative
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
# 3. COLLECTE & TRAITEMENT PRINCIPAL
# =============================================================================
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
                    "symbol": symbol,
                    "info": info,
                    "price": price,
                    "marketCap": mcap,
                })
            except Exception as exc:
                print(f"  [!] Ignoré {symbol}: {exc}")
            time.sleep(0.15)  # Limite douce pour éviter le blocage Yahoo
    return raw_items


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
            "pe": median(pe_list) if len(pe_list) >= 3 else defaults["pe"],
            "ev_ebitda": median(ev_list) if len(ev_list) >= 3 else defaults["ev_ebitda"],
        }
    return medians


def update_history(stocks: list[dict[str, Any]], history_path: Path) -> list[dict[str, Any]]:
    """Suit les titres sous-évalués dans le temps et détecte les précédents gagnants."""
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

        # Vérifie si un titre suivi a atteint son objectif
        if sym in tracked:
            entry = tracked[sym]
            if price >= entry["targetFairValue"]:
                perf = round(((price - entry["entryPrice"]) / entry["entryPrice"]) * 100, 1)
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

        # Ajoute les nouveaux candidats répondant aux 3 critères clés
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

    # Garde les 30 derniers gagnants
    history["winners"] = winners[:30]
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return history["winners"]


def main() -> None:
    raw_items = fetch_raw_universe()
    sector_medians = compute_sector_medians(raw_items)
    stocks: list[dict[str, Any]] = []

    for item in raw_items:
        info = item["info"]
        price = item["price"]
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
        upside = round(((fair_value - price) / price) * 100, 1)

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
            "marketCapB": round(item["marketCap"] / 1e9, 2),
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

    # Tri décroissant par potentiel de hausse
    stocks.sort(key=lambda x: x["upside"], reverse=True)

    winners = update_history(stocks, Path("history.json"))

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(stocks),
        "stocks": stocks,
        "winners": winners,
    }
    Path("data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Terminé : {len(stocks)} actions enregistrées dans data.json.")


if __name__ == "__main__":
    main()
