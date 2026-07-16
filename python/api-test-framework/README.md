# API 自动化测试框架

基于 pytest 构建的可扩展 API 测试框架，支持 YAML/JSON 数据驱动、Schema 校验、HTTP 压测。

## 结构

```
api-test-framework/
├── conftest.py        # 全局 fixtures 和配置
├── test_users.py      # API 测试用例
├── benchmark.py       # HTTP 压测工具
└── test_data/         # 数据驱动测试数据
    └── ddt_example.yaml
```

## 运行

```bash
pip install -r requirements.txt

# 运行 API 测试
pytest test_users.py -v

# 运行压测
python benchmark.py
```
