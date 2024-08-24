# app.py is the main file for the application. It contains the Flask application and the routes for the application.
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Transactions, Position, User
from forms import LoginForm, RegistrationForm, TransactionForm
from config import Config
import yfinance as yf
import csv
import sys
from datetime import datetime, time, timedelta

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_latest_price(symbol):
    ticker = yf.Ticker(symbol)
    info = ticker.info
    if 'currentPrice' in info:
        latest_price = info['currentPrice']
        return latest_price
    else:
        todays_data = ticker.history(period='1d')
        if not todays_data.empty:
            latest_price = todays_data['Close'].iloc[0]
            return latest_price
        else:
            return None

@app.route('/')
@login_required
def home():
    return redirect(url_for('transactions'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', title='Sign In', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, 
                    starting_balance=form.starting_balance.data)
        user.password_hash = generate_password_hash(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    form = TransactionForm()
    if form.validate_on_submit():
        try:
            transaction_date = form.date.data
            transaction_date = datetime.combine(transaction_date, time.min)
            transaction_type = form.transaction_type.data
            symbol = form.symbol.data.upper()
            quantity = form.quantity.data
            price = form.price.data
            commission = form.commission.data
            taf_fee = form.taf_fee.data
            transaction_value = (quantity * price) - commission - taf_fee

            # Find the most recent transaction before or on the current transaction date. 
            previous_transaction = Transactions.query.filter(
                Transactions.user_id == current_user.id,
                Transactions.date <= transaction_date
            ).order_by(Transactions.date.desc(), Transactions.id.desc()).first()
            
            # Calculate cash balance
            if previous_transaction:
                cash_balance = previous_transaction.cash_balance
            else:
                cash_balance = current_user.starting_balance
            
            # Update cash balance based on transaction type
            if transaction_type == 'buy':
                cash_balance -= transaction_value
            elif transaction_type in ['sell', 'div']:
                cash_balance += transaction_value

            # Calculate stock value on the transaction date, excluding current transaction if it's a sell
            stock_value = calculate_stock_value_on_date(
                current_user.id, 
                transaction_date, 
                transaction_type=transaction_type, 
                transaction_symbol=symbol, 
                transaction_quantity=quantity
            )

            # Update stock value based on transaction type
            if transaction_type == 'buy':
                stock_value += transaction_value
            elif transaction_type == 'sell':
                pass # exclude the value of the shares being sold. This was already done in calculate_stock_value_on_date
                #stock_value -= transaction_value

            # Create new transaction
            new_transaction = Transactions(
                date=transaction_date,
                transaction_type=transaction_type,
                symbol=symbol,
                quantity=quantity,
                price=price,
                commission=commission,
                cash_balance=cash_balance,
                stock_value=stock_value,
                user_id=current_user.id
            )
            db.session.add(new_transaction)

            # Update or create position
            update_position(current_user.id, symbol, quantity, price, transaction_type)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Transaction added successfully.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    
    if form.errors:
        return jsonify({'success': False, 'message': 'Validation error', 'errors': form.errors}), 400

        #flash('Transaction added successfully.', 'success')
        #return redirect(url_for('transactions'))

    # Fetch all transactions for the current user, sorted by date and then id
    all_transactions   = Transactions.query.filter_by(user_id=current_user.id).order_by(Transactions.date.desc(), Transactions.id.desc()).all()
    latest_transaction = Transactions.query.filter_by(user_id=current_user.id).order_by(Transactions.date.desc(), Transactions.id.desc()).first()
    
    cash_balance = latest_transaction.cash_balance if latest_transaction else current_user.starting_balance
    total_stock_value = latest_transaction.stock_value if latest_transaction else 0

    # Fetch current positions and active transaction IDs
    positions, active_transaction_ids, total_current_value, position_gain_loss= get_current_positions(current_user.id)
    total_account_value = cash_balance + total_current_value
    total_gain_loss = total_account_value - current_user.starting_balance   
    position_gain_loss_percentage = (position_gain_loss / (total_account_value - position_gain_loss)) * 100 if (total_account_value - total_gain_loss) != 0 else 0
    overall_gain_loss_percentage = ((total_account_value - current_user.starting_balance) / current_user.starting_balance) * 100

    # Calculate total value and gain/loss for each transaction
    for transaction in all_transactions:
        transaction.total_value = transaction.cash_balance + transaction.stock_value
        transaction.gain_loss = transaction.total_value - current_user.starting_balance
        
        # Calculate gain/loss percentage
        if current_user.starting_balance != 0:
            transaction.gain_loss_percentage = (transaction.gain_loss / current_user.starting_balance) * 100
        else:
            transaction.gain_loss_percentage = 0
        
        # Get current price for active positions
        if transaction.id in active_transaction_ids:
            transaction.current_price = get_latest_price(transaction.symbol)
        else:
            transaction.current_price = None
        # Calculate transaction amount
        if transaction.transaction_type == 'sell':
            transaction.taf_fee = round(transaction.quantity * 0.0001666, 2)
        else:
            transaction.taf_fee = 0.00
        commission = transaction.commission if transaction.commission is not None else 0.0
        transaction.transaction_amount = transaction.quantity * transaction.price - commission - transaction.taf_fee
        print(f"  {transaction.symbol} Transaction amount: {transaction.transaction_amount} = {transaction.quantity} * {transaction.price} - {commission} - {transaction.taf_fee}")


    return render_template('transactions.html', 
                           form=form, 
                           transactions=all_transactions, 
                           positions=positions,
                           show_all=request.args.get('show_all', 'true') == 'true',
                           active_transaction_ids=active_transaction_ids,
                           cash_balance=cash_balance,
                           total_stock_value=total_stock_value,
                           total_account_value=total_account_value,
                           total_current_value=total_current_value,
                           total_gain_loss=total_account_value - current_user.starting_balance,
                           overall_gain_loss_percentage=overall_gain_loss_percentage,
                           position_gain_loss=position_gain_loss,
                           position_gain_loss_percentage=position_gain_loss_percentage
                           )

@app.route('/buy_opportunities')
@login_required
def buy_opportunities():
    opportunities = get_buy_opportunities(current_user.id)
    return render_template('buy_opportunities.html', opportunities=opportunities)

def calculate_stock_value_on_date(user_id, date, transaction_type=None, transaction_symbol=None, transaction_quantity=0):
  """Calculates the total value of all stocks held by a user on a given date,
  excluding the value of shares being sold.

  Args:
    user_id: The ID of the user.
    date: The date for which to calculate the stock value.
    sell_symbol: The symbol of the stock being sold (optional).
    sell_quantity: The quantity of shares being sold (optional).

  Returns:
    The total value of all stocks held by the user on the given date, excluding the
    value of the shares being sold.
  """

  total_value = 0

  # Get all positions for the user
  positions = Position.query.filter_by(user_id=user_id).all()

  for position in positions:
    #print(f"  CSVOD - Total positions {len(positions)}, Processing position: {position.symbol} - {position.quantity} shares")
    if transaction_type == 'sell' and position.symbol == transaction_symbol:
      # Adjust quantity for the stock being sold
      remaining_quantity = max(position.quantity - transaction_quantity, 0)
      #print(f"    CSVOD - Adjusted position quantity for selling stock: {remaining_quantity}")
    else:
      remaining_quantity = position.quantity
      #print(f"    CSVOD - Position quantity: {remaining_quantity}")

    # Get the historical price for the stock on the given date
    historical_price = get_historical_price(position.symbol, date)
    if historical_price:
      total_value += remaining_quantity * historical_price
    #print(f"    CSVOD - Historical price for {position.symbol} on {date}: {historical_price} for a value of {remaining_quantity * historical_price}")
  
  #print(f"    CSVOD - Total value of all stock positions: {total_value}")
  return total_value

@app.route('/test')
def index():
    return render_template('test.html')

def get_historical_price(symbol, date):
    # Use yfinance to get historical price
    stock = yf.Ticker(symbol)
    historical_data = stock.history(start=date, end=date + timedelta(days=1))
    if not historical_data.empty:
        return historical_data['Close'].iloc[0]
    return None

def update_position(user_id, symbol, quantity, price, transaction_type):
    position = Position.query.filter_by(user_id=user_id, symbol=symbol).first()
    print(f"  Updating positions, current number of positions: {len(Position.query.all())}")
    if position:
        if transaction_type == 'buy':
            print(f"    UP - Adding to buy position: {position.symbol} - {position.quantity} shares, average price: {position.average_price}")
            total_cost = (position.quantity * position.average_price) + (quantity * price)
            position.quantity += quantity
            position.average_price = total_cost / position.quantity
        elif transaction_type == 'sell':
            print(f"    UP - Reducing sell position: {position.symbol} - {position.quantity} shares, average price: {position.average_price}")
            position.quantity -= quantity
            if position.quantity <= 0:
                print(f"      UP - Deleting position: {position.symbol}")
                db.session.delete(position)
    elif transaction_type == 'buy':
        new_position = Position(user_id=user_id, symbol=symbol, quantity=quantity, average_price=price)
        print(f"    UP - Adding new position: {new_position.symbol} - {new_position.quantity} shares, average price: {new_position.average_price} for total value of {new_position.quantity * new_position.average_price}")
        db.session.add(new_position)

def get_current_positions(user_id):
    positions = Position.query.filter_by(user_id=user_id).all()
    position_data = []
    total_current_value = 0
    position_gain_loss = 0
    active_transaction_ids = set()

    for position in positions:
        current_price = get_latest_price(position.symbol)
        if current_price:
            current_value = position.quantity * current_price
            gain_loss = current_value - (position.quantity * position.average_price)
            gain_loss_percentage = (gain_loss / (position.quantity * position.average_price)) * 100 if (position.quantity * position.average_price) != 0 else 0
            total_cost = position.quantity * position.average_price
            total_current_value += current_value
            position_gain_loss += gain_loss

            # Get the transactions that make up this position
            transactions = Transactions.query.filter_by(
                user_id=user_id,
                symbol=position.symbol
            ).order_by(Transactions.date.desc(), Transactions.id.desc()).all()
            
            remaining_quantity = position.quantity
            for transaction in transactions:
                if remaining_quantity > 0:
                    if transaction.transaction_type == 'buy':
                        if transaction.quantity <= remaining_quantity:
                            active_transaction_ids.add(transaction.id)
                            remaining_quantity -= transaction.quantity
                        else:
                            active_transaction_ids.add(transaction.id)
                            break
                    elif transaction.transaction_type == 'sell':
                        remaining_quantity += transaction.quantity
                else:
                    break
            
            position_data.append({
                'symbol': position.symbol,
                'quantity': position.quantity,
                'average_price': position.average_price,
                'current_price': current_price,
                'current_value': current_value,
                'gain_loss': gain_loss,
                'gain_loss_percentage': gain_loss_percentage,
                'total_cost': total_cost
            })

    return position_data, active_transaction_ids, total_current_value, position_gain_loss

def get_buy_opportunities(user_id):
    opportunities = []
    
    # Get all unique symbols for the user
    symbols = db.session.query(Transactions.symbol).filter_by(user_id=user_id).distinct().all()
    symbols = [symbol[0] for symbol in symbols]
    
    for symbol in symbols:
        # Get the last buy transaction for this symbol
        last_buy = Transactions.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            transaction_type='buy'
        ).order_by(Transactions.date.desc()).first()
        
        if last_buy:
            current_price = get_latest_price(symbol)
            if current_price and current_price < last_buy.price:
                # Get P/E ratio
                ticker = yf.Ticker(symbol)
                pe_ratio = ticker.info.get('trailingPE', None)
                
                opportunities.append({
                    'symbol': symbol,
                    'last_buy_price': last_buy.price,
                    'current_price': current_price,
                    'price_difference': last_buy.price - current_price,
                    'price_difference_percentage': ((last_buy.price - current_price) / last_buy.price) * 100,
                    'pe_ratio': pe_ratio
                })
    
    # Sort opportunities by price difference percentage (descending)
    opportunities.sort(key=lambda x: x['price_difference_percentage'], reverse=True)
    
    return opportunities

from flask import request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ... (existing imports and code)

@app.route('/sp500', methods=['GET'])
def sp500():
    # Get S&P 500 symbols
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
    symbols = sp500['Symbol'].tolist()

    # Get current date and date from a day ago
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)

    # Fetch data for all symbols
    data = yf.download(symbols, start=start_date, end=end_date)

    # Prepare the data for the table
    table_data = []
    for symbol in symbols:
        try:
            current_price = data['Close'][symbol].iloc[-1]
            previous_price = data['Close'][symbol].iloc[0]
            gain_loss = current_price - previous_price
            gain_loss_percentage = (gain_loss / previous_price) * 100

            table_data.append({
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'previous_price': round(previous_price, 2),
                'gain_loss': round(gain_loss, 2),
                'gain_loss_percentage': round(gain_loss_percentage, 2)
            })
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")

    # Sorting
    sort_by = request.args.get('sort_by', 'symbol')
    sort_order = request.args.get('sort_order', 'asc')
    
    table_data = sorted(table_data, key=lambda x: x[sort_by], reverse=(sort_order == 'desc'))

    # Pagination
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))
    total_pages = (len(table_data) + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_data = table_data[start_idx:end_idx]

    return render_template('sp500.html', 
                           data=paginated_data, 
                           page=page, 
                           total_pages=total_pages, 
                           sort_by=sort_by, 
                           sort_order=sort_order)


def process_csv_transactions(file_path, user_id):
    with app.app_context():
        with open(file_path, 'r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                try:
                    transaction_date = datetime.strptime(row['TransactionDate'], '%m/%d/%Y')
                    transaction_type = row['TransactionType']
                    security_type = row['SecurityType']
                    symbol = row['Symbol'].upper()
                    quantity = float(row['Quantity'])
                    commission = float(row['Commission'])
                    amount = float(row['Amount'])
                    print(f"Processing row: {row}")
                    # On the web page a positive number is always used but on spreadsheet a negative number is used for sell transactions
                    if transaction_type == 'Sold':
                        transaction_type = 'sell'
                        quantity = -quantity
                    elif transaction_type == 'Bought':
                        transaction_type = 'buy'
                    elif transaction_type == 'Dividend':
                        transaction_type = 'div'
                    elif transaction_type == 'Interest':
                        transaction_type = 'int'
                    price = float(row['Price'])
                
                    if transaction_type == 'sell':
                        taf_fee = quantity * 0.000166 
                        print(f"  CSV - TAF Fee: {taf_fee}")
                    else:
                        taf_fee = 0.0

                    transaction_value = quantity * price - commission - taf_fee
                   
                    previous_transaction = Transactions.query.filter(
                        Transactions.user_id == user_id,
                        Transactions.date <= transaction_date
                    ).order_by(Transactions.date.desc(), Transactions.id.desc()).first()
                    
                    if previous_transaction:
                        cash_balance = previous_transaction.cash_balance
                    else:
                        user = User.query.get(user_id)
                        cash_balance = user.starting_balance
                    if transaction_type == 'buy':
                        cash_balance -= transaction_value
                    elif transaction_type == 'sell':
                        cash_balance += transaction_value
                    elif transaction_type == 'div':
                        cash_balance += amount
                    elif transaction_type == 'int':
                        cash_balance += amount

                    print(f"  CSV - Cash balance: {cash_balance}")
                    stock_value = calculate_stock_value_on_date(
                        user_id, 
                        transaction_date, 
                        transaction_type=transaction_type, 
                        transaction_symbol=symbol, 
                        transaction_quantity=quantity
                    )
                    print(f"  CSV - Stock value: {stock_value}")

                    if transaction_type == 'buy':
                        stock_value += transaction_value

                    new_transaction = Transactions(
                        date=transaction_date,
                        transaction_type=transaction_type,
                        symbol=symbol,
                        quantity=quantity,
                        price=price,
                        commission=commission,
                        cash_balance=cash_balance,
                        stock_value=stock_value,
                        user_id=user_id
                    )
                    db.session.add(new_transaction)

                    update_position(user_id, symbol, quantity, price, transaction_type)

                except Exception as e:
                    print(f"Error processing row: {row}. Error: {str(e)}")
                    db.session.rollback()
                    continue

        db.session.commit()
        print("CSV import completed.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'import_csv':
        if len(sys.argv) != 4:
            print("Usage: python app.py import_csv <csv_file_path> <user_id>")
            sys.exit(1)
        
        csv_file_path = sys.argv[2]
        user_id = int(sys.argv[3])
        
        with app.app_context():
            process_csv_transactions(csv_file_path, user_id)
    else:
        with app.app_context():
            db.create_all()
        app.run(port=5010, debug=True)