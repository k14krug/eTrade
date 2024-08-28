# transactions/routes.py
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Transactions, Position, User
from forms import TransactionForm
from .utils import calculate_stock_value_on_date, update_position, get_current_positions, get_buy_opportunities
from stock_data import StockData
from datetime import datetime, time
import csv
import sys

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/', methods=['GET', 'POST'])
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

            previous_transaction = Transactions.query.filter(
                Transactions.user_id == current_user.id,
                Transactions.date <= transaction_date
            ).order_by(Transactions.date.desc(), Transactions.id.desc()).first()

            if previous_transaction:
                cash_balance = previous_transaction.cash_balance
            else:
                cash_balance = current_user.starting_balance

            if transaction_type == 'buy':
                cash_balance -= transaction_value
            elif transaction_type in ['sell', 'div']:
                cash_balance += transaction_value

            stock_value = calculate_stock_value_on_date(
                current_user.id, 
                transaction_date, 
                transaction_type=transaction_type, 
                transaction_symbol=symbol, 
                transaction_quantity=quantity
            )

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
                user_id=current_user.id
            )
            db.session.add(new_transaction)

            update_position(current_user.id, symbol, quantity, price, transaction_type)

            db.session.commit()
            return jsonify({'success': True, 'message': 'Transaction added successfully.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400

    if form.errors:
        return jsonify({'success': False, 'message': 'Validation error', 'errors': form.errors}), 400

    all_transactions = Transactions.query.filter_by(user_id=current_user.id).order_by(Transactions.date.desc(), Transactions.id.desc()).all()
    latest_transaction = Transactions.query.filter_by(user_id=current_user.id).order_by(Transactions.date.desc(), Transactions.id.desc()).first()

    cash_balance = latest_transaction.cash_balance if latest_transaction else current_user.starting_balance
    total_stock_value = latest_transaction.stock_value if latest_transaction else 0

    positions, active_transaction_ids, total_current_value, position_gain_loss = get_current_positions(current_user.id)
    total_account_value = cash_balance + total_current_value
    total_gain_loss = total_account_value - current_user.starting_balance   
    position_gain_loss_percentage = (position_gain_loss / (total_account_value - position_gain_loss)) * 100 if (total_account_value - total_gain_loss) != 0 else 0
    overall_gain_loss_percentage = ((total_account_value - current_user.starting_balance) / current_user.starting_balance) * 100

    for transaction in all_transactions:
        transaction.total_value = transaction.cash_balance + transaction.stock_value
        transaction.gain_loss = transaction.total_value - current_user.starting_balance

        if current_user.starting_balance != 0:
            transaction.gain_loss_percentage = (transaction.gain_loss / current_user.starting_balance) * 100
        else:
            transaction.gain_loss_percentage = 0

        if transaction.id in active_transaction_ids:
            transaction.current_price = StockData.get_latest_price(transaction.symbol)
        else:
            transaction.current_price = None
        
        if transaction.transaction_type == 'sell':
            transaction.taf_fee = round(transaction.quantity * 0.0001666, 2)
        else:
            transaction.taf_fee = 0.00
        commission = transaction.commission if transaction.commission is not None else 0.0
        transaction.transaction_amount = transaction.quantity * transaction.price - commission - transaction.taf_fee

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

@transactions_bp.route('/buy_opportunities')
@login_required
def buy_opportunities():
    opportunities = get_buy_opportunities(current_user.id)
    return render_template('buy_opportunities.html', opportunities=opportunities)

def process_csv_transactions(file_path, user_id):
    with current_app.app_context():
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