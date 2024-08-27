#!/bin/bash
# manage_services.sh

# Set the project directory
PROJECT_DIR="/mnt/wsl_projects/eTrade"

start_services() {
  echo "Starting Redis..."
  python manage_redis.py start &
  echo "Starting Celery worker..."
  cd $PROJECT_DIR && PYTHONPATH=$PYTHONPATH:$PROJECT_DIR celery -A celery_worker worker --loglevel=info &
  echo "Starting Flask app..."
  cd $PROJECT_DIR && python app.py
}

stop_services() {
  echo "Stopping all services..."
  pkill -f "python start_redis.py"
  pkill -f "celery"
  pkill -f "python app.py"
}

case "$1" in
  start)
    start_services
    ;;
  stop)
    stop_services
    ;;
  *)
    echo "Usage: $0 {start|stop}"
    exit 1
esac

exit 0