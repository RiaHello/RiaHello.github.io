#!/usr/bin/env python3
"""Test Kimi codingplan API"""

import requests
import json

# Kimi API配置
API_KEY = "YOUR_API_KEY_HERE"  # 替换为你的API KEY
API_URL = "https://api.moonshot.cn/v1/chat/completions"

def test_kimi_codingplan():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": "moonshot-v1-auto",  # 或 moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
        "messages": [
            {
                "role": "user",
                "content": "你好，请介绍一下你自己"
            }
        ],
        "temperature": 0.7
    }

    print("发送请求到 Kimi API...")
    print(f"URL: {API_URL}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")

    response = requests.post(API_URL, headers=headers, json=payload)

    print(f"状态码: {response.status_code}")
    print(f"响应内容:\n{json.dumps(response.json(), ensure_ascii=False, indent=2)}")

    return response.json()

if __name__ == "__main__":
    test_kimi_codingplan()
