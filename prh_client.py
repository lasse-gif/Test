"""
PRH (Patentti- ja rekisterihallitus) API -asiakas
Hakee yritystiedot YTJ-rajapinnasta ja tilinpäätöstiedot XBRL-rajapinnasta.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error


YTJ_BASE = "https://avoindata.prh.fi/opendata-ytj-api/v3"
XBRL_BASE = "https://avoindata.prh.fi/opendata-xbrl-api/v3"


@dataclass
class Company:
    business_id: str
    name: str
    company_form: str
    registration_date: str
    status: str
    address: str = ""


@dataclass
class FinancialPeriod:
    business_id: str
    period_start: str
    period_end: str
    filing_date: str
    document_id: str
    data: dict = field(default_factory=dict)


class PRHClientError(Exception):
    pass


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise PRHClientError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise PRHClientError(f"Yhteysvirhe: {e.reason}") from e


def search_companies(name: str = "", business_id: str = "", page: int = 1) -> list[Company]:
    """Hae yrityksiä nimellä tai Y-tunnuksella."""
    params = {"page": str(page)}
    if name:
        params["name"] = name
    if business_id:
        params["businessId"] = business_id

    url = f"{YTJ_BASE}/companies?{urllib.parse.urlencode(params)}"
    data = _get(url)

    companies = []
    for item in data.get("companies", []):
        names = item.get("names", [])
        current_name = next((n["name"] for n in names if n.get("registrationDate")), "")
        if not current_name and names:
            current_name = names[0].get("name", "")

        addresses = item.get("addresses", [])
        addr_parts = []
        if addresses:
            a = addresses[0]
            if a.get("street"):
                addr_parts.append(a["street"])
            if a.get("city"):
                addr_parts.append(a["city"])

        companies.append(Company(
            business_id=item.get("businessId", ""),
            name=current_name,
            company_form=item.get("companyForm", ""),
            registration_date=item.get("registrationDate", ""),
            status=item.get("mainBusinessLine", {}).get("descriptions", [{}])[0].get("description", "") if item.get("mainBusinessLine") else "",
            address=", ".join(addr_parts),
        ))

    return companies


def get_company(business_id: str) -> Optional[Company]:
    """Hae yritys Y-tunnuksella."""
    results = search_companies(business_id=business_id)
    return results[0] if results else None


def get_financial_periods(business_id: str, page: int = 1) -> list[FinancialPeriod]:
    """Hae yrityksen tilinpäätösjaksot."""
    params = {"businessId": business_id, "page": str(page)}
    url = f"{XBRL_BASE}/financials?{urllib.parse.urlencode(params)}"
    data = _get(url)

    periods = []
    for item in data.get("financialStatements", []):
        periods.append(FinancialPeriod(
            business_id=item.get("businessId", ""),
            period_start=item.get("financialPeriodStart", ""),
            period_end=item.get("financialPeriodEnd", ""),
            filing_date=item.get("filingDate", ""),
            document_id=item.get("documentId", ""),
        ))

    return periods


def get_financial_statement(business_id: str, financial_date: str) -> Optional[dict]:
    """
    Hae tilinpäätöstiedot Y-tunnuksella ja tilikauden päätöspäivämäärällä (YYYY-MM-DD).
    """
    params = {"businessId": business_id, "financialDate": financial_date}
    url = f"{XBRL_BASE}/financial?{urllib.parse.urlencode(params)}"
    return _get(url)


def format_number(value) -> str:
    """Muotoile numero luettavaan muotoon."""
    try:
        num = float(value)
        return f"{num:>15,.0f} €".replace(",", " ")
    except (TypeError, ValueError):
        return str(value) if value is not None else "-"


def extract_key_figures(statement: dict) -> dict[str, str]:
    """Pura tilinpäätöksen keskeisimmät luvut."""
    figures = {}

    # Yritetään löytää tunnusluvut yleisistä XBRL-kentistä
    facts = statement.get("facts", {})
    inline = statement.get("inlineXbrl", {})

    # Molemmat formaatit voivat olla käytössä
    source = facts if facts else inline

    # Tunnettuja XBRL-tunnisteita tuloslaskelmalle ja taseelle
    key_map = {
        # Tuloslaskelma
        "Liikevaihto": [
            "fi-fs-2013-01-01:Liikevaihto",
            "ifrs-full:Revenue",
            "Revenue",
            "Liikevaihto",
        ],
        "Liiketulos": [
            "fi-fs-2013-01-01:Liiketulos",
            "ifrs-full:ProfitLossFromOperatingActivities",
            "Liiketulos",
        ],
        "Tilikauden tulos": [
            "fi-fs-2013-01-01:TilikaudenVoittoTappio",
            "ifrs-full:ProfitLoss",
            "TilikaudenVoittoTappio",
        ],
        # Tase
        "Taseen loppusumma": [
            "fi-fs-2013-01-01:Loppusumma",
            "ifrs-full:Assets",
            "Loppusumma",
        ],
        "Oma pääoma": [
            "fi-fs-2013-01-01:OmaPaaoma",
            "ifrs-full:Equity",
            "OmaPaaoma",
        ],
    }

    def search_nested(data: dict, keys: list[str]) -> Optional[str]:
        for key in keys:
            # Suora osuma
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    return val.get("value") or val.get("decimals") or str(val)
                return str(val)
            # Osittainen osuma (ilman nimiavaruutta)
            short_key = key.split(":")[-1] if ":" in key else key
            for k, v in data.items():
                if k.endswith(short_key) or short_key in k:
                    if isinstance(v, dict):
                        return v.get("value") or str(v)
                    return str(v)
        return None

    for label, identifiers in key_map.items():
        val = search_nested(source, identifiers)
        if val:
            figures[label] = format_number(val)

    return figures


def print_company(company: Company) -> None:
    print(f"\n{'─'*50}")
    print(f"  {company.name}")
    print(f"{'─'*50}")
    print(f"  Y-tunnus:      {company.business_id}")
    print(f"  Yhtiömuoto:    {company.company_form}")
    print(f"  Rekisteröity:  {company.registration_date}")
    if company.address:
        print(f"  Osoite:        {company.address}")
    if company.status:
        print(f"  Toimiala:      {company.status}")


def print_periods(periods: list[FinancialPeriod]) -> None:
    if not periods:
        print("\n  Tilinpäätöstietoja ei löydy (IXBRL-muodossa).")
        print("  Vanhemmat tilinpäätökset ovat saatavilla PRH:n Virre-palvelusta.")
        return
    print(f"\n  {'#':<4} {'Tilikausi':<25} {'Jätetty':<12}")
    print(f"  {'─'*45}")
    for i, p in enumerate(periods, 1):
        period = f"{p.period_start} – {p.period_end}"
        print(f"  {i:<4} {period:<25} {p.filing_date:<12}")


def print_statement(statement: dict, business_id: str, period_end: str) -> None:
    print(f"\n{'═'*52}")
    print(f"  TILINPÄÄTÖS  {business_id}  ({period_end})")
    print(f"{'═'*52}")

    figures = extract_key_figures(statement)

    if figures:
        print(f"\n  Keskeisimmät tunnusluvut:")
        print(f"  {'─'*45}")
        for label, value in figures.items():
            print(f"  {label:<22} {value}")
    else:
        print("\n  Rakenne-esikatselu (raw JSON, 5 ylintä kenttää):")
        for i, (k, v) in enumerate(statement.items()):
            if i >= 5:
                print("  ...")
                break
            print(f"  {k}: {str(v)[:80]}")

    print()
