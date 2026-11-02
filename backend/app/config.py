import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

class ConfigurationError(RuntimeError):
    """Only configuration field names may appear in this exception."""

@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    model: str
    hmac_secret: str = field(repr=False)
    redis_url: str = field(default='redis://127.0.0.1:6379/0', repr=False)
    app_env: str = 'development'
    origins: tuple[str, ...] = ('http://localhost:5173', 'http://127.0.0.1:5173')

    @classmethod
    def from_env(cls):
        bad = []
        key, model, secret = (os.getenv(n, '') for n in ('DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL', 'RATE_LIMIT_HMAC_SECRET'))
        if not key.strip(): bad.append('DEEPSEEK_API_KEY')
        if not model.strip(): bad.append('DEEPSEEK_MODEL')
        if len(secret) < 32 or not secret.isascii(): bad.append('RATE_LIMIT_HMAC_SECRET')
        env = os.getenv('APP_ENV', 'development')
        if env not in ('development', 'production'): bad.append('APP_ENV')
        raw_origins = os.getenv('ALLOWED_ORIGINS')
        if env == 'production' and not raw_origins: bad.append('ALLOWED_ORIGINS')
        origins = tuple(x.strip() for x in (raw_origins if raw_origins is not None else ','.join(cls.origins)).split(','))
        for origin in origins:
            try:
                u = urlsplit(origin)
                valid = u.scheme in ('http', 'https') and bool(u.hostname) and not u.username and not u.password and not u.path and not u.query and not u.fragment and '*' not in origin
                _ = u.port
            except ValueError:
                valid = False
            if not valid: bad.append('ALLOWED_ORIGINS')
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
        try:
            u = urlsplit(redis_url)
            if u.scheme not in ('redis', 'rediss') or not u.hostname: bad.append('REDIS_URL')
            _ = u.port
        except ValueError:
            bad.append('REDIS_URL')
        if bad:
            raise ConfigurationError(','.join(dict.fromkeys(bad)))
        return cls(key, model.strip(), secret, redis_url, env, origins)
