# 本地打开 FlowRemote 产品介绍页（Windows）

这份教程带你在本机启动 FlowRemote，并打开新增的产品介绍页。
介绍页是独立静态页，位于 `src\flowremote\ui\static\landing.html`，
**没有修改原产品的任何页面或代码**。

所有命令都在 **`Knight-hell` 项目目录**中执行，不是 `ENT207` 根目录。

## 1. 准备环境

需要：

- Windows 10/11
- Python 3.13（推荐交给 uv 管理，不一定要单独安装）
- [uv](https://docs.astral.sh/uv/)（安装依赖、运行命令）
- Git（获取代码）

检查 uv 是否可用：

```powershell
uv --version
```

如果提示 `uv` 不是可识别的命令，安装后重新打开 PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 2. 获取代码

首次获取：

```powershell
git clone https://github.com/xianhuiqizi/Knight-hell.git
cd Knight-hell
```

已经在本地时，直接进入项目目录并拉取最新代码：

```powershell
cd path\to\Knight-hell
git pull
```

确认当前目录中存在 `pyproject.toml`、`src\flowremote` 和
`src\flowremote\ui\static\landing.html`。

## 3. 安装依赖（首次运行）

```powershell
uv sync
```

这会把 Python 3.13 和项目依赖安装到 `.venv`。

也可以运行项目自带的一键脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

脚本会检测并安装 uv、Python 3.13 和依赖，重复执行是安全的。

## 4. 生成演示数据（首次运行或需要重置时）

```powershell
uv run python src\flowremote\devtools\seed.py --reset --verify
```

成功时会看到类似输出：

```text
seeded 1 task, 100 source records, 12 exceptions, 0 decisions, 0 approvals
demo accounts (password: 123456)
  operator : alex.morgan@example.com
  admin    : admin@example.com
```

> `--reset` 会删除并重建 `data\runtime\flowremote.db`。
> 如果本地已经注册了想保留的账号，先备份这个文件，或去掉 `--reset` 直接运行 seed。
> 演示库需要处于初始状态时，再使用 `--reset`。

## 5. 启动网站

```powershell
uv run uvicorn flowremote.api.app:app --reload --host 127.0.0.1 --port 8000
```

看到下面的日志就表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

保持这个 PowerShell 窗口开启。关闭窗口或在窗口中按 `Ctrl+C` 会停止网站。

## 6. 在浏览器中打开

| 页面 | 地址 |
| --- | --- |
| **产品介绍页（新增）** | http://127.0.0.1:8000/static/landing.html |
| 应用入口 | http://127.0.0.1:8000/ |
| 登录 | http://127.0.0.1:8000/login |
| 注册 | http://127.0.0.1:8000/signup |

说明：

- 介绍页是 `src\flowremote\ui\static\landing.html`，由应用现有的 `/static`
  静态目录直接提供，不需要登录，也不会改变原产品的首页、登录页或任何业务逻辑。
- 介绍页上的 **Try the live demo** 等按钮会跳到原产品的 `/login` 页面；
  原产品仍按它原本的方式工作。
- 第一次打开如果浏览器有缓存，按 `Ctrl+F5` 强制刷新。

### 演示账号

| 账号 | 密码 | 权限 |
| --- | --- | --- |
| `alex.morgan@example.com` | `123456` | operator，只能看到 TASK-1001 |
| `admin@example.com` | `123456` | admin，可以看到全部任务 |

演示账号只用于本地课程演示；OA/BI 的外部写入是模拟的，应用内会明确标注。

## 7. 停止和再次启动

停止：在运行 uvicorn 的窗口中按 `Ctrl+C`。

下次启动不需要重新安装依赖，也不需要重新 seed：

```powershell
cd path\to\Knight-hell
uv run uvicorn flowremote.api.app:app --reload --host 127.0.0.1 --port 8000
```

## 8. 让其他电脑访问（可选）

以上命令只允许本机访问。如果同一 Wi-Fi 下的同学需要打开介绍页，把监听地址改为所有网卡：

```powershell
uv run uvicorn flowremote.api.app:app --host 0.0.0.0 --port 8000
```

查询本机 IPv4 地址：

```powershell
ipconfig
```

其他电脑打开：

```text
http://<你的局域网IP>:8000/static/landing.html
```

例如本机地址是 `192.168.5.19`，链接就是：

```text
http://192.168.5.19:8000/static/landing.html
```

需要保持电脑开机、网站运行，并且两台设备在同一个 Wi-Fi。若已启用 Windows
防火墙，需要允许 TCP 8000 入站；公共 Wi-Fi 不适合直接开放演示服务。

需要公网长期访问时，把整个应用部署到 Render、Railway、学校服务器或 VPS，
部署后介绍页地址就是：

```text
https://你的域名/static/landing.html
```

## 9. 常见问题

**端口 8000 被占用**

```powershell
netstat -ano | findstr :8000
taskkill /PID <占用进程的PID> /F
```

或者换一个端口启动，例如 `--port 8001`，然后访问
`http://127.0.0.1:8001/static/landing.html`。

**介绍页 404**

确认启动命令是在 `Knight-hell` 项目根目录执行的，并确认文件存在：

```powershell
Test-Path src\flowremote\ui\static\landing.html
```

**介绍页没有样式**

按 `Ctrl+F5` 强制刷新，并确认以下文件存在：

```text
src\flowremote\ui\static\landing.css
src\flowremote\ui\static\img\flowremote-lockup.png
```

**登录提示账号密码不匹配**

本地库没有演示账号，或库不是初始状态。先停止服务，再执行：

```powershell
uv run python src\flowremote\devtools\seed.py --reset --verify
```

然后重新启动并登录。

**`ModuleNotFoundError: flowremote`**

启动命令要在 `Knight-hell` 根目录执行，并且先运行过 `uv sync`。

## 10. 运行测试

```powershell
uv run python -m pytest tests -q
```

介绍页是静态文件，不参与业务逻辑；原产品的测试不受影响。
