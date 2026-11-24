"""
日志解析模块
------------
把一行 combined 格式的 Web 访问日志解析成结构化字典。

支持的格式（Nginx / Apache 通用）：
    127.0.0.1 - frank [10/Oct/2023:13:55:36 +0800]
        "GET /apache_pb.gif HTTP/1.0" 200 2326
        "http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"

设计要点：
1. 正则模块级只编译一次，避免在循环里重复编译（1 万行时的性能关键）。
2. 坏行返回 None 而不是抛异常，保证一批日志里几行畸形数据不会中断整个导入。
3. 时间、字节数等字段做"防御式转换"：转换失败不丢整行，只置空。
"""

import re
from datetime import datetime, timezone, timedelta

# combined 日志的正则：用"成对的边界符"（方括号、双引号）定位字段，而不是数空格
LOG_PATTERN = re.compile(
    r'^(?P<ip>\S+)'                 # 1. 客户端 IP
    r' \S+'                         # 2. identd 标识（恒为 -）
    r' (?P<user>\S+)'               # 3. Basic 认证用户名（通常是 -）
    r' \[(?P<time>[^\]]+)\]'        # 4. [时间 + 时区]
    r' "(?P<request>[^"]*)"'        # 5. "方法 路径 协议"
    r' (?P<status>\d{3}|-)'         # 6. 状态码
    r' (?P<bytes>\d+|-)'            # 7. 响应字节数（可能为 -）
    r'(?: "(?P<referer>[^"]*)")?'   # 8. 可选：Referer
    r'(?: "(?P<ua>[^"]*)")?'        # 9. 可选：User-Agent
    r'(?P<extra>.*)'                # 10. 可选：X-Forwarded-For、request_time 等扩展字段
)

# 月份缩写 → 月份数字（combined 日志里月份是英文三字母缩写）
MONTHS = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12,
}

TIME_FORMAT = '%d/%b/%Y:%H:%M:%S'


def parse_time(raw: str):
    """把 '10/Oct/2023:13:55:36 +0800' 转成带时区的 datetime；失败返回 None。"""
    try:
        # 拆成 "10/Oct/2023:13:55:36" 和 "+0800" 两部分
        body, tz = raw.rsplit(' ', 1)
        dt = datetime.strptime(body, TIME_FORMAT)
        sign = 1 if tz[0] == '+' else -1
        offset = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
        return dt.replace(tzinfo=timezone(sign * offset))
    except (ValueError, IndexError):
        return None


def parse_line(line: str):
    """解析单行日志 → dict；解析失败返回 None。"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    m = LOG_PATTERN.match(line)
    if not m:
        return None

    d = m.groupdict()

    # 请求行拆成三部分：方法 / 路径 / 协议。畸形请求可能整体是 "-"
    request = d['request'] or '-'
    parts = request.split(' ')
    if len(parts) >= 3:
        method, path, protocol = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        method, path, protocol = parts[0], parts[1], '-'
    else:
        method, path, protocol = '-', request, '-'

    # 路径同时保留"带查询串"和"纯路径"两份，检测用前者，排行榜用后者
    path_only = path.split('?', 1)[0]

    status = int(d['status']) if d['status'].isdigit() else 0
    byte_count = int(d['bytes']) if d['bytes'].isdigit() else None

    ts = parse_time(d['time'])

    return {
        'ip': d['ip'],
        'user': d['user'],
        'time': ts.isoformat() if ts else None,
        'time_raw': d['time'],
        'timestamp': ts.timestamp() if ts else None,
        'method': method.upper(),
        'path': path,
        'path_only': path_only,
        'protocol': protocol,
        'status': status,
        'bytes': byte_count,
        'referer': d['referer'] or '-',
        'ua': d['ua'] or '',
        'extra': (d['extra'] or '').strip(),
    }


def parse_file(path, encoding='utf-8', max_lines=None):
    """
    读取整份日志文件 → (记录列表, 统计信息)。

    返回的 stats 里包含总行数、成功行数、失败行数以及前 5 条失败示例，
    方便前端提示"这批日志有多少脏数据"。
    """
    records = []
    total = failed = 0
    samples = []

    # errors='replace'：遇到非 UTF-8 的脏字节不至于让整次导入失败
    with open(path, 'r', encoding=encoding, errors='replace') as f:
        for lineno, line in enumerate(f, 1):
            if max_lines and lineno > max_lines:
                break
            if not line.strip():
                continue
            total += 1
            rec = parse_line(line)
            if rec is None:
                failed += 1
                if len(samples) < 5:
                    samples.append({'line': lineno, 'text': line.strip()[:120]})
            else:
                records.append(rec)

    return records, {
        'total_lines': total,
        'parsed': len(records),
        'failed': failed,
        'failed_samples': samples,
    }
