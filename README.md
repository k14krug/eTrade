# Stock Tracker App

## Description
A Flask-based web application for tracking my eTrade stock transactions. And also provide S&P 500 stock data. It includes redis/celery background tasks for updating stock prices and an admin dashboard for managing tasks.

.
├── README.md
├── init_db.py
├── instance
│   └── eTrade.sqlite
├── project
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── extensions.py
│   ├── forms.py
│   ├── models.py
│   ├── routes.py
│   ├── sp500
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── tasks.py
│   ├── sp500_hist_initializer.py
│   ├── static
│   │   └── js
│   │       └── components
│   │           └── StockPriceChartWithVolatility.js
│   ├── stock_data.py
│   ├── templates
│   │   ├── admin.html
│   │   ├── base.html
│   │   ├── cancel.html
│   │   ├── form.html
│   │   ├── login.html
│   │   ├── sp500
│   │   │   ├── sp500_overview.html
│   │   │   └── stock_detail.html
│   │   └── transactions
│   │       ├── _account_summary.html
│   │       └── transactions.html
│   ├── transactions
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── utils.py
│   └── utils.py
├── requirements.txt
└── run.py

10 directories, 32 files
