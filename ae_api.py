

# from fastapi import FastAPI, HTTPException, Query
# import requests
# import yfinance as yf # Note: This import is present in the original code but unused.

# # Clinical Trials.gov API v2 endpoint
# CTG_V2_SEARCH = "https://clinicaltrials.gov/api/v2/studies"

# # Hardcoded map to convert tickers to full company sponsor names
# TICKER_MAP = {
#     "MRNA": "Moderna, Inc.",
#     "PFE": "Pfizer",
#     "LLY": "Eli Lilly",
#     "BMY": "Bristol Myers Squibb",
#     "JNJ": "Johnson & Johnson",
# }

# app = FastAPI(title="AE-API")


# def resolve_name(ticker: str) -> str:
#     """Converts a stock ticker to a full sponsor name."""
#     ticker = ticker.strip().upper()
#     if ticker in TICKER_MAP:
#         return TICKER_MAP[ticker]
#     raise HTTPException(status_code=400, detail=f"Unknown ticker '{ticker}'. Please add it to TICKER_MAP.")


# def search_trials(company: str, size: int = 20):
#     """Queries ClinicalTrials.gov for studies sponsored by the company."""
#     params = {
#         "query.spons": company,
#         "pageSize": size,
#         "format": "json"
#     }
#     # Set a timeout for the external request
#     r = requests.get(CTG_V2_SEARCH, params=params, timeout=10)
#     r.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
#     return r.json().get("studies", [])

# def extract_adverse(study: dict):
#     """Extracts a list of adverse event terms from a study dictionary."""
#     out = []
#     # Adverse events are buried deep in the JSON structure
#     rs = study.get("resultsSection")
#     if not rs:
#         return out
        
#     ae_mod = rs.get("adverseEventsModule") or {}
#     table = ae_mod.get("adverseEventsTable", {})
    
#     # The structure sometimes uses 'rows' or 'row'
#     rows = table.get("rows", []) or table.get("row", [])
    
#     for r in rows:
#         # The term can be 'eventTerm' or 'adverseEventTerm'
#         term = r.get("eventTerm") or r.get("adverseEventTerm")
#         if term:
#             out.append(term)
#     return out

# @app.get("/adverse-effects")
# def get_adverse(ticker: str = Query(..., description="US Biopharma Stock Ticker (e.g., MRNA, LLY)"), 
#                 size: int = Query(20, ge=1, le=100, description="Max number of trials to check")):
#     """
#     Retrieves adverse effects reported in clinical trials for a given company.
#     """
#     # 1. Resolve Ticker to Company Name
#     company = resolve_name(ticker)
    
#     # 2. Search Clinical Trials.gov
#     studies = search_trials(company, size=size)
    
#     results = []
    
#     # 3. Process each study
#     for s in studies:
#         # Get identifying information
#         protocol = s.get("protocolSection", {})
#         id_module = protocol.get("identificationModule", {})
#         nct = id_module.get("nctId")
#         title = id_module.get("officialTitle")
        
#         # Extract adverse effects
#         # NOTE: We pass the whole study dict here, as the extract_adverse function handles the traversal
#         aelist = extract_adverse(s) 
        
#         # Only include results that actually list adverse effects
#         if aelist:
#             results.append({
#                 "nctId": nct, 
#                 "title": title, 
#                 "adverseEffects": aelist
#             })
            
#     # 4. Return Final Structured JSON
#     return {
#         "ticker": ticker.upper(), 
#         "company": company, 
#         "count_trials_with_adverse_effects": len(results), 
#         "trials": results
#     }


from fastapi import FastAPI, HTTPException, Query
import requests

app = FastAPI(title="CTR API v2")

YF_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
CTG_STUDIES = "https://clinicaltrials.gov/api/v2/studies"

# fallback if yahoo fails
TICKER_FALLBACK = {
    "MRNA": "Moderna, Inc.",
    "PFE": "Pfizer",
    "LLY": "Eli Lilly",
    "BMY": "Bristol Myers Squibb",
    "JNJ": "Johnson & Johnson",
}


def resolve_company_from_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()

    # attempt yahoo finance
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(f"{YF_SEARCH}?q={ticker}", timeout=8, headers=headers)
        j = r.json()

        quotes = j.get("quotes") or []

        for q in quotes:
            if q.get("symbol", "").upper() == ticker and q.get("shortname"):
                return q["shortname"]

        if quotes and quotes[0].get("shortname"):
            return quotes[0]["shortname"]
    except Exception:
        pass

    # fallback map
    if ticker in TICKER_FALLBACK:
        return TICKER_FALLBACK[ticker]

    raise HTTPException(404, f"Could not resolve company name for '{ticker}'")


def fetch_studies(company: str, size: int, statuses: list[str] | None):
    params = {
        "query.spons": f"\"{company}\"",   # quote the company name because it has commas
        "pageSize": size,
        "format": "json",
        "countTotal": True
    }

    if statuses:
        params["filter.overallStatus"] = f"[{','.join(statuses)}]"

    r = requests.get(CTG_STUDIES, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    return data.get("studies", []), data.get("totalCount")


@app.get("/studies")
def get_studies(
    ticker: str = Query(...),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="comma list e.g. COMPLETED,RECRUITING")
):
    company = resolve_company_from_ticker(ticker)

    statuses = [s.strip().upper() for s in status.split(",")] if status else None

    studies, totalCount = fetch_studies(company, size, statuses)

    output = []
    for s in studies:
        protocol = s.get("protocolSection", {})
        idmod = protocol.get("identificationModule", {})
        status_val = protocol.get("statusModule", {}).get("overallStatus")

        output.append({
            "nctId": idmod.get("nctId"),
            "title": idmod.get("officialTitle"),
            "status": status_val
        })

    return {
        "ticker": ticker.upper(),
        "company": company,
        "count_returned": len(output),
        "count_total_matching": totalCount,
        "studies": output
    }
