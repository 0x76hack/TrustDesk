import re
from arq.connections import RedisSettings
from app.config import settings
from app.workers.tasks import triage_task, draft_task, action_task, eval_task


def parse_redis_url(url: str) -> RedisSettings:
    match = re.match(r"redis://(?:(.+?)(?::(.+?))?@)?(.+?):?(\d+)?/?(\d+)?$", url)
    if not match:
        return RedisSettings()
    host = match.group(3) or "localhost"
    port = int(match.group(4) or 6379)
    database = int(match.group(5) or 0)
    return RedisSettings(host=host, port=port, database=database)


class WorkerSettings:
    redis_settings = parse_redis_url(settings.REDIS_URL)
    functions = [
        triage_task,
        draft_task,
        action_task,
        eval_task,
    ]
    max_jobs = 10
    job_timeout = 120
