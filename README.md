# International Cost of Capital App

A Streamlit app that compares a project's cost of equity, cost of debt and WACC in USD and in the currency of any selected country.

## Data sources

| Input | Source |
|---|---|
| Industry unlevered betas (US) | [Damodaran, betas.xls](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) |
| USD BBB spread (Baa2/BBB, large non-financial service firms) | [Damodaran, ratings.html](https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html) |
| Corporate tax rates | [OECD Corporate Tax Statistics 2024](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) |
| 10-year government bond yields | [Trading Economics](https://tradingeconomics.com/bonds) |

The app shows the source, date and status (Live, Fallback or Manual override) of every input. **Refresh data** clears the cache and fetches again. If a live fetch fails, the app uses a clearly flagged cached value, which can be overwritten in the sidebar.

## Features

- Select an industry and a target country
- Adjust the equity risk premium and target debt share
- Switch the project tax rate between the U.S. and the selected country
- Override the unlevered beta, both tax rates, the USD BBB spread and both government yields
- Override the foreign-currency BBB spread, or leave it off to use the auto calculation
- Side-by-side USD and foreign-currency results, an assumptions panel with a calculation trace, built-in verification checks, an all-industry comparison and CSV downloads

**Defaults:** Software (System & Application), United States, U.S. tax rate, 6.5% equity risk premium, 30% debt.

## Formulas

All formulas are in the `compute()` function in `app.py`.

- Levered beta: `βL = βU × [1 + (1 − t) × D/E]`
- USD cost of equity: `kE(USD) = y_US + βL × ERP`
- Foreign cost of equity (selectable):
  - Yield-ratio conversion: `kE(FC) = (1 + kE(USD)) × (1 + y_F)/(1 + y_US) − 1`
  - Local CAPM: `kE(FC) = y_F + βL × ERP`
- USD cost of debt: `kD(USD) = y_US + s_USD`
- Auto foreign spread: `s_FC = (1 + kD(USD)) × (1 + y_F)/(1 + y_US) − 1 − y_F`
- Foreign cost of debt: `kD(FC) = y_F + s_FC`
- WACC: `E/V × kE + D/V × kD × (1 − t)`

## Verification

The app checks on the current inputs that:

1. Equal government yields give equal USD and foreign results when the foreign spread override is off
2. Zero debt makes WACC equal the cost of equity
3. Overriding the foreign spread leaves USD results unchanged

## Run

Deploy on [Streamlit Community Cloud](https://share.streamlit.io) with Python 3.12 and `app.py` as the main file. To run locally:

```
pip install -r requirements.txt
streamlit run app.py
```
