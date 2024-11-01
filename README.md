# Stock Tracker App

## Description
This Flask-based web app has two main components:
1) Tracking my eTrade stock transactions. 
2) Historical access to S&P 500 stock data going back to 2020
    Filterable web page to display current info on all stocks
    Web page has selection of queriers to filter the data, like P/E below 30% or price above 20 SMA
    Another page has detailed information about a stock including news and charts.

Planed New feature:
    Trend Anaysis - Develop an analysis engine to find trends. For example find the relationship one stocks prices has on another. Like if stock x opens down which other stock is most likely to have a gain that day.


.
├── README.md
├── init_db.py
├── instance
│   └── eTrade.sqlite
├── project
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── extensions.py
│   ├── forms.py
│   ├── models.py
│   ├── routes.py
│   ├── sp500
│   │   ├── QUERY_histdata.sql
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── tasks.py
│   ├── sp500_hist_initializer.py
│   ├── static
│   │   └── js
│   │       └── components
│   │           └── StockPriceChartWithVolatility.js
│   ├── stock_data.py
│   ├── templates
│   │   ├── admin.html
│   │   ├── base.html
│   │   ├── cancel.html
│   │   ├── form.html
│   │   ├── login.html
│   │   ├── sp500
│   │   │   ├── sp500_overview.html
│   │   │   ├── stock_detail.html
│   │   │   ├── watchlist.html
│   │   │   └── watchlist_detail.html
│   │   └── transactions
│   │       ├── _account_summary.html
│   │       ├── buy_opportunities.html
│   │       └── transactions.html
│   ├── transactions
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── utils.py
│   ├── update_sma.py
│   ├── utils.py
│   └── yahoofinance.py
├── requirements.txt
├── run.py
├── watchlist.json
└── wsgi.py

