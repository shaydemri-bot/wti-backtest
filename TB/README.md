
# WTI Strategy Lab (Streamlit)

Interactive app to explore a simple WTI strategy, backtest quickly, and visualize indicators & trades.

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Cloud
1. Push this folder to GitHub (no `.venv`).
2. Go to https://share.streamlit.io → New App → pick your repo → set `streamlit_app.py` as entry point.
3. If you need API keys later, use **App → Settings → Secrets**.

## Notes
- Data source: yfinance (`CL=F`).
- The app includes a Help tab and tooltips for each parameter.
