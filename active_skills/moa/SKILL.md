---
name: moa
description: "Mixture of Agents: 让多个前沿模型辩论，然后综合最佳见解生成更优答案"
metadata:
  {
    "copaw":
      {
        "emoji": "🤖",
        "requires": []
      }
  }
---

# Mixture of Agents (MoA) 技能

## 概述

Mixture of Agents (MoA) 利用多个 LLM 的集体优势增强性能。在 AlpacaEval 2.0 上以 **65.1%** 超越 GPT-4 Omni 的 57.5%！

## 工作原理

```
用户问题 → Layer 1 (多模型回答) → Layer 2 (聚合优化) → 最终答案
```

## API 选择

支持两种 API，**任选其一**：

| API | 环境变量 | 优势 |
|-----|---------|------|
| OpenRouter | OPENROUTER_API_KEY | 统一入口，模型丰富 |
| Together | TOGETHER_API_KEY | 开源模型多，价格低 |

## 使用 OpenRouter (推荐)

```bash
pip install openai
export OPENROUTER_API_KEY=your_key
```

```python
import openai
import os

client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# 参考模型 (OpenRouter 格式)
models = [
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3.3-70b-instruct", 
    "mistralai/mixtral-8x7b-instruct"
]

def run_moa(prompt: str) -> str:
    # Layer 1: 收集各模型答案
    responses = []
    for model in models:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        responses.append(r.choices[0].message.content)
    
    # Layer 2: 聚合答案
    agg_prompt = f"""原问题: {prompt}

多个模型的回答:
{chr(10).join([f'Model {i+1}: {r}' for i, r in enumerate(responses)])}

请综合以上回答，生成最优答案:"""

    final = client.chat.completions.create(
        model="qwen/qwen-2.5-72b-instruct",
        messages=[{"role": "user", "content": agg_prompt}]
    )
    return final.choices[0].message.content
```

## 使用 Together API

```bash
pip install together
export TOGETHER_API_KEY=your_key
```

```python
from together import Together
import os

client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

models = [
    "Qwen/Qwen2.5-72B-Instruct-Turbo",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
]

# 同上 MoA 逻辑...
```

## 使用场景

- 需要多角度分析的复杂问题
- 追求超越单一模型的答案
- 重要决策需要多模型意见
- 股票分析、投资决策等高质量输出需求

## 注意事项

1. 成本比单一模型高 (约$0.03/query)
2. 响应时间较长 (3-5个模型调用)
3. 可调整模型数量和层数

## 参考

- [GitHub](https://github.com/togethercomputer/MoA)
- [论文](https://arxiv.org/abs/2406.04692)
- [OpenRouter](https://openrouter.ai)
- [Together AI](https://together.ai)
