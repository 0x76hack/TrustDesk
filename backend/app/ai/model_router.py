from app.config import settings


class ModelRouter:

    def __init__(self):
        self._mapping = {
            'triage': settings.MODEL_FAST,
            'draft': settings.MODEL_CAPABLE,
            'complex': settings.MODEL_REASONING,
            'embedding': settings.EMBEDDING_MODEL,
        }
        self._default = settings.MODEL_CAPABLE

    def route(self, task_type: str) -> str:
        return self._mapping.get(task_type, self._default)
