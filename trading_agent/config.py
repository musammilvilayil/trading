from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    starting_capital: float = 25_000
    max_position_inr: float = 3_000
    risk_per_trade_pct: float = 0.005
    max_daily_loss_pct: float = 0.02
    min_confidence: float = 0.62
    reward_risk_ratio: float = 2.0
    paper_trading: bool = True

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


settings = Settings()
