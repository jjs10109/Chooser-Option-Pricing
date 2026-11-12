"""Fixed model baselines; preprocessing is fit inside each temporal fold."""

from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


def make_models():
    return {
        "linear": make_pipeline(SimpleImputer(), StandardScaler(), LinearRegression()),
        "random_forest": make_pipeline(
            SimpleImputer(),
            RandomForestRegressor(
                n_estimators=150, min_samples_leaf=5, random_state=42, n_jobs=-1
            ),
        ),
        "xgboost": make_pipeline(
            SimpleImputer(),
            XGBRegressor(
                n_estimators=150,
                max_depth=3,
                learning_rate=0.05,
                objective="reg:squarederror",
                random_state=42,
                n_jobs=2,
            ),
        ),
    }
