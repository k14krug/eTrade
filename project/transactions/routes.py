from flask import Blueprint, render_template, redirect, request, jsonify, session
from datetime import datetime, time
from . import bp
from project.models import db, Transactions
from project.forms import TransactionForm
from flask_login import login_required, current_user
from project.stock_data import StockData
from .utils import calculate_stock_value_on_date, update_position, get_current_positions, get_buy_opportunities

@bp.route('/', methods=['GET', 'POST'])
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
            elif transaction_type in ['sell', 'div', 'int']:
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
        print(f"Validation errors: {form.errors}")
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

    return render_template('transactions/transactions.html', 
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

@bp.route('/buy_opportunities')
@login_required
def buy_opportunities():
    opportunities = get_buy_opportunities(current_user.id)
    
    # Print session state before modifying anything
    print(f"Buy Opportunity - Session Stock Filters Before: {session.get('stock_filters')}")
    
    # Print request args to see if `stock_filters` is being passed here
    print(f"Request Args in buy_opportunities: {request.args}")
    
    # After processing, print the session state again
    print(f"Buy Opportunity - Session Stock Filters After: {session.get('stock_filters')}")
    
    return render_template('transactions/buy_opportunities.html', opportunities=opportunities)