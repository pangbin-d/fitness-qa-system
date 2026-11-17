"""
step3_store.py —— 第三步：向量入库 + 检索

目标：
    把 step2 切好的块变成向量存进 Chroma，然后验证「问一句话，能不能捞到对的那几块」。

这是整条链路里最需要反复调的一步。
检索不准，后面接多强的模型都是白搭 —— 它只能根据你给的材料答，材料错了答案必错。

跑通标准：
    三个测试问题，返回的前 3 块里都包含正确答案所在的那一句。

⚠️ 第一次运行会下载 bge 模型（约 95MB），会卡 1-3 分钟，别 Ctrl+C。
"""

import shutil
from pathlib import Path
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from data_source import build_chunks

# 向量库落盘目录
PERSIST_DIR = "./chroma_demo"
COLLECTION = "fitness_demo"


def get_embeddings():
    """
    Embedding 模型选择说明：

    DeepSeek 不提供 embedding API，只有 chat 接口，所以向量化必须另找方案。
    这里用本地开源模型，免费、不联网、可控。

    bge-small-zh-v1.5 是中文小模型，512 维，速度和效果平衡得不错。
    想要更好效果可以换 bge-base-zh-v1.5（768 维，慢一些，文件大一倍）。
    """
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},  # 归一化，让余弦相似度更稳
    )


def build_vectorstore(rebuild: bool = True):
    """建向量库。rebuild=True 时先清空旧目录，避免每次运行重复追加。"""
    if rebuild and Path(PERSIST_DIR).exists():
        # 这是脚本自己生成的缓存目录，删掉重建是预期行为
        shutil.rmtree(PERSIST_DIR)
        print(f"[i] 已清空旧的 {PERSIST_DIR}/")

    chunks = build_chunks(chunk_size=60, chunk_overlap=15)
    print(f"[i] 待入库 {len(chunks)} 块")

    embeddings = get_embeddings()
    print("[i] Embedding 模型加载中（首次会下载约 95MB，耐心等）...")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
        collection_name=COLLECTION,
    )
    print(f"[√] 入库完成，已落盘到 {PERSIST_DIR}/")
    return vectorstore


def run_test(vectorstore, question: str, must_contain: str):
    """
    检索并自检。

    参数：
        question      测试问题
        must_contain  正确答案里必须出现的关键词，用来判断检索有没有命中
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    hits = retriever.invoke(question)

    print(f"\n问题：{question}")
    print(f"期望命中包含「{must_contain}」的片段")

    hit_ok = False
    for i, d in enumerate(hits, 1):
        marked = ""
        if must_contain in d.page_content:
            marked = "  ← 命中"
            hit_ok = True
        print(f"  {i}. {d.page_content}{marked}")

    if hit_ok:
        print("  [√] 检索正常")
    else:
        print("  [X] 没命中！说明 embedding 或切分有问题")

    return hit_ok


def main():
    vectorstore = build_vectorstore(rebuild=True)

    print("\n" + "=" * 60)
    print("检索测试")
    print("=" * 60)

    # 三个问题分别对应文本里不同位置的内容，用来验证检索不是「随便返回几条」
    results = [
        run_test(vectorstore, "增肌期每天要吃多少蛋白质", "1.6 到 2.2 克"),
        run_test(vectorstore, "深蹲的时候膝盖往里扣怎么改", "膝盖内扣"),
        run_test(vectorstore, "减脂太快会怎么样", "肌肉流失"),
    ]

    print("\n" + "=" * 60)
    if all(results):
        print(f"[√] {len(results)}/{len(results)} 全部命中，step3 通过")
        print("    可以进 step4 了")
    else:
        print(f"[!] 只有 {sum(results)}/{len(results)} 命中，先修检索再往下走")
        print("    排查方向：")
        print("      1. embedding 模型是不是中文的")
        print("      2. chunk_size 是不是太小，导致语义不完整")
        print("      3. 知识库文本里到底有没有这个信息")
        print("    调好之前不要进 step4，串起来只会更乱")


if __name__ == "__main__":
    main()
