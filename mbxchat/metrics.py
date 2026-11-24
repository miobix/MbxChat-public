import time

from langchain_core.callbacks import BaseCallbackHandler
from prometheus_client import Counter, Gauge, Histogram
from telegram.request import HTTPXRequest

GRADES = Counter("mbxchat_grades", "Answers graded, by grader tier", ["tier"])
for _tier in ("reference", "llm"):
    GRADES.labels(_tier)
MODEL_SECONDS = Histogram(
    "mbxchat_model_call_seconds", "Model call latency", ["model"], buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 160)
)
MODEL_ERRORS = Counter("mbxchat_model_errors", "Model calls that raised", ["model"])
ERRORS = Counter("mbxchat_errors", "Unhandled errors reported in the chat")
LAST_POLL = Gauge("mbxchat_last_poll_timestamp_seconds", "Unix time of the last completed getUpdates")


class ModelMetrics(BaseCallbackHandler):
    def __init__(self):
        self._start: dict = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kw):
        self._start[run_id] = (time.monotonic(), (metadata or {}).get("ls_model_name", "unknown"))

    def on_llm_end(self, response, *, run_id, **kw):
        if start := self._start.pop(run_id, None):
            MODEL_SECONDS.labels(start[1]).observe(time.monotonic() - start[0])

    def on_llm_error(self, error, *, run_id, **kw):
        if start := self._start.pop(run_id, None):
            MODEL_ERRORS.labels(start[1]).inc()


MODEL = ModelMetrics()


class PollRequest(HTTPXRequest):
    """getUpdates request that stamps LAST_POLL on every completed long poll, empty or not."""

    async def do_request(self, *args, **kwargs):
        result = await super().do_request(*args, **kwargs)
        LAST_POLL.set_to_current_time()
        return result
