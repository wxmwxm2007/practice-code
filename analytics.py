"""
统计分析模块
------------
对解析后的记录做五类基础统计：
1. 访问量时间趋势（自动选择合适的粒度：分钟 / 小时 / 天）
2. Top 10 访问 IP
3. Top 10 访问 URL
4. 状态码分布（以及 2xx/3xx/4xx/5xx 归类）
5. 请求方法分布

所有函数只接受记录列表、返回纯 Python 结构，方便单元测试和复用。
"""

from collections import Counter, defaultdict
from datetime import datetime


def _fmt_bucket(ts, granularity):
    """把时间戳格式化成趋势图横轴标签。"""
    dt = datetime.fromtimestamp(ts)
    if granularity == 'minute':
        return dt.strftime('%H:%M')
    if granularity == 'hour':
        return dt.strftime('%m-%d %H:00')
    return dt.strftime('%Y-%m-%d')


def overview(records):
    """总览指标：总量、独立 IP、独立 URL、错误率、时间跨度。"""
    total = len(records)
    ips = {r['ip'] for r in records}
    urls = {r['path_only'] for r in records}
    errors = sum(1 for r in records if r['status'] >= 400 or r['status'] == 0)
    timestamps = [r['timestamp'] for r in records if r['timestamp']]
    span = (max(timestamps) - min(timestamps)) if timestamps else 0

    return {
        'total_requests': total,
        'unique_ips': len(ips),
        'unique_urls': len(urls),
        'error_requests': errors,
        'error_rate': round(errors / total, 4) if total else 0,
        'start_time': datetime.fromtimestamp(min(timestamps)).isoformat(timespec='seconds') if timestamps else None,
        'end_time': datetime.fromtimestamp(max(timestamps)).isoformat(timespec='seconds') if timestamps else None,
        'span_seconds': int(span),
        'total_bytes': sum(r['bytes'] or 0 for r in records),
    }


def _pick_granularity(records, max_points=120):
    """按时间跨度自动选粒度，保证横轴点不会多到看不清。"""
    timestamps = [r['timestamp'] for r in records if r['timestamp']]
    if not timestamps:
        return 'hour'
    span = max(timestamps) - min(timestamps)
    if span <= 3 * 3600:
        return 'minute'
    if span <= 3 * 86400:
        return 'hour'
    return 'day'


def trend(records, granularity=None, max_points=120):
    """
    访问量趋势：返回 {granularity, labels, total, success, errors}。
    labels 是时间段，total 是该段总请求数，errors 是该段 4xx/5xx 请求数。
    """
    g = granularity or _pick_granularity(records, max_points)
    step = {'minute': 60, 'hour': 3600, 'day': 86400}[g]

    # 先按整数时间桶聚合成 {桶起点: [总数, 错误数]}
    buckets = defaultdict(lambda: [0, 0])
    for r in records:
        ts = r['timestamp']
        if not ts:
            continue
        key = int(ts // step * step)
        buckets[key][0] += 1
        if r['status'] >= 400 or r['status'] == 0:
            buckets[key][1] += 1

    if not buckets:
        return {'granularity': g, 'labels': [], 'total': [], 'success': [], 'errors': []}

    # 补齐中间没有请求的时间段，让折线的时间轴保持连续（否则会"压缩"掉空白时段）
    start, end = min(buckets), max(buckets)
    labels, total, errors = [], [], []
    for key in range(start, end + 1, step):
        v = buckets.get(key, [0, 0])
        labels.append(_fmt_bucket(key, g))
        total.append(v[0])
        errors.append(v[1])

    return {
        'granularity': g,
        'labels': labels,
        'total': total,
        'success': [t - e for t, e in zip(total, errors)],
        'errors': errors,
    }


def top_ips(records, n=10, ip_filter=None):
    """Top N 访问 IP（可传入要排除的 IP 集合用于"排除攻击源后的正常排行"）。"""
    counter = Counter(r['ip'] for r in records if not ip_filter or r['ip'] not in ip_filter)
    total = sum(counter.values()) or 1
    return [
        {'ip': ip, 'count': c, 'percent': round(c / total, 4)}
        for ip, c in counter.most_common(n)
    ]


def top_urls(records, n=10):
    """Top N 访问 URL（用去掉查询串的纯路径聚合，避免 ?id=1、?id=2 被拆成多条）。"""
    counter = Counter(r['path_only'] for r in records)
    total = sum(counter.values()) or 1
    return [
        {'url': u, 'count': c, 'percent': round(c / total, 4)}
        for u, c in counter.most_common(n)
    ]


def status_distribution(records):
    """状态码分布：具体状态码 + 大类（2xx/3xx/4xx/5xx）两层。"""
    codes = Counter(r['status'] for r in records)
    classes = Counter()
    for code, c in codes.items():
        if 200 <= code < 300:
            classes['2xx'] += c
        elif 300 <= code < 400:
            classes['3xx'] += c
        elif 400 <= code < 500:
            classes['4xx'] += c
        elif code >= 500:
            classes['5xx'] += c
        else:
            classes['unknown'] += c

    return {
        'codes': [{'code': k, 'count': v} for k, v in sorted(codes.items(), key=lambda x: -x[1])],
        'classes': [{'name': k, 'value': v} for k, v in classes.most_common()],
    }


def method_distribution(records):
    """请求方法分布（GET / POST / HEAD ...）。"""
    counter = Counter(r['method'] for r in records)
    return [{'method': k, 'count': v} for k, v in counter.most_common()]


def ua_distribution(records, n=8):
    """
    Top UA。注意：聚合键用**完整** UA，只在展示时截断；
    如果先截断再计数，Chrome 和 Edge 这种前 60 字符相同的 UA 会被错误合并。
    """
    counter = Counter((r['ua'] or '(空 UA)') for r in records)
    result = []
    for ua, c in counter.most_common(n):
        shown = ua if len(ua) <= 110 else ua[:109] + '…'
        result.append({'ua': shown, 'count': c})
    return result
