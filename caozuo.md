# FlowRemote 完整宣传版实施操作手册

本文档用于把当前 FlowRemote 从“可交互的 AI-RPA 原型”逐步升级为“可以完整展示正常流程、失败恢复、真实文件输出和审计对账的宣传应用”。

目标是实现一条完整、可重复的演示链路：

```text
登录
→ 上传 Excel
→ 后台校验
→ AI 辅助处理异常
→ 人工 Accept/Edit/Skip
→ 审批
→ 后台 Worker 执行
→ 写入真实 Excel
→ 写入本地 HTTP Target
→ 保存逐条回执
→ 中途失败
→ 只重试失败记录
→ 对账
→ 完成并展示审计
```

不要一开始连接所有企业 OA/BI。第一阶段使用真实本地 Excel 和真实本地 HTTP Target 证明完整架构。

---

# 一、开始前的准备

## 1. 确认当前项目

在 PowerShell 中执行：

```powershell
cd E:\knight_hell
git status --short --branch
git log -3 --oneline
```

确认当前已有：

- 用户注册、登录和持久化。
- Excel 上传和订单校验。
- AI 建议和 AI 设置。
- 人工复核和审批。
- 模拟执行进度。
- 活动日志。
- 本地缓存和离线 Outbox。
- PWA 和同步 API。

## 2. 安装和运行当前版本

```powershell
uv sync
.\.venv\Scripts\python.exe src\flowremote\devtools\seed.py --reset --verify
.\.venv\Scripts\python.exe -m uvicorn flowremote.api.app:app --reload --host 127.0.0.1 --port 8000
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

当前测试基线应为：

```text
230 passed, 11 subtests passed
```

## 3. 固定第一阶段演示范围

第一阶段只支持一个样例工作流：

```text
订单 Excel 校验与同步
```

两个真实演示目标：

```text
Local Excel Connector
Local HTTP Target Connector
```

暂不实现真实 OA/BI。后续企业 Connector 必须遵循同一接口。

---

# 二、第一步：建立后台 Worker 和数据库任务队列

## 步骤 1：创建迁移文件

新增：

```text
src/flowremote/control_plane/migrations/0008_worker_connectors.sql
```

第一版至少增加以下表：

```text
workflow_jobs
workers
execution_items
connector_targets
connector_receipts
reconciliation_runs
```

## 步骤 2：设计 workflow_jobs

建议字段：

```text
id                  TEXT PRIMARY KEY
task_id             TEXT NOT NULL
run_id              TEXT
job_type            TEXT NOT NULL
status              TEXT NOT NULL
attempts            INTEGER NOT NULL
available_at        TEXT NOT NULL
lease_owner         TEXT
lease_expires_at    TEXT
payload_json        TEXT NOT NULL
created_at          TEXT NOT NULL
updated_at          TEXT NOT NULL
```

支持的 job_type：

```text
VALIDATE_TASK
EXECUTE_APPROVED
RETRY_FAILED
RECONCILE_RUN
```

Job 状态：

```text
queued
claimed
running
completed
failed
dead_letter
```

## 步骤 3：设计 workers

建议字段：

```text
id
name
status
last_heartbeat_at
started_at
```

状态：

```text
online
busy
offline
```

## 步骤 4：新增 Worker 模块

创建目录：

```text
src/flowremote/worker/
```

建议文件：

```text
__init__.py
main.py
queue.py
runner.py
heartbeat.py
recovery.py
```

职责：

- `main.py`：启动 Worker 主循环。
- `queue.py`：领取、续租和完成 Job。
- `runner.py`：按 job_type 调用处理函数。
- `heartbeat.py`：更新 Worker 在线状态。
- `recovery.py`：回收过期租约和处理恢复逻辑。

## 步骤 5：实现原子领取 Job

必须使用数据库事务和租约，不能简单地先查询再更新。

推荐做法：

```text
SELECT 可领取的 Job
→ UPDATE status = claimed
→ 写入 worker_id 和 lease_expires_at
→ COMMIT
```

或者使用支持条件更新的单条 SQL。

保证：

- 两个 Worker 不会领取同一个 Job。
- Worker 崩溃后租约会过期。
- 另一个 Worker 可以重新领取。

## 步骤 6：实现 Worker 启动命令

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m flowremote.worker
```

开发演示时可以同时运行：

```text
Terminal 1：FastAPI Web
Terminal 2：FlowRemote Worker
Terminal 3：Local HTTP Target
```

## 步骤 7：把审批后的执行改为入队

修改审批流程：

```text
Approve & Execute
→ 写 approval
→ 创建 execution run
→ 创建 EXECUTE_APPROVED Job
→ 返回“Execution queued”
```

浏览器不再通过 `/execution/step` 推进生产执行。

旧的 step 接口可以只保留在演示调试模式。

## 第一步验收

- 关闭浏览器后 Worker 仍能执行任务。
- Job 只能被一个 Worker 领取。
- Worker 重启后任务可以继续。
- Worker 心跳能在页面显示。
- 原有测试全部通过。

---

# 三、第二步：建立记录级执行状态

## 步骤 1：创建 execution_items

建议字段：

```text
id
task_id
run_id
record_id
target_id
status
attempts
idempotency_key
external_record_id
last_error
created_at
written_at
reconciled_at
```

状态：

```text
pending
writing
written
failed_retryable
failed_permanent
reconciling
verified
cancelled
```

## 步骤 2：审批后生成记录快照

审批成功后，不要只记录 approved_count。

需要为每条审批记录创建 execution_item：

```text
task_id
run_id
record_id
target_id
idempotency_key
```

初始状态：

```text
pending
```

## 步骤 3：生成幂等键

推荐格式：

```text
{task_id}:{attempt}:{target_id}:{record_id}
```

幂等键必须：

- 在重试时保持不变。
- 对同一目标、同一记录唯一。
- 写入回执和审计日志。

## 步骤 4：创建 connector_receipts

建议字段：

```text
id
run_id
record_id
target_id
idempotency_key
external_record_id
response_json
written_at
```

每次外部写入成功都必须保存回执。

## 步骤 5：创建时间线 API

新增：

```text
GET /api/runs/{run_id}
GET /api/runs/{run_id}/receipts
```

返回：

- 当前运行状态。
- 每个 Target 的进度。
- pending/written/failed/verified 数量。
- 失败记录。
- 外部回执。
- 当前 Worker。

## 第二步验收

- 每条审批记录都有独立状态。
- 页面可以查看哪个 Target 成功或失败。
- 失败可以精确定位到 record_id。
- 已完成记录和回执可以长期查询。
- 不再只依赖 execution_runs 的总计数。

---

# 四、第三步：实现真实 Local Excel Connector

## 步骤 1：创建 Connector 基础接口

新增：

```text
src/flowremote/connectors/base.py
```

接口建议：

```python
class TargetConnector(Protocol):
    def probe(self): ...
    def prepare(self, config): ...
    def preview(self, records): ...
    def write(self, records, idempotency_key): ...
    def read_back(self, keys): ...
    def reconcile(self, records, receipts): ...
```

## 步骤 2：实现 LocalExcelConnector

新增：

```text
src/flowremote/connectors/local_excel.py
```

输出位置：

```text
data/runtime/targets/{task_id}/{attempt}/orders-result.xlsx
data/runtime/targets/{task_id}/{attempt}/receipts.jsonl
```

写入内容：

- 订单字段。
- 修正后的值。
- record ID。
- 幂等键。
- 写入状态。

每写入一行，生成一条回执。

## 步骤 3：增加结果下载接口

新增：

```text
GET /tasks/{task_id}/runs/{run_id}/result.xlsx
```

访问前检查：

- 当前用户是否可见该任务。
- 文件是否属于对应 run。
- 文件是否真实存在。

## 步骤 4：展示生成结果

执行结果页增加：

- 下载结果 Excel。
- 下载回执 JSONL。
- 显示输出文件 checksum。
- 显示输出行数。

## 第三步验收

- 上传输入 Excel。
- 完成审批后生成真实结果 Excel。
- 文件中包含正确订单值。
- 每个输出行有回执。
- 未授权用户无法下载结果。

---

# 五、第四步：实现真实 Local HTTP Target Connector

## 步骤 1：创建演示目标服务

新增：

```text
demo/target_server.py
```

至少提供：

```text
GET  /health
POST /reset
POST /fail-next
POST /orders
GET  /orders/{idempotency_key}
GET  /orders
```

数据可以保存在内存或演示专用 SQLite 文件中。

## 步骤 2：实现幂等写入

主应用请求：

```text
POST /orders
Idempotency-Key: TASK-1001:1:http:ORD-052
```

目标服务行为：

- 第一次收到幂等键：保存记录并返回回执。
- 再次收到同一幂等键：返回已有回执，不新增记录。

## 步骤 3：实现失败注入

调用：

```text
POST /fail-next
```

下一次写入返回 HTTP 500。

用于演示：

```text
成功 2 条
→ 第 3 条失败
→ 继续保存失败状态
→ 用户点击 Retry failed only
→ 仅第 3 条重新执行
→ 最终成功
```

## 步骤 4：实现 LocalHttpConnector

新增：

```text
src/flowremote/connectors/local_http.py
```

功能：

- health probe。
- 超时。
- 最多重试次数。
- 幂等键请求头。
- 单条或小批量写入。
- 保存外部记录 ID。
- 网络异常分类。

## 步骤 5：启动演示目标

```powershell
.\.venv\Scripts\python.exe demo\target_server.py --port 8770
```

配置 Local HTTP Target：

```text
http://127.0.0.1:8770
```

## 第四步验收

- 浏览器关闭后，Worker 继续通过 HTTP 写入。
- 目标服务能够查询已写入记录。
- 重复幂等键不会生成重复记录。
- fail-next 可以稳定制造失败。
- 页面可以显示 HTTP 目标和健康状态。

---

# 六、第五步：实现 Retry、Resume、Pause、Cancel 和对账

## 步骤 1：扩展状态机

建议 Task/Run 状态：

```text
execution_queued
executing
partial
retry_queued
paused
cancel_requested
cancelled
reconciling
complete
failed
```

增加 `desired_state`：

```text
run
pause
cancel
retry_failed
reconcile
```

Worker 每处理一批后检查 desired_state。

## 步骤 2：实现 Retry failed only

只选择：

```text
failed_retryable
pending
```

永远跳过：

```text
written
verified
cancelled
```

接口：

```text
POST /api/runs/{run_id}/retry-failed
```

## 步骤 3：实现错误分类

可重试：

- 连接超时。
- HTTP 429。
- HTTP 500/502/503。
- 临时网络错误。
- Worker 租约丢失。

不可重试：

- 权限不足。
- 无效凭据。
- 字段被永久拒绝。
- 业务规则冲突。

不可重试错误进入：

```text
failed_permanent
```

## 步骤 4：实现退避

建议：

```text
第 1 次重试：立即
第 2 次：5 秒
第 3 次：30 秒
第 4 次：2 分钟
```

超过最大次数后进入人工处理或 dead letter。

## 步骤 5：实现 Pause 和 Cancel

接口：

```text
POST /api/runs/{run_id}/pause
POST /api/runs/{run_id}/resume
POST /api/runs/{run_id}/cancel
```

Pause：

- 设置 desired_state。
- Worker 在安全 checkpoint 后停止。

Cancel：

- 停止未来写入。
- 保留已写入记录和回执。
- 进入 cancelled 或 reconciling。

不要声称 Cancel 能自动回滚外部系统。

## 步骤 6：实现对账

接口：

```text
POST /api/runs/{run_id}/reconcile
```

流程：

```text
读取 execution_items
→ 对每条 written/unknown 记录调用 Connector.read_back
→ 找到远端记录：verified
→ 未找到：failed_retryable
→ 保存 reconciliation_runs
→ 更新 run 状态
```

对账必须能处理：

- 外部写入成功但客户端超时。
- 外部写入成功但回执丢失。
- Worker 在写完后、提交数据库前崩溃。

## 第五步验收

- 第 3 条失败后只重试第 3 条。
- 已成功记录不会重复发送。
- Worker 中断后可以恢复。
- Pause 能在 checkpoint 停止。
- Cancel 不再产生新写入。
- 对账可以识别外部已存在记录。

---

# 七、第六步：前端完整展示

## 步骤 1：Dashboard

展示：

- Worker 在线状态。
- 当前运行任务。
- 待复核数量。
- 待审批数量。
- 最近失败。
- Connector 健康状态。
- 成功率和耗时。

## 步骤 2：Run 时间线

新增或扩展运行页面：

```text
Uploaded
Queued
Validated
Review Required
AI Suggested
Human Reviewed
Approved
Execution Queued
Excel Writing
HTTP Writing
Partial
Retry Queued
Executing
Reconciling
Complete
```

每个节点显示：

- 时间。
- 执行者。
- 成功/失败数量。
- 错误原因。
- 外部回执链接。

## 步骤 3：Execution 控制

增加按钮：

- Retry failed only
- Resume
- Pause
- Cancel
- Reconcile
- Download failure report

## 步骤 4：Integrations 页面

新增：

```text
/settings/integrations
```

展示：

- Local Excel。
- Local HTTP Target。
- Enabled/Disabled。
- Health。
- Last checked。
- Target version。
- Probe 按钮。

## 步骤 5：Audit Center

新增：

```text
/tasks/{task_id}/audit
```

展示：

- 用户操作。
- AI 请求。
- Worker 领取和完成 Job。
- Connector 写入。
- 外部回执。
- 重试。
- 对账。

提供：

- JSON 导出。
- CSV 导出。

## 步骤 6：Demo Mode

仅当环境变量启用时显示：

```text
FLOWREMOTE_DEMO_MODE=1
```

功能：

- Reset demo。
- Fail next HTTP record。
- Run demo。
- Download evidence。

生产环境必须隐藏。

---

# 八、第七步：增加测试

## 1. Job Queue 测试

- 两个 Worker 不会领取同一个 Job。
- 租约过期后可重新领取。
- Worker 完成后 Job 状态正确。
- Worker 崩溃后 Job 恢复。

## 2. Excel Connector 测试

- 生成真实文件。
- 文件行数正确。
- 修正值正确。
- checksum 和回执正确。

## 3. HTTP Connector 测试

- 正常写入。
- 幂等重复写入。
- 429/500/超时。
- fail-next。
- read-back。

## 4. Retry 测试

- 只重试 failed/pending。
- 不重复写 written。
- 主目标成功、次目标失败。
- 重试后完成。

## 5. Pause/Cancel 测试

- Pause 停在 checkpoint。
- Resume 继续。
- Cancel 后无新写入。
- Cancel 保留已存在回执。

## 6. 对账测试

- 外部成功、数据库未知。
- 外部不存在。
- 重复回执。
- verified/missing 数量正确。

## 7. 浏览器 E2E

建议引入 Playwright：

- 登录和上传。
- AI 建议和人工复核。
- 审批。
- Worker 后台执行。
- 关闭浏览器后重新查看。
- 离线复核和恢复。
- fail-next 和 Retry。
- 下载 Excel 和审计。

---

# 九、第八步：形成宣传演示

## 1. 固定演示数据

建议：

```text
Task：Order Exception Automation
输入：10 条订单
通过：6 条
异常：4 条
AI 建议：3 条
人工修改：1 条
跳过：0 条
```

## 2. 演示台词

```text
这是 AI-RPA 控制台。
用户上传订单 Excel。
后台 Worker 自动校验数据。
AI 根据客户目录和订单上下文给出有证据的修正建议。
所有建议都必须由人审批。
审批后任务进入后台执行，不依赖浏览器。
系统生成真实 Excel，并写入 HTTP Target。
中途模拟一次失败，系统只重试失败记录。
最后展示逐条回执、对账结果和审计日志。
```

## 3. 宣传截图

至少保存：

- Dashboard。
- AI settings。
- Review + AI evidence。
- Approval。
- Worker execution progress。
- Failure and Retry。
- Result Excel。
- HTTP receipts。
- Audit timeline。

## 4. 演示限制说明

可以宣称：

- Human-in-the-loop AI.
- Background Worker.
- Real local Excel output.
- Real local HTTP integration.
- Retry and reconciliation.
- Audit.

不能宣称：

- 已连接全部企业 OA/BI。
- 生产级高可用。
- 绝对 exactly-once。
- AI 可以无人审批自动执行。

---

# 十、推荐实施顺序

严格按以下顺序推进：

1. `0008` 迁移和 workflow_jobs。
2. Worker 主循环、租约和心跳。
3. execution_items 和逐条回执。
4. Local Excel Connector。
5. Local HTTP Target 和 Connector。
6. Retry failed only。
7. Reconcile。
8. Pause/Cancel。
9. Run 时间线和 Integrations 页面。
10. Demo Mode。
11. Playwright E2E。
12. 宣传截图和演示视频。

不要先做复杂工作流编辑器，也不要先接企业 OA/BI。

---

# 十一、每一阶段完成后的必跑命令

运行全部测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

运行 Python 编译检查：

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests demo
```

检查 JavaScript：

```powershell
node --check src\flowremote\ui\static\app.js
node --check src\flowremote\ui\static\sync-client.js
```

重建演示数据：

```powershell
.\.venv\Scripts\python.exe src\flowremote\devtools\seed.py --reset --verify
```

运行 Feature 3 演示：

```powershell
.\.venv\Scripts\python.exe demo\run_feature3_demo.py --check
```

检查 Git 空白和状态：

```powershell
git diff --check
git status --short --branch
```

---

# 十二、最终验收标准

完成品 v1 必须满足：

1. 注册用户可以再次登录并恢复任务。
2. Excel 上传后的校验由后台流程完成。
3. AI 建议可查看依据和置信度。
4. 人工 Accept/Edit/Skip 生效。
5. 审批后无需打开浏览器，Worker 继续执行。
6. 生成真实 Excel 输出文件。
7. 真实调用本地 HTTP Target。
8. 保存逐条回执和幂等键。
9. 可以稳定演示一次写入失败。
10. Retry failed only 不重复写成功记录。
11. Worker 中途重启可以恢复。
12. 可以完成对账并显示 verified 数量。
13. Dashboard、Run Timeline、Integrations 和 Audit 页面可访问。
14. 离线复核和重新联网同步仍然可用。
15. 完整测试、编译和浏览器静态检查通过。
16. 宣传中明确区分真实本地 Target 与尚未连接的企业 OA/BI。

满足以上条件后，FlowRemote 就可以作为完整的宣传应用展示真实的 AI 建议、人工审批、后台执行、失败恢复、真实文件输出和审计对账流程。
