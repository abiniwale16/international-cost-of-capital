"""International Cost of Capital App.

Compares a project's cost of equity, cost of debt and WACC in USD and in the
currency of a selected country. All formulas live in compute() so they can be
matched to the versions taught in class.
"""

import io
import re
from datetime import datetime, timezone

import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")

# ----------------------------------------------------------------------------
# Sources
# ----------------------------------------------------------------------------
BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = (
    "https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
    "full-report/statutory-corporate-income-tax-rates_440f9286.html"
    "#chapter-d1e2342-08e74a33fb"
)
TE_URL = "https://tradingeconomics.com/bonds"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"
DEFAULT_ERP = 0.065
DEFAULT_DEBT = 0.30

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)

# Country name aliases so the three sources line up.
ALIASES = {
    "US": "United States",
    "USA": "United States",
    "United States of America": "United States",
    "UK": "United Kingdom",
    "Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "Korea, Republic of": "South Korea",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "Czech Republic": "Czechia",
    "Slovak Republic": "Slovakia",
    "Hong Kong, China": "Hong Kong",
    "Hong Kong (China)": "Hong Kong",
    "China (People's Republic of)": "China",
    "Viet Nam": "Vietnam",
}

CURRENCY = {
    "United States": "USD", "United Kingdom": "GBP", "Japan": "JPY", "Canada": "CAD",
    "Australia": "AUD", "New Zealand": "NZD", "Switzerland": "CHF", "Sweden": "SEK",
    "Norway": "NOK", "Denmark": "DKK", "India": "INR", "China": "CNY", "Brazil": "BRL",
    "Mexico": "MXN", "South Korea": "KRW", "South Africa": "ZAR", "Indonesia": "IDR",
    "Singapore": "SGD", "Hong Kong": "HKD", "Poland": "PLN", "Turkey": "TRY",
    "Chile": "CLP", "Colombia": "COP", "Israel": "ILS", "Philippines": "PHP",
    "Thailand": "THB", "Malaysia": "MYR", "Vietnam": "VND", "Czechia": "CZK",
    "Hungary": "HUF", "Peru": "PEN", "Argentina": "ARS", "Saudi Arabia": "SAR",
    "Pakistan": "PKR", "Egypt": "EGP", "Nigeria": "NGN", "Kenya": "KES",
    "Taiwan": "TWD", "Russia": "RUB", "Romania": "RON", "Iceland": "ISK",
}
EURO_AREA = {
    "Germany", "France", "Italy", "Spain", "Netherlands", "Belgium", "Austria",
    "Portugal", "Greece", "Finland", "Ireland", "Slovakia", "Slovenia", "Lithuania",
    "Latvia", "Estonia", "Luxembourg", "Malta", "Cyprus", "Croatia",
}

# ----------------------------------------------------------------------------
# Cached fallbacks, used only if a live fetch fails. Always labeled in the app.
# ----------------------------------------------------------------------------
FALLBACK_BETAS = {
    # Approximate Damodaran US unlevered betas. Verify against betas.xls.
    "Software (System & Application)": 1.23,
    "Software (Internet)": 1.45,
    "Semiconductor": 1.45,
    "Computer Services": 0.95,
    "Drugs (Pharmaceutical)": 0.95,
    "Retail (General)": 0.85,
    "Auto & Truck": 1.05,
    "Utility (General)": 0.35,
    "Telecom. Services": 0.60,
    "Hotel/Gaming": 0.85,
}

FALLBACK_TAX = {
    # OECD Corporate Tax Statistics 2024, combined statutory CIT rates (%).
    # Approximate cache. Verify against the OECD table before relying on it.
    "United States": 25.77, "United Kingdom": 25.0, "Germany": 29.94, "France": 25.83,
    "Italy": 27.81, "Spain": 25.0, "Netherlands": 25.8, "Belgium": 25.0,
    "Austria": 23.0, "Portugal": 31.5, "Greece": 22.0, "Finland": 20.0,
    "Ireland": 12.5, "Japan": 29.74, "Canada": 26.14, "Australia": 30.0,
    "New Zealand": 28.0, "Switzerland": 19.61, "Sweden": 20.6, "Norway": 22.0,
    "Denmark": 22.0, "India": 25.17, "China": 25.0, "Brazil": 34.0, "Mexico": 30.0,
    "South Korea": 26.4, "South Africa": 27.0, "Indonesia": 22.0, "Singapore": 17.0,
    "Hong Kong": 16.5, "Poland": 19.0, "Turkey": 25.0, "Chile": 27.0,
    "Colombia": 35.0, "Israel": 23.0, "Philippines": 25.0, "Thailand": 20.0,
    "Malaysia": 24.0, "Vietnam": 20.0, "Argentina": 35.0, "Saudi Arabia": 20.0,
    "Czechia": 21.0, "Hungary": 9.0,
}

FALLBACK_YIELDS = {
    # Approximate 10-year yields (%). Stale cache, override with current values.
    "United States": 4.2, "United Kingdom": 4.5, "Germany": 2.7, "France": 3.4,
    "Italy": 3.5, "Spain": 3.2, "Netherlands": 2.9, "Belgium": 3.2, "Austria": 3.0,
    "Portugal": 3.1, "Greece": 3.4, "Finland": 2.9, "Ireland": 2.9, "Japan": 1.6,
    "Canada": 3.2, "Australia": 4.4, "New Zealand": 4.4, "Switzerland": 0.3,
    "Sweden": 2.5, "Norway": 3.9, "Denmark": 2.4, "India": 6.4, "China": 1.8,
    "Brazil": 13.5, "Mexico": 9.0, "South Korea": 2.9, "South Africa": 9.5,
    "Indonesia": 6.4, "Singapore": 2.1, "Hong Kong": 3.0, "Poland": 5.4,
    "Turkey": 30.0, "Chile": 5.6, "Colombia": 11.5, "Israel": 4.2,
    "Philippines": 6.2, "Thailand": 1.7, "Malaysia": 3.4, "Vietnam": 3.2,
}

FALLBACK_BBB_SPREAD = 0.0111  # Approximate. Verify against ratings.html.


def canon(name):
    name = re.sub(r"\s+", " ", str(name)).strip()
    name = re.sub(r"\s*\d+\s*Y$", "", name).strip()  # "Germany 10Y" -> "Germany"
    return ALIASES.get(name, name)


def currency_of(country):
    if country in EURO_AREA:
        return "EUR"
    return CURRENCY.get(country, "LCU")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def http_date(resp):
    lm = resp.headers.get("Last-Modified")
    if not lm:
        return None
    try:
        return pd.to_datetime(lm).strftime("%Y-%m-%d")
    except Exception:
        return lm


def to_rate(x):
    """Parse '1.11%', '1.11', 0.0111 or 25.8 into a decimal rate."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    s = str(x).replace(",", "").strip()
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return np.nan
    v = float(m.group(0))
    if "%" in s or abs(v) >= 1:
        return v / 100
    return v


# ----------------------------------------------------------------------------
# Data fetchers. Each returns a dict with data, as_of, status, note, fetched_at.
# ----------------------------------------------------------------------------
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_betas():
    try:
        r = requests.get(BETAS_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        sheets = pd.read_excel(io.BytesIO(r.content), sheet_name=None, header=None, engine="xlrd")
        for _, df in sheets.items():
            hdr = None
            for i in range(min(len(df), 60)):
                row = df.iloc[i].astype(str).str.strip().str.lower()
                if (row == "industry name").any() and row.str.startswith("unlevered beta").any():
                    hdr = i
                    break
            if hdr is None:
                continue
            labels = df.iloc[hdr].astype(str).str.strip().str.lower().tolist()
            ind_idx = labels.index("industry name")
            if "unlevered beta" in labels:
                ub_idx = labels.index("unlevered beta")
            else:
                ub_idx = next(i for i, c in enumerate(labels) if c.startswith("unlevered beta"))
            body = df.iloc[hdr + 1:]
            out = pd.DataFrame({
                "Industry": body.iloc[:, ind_idx].astype(str).str.strip(),
                "Unlevered beta": pd.to_numeric(body.iloc[:, ub_idx], errors="coerce"),
            }).dropna()
            out = out[~out["Industry"].str.lower().str.startswith("total market")]
            out = out[out["Industry"].str.lower() != "nan"].reset_index(drop=True)
            if out.empty:
                continue
            # Look for the "Date updated" cell near the top of the sheet.
            as_of = None
            top = df.iloc[:hdr]
            for _, row in top.iterrows():
                cells = row.tolist()
                for j, c in enumerate(cells):
                    if isinstance(c, str) and "updated" in c.lower():
                        for nxt in cells[j + 1:]:
                            if pd.notna(nxt):
                                as_of = pd.to_datetime(nxt, errors="coerce")
                                as_of = as_of.strftime("%Y-%m-%d") if pd.notna(as_of) else str(nxt)
                                break
                    if as_of:
                        break
                if as_of:
                    break
            return {
                "data": out, "as_of": as_of or http_date(r) or "see source",
                "status": "Live", "note": "", "fetched_at": now_utc(),
            }
        raise ValueError("Could not locate the industry table in betas.xls")
    except Exception as e:
        out = pd.DataFrame(
            {"Industry": list(FALLBACK_BETAS), "Unlevered beta": list(FALLBACK_BETAS.values())}
        )
        return {
            "data": out, "as_of": "cached approximation", "status": "Fallback",
            "note": f"Live fetch failed ({type(e).__name__}). Showing a small cached set.",
            "fetched_at": now_utc(),
        }


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_bbb_spread():
    try:
        r = requests.get(RATINGS_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        spread = None
        # The first table on the page is for large non-financial service firms.
        for t in tables:
            s = t.astype(str)
            hit = s.apply(lambda col: col.str.contains("Baa2/BBB", regex=False)).any(axis=1)
            if hit.any():
                row = s[hit].iloc[0].tolist()
                for cell in reversed(row):
                    v = to_rate(cell)
                    if pd.notna(v):
                        spread = v
                        break
                break
        if spread is None:
            raise ValueError("Baa2/BBB row not found")
        m = re.search(rf"({MONTHS})\s+(20\d\d)", r.text)
        as_of = f"{m.group(1)} {m.group(2)}" if m else (http_date(r) or "see source")
        return {"data": spread, "as_of": as_of, "status": "Live", "note": "", "fetched_at": now_utc()}
    except Exception as e:
        return {
            "data": FALLBACK_BBB_SPREAD, "as_of": "cached approximation", "status": "Fallback",
            "note": f"Live fetch failed ({type(e).__name__}).", "fetched_at": now_utc(),
        }


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_tax_rates():
    try:
        r = requests.get(OECD_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        for t in tables:
            t = t.copy()
            t.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
            name_col = next((c for c in t.columns if t[c].astype(str).str.contains("United States").any()), None)
            if name_col is None:
                continue
            num_cols = [c for c in t.columns if c != name_col and pd.to_numeric(t[c], errors="coerce").notna().mean() > 0.5]
            if not num_cols:
                continue
            combined = [c for c in num_cols if "combined" in c.lower()]
            rate_col = combined[0] if combined else num_cols[-1]
            rates = {}
            for name, val in zip(t[name_col], t[rate_col]):
                v = pd.to_numeric(val, errors="coerce")
                if pd.notna(v):
                    rates[canon(name)] = v / 100 if v > 1 else v
            if "United States" in rates:
                return {"data": rates, "as_of": "OECD Corporate Tax Statistics 2024", "status": "Live",
                        "note": "", "fetched_at": now_utc()}
        raise ValueError("No tax table found on the OECD page")
    except Exception as e:
        return {
            "data": {k: v / 100 for k, v in FALLBACK_TAX.items()},
            "as_of": "OECD Corporate Tax Statistics 2024 (cached)", "status": "Fallback",
            "note": f"The OECD page could not be parsed ({type(e).__name__}). Using a cached copy of the 2024 combined statutory rates.",
            "fetched_at": now_utc(),
        }


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_yields():
    try:
        r = requests.get(TE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        tables = pd.read_html(io.StringIO(r.text))
        ylds, dates = {}, {}
        for t in tables:
            cols = [str(c) for c in t.columns]
            t.columns = cols
            ycol = next((c for c in cols if c.lower() == "yield"), None)
            if ycol is None:
                continue
            ncol = cols[0]
            dcol = next((c for c in cols if c.lower() == "date"), None)
            for _, row in t.iterrows():
                name = canon(row[ncol])
                v = pd.to_numeric(row[ycol], errors="coerce")
                if pd.isna(v) or not name or name.lower() == "nan":
                    continue
                ylds[name] = v / 100
                dates[name] = str(row[dcol]) if dcol else ""
        if "United States" not in ylds:
            raise ValueError("US 10Y not found")
        return {"data": ylds, "dates": dates, "as_of": "Trading Economics, latest quote",
                "status": "Live", "note": "", "fetched_at": now_utc()}
    except Exception as e:
        return {
            "data": {k: v / 100 for k, v in FALLBACK_YIELDS.items()}, "dates": {},
            "as_of": "cached approximation", "status": "Fallback",
            "note": f"Trading Economics fetch failed ({type(e).__name__}). Yields are stale; override them in the sidebar.",
            "fetched_at": now_utc(),
        }


# ----------------------------------------------------------------------------
# Finance. Every formula is here.
# ----------------------------------------------------------------------------
METHODS = {
    "convert": "Convert USD rates with the yield ratio",
    "local": "Local CAPM with the foreign risk-free rate",
}


def compute(beta_u, tax, debt_share, erp, y_us, y_f, spread_usd, spread_f_override=None, method="convert"):
    """Return a dict of USD and foreign-currency results.

    beta_u              unlevered beta
    tax                 project tax rate (one rate used in both currencies)
    debt_share          D / (D + E)
    erp                 equity risk premium
    y_us, y_f           10-year government yields, US and selected country
    spread_usd          USD BBB spread
    spread_f_override   foreign BBB spread if the user overrides it, else None
    method              "convert" or "local" (cost of equity in foreign currency)
    """
    d = debt_share
    e = 1 - d
    de = d / e
    beta_l = beta_u * (1 + (1 - tax) * de)  # Hamada relevering

    # USD
    ke_usd = y_us + beta_l * erp
    kd_usd = y_us + spread_usd
    wacc_usd = e * ke_usd + d * kd_usd * (1 - tax)

    # Foreign currency
    ratio = (1 + y_f) / (1 + y_us)
    if method == "local":
        ke_f = y_f + beta_l * erp
    else:
        ke_f = (1 + ke_usd) * ratio - 1
    spread_f_auto = (1 + kd_usd) * ratio - 1 - y_f  # = spread_usd * ratio
    spread_f = spread_f_auto if spread_f_override is None else spread_f_override
    kd_f = y_f + spread_f
    wacc_f = e * ke_f + d * kd_f * (1 - tax)

    return {
        "beta_l": beta_l, "de": de,
        "usd": {"rf": y_us, "ke": ke_usd, "spread": spread_usd, "kd": kd_usd,
                "kd_at": kd_usd * (1 - tax), "wacc": wacc_usd},
        "fc": {"rf": y_f, "ke": ke_f, "spread": spread_f, "kd": kd_f,
               "kd_at": kd_f * (1 - tax), "wacc": wacc_f},
        "spread_f_auto": spread_f_auto,
    }


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%"


# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
st.title("International Cost of Capital")
st.caption("Cost of equity, cost of debt and WACC for a project, in USD and in the currency of a selected country.")

with st.sidebar:
    if st.button("Refresh data", width="stretch", help="Clear the cache and fetch all sources again"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Fetching data..."):
    betas = fetch_betas()
    bbb = fetch_bbb_spread()
    tax = fetch_tax_rates()
    yields = fetch_yields()

beta_df = betas["data"]
tax_rates = tax["data"]
yld = yields["data"]

countries = sorted(set(yld))
if DEFAULT_COUNTRY not in countries:
    countries = [DEFAULT_COUNTRY] + countries
industries = beta_df["Industry"].tolist()

# ----------------------------------------------------------------------------
# Sidebar inputs
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("Project")
    industry = st.selectbox(
        "Industry", industries,
        index=industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0,
    )
    country = st.selectbox("Target country", countries, index=countries.index(DEFAULT_COUNTRY))
    ccy = currency_of(country)

    erp = st.number_input("Equity risk premium (%)", value=DEFAULT_ERP * 100, step=0.25, format="%.2f") / 100
    debt_share = st.slider("Target debt share, D/(D+E) (%)", 0.0, 90.0, DEFAULT_DEBT * 100, 1.0) / 100

    tax_choice = st.radio("Project tax rate", ["U.S. tax rate", f"{country} tax rate"], index=0)
    method_key = st.radio(
        "Foreign-currency cost of equity", list(METHODS), format_func=METHODS.get, index=0,
        help="Pick the version taught in class. Debt always converts the USD BBB spread with the yield ratio unless you override it.",
    )

    st.header("Manual overrides")

    def override_pct(label, fetched, key):
        on = st.checkbox(f"Override {label}", key=f"{key}_on")
        if not on:
            return fetched, False
        v = st.number_input(f"{label} (%)", value=round(float(fetched) * 100, 4), step=0.05,
                            format="%.3f", key=f"{key}_val")
        return v / 100, True

    fetched_beta = float(beta_df.loc[beta_df["Industry"] == industry, "Unlevered beta"].iloc[0])
    if st.checkbox("Override unlevered beta", key=f"beta_on_{industry}"):
        beta_u = st.number_input("Unlevered beta", value=round(fetched_beta, 4), step=0.01,
                                 format="%.4f", key=f"beta_val_{industry}")
        beta_ovr = True
    else:
        beta_u, beta_ovr = fetched_beta, False

    us_tax_fetched = tax_rates.get("United States", FALLBACK_TAX["United States"] / 100)
    f_tax_fetched = tax_rates.get(country)
    if f_tax_fetched is None:
        st.warning(f"No OECD rate found for {country}. Using the U.S. rate until you override it.")
        f_tax_fetched = us_tax_fetched

    t_us, t_us_ovr = override_pct("U.S. tax rate", us_tax_fetched, "tax_us")
    t_f, t_f_ovr = override_pct(f"{country} tax rate", f_tax_fetched, f"tax_f_{country}")
    s_usd, s_usd_ovr = override_pct("USD BBB spread", bbb["data"], "spread_usd")
    y_us, y_us_ovr = override_pct("U.S. 10Y yield", yld.get("United States", FALLBACK_YIELDS["United States"] / 100), "y_us")
    y_f_fetched = yld.get(country, y_us) if country != "United States" else yld.get("United States")
    y_f, y_f_ovr = override_pct(f"{country} 10Y yield", y_f_fetched, f"y_f_{country}")
    if country == "United States" and not y_f_ovr:
        y_f = y_us  # keep the two legs identical unless the user overrides

    # Foreign spread: auto unless switched on
    preview = compute(beta_u, t_us, debt_share, erp, y_us, y_f, s_usd, None, method_key)
    s_f_on = st.checkbox(f"Override {ccy} BBB spread", key=f"spread_f_on_{country}")
    if s_f_on:
        s_f_override = st.number_input(f"{ccy} BBB spread (%)", value=round(preview["spread_f_auto"] * 100, 4),
                                       step=0.05, format="%.3f", key=f"spread_f_val_{country}") / 100
    else:
        s_f_override = None
        st.caption(f"Auto {ccy} BBB spread: {pct(preview['spread_f_auto'], 3)}")

project_tax = t_us if tax_choice.startswith("U.S.") else t_f

# ----------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------
res = compute(beta_u, project_tax, debt_share, erp, y_us, y_f, s_usd, s_f_override, method_key)
u, f = res["usd"], res["fc"]
fc_label = f"{ccy} ({country})"

st.subheader(f"{industry}: USD vs {fc_label}")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**USD**")
    a, b, c = st.columns(3)
    a.metric("Cost of equity", pct(u["ke"]))
    b.metric("After-tax cost of debt", pct(u["kd_at"]))
    c.metric("WACC", pct(u["wacc"]))
with c2:
    st.markdown(f"**{fc_label}**")
    a, b, c = st.columns(3)
    a.metric("Cost of equity", pct(f["ke"]))
    b.metric("After-tax cost of debt", pct(f["kd_at"]))
    c.metric("WACC", pct(f["wacc"]))

results = pd.DataFrame(
    {
        "USD": [pct(u["rf"]), f"{beta_u:.4f}", f"{res['beta_l']:.4f}", pct(erp), pct(u["ke"]),
                pct(u["spread"], 3), pct(u["kd"]), pct(project_tax), pct(u["kd_at"]),
                pct(1 - debt_share, 1), pct(debt_share, 1), pct(u["wacc"])],
        fc_label: [pct(f["rf"]), f"{beta_u:.4f}", f"{res['beta_l']:.4f}", pct(erp), pct(f["ke"]),
                   pct(f["spread"], 3), pct(f["kd"]), pct(project_tax), pct(f["kd_at"]),
                   pct(1 - debt_share, 1), pct(debt_share, 1), pct(f["wacc"])],
    },
    index=["10Y government yield (risk-free)", "Unlevered beta", "Levered beta", "Equity risk premium",
           "Cost of equity", "BBB spread", "Pre-tax cost of debt", "Project tax rate",
           "After-tax cost of debt", "Equity weight", "Debt weight", "WACC"],
)
st.dataframe(results, width="stretch")

# ----------------------------------------------------------------------------
# Data sources
# ----------------------------------------------------------------------------
st.subheader("Data sources")
y_us_date = yields.get("dates", {}).get("United States", "")
y_f_date = yields.get("dates", {}).get(country, "")


def status(base, overridden):
    return "Manual override" if overridden else base


sources = pd.DataFrame([
    ["Unlevered beta", f"{beta_u:.4f}", "Damodaran, betas.xls (US)", betas["as_of"], status(betas["status"], beta_ovr), BETAS_URL],
    ["USD BBB spread (Baa2/BBB, large non-financial)", pct(s_usd, 3), "Damodaran, ratings.html", bbb["as_of"], status(bbb["status"], s_usd_ovr), RATINGS_URL],
    ["U.S. corporate tax rate", pct(t_us), "OECD Corporate Tax Statistics", tax["as_of"], status(tax["status"], t_us_ovr), OECD_URL],
    [f"{country} corporate tax rate", pct(t_f), "OECD Corporate Tax Statistics", tax["as_of"], status(tax["status"], t_f_ovr), OECD_URL],
    ["U.S. 10Y yield", pct(y_us, 3), "Trading Economics", y_us_date or yields["as_of"], status(yields["status"], y_us_ovr), TE_URL],
    [f"{country} 10Y yield", pct(y_f, 3), "Trading Economics", y_f_date or yields["as_of"], status(yields["status"], y_f_ovr), TE_URL],
    [f"{ccy} BBB spread", pct(f["spread"], 3), "Calculated" if s_f_override is None else "User input", "", "Manual override" if s_f_override is not None else "Auto", ""],
], columns=["Input", "Value", "Source", "As of", "Status", "Link"])
st.dataframe(sources, width="stretch", hide_index=True,
             column_config={"Link": st.column_config.LinkColumn("Link")})

st.caption(
    f"Last fetched: betas {betas['fetched_at']} | spread {bbb['fetched_at']} | "
    f"tax {tax['fetched_at']} | yields {yields['fetched_at']}. Use Refresh data in the sidebar to fetch again."
)
for src in (betas, bbb, tax, yields):
    if src["status"] != "Live" and src["note"]:
        st.warning(src["note"])

# ----------------------------------------------------------------------------
# Assumptions
# ----------------------------------------------------------------------------
with st.expander("Main assumptions and formulas", expanded=False):
    st.markdown(
        f"""
- The project uses the industry's **US unlevered beta**, relevered at the target debt share with the project tax rate (Hamada).
- The **10-year government bond yield** is the risk-free rate in each currency.
- The **same project tax rate, debt share and equity risk premium** apply in both currencies. The tax rate is currently the **{tax_choice}**.
- USD cost of debt is the US yield plus the **Baa2/BBB spread** for large non-financial firms.
- Foreign-currency rates come from USD rates through the ratio of gross yields, (1 + y_F)/(1 + y_US), which treats the yield gap as expected inflation or depreciation.
- Data are the latest available from each source. Cached values appear only when a live fetch fails and are flagged above.
"""
    )
    st.latex(r"\beta_L = \beta_U\left[1 + (1-t)\frac{D}{E}\right]")
    st.latex(r"k_E^{USD} = y_{US} + \beta_L \times ERP")
    if method_key == "convert":
        st.latex(r"k_E^{FC} = (1+k_E^{USD})\frac{1+y_F}{1+y_{US}} - 1")
    else:
        st.latex(r"k_E^{FC} = y_F + \beta_L \times ERP")
    st.latex(r"k_D^{USD} = y_{US} + s_{USD}, \qquad s_{FC}^{auto} = (1+k_D^{USD})\frac{1+y_F}{1+y_{US}} - 1 - y_F")
    st.latex(r"k_D^{FC} = y_F + s_{FC}, \qquad WACC = \frac{E}{V}k_E + \frac{D}{V}k_D(1-t)")

    st.markdown("**Calculation trace with current inputs**")
    st.code(
        f"D/E           = {debt_share:.4f} / {1 - debt_share:.4f} = {res['de']:.6f}\n"
        f"Levered beta  = {beta_u:.4f} x (1 + (1 - {project_tax:.4f}) x {res['de']:.6f}) = {res['beta_l']:.6f}\n"
        f"ke USD        = {y_us:.6f} + {res['beta_l']:.6f} x {erp:.4f} = {u['ke']:.6f}\n"
        f"kd USD        = {y_us:.6f} + {s_usd:.6f} = {u['kd']:.6f}\n"
        f"WACC USD      = {1 - debt_share:.4f} x {u['ke']:.6f} + {debt_share:.4f} x {u['kd']:.6f} x (1 - {project_tax:.4f}) = {u['wacc']:.6f}\n"
        f"Yield ratio   = (1 + {y_f:.6f}) / (1 + {y_us:.6f}) = {(1 + y_f) / (1 + y_us):.6f}\n"
        f"ke {ccy:<10} = {f['ke']:.6f}\n"
        f"spread {ccy:<6} = {f['spread']:.6f}\n"
        f"kd {ccy:<10} = {f['kd']:.6f}\n"
        f"WACC {ccy:<8} = {f['wacc']:.6f}",
        language="text",
    )

# ----------------------------------------------------------------------------
# Built-in checks
# ----------------------------------------------------------------------------
with st.expander("Verification checks", expanded=False):
    tol = 1e-12
    eq = compute(beta_u, project_tax, debt_share, erp, y_us, y_us, s_usd, None, method_key)
    zero = compute(beta_u, project_tax, 0.0, erp, y_us, y_f, s_usd, s_f_override, method_key)
    alt_override = (s_f_override if s_f_override is not None else res["spread_f_auto"]) + 0.01
    ovr = compute(beta_u, project_tax, debt_share, erp, y_us, y_f, s_usd, alt_override, method_key)
    checks = pd.DataFrame([
        ["Equal yields give equal USD and foreign results (spread override off)",
         all(abs(eq["usd"][k] - eq["fc"][k]) < tol for k in ("ke", "kd", "wacc"))],
        ["Zero debt makes WACC equal cost of equity (both currencies)",
         abs(zero["usd"]["wacc"] - zero["usd"]["ke"]) < tol and abs(zero["fc"]["wacc"] - zero["fc"]["ke"]) < tol],
        ["Overriding the foreign spread leaves USD results unchanged",
         all(abs(ovr["usd"][k] - res["usd"][k]) < tol for k in ("ke", "kd", "wacc"))],
    ], columns=["Check", "Pass"])
    st.dataframe(checks, width="stretch", hide_index=True)
    st.caption("These run on the current inputs. You still need one independent check in a spreadsheet or calculator.")

# ----------------------------------------------------------------------------
# All-industry comparison
# ----------------------------------------------------------------------------
st.subheader("All-industry comparison")
rows = []
for ind, bu in zip(beta_df["Industry"], beta_df["Unlevered beta"]):
    b = beta_u if (ind == industry and beta_ovr) else float(bu)
    r_ = compute(b, project_tax, debt_share, erp, y_us, y_f, s_usd, s_f_override, method_key)
    rows.append({
        "Industry": ind, "Unlevered beta": b, "Levered beta": r_["beta_l"],
        "Cost of equity USD": r_["usd"]["ke"], f"Cost of equity {ccy}": r_["fc"]["ke"],
        "WACC USD": r_["usd"]["wacc"], f"WACC {ccy}": r_["fc"]["wacc"],
    })
all_ind = pd.DataFrame(rows).sort_values("WACC USD", ascending=False).reset_index(drop=True)

pct_cols = [c for c in all_ind.columns if c.startswith(("Cost", "WACC"))]
st.dataframe(
    all_ind.style.format({**{c: "{:.2%}" for c in pct_cols}, "Unlevered beta": "{:.3f}", "Levered beta": "{:.3f}"})
    .apply(lambda r: ["background-color: rgba(255, 200, 0, 0.25)" if r["Industry"] == industry else "" for _ in r], axis=1),
    width="stretch", height=400,
)

chart_df = all_ind.melt(id_vars="Industry", value_vars=["WACC USD", f"WACC {ccy}"], var_name="Series", value_name="WACC")
chart = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        y=alt.Y("Industry:N", sort=all_ind["Industry"].tolist(), title=None),
        x=alt.X("WACC:Q", axis=alt.Axis(format="%"), title="WACC"),
        color=alt.Color("Series:N", title=None),
        yOffset="Series:N",
        tooltip=["Industry", "Series", alt.Tooltip("WACC:Q", format=".2%")],
    )
    .properties(height=max(300, 22 * len(all_ind)))
)
with st.expander("WACC chart, all industries", expanded=False):
    st.altair_chart(chart, width="stretch")

# ----------------------------------------------------------------------------
# Downloads
# ----------------------------------------------------------------------------
st.subheader("Download")
inputs = pd.DataFrame({
    "Item": ["Industry", "Country", "Currency", "Project tax rate choice", "Foreign cost of equity method",
             "Unlevered beta", "U.S. tax rate", f"{country} tax rate", "Project tax rate", "Equity risk premium",
             "Debt share", "U.S. 10Y yield", f"{country} 10Y yield", "USD BBB spread", f"{ccy} BBB spread",
             f"{ccy} spread mode", "Generated"],
    "Value": [industry, country, ccy, tax_choice, METHODS[method_key], beta_u, t_us, t_f, project_tax, erp,
              debt_share, y_us, y_f, s_usd, f["spread"], "override" if s_f_override is not None else "auto", now_utc()],
})
out = pd.DataFrame({
    "Metric": ["Risk-free rate", "Levered beta", "Cost of equity", "BBB spread", "Pre-tax cost of debt",
               "After-tax cost of debt", "WACC"],
    "USD": [u["rf"], res["beta_l"], u["ke"], u["spread"], u["kd"], u["kd_at"], u["wacc"]],
    ccy: [f["rf"], res["beta_l"], f["ke"], f["spread"], f["kd"], f["kd_at"], f["wacc"]],
})
buf = io.StringIO()
buf.write("INPUTS\n")
inputs.to_csv(buf, index=False)
buf.write("\nRESULTS\n")
out.to_csv(buf, index=False)
buf.write("\nSOURCES\n")
sources.to_csv(buf, index=False)

d1, d2 = st.columns(2)
d1.download_button("Download results (CSV)", buf.getvalue(), file_name="cost_of_capital_results.csv",
                   mime="text/csv", width="stretch")
d2.download_button("Download all-industry comparison (CSV)", all_ind.to_csv(index=False),
                   file_name="all_industry_comparison.csv", mime="text/csv", width="stretch")
