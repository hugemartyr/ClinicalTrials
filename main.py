# from fastapi import FastAPI, HTTPException
# from typing import Dict
# import requests

# app = FastAPI()

# TICKER_MAP: Dict[str, str] = {
#     "MRNA": "Moderna",
#     "PFE": "Pfizer",
#     "LLY": "Eli Lilly",
#     "BMY": "Bristol Myers Squibb",
#     "JNJ": "Johnson & Johnson",
# }

# CTG = "https://clinicaltrials.gov/api/v2/studies"

# @app.get("/studies")
# def get_studies(ticker: str, size: int = 20):
#     ticker = ticker.upper()

#     if ticker not in TICKER_MAP:
#         raise HTTPException(status_code=400, detail="Ticker not found in map")

#     company = TICKER_MAP[ticker]

#     params = {
#         "format": "json",
#         "pageSize": size,
#         "query.titles": company,
#         "postFilter.overallStatus" : "COMPLETED",
#         "query.outc" : "adverse",
        
#     }

#     r = requests.get(CTG, params=params, timeout=10)
#     r.raise_for_status()

#     return r.json()



from fastapi import FastAPI, HTTPException
from typing import Dict, List
import requests

app = FastAPI()

# fallback map if API fails
TICKER_MAP: Dict[str, str] = {
    "MRNA": "Moderna",
    "PFE": "Pfizer",
    "LLY": "Eli Lilly",
    "BMY": "Bristol Myers Squibb",
    "JNJ": "Johnson & Johnson",
}

FMP_URL = "https://financialmodelingprep.com/stable/search-symbol"
CTG_URL = "https://clinicaltrials.gov/api/v2/studies"

API_KEY = "YOUR_API_KEY_HERE"   # <--- insert your FMP key


def get_company_from_api(ticker: str) -> str:
    """
    Tries to fetch company name using FMP search-symbol API.
    Falls back to TICKER_MAP if API fails or ticker not found.
    """

    params = {
        "query": ticker,
        "apikey": API_KEY
    }

    try:
        response = requests.get(FMP_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            # FMP returns entries with keys: symbol, name, currency, etc.
            for item in data:
                if item.get("symbol", "").upper() == ticker.upper():
                    return item.get("name")

        # If no match found → try fallback
        return TICKER_MAP.get(ticker.upper())

    except Exception:
        # API failed → fallback
        return TICKER_MAP.get(ticker.upper())


@app.get("/studies")
def get_studies(ticker: str, size: int = 20):
    ticker = ticker.upper()

    company = get_company_from_api(ticker)

    if not company:
        raise HTTPException(status_code=400, detail="Ticker not found in API or fallback map")

    params = {
        "format": "json",
        "pageSize": size,
        "query.titles": company,
        "postFilter.overallStatus": "COMPLETED",
        "query.outc": "adverse"
    }

    r = requests.get(CTG_URL, params=params, timeout=10)
    r.raise_for_status()

    return {
        "ticker": ticker,
        "companyUsed": company,
        "data": r.json()
    }
