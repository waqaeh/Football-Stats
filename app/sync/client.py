import time

import httpx

BASE_URL = "https://api.football-data.org/v4"


class FootballDataClient:
    """Talks to football-data.org and stays under its rate limit (10 requests/minute on the free plan)."""

    def __init__(self, api_key: str, http: httpx.Client | None = None, sleep=time.sleep):
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=30)
        self.http.headers["X-Auth-Token"] = api_key
        self.sleep = sleep

    def get(self, path: str, **params) -> dict:
        for _ in range(3):
            response = self.http.get(path, params=params)
            seconds_until_reset = int(response.headers.get("x-requestcounter-reset", 60))

            if response.status_code == 429:  # too many requests: wait for the counter to reset, then retry
                print(f"  rate limited, waiting {seconds_until_reset}s...")
                self.sleep(seconds_until_reset)
                continue

            response.raise_for_status()
            if response.headers.get("x-requests-available-minute") == "0":
                print(f"  used all requests for this minute, waiting {seconds_until_reset}s...")
                self.sleep(seconds_until_reset)
            return response.json()

        raise RuntimeError(f"Still rate limited after 3 attempts: {path}")
