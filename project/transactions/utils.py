# transactions/utils.py
from project.models import db, Transactions, Position, User
from project.stock_data import StockData
from datetime import timedelta
import csv

def calculate_stock_value_on_date(user_id, date, transaction_type=None, transaction_symbol=None, transaction_quantity=0):
    total_value = 0
    positions = Position.query.filter_by(user_id=user_id).all()

    for position in positions:
        if transaction_type == 'sell' and position.symbol == transaction_symbol:
            remaining_quantity = max(position.quantity - transaction_quantity, 0)
        else:
            remaining_quantity = position.quantity

        historical_price = StockData.get_historical_price(position.symbol, date)
        if historical_price:
            total_value += remaining_quantity * historical_price

    return total_value

def update_position(user_id, symbol, quantity, price, transaction_type):
    position = Position.query.filter_by(user_id=user_id, symbol=symbol).first()
    if position:
        if transaction_type == 'buy':
            total_cost = (position.quantity * position.average_price) + (quantity * price)
            position.quantity += quantity
            position.average_price = total_cost / position.quantity
        elif transaction_type == 'sell':
            position.quantity -= quantity
            if position.quantity <= 0:
                db.session.delete(position)
    elif transaction_type == 'buy':
        new_position = Position(user_id=user_id, symbol=symbol, quantity=quantity, average_price=price)
        db.session.add(new_position)

def get_current_positions(user_id):
    positions = Position.query.filter_by(user_id=user_id).all()
    position_data = []
    total_current_value = 0
    position_gain_loss = 0
    active_transaction_ids = set()

    for position in positions:
        current_price = StockData.get_latest_price(position.symbol)
        if current_price:
            current_value = position.quantity * current_price
            gain_loss = current_value - (position.quantity * position.average_price)
            gain_loss_percentage = (gain_loss / (position.quantity * position.average_price)) * 100 if (position.quantity * position.average_price) != 0 else 0
            total_cost = position.quantity * position.average_price
            total_current_value += current_value
            position_gain_loss += gain_loss

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
    symbols = db.session.query(Transactions.symbol).filter_by(user_id=user_id).distinct().all()
    symbols = [symbol[0] for symbol in symbols]

    for symbol in symbols:
        last_buy = Transactions.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            transaction_type='buy'
        ).order_by(Transactions.date.desc()).first()

        if last_buy:
            current_price = StockData.get_latest_price(symbol)
            if current_price and current_price < last_buy.price:
                pe_ratio = StockData.get_pe_ratio(symbol)

                opportunities.append({
                    'symbol': symbol,
                    'last_buy_price': last_buy.price,
                    'current_price': current_price,
                    'price_difference': last_buy.price - current_price,
                    'price_difference_percentage': ((last_buy.price - current_price) / last_buy.price) * 100,
                    'pe_ratio': pe_ratio
                })

    opportunities.sort(key=lambda x: x['price_difference_percentage'], reverse=True)
    return opportunities

def process_csv_transactions(file_path, user_id):
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