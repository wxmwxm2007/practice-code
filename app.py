"""
网站访问日志可视化分析工具 —— Flask 应用入口
--------------------------------------------
职责很轻：接收日志文件、调用 analyzer 里的解析/统计/检测模块、把结果以 JSON
返回给前端；另外提供 CSV 导出接口。

真正的业务逻辑都在 analyzer 包里：
    analyzer/parser.py     日志解析
    analyzer/analytics.py  五种基础统计
    analyzer/detector.py   规则引擎 + 异常检测

运行方式： python app.py   → 浏览器打开 http://127.0.0.1:5000
"""

import csv
import io
import os
import time
from datetime import datetime

from flask import Flask, jsonify, request, send_file, send_from_directory

from analyzer.parser import parse_file
from analyzer.analytics import (
    overview, trend, top_ips, top_urls, status_distribution,
    method_distribution, ua_distribution,
)
from analyzer.detector import RuleEngine, detect_anomalies

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(BASE_DIR, 'rules.json')
DEMO_LOG = os.path.join(BASE_DIR, 'sample_data', 'demo_access.log')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024   # 单次上传上限 100MB
app.config['JSON_AS_ASCII'] = False

# 最近一次分析结果，供"分类导出 CSV"等后续请求使用（单机演示足够）
CACHE = {'result': None}


def analyze_log_file(file_path, source_name):
    """读取 → 解析 → 统计 → 检测，返回前端需要的完整结果。"""
    t_start = time.perf_counter()

    records, parse_stats = parse_file(file_path)
    if not records:
        raise ValueError('没有解析出任何有效日志行，请确认文件是 combined 格式的访问日志')

    parse_ms = (time.perf_counter() - t_start) * 1000

    # 规则每次分析都重新加载，改完 rules.json 不用重启服务
    engine = RuleEngine(RULES_PATH)
    anomalies = detect_anomalies(records, engine)

    t_stats = time.perf_counter()
    result = {
        'token': str(int(time.time() * 1000)),
        'meta': {
            'filename': source_name,
            'file_size': os.path.getsize(file_path),
            'parsed': parse_stats['parsed'],
            'total_lines': parse_stats['total_lines'],
            'failed': parse_stats['failed'],
            'failed_samples': parse_stats['failed_samples'],
            'parse_ms': round(parse_ms, 1),
            'total_ms': round((t_stats - t_start) * 1000, 1),
            'generated_at': datetime.now().isoformat(timespec='seconds'),
        },
        'overview': overview(records),
        'trend': trend(records),
        'top_ips': top_ips(records, 10),
        'top_urls': top_urls(records, 10),
        'status': status_distribution(records),
        'methods': method_distribution(records),
        'ua_top': ua_distribution(records),
        'anomalies': anomalies,
    }
    CACHE['result'] = result
    return result


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.post('/api/analyze')
def api_analyze():
    """上传日志文件并分析。前端用 multipart/form-data 的 file 字段上传。"""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': '没有收到文件，请选择 .log 文件后重试'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'ok': False, 'error': '文件名为空'}), 400

    os.makedirs(os.path.join(BASE_DIR, 'uploads'), exist_ok=True)
    # 只取原始文件名，避免路径穿越
    safe_name = os.path.basename(f.filename)
    tmp_path = os.path.join(BASE_DIR, 'uploads', safe_name)
    f.save(tmp_path)

    try:
        result = analyze_log_file(tmp_path, safe_name)
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    finally:
        # 解析完就删掉上传的临时文件，避免磁盘里堆满日志
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return jsonify({'ok': True, 'data': result})


@app.post('/api/demo')
def api_demo():
    """一键分析随项目附带的演示日志（现场演示时不用先找文件）。"""
    if not os.path.exists(DEMO_LOG):
        return jsonify({'ok': False, 'error': '演示日志不存在：sample_data/demo_access.log'}), 404
    try:
        result = analyze_log_file(DEMO_LOG, os.path.basename(DEMO_LOG))
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    return jsonify({'ok': True, 'data': result})


@app.get('/api/rules')
def api_rules():
    """返回当前规则清单，前端"检测规则"面板直接展示。"""
    engine = RuleEngine(RULES_PATH)
    return jsonify({'ok': True, 'data': {'rules': engine.describe(), 'thresholds': engine.thresholds}})


def _csv_response(rows, header, filename):
    """统一的 CSV 响应：utf-8-sig 防 Excel 中文乱码，newline='' 防多余空行。"""
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    data = buf.getvalue().encode('utf-8-sig')
    os.makedirs(EXPORT_DIR, exist_ok=True)
    save_path = os.path.join(EXPORT_DIR, filename)
    with open(save_path, 'wb') as f:
        f.write(data)
    return send_file(
        io.BytesIO(data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


@app.get('/api/export/anomalies.csv')
def export_anomalies():
    """导出异常明细。可选 ?level=high/medium/low 按等级筛选。"""
    result = CACHE['result']
    if not result:
        return jsonify({'ok': False, 'error': '还没有分析结果，请先分析一份日志'}), 400

    level = request.args.get('level', '').lower()
    alerts = result['anomalies']['alerts']
    if level in ('high', 'medium', 'low'):
        alerts = [a for a in alerts if a['level'] == level]

    header = ['告警编号', '风险等级', '类别', 'IP', '时间', '方法', 'URL',
              '状态码', 'User-Agent', '命中规则', '证据说明']
    rows = [
        [a['id'], a['level_label'], a['category'], a['ip'], a['time'], a['method'],
         a['url'], a['status'], a['ua'], '、'.join(a['rule_names']), a['evidence']]
        for a in alerts
    ]
    suffix = f'_{level}' if level in ('high', 'medium', 'low') else ''
    return _csv_response(rows, header, f'anomalies{suffix}.csv')


@app.get('/api/export/stats.csv')
def export_stats():
    """导出基础统计：总览 + Top IP + Top URL + 状态码 + 方法。"""
    result = CACHE['result']
    if not result:
        return jsonify({'ok': False, 'error': '还没有分析结果，请先分析一份日志'}), 400

    ov = result['overview']
    rows = [['总览', '总请求数', ov['total_requests']],
            ['总览', '独立 IP', ov['unique_ips']],
            ['总览', '独立 URL', ov['unique_urls']],
            ['总览', '错误请求数', ov['error_requests']],
            ['总览', '错误率', f"{ov['error_rate']:.2%}"],
            ['总览', '时间范围', f"{ov['start_time']} ~ {ov['end_time']}"],
            [], ['Top 访问 IP', '请求数', '占比']]
    rows += [[x['ip'], x['count'], f"{x['percent']:.2%}"] for x in result['top_ips']]
    rows += [[], ['Top 访问 URL', '请求数', '占比']]
    rows += [[x['url'], x['count'], f"{x['percent']:.2%}"] for x in result['top_urls']]
    rows += [[], ['状态码分布', '请求数']]
    rows += [[x['code'], x['count']] for x in result['status']['codes']]
    rows += [[], ['请求方法分布', '请求数']]
    rows += [[x['method'], x['count']] for x in result['methods']]
    return _csv_response(rows, ['统计类别', '统计项', '数值'], 'stats.csv')


@app.errorhandler(413)
def too_large(e):
    return jsonify({'ok': False, 'error': '文件超过 100MB 上限，请拆分日志后再上传'}), 413


def pick_port(preferred=5000, tries=20):
    """从 5000 开始找一个没被占用的端口，避免演示时和别的服务撞车。"""
    import socket
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # 不加 SO_REUSEADDR：Windows 下它会允许两个程序同时绑同一端口，
            # 探测结果就不准了
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return preferred


if __name__ == '__main__':
    port = pick_port()
    print('=' * 60)
    print(' 网站访问日志可视化分析工具')
    print(f' 启动地址： http://127.0.0.1:{port}')
    print(' 演示数据： sample_data/demo_access.log')
    print('=' * 60)
    app.run(host='127.0.0.1', port=port, debug=False)
