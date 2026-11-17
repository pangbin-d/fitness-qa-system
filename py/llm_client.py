# -*- coding: utf-8 -*-
"""
LLM 调用层 —— 全项目唯一入口。

铁律：model 必须由调用方传入，这里不给默认值。
    任何一处硬编码 model 都会让「多模型对比」在无声中失效——
    你以为在测三个模型，实际三个 task 全跑的是同一个，而且不报错。
    所以这里把 model 设成必填位置参数，漏传直接 TypeError。

client 复用：
    client 只是 HTTP 连接对象（base_url + api_key），跟具体模型无关。
    同一个 base_url 下的所有模型共用一个 client，省掉重复建连。
    真正决定「用哪个模型」的是 create(model=...) 这个参数。

思考模式（2026-11-16 实测）：
    硅基流动上这 5 个模型默认全部开启思考，`enable_thinking: False` 全部可关。
    实测「只回答两个字：收到」的对比：
        qwen3.5-9b      开思考 7.2s / 199 token  →  关思考 0.5s / 1 token
        deepseek-v4.1   开思考 1.2s /  22 token  →  关思考 1.2s / 1 token
    思考 token 按输出价计费，且长度不可控。本项目的问答属于知识性问答，
    不需要长链推理，因此默认关闭，保证：
        1. 成本可预期
        2. 各模型条件一致（都关，不会出现「A 模型多想了 200 字」这种不可比因素）
        3. 耗时可控（qwen3.5-9b 快 14 倍）
    需要思考时显式传 enable_thinking=True。
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    BadRequestError,
)

BASE_DIR = Path(__file__).parent.parent

# 依次尝试，先读到的优先（override=False）
#   1. 毕设文件/.env —— 项目自己的配置，优先
#   2. pythonProject AI/.env —— 历史遗留，作为回落
for _p in (BASE_DIR / ".env", BASE_DIR.parent / "pythonProject AI" / ".env"):
    if _p.exists():
        load_dotenv(_p, override=False)

from config import PROVIDERS

MAX_RETRIES = 3

RETRYABLE_ERRORS = (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
)

# 同一 provider 复用同一个 client
_CLIENTS = {}


def make_client(provider="siliconflow"):
    """
    按 provider 建（或复用）client。

    参数：
        provider : config.PROVIDERS 的键，如 siliconflow / deepseek
    返回：
        openai.OpenAI 实例
    """
    if provider in _CLIENTS:
        return _CLIENTS[provider]

    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"未定义的 provider：{provider}，可选 {list(PROVIDERS)}")

    key = os.getenv(cfg["api_key_env"])
    if not key:
        raise RuntimeError(
            f"环境变量 {cfg['api_key_env']} 未配置，无法调用 {provider}"
        )

    client = OpenAI(api_key=key, base_url=cfg["base_url"])
    _CLIENTS[provider] = client
    return client


def chat_with_retry(client, msgs, model, temperature=0.0, json_mode=False,
                    max_tokens=None, enable_thinking=False):
    """
    带重试的对话调用。只对「临时故障」重试，业务错误（如模型不存在）直接抛。

    参数：
        client      : make_client() 的返回
        msgs        : messages 列表
        model       : 模型 ID（如 deepseek-ai/DeepSeek-V3），必传
        temperature : 采样温度
        json_mode   : 是否要求 JSON 输出。部分模型不支持 response_format，
                      遇到 BadRequestError 会自动关掉 json_mode 再试一次，
                      否则一个不支持的模型会把整个实验跑挂。
        max_tokens  : 可选上限
        enable_thinking : 是否开启思考模式。默认 False（理由见模块文档）。
                      硅基流动用 extra_body 透传，不支持的模型会忽略该字段。
    """
    if not model:
        raise ValueError("model 不能为空：调用方必须显式指定模型 ID")

    kwargs = {
        "model": model,
        "messages": msgs,
        "temperature": temperature,
        "extra_body": {"enable_thinking": bool(enable_thinking)},
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    use_json = json_mode
    json_downgraded = False

    for attempt in range(MAX_RETRIES + 1):
        try:
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}
            else:
                kwargs.pop("response_format", None)
            return client.chat.completions.create(**kwargs)

        except BadRequestError as e:
            # 模型不支持 response_format：关掉 json_mode 重来一次
            if use_json and not json_downgraded:
                json_downgraded = True
                use_json = False
                print(f"    [!] {model} 不支持 JSON 模式，已降级为普通输出")
                continue
            raise

        except RETRYABLE_ERRORS as e:
            if attempt == MAX_RETRIES:
                print(f"    连打{MAX_RETRIES + 1}次全挂，放弃：{type(e).__name__}")
                raise
            wait = 2 ** attempt
            print(f"    第{attempt + 1}次挂了({type(e).__name__})，{wait}秒后重拨...")
            time.sleep(wait)


def strip_fence(text):
    """
    剥掉模型爱加的 ```json 围栏。
    降级掉 json_mode 之后，模型很可能把 JSON 包在代码块里，直接 json.loads 会炸。
    """
    if not text:
        return text
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t
