from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://xsmb:xsmb_secret@localhost:5432/xsmb"
    log_level: str = "INFO"

    # Source URLs
    ketqua_vn_base_url: str = "https://ketqua.vn"
    ketqua_net_base_url: str = "https://ketqua04.net"

    # Rate limiting
    ketqua_vn_delay_min: float = 1.5
    ketqua_vn_delay_max: float = 2.5
    ketqua_net_delay_min: float = 2.0
    ketqua_net_delay_max: float = 3.0
    max_retries: int = 3
    backoff_multiplier: float = 3.0
    pause_on_429: int = 60

    # Scraping
    start_date: str = "2009-01-01"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
