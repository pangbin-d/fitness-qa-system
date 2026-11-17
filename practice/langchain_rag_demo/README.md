# LangChain RAG 最小闭环 Demo

用于验证 LangChain 1.x 下 RAG 链路的完整实现，作为毕设主项目 RAG 链路重写的技术预研。

## 技术栈

| 组件 | 选型 | 说明 |
|---|---|---|
| 框架 | LangChain 1.x | 全程用 LCEL，不用 0.x legacy chains |
| 模型 | DeepSeek V4.1 Flash | `deepseek-flash` |
| Embedding | BAAI/bge-small-zh-v1.5 | 本地开源，512 维，免费 |
| 向量库 | Chroma | 落盘到 `./chroma_demo/` |

> ⚠️ DeepSeek 不提供 embedding API，只有 chat 接口，所以向量化必须用别的方案。
> 这里选本地模型，不额外花钱、不依赖外部服务。

## 文件说明

```
langchain_rag_demo/
├── data_source.py      共享数据源：原始文本 + 中文友好切分函数
├── step1_model.py      第一步：模型连通性验证
├── step2_split.py      第二步：文档切分，对比不同 chunk_size 的效果
├── step3_store.py      第三步：向量入库 + 检索准确性自检
├── step4_rag.py        第四步：LCEL 串联完整 RAG 链
├── requirements.txt
├── .env.example
└── .gitignore
```

## 运行方式

### 1. 建虚拟环境

```bash
cd practice/langchain_rag_demo
python -m venv .venv

# Git Bash
source .venv/Scripts/activate
# CMD
.venv\Scripts\activate
```

### 2. 装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 Key

```bash
cp .env .env
```

用编辑器打开 `.env`，填入真实的 `DEEPSEEK_API_KEY`。

### 4. 按顺序跑

```bash
python step1_model.py    # 验证模型能通
python step2_split.py    # 看切分效果
python step3_store.py    # 验证检索准确（首次会下载 bge 模型约 95MB）
python step4_rag.py      # 完整 RAG 链
```

**必须按顺序**。step3 依赖 step2 的切分逻辑，step4 依赖 step3 的向量库。

## 每步的验收标准

| 步骤 | 怎么算通过 |
|---|---|
| step1 | 打印出一句中文回答，且显示 token 用量 |
| step2 | 每块都在 80 字以内，结尾是标点，没有句子被硬切断 |
| step3 | 三个测试问题全部命中，输出里有 `[√] 检索正常` |
| step4 | 测试 1、2 答出具体数值；测试 3 老实说「资料中没有提到」 |

**step3 不过就别进 step4。** 检索不准的话，后面接多强的模型都是白搭。

## 已知坑

| 现象 | 原因 | 解法 |
|---|---|---|
| `ModuleNotFoundError: langchain.chains` | 抄了 0.x 写法 | 改用 LCEL：`prompt \| model \| parser` |
| `Model not found` | 用了 `deepseek-chat` | 改 `deepseek-flash` |
| 检索结果全是无关片段 | embedding 用了英文模型 | 换 `bge-small-zh-v1.5` |
| 中文被切成半句 | 默认分隔符是英文的 | separators 里加 `"。"` `"，"` |
| 首次运行卡几分钟 | 在下载 bge 模型 | 等，别 Ctrl+C |
| Windows 终端中文乱码 | 编码问题 | `chcp 65001` 切 UTF-8 |

## 与主项目的关系

本 Demo 是**独立验证**，不 import 主项目任何代码。

验证通过后，把链路迁移到主项目，替换现有的裸 Chroma 实现。届时需要处理：

1. 数据源从这段示例文本换成真实知识库
2. embedding 要与主项目保持一致（否则历史基线不可比）
3. 模型调用封装成可配置项，方便做多模型横向评测

## 版本备注

- 课程视频录制于 2026-06，代码大概率是 LangChain 0.x 写法
- 本项目按 LangChain 1.x 编写，**只看概念，不抄代码**
- `deepseek-chat` / `deepseek-reasoner` 已于 2026-07-24 停用
