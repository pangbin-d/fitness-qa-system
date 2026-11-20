-- ============================================================
-- 健身问答评测系统 · 九张表
-- SQLite 3
-- 用法：python3 py/init_db.py
-- 说明：全部 CREATE ... IF NOT EXISTS，可重复执行，不会破坏已有数据
--      已有旧库升级请先跑 python3 py/migrate_db.py
--
-- 表清单：
--   1. questions   题目表
--   2. models      模型配置表（多模型横向评测的地基）
--   3. prompts     提示词版本表
--   4. tasks       任务表（一次运行 = 一条 task = 一组实验条件）
--   5. results     结果表
--   6. snapshots   快照表
--   7. knowledge   知识库条目表（RAG 检索源）
--   8. kb_chunks   知识库切块表（对应 Chroma 向量）
--   9. configs     全局配置表
-- ============================================================

-- ------------------------------------------------------------
-- 1. questions 题目表
--    承载多批题集：legacy30（旧30题）/ v2_60（新60题）
--    batch 与 topic 是两个正交维度，不要混用
--    qtype 与 is_in_kb 的关系：
--        qtype=kb           -> is_in_kb=1  知识库内可答题
--        qtype=ood          -> is_in_kb=0  普通超纲题（测幻觉，正确行为是承认不知道）
--        qtype=safety_trap  -> is_in_kb=0  安全陷阱题（测安全意识，正确行为是识别风险+拒绝具体建议+建议就医）
--    is_in_kb 保留作快速筛选，qtype 才是权威分类
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id              TEXT PRIMARY KEY,                  -- 题目编号，如 q001
    batch           TEXT NOT NULL,                     -- 题集批次：legacy30 / v2_60
    topic           TEXT NOT NULL,                     -- 六类之一：增肌/减脂/饮食营养/训练安排/动作要领/安全
    aspect          TEXT,                              -- 语义侧面（topic 下的子话题），用于分层检索去重
    qtype           TEXT NOT NULL DEFAULT 'kb',        -- kb / ood / safety_trap
    difficulty      TEXT,                              -- 难度：易/中/难
    question        TEXT NOT NULL,                     -- 题干
    ref_points      TEXT NOT NULL,                     -- 参考答案要点
    score_points    TEXT NOT NULL,                     -- 评分要点
    kb_refs         TEXT NOT NULL DEFAULT '[]',        -- 主答案知识条目ID，JSON数组，召回率只按此字段算
    kb_related      TEXT NOT NULL DEFAULT '[]',        -- 辅助相关知识条目ID，命中算加分不算漏
    is_in_kb        INTEGER NOT NULL DEFAULT 1,        -- 1=库内题 0=超纲题
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ------------------------------------------------------------
-- 2. models 模型配置表
--    多模型横向评测的地基。被测模型与评审模型都在这张表里，
--    用 role 区分。约束：评审模型不得同时出现在被测名单中。
--    api_key 不落库，只存环境变量名。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS models (
    model_key       TEXT PRIMARY KEY,                  -- 内部标识，如 deepseek-v3
    display_name    TEXT NOT NULL,                     -- 展示名，如 DeepSeek-V3
    provider        TEXT NOT NULL,                     -- siliconflow / deepseek / dashscope
    base_url        TEXT NOT NULL,                     -- 如 https://api.siliconflow.cn/v1
    api_key_env     TEXT NOT NULL,                     -- 环境变量名，如 SILICONFLOW_API_KEY
    model_id        TEXT NOT NULL,                     -- 真实请求名，如 deepseek-ai/DeepSeek-V3
    role            TEXT NOT NULL DEFAULT 'candidate', -- candidate=被测 / reviewer=评审
    temperature     REAL DEFAULT 0.3,                  -- 被测默认 0.3，评审必须 0
    enabled         INTEGER NOT NULL DEFAULT 1,
    note            TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ------------------------------------------------------------
-- 3. prompts 提示词版本表
--    同一 name 下多个 version 构成版本序列。
--    is_active=1 表示该 name 当前默认使用的版本。
--    历史提示词只增不改，保证实验结果可追溯。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,                     -- answer=答题 / review=评审
    version         TEXT NOT NULL,                     -- v1_baseline / v2_coach / ...
    content         TEXT NOT NULL,                     -- 完整提示词文本
    changelog       TEXT,                              -- 这一版改了什么
    is_active       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(name, version)
);

-- ------------------------------------------------------------
-- 4. tasks 任务表
--    一次评测运行 = 一条 task = 一组完整实验条件
--    （batch + prompt_version + model_name + rag_enabled 四元组）
--
--    多模型横向评测的做法：每个模型跑一条独立 task，
--    用 experiment_id 把同批次的若干条 task 串成一个实验。
--    这样失败隔离、断点续跑、回归对比都以 task 为单位，语义干净。
--
--    状态机：pending→running→completed
--                          ↘cancelled
--                          ↘failed
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,                  -- 任务ID，如 task_20261113_001
    experiment_id   TEXT,                              -- 实验编号，如 exp_20261116_001；单次运行可为空
    batch           TEXT NOT NULL,                     -- 使用哪批题集
    prompt_version  TEXT NOT NULL,                     -- 提示词版本：v1 / v2 / ...
    model_name      TEXT NOT NULL,                     -- 被测模型 key（对应 models.model_key）
    model_version   TEXT,                              -- 接口实际返回的模型版本（模型换代留痕）
    reviewer_model  TEXT,                              -- 评审模型 key（对应 models.model_key）
    rag_enabled     INTEGER NOT NULL DEFAULT 0,        -- 0=纯模型 1=检索增强
    config_json     TEXT,                              -- 温度、top_k 等完整配置快照
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending/running/completed/cancelled/failed
    total           INTEGER NOT NULL DEFAULT 0,        -- 总题数
    progress        INTEGER NOT NULL DEFAULT 0,        -- 已完成题数
    error_msg       TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    started_at      TEXT,
    finished_at     TEXT
);

-- ------------------------------------------------------------
-- 5. results 结果表
--    每题每次运行一条；run_index 支持同一题重复运行取均值
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    run_index       INTEGER NOT NULL DEFAULT 1,        -- 第几次重复运行（1..N）
    answer          TEXT,                              -- 被测模型的原始回答
    score_accuracy  REAL,                              -- 准确性 1-5
    score_complete  REAL,                              -- 完整性 1-5
    score_safety    REAL,                              -- 安全性 1-5
    score_relevance REAL,                              -- 相关性 1-5
    score_overall   REAL,                              -- 代码加权计算的综合分（不用模型算）
    safety_vetoed   INTEGER NOT NULL DEFAULT 0,        -- 是否触发安全性否决（1=总分被封顶）
    reviewer_model  TEXT,                              -- 本次打分用的评审模型 key（评审换代后分数不可比，必须留痕）
    review_raw      TEXT,                              -- 评审模型原始输出，便于复查
    retrieved_ids   TEXT NOT NULL DEFAULT '[]',        -- 本次实际召回的知识条目ID，JSON数组
    latency_ms      INTEGER,                           -- 单题耗时
    error           TEXT,                              -- 单题异常信息（隔离后记录，不中断任务）
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (task_id)     REFERENCES tasks(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

-- ------------------------------------------------------------
-- 6. snapshots 快照表
--    一次任务的汇总结果，回归对比的比对对象
--    config_json 里必须写明 scoring_rule，因为历史数据用的是
--    简单平均、新数据用的是加权+安全否决，口径不同不可直接比
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS snapshots (
    id              TEXT PRIMARY KEY,                  -- 快照ID，如 snap_20261113_001
    task_id         TEXT NOT NULL,
    experiment_id   TEXT,
    batch           TEXT NOT NULL,
    prompt_version  TEXT,
    model_name      TEXT,
    reviewer_model  TEXT,
    rag_enabled     INTEGER NOT NULL DEFAULT 0,
    data_version    TEXT,                              -- 数据版本戳，如 kb_v4_100
    scoring_rule    TEXT,                              -- simple_average / weighted_with_veto
    metrics_json    TEXT,                              -- 总体均值、分类均值、方差、样本数
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- ------------------------------------------------------------
-- 7. knowledge 知识库条目表
--    RAG 的检索源。100 条权威机构知识点，支持增删改查。
--    status=disabled 的条目不参与检索，但保留在库里便于追溯。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge (
    id              TEXT PRIMARY KEY,                  -- kb001
    topic           TEXT NOT NULL,                     -- 六类之一
    aspect          TEXT,                              -- 语义侧面
    content         TEXT NOT NULL,                     -- 知识正文
    source_title    TEXT,                              -- 来源文献标题
    source_page     TEXT,                              -- 页码
    source_note     TEXT,                              -- 补充说明
    status          TEXT NOT NULL DEFAULT 'active',    -- active / disabled
    data_version    TEXT,                              -- 如 kb_v4_100
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    updated_at      TEXT
);

-- ------------------------------------------------------------
-- 8. kb_chunks 知识库切块表
--    一条 knowledge 按 chunk_size 切分后的块，与 Chroma 向量一一对应。
--    改知识库内容后，对应 chunks 需重建并重新 embedding。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kb_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id    TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,
    vector_id       TEXT,                              -- Chroma 中的 id
    embedded_at     TEXT,
    FOREIGN KEY (knowledge_id) REFERENCES knowledge(id)
);

-- ------------------------------------------------------------
-- 9. configs 配置表
--    键值对，存全局参数与数据版本
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS configs (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    note            TEXT,
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

-- ------------------------------------------------------------
-- 索引
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_q_batch      ON questions(batch);
CREATE INDEX IF NOT EXISTS idx_q_topic      ON questions(topic);
CREATE INDEX IF NOT EXISTS idx_q_qtype      ON questions(qtype);
CREATE INDEX IF NOT EXISTS idx_q_in_kb      ON questions(is_in_kb);
CREATE INDEX IF NOT EXISTS idx_m_role       ON models(role);
CREATE INDEX IF NOT EXISTS idx_p_name       ON prompts(name);
CREATE INDEX IF NOT EXISTS idx_r_task       ON results(task_id);
CREATE INDEX IF NOT EXISTS idx_r_question   ON results(question_id);
CREATE INDEX IF NOT EXISTS idx_s_batch      ON snapshots(batch);
CREATE INDEX IF NOT EXISTS idx_s_experiment ON snapshots(experiment_id);
CREATE INDEX IF NOT EXISTS idx_t_batch      ON tasks(batch);
CREATE INDEX IF NOT EXISTS idx_t_status     ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_t_experiment ON tasks(experiment_id);
CREATE INDEX IF NOT EXISTS idx_k_topic      ON knowledge(topic);
CREATE INDEX IF NOT EXISTS idx_k_status     ON knowledge(status);
CREATE INDEX IF NOT EXISTS idx_c_kid        ON kb_chunks(knowledge_id);

-- ------------------------------------------------------------
-- 初始配置（幂等写入）
--    注意：这里的值只是兜底默认，实际以 py/config.py 为准，
--    init_db.py 会调用 sync_configs() 用 config.py 覆盖
-- ------------------------------------------------------------
INSERT OR IGNORE INTO configs(key, value, note) VALUES
    ('data_version_kb',   'kb_v4_100',             '知识库数据版本'),
    ('data_version_qb',   'qb_legacy30',           '题库数据版本'),
    ('reviewer_model',    'hy4-judge',              '评审模型 key（统一一个，不得与被测重复）'),
    ('score_weights',     '{"准确性":0.25,"完整性":0.25,"安全性":0.25,"相关性":0.25}', '主指标权重（等权）'),
    ('scoring_rule',      'weighted_with_veto',    '评分口径：simple_average / weighted_with_veto'),
    ('repeat_times',      '3',                     '每题重复运行次数'),
    ('rag_top_k',         '3',                     '检索返回条数');
