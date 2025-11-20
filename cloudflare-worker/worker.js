/**
 * PCC API 反向代理 - Cloudflare Workers
 * 用途：繞過 GitHub Actions IP 封鎖，轉發請求到政府採購網 API
 */

// 目標 API 網址
const TARGET_API = 'https://pcc-api.openfun.app';

// 允許的來源（CORS）
const ALLOWED_ORIGINS = [
  'https://github.com',
  'http://localhost',
  'http://127.0.0.1'
];

/**
 * 處理請求
 */
async function handleRequest(request) {
  const url = new URL(request.url);

  // 建構目標 URL（保留原始路徑和查詢參數）
  const targetUrl = `${TARGET_API}${url.pathname}${url.search}`;

  // 準備轉發的請求
  const modifiedRequest = new Request(targetUrl, {
    method: request.method,
    headers: request.headers,
    body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined
  });

  try {
    // 轉發請求到目標 API
    const response = await fetch(modifiedRequest);

    // 複製回應
    const modifiedResponse = new Response(response.body, response);

    // 設定 CORS headers
    modifiedResponse.headers.set('Access-Control-Allow-Origin', '*');
    modifiedResponse.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    modifiedResponse.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    // 加入自訂 header 用於除錯
    modifiedResponse.headers.set('X-Proxy-By', 'Cloudflare-Workers');

    return modifiedResponse;
  } catch (error) {
    return new Response(JSON.stringify({
      error: 'Proxy Error',
      message: error.message,
      target: targetUrl
    }), {
      status: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      }
    });
  }
}

/**
 * 處理 CORS preflight 請求
 */
function handleOptions(request) {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400',
    }
  });
}

/**
 * Worker 主入口
 */
export default {
  async fetch(request, env, ctx) {
    // 處理 OPTIONS 請求（CORS preflight）
    if (request.method === 'OPTIONS') {
      return handleOptions(request);
    }

    // 處理一般請求
    return handleRequest(request);
  }
};
