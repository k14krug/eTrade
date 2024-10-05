import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime, timedelta
import pytz

# Define the market calendar for the NYSE
nyse = mcal.get_calendar('NYSE')
# Define the Pacific Time zone
pacific = pytz.timezone("America/Los_Angeles")

def is_market_open_for_date(date):
    """
    Check if the market was open for a given date.
    
    Args:
        date (datetime.date): Date to check.
    
    Returns:
        bool: True if the market was open, False otherwise.
    """
    schedule = nyse.schedule(start_date=str(date), end_date=str(date))
    return not schedule.empty

def get_market_status_for_today():
    """
    Determine the detailed current market status.
    Checks if the market is open, closed, pre-market, or after-market
    for the current date in Pacific Time.
    
    Returns:
        str: 'Pre-Market', 'Open', 'After-Market', 'Holiday', or 'Closed'.
    """
    # Get current time in UTC and convert to Pacific Time
    current_time_utc = datetime.utcnow()
    current_time_pacific = current_time_utc.replace(tzinfo=pytz.utc).astimezone(pacific)
    
    # Extract just the date for today
    today = current_time_pacific.date()

    # Check if today is a holiday
    if is_market_holiday(today):
        return "Holiday"

    # Get today's trading schedule
    schedule = nyse.schedule(start_date=str(today), end_date=str(today))

    if schedule.empty:
        return "Closed"
    
    # Extract market open and close times in Pacific Time
    market_open_pacific = schedule.iloc[0]['market_open'].tz_convert(pacific)
    market_close_pacific = schedule.iloc[0]['market_close'].tz_convert(pacific)
    
    # Determine market status based on the current time
    if current_time_pacific < market_open_pacific:
        return "Pre-Market"
    elif market_open_pacific <= current_time_pacific <= market_close_pacific:
        return "Open"
    else:
        return "After-Market"

def is_market_holiday(date):
    """
    Check if the given date is a market holiday.
    
    Args:
        date (datetime.date): Date to check.
    
    Returns:
        bool: True if the given date is a holiday, False otherwise.
    """
    schedule = nyse.schedule(start_date=str(date), end_date=str(date))
    return schedule.empty

def check_market_status_for_multiple_days(dates):
    """
    Check if the market was open for each date in a list of dates.
    For the current date, include the detailed status.
    
    Args:
        dates (list of datetime.date): List of dates to check.
    
    Returns:
        dict: A dictionary where keys are dates and values are status strings.
    """
    status_report = {}
    today = datetime.utcnow().date()

    for date in dates:
        if date == today:
            status_report[str(date)] = get_market_status_for_today()
        else:
            status_report[str(date)] = "Open" if is_market_open_for_date(date) else "Closed"

    return status_report

# Example usage for testing
if __name__ == "__main__":
    # Get today's date in UTC and subtract 1 to get past days only
    today = datetime.utcnow().date()
    last_8_days = [today - timedelta(days=i) for i in range(1, 9)]  # Exclude today

    # Check market status for the last 8 days
    status_report = check_market_status_for_multiple_days(last_8_days)
    print("Market Status Report for Last 8 Days:")
    for day, status in status_report.items():
        print(f"{day}: {status}")
