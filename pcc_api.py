"""政府採購網 API 呼叫，經 Cloudflare Workers 上的 cf-fetch-proxy 轉發（解決 GitHub Actions IP 封鎖問題）"""
import os
import time
from urllib.parse import urlencode

import requests

PCC_API_BASE = "https://pcc-api.openfun.app/api"
PROXY_URL = os.getenv("PCC_PROXY_URL", "https://cf-fetch-proxy.alexabc.workers.dev/")

# 被限流（429）時重試，等待時間依序加倍：10、20、40 秒
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 10


def pcc_get(path, params, timeout):
    target = f"{PCC_API_BASE}/{path}?{urlencode(params)}"
    for attempt in range(MAX_RETRIES + 1):
        response = requests.get(PROXY_URL, params={"url": target}, timeout=timeout)
        if response.status_code != 429 or attempt == MAX_RETRIES:
            return response
        time.sleep(RETRY_WAIT_SECONDS * 2 ** attempt)
