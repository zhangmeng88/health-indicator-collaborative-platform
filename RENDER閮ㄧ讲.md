# 部署到 Render

本工程已内置 `render.yaml`（Blueprint），可在 Render 上一键拉起：托管 PostgreSQL + 后端（Docker）+ 前端（静态站点）。前端通过 rewrite 把 `/api/*` 反代到后端，浏览器同源访问、**无跨域**。

## 一、准备

1. 注册 [Render](https://render.com) 账号。
2. 把本工程推到一个 GitHub / GitLab 仓库（确保 `render.yaml` 在仓库**根目录**）。

## 二、一键部署

1. Render 控制台 → **New** → **Blueprint**。
2. 选择你的仓库，Render 会读取 `render.yaml` 并列出将创建的资源：数据库 `hsr-db`、后端 `hsr-backend`、前端 `hsr-frontend`。
3. 系统会提示输入 **ADMIN_PASSWORD**（标记为 `sync: false` 的密钥）——填一个强密码。
4. 点击 **Apply**，等待三者依次构建完成。

后端首次启动会自动建表并播种（管理员 + 示例数据）。

## 三、关键一步：核对后端地址

Blueprint 里前端把 API 反代到了 `https://hsr-backend.onrender.com`。如果你的后端服务名被占用，Render 会**加随机后缀**，真实地址会不同。

部署完成后：

1. 打开后端服务，复制其真实公网 URL（形如 `https://hsr-backend-xxxx.onrender.com`）。
2. 若与默认不一致，编辑 `render.yaml` 中前端 `routes` 的 `destination`，改成真实地址：
   ```yaml
   - type: rewrite
     source: /api/*
     destination: https://hsr-backend-xxxx.onrender.com/api/*
   ```
   提交后 Render 自动重新部署；或直接在前端服务的 **Redirects/Rewrites** 设置里改（无需改代码）。

完成后访问前端 URL，用 `admin` + 你设置的密码登录。

## 四、导入完整指标数据

**最简单：网页上传（推荐）。** 用管理员登录平台 → 左侧「导入 / 导出」→「上传现有标准」→ 选择 `2018卫生统计指标完整.xlsx` → 开始导入。导入完成会显示新增/跳过数量，指标随即出现在「指标总览」。按标识符去重，可重复上传。

**备选：命令行直连数据库导入。** 适合批量/自动化场景。

1. 在 Render 数据库页复制 **External Database URL**（形如 `postgresql://user:pwd@xxx.oregon-postgres.render.com/hsr`）。
2. 本机执行（需 Python，且装好 openpyxl、psycopg2-binary、SQLAlchemy）：
   ```bash
   cd backend
   pip install -r requirements.txt
   DATABASE_URL="<External URL>?sslmode=require" \
     python scripts/import_xlsx.py /path/to/2018卫生统计指标完整.xlsx
   ```
   外部连接需加 `?sslmode=require`。脚本幂等，可重复运行。

> 也可在后端服务的 **Shell**（Render 控制台）里运行导入，但需先把 xlsx 放入 `backend/` 并提交，使其包含在镜像中。

## 五、注意事项（免费档）

- **免费 Web 服务**闲置一段时间会休眠，下次访问有几十秒冷启动；正式使用请把后端 `plan` 改为付费档（`starter` 等）。
- **免费 PostgreSQL** 有存续期限制（到期会被回收），正式使用请选付费实例，并在数据库页开启/配置备份。
- 改 `plan` 只需编辑 `render.yaml` 后重新 Apply。

## 六、自定义域名（可选）

在前端服务的 **Settings → Custom Domains** 添加你的域名，按提示配置 DNS，Render 自动签发 HTTPS 证书。

---

## 三种部署方式对照

| 方式 | 适用 | 入口 |
|------|------|------|
| 本机 Docker Compose | 本地试用 / 内网服务器 | `docker-compose.yml`（见根 README） |
| Render Blueprint | 云端托管、零运维 | `render.yaml`（本文档） |
| 自有服务器手工部署 | 需完全自控 | 见根 README「部署」一节 |

> Render 与本机 Docker 用的是**同一套**后端/前端代码；区别仅在编排：Render 用托管 Postgres 并注入 `DATABASE_URL`，前端用静态站点 + rewrite 取代了 nginx 容器。
