from dataclasses import dataclass

ERRORS = {
    'INVALID_JSON': (400, '请求内容不是有效的 JSON。'),
    'PAYLOAD_TOO_LARGE': (413, '请求内容过大。'),
    'UNSUPPORTED_MEDIA_TYPE': (415, '请使用未压缩的 JSON 请求。'),
    'VALIDATION_ERROR': (422, '请检查问题及对话历史的格式和长度。'),
    'RATE_LIMITED': (429, '请求过于频繁，请稍后再试。'),
    'DAILY_QUOTA_EXCEEDED': (503, '今天的服务额度已用完，请明天再来。'),
    'RESUME_UNAVAILABLE': (503, '公开简历暂未准备好。'),
    'LIMITER_UNAVAILABLE': (503, '服务暂时无法接受请求，请稍后再试。'),
    'AI_UNAVAILABLE': (503, '助手暂时繁忙，请稍后再试。'),
    'AI_CONFIGURATION_ERROR': (503, '助手服务配置暂不可用。'),
    'AI_TIMEOUT': (504, '本次回答超时，请稍后手动重试。'),
    'AI_INVALID_RESPONSE': (502, '助手未能生成完整有效的回答。'),
    'INTERNAL_ERROR': (500, '服务遇到问题，请稍后再试。'),
    'NOT_FOUND': (404, '接口不存在。'),
    'METHOD_NOT_ALLOWED': (405, '请求方法不受支持。'),
    'CORS_REJECTED': (400, '请求来源或跨域参数不受支持。'),
}
RETRYABLE = {'RATE_LIMITED', 'DAILY_QUOTA_EXCEEDED', 'LIMITER_UNAVAILABLE', 'AI_UNAVAILABLE', 'AI_TIMEOUT'}

@dataclass
class AppError(Exception):
    code: str
    retry_after: int | None = None

    @property
    def status(self):
        return ERRORS[self.code][0]

    def body(self, request_id):
        return {'request_id': request_id, 'error': {'code': self.code, 'message': ERRORS[self.code][1], 'retryable': self.code in RETRYABLE}}
