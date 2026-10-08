"""政府採購網 API 呼叫，經 Cloudflare Workers 上的 cf-fetch-proxy 轉發（解決 GitHub Actions IP 封鎖問題）"""
import os
from urllib.parse import urlencode

import requests

PCC_API_BASE = "https://pcc-api.openfun.app/api"
PROXY_URL = os.getenv("PCC_PROXY_URL", "https://cf-fetch-proxy.alexabc.workers.dev/")


def pcc_get(path, params, timeout):
    target = f"{PCC_API_BASE}/{path}?{urlencode(params)}"
    response = requests.get(PROXY_URL, params={"url": target}, timeout=timeout)
    if response.status_code >= 400:
        h = response.headers
        print(
            f"BUGFIX/pcc-403 path={path} status={response.status_code} "
            f"x-proxy-by={h.get('x-proxy-by')} server={h.get('server')} cf-ray={h.get('cf-ray')} "
            f"ctype={h.get('content-type')} body={response.text[:200]!r}",
            flush=True,
        )
    return response
