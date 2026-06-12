import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default

def _get_list(name: str) -> list[str]:
    value = os.getenv(name, "").strip()
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]

class Settings:
    def __init__(self):
        self._qq_mail_user = os.getenv("QQ_MAIL_USER", "")
        self._qq_mail_auth = os.getenv("QQ_MAIL_AUTH", "")
        self._qq_mail_to = os.getenv("QQ_MAIL_TO", "")

        self._traffic_warn_mb = _get_int("TRAFFIC_WARN_MB", 500)
        self._traffic_critical_mb = _get_int("TRAFFIC_CRITICAL_MB", 700)
        self._traffic_shutdown_mb = _get_int("TRAFFIC_SHUTDOWN_MB", 900)
        self._auto_shutdown = _get_bool("AUTO_SHUTDOWN", False)

        self._alert_cooldown_seconds = _get_int("ALERT_COOLDOWN_SECONDS", 1800)
        self._daily_mail_limit = _get_int("DAILY_MAIL_LIMIT", 20)

        self.check_urls = _get_list("CHECK_URLS")
        self.check_tcp = _get_list("CHECK_TCP")

        self.web_host = os.getenv("WEB_HOST", "127.0.0.1")
        self.web_port = _get_int("WEB_PORT", 8765)

        data_dir_str = os.getenv("DATA_DIR", "data")
        log_dir_str = os.getenv("LOG_DIR", "logs")
        
        data_dir = Path(data_dir_str)
        log_dir = Path(log_dir_str)
        
        self.data_dir = (BASE_DIR / data_dir).resolve() if not data_dir.is_absolute() else data_dir
        self.log_dir = (BASE_DIR / log_dir).resolve() if not log_dir.is_absolute() else log_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def qq_mail_user(self) -> str:
        import storage
        return storage.get_state("smtp_user", self._qq_mail_user)

    @property
    def qq_mail_auth(self) -> str:
        import storage
        return storage.get_state("smtp_auth", self._qq_mail_auth)

    @property
    def qq_mail_to(self) -> str:
        import storage
        return storage.get_state("smtp_to", self._qq_mail_to)

    @property
    def smtp_host(self) -> str:
        import storage
        return storage.get_state("smtp_host", "smtp.qq.com")

    @property
    def smtp_port(self) -> int:
        import storage
        val = storage.get_state("smtp_port")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return 465

    @property
    def smtp_ssl(self) -> bool:
        import storage
        val = storage.get_state("smtp_ssl")
        if val is not None:
            return val.strip().lower() in {"1", "true", "yes", "on"}
        return True

    @property
    def traffic_warn_mb(self) -> int:
        import storage
        val = storage.get_state("traffic_warn_mb")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return self._traffic_warn_mb

    @property
    def traffic_critical_mb(self) -> int:
        import storage
        val = storage.get_state("traffic_critical_mb")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return self._traffic_critical_mb

    @property
    def traffic_shutdown_mb(self) -> int:
        import storage
        val = storage.get_state("traffic_shutdown_mb")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return self._traffic_shutdown_mb

    @property
    def auto_shutdown(self) -> bool:
        import storage
        val = storage.get_state("auto_shutdown")
        if val is not None:
            return val.strip().lower() in {"1", "true", "yes", "on"}
        return self._auto_shutdown

    @property
    def alert_cooldown_seconds(self) -> int:
        import storage
        val = storage.get_state("alert_cooldown_seconds")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return self._alert_cooldown_seconds

    @property
    def daily_mail_limit(self) -> int:
        import storage
        val = storage.get_state("daily_mail_limit")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return self._daily_mail_limit

    @property
    def mem_warn_pct(self) -> int:
        import storage
        val = storage.get_state("mem_warn_pct")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return 90

    @property
    def disk_warn_pct(self) -> int:
        import storage
        val = storage.get_state("disk_warn_pct")
        if val is not None:
            try:
                return int(val)
            except Exception:
                pass
        return 85

    @property
    def secret_key(self) -> str:
        import storage
        import secrets
        val = storage.get_state("secret_key")
        if not val:
            val = secrets.token_hex(32)
            storage.set_state("secret_key", val)
        return val

    @property
    def webhook_url(self) -> str:
        import storage
        return storage.get_state("webhook_url", "")

settings = Settings()
