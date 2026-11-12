"""
step2_split.py —— 第二步：中文文档切分

目标：
    看懂「一段长文本怎么变成一堆小块」，以及 chunk_size / chunk_overlap 到底在控制什么。

为什么 RAG 必须切分：
    1. 模型上下文有限，整篇塞不进去
    2. 检索要精准，整篇作为一个单位检索，命中了也没法用
    3. 块太大 → 检索到一堆无关内容，噪声高
       块太小 → 语义不完整，模型看不懂

跑通标准：
    打印出若干块，每块读起来都是完整的句子，没有从中间被切断的。
"""

from data_source import build_chunks


def main():
    print("=" * 60)
    print("切分实验：对比不同 chunk_size 的效果")
    print("=" * 60)

    # ── 对照组 1：块太大 ──────────────────────────────────────
    print("\n【对照组 A】chunk_size=200（块太大）")
    big = build_chunks(chunk_size=200, chunk_overlap=30)
    print(f"切出 {len(big)} 块")
    for i, c in enumerate(big):
        preview = c.page_content[:50].replace("\n", " ")
        print(f"  [{i}] {len(c.page_content):>3}字 | {preview}...")

    # ── 对照组 2：块太小 ──────────────────────────────────────
    print("\n【对照组 B】chunk_size=20（块太小）")
    small = build_chunks(chunk_size=20, chunk_overlap=5)
    print(f"切出 {len(small)} 块")
    for i, c in enumerate(small):
        print(f"  [{i}] {len(c.page_content):>3}字 | {c.page_content}")

    # ── 本次采用：块大小适中 ──────────────────────────────────
    print("\n【采用方案】chunk_size=60, chunk_overlap=15")
    chunks = build_chunks(chunk_size=60, chunk_overlap=15)
    print(f"切出 {len(chunks)} 块\n")
    for i, c in enumerate(chunks):
        print(f"  [{i:02d}] ({len(c.page_content):>2}字) {c.page_content}")

    # ── 观察元数据 ────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("每一块都自带 metadata，检索时可以用来溯源：")
    print("  ", chunks[0].metadata)
    print("\n注意 metadata 里没有块序号，如果你需要，可以自己补：")
    print("  for i, c in enumerate(chunks):")
    print("      c.metadata['chunk_id'] = i")

    # ── 自检 ──────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("【自检清单】")
    too_long = [i for i, c in enumerate(chunks) if len(c.page_content) > 80]
    if too_long:
        print(f"  [!] 有 {len(too_long)} 块超过 80 字，块可能偏大：{too_long}")
    else:
        print("  [√] 所有块都在 80 字以内")

    # 检查有没有句子被硬切断（块末尾不是标点，且下一块开头不是完整句子）
    broken = []
    for i in range(len(chunks) - 1):
        tail = chunks[i].page_content.rstrip()
        if tail and tail[-1] not in "。！？；，、":
            broken.append(i)
    if broken:
        print(f"  [!] 有 {len(broken)} 块结尾不是标点，可能被切断：{broken}")
        print("      调小 chunk_size，或者往 separators 里补更多分隔符")
    else:
        print("  [√] 没有发现句子被硬切断")

    print("\n[√] step2 通过，可以进 step3 了")


if __name__ == "__main__":
    main()
