#!/usr/bin/env python3
"""多Agent协作工作流 — 使用LangChain构建"""
import json, os, subprocess, sys
from pathlib import Path
from typing import Optional

class Agent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    def execute(self, task: str) -> str:
        return f"[{self.name}] 完成任务: {task}"

class Workflow:
    def __init__(self):
        self.agents = {}
        self.steps = []

    def add_agent(self, agent: Agent):
        self.agents[agent.name] = agent

    def add_step(self, agent_name: str, task: str):
        self.steps.append((agent_name, task))

    def run(self) -> dict:
        results = {}
        for name, task in self.steps:
            if name not in self.agents:
                results[name] = f"Agent {name} 不存在"
                continue
            results[name] = self.agents[name].execute(task)
        return results

def read_file_content(filepath: str) -> str:
    """读取文件内容，用于Agent分析"""
    try:
        path = Path(filepath).expanduser()
        content = path.read_text(encoding="utf-8")[:5000]
        fence = chr(96) * 3  # backticks
        return f"文件: {path.name}\n{fence}\n{content}\n{fence}"
    except FileNotFoundError:
        return f"文件未找到: {filepath}"
    except Exception as e:
        return f"错误: {e}"

def main():
    wf = Workflow()
    wf.add_agent(Agent("分析师", "数据分析"))
    wf.add_agent(Agent("程序员", "代码编写"))
    wf.add_agent(Agent("测试员", "质量保证"))

    wf.add_step("分析师", "分析项目需求")
    wf.add_step("程序员", "编写核心代码")
    wf.add_step("测试员", "运行测试用例")

    results = wf.run()
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # 读取文件演示
    if len(sys.argv) > 1:
        print(read_file_content(sys.argv[1]))

if __name__ == "__main__":
    main()
