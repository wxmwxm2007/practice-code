"""
核心模块单元测试
----------------
不依赖 pytest，直接用标准库 unittest，双击运行或命令行 `python -m unittest` 均可。

覆盖点：
1. 解析器：标准行、带 X-Forwarded-For 的扩展行、坏行、字节数为 -、请求行为 -
2. 时间解析：时区偏移是否正确
3. 统计：Top IP、状态码归类、趋势粒度
4. 规则引擎：SQL 注入、路径遍历、敏感路径、工具 UA、URL 编码绕过
5. 统计类检测：错误率异常、暴力破解（含成功）
6. Flask 接口：上传分析、CSV 导出编码
"""

import io
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from analyzer.parser import parse_line, parse_time
from analyzer.analytics import overview, trend, top_ips, top_urls, status_distribution
from analyzer.detector import RuleEngine, detect_anomalies
import app as webapp

RULES = os.path.join(BASE, 'rules.json')
ENGINE = RuleEngine(RULES)

STANDARD_LINE = ('127.0.0.1 - frank [10/Oct/2023:13:55:36 +0800] '
                 '"GET /apache_pb.gif HTTP/1.0" 200 2326 '
                 '"http://www.example.com/start.html" "Mozilla/4.08 [en] (Win98; I ;Nav)"')


class TestParser(unittest.TestCase):

    def test_standard_line(self):
        rec = parse_line(STANDARD_LINE)
        self.assertIsNotNone(rec)
        self.assertEqual(rec['ip'], '127.0.0.1')
        self.assertEqual(rec['user'], 'frank')
        self.assertEqual(rec['method'], 'GET')
        self.assertEqual(rec['path'], '/apache_pb.gif')
        self.assertEqual(rec['status'], 200)
        self.assertEqual(rec['bytes'], 2326)
        self.assertEqual(rec['referer'], 'http://www.example.com/start.html')
        self.assertIn('Mozilla/4.08', rec['ua'])

    def test_time_with_timezone(self):
        dt = parse_time('10/Oct/2023:13:55:36 +0800')
        self.assertEqual(dt.utcoffset(), timedelta(hours=8))
        self.assertEqual(dt.hour, 13)

    def test_bytes_dash_and_head(self):
        line = ('203.0.113.5 - - [07/Sep/2026:02:15:44 +0000] '
                '"HEAD /index.html HTTP/1.1" 304 - "-" "curl/7.68.0"')
        rec = parse_line(line)
        self.assertEqual(rec['method'], 'HEAD')
        self.assertEqual(rec['status'], 304)
        self.assertNoneBytes(rec)

    def assertNoneBytes(self, rec):
        self.assertIsNone(rec['bytes'])

    def test_malformed_request(self):
        line = ('1.2.3.4 - - [07/Sep/2026:02:15:44 +0000] '
                '"-" 400 0 "-" "-"')
        rec = parse_line(line)
        self.assertEqual(rec['method'], '-')
        self.assertEqual(rec['path'], '-')
        self.assertEqual(rec['status'], 400)

    def test_extra_forwarded_for(self):
        line = ('10.0.0.8 - - [07/Sep/2026:02:15:44 +0000] '
                '"GET /a HTTP/1.1" 200 100 "-" "UA" "1.2.3.4, 10.0.0.8"')
        rec = parse_line(line)
        self.assertEqual(rec['ip'], '10.0.0.8')
        self.assertIn('1.2.3.4', rec['extra'])

    def test_bad_line_returns_none(self):
        self.assertIsNone(parse_line('this is not a log line'))
        self.assertIsNone(parse_line(''))
        self.assertIsNone(parse_line('# comment'))


class TestAnalytics(unittest.TestCase):

    def setUp(self):
        self.records = [
            {'ip': '1.1.1.1', 'path_only': '/a', 'status': 200, 'method': 'GET', 'timestamp': 1000.0,
             'ua': 'UA-A', 'bytes': 10},
            {'ip': '1.1.1.1', 'path_only': '/a', 'status': 404, 'method': 'GET', 'timestamp': 1000.0,
             'ua': 'UA-A', 'bytes': 10},
            {'ip': '2.2.2.2', 'path_only': '/b', 'status': 500, 'method': 'POST', 'timestamp': 7300.0,
             'ua': 'UA-B', 'bytes': 20},
        ]

    def test_overview(self):
        ov = overview(self.records)
        self.assertEqual(ov['total_requests'], 3)
        self.assertEqual(ov['unique_ips'], 2)
        self.assertAlmostEqual(ov['error_rate'], round(2 / 3, 4))

    def test_top(self):
        self.assertEqual(top_ips(self.records)[0]['ip'], '1.1.1.1')
        self.assertEqual(top_urls(self.records)[0]['url'], '/a')

    def test_status_classes(self):
        classes = {x['name']: x['value'] for x in status_distribution(self.records)['classes']}
        self.assertEqual(classes['2xx'], 1)
        self.assertEqual(classes['4xx'], 1)
        self.assertEqual(classes['5xx'], 1)

    def test_trend_minute_granularity(self):
        t = trend(self.records)
        self.assertEqual(t['granularity'], 'minute')
        self.assertEqual(sum(t['total']), 3)
        self.assertEqual(sum(t['errors']), 2)


class TestRuleEngine(unittest.TestCase):

    def hits(self, path, ua='Mozilla/5.0'):
        return [h['id'] for h in ENGINE.match({'path': path, 'ua': ua})]

    def test_union_select(self):
        self.assertIn('SQLI-001', self.hits('/a.php?id=1 UNION SELECT 1,2'))

    def test_case_and_comment_bypass(self):
        self.assertIn('SQLI-001', self.hits('/a.php?id=1 uNiOn/**/SeLeCt 1,2'))

    def test_time_based_blind(self):
        self.assertIn('SQLI-003', self.hits('/a.php?id=1 AND SLEEP(5)'))

    def test_path_traversal(self):
        self.assertIn('TRAV-001', self.hits('/download?file=../../etc/passwd'))

    def test_encoded_traversal(self):
        self.assertIn('TRAV-001', self.hits('/download?file=%2e%2e%2f%2e%2e%2fetc/passwd'))

    def test_sensitive_path(self):
        self.assertIn('SENS-001', self.hits('/.git/config'))

    def test_tool_ua(self):
        self.assertIn('UA-001', self.hits('/index.html', ua='sqlmap/1.7.2#stable'))

    def test_url_encoded_sql(self):
        self.assertIn('SQLI-002', self.hits("/search?q=%27or%201%3D1"))

    def test_clean_request(self):
        self.assertEqual(self.hits('/article/12345', ua='Mozilla/5.0 (Windows NT 10.0)'), [])


class TestStatisticalDetect(unittest.TestCase):

    def make_records(self):
        recs = []
        # 一个扫描 IP：100 次请求 90 个 404，集中在同一分钟
        for i in range(100):
            recs.append({
                'ip': '9.9.9.9', 'path': '/guess%d' % i, 'ua': 'Mozilla/5.0',
                'status': 404 if i < 90 else 200, 'method': 'GET',
                'timestamp': 1000.0 + i * 0.3, 'time_raw': '07/Sep/2026:00:00:00 +0000',
            })
        # 一个爆破 IP：40 次 401 后 1 次 200
        for i in range(41):
            recs.append({
                'ip': '8.8.8.8', 'path': '/login', 'ua': 'Hydra/9.4',
                'status': 401 if i < 40 else 200, 'method': 'POST',
                'timestamp': 2000.0 + i * 3, 'time_raw': '07/Sep/2026:00:30:00 +0000',
            })
        return recs

    def test_error_rate_alert(self):
        result = detect_anomalies(self.make_records(), ENGINE)
        ips = {a['ip'] for a in result['alerts'] if a['category'] == '错误率异常'}
        self.assertIn('9.9.9.9', ips)

    def test_scanner_404(self):
        result = detect_anomalies(self.make_records(), ENGINE)
        scanner = {s['ip'] for s in result['scanner_ips']}
        self.assertIn('9.9.9.9', scanner)

    def test_bruteforce_with_success(self):
        result = detect_anomalies(self.make_records(), ENGINE)
        bf = [b for b in result['bruteforce'] if b['ip'] == '8.8.8.8']
        self.assertTrue(bf)
        self.assertEqual(bf[0]['fails'], 40)
        self.assertEqual(bf[0]['success'], 1)
        self.assertEqual(bf[0]['level'], 'high')

    def test_high_freq(self):
        result = detect_anomalies(self.make_records(), ENGINE)
        freq = [f for f in result['high_freq_ips'] if f['ip'] == '9.9.9.9']
        self.assertTrue(freq)
        self.assertGreaterEqual(freq[0]['peak_per_minute'], 25)


class TestFlaskApi(unittest.TestCase):

    def setUp(self):
        self.client = webapp.app.test_client()

    def test_demo_api(self):
        resp = self.client.post('/api/demo')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['ok'])
        self.assertGreater(data['data']['meta']['parsed'], 10000)
        self.assertGreater(data['data']['anomalies']['summary']['high'], 0)

    def test_upload_api(self):
        with open(os.path.join(BASE, 'sample_data', 'demo_access.log'), 'rb') as f:
            content = f.read()
        resp = self.client.post('/api/analyze', data={
            'file': (io.BytesIO(content), 'upload_test.log'),
        }, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['ok'])

    def test_export_csv(self):
        self.client.post('/api/demo')
        resp = self.client.get('/api/export/anomalies.csv')
        self.assertEqual(resp.status_code, 200)
        # utf-8-sig 开头带 BOM，Excel 中文不乱码
        self.assertTrue(resp.data.startswith(b'\xef\xbb\xbf'))
        text = resp.data.decode('utf-8-sig')
        self.assertIn('风险等级', text.splitlines()[0])

    def test_export_filtered(self):
        self.client.post('/api/demo')
        resp = self.client.get('/api/export/anomalies.csv?level=high')
        self.assertEqual(resp.status_code, 200)

    def test_export_without_analysis(self):
        webapp.CACHE['result'] = None
        resp = self.client.get('/api/export/stats.csv')
        self.assertEqual(resp.status_code, 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
