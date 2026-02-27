from core.tasks import test_task

# Call the task
result = test_task.delay()
print(f"Task ID: {result.id}")
print("Task has been sent to Celery!") 