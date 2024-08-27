import subprocess
import signal
import sys

def start_redis():
    print("Starting Redis server...")
    process = subprocess.Popen(["redis-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Redis server started.")
    return process

def stop_redis(process):
    print("Stopping Redis server...")
    process.send_signal(signal.SIGTERM)
    process.wait()
    print("Redis server stopped.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            redis_process = start_redis()
            print("Press Ctrl+C to stop the Redis server.")
            try:
                redis_process.wait()
            except KeyboardInterrupt:
                stop_redis(redis_process)
        elif sys.argv[1] == "stop":
            print("This script can't stop an externally started Redis server.")
            print("To stop Redis, use: sudo service redis-server stop")
    else:
        print("Usage: python manage_redis.py [start|stop]")