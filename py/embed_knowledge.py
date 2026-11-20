# -*- coding: utf-8 -*-
"""
知识库向量化 —— knowledge 表 → kb_chunks 表 + Chroma 集合

阶段 1 的唯一产出脚本。跑完这一步，RAG 才具备「检索」能力，
evaluate.py 的 build_retriever() 才有东西可接。

用法：
    python3 py/embed_knowledge.py --check      # 体检：不调 API、不写库
    python3 py/embed_knowledge.py              # 正式建库（幂等，可重复跑）
    python3 py/embed_knowledge.py --limit 3    # 只做前 3 条知识，调链路用
    python3 py/embed_knowledge.py --no-chroma  # 只写 kb_chunks，不碰 Chroma
    python3 py/embed_knowledge.py --smoke      # 检索自检：查一条看相似度

四段结构：
    chunk_text()            中文分块，句末标点优先断开
    SiliconFlowEmbedding    批量向量化（走 SiliconFlow /embeddings）
    build_chunk_rows()      从 knowledge 表组装待写块行
    write_to_db() / write_to_chroma()   双写，Chroma 成功后回填 vector_id

为什么双写而不是只写 Chroma：
    kb_chunks 是账本 —— 能 JOIN knowledge、能统计哪条知识没向量化、
    能在 SQL 里查「这次召回了哪些块」；Chroma 是索引 —— 只负责相似度检索。
    账本丢了就说不清「100 条知识到底切了多少块」，索引丢了检索直接失效。
    两者都要，且以 kb_chunks 为准回填 vector_id，保证账实相符。

验收（跑完对照）：
    1. kb_chunks 行数 ≥ 100（当前 100 条知识正文都在 200 字以内，
       恰好一知识一块；等题库换成长文才会出现一块以上的情况）
    2. Chroma 集合 count() == kb_chunks 行数
    3. search("增肌每天要吃多少蛋白质") 首条 similarity > 0.5
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import init_db as db
import llm_client
from config import RAG

BASE_DIR = Path(__file__).parent.parent
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"
COLLECTION = "kb_chunks"

# 句末标点：分块时优先在这些字符后断开，避免把一句话劈成两半
SENTENCE_END = "。！？；\n"

# 硅基流动上 bge 系列的备选型号。config 里写错或模型下线时按这个提示，
# 但绝不自动切换 —— 换模型等于换向量空间，旧向量会全部失效。
MODEL_HINTS = ["BAAI/bge-large-zh-v1.5", "BAAI/bge-m3",
               "netease-youdao/bce-embedding-base_v1"]


# ============================================================
# 第一段：切块
# ============================================================
def chunk_text(text, size=None, overlap=None):
    """
    把一条知识切成若干块。

    参数：
        text    : 原始正文
        size    : 单块最大字符数，默认取 config.RAG["chunk_size"]
        overlap : 相邻块重叠字符数，默认取 config.RAG["chunk_overlap"]

    返回：list[str]，空文本返回 []

    切法：
        1. 从 start 往后取 size 个字符作为候选窗口
        2. 在窗口里从后往前找最近的句末标点，找到就在标点后断开
        3. 找不到合适标点（比如一句超长话）就硬切在 size 处
        4. 下一块起点 = 本块终点 - overlap

    为什么要 overlap：
        答案可能正好落在切缝上，比如第 200 字是「蛋白质摄入量应」、
        第 201 字是「达到每公斤体重 2 克」。不重叠的话前一块缺后半句、
        后一块缺前半句，检索命中哪块都不完整。留 40 字重叠，两块都能用。

    为什么至少回退 size//3 才认标点：
        窗口末尾刚好有个句号，但句号前面只有 20 个字，按它切会切出
        一堆 20 字的碎块，上下文全丢。宁可硬切也不切碎。
    """
    size = size or RAG["chunk_size"]
    overlap = overlap or RAG["chunk_overlap"]
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window = text[start:end]
            cut = -1
            for p in SENTENCE_END:
                pos = window.rfind(p)
                if pos > cut:
                    cut = pos
            if cut >= size // 3:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        # 防止 overlap >= size 时原地踏步变成死循环
        start = max(end - overlap, start + 1)
    return chunks


# ============================================================
# 第二段：向量化
# ============================================================
class SiliconFlowEmbedding:
    """
    向量化客户端。走 SiliconFlow 的 /embeddings 接口，
    和聊天共用同一个 client、同一个 api_key，只是端点不同。

    为什么不用本地 HuggingFaceEmbeddings：
        本地要先下 1.3G 的 bge-large，首次加载慢、吃内存，换机器还要重下。
        走 API 一次调用就拿到，100 条知识总共几分钱。
        代价是每次检索多一次网络往返，但单次延迟在百毫秒级，可接受。

    批量大小 32：
        硅基流动对单次 input 数组长度有限制，32 是稳的。
        太大了会被拒，太小了往返次数多，纯效率问题。
    """

    def __init__(self, model=None, batch_size=32):
        self.model = model or RAG["embedding_model"]
        self.batch_size = batch_size
        self.client = llm_client.make_client("siliconflow")
        self.dim = None

    def embed(self, texts, show_progress=True):
        """批量向量化，返回与 texts 等长的 list[list[float]]"""
        if not texts:
            return []
        out = []
        total = len(texts)
        for i in range(0, total, self.batch_size):
            batch = texts[i:i + self.batch_size]
            out.extend(self._embed_batch(batch))
            if show_progress:
                print(f"    向量化 {min(i + len(batch), total)}/{total}", end="\r")
        if show_progress:
            print()
        return out

    def _embed_batch(self, batch):
        """
        单批调用 + 重试。

        只对临时故障重试（超时、限流、5xx），模型不存在这种业务错误
        重试一百次也没用，直接抛出去让人改配置。
        """
        last_err = None
        for attempt in range(llm_client.MAX_RETRIES + 1):
            try:
                resp = self.client.embeddings.create(
                    model=self.model, input=batch
                )
                # 按 index 排序，别信返回顺序 —— 批量接口不保证有序，
                # 顺序错了会出现「A 的文本配 B 的向量」，检索全乱但不报错
                items = sorted(resp.data, key=lambda d: d.index)
                if self.dim is None and items:
                    self.dim = len(items[0].embedding)
                return [d.embedding for d in items]
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt == llm_client.MAX_RETRIES:
                    break
                wait = 2 ** attempt
                print(f"\n    [!] 第 {attempt + 1} 次失败：{e}；{wait}s 后重试")
                time.sleep(wait)
        raise RuntimeError(
            f"向量化失败（模型 {self.model}）：{last_err}\n"
            f"若提示模型不存在，把 config.RAG['embedding_model'] 改成其中之一再试：\n"
            f"    {', '.join(MODEL_HINTS)}"
        )

    def embed_one(self, text):
        """单条向量化，检索时用"""
        return self.embed([text], show_progress=False)[0]


# ============================================================
# 第三段：组装待写行
# ============================================================
def build_chunk_rows(limit=0):
    """
    读 knowledge 表 → 切块 → 组装待写行。

    只取 status='active'：停用条目不该进向量库，
    否则检索会召回已经作废的内容，而且很难发现。
    """
    items = db.list_knowledge(status="active")
    if limit:
        items = items[:limit]
    if not items:
        return [], 0

    rows = []
    for k in items:
        pieces = chunk_text(k["content"])
        for idx, piece in enumerate(pieces):
            rows.append({
                "knowledge_id": k["id"],
                "chunk_index": idx,
                "chunk_text": piece,
                "topic": k["topic"],
                "aspect": k.get("aspect") or "",
            })
    return rows, len(items)


# ============================================================
# 第四段：双写
# ============================================================
def write_to_db(rows, vectors):
    """
    写 kb_chunks。按 knowledge_id 先删后插，保证同一条知识重跑不重复。

    为什么不整表清空：
        --limit 3 调试时整表清空会毁掉已有的 100 条数据。
        只删本次涉及的 knowledge_id，跑多少条就只管多少条。

    返回 [(chunk_row_id, row), ...]，顺序与 rows 一致，
    后面回填 vector_id 要用这个对齐。
    """
    kids = sorted({r["knowledge_id"] for r in rows})
    pairs = []
    with db.get_conn() as conn:
        conn.executemany(
            "DELETE FROM kb_chunks WHERE knowledge_id = ?", [(k,) for k in kids]
        )
        for r, _vec in zip(rows, vectors):
            cur = conn.execute(
                "INSERT INTO kb_chunks "
                "(knowledge_id, chunk_index, chunk_text, embedded_at) "
                "VALUES (?, ?, ?, datetime('now','localtime'))",
                (r["knowledge_id"], r["chunk_index"], r["chunk_text"]),
            )
            pairs.append((cur.lastrowid, r))
    print(f"    kb_chunks 写入 {len(pairs)} 行（涉及 {len(kids)} 条知识）")
    return pairs


def get_collection(create=True):
    """
    拿（或建）Chroma 集合。

    hnsw:space 设成 cosine：bge 系列训练目标就是余弦相似度，
    用 L2 会得到方向不同但长度不同的向量被判为「不相似」，排序会歪。
    """
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if create:
        return client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"}
        )
    return client.get_collection(name=COLLECTION)


def write_to_chroma(rows, vectors, pairs):
    """
    写 Chroma 并回填 vector_id。

    id 规则：{knowledge_id}_{chunk_index}，如 kb001_0。
    这个 id 同时是 Chroma 主键和 kb_chunks.vector_id，两边对得上，
    以后要查「某次召回命中的是哪条知识」只需一次 rsplit('_', 1)。
    """
    col = get_collection()
    kids = sorted({r["knowledge_id"] for r in rows})

    # 先删再写：Chroma 的 add 遇到重复 id 会报错，幂等重跑必须这么做。
    # 集合本来就是空的时候 delete 可能抛异常，忽略即可。
    try:
        col.delete(where={"knowledge_id": {"$in": kids}})
    except Exception:  # noqa: BLE001
        pass

    ids = [f"{r['knowledge_id']}_{r['chunk_index']}" for r in rows]
    metas = [
        {
            "knowledge_id": r["knowledge_id"],
            "chunk_index": r["chunk_index"],
            "topic": r.get("topic", ""),
            "aspect": r.get("aspect", ""),
        }
        for r in rows
    ]
    col.add(
        ids=ids,
        documents=[r["chunk_text"] for r in rows],
        metadatas=metas,
        embeddings=vectors,
    )
    print(f"    Chroma 写入 {len(ids)} 条，集合总数 {col.count()}")

    with db.get_conn() as conn:
        conn.executemany(
            "UPDATE kb_chunks SET vector_id = ? WHERE id = ?",
            [(vid, cid) for (cid, _row), vid in zip(pairs, ids)],
        )
    print("    vector_id 已回填")


# ============================================================
# 检索入口（evaluate.py 接这个）
# ============================================================
def search(query, top_k=None):
    """
    检索入口。返回 list[dict]，按相似度从高到低：

        {id, knowledge_id, chunk_index, topic, text, distance, similarity}

    similarity = 1 - cosine_distance，1.0 表示完全一致。
    注意这是「向量相似度」，不是「答案正确率」，0.5 以上只说明
    语义相关，不代表这段知识能回答这个问题。
    """
    top_k = top_k or RAG["top_k"]
    qv = SiliconFlowEmbedding().embed_one(query)
    col = get_collection()
    res = col.query(query_embeddings=[qv], n_results=top_k)

    out = []
    for i, cid in enumerate(res["ids"][0]):
        meta = res["metadatas"][0][i] or {}
        dist = float(res["distances"][0][i])
        out.append({
            "id": cid,
            "knowledge_id": meta.get("knowledge_id", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "topic": meta.get("topic", ""),
            "text": res["documents"][0][i],
            "distance": round(dist, 4),
            "similarity": round(1 - dist, 4),
        })
    return out


def retrieve(query, top_k=None):
    """
    evaluate.py 要的形状：(上下文文本, 召回的知识 id 列表)。

    直接把 build_retriever() 里那段注释的形态实现好，
    接进去只需要 return embed_knowledge.retrieve 一行。
    """
    hits = search(query, top_k)
    ctx = "\n".join(f"[{h['knowledge_id']}] {h['text']}" for h in hits)
    ids = [h["knowledge_id"] for h in hits]
    return ctx, ids


# ============================================================
# 体检 / 自检
# ============================================================
def check():
    print("=" * 60)
    print("embed_knowledge 体检")
    print("=" * 60)

    items = db.list_knowledge(status="active")
    stats = db.knowledge_stats()
    print(f"knowledge 表       : {len(items)} 条 active（全表 {stats['total']} 条）")
    if not items:
        print("[x] knowledge 表是空的，先跑 import_knowledge.py")
        return False

    print(f"kb_chunks 表       : {stats['chunks']} 行")

    sample = items[0]
    pieces = chunk_text(sample["content"])
    print(f"试切 {sample['id']}       : {len(sample['content'])} 字 → {len(pieces)} 块")
    for i, p in enumerate(pieces):
        print(f"      块{i}（{len(p)}字）{p[:36]}...")

    try:
        import chromadb
        print(f"chromadb           : {chromadb.__version__}")
    except ImportError:
        print("chromadb           : [x] 未安装 → pip install chromadb")

    has_key = bool(os.getenv("SILICONFLOW_API_KEY"))
    print(f"SILICONFLOW_API_KEY: {'已配置' if has_key else '[x] 未配置（检查 .env）'}")
    print(f"embedding_model    : {RAG['embedding_model']}")
    print(f"chunk_size/overlap : {RAG['chunk_size']} / {RAG['chunk_overlap']}")

    ok = bool(items) and has_key
    print("=" * 60)
    print("体检" + ("通过，可以正式跑" if ok else "未通过，先修上面标 [x] 的项"))
    return ok


def smoke():
    """检索自检：跑一条真实问题，看首条相似度够不够"""
    print("=" * 60)
    print("检索自检")
    print("=" * 60)
    q = "增肌每天要吃多少蛋白质"
    print(f"query: {q}\n")
    hits = search(q, top_k=RAG["top_k"])
    if not hits:
        print("[x] 没召回任何内容，Chroma 集合可能是空的")
        return False
    for h in hits:
        print(f"  {h['similarity']:.4f}  {h['knowledge_id']}#{h['chunk_index']}  "
              f"{h['text'][:44]}...")
    best = hits[0]["similarity"]
    print()
    if best > 0.5:
        print(f"[ok] 首条相似度 {best:.4f} > 0.5，检索链路通了")
        return True
    print(f"[!] 首条相似度只有 {best:.4f}，检查 embedding 模型是否与建库时一致")
    return False


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="知识库向量化：knowledge → kb_chunks + Chroma")
    ap.add_argument("--check", action="store_true", help="只体检，不调 API 不写库")
    ap.add_argument("--smoke", action="store_true", help="检索自检")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条知识")
    ap.add_argument("--no-chroma", action="store_true", help="只写 kb_chunks")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if check() else 1)
    if args.smoke:
        sys.exit(0 if smoke() else 1)

    if not args.no_chroma:
        try:
            import chromadb  # noqa: F401
        except ImportError:
            print("[x] 没装 chromadb，先 pip install chromadb")
            print("    或者加 --no-chroma 只写 kb_chunks")
            sys.exit(1)

    t0 = time.time()

    print("=" * 60)
    print("Step 1/4  切块")
    print("=" * 60)
    rows, n_kb = build_chunk_rows(limit=args.limit)
    if not rows:
        print("[x] 没有可处理的知识")
        sys.exit(1)
    print(f"    {n_kb} 条知识 → {len(rows)} 块")

    print("=" * 60)
    print("Step 2/4  向量化")
    print("=" * 60)
    emb = SiliconFlowEmbedding()
    vectors = emb.embed([r["chunk_text"] for r in rows])
    print(f"    模型 {emb.model}，维度 {emb.dim}，共 {len(vectors)} 条向量")

    print("=" * 60)
    print("Step 3/4  写 kb_chunks")
    print("=" * 60)
    pairs = write_to_db(rows, vectors)

    if not args.no_chroma:
        print("=" * 60)
        print("Step 4/4  写 Chroma")
        print("=" * 60)
        write_to_chroma(rows, vectors, pairs)
    else:
        print("[i] --no-chroma，已跳过 Chroma")

    stats = db.knowledge_stats()
    print("=" * 60)
    print(f"完成，耗时 {time.time() - t0:.1f}s")
    print(f"kb_chunks 现有 {stats['chunks']} 行")
    if not args.no_chroma:
        try:
            col = get_collection(create=False)
            print(f"Chroma 集合   {col.count()} 条")
            if col.count() != stats["chunks"]:
                print("[!] 两边数量不一致，说明有历史残留，建议重跑一次全量")
        except Exception as e:  # noqa: BLE001
            print(f"[!] 读集合失败：{e}")
    print("=" * 60)
    print("下一步：python3 py/embed_knowledge.py --smoke")


if __name__ == "__main__":
    main()
