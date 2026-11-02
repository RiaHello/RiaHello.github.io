import hashlib
import hmac
import time
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.errors import AppError

IP_SCRIPT = """
local a = tonumber(redis.call('GET', KEYS[1]) or '0')
local b = tonumber(redis.call('GET', KEYS[2]) or '0')
if b >= 50 then return tonumber(ARGV[2]) end
if a >= 5 then return tonumber(ARGV[1]) end
redis.call('INCR', KEYS[1]); redis.call('EXPIRE', KEYS[1], ARGV[1])
redis.call('INCR', KEYS[2]); redis.call('EXPIRE', KEYS[2], ARGV[2])
return 0
"""
DAILY_SCRIPT = """
local n = tonumber(redis.call('GET', KEYS[1]) or '0')
if n >= 500 then return 0 end
redis.call('INCR', KEYS[1]); redis.call('EXPIRE', KEYS[1], ARGV[1])
return 1
"""

class RateLimiter:
    def __init__(self, redis: Redis, secret: str, prefix='resume:v1'):
        self.redis, self.secret, self.prefix = redis, secret.encode('ascii'), prefix

    def windows(self, now=None):
        now = int(time.time() if now is None else now)
        return now // 60, now // 86400, 60 - now % 60, 86400 - now % 86400

    def ip_keys(self, ip, now=None):
        minute, day, mt, dt = self.windows(now)
        digest = hmac.new(self.secret, ip.encode(), hashlib.sha256).hexdigest()
        return [f'{self.prefix}:ip:{digest}:m:{minute}', f'{self.prefix}:ip:{digest}:d:{day}'], mt, dt

    async def check_ip(self, ip):
        keys, mt, dt = self.ip_keys(ip)
        try:
            retry = int(await self.redis.eval(IP_SCRIPT, 2, *keys, mt, dt))
        except (RedisError, OSError):
            raise AppError('LIMITER_UNAVAILABLE') from None
        if retry: raise AppError('RATE_LIMITED', retry)

    async def reserve_daily(self):
        _, day, _, dt = self.windows()
        try:
            ok = await self.redis.eval(DAILY_SCRIPT, 1, f'{self.prefix}:global:{day}', dt)
        except (RedisError, OSError):
            raise AppError('LIMITER_UNAVAILABLE') from None
        if not ok: raise AppError('DAILY_QUOTA_EXCEEDED', dt)

    async def ready(self):
        try:
            return bool(await self.redis.ping())
        except (RedisError, OSError):
            return False
