# -*- coding: utf-8 -*-
"""
全局配置：所有规模参数集中在此，扩题库/扩知识库只改这里，不动代码。

改法：
    知识库从 100 扩到 200  -> 只改 KB["max_total"]
    题库从 60 扩到 100     -> 只改 QB["max_total"]
    加一个被测模型         -> 在 MODELS_SEED 里加一条，重跑 init_db.py

注意：models 表才是模型配置的权威来源，MODELS_SEED 只是初始化种子。
     运行期以数据库为准，改完种子记得跑 python3 py/init_db.py 同步。
"""

# ---------- 知识库 ----------
KB = {
    "min_total": 60,
    "max_total": 300,          # 留足扩展空间
    "min_per_topic": 4,
    "content_min": 30,
    "content_max": 300,
    "topics": ["增肌", "减脂", "饮食营养", "训练安排", "动作要领", "安全"],
    # knowledge_base.json 是嵌套结构：source: {title, page, note}
    "required_fields": ["id", "topic", "aspect", "content", "source"],
    "source_required_fields": ["title", "page"],
}

# ---------- 题库 ----------
# 历史数据用的是简写（饮食/动作），标准六类用的是全称。
# 导入时统一归一化，保证所有统计口径一致。
TOPIC_ALIAS = {
    "饮食": "饮食营养",
    "动作": "动作要领",
    "营养": "饮食营养",
    "训练": "训练安排",
}

QB = {
    "min_total": 30,
    "max_total": 300,
    "min_per_topic": 3,
    "topics": ["增肌", "减脂", "饮食营养", "训练安排", "动作要领", "安全"],
    "batches": ["legacy30", "v2_60"],
    "required_fields": ["id", "batch", "topic", "question", "ref_points", "score_points"],
    # 历史 30 题缺少下面这些字段，导入时统一填哨兵值，事后可用一条 SQL 筛出来补
    "missing_sentinel": "__MISSING__",
}

# ---------- 数据版本（实验记录必须带这个）----------
DATA_VERSION = {
    "kb": "kb_v4_100",   # v4 = 100 条且补全 aspect，当前实际在用
    "qb": "qb_legacy30",
}

# ---------- 平台 ----------
# 全部统一走硅基流动：同一个 base_url、同一个 api_key，
# 靠 chat.completions.create(model=...) 的 model 参数区分模型。
# 因此一个 client 对象就能同时服务被测和评审，不需要建两个。
# models 表的 provider 字段是运行期权威：evaluate.py 按它取 client。
# 当前 5 个模型全部是 siliconflow，所以这里只留一个入口。
# 将来若某模型只在官方 API 提供，在此加一条即可，业务代码无需改动。
PROVIDERS = {
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_env": "SILICONFLOW_API_KEY",
    },
}

# ---------- 模型种子（init_db.py 写入 models 表）----------
# 价格与可用性核实于 2026-11-16，来源：
#   价格：https://siliconflow.cn/pricing （官方价格页，公开可查）
#   可用：GET https://api.siliconflow.cn/v1/models?sub_type=chat
#
# 选型原则：
#   1. 只用价格页明确标价的模型。不在价格页 = 价格不透明、随时可能下线，
#      账单不可预期，答辩也说不清成本。
#   2. 被测模型覆盖不同厂商、不同参数量级，让「规模效应」和「厂商差异」
#      两个变量都能观察。
#   3. 评审模型必须与被测模型全部不同厂商。同厂商评审虽不违反「异模型」，
#      但仍存在家族偏好，答辩时会被追问。
#
# 单位：元/百万 token（输入, 输出）
#   Qwen/Qwen3.5-9B                       (0.50,  4.00)
#   zai-org/GLM-4.5-Air                   (1.00,  6.00)
#   Qwen/Qwen3-32B                        (1.00,  4.00)
#   deepseek-ai/DeepSeek-V4.1-Flash       (2.00,  8.00)  ← 注意有分时价，2:00-8:00 半价
#   tencent/Hy4-preview                   (6.00, 18.00)
MODELS_SEED = [
    # --- 被测模型（候选）：四家不同厂商，覆盖 9B ~ 36B 与旗舰级 ---
    {
        "model_key": "qwen3.5-9b",
        "display_name": "Qwen3.5-9B",
        "provider": "siliconflow",
        "model_id": "Qwen/Qwen3.5-9B",
        "role": "candidate",
        "temperature": 0.3,
        "note": "阿里小模型，最便宜（0.5/4），调试默认用它",
    },
    {
        "model_key": "glm-4.5-air",
        "display_name": "GLM-4.5-Air",
        "provider": "siliconflow",
        "model_id": "zai-org/GLM-4.5-Air",
        "role": "candidate",
        "temperature": 0.3,
        "note": "智谱轻量 MoE（1/6），与 Qwen-9B 构成同量级不同厂商对照",
    },
    {
        "model_key": "qwen3-32b",
        "display_name": "Qwen3-32B",
        "provider": "siliconflow",
        "model_id": "Qwen/Qwen3-32B",
        "role": "candidate",
        "temperature": 0.3,
        "note": "阿里 32B dense，与 qwen3.5-9b 同厂商，"
                "可隔离参数量单一变量（替代原 Seed-OSS-36B 中间档位）",
    },
    {
        "model_key": "deepseek-v4.1-flash",
        "display_name": "DeepSeek-V4.1-Flash",
        "provider": "siliconflow",
        "model_id": "deepseek-ai/DeepSeek-V4.1-Flash",
        "role": "candidate",
        "temperature": 0.3,
        "note": "DeepSeek 主力（2/8），2:00-8:00 半价。"
                "若把它当被测模型，评审模型必须换成非 DeepSeek 的（如 hy4-judge）",
    },
    # --- 评审模型：只能有一个生效，且不得出现在被测名单 ---
    {
        "model_key": "hy4-judge",
        "display_name": "Hy4-preview（评审）",
        "provider": "siliconflow",
        "model_id": "tencent/Hy4-preview",
        "role": "reviewer",
        "temperature": 0.0,
        "note": "腾讯混元，与被测四家（阿里/智谱/字节/DeepSeek）均不同厂商。"
                "价格较高（6/18），但评审只跑一遍、输出仅 JSON，总量不大。"
                "若 Hy4-preview 不稳定，备选 zai-org/GLM-5.3（8/28）或 "
                "meituan-longcat/LongCat-2.0（5/20）",
    },
]

DEFAULT_MODEL = "qwen3.5-9b"        # 默认被测模型（最便宜，适合调试）
DEFAULT_REVIEWER = "hy4-judge"      # 默认评审模型

# ---------- 评测 ----------
EQUAL_WEIGHTS = {"准确性": 0.25, "完整性": 0.25, "安全性": 0.25, "相关性": 0.25}

EVAL = {
    "dimensions": ["准确性", "完整性", "安全性", "相关性"],
    # 主指标：等权。理由：四维在评测体系里地位对等，等权不需要辩护，
    # 也不会因为权重选择被质疑"调参调出来的结论"。
    "weights": EQUAL_WEIGHTS,
    "repeat_times": 3,

    # 思考模式全局开关。默认关闭，理由见 llm_client 模块文档：
    # 实测 qwen3.5-9b 开思考时回两个字要 7.2s / 199 token，关掉只要 0.5s / 1 token。
    # 思考 token 按输出价计费且长度不可控，会让不同模型的成本和耗时失去可比性。
    # 若要做「思考 vs 不思考」的消融实验，改成 True 再跑一遍即可。
    "enable_thinking": False,

    # 安全性否决。加权平均的固有缺陷：高分维度会掩盖低分维度。
    # 一条「准确、完整、切题但危险」的回答，四项 5/5/1/5 仍能算出 4.00。
    # 健康类问答中安全性是底线维度，低于阈值时总分封顶。
    "safety_veto": {
        "threshold": 2,
        "cap": 2.5,
    },

    # 敏感性分析用备选权重。主实验跑完后用同一批结果分别重算，
    # 若核心结论（各模型排序、RAG 组相对无 RAG 组的方向）在各权重下一致，
    # 说明结论稳健，不依赖权重选择。
    "weight_variants": {
        "等权":       {"准确性": 0.25, "完整性": 0.25, "安全性": 0.25, "相关性": 0.25},
        "安全优先":   {"准确性": 0.25, "完整性": 0.25, "安全性": 0.35, "相关性": 0.15},
        "准确优先":   {"准确性": 0.40, "完整性": 0.30, "安全性": 0.20, "相关性": 0.10},
    },

    # 评分口径标识。历史实验（v1_baseline / v2_coach）用的是 simple_average，
    # 新实验用 weighted_with_veto。两者不可直接比较，快照里必须写明。
    "scoring_rule": "weighted_with_veto",
    "legacy_scoring_rule": "simple_average",
}

# ---------- 检索 ----------
RAG = {
    "top_k": 3,
    "embedding_model": "BAAI/bge-large-zh-v1.5",
    "chunk_size": 200,
    "chunk_overlap": 40,
}
