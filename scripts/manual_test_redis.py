import redis

# Redis connection URL with correct SSL configuration
redis_url = "rediss://:bSEDHclfM2KUs4iJGubgw1lt2S8p6mLF7AzCaLnaDRU=@celery-redis-cache.redis.cache.windows.net:6380/0"

try:
    # Create Redis client with SSL configuration
    r = redis.from_url(
        redis_url,
        ssl_cert_reqs=None  # This is equivalent to CERT_NONE but in the correct format
    )
    
    # Test connection
    r.ping()
    print("Successfully connected to Redis!")
    
    # Test set and get
    r.set('test_key', 'test_value')
    value = r.get('test_key')
    print(f"Test value retrieved: {value}")
    
except Exception as e:
    print(f"Error connecting to Redis: {str(e)}") 