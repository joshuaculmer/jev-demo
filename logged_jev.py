import json

from typesafe_sdk import TypeSafeClient


def pretty(raw):
    return json.dumps(json.loads(raw), indent=2)


class LoggedJev:
    """Sends questions to Jev and logs each raw request and response as it happens."""

    def __init__(self, logger, run_name):
        self.logger = logger
        self.run_name = run_name
        self.calls = 0
        self.client = TypeSafeClient()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.client.close()

    def system_one(self, *args, **kwargs):
        response = self.client.system_one(*args, **kwargs)
        self.calls += 1

        http = response.raw_http_response
        self.logger.log(
            self.run_name,
            f"=== Request {self.calls} ===\n{pretty(http.request.content)}\n\n"
            f"=== Response {self.calls} ({response.request_id}) ===\n{pretty(http.text)}",
        )
        return response
