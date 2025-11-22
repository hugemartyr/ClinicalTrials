from fastapi import FastAPI, HTTPException
from typing import Dict
import requests

app = FastAPI()

TICKER_MAP: Dict[str, str] = {
    "MRNA": "Moderna",
    "PFE": "Pfizer",
    "LLY": "Eli Lilly",
    "BMY": "Bristol Myers Squibb",
    "JNJ": "Johnson & Johnson",
}

CTG = "https://clinicaltrials.gov/api/v2/studies"

@app.get("/studies")
def get_studies(ticker: str, size: int = 20):
    ticker = ticker.upper()

    if ticker not in TICKER_MAP:
        raise HTTPException(status_code=400, detail="Ticker not found in map")

    company = TICKER_MAP[ticker]

    params = {
        "format": "json",
        "pageSize": size,
        "query.titles": company,
        "postFilter.overallStatus" : "COMPLETED",
        "query.outc" : "adverse",
        
    }

    r = requests.get(CTG, params=params, timeout=10)
    r.raise_for_status()

    return r.json()
