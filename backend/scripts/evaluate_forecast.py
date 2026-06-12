import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import warnings

# Suppress statsmodels optimization warnings for clean console output
warnings.filterwarnings("ignore") 

DATABASE_URL = "sqlite:///./metrobike_dev.db"

def get_top_station_data(engine):
    print("Querying the database for the highest-volume zone...")
    # Find the single busiest station to ensure a dense time series
    top_station_query = """
    SELECT zone_id, SUM(pickup_volume) as total_volume
    FROM fact_demand
    GROUP BY zone_id
    ORDER BY total_volume DESC
    LIMIT 1
    """
    top_station_id = pd.read_sql(top_station_query, engine).iloc[0]['zone_id']
    
    # Pull the daily time series for that specific station
    ts_query = f"""
    SELECT date, pickup_volume
    FROM fact_demand
    WHERE zone_id = '{top_station_id}'
    ORDER BY date ASC
    """
    df = pd.read_sql(ts_query, engine)
    df['date'] = pd.to_datetime(df['date'])
    
    # Set the date as the index and fill missing days with 0 demand 
    # (Crucial for time-series math which expects continuous frequencies)
    df = df.set_index('date').asfreq('D', fill_value=0) 
    
    print(f"Targeting Zone: '{top_station_id}' with {len(df)} days of history.")
    return df['pickup_volume']

def rolling_origin_backtest(series, test_days=30):
    print(f"\nRunning {test_days}-day rolling-origin backtest...")
    
    actuals = []
    hw_predictions = []
    naive_predictions = []
    
    # Start the test window
    start_idx = len(series) - test_days
    
    for i in range(start_idx, len(series)):
        # Train data is everything from the beginning up to 'today'
        train = series.iloc[:i]
        actual = series.iloc[i] # What actually happened 'tomorrow'
        
        # 1. The Naïve Baseline: Predict 'tomorrow' will equal 'today'
        naive_pred = train.iloc[-1]
        
        # 2. The DS Model: Triple Exponential Smoothing (Holt-Winters)
        # Accounts for base level, trend, and weekly (7-day) seasonality
        try:
            model = ExponentialSmoothing(
                train, 
                trend='add', 
                seasonal='add', 
                seasonal_periods=7
            ).fit(optimized=True)
            hw_pred = model.forecast(1).iloc[0]
        except Exception:
            # Fallback if the solver fails to converge on a specific sparse window
            hw_pred = naive_pred
            
        actuals.append(actual)
        hw_predictions.append(max(0, hw_pred)) # Demand can't be negative
        naive_predictions.append(naive_pred)
        
    # Calculate Mean Absolute Error (MAE)
    hw_mae = np.mean(np.abs(np.array(actuals) - np.array(hw_predictions)))
    naive_mae = np.mean(np.abs(np.array(actuals) - np.array(naive_predictions)))
    
    # Calculate Mean Absolute Scaled Error (MASE)
    mase = hw_mae / naive_mae if naive_mae != 0 else 1.0
    improvement = (1 - mase) * 100
    
    print("\n" + "="*50)
    print("📊 FORECAST EVALUATION RESULTS")
    print("="*50)
    print(f"Naïve Baseline MAE : {naive_mae:.2f} bikes/day off")
    print(f"Holt-Winters MAE   : {hw_mae:.2f} bikes/day off")
    print("-" * 50)
    print(f"MASE Score         : {mase:.3f} (< 1.0 means we beat the baseline)")
    print(f"Model Improvement  : {improvement:.1f}% more accurate than guessing")
    print("="*50)

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    demand_series = get_top_station_data(engine)
    
    # Run the backtest over the last 30 days of data
    rolling_origin_backtest(demand_series, test_days=30)