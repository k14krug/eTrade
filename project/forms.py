from wtforms import StringField, PasswordField, SubmitField, BooleanField, FloatField, DateField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from .models import User
from datetime import date
from flask_wtf import FlaskForm


class MyForm(FlaskForm):
    name = StringField('name', validators=[DataRequired()])


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    starting_balance = FloatField('Starting Balance', validators=[DataRequired()])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')
        
class TransactionForm(FlaskForm):
    date = DateField('Transaction Date', validators=[DataRequired()], default=date.today)
    transaction_type = SelectField('Transaction Type', 
                                   choices=[('buy', 'Buy'), 
                                            ('sell', 'Sell'), 
                                            ('sell_on_limit', 'Sell on Limit'), 
                                            ('div', 'Dividend')],
                                   validators=[DataRequired()])
    symbol = StringField('Stock Symbol', validators=[DataRequired(), Length(min=1, max=5)])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired()])
    commission = FloatField('Commission', default=0)
    taf_fee = FloatField('TAF Fee', default=0)
    submit = SubmitField('Add Transaction')

    def validate_quantity(self, quantity):
        if self.transaction_type.data in ['buy', 'sell', 'sell_on_limit'] and quantity.data <= 0:
            raise ValidationError('Quantity must be greater than 0 for buy/sell transactions.')
        if self.transaction_type.data == 'div' and quantity.data != 0:
            raise ValidationError('Quantity should be 0 for dividend transactions.')

    def validate_price(self, price):
        if price.data <= 0:
            raise ValidationError('Price must be greater than 0.')

    def validate_date(self, date_field):
        if date_field.data > date.today():
            raise ValidationError('Transaction date cannot be in the future.')