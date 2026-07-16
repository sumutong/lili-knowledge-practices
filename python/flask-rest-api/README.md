# Flask 全栈 RESTful API

Flask + SQLAlchemy + JWT 实现的完整 RESTful 用户与文章管理系统。

## 功能
- 用户注册/登录（JWT 认证）
- 文章 CRUD（含 slug 自动生成）
- 分页、搜索、过滤
- Marshmallow 请求验证
- Blueprint 模块化架构
- 管理员权限控制

## 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/flask_api"
export SECRET_KEY="your-secret-key"

# 初始化数据库
flask init-db

# 启动服务
python app.py
```

## API 测试

```bash
# 注册
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123456"}'

# 登录
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123456"}'

# 获取文章列表
curl http://localhost:5000/api/posts

# 健康检查
curl http://localhost:5000/api/health
```
