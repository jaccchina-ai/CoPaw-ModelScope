#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mixture of Agents (MoA) 多层分析演示
支持 2层/3层/多层分析
"""

import os
from together import Together

# 初始化客户端
client = Together(api_key=os.getenv("TOGETHER_API_KEY", ""))

# 参考模型（Layer 1 用于回答的模型）
REFERENCE_MODELS = [
    "MiniMaxAI/MiniMax-M2.5",
    "moonshotai/Kimi-K2.5",
    "openai/gpt-oss-120b",
    "deepseek-ai/DeepSeek-V3.1",
    "Qwen/Qwen3.5-397B-A17B"
]

# 聚合模型（用于综合答案的模型）
AGGREGATOR_MODEL = "deepseek-ai/DeepSeek-V3.1"


def run_moa(prompt: str, layers: int = 3) -> dict:
    """
    运行 MoA 多层分析
    
    Args:
        prompt: 用户问题
        layers: 层数 (2层 或 3层)
    
    Returns:
        dict: 包含各层结果的字典
    """
    result = {
        "prompt": prompt,
        "layers": layers,
        "layer1_responses": [],
        "layer2_response": None,
        "layer3_response": None,
        "final_response": None
    }
    
    print(f"\n{'='*60}")
    print(f"MoA 多层分析 (共 {layers} 层)")
    print(f"{'='*60}")
    
    # ========== Layer 1: 多模型独立回答 ==========
    print(f"\n【Layer 1】{len(REFERENCE_MODELS)} 个模型独立回答...")
    
    for i, model in enumerate(REFERENCE_MODELS, 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512
            )
            answer = response.choices[0].message.content
            result["layer1_responses"].append({
                "model": model,
                "response": answer
            })
            print(f"  模型 {i} ({model.split('/')[-1]}): 完成 ✓")
        except Exception as e:
            print(f"  模型 {i} 失败: {e}")
            result["layer1_responses"].append({
                "model": model,
                "response": f"错误: {e}"
            })
    
    # ========== Layer 2: 聚合答案 ==========
    print(f"\n【Layer 2】聚合优化...")
    
    # 构建 Layer 1 答案汇总
    layer1_summary = "\n\n".join([
        f"### 模型 {i+1} ({r['model'].split('/')[-1]}):\n{r['response']}"
        for i, r in enumerate(result["layer1_responses"])
    ])
    
    layer2_prompt = f"""你是一个专业的分析助手。以下是多个 AI 模型对同一个问题的回答。

原问题: {prompt}

各模型的回答:
{layer1_summary}

请综合以上所有模型的见解，取其精华，生成一个更全面、更准确的答案。"""

    try:
        response = client.chat.completions.create(
            model=AGGREGATOR_MODEL,
            messages=[{"role": "user", "content": layer2_prompt}],
            max_tokens=1024
        )
        result["layer2_response"] = response.choices[0].message.content
        print(f"  聚合完成 ✓")
    except Exception as e:
        print(f"  聚合失败: {e}")
        result["layer2_response"] = f"错误: {e}"
    
    # ========== Layer 3 (可选): 再次优化 ==========
    if layers >= 3:
        print(f"\n【Layer 3】深度优化...")
        
        layer3_prompt = f"""你是一个资深专家。以下是经过初步聚合的答案，请进一步优化：

原问题: {prompt}

初步聚合答案:
{result["layer2_response"]}

请进一步深化分析，补充遗漏要点，使答案更加精准、有洞察力。"""

        try:
            response = client.chat.completions.create(
                model=AGGREGATOR_MODEL,
                messages=[{"role": "user", "content": layer3_prompt}],
                max_tokens=1024
            )
            result["layer3_response"] = response.choices[0].message.content
            print(f"  深度优化完成 ✓")
        except Exception as e:
            print(f"  深度优化失败: {e}")
            result["layer3_response"] = f"错误: {e}"
    
    # 最终答案
    if layers >= 3 and result.get("layer3_response"):
        result["final_response"] = result["layer3_response"]
    else:
        result["final_response"] = result["layer2_response"]
    
    return result


def print_result(result: dict):
    """打印分析结果"""
    print(f"\n{'='*60}")
    print("【最终答案】")
    print(f"{'='*60}")
    print(result["final_response"])
    
    print(f"\n{'='*60}")
    print("【分析统计】")
    print(f"{'='*60}")
    print(f"层数: {result['layers']}")
    print(f"参与模型: {len(REFERENCE_MODELS)} 个")
    print(f"Layer 1 模型: {[m.split('/')[-1] for m in REFERENCE_MODELS]}")


if __name__ == "__main__":
    # 示例：分析今天选出的股票
    test_prompt = """分析以下股票的投资价值：
1. 赣能股份(000899) - 2板，智能电网板块
2. 云南锗业(002428) - 2板，通信板块
请从基本面、技术面、市场情绪三个角度分析。"""
    
    # 2层分析（推荐日常使用）
    print("\n" + "="*70)
    print("示例：2层 MoA 分析")
    print("="*70)
    result_2layer = run_moa(test_prompt, layers=2)
    print_result(result_2layer)
    
    # 3层分析（用于重要决策）
    # result_3layer = run_moa(test_prompt, layers=3)
    # print_result(result_3layer)
