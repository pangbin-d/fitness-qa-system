"""
step4_rag.py —— 第四步：串成完整 RAG 链

目标：
    检索 → 拼上下文 → 调模型 → 出答案，串成一条链。

技术选择说明（这段很重要，别跳过）：
    本文件全程用 LCEL（LangChain Expression Language）手写链路，
    没有用 RetrievalQA、create_retrieval_chain 这些工厂函数。

    原因：这些 legacy chains 在 LangChain 1.0 里已经被移进 langchain-classic 包，
    新版里 from langchain.chains import RetrievalQA 会直接 ModuleNotFoundError。
    网上教程大多还是 0.x 写法，照抄必踩坑。

    LCEL 是 langchain-core 的原语，1.x 里一直在用，最稳。

跑通标准：
    1. 知识库内的问题，答得出具体数字
    2. 知识库外的问题，模型老实说「资料中没有提到」，不瞎编
"""

import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import sys

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

from step3_store import build_vectorstore

load_dotenv()


# ── 上下文拼接 ──────────────────────────────────────────────────
def format_docs(docs):
    """
    把检索到的 Document 列表拼成一段文本，塞进 prompt 的 {context}。

    这里加编号是为了让模型能引用来源（「根据资料 2」），
    你后面做评测时，这个编号可以用来算「引用准确率」。
    """
    return "\n\n".join(f"[资料{i}] {d.page_content}" for i, d in enumerate(docs, 1))


def main():
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("[X] 没读到 DEEPSEEK_API_KEY，检查 .env")
        sys.exit(1)

    # ── 准备检索器 ────────────────────────────────────────────
    vectorstore = build_vectorstore(rebuild=True)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    # ── 准备模型 ──────────────────────────────────────────────
    model = init_chat_model("deepseek:deepseek-flash", temperature=0)

    # ── 准备提示词 ────────────────────────────────────────────
    # system 里把「只依据资料回答」这条约束写死，这是抑制幻觉的第一道闸。
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是一名专业健身教练。请严格依据下面的参考资料回答问题。\n"
         "规则：\n"
         "1. 资料里有明确答案的，直接给出具体数值或做法\n"
         "2. 资料里没有的，必须回答「资料中没有提到」，禁止自行补充\n"
         "3. 不要解释你的推理过程，直接给结论\n\n"
         "参考资料：\n{context}"),
        ("human", "{question}"),
    ])

    # ── 组装链 ────────────────────────────────────────────────
    # 这是 LCEL 的核心写法，用 | 把各环节串成管道：
    #
    #   {"context": ..., "question": ...}   准备输入字典
    #        ↓
    #   prompt                              填进模板
    #        ↓
    #   model                               调模型
    #        ↓
    #   StrOutputParser()                   从 AIMessage 里抽出纯文本
    #
    # RunnablePassthrough() 的作用是把用户的问题原样透传下去，
    # 因为 retriever 分支只产 context，question 要另外一路带过去。
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | model
        | StrOutputParser()
    )

    # ── 测试用例 ──────────────────────────────────────────────
    # 前两个是知识库内，应该答得出具体数字
    # 第三个是知识库外，必须老实说没有 —— 这是验证不瞎编
    test_cases = [
        ("体重 78 公斤增肌，每天蛋白质该吃多少？", "应当给出具体克数"),
        ("硬拉的时候腰会痛是什么原因？", "应当提到腰背中立位或发力方式"),
        ("增肌期可以每天只睡 4 小时吗？", "资料里没有，必须答「资料中没有提到」"),
    ]

    for i, (q, expect) in enumerate(test_cases, 1):
        print("\n" + "=" * 60)
        print(f"测试 {i}：{q}")
        print(f"期望：{expect}")
        print("=" * 60)

        # 先单独跑一次检索，把捞到的内容打出来
        # 调 RAG 时这步非常有用：答案不对时，一眼能看出是检索错还是模型错
        docs = retriever.invoke(q)
        print("\n[检索到的资料]")
        for j, d in enumerate(docs, 1):
            print(f"  [{j}] {d.page_content}")

        # 再跑完整链
        answer = chain.invoke(q)
        print(f"\n[模型回答]\n  {answer}")

    # ── 收尾 ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("全部测试完成")
    print("=" * 60)
    print("""
自查两件事：

1. 测试 1、2 有没有给出具体数值/做法？
   如果答得含糊或跑题 → 问题在检索，回 step3 调 chunk_size

2. 测试 3 有没有老实说「资料中没有提到」？
   如果它开始编睡眠时间 → prompt 里那条约束没起作用，
   试着把「禁止自行补充」再强调一遍，或者换更强的模型

这两条都过了，最小闭环就算跑通。
接下来要做的是：换成你真实的 30 条健身知识库，把链路接进主项目。
""")


if __name__ == "__main__":
    main()
