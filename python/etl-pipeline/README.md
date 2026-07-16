# ETL 数据清洗管道

从多种数据源（CSV、Excel、JSON、API）抽取数据，使用 pandas 进行清洗、转换、去重、标准化，批量写入 PostgreSQL。

## 特性
- 多数据源支持（CSV/Excel/JSON/Parquet/API/DB）
- 列映射与类型转换
- 标准化清洗步骤（去重、空值、列名规范化）
- 邮箱/手机号验证
- 管道血缘追踪
- 增量 Upsert

## 运行

```bash
pip install -r requirements.txt
mkdir -p data
echo "Order ID,Customer Name,Email,Phone,Product,Quantity,Price,Order Date,Status" > data/orders_2024.csv
echo "1,张三,zhangsan@example.com,13800138000,iPhone 15,2,6999.00,2024-01-15,completed" >> data/orders_2024.csv
python pipeline.py
```
