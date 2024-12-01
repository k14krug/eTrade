# Class to avoid duplicate tasks in Celery
import redis
from celery import Task
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

class DeduplicationTask(Task):
    def __call__(self, *args, **kwargs):
        task_id = self.request.id
        task_name = self.name
        redis_client = redis.StrictRedis.from_url(self.app.conf.broker_url)

        # Check if the task is already in the queue
        if redis_client.exists(f"celery-task-{task_name}-{task_id}"):
            logger.info(f"Task {task_name} with ID {task_id} is already in the queue. Ignoring duplicate task.")
            raise Ignore()

        # Add the task to the queue
        redis_client.set(f"celery-task-{task_name}-{task_id}", "queued", ex=3600)  # Set expiration time as needed
        return super().__call__(*args, **kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        task_name = self.name
        redis_client = redis.StrictRedis.from_url(self.app.conf.broker_url)
        redis_client.delete(f"celery-task-{task_name}-{task_id}")
        super().on_success(retval, task_id, args, kwargs)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        task_name = self.name
        redis_client = redis.StrictRedis.from_url(self.app.conf.broker_url)
        redis_client.delete(f"celery-task-{task_name}-{task_id}")
        super().on_failure(exc, task_id, args, kwargs, einfo)