# databases/redis.md without a server: the fragments' first redis-py call is issued against an address
# nothing listens on. redis-py raises its DeprecationWarnings before connecting, so a deprecated first call
# (the session SET) fails this smoke. --live runs every call against Redis 7 and checks values and TTLs.
import redis

from app.cache_aside import get_or_load
from app.sessions import store_session
from harness_stubs.redis_app import Db, User

nowhere = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
for call in (lambda: get_or_load(nowhere, Db(), "k", 60), lambda: store_session(nowhere, "tok", User())):
    try:
        call()
    except redis.exceptions.ConnectionError:
        pass
    else:
        raise AssertionError("expected no Redis at 127.0.0.1:1")
nowhere.close()
