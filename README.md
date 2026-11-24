# WebLog Sentinel · 网站访问日志可视化分析工具

大二项目实训作品。导入 Nginx/Apache 的 combined 格式访问日志，自动完成**解析 → 统计 → 异常检测 → 可视化**，并支持异常明细导出 CSV。

- 后端：Python 3 + Flask（解析、统计、规则引擎、异常检测、CSV 导出）
- 前端：HTML + JavaScript + ECharts 5（原生实现，无第三方框架依赖）
- 规则：外置在 `rules.json`，改规则不用改代码

---

## 一、快速开始

```bash
# 1. 安装依赖（只需 Flask）
pip install -r requirements.txt

# 2. 启动（默认 5000；若被占用会自动顺延到 5001、5002…）
python app.py

# 3. 浏览器打开终端里打印的地址，例如
#    http://127.0.0.1:5000
```

打开页面后有两种使用方式：

1. 点 **「▶ 直接用演示日志体验」**，立刻看到 13,000+ 行、含 7 类攻击的完整分析结果；
2. 把 `sample_data/demo_access.log` 拖进上传区（或点「导入日志」选择文件），走真实的上传 → 解析流程。

> 演示彩蛋：访问 `http://127.0.0.1:5000/?demo=1` 会自动加载演示日志，现场演示时少点一次鼠标。

---

## 二、功能对照（任务书 5.1）

| 模块 | 实现 | 说明 |
| --- | --- | --- |
| 日志导入 | `POST /api/analyze` | 支持 .log/.txt，单文件 ≤100MB，13,000 行约 0.3 秒完成 |
| 日志解析 | `analyzer/parser.py` | combined 正则解析，提取 IP/时间/方法/URL/协议/状态码/字节数/Referer/UA，坏行跳过并计数 |
| 统计分析 | `analyzer/analytics.py` | ①访问量趋势 ②Top10 IP ③Top10 URL ④状态码分布 ⑤请求方法分布（+ Top UA） |
| 异常检测 | `analyzer/detector.py` | ①单 IP 高频 Top N ②4xx/5xx 错误率异常 ③可疑 User-Agent ④攻击特征请求（12 条规则）⑤登录爆破 ⑥404 目录扫描 |
| 可视化 | `static/` | 7 个 ECharts 图表 + 告警明细/聚合双视图表格 + 等级/类别/关键字筛选 |
| 结果导出 | `/api/export/anomalies.csv`、`/api/export/stats.csv` | UTF-8-SIG 编码，Excel 打开中文不乱码；支持按风险等级导出 |

---

## 三、目录结构

```
日志分析工具/
├─ app.py                  Flask 入口：路由、上传、缓存、CSV 导出
├─ rules.json              检测规则 + 阈值（可配置，改完刷新即生效）
├─ requirements.txt
├─ analyzer/
│  ├─ parser.py            日志解析（combined 正则、时间/字节容错）
│  ├─ analytics.py         五类统计 + 趋势粒度自动选择
│  └─ detector.py          规则引擎 + 统计类异常检测 + 告警聚合
├─ static/
│  ├─ index.html           页面结构
│  ├─ css/style.css        深色运营大屏风格
│  ├─ js/app.js            上传、图表、表格、筛选、导出
│  └─ vendor/echarts.min.js 本地化的 ECharts，断网也能演示
├─ sample_data/
│  └─ demo_access.log      13,000+ 行演示日志（含 SQL 注入/扫描/爆破等）
├─ tools/
│  └─ gen_demo_log.py      演示日志生成脚本（可复现）
├─ tests/
│  └─ test_core.py         28 个单元/接口测试
├─ exports/                导出的 CSV 自动落盘一份
└─ 项目报告.docx           架构设计、规则说明、测试结果、个人总结
```

---

## 四、接口一览

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/analyze` | 上传日志（form-data 字段名 `file`），返回完整分析结果 |
| POST | `/api/demo` | 直接分析 `sample_data/demo_access.log` |
| GET | `/api/rules` | 返回当前规则清单与阈值 |
| GET | `/api/export/anomalies.csv?level=high` | 导出异常明细，`level` 可选 |
| GET | `/api/export/stats.csv` | 导出基础统计（总览 + 排名 + 分布） |

返回 JSON 结构：

```
data.meta        文件信息、解析耗时、失败行数
data.overview    总量/独立 IP/错误率/时间范围
data.trend       趋势（labels/total/errors/granularity）
data.top_ips      Top 10 IP
data.top_urls     Top 10 URL
data.status       状态码分布（具体码 + 2xx/3xx/4xx/5xx 归类）
data.methods      请求方法分布
data.ua_top       Top UA
data.anomalies    alerts（明细）/ groups（聚合）/ summary / high_freq_ips /
                  error_rate_ips / scanner_ips / bruteforce / suspect_uas / rules / thresholds
```

---

## 五、检测规则（rules.json）

### 5.1 特征规则（12 条）

| ID | 类型 | 名称 | 等级 |
| --- | --- | --- | --- |
| SQLI-001 | path_pattern | SQL 注入 - 联合查询（含 `/**/` 注释绕过） | 高 |
| SQLI-002 | path_pattern | SQL 注入 - 恒真条件 | 高 |
| SQLI-003 | path_pattern | SQL 注入 - 时间盲注（sleep/benchmark） | 高 |
| SQLI-004 | path_pattern | SQL 注入 - 数据窃取（information_schema/load_file） | 高 |
| SQLI-005 | path_pattern | SQL 注入 - 语句闭合 | 高 |
| TRAV-001 | path_pattern | 路径遍历 - 目录穿越（含 URL 编码、`....//` 变体） | 高 |
| TRAV-002 | path_pattern | 路径遍历 - 敏感文件（etc/passwd、win.ini） | 高 |
| XSS-001 | path_pattern | 跨站脚本 - `<script>`、`%3Cscript`、onerror | 高 |
| CMD-001 | path_pattern | 命令注入 - `;cat`、`\|whoami` 等 | 高 |
| SENS-001 | path_keyword | 敏感路径探测（.git/.env/phpmyadmin/backup.zip…） | 中 |
| UA-001 | ua_keyword | 攻击工具 UA（sqlmap/hydra/dirsearch/nikto/nmap…） | 高 |
| UA-002 | ua_keyword | 脚本类 UA（python-requests/curl/wget…） | 低 |

所有路径类规则匹配前统一做 **URL 解码 + 小写**，用来对抗 `%27`、`%2e%2e`、`UnIoN SeLeCt` 这类变形。

### 5.2 统计阈值（thresholds）

```json
{
  "high_freq_per_minute": 300,   // 单 IP 每分钟请求数 ≥300 → 高频告警
  "error_rate": 0.6,             // 单 IP 4xx/5xx 占比 ≥60% → 错误率异常
  "error_min_requests": 50,      // 至少 50 次请求才参与判定，防小样本误报
  "bruteforce_fails": 30,        // 登录接口失败 ≥30 次 → 爆破
  "scan_404_rate": 0.8           // 404 占比 ≥80% → 疑似目录扫描
}
```

改规则的两种典型操作：

1. 新增一条 SQL 注入变体：在 `rules.json` 的 `rules` 里加一条，刷新页面即可生效（每次分析都会重新加载规则）；
2. 调整灵敏度：改 `thresholds` 的数字，例如把 `high_freq_per_minute` 调成 200。

### 5.3 风险分级

- **高危（红）**：注入/遍历/命令执行特征、攻击工具 UA、爆破且出现成功响应、错误率 ≥90%
- **中危（橙）**：敏感路径探测、空 User-Agent、错误率 60%~90%、扫描未达高频
- **低危（黄）**：curl / python-requests 等脚本类 UA（正常运行也会出现，仅作提示）

---

## 六、演示日志说明（sample_data/demo_access.log）

由 `tools/gen_demo_log.py` 生成，13,000+ 行、覆盖 2026-09-07 全天，含：

| 场景 | IP | 特征 |
| --- | --- | --- |
| dirsearch 目录扫描 | 66.102.9.15 | 40 秒 400 次请求，全部 404，路径全是 .git/.env/phpmyadmin |
| Hydra 登录爆破 | 45.148.10.88 | 60 次 401 后出现 1 次 200（可能已攻破） |
| sqlmap SQL 注入 | 198.51.100.7 | union select / sleep() / information_schema 等 15 条 |
| 路径遍历 | 3 个 IP | `../../etc/passwd`、`%2e%2e%2f`、`....//` |
| XSS + 命令注入 | 91.219.236.44 / 41.203.72.18 | `<script>`、`%3Cscript`、`;cat /etc/passwd` |
| nikto 漏洞扫描 | 203.0.113.66 | 探测 /admin、/server-status、/.htaccess |
| 浏览器手工探路 | 61.160.35.2 | 正常 UA 探 .git/.env，命中中危 |

重新生成：

```bash
python tools/gen_demo_log.py
```

---

## 七、测试

```bash
python -m unittest discover -s tests -v
```

28 个用例，覆盖解析容错、时区、统计口径、规则命中（含编码绕过）、错误率/爆破/高频检测、上传接口、CSV 编码。

---

## 八、10 分钟现场演示流程

1. （30 秒）打开页面，讲一句定位：「把日志变成能看懂的现场图」；
2. （1 分钟）点「演示日志」，展示总览 KPI：13,570 次请求 / 113 个 IP / 8.1% 错误率 / 558 条告警；
3. （2 分钟）讲趋势图：凌晨 3:31 那个尖峰就是 dirsearch 扫描，白天是正常业务曲线；
4. （2 分钟）讲 Top IP 排名第一的 66.102.9.15：400 次请求、404 占比 100%，红色高亮；
5. （2 分钟）异常明细：按「高危」筛选，展示 SQL 注入、路径遍历、爆破成功的证据链，切「聚合」看 19 组告警；
6. （1 分钟）导出 CSV，用 Excel 打开证明中文不乱码；
7. （30 秒）回答老师追问：打开 `rules.json` 现场加一条规则，刷新页面即生效——证明「规则可配置」不是空话。

---

## 九、已知局限

- 单机演示级实现，分析结果放在内存里（`CACHE`），不支持多用户并发与历史任务保存；
- 只解析 combined 格式（及带 X-Forwarded-For 的扩展），自定义日志格式需改 `parser.py` 的正则；
- 规则基于正则与统计阈值，一定存在误报/漏报：例如技术博客文章标题含 "union select" 会被判高危；
- 反向代理场景若日志只记录上一跳代理 IP，需要先确认日志里是否带 X-Forwarded-For 字段。
