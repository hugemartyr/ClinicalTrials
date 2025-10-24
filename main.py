# # main.py
# from typing import List, Optional, Dict, Any
# from fastapi import FastAPI, HTTPException, Query
# import requests
# import yfinance as yf
# import uvicorn
# import re
# import logging

# app = FastAPI(title="ClinicalTrials AE API")

# CLINICALTRIALS_FULL_STUDIES = "https://clinicaltrials.gov/api/query/full_studies"

# logger = logging.getLogger("uvicorn")
# logger.setLevel(logging.INFO)

# TICKER_MAP = {
#     "MRNA": "Moderna, Inc.",
#     "PFE": "Pfizer",
#     "LLY": "Eli Lilly",
#     "BMY": "Bristol Myers Squibb",
#     "JNJ": "Johnson & Johnson",
#     # Add more as needed
# }

# def get_company_name_from_ticker(ticker: str) -> Optional[str]:
#     """Try yfinance first; if that fails, try a simple Yahoo Finance search endpoint fallback."""
#     ticker = ticker.strip().upper()
#     try:
#         if ticker in TICKER_MAP:
#             return TICKER_MAP[ticker]
#         tk = yf.Ticker(ticker)
#         info = tk.info or {}
#         if "longName" in info and info["longName"]:
#             return info["longName"]
#         if "shortName" in info and info["shortName"]:
#             return info["shortName"]
#     except Exception as e:
#         logger.info(f"yfinance lookup failed for {ticker}: {e}")

#     # fallback: Yahoo search endpoint
#     try:
#         qurl = f"https://query2.finance.yahoo.com/v1/finance/search?q={ticker}"
#         r = requests.get(qurl, timeout=10)
#         j = r.json()
#         if j.get("quotes"):
#             # choose first match that has a shortname
#             for q in j["quotes"]:
#                 if q.get("symbol","").upper() == ticker and q.get("shortname"):
#                     return q.get("shortname")
#             # otherwise pick first
#             if j["quotes"] and j["quotes"][0].get("shortname"):
#                 return j["quotes"][0]["shortname"]
#     except Exception as e:
#         logger.info(f"Yahoo search fallback failed for {ticker}: {e}")

#     return None


# def query_clinicaltrials(company_query: str, max_records: int = 50) -> Dict[str, Any]:
#     """
#     Query the ClinicalTrials.gov full_studies endpoint for records that mention the company_query.
#     Returns the JSON response (may include 0 'FullStudies').
#     """
#     # Build a simple expr using the company name. You can make this more strict (sponsor, intervention, etc.)
#     expr = requests.utils.quote(company_query)
#     params = {
#         "expr": company_query,
#         "min_rnk": 1,
#         "max_rnk": max_records,
#         "fmt": "json"
#     }
#     r = requests.get(CLINICALTRIALS_FULL_STUDIES, params=params, timeout=20)
#     r.raise_for_status()
#     return r.json()


# def extract_adverse_events_from_study(full_study: dict) -> Dict[str, Any]:
#     """Extract adverse events from a single FullStudy JSON object (if available)."""
#     out = {
#         "nct_id": None,
#         "title": None,
#         "adverse_events": []
#     }
#     try:
#         study = full_study.get("Study", {})
#         # identification
#         id_info = study.get("ProtocolSection", {}) or study.get("IdentificationModule", {}) or study
#         # fallback NCT:
#         nct = None
#         try:
#             nct = (study.get("ProtocolSection", {})
#                         .get("IdentificationModule", {})
#                         .get("NCTId"))
#         except Exception:
#             pass
#         if not nct:
#             # sometimes NCT appears higher
#             nct = study.get("IdentificationModule", {}).get("NCTId") or study.get("NCTId")
#         out["nct_id"] = nct or (study.get("ProtocolSection", {}).get("IdentificationModule", {}).get("NCTId"))

#         # title
#         try:
#             out["title"] = study.get("ProtocolSection", {}).get("IdentificationModule", {}).get("OfficialTitle") \
#                 or study.get("ProtocolSection", {}).get("IdentificationModule", {}).get("BriefTitle") \
#                 or study.get("Study")["ProtocolSection"]["IdentificationModule"].get("OfficialTitle")
#         except Exception:
#             out["title"] = full_study.get("Study", {}).get("BriefTitle")

#         # Results section may live in Study.ResultsSection or ResultsModule
#         rs = study.get("ResultsSection") or study.get("ResultsModule") or study.get("Study", {}).get("ResultsSection")
#         # ClinicalTrials.gov results structure varies; try common paths:
#         if rs:
#             # Serious adverse events module
#             serious = rs.get("SeriousAdverseEventsModule") or {}
#             other = rs.get("OtherEventsModule") or {}
#             def parse_event_table(mod):
#                 events = []
#                 # look for tables or lists
#                 # common places: 'SeriousEventsTable' / 'OtherEventsTable' with a 'Row' list that contains fields
#                 table = mod.get("SeriousEventsTable") or mod.get("OtherEventsTable") or mod.get("AdverseEventsTable")
#                 if table and isinstance(table, dict):
#                     rows = table.get("Row") or table.get("Rows") or []
#                     for r in rows:
#                         # event term might be under 'EventTerm' or 'AdverseEventTerm' etc.
#                         term = r.get("EventTerm") or r.get("AdverseEventTerm") or r.get("AdverseEvent")
#                         if isinstance(term, dict):
#                             term = term.get("Term")
#                         if term:
#                             events.append({
#                                 "term": term,
#                                 "details": r
#                             })
#                 # fallback: sometimes textual lists exist
#                 elif mod:
#                     # try to find any 'AdverseEvent' keys
#                     for k, v in mod.items():
#                         if isinstance(v, list):
#                             for item in v:
#                                 if isinstance(item, dict) and ("AdverseEventTerm" in item or "EventTerm" in item):
#                                     term = item.get("AdverseEventTerm") or item.get("EventTerm")
#                                     if isinstance(term, dict):
#                                         term = term.get("Term")
#                                     if term:
#                                         events.append({"term": term, "details": item})
#                 return events

#             out["adverse_events"].extend(parse_event_table(serious))
#             out["adverse_events"].extend(parse_event_table(other))
#         else:
#             # try older schema paths: Study.ResultsModule
#             rm = study.get("ResultsModule") or {}
#             if rm:
#                 serious = rm.get("SeriousAdverseEventsModule", {})
#                 other = rm.get("OtherEventsModule", {})
#                 out["adverse_events"].extend(parse_event_table(serious))
#                 out["adverse_events"].extend(parse_event_table(other))

#     except Exception as e:
#         logger.info(f"Error parsing study: {e}")
#     return out


# @app.get("/adverse-effects")
# def get_adverse_effects(ticker: str = Query(..., description="US stock ticker (e.g., PFE, MRNA)"),
#                         max: int = Query(50, ge=1, le=200, description="max number of clinicaltrials.gov records to fetch")):
#     # 1) resolve ticker -> company name
#     company_name = get_company_name_from_ticker(ticker)
#     if not company_name:
#         raise HTTPException(status_code=400, detail=f"Cannot resolve company name for ticker '{ticker}'")

#     # 2) query clinicaltrials.gov
#     try:
#         ct_json = query_clinicaltrials(company_name, max_records=max)
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"ClinicalTrials.gov query failed: {str(e)}")

#     full_studies = ct_json.get("FullStudiesResponse", {}).get("FullStudies", [])
#     if not full_studies:
#         return {"ticker": ticker, "company_name": company_name, "count": 0, "trials": [], "aggregated_events": []}

#     trials_out = []
#     aggregated = {}
#     for fs in full_studies:
#         item = extract_adverse_events_from_study(fs.get("FullStudy") or fs)
#         if item["adverse_events"]:
#             trials_out.append(item)
#             for ev in item["adverse_events"]:
#                 term = ev.get("term", "").strip()
#                 if term:
#                     aggregated[term] = aggregated.get(term, 0) + 1

#     # build aggregated list
#     agg_list = [{"term": t, "count": c} for t, c in sorted(aggregated.items(), key=lambda x: -x[1])]

#     return {
#         "ticker": ticker,
#         "company_name": company_name,
#         "count": len(trials_out),
#         "trials": trials_out,
#         "aggregated_events": agg_list
#     }


# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




from fastapi import FastAPI, HTTPException, Query
import requests
import yfinance as yf

app = FastAPI(title="AE-API")

CTG_V2_SEARCH = "https://clinicaltrials.gov/api/v2/studies"


TICKER_MAP = {
    "MRNA": "Moderna, Inc.",
    "PFE": "Pfizer",
    "LLY": "Eli Lilly",
    "BMY": "Bristol Myers Squibb",
    "JNJ": "Johnson & Johnson",
}

def resolve_name(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker in TICKER_MAP:
        return TICKER_MAP[ticker]
    raise HTTPException(status_code=400, detail=f"Unknown ticker '{ticker}'. Please add it to TICKER_MAP.")



def search_trials(company: str, size: int = 20):
    params = {
        "query.spons": company,
        "pageSize": size,
        "format": "json"
    }
    r = requests.get(CTG_V2_SEARCH, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("studies", [])

def extract_adverse(study: dict):
    """Simplified: look for resultsSection → adverseEvents etc."""
    out = []
    rs = study.get("resultsSection")
    if not rs:
        return out
    ae_mod = rs.get("adverseEventsModule") or {}
    table = ae_mod.get("adverseEventsTable", {})
    rows = table.get("rows", []) or table.get("row", [])
    for r in rows:
        term = r.get("eventTerm") or r.get("adverseEventTerm")
        if term:
            out.append(term)
    return out

@app.get("/adverse-effects")
def get_adverse(ticker: str = Query(...), size: int = Query(20, ge=1, le=100)):
    company = resolve_name(ticker)
    studies = search_trials(company, size=size)
    results = []
    for s in studies:
        nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
        title = s.get("protocolSection", {}).get("identificationModule", {}).get("officialTitle")
        aelist = extract_adverse(s.get("protocolSection", {}))
        if aelist:
            results.append({"nctId": nct, "title": title, "adverseEffects": aelist})
    return {"ticker": ticker.upper(), "company": company, "count": len(results), "trials": results}
