import os
import time

import redis
from flask import Flask, jsonify

app = Flask(__name__)

cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    decode_responses=True,
)
CACHE_TTL_SECONDS = 60


def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/compute/<int:n>")
def compute(n):
    start = time.time()
    key = f"fib:{n}"

    cached_value = cache.get(key)
    if cached_value is not None:
        result = int(cached_value)
        cached = True
    else:
        time.sleep(5)  # simulates a slow database query
        result = fibonacci(n)
        cache.setex(key, CACHE_TTL_SECONDS, result)
        cached = False

    duration = round(time.time() - start, 2)
    return jsonify(n=n, result=result, cached=cached, duration_seconds=duration)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
