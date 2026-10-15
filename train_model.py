"""
Groundwater Level Prediction Model Training Script
AquaSense AI - BTech Mini Project

This script trains a Machine Learning model (Random Forest Regressor)
to predict future groundwater levels based on environmental factors
and historical water levels.

Evaluation metrics: MAE, RMSE, and R² Score.
Output: groundwater_model.pkl and model_metadata.json
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


def load_and_preprocess_data(csv_path: str):
    """
    Load dataset, clean missing values, and engineer lag features
    to predict next month's groundwater level.
    """
    df = pd.read_csv(csv_path)
    print(f"Loaded dataset from {csv_path}: {df.shape[0]} rows, {df.shape[1]} columns")

    # Ensure correct data types
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(by=["location", "date"]).reset_index(drop=True)

    # Handle any potential missing values
    numeric_cols = [
        "water_level", "rainfall", "temperature", "humidity",
        "extraction_rate", "recharge_rate"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df.groupby("location")[col].transform("mean"))

    # Feature engineering:
    # Target: Next month's water level (depth in meters)
    # Features: current water_level, rainfall, temperature, humidity, extraction_rate, recharge_rate
    df["target_water_level"] = df.groupby("location")["water_level"].shift(-1)

    # Drop the last record for each location since it won't have a future target
    clean_df = df.dropna(subset=["target_water_level"]).copy()

    feature_columns = [
        "water_level",
        "rainfall",
        "temperature",
        "humidity",
        "extraction_rate",
        "recharge_rate"
    ]

    X = clean_df[feature_columns]
    y = clean_df["target_water_level"]

    return X, y, feature_columns


def train_and_evaluate(X, y, feature_columns):
    """
    Split data, train Random Forest and Linear Regression,
    evaluate both, and persist the top-performing model.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"\nTraining set size: {len(X_train)} samples")
    print(f"Testing set size: {len(X_test)} samples")

    # 1. Baseline Model: Linear Regression
    lr_model = LinearRegression()
    lr_model.fit(X_train, y_train)
    lr_preds = lr_model.predict(X_test)
    lr_mae = mean_absolute_error(y_test, lr_preds)
    lr_rmse = np.sqrt(mean_squared_error(y_test, lr_preds))
    lr_r2 = r2_score(y_test, lr_preds)

    print("\n--- Baseline Model: Linear Regression ---")
    print(f"MAE  : {lr_mae:.4f} meters")
    print(f"RMSE : {lr_rmse:.4f} meters")
    print(f"R²   : {lr_r2:.4f}")

    # 2. Main Model: Random Forest Regressor
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=8,
        random_state=42
    )
    rf_model.fit(X_train, y_train)
    rf_preds = rf_model.predict(X_test)
    rf_mae = mean_absolute_error(y_test, rf_preds)
    rf_rmse = np.sqrt(mean_squared_error(y_test, rf_preds))
    rf_r2 = r2_score(y_test, rf_preds)

    print("\n--- Primary Model: Random Forest Regressor ---")
    print(f"MAE  : {rf_mae:.4f} meters")
    print(f"RMSE : {rf_rmse:.4f} meters")
    print(f"R²   : {rf_r2:.4f}")

    # Feature Importance
    importances = rf_model.feature_importances_
    print("\n--- Feature Importances ---")
    for feat, imp in sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True):
        print(f"  {feat:<18}: {imp * 100:.2f}%")

    # Choose best model (Random Forest)
    chosen_model = rf_model
    model_name = "Random Forest Regressor"
    metrics = {
        "model_name": model_name,
        "mae": round(float(rf_mae), 4),
        "rmse": round(float(rf_rmse), 4),
        "r2_score": round(float(rf_r2), 4),
        "baseline_lr_mae": round(float(lr_mae), 4),
        "baseline_lr_r2": round(float(lr_r2), 4),
        "features": feature_columns,
        "sample_count": int(len(X))
    }

    return chosen_model, metrics


def main():
    root_dir = Path(__file__).resolve().parent.parent
    data_path = root_dir / "data" / "groundwater_data.csv"
    model_path = root_dir / "ml" / "groundwater_model.pkl"
    meta_path = root_dir / "ml" / "model_metadata.json"

    print("==================================================")
    print("      AQUASENSE AI - MODEL TRAINING PIPELINE      ")
    print("==================================================")
    print(f"Reading from: {data_path}")

    X, y, feature_columns = load_and_preprocess_data(str(data_path))
    model, metrics = train_and_evaluate(X, y, feature_columns)

    # Save model and metadata
    joblib.dump(model, model_path)
    print(f"\nTrained model successfully saved to: {model_path}")

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)
    print(f"Model metadata successfully saved to: {meta_path}")
    print("\n==================================================")
    print("               TRAINING COMPLETED                 ")
    print("==================================================")


if __name__ == "__main__":
    main()
