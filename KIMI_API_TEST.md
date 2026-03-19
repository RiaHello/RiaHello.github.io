# Kimi API 测试命令

## 使用 curl 测试

```bash
curl https://api.moonshot.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -d '{
    "model": "moonshot-v1-auto",
    "messages": [
      {
        "role": "user",
        "content": "你好，请介绍一下你自己"
      }
    ],
    "temperature": 0.7
  }'
```

## 使用 Python 脚本

运行：
```bash
python3 test_kimi_api.py
```

记得先替换 API_KEY！

## 可用模型
- moonshot-v1-8k
- moonshot-v1-32k
- moonshot-v1-128k
- moonshot-v1-auto (自动选择)
