"""
data_source.py —— 共享数据源

作用：
    放原始知识文本 + 中文友好的切分函数。
    step2 / step3 / step4 都从这里拿 chunks，避免每个文件重复贴一遍文本。

为什么单独拆一个文件：
    等你后面换成真实文档（PDF、txt、网页）时，只需要改这个文件，
    上面三层逻辑一行都不用动。
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ── 原始知识文本 ────────────────────────────────────────────────
# 先用一小段健身知识做验证，后面换成你题库里的 30 条知识库内容。
# 注意：每句话都是一个完整语义单元，方便观察切分效果。
RAW_TEXT = """增肌期每日蛋白质摄入建议为每公斤体重 1.6 到 2.2 克。
对于体重 78 公斤的健身者，目标摄入量约为 125 到 172 克。
蛋白质来源应优先选择鸡胸肉、鸡蛋、瘦牛肉、鱼类和乳制品。
训练后 30 分钟内补充 20 到 40 克蛋白质有助于肌肉合成。
蛋白质摄入过量会增加肾脏代谢负担，肾功能异常者需咨询医生。
深蹲时膝盖内扣是常见错误，应先降低重量纠正动作模式。
深蹲下蹲时膝盖可以略微超过脚尖，这不是错误，关键看重心是否稳定。
硬拉时腰背必须保持中立位，避免弓背导致腰椎损伤。
硬拉起始阶段应该用腿部发力而不是腰部发力。
卧推时肩胛骨要收紧下沉，避免肩关节前侧过度受力。
有氧训练建议每周 3 到 4 次，每次 30 到 45 分钟中等强度。
减脂期热量缺口建议控制在每日 300 到 500 千卡。
减脂速度过快会导致肌肉流失，建议每周减重不超过体重的百分之一。
训练前出现关节刺痛应该立即停止训练并就医检查。
连续训练同一肌群需要间隔 48 小时以上，让肌肉充分恢复。"""


# ── 切分函数 ────────────────────────────────────────────────────
def build_chunks(chunk_size: int = 60, chunk_overlap: int = 15):
    """
    把原始文本切成小块，返回 Document 列表。

    参数说明：
        chunk_size    每块最大字符数。中文按字符算，60 个字大约是一到两句。
        chunk_overlap 相邻块重叠的字符数。设 15 是为了防止跨块的句子丢上下文。

    关键点：
        separators 里加了中文标点 "。" "，" 等。
        默认分隔符是 ["\n\n", "\n", " ", ""] —— 全是英文习惯，
        切中文会在句子中间硬断，检索出来的片段读起来莫名其妙。
    """
    doc = Document(
        page_content=RAW_TEXT,
        metadata={"source": "健身知识库", "topic": "营养与训练"},
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "，", ""],
    )

    return splitter.split_documents([doc])


if __name__ == "__main__":
    # 直接运行本文件可以预览切分效果
    chunks = build_chunks()
    print(f"共切出 {len(chunks)} 块\n")
    for i, c in enumerate(chunks):
        print(f"[{i:02d}] ({len(c.page_content):>2}字) {c.page_content}")
