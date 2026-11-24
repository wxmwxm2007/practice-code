"""
异常检测模块
------------
两条腿走路：

1. 特征类检测（逐条匹配）：由外置的 rules.json 驱动，
   覆盖 SQL 注入、路径遍历、XSS、命令注入、敏感路径探测、攻击工具 UA 等。
   规则可增删改，不用改代码。

2. 统计类检测（按 IP 聚合）：
   - 单 IP 高频访问（每分钟请求数超阈值）
   - 4xx/5xx 错误率异常（大量 404 往往意味着目录扫描）
   - 暴力破解（同一 IP 对登录接口大量 401/403，且出现 200）
   阈值同样写在 rules.json 的 thresholds 里。

所有告警都保留完整字段（IP、时间、方法、URL、状态码、UA、证据），
这样导出的 CSV 能直接用来还原攻击时间线。
"""

import json
import re
import urllib.parse
from collections import Counter, defaultdict

LEVEL_ORDER = {'high': 3, 'medium': 2, 'low': 1}
LEVEL_LABEL = {'high': '高危', 'medium': '中危', 'low': '低危'}


class RuleEngine:
    """加载 JSON 规则 → 预编译正则 → 对单条记录执行匹配。"""

    def __init__(self, rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.raw_rules = cfg.get('rules', [])
        self.thresholds = cfg.get('thresholds', {})
        self.rules = []
        for r in self.raw_rules:
            item = dict(r)
            # 只有正则型规则需要预编译；关键词型（path_keyword/ua_keyword）直接子串匹配
            if r['type'].endswith('_pattern') and r.get('pattern'):
                item['compiled'] = re.compile(r['pattern'], re.I)
            self.rules.append(item)

    @staticmethod
    def _target_text(record, rule_type):
        """按规则类型取待检测文本：路径统一 URL 解码 + 小写，对抗 %27 等编码变形。"""
        if rule_type.startswith('path'):
            return urllib.parse.unquote(record.get('path', '') or '').lower()
        if rule_type == 'ua_keyword':
            return (record.get('ua', '') or '').lower()
        return ''

    def match(self, record):
        """返回命中的规则列表（可能同时命中多条）。"""
        hits = []
        for rule in self.rules:
            text = self._target_text(record, rule['type'])
            if rule['type'] in ('path_keyword', 'ua_keyword'):
                keywords = [k.strip().lower() for k in rule['pattern'].split(',') if k.strip()]
                if any(kw in text for kw in keywords):
                    hits.append(rule)
            elif rule.get('compiled') and rule['compiled'].search(text):
                hits.append(rule)
        return hits

    def describe(self):
        """给前端展示的规则清单。"""
        return [
            {'id': r['id'], 'name': r['name'], 'type': r['type'],
             'level': r['level'], 'pattern': r.get('pattern', '')}
            for r in self.raw_rules
        ]


def _max_in_window(minutes_counter):
    """每分钟请求数的峰值。"""
    return max(minutes_counter.values()) if minutes_counter else 0


def detect_anomalies(records, engine, top_n=10):
    """
    返回完整异常检测结果：
    alerts（明细）、summary（等级汇总）、high_freq_ips（高频排行）、
    error_rate_ips、bruteforce、suspect_uas、rules（规则清单）。
    """
    th = {
        'high_freq_per_minute': engine.thresholds.get('high_freq_per_minute', 300),
        'error_rate': engine.thresholds.get('error_rate', 0.6),
        'error_min_requests': engine.thresholds.get('error_min_requests', 50),
        'bruteforce_fails': engine.thresholds.get('bruteforce_fails', 30),
        'scan_404_rate': engine.thresholds.get('scan_404_rate', 0.8),
    }

    alerts = []
    counter = {'high': 0, 'medium': 0, 'low': 0}
    next_id = [0]

    def add_alert(level, category, ip, time, method, path, status, ua,
                  rule_ids, rule_names, evidence):
        next_id[0] += 1
        counter[level] += 1
        alerts.append({
            'id': f'A{next_id[0]:04d}',
            'level': level,
            'level_label': LEVEL_LABEL[level],
            'category': category,
            'ip': ip,
            'time': time,
            'method': method,
            'url': path,
            'status': status,
            'ua': ua,
            'rule_ids': rule_ids,
            'rule_names': rule_names,
            'evidence': evidence,
        })

    # ---------- 1. 特征规则逐条匹配 ----------
    per_ip = defaultdict(lambda: {
        'total': 0, 'errors': 0, 'minutes': Counter(), 'status': Counter(),
        'login_fail': 0, 'login_success': 0, 'ua': Counter(),
    })
    suspect_ua_counter = Counter()

    for rec in records:
        ip = rec['ip']
        stats = per_ip[ip]
        stats['total'] += 1
        stats['status'][rec['status']] += 1
        if rec['timestamp']:
            stats['minutes'][int(rec['timestamp'] // 60)] += 1
        if rec['status'] >= 400 or rec['status'] == 0:
            stats['errors'] += 1
        stats['ua'][rec['ua'][:60] or '(空)'] += 1

        is_login_path = any(kw in rec['path'].lower() for kw in ('login', 'signin', 'auth', 'logon'))
        if is_login_path and rec['method'] == 'POST':
            if rec['status'] in (401, 403):
                stats['login_fail'] += 1
            elif rec['status'] == 200:
                stats['login_success'] += 1

        hits = engine.match(rec)

        # 空 User-Agent 单独提示：浏览器一定带 UA，空 UA 常见于脚本或扫描器
        if not (rec['ua'] or '').strip():
            add_alert(
                'medium', '可疑 User-Agent', ip, rec['time_raw'], rec['method'],
                rec['path'], rec['status'], '(空)', ['STAT-004'], ['空 User-Agent'],
                '该请求没有携带 User-Agent，正常浏览器不会这样',
            )

        if not hits:
            continue

        for h in hits:
            if h['type'] == 'ua_keyword':
                suspect_ua_counter[(rec['ua'] or '(空)')[:120]] += 1

        # 同一请求命中多条规则时合并成一条告警，规则数越多越可疑
        level = max((h['level'] for h in hits), key=lambda x: LEVEL_ORDER.get(x, 0))
        names = [h['name'] for h in hits]
        evidence = '命中规则：' + '、'.join(f"{h['id']} {h['name']}" for h in hits)
        add_alert(
            level, '特征匹配', ip, rec['time_raw'], rec['method'], rec['path'],
            rec['status'], rec['ua'][:80],
            [h['id'] for h in hits], names, evidence,
        )

    # ---------- 2. 统计类检测 ----------
    high_freq_ips = []
    error_rate_ips = []
    bruteforce = []
    scanner_ips = []

    for ip, s in per_ip.items():
        peak = _max_in_window(s['minutes'])
        # 每分钟峰值排行（前 10）
        if peak > 0:
            high_freq_ips.append({
                'ip': ip, 'total': s['total'], 'peak_per_minute': peak,
                'error_rate': round(s['errors'] / s['total'], 4) if s['total'] else 0,
            })

        if peak >= th['high_freq_per_minute']:
            level = 'high' if peak >= th['high_freq_per_minute'] * 2 else 'medium'
            add_alert(
                level, '单 IP 高频访问', ip, '-', '-', '-', 0, '',
                ['STAT-001'], ['单 IP 高频访问（疑似扫描/爆破）'],
                f'该 IP 在 1 分钟窗口内峰值 {peak} 次请求，超过阈值 {th["high_freq_per_minute"]} 次',
            )

        # 错误率异常（总量够大才有统计意义，避免"3 个请求 3 个 404"误报）
        if s['total'] >= th['error_min_requests']:
            rate = s['errors'] / s['total']
            if rate >= th['error_rate']:
                level = 'high' if rate >= 0.9 else 'medium'
                error_rate_ips.append({
                    'ip': ip, 'total': s['total'], 'errors': s['errors'],
                    'error_rate': round(rate, 4), 'level': level,
                })
                add_alert(
                    level, '错误率异常', ip, '-', '-', '-', 0, '',
                    ['STAT-002'], ['4xx/5xx 错误率异常'],
                    f'该 IP 共 {s["total"]} 次请求，其中 {s["errors"]} 次为 4xx/5xx，错误率 {rate:.0%}',
                )

        # 404 为主的 IP，单独列为"疑似目录扫描"
        not_found = s['status'].get(404, 0)
        if s['total'] >= th['error_min_requests'] and not_found / s['total'] >= th['scan_404_rate']:
            scanner_ips.append({
                'ip': ip, 'total': s['total'], 'not_found': not_found,
                'rate': round(not_found / s['total'], 4),
            })

        # 暴力破解：对登录接口大量失败 + 出现过成功 → 高危
        if s['login_fail'] >= th['bruteforce_fails']:
            success = s['login_success'] > 0
            level = 'high' if success else 'medium'
            bruteforce.append({
                'ip': ip, 'fails': s['login_fail'], 'success': s['login_success'],
                'level': level,
            })
            add_alert(
                level, '暴力破解', ip, '-', 'POST', '登录相关接口', 200 if success else 401, '',
                ['STAT-003'], ['登录接口暴力破解'],
                f'该 IP 对登录接口发起 {s["login_fail"]} 次失败尝试'
                + ('，且之后出现 200 成功响应，账户可能已被攻破' if success else '，疑似字典爆破'),
            )

    # 排序：风险等级优先，其次时间
    alerts.sort(key=lambda a: (-LEVEL_ORDER.get(a['level'], 0), a['id']))

    # 按"IP + 类别 + 命中规则"聚合：一次目录扫描会产生几百条同质告警，
    # 聚合视图能让人一眼看到"谁、干了什么、多少次"，明细留着溯源。
    grouped = defaultdict(lambda: {'count': 0, 'levels': Counter()})
    for a in alerts:
        key = (a['ip'], a['category'], '、'.join(a['rule_names']))
        g = grouped[key]
        g['count'] += 1
        g['levels'][a['level']] += 1
    groups = []
    for (ip, category, names), g in grouped.items():
        level = max(g['levels'], key=lambda x: LEVEL_ORDER.get(x, 0))
        groups.append({
            'ip': ip, 'category': category, 'rules': names,
            'count': g['count'], 'level': level, 'level_label': LEVEL_LABEL[level],
        })
    groups.sort(key=lambda x: (-LEVEL_ORDER.get(x['level'], 0), -x['count']))

    # 可疑 UA 汇总（含命中工具 UA 的记录次数）
    suspect_uas = [
        {'ua': ua, 'count': c}
        for ua, c in suspect_ua_counter.most_common(10)
    ]

    return {
        'alerts': alerts,
        'groups': groups,
        'summary': {
            'total': len(alerts),
            'high': counter['high'],
            'medium': counter['medium'],
            'low': counter['low'],
            'affected_ips': len({a['ip'] for a in alerts}),
        },
        'high_freq_ips': sorted(high_freq_ips, key=lambda x: -x['peak_per_minute'])[:top_n],
        'error_rate_ips': sorted(error_rate_ips, key=lambda x: -x['error_rate'])[:top_n],
        'scanner_ips': sorted(scanner_ips, key=lambda x: -x['not_found'])[:top_n],
        'bruteforce': sorted(bruteforce, key=lambda x: -x['fails'])[:top_n],
        'suspect_uas': suspect_uas,
        'rules': engine.describe(),
        'thresholds': th,
    }
