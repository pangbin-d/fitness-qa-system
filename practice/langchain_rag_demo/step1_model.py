"""
step1_model.py —— 第一步：先让模型能通

目标：
    在写任何 RAG 逻辑之前，先确认「包版本对 + API Key 对 + 模型名对」。
    这三件事任何一个不对，后面全部白搭。

跑通标准：
    终端打印出一句中文回答。

常见报错对照：
    ModuleNotFoundError: No module named 'langchain'     → 没装包 / venv 没激活
    Model not found                                      → 模型名写错，用 deepseek-flash
    AuthenticationError / 401                            → API Key 错或没读到 .env
"""

import os
import sys

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# 读 .env 里的 DEEPSEEK_API_KEY
load_dotenv()


def main():
    # ── 前置检查：Key 有没有读到 ──────────────────────────────
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("[X] 没读到 DEEPSEEK_API_KEY")
        print("    检查 langchain_rag_demo/ 目录下有没有 .env 文件")
        print("    .env 内容应该是一行：DEEPSEEK_API_KEY=sk-xxxxx")
        sys.exit(1)

    print("[√] API Key 已读取")
    print(f"    Key 前 8 位：{os.getenv('DEEPSEEK_API_KEY')[:8]}...")

    # ── 初始化模型 ────────────────────────────────────────────
    # 格式是 "provider:model_name"
    # provider = deepseek，model_name = deepseek-flash
    #    deepseek-flash 背后是 V4.1-Flash-1017
    model = init_chat_model("deepseek:deepseek-flash", temperature=0)
    print("[√] 模型初始化完成：deepseek-flash")

    # ── 发一条最简单的请求 ────────────────────────────────────
    print("\n正在调用模型...\n")
    resp = model.invoke("用一句话解释什么是 RAG（检索增强生成）")

    print("模型返回：")
    print(resp.content)

    # ── 顺便看看返回对象长什么样 ──────────────────────────────
    print("\n" + "─" * 50)
    print("返回对象类型：", type(resp).__name__)
    print("有 .content 属性（正文）：", hasattr(resp, "content"))
    print("有 .usage_metadata 属性（token 统计）：", hasattr(resp, "usage_metadata"))
    if hasattr(resp, "usage_metadata") and resp.usage_metadata:
        print("本次 token 用量：", resp.usage_metadata)

    print("\n[√] step1 通过，可以进 step2 了")


if __name__ == "__main__":
    main()
