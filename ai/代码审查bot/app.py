#!/usr/bin/env python3
"""AI代码审查Bot — 分析PR diff并给出建议"""
import json, os, sys
from typing import Optional
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "demo"))

SYSTEM_PROMPT = """你是一个资深代码审查专家。请审查以下代码 diff，关注:
1. 潜在的 bug 和安全漏洞
2. 代码风格和最佳实践
3. 性能优化建议
4. 测试覆盖建议
"""

def review_diff(diff_text: str, model: str = "gpt-4o") -> dict:
    """审查代码 diff 并返回结构化建议"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请审查以下代码 diff:\n\n{chr(96)*3}diff\n{diff_text}\n{chr(96)*3}"},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return {
        "review": response.choices[0].message.content,
        "model": model,
        "usage": response.usage.total_tokens if response.usage else 0,
    }

def format_review(review: dict) -> str:
    """格式化审查结果为 Markdown"""
    return f"""## 🤖 AI 代码审查报告

**模型**: {review['model']}
**Token 用量**: {review['usage']}

{review['review']}
"""

def main():
    if len(sys.argv) < 2:
        print("用法: python code_review.py <diff_file>")
        sys.exit(1)

    diff_path = sys.argv[1]
    with open(diff_path) as f:
        diff_text = f.read()

    print(f"审查中... ({len(diff_text)} 字符)")
    result = review_diff(diff_text)
    print(format_review(result))

if __name__ == "__main__":
    main()
