"""
生成《网站访问日志可视化分析工具 项目报告》Word 文档。

运行： python tools/generate_report.py
输出： 项目报告.docx
"""

import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, '项目报告.docx')
ASSETS = os.path.join(BASE, 'docs', 'assets')

FONT_CN = '宋体'
FONT_HEI = '黑体'
FONT_EN = 'Times New Roman'


def set_run_font(run, cn=FONT_CN, size=12, bold=False):
    """设置中西文字体（中文必须写 eastAsia，否则 Word 会回退到默认字体）。"""
    run.font.name = FONT_EN
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    rfonts.set(qn('w:ascii'), FONT_EN)
    rfonts.set(qn('w:hAnsi'), FONT_EN)
    rfonts.set(qn('w:eastAsia'), cn)


def set_style_font(style, cn, size, bold=False):
    style.font.name = FONT_EN
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    rfonts.set(qn('w:ascii'), FONT_EN)
    rfonts.set(qn('w:hAnsi'), FONT_EN)
    rfonts.set(qn('w:eastAsia'), cn)


def setup_document():
    doc = Document()

    # 页面：A4，四边 2.5 cm
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.5)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)

    # 正文：宋体 12pt，1.5 倍行距，首行缩进 2 字符，两端对齐
    normal = doc.styles['Normal']
    set_style_font(normal, FONT_CN, 12)
    pf = normal.paragraph_format
    pf.line_spacing = 1.5
    pf.first_line_indent = Pt(24)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 标题样式：黑体、黑色，不使用 Word 默认主题蓝
    h1 = doc.styles['Heading 1']
    set_style_font(h1, FONT_HEI, 14, bold=True)
    h1.paragraph_format.space_before = Pt(10)
    h1.paragraph_format.space_after = Pt(5)
    h1.paragraph_format.keep_with_next = True
    h1.paragraph_format.first_line_indent = Pt(0)
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    h2 = doc.styles['Heading 2']
    set_style_font(h2, FONT_HEI, 12, bold=True)
    h2.paragraph_format.space_before = Pt(8)
    h2.paragraph_format.space_after = Pt(4)
    h2.paragraph_format.keep_with_next = True
    h2.paragraph_format.first_line_indent = Pt(0)
    h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # 页脚页码（正文页，居中）
    footer_p = sec.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_p.paragraph_format.first_line_indent = Pt(0)
    add_page_field(footer_p)

    return doc


def add_page_field(paragraph):
    run = paragraph.add_run()
    set_run_font(run, FONT_CN, 10.5)
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = ' PAGE '
    fld_sep = OxmlElement('w:fldChar')
    fld_sep.set(qn('w:fldCharType'), 'separate')
    text = OxmlElement('w:t')
    text.text = '1'
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(text)
    run._r.append(fld_end)


def body(doc, text):
    p = doc.add_paragraph(style='Normal')
    p.add_run(text)
    return p


def h1(doc, text, new_page=True):
    p = doc.add_paragraph(style='Heading 1')
    if new_page:
        p.paragraph_format.page_break_before = True
    p.add_run(text)
    return p


def h2(doc, text):
    p = doc.add_paragraph(style='Heading 2')
    p.add_run(text)
    return p


def caption(doc, text, above=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Pt(0)
    pf.space_before = Pt(4)
    pf.space_after = Pt(4 if above else 6)
    pf.line_spacing = 1.0
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.keep_with_next = above
    r = p.add_run(text)
    set_run_font(r, FONT_CN, 10.5)
    return p


def shade_cell(cell, color='D9D9D9'):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color)
    tcpr.append(shd)


def set_cell_margins(table, top=40, bottom=40, left=110, right=110):
    """单元格边距（单位 twip），左右约 0.19cm。"""
    tblpr = table._tbl.tblPr
    mar = OxmlElement('w:tblCellMar')
    for tag, val in (('top', top), ('left', left), ('bottom', bottom), ('right', right)):
        node = OxmlElement(f'w:{tag}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        mar.append(node)
    tblpr.append(mar)


def row_props(row, header=False):
    trpr = row._tr.get_or_add_trPr()
    cant = OxmlElement('w:cantSplit')
    trpr.append(cant)
    if header:
        th = OxmlElement('w:tblHeader')
        trpr.append(th)


def write_cell(cell, text, bold=False, align='left', size=10.5):
    cell.text = ''
    p = cell.paragraphs[0]
    pf = p.paragraph_format
    pf.first_line_indent = Pt(0)
    pf.left_indent = Pt(0)
    pf.right_indent = Pt(0)
    pf.space_before = Pt(1)
    pf.space_after = Pt(1)
    pf.line_spacing = 1.0
    pf.alignment = {'left': WD_ALIGN_PARAGRAPH.LEFT,
                    'center': WD_ALIGN_PARAGRAPH.CENTER,
                    'right': WD_ALIGN_PARAGRAPH.RIGHT}[align]
    r = p.add_run(str(text))
    set_run_font(r, FONT_CN, size, bold=bold)


def add_table(doc, headers, rows, widths, aligns, title=None, caption_above=True):
    """创建规范表格：浅灰表头、全表垂直居中、行不跨页、表头跨页重复。"""
    if title:
        caption(doc, title, above=caption_above)

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_cell_margins(table)

    for i, w in enumerate(widths):
        table.columns[i].width = Cm(w)

    hdr = table.rows[0]
    row_props(hdr, header=True)
    for i, text in enumerate(headers):
        cell = hdr.cells[i]
        cell.width = Cm(widths[i])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade_cell(cell, 'D9D9D9')
        write_cell(cell, text, bold=True, align='center')

    for row_data in rows:
        row = table.add_row()
        row_props(row)
        for i, text in enumerate(row_data):
            cell = row.cells[i]
            cell.width = Cm(widths[i])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            write_cell(cell, text, align=aligns[i])

    return table


def add_image(doc, filename, width_cm, cap):
    path = os.path.join(ASSETS, filename)
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Cm(width_cm))
    caption(doc, cap)


def build_cover(doc):
    # 封面：用段前间距代替空段落，避免出现空白页
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(90)
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('网站访问日志可视化分析工具')
    set_run_font(r, FONT_HEI, 26, bold=True)

    p2 = doc.add_paragraph()
    p2.paragraph_format.first_line_indent = Pt(0)
    p2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(6)
    r2 = p2.add_run('项 目 报 告')
    set_run_font(r2, FONT_HEI, 20, bold=True)

    p3 = doc.add_paragraph()
    p3.paragraph_format.first_line_indent = Pt(0)
    p3.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_before = Pt(10)
    r3 = p3.add_run('大二项目实训 · 周期两周 · 后端 Python + 前端 ECharts')
    set_run_font(r3, FONT_CN, 11)

    p4 = doc.add_paragraph()
    p4.paragraph_format.space_before = Pt(110)
    p4.paragraph_format.first_line_indent = Pt(0)

    info = [
        ('项目名称', '网站访问日志可视化分析工具开发'),
        ('技术栈', 'Python 3 / Flask / HTML / JavaScript / ECharts 5 / Git'),
        ('开发者', '【姓名】'),
        ('专业班级', '【专业班级】'),
        ('学号', '【学号】'),
        ('指导教师', '【指导教师】'),
        ('完成日期', '2026 年 11 月 24 日'),
    ]
    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_cell_margins(table, top=60, bottom=60)
    for k, v in info:
        row = table.add_row()
        row_props(row)
        row.cells[0].width = Cm(3.6)
        row.cells[1].width = Cm(9.4)
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        write_cell(row.cells[0], k, bold=True, align='center', size=11)
        write_cell(row.cells[1], v, align='left', size=11)

    # 去掉信息表边框（封面用无框表更干净）
    remove_table_borders(table)


def remove_table_borders(table):
    tblpr = table._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'none')
        el.set(qn('w:sz'), '0')
        borders.append(el)
    tblpr.append(borders)


def build_content(doc):
    # ================= 一、项目概述 =================
    h1(doc, '一、项目概述')

    h2(doc, '（一）项目背景')
    body(doc, 'Web 访问日志是网站安全运维中最基础、也最容易被忽略的数据来源。攻击者的目录扫描、'
              '暴力破解、SQL 注入尝试，都会在 Nginx 或 Apache 的访问日志里留下一行行文本痕迹。'
              '一份普通企业站一天的日志就有一万多行，人工用记事本翻看既不现实，也看不出真正的异常。'
              '本项目要解决的正是这个问题：把一份文本日志变成一张能快速判断“网站正在发生什么”的现场图。')

    h2(doc, '（二）项目目标')
    body(doc, '按照任务书的要求，本项目需要完成一个可运行的工具，支持导入 Nginx/Apache 的 combined 格式'
              '访问日志，正确解析出 IP、时间、请求方法、URL、状态码、User-Agent 等字段，在此基础上完成'
              '访问趋势、Top 访问对象、状态码分布、请求方法分布等统计，并通过可配置规则识别高频访问、'
              '错误率突增、可疑 User-Agent 与攻击特征请求，最后以 ECharts 图表和异常明细表呈现，'
              '异常结果可导出为 CSV 文件。')

    h2(doc, '（三）成果概览')
    body(doc, '最终交付的工具由 Flask 后端与原生前端两部分组成，共 12 条检测规则、4 类统计检测、'
              '7 个可视化图表、28 个自动化测试用例。用一份 13,570 行的演示日志实测，完整分析'
              '（解析、统计、检测、组装返回数据）耗时约 0.3 秒，检出 558 条告警，覆盖目录扫描、'
              '登录爆破、SQL 注入、路径遍历、XSS、命令注入等 7 类行为。代码使用 Git 管理，'
              '共 12 次提交，提交信息按模块划分。')

    # ================= 二、需求分析 =================
    h1(doc, '二、需求分析与范围界定')

    h2(doc, '（一）功能需求')
    body(doc, '任务书把功能拆成六个模块。开发前我把每一条要求翻译成可验证的验收标准，'
              '避免最后“看起来做了”但经不起检查。具体对照见表 1。')

    add_table(doc,
              ['功能模块', '任务书要求', '本项目的实现与验证方式'],
              [
                  ['日志导入', '支持上传 .log 文件，1 万行以上不卡顿', '表单上传，单文件上限 100MB；13,570 行实测 0.3 秒完成'],
                  ['日志解析', '正确解析 combined 格式，字段提取准确', '正则命名分组提取 9 个字段，坏行跳过并计数；含时区与扩展字段'],
                  ['统计分析', '趋势、Top10 IP、Top10 URL、状态码、方法', '五个统计接口，另加 Top UA 辅助判断爬虫与工具'],
                  ['异常检测', '高频 IP、错误率异常、可疑 UA、攻击特征（规则≥5 条）', '12 条特征规则 + 4 类统计检测，阈值全部外置'],
                  ['可视化', '以上结果均以 ECharts 展示，布局清晰', '7 个图表 + 告警明细/聚合双视图表格，支持筛选与分页'],
                  ['结果导出', '异常明细导出 CSV', '按等级筛选导出，UTF-8-SIG 编码，Excel 打开不乱码'],
              ],
              widths=[3.0, 5.2, 7.6],
              aligns=['center', 'left', 'left'],
              title='表 1 功能需求对照表')

    h2(doc, '（二）非功能需求')
    body(doc, '除了功能，任务书还提出了三条工程性要求，它们比功能本身更能区分“能交差”和“能讲清楚”。'
              '其一是解析与检测逻辑必须模块化，规则要可配置，这意味着规则不能硬编码在 Python 字符串里；'
              '其二是使用 Git 管理代码且提交不少于 10 次，意味着提交历史本身也是交付物，'
              '不能一次把所有文件塞进一个 commit；其三是必须有可现场演示的样例数据，'
              '意味着演示日志要既能撑起图表的“量感”，又要真实包含各类攻击。')

    h2(doc, '（三）范围与取舍')
    body(doc, '本项目定位为单机演示工具，因此有意做了三处取舍：分析结果保存在内存中，'
              '不引入数据库，刷新后重新分析即可；只解析 combined 格式及其带 X-Forwarded-For 的变体，'
              '自定义日志格式需要修改解析器的正则；前端不引入构建工具，'
              '用原生 HTML 与 JavaScript 直接加载本地化的 ECharts，保证断网也能演示。'
              '这些取舍在下文“已知局限”中还会再次说明。')

    # ================= 三、总体架构 =================
    h1(doc, '三、总体架构与关键设计')

    h2(doc, '（一）技术选型')
    body(doc, '后端选择 Flask 而不是 FastAPI，原因很实际：本项目只有五个接口，'
              '不需要异步与自动文档，Flask 的路由与请求对象足够直观，'
              '排查“文件没收到”“路径写错”这类问题时调试成本最低。'
              '前端选择 HTML + 原生 JavaScript + ECharts，是因为任务书明确要求 ECharts，'
              '而 ECharts 本身就是 JavaScript 库；不引入 Vue 或 React，可以省掉 Node 构建环节，'
              '演示时直接打开浏览器就能跑。规则库用 JSON 而不是 YAML，'
              '是因为 Python 标准库自带 json，少一个依赖，且 JSON 在浏览器里可以直接查看。')

    h2(doc, '（二）分层结构')
    body(doc, '整个项目按“入口层—业务层—数据层—展示层”分层，每一层只做一件事。'
              '这样做的直接好处是：新增一条检测规则只需改 JSON，'
              '调整一个统计口径只需改 analytics，前端完全不用动。分层职责见表 2。')

    add_table(doc,
              ['层级', '文件/目录', '职责'],
              [
                  ['入口层', 'app.py', '五个 HTTP 接口、上传文件保存与清理、结果缓存、CSV 响应'],
                  ['业务层', 'analyzer/detector.py', '加载规则、特征匹配、统计类检测、告警聚合与分级'],
                  ['业务层', 'analyzer/analytics.py', '五类统计，趋势粒度自动选择与空时间段补齐'],
                  ['数据层', 'analyzer/parser.py', 'combined 日志正则解析、时间与字节容错、坏行统计'],
                  ['配置层', 'rules.json', '12 条特征规则与 5 个统计阈值，改完刷新即生效'],
                  ['展示层', 'static/', '页面结构、深色主题样式、图表渲染、表格筛选、CSV 下载'],
              ],
              widths=[2.6, 4.6, 8.6],
              aligns=['center', 'left', 'left'],
              title='表 2 分层架构与职责划分')

    h2(doc, '（三）数据流与解耦方式')
    body(doc, '一次分析的完整链路是：浏览器把文件以 multipart 形式上送到 /api/analyze，'
              '后端先落盘为临时文件，再交给 parser 逐行解析成“记录字典”，'
              '随后 analytics 与 detector 各自消费这份字典，产出若干纯 Python 结构，'
              '最后组装成一个 JSON 返回前端，前端用 ECharts 渲染并填充表格。'
              '解析与检测之间不直接调用，只通过“记录字典”这一中间格式衔接，'
              '因此检测模块可以脱离解析器单独测试，解析器也不需要知道规则长什么样。'
              '这一设计来自课程讲义中“解析器与检测引擎通过记录字典解耦”的思路，'
              '在编写单元测试时体现出明显价值：构造几条假记录就能验证检测逻辑，不必准备日志文件。')

    # ================= 四、核心实现 =================
    h1(doc, '四、核心模块实现')

    h2(doc, '（一）日志解析：用边界符而不是数空格')
    body(doc, 'combined 格式的难点在于字段内部含空格。User-Agent 与 Referer 被双引号包住，'
              '请求行整体也是一个双引号字段，如果按空格切分，UA 里的空格会把后面的字段全部错位。'
              '因此解析正则用“成对的边界符”定位字段：方括号只出现在时间字段，'
              '双引号只出现在请求行、Referer、UA，抓住边界符比数字段可靠得多。'
              '正则里使用命名分组，解析结果直接是字段名到值的字典，后续代码不需要再按位置取下标。')

    body(doc, '容错分三层处理。第一层是整行匹配失败时返回 None 而不是抛异常，'
              '一批日志中几行畸形数据不会中断整个导入，失败行会被统计并给出前五条示例；'
              '第二层是字段级容错，状态码可能是三位数字、字节数可能是“-”、'
              '请求行可能整体是“-”（服务器收到畸形请求时无法解析），这些情况都做了判断，'
              '不会把字符串直接转整数而崩溃；第三层是编码容错，读取时使用 errors="replace"，'
              '遇到非 UTF-8 的脏字节不会让整次导入失败。')

    body(doc, '时间字段的时区偏移被保留下来转成带时区的 datetime，而不是简单地按本地时间处理。'
              '这一点直接影响趋势图：如果把 +0000 的日志按 +0800 解释，凌晨的攻击会被画到上午八点，'
              '整条曲线会平移八小时，安全分析的时间线也就失真了。')

    h2(doc, '（二）统计分析：口径先想清楚再写代码')
    body(doc, '统计部分最容易出错的地方不是写代码，而是口径。以 Top URL 为例，'
              '如果直接用完整路径聚合并把查询串算进去，/article?id=1 和 /article?id=2 会被算成两条 URL，'
              '排名完全失真，所以项目里用去掉查询串的纯路径做聚合键。'
              '状态码统计则做了两层：既给出每个具体状态码的数量，用于前端饼图，'
              '也归并成 2xx、3xx、4xx、5xx 四类，用于计算错误率和错误率异常检测。')

    body(doc, '趋势图的横轴粒度按时间跨度自动选择：三小时内按分钟、三天内按小时、更长按天，'
              '并在聚合后补齐中间没有请求的时间段。补桶这一步看起来多余，'
              '但如果不补，凌晨没有访问的两小时会被直接“压缩”掉，尖峰的位置就会骗人。')

    h2(doc, '（三）规则引擎：可配置不是一句口号')
    body(doc, '规则引擎的设计目标是“发现新攻击变种时，只改 JSON，不动代码”。'
              '它在初始化时一次性读取 rules.json，把正则类型的规则预编译，'
              '检测循环里没有任何 re.compile 的开销。匹配前统一做两件事：'
              'URL 解码与小写化。解码用来对抗 %27or%201%3D1 这类把单引号和空格编码的写法，'
              '小写化配合正则的 re.I 用来对抗 UnIoN SeLeCt 这类大小写混淆。'
              '这两步统一放在取待检测文本的函数里，一处处理，所有规则受益。')

    body(doc, '引擎支持两类规则：path_pattern 是正则型，适合表达变体；'
              'path_keyword 与 ua_keyword 是关键词型，用逗号分隔关键词做子串匹配，'
              '适合“敏感路径列表”“工具 UA 列表”这种枚举型规则。'
              '两类规则分开处理是有教训的：开发中曾把 UA 关键词规则也编译成正则，'
              '结果 “sqlmap,hydra,dirsearch” 这串文本被当成一个完整正则去匹配，'
              '自然一条都命中不了，导致整个演示数据里一个工具 UA 都没报出来。'
              '这个 bug 在单元测试里被固定为回归用例，提醒自己规则类型必须显式分派。')

    h2(doc, '（四）统计类检测：阈值是防误报的关键')
    body(doc, '特征规则只能判断“单条请求可疑”，而扫描、爆破的本质是“行为模式可疑”，'
              '必须靠按 IP 聚合后的统计量来判断。项目实现了四类统计检测。'
              '单 IP 高频访问以一分钟为窗口统计峰值请求数，超过阈值即告警，'
              '并按“达到两倍阈值”提升为高危。错误率异常要求该 IP 总请求数不少于 50 次、'
              '且 4xx/5xx 占比超过 60%，最小样本这一条专门用来防止“三次请求三次 404”的误报。'
              '在错误率基础上又单独识别 404 占比超过 80% 的 IP，'
              '因为目录扫描的典型形态就是大量 404 而不是大量 500。')

    body(doc, '暴力破解的判定不只看失败次数：同一 IP 对含 login、signin、auth 的路径发起 POST 请求，'
              '401/403 次数超过 30 次即可疑，如果之后又出现 200 响应，则直接判为高危，'
              '因为这意味着字典爆破可能已经成功，账户处于失守状态。'
              '这是本项目中唯一一条“结果导向”的判定，也是最需要人工复核的一条。')

    body(doc, '由于一条目录扫描会产生几百条同质告警，如果全部平铺在表格里，'
              '真正要紧的几条就会被淹没。因此检测结果在返回前又按“IP + 类别 + 命中规则”做了一次聚合，'
              '前端提供“明细/聚合”双视图：聚合视图看谁在做什么、做了多少次，'
              '明细视图留着回溯具体的时间与 URL。')

    h2(doc, '（五）可视化与交互')
    body(doc, '前端共七个图表：访问趋势折线（总请求与 4xx/5xx 两条线）、状态码分布环形图、'
              '告警风险等级环形图、Top10 IP 与 Top10 URL 横向条形图、请求方法柱状图、Top UA 横向条形图。'
              '图表并非装饰：Top IP 里第一名用红色渐变高亮，和正常访客区分开；'
              '趋势图上凌晨的尖峰与扫描时间段能够对应；状态码环形图里 4xx 与 2xx 的比例一目了然。')

    body(doc, '异常明细表支持按风险等级、类别、关键字三重筛选，并按每页 20 条分页。'
              '一个容易被忽略的安全细节是：日志内容是不可信输入，演示数据里就包含 '
              '<script>alert(1)</script> 这样的 XSS 载荷，如果直接把日志文本拼进 innerHTML，'
              '页面自己就会被注入。因此前端所有展示字段都经过转义函数处理，'
              '只允许作为文本显示。这既是安全习惯，也让“分析攻击日志的工具本身不能被打穿”这句话站得住。')

    body(doc, 'CSV 导出有两个坑：一是编码，必须使用 utf-8-sig 带 BOM，否则 Excel 打开中文会乱码；'
              '二是换行，StringIO 必须使用 newline=""，否则 Windows 下会多出空行。'
              '导出接口同时支持按等级筛选，例如只导出高危告警，方便现场演示时聚焦重点。')

    # ================= 五、规则说明 =================
    h1(doc, '五、检测规则说明')

    h2(doc, '（一）特征规则清单')
    body(doc, '规则库共 12 条特征规则，覆盖注入、遍历、脚本执行、敏感路径与工具指纹五类，'
              '全部写在 rules.json 中，逐条标注风险等级。清单见表 3。')

    add_table(doc,
              ['规则 ID', '规则名称', '类型', '等级', '覆盖的典型特征'],
              [
                  ['SQLI-001', 'SQL 注入 - 联合查询', '正则', '高', 'union select，含 /**/ 注释绕过'],
                  ['SQLI-002', 'SQL 注入 - 恒真条件', '正则', '高', 'or 1=1、and 1=1 及引号闭合变体'],
                  ['SQLI-003', 'SQL 注入 - 时间盲注', '正则', '高', 'sleep()、benchmark()、waitfor delay'],
                  ['SQLI-004', 'SQL 注入 - 数据窃取', '正则', '高', 'information_schema、load_file、outfile'],
                  ['SQLI-005', 'SQL 注入 - 语句闭合', '正则', '高', 'or/and 后直接接 select/update'],
                  ['TRAV-001', '路径遍历 - 目录穿越', '正则', '高', '../../../、..;、%2e%2e、双重编码'],
                  ['TRAV-002', '路径遍历 - 敏感文件', '正则', '高', 'etc/passwd、win.ini、proc/self'],
                  ['XSS-001', '跨站脚本特征', '正则', '高', '<script>、%3Cscript、onerror='],
                  ['CMD-001', '命令注入 - 管道执行', '正则', '高', ';cat、|whoami、&&wget'],
                  ['SENS-001', '敏感路径探测', '关键词', '中', '.git、.env、phpmyadmin、backup.zip'],
                  ['UA-001', '攻击工具 UA', '关键词', '高', 'sqlmap、hydra、dirsearch、nikto、nmap'],
                  ['UA-002', '脚本类 UA', '关键词', '低', 'python-requests、curl、wget、go-http-client'],
              ],
              widths=[2.2, 4.2, 1.8, 1.4, 6.2],
              aligns=['center', 'left', 'center', 'center', 'left'],
              title='表 3 特征规则清单')

    h2(doc, '（二）统计阈值')
    body(doc, '统计类检测的五个阈值同样放在 rules.json 的 thresholds 节点中，'
              '调整灵敏度不需要改任何 Python 代码。当前配置见表 4。')

    add_table(doc,
              ['配置项', '当前值', '含义与设定依据'],
              [
                  ['high_freq_per_minute', '300 次/分', '正常访客一分钟极少超过 300 次，扫描器轻易突破'],
                  ['error_rate', '0.6', '错误率超过 60% 时，正常业务的可能性已经很低'],
                  ['error_min_requests', '50 次', '最小样本量，避免请求量太小的 IP 被误判'],
                  ['bruteforce_fails', '30 次', '同一 IP 对登录接口失败 30 次以上，已超出人工试错范围'],
                  ['scan_404_rate', '0.8', '404 占比超过 80%，符合目录字典扫描的典型形态'],
              ],
              widths=[4.6, 2.6, 8.6],
              aligns=['left', 'center', 'left'],
              title='表 4 统计阈值配置')

    h2(doc, '（三）风险分级与处置建议')
    body(doc, '分级不是为了好看，而是为了让人知道先看哪一条。高危意味着应当立即人工核查，'
              '中危列入观察，低危仅作记录。分级标准见表 5，前端用红、橙、黄三色区分，'
              '导出 CSV 时也按等级排序。')

    add_table(doc,
              ['等级', '判定依据', '处置建议'],
              [
                  ['高危', '注入、遍历、命令执行特征命中；攻击工具 UA；爆破后出现 200；错误率≥90%', '立即核查看该 IP 完整请求序列，必要时封禁'],
                  ['中危', '敏感路径探测；空 User-Agent；错误率 60%~90%；扫描未达高频阈值', '列入观察名单，结合访问频率判断'],
                  ['低危', 'curl、python-requests 等脚本类 UA；少量敏感路径探测', '仅记录，避免淹没真正的告警'],
              ],
              widths=[1.8, 10.4, 4.6],
              aligns=['center', 'left', 'left'],
              title='表 5 风险分级与处置建议')

    h2(doc, '（四）误报与漏报的权衡')
    body(doc, '规则系统一定同时存在误报和漏报，报告里如实写出这一点比宣称“准确率很高”更可信。'
              '典型的误报是：技术博客文章的标题恰好含有 “union select”，被 SQLI-001 判为高危；'
              '用户手敲错网址产生单个 404，如果只看单条就会被当成扫描。'
              '项目用三种方式缓解：叠加频率与最小样本阈值、引入路径白名单思路（本站正常路径可排除）、'
              '分级展示让中危只提示不告警。')

    body(doc, '漏报同样存在：攻击者用 /**/union/**/select 把注释当空格，'
              '或用 %252e%252e 做双重编码，明文规则就会失效。项目对常见变体做了覆盖'
              '（SQLI-001 已包含注释绕过写法，TRAV-001 覆盖双重编码与 ..; 变体），'
              '但不可能穷尽。这也是规则必须外置的现实原因：发现新变种时，'
              '改一行 JSON、刷新页面即可生效，不必重新部署。'
              '新增规则的写法是在 rules 数组里追加一个对象，指定 id、type、name、level 与 pattern，'
              '正则型规则默认不区分大小写。')

    # ================= 六、测试 =================
    h1(doc, '六、测试与结果')

    h2(doc, '（一）自动化测试')
    body(doc, '测试使用 Python 标准库 unittest 编写，共 28 个用例，不依赖第三方测试框架，'
              '命令行执行 python -m unittest discover -s tests -v 即可。'
              '测试覆盖解析容错、时区、统计口径、规则命中（含大小写与 URL 编码绕过）、'
              '统计类检测、上传接口与 CSV 编码。分类与结果见表 6。')

    add_table(doc,
              ['测试类', '用例数', '重点验证内容', '结果'],
              [
                  ['TestParser', '6', '标准行、扩展 XFF 行、畸形请求行、字节数为 -、时区、坏行返回 None', '全部通过'],
                  ['TestAnalytics', '4', '总览指标、Top 排名、状态码归类、分钟粒度趋势', '全部通过'],
                  ['TestRuleEngine', '9', '注入、注释绕过、盲注、遍历与编码、敏感路径、工具 UA、干净请求', '全部通过'],
                  ['TestStatisticalDetect', '4', '错误率异常、404 扫描、爆破成功判定、高频检测', '全部通过'],
                  ['TestFlaskApi', '5', '演示接口、文件上传、CSV BOM 与表头、等级筛选、无结果时导出', '全部通过'],
              ],
              widths=[4.4, 1.6, 8.6, 2.2],
              aligns=['left', 'center', 'left', 'center'],
              title='表 6 测试用例分类与结果')

    body(doc, '其中三类用例是“踩过坑之后补的”：UA 关键词规则误编译为正则、'
              'error_rate 字段名前后不一致、导入时端口被占用导致服务看似启动实际不可用。'
              '把 bug 固化成测试，是这轮开发里最有效的一个习惯。')

    h2(doc, '（二）性能测试')
    body(doc, '任务书要求 1 万行以上不卡顿。用 13,570 行的演示日志实测，'
              '纯解析耗时 136 ms，解析加统计加异常检测的完整流程约 296 ms，'
              '文件体积 2.9MB。这个量级下用户几乎感知不到等待，前端加载动画只是为了体验一致，'
              '并非性能不足的遮掩。如果把日志扩大到百万行，瓶颈会出现在按 IP 聚合的字典与内存占用上，'
              '这属于后续优化范围。')

    h2(doc, '（三）功能验证结果')
    body(doc, '演示日志中植入的七类行为全部被检出，具体结果见表 7。'
              '值得注意的是 dirsearch 扫描：400 次请求全部返回 404，404 占比 100%，'
              '既触发敏感路径规则，也触发错误率异常与 404 扫描识别，'
              '在聚合视图里显示为一条 355 次的高危记录，比 355 条平铺告警更容易读懂。'
              'Hydra 爆破的 60 次 401 与随后一次 200 被判定为高危，对应“可能已攻破”的结论。')

    add_table(doc,
              ['植入场景', '来源 IP', '日志中的表现', '检出结果'],
              [
                  ['dirsearch 目录扫描', '66.102.9.15', '40 秒 400 次请求，全部 404', '敏感路径 + 工具 UA + 错误率 100% + 404 扫描，高危'],
                  ['Hydra 登录爆破', '45.148.10.88', '60 次 401 后出现 1 次 200', '爆破成功，高危'],
                  ['sqlmap 注入测试', '198.51.100.7', '15 条 union select、sleep 等载荷', 'SQLI 系列规则命中，高危'],
                  ['路径遍历', '185.220.101.5 等', '../../etc/passwd、%2e%2e、....//', 'TRAV-001 与 TRAV-002 同时命中'],
                  ['XSS 与命令注入', '91.219.236.44 等', '<script>、%3Cscript、;cat /etc/passwd', 'XSS-001 与 CMD-001 命中'],
                  ['nikto 漏洞扫描', '203.0.113.66', '探测 /admin、/server-status', '工具 UA 命中，高危'],
                  ['浏览器手工探路', '61.160.35.2', '正常 UA 探测 .git、.env', '仅命中敏感路径规则，中危'],
              ],
              widths=[3.4, 3.0, 5.6, 4.8],
              aligns=['left', 'center', 'left', 'left'],
              title='表 7 演示数据检测结果')

    body(doc, '图 1 为首页，图 2 为分析结果页首屏，图 3 为异常明细区。'
              '三张图对应现场演示的三个动作：导入、看总览与图表、看告警并解释证据链。')

    add_image(doc, 'ui-home.png', 15.2, '图 1 系统首页与日志上传入口')
    add_image(doc, 'ui-dashboard.png', 15.2, '图 2 分析结果页：总览指标与七个图表')
    add_image(doc, 'ui-alerts.png', 15.2, '图 3 异常明细区：等级筛选、明细与聚合双视图')

    # ================= 七、难点 =================
    h1(doc, '七、开发中的问题与解决')

    body(doc, '开发过程中遇到的问题大多属于“看起来能跑，实际结果不对”的类型，'
              '比语法错误更难排查。挑选六个有代表性的记录下来，见表 8。')

    add_table(doc,
              ['问题现象', '原因', '解决方式'],
              [
                  ['工具 UA 一条都没报出来', 'UA 关键词规则被当成正则编译，逗号串不匹配任何 UA', '按规则类型分派，关键词型走子串匹配；补回归用例'],
                  ['前端导出报 500', '错误率列表字段叫 rate，排序读取 error_rate，键名不一致', '统一字段名并补接口测试'],
                  ['本地服务“启动成功”却访问不到接口', 'Windows 下 SO_REUSEADDR 允许两个进程绑同一端口', '端口探测不加复用选项，被占用则顺延到 5001'],
                  ['Top UA 图表出现 6,487 次一条的超大条目', '先截断 UA 60 字符再计数，Chrome 与 Edge 被合并', '用完整 UA 做聚合键，仅展示时截断'],
                  ['表格列过挤、证据文字换行挤成多行', '九列同屏超出可用宽度', '合并方法与 URL 列，时间精简为月日时分'],
                  ['页面渲染时告警表把脚本内容当代码执行风险', '日志是不可信输入', '所有展示字段统一转义，只作文本输出'],
              ],
              widths=[4.6, 6.0, 6.4],
              aligns=['left', 'left', 'left'],
              title='表 8 典型问题与解决方式')

    body(doc, '这些问题背后有一个共同经验：凡是“统计结果看起来不对”，先检查数据口径和字段名；'
              '凡是“规则不命中”，先检查编码、大小写与规则类型；'
              '凡是“本地环境正常、演示环境不对”，先检查端口与文件路径。'
              '把每次排查的结论写进测试或文档，比记住结论本身更有用。')

    # ================= 八、总结 =================
    h1(doc, '八、个人总结与改进方向')

    h2(doc, '（一）主要收获')
    body(doc, '第一，真正理解了“日志是证据”。以前看日志只是找报错，这次为了写规则，'
              '必须按攻击者的视角逐条读：扫描器为什么在 40 秒内打 400 次、'
              '爆破为什么总是在同一路径上留下整齐的 401。规则写不出来，往往不是正则不会写，'
              '而是没有想清楚这个行为在日志里到底长什么样。')

    body(doc, '第二，体会到模块化不是为了好看，而是为了能改。解析器与检测器通过记录字典解耦之后，'
              '补一条规则不需要碰解析代码，写一个测试不需要准备日志文件。'
              '当 UA 规则那个 bug 出现时，我只改了一个函数就能修好，因为边界是清楚的。')

    body(doc, '第三，学会了在“误报”和“漏报”之间做取舍。任何检测系统都不可能两全，'
              '关键是让阈值可配置、让等级可分级、让证据可追溯。'
              '这也是我在报告里专门写“已知局限”的原因：承认抓不全，比假装抓得全更专业。')

    h2(doc, '（二）不足')
    body(doc, '当前实现的不足也很明确。分析结果只存在内存里，无法对比历史批次，'
              '也就看不出“今天比昨天多了 30% 扫描”这种趋势；'
              '只支持 combined 一种格式，真实环境的自定义日志还需要改代码；'
              '规则全部是正则与阈值，没有引入白名单与机器学习，'
              '对低速慢扫（每分钟十几次、持续几小时）几乎无能为力；'
              '前端为单页结构，没有做移动端适配的深入优化。')

    h2(doc, '（三）后续改进计划')
    body(doc, '如果继续做，我会按优先级推进四件事：其一，引入 SQLite 保存每次分析结果，'
              '支持按天对比与历史查询；其二，增加规则白名单与“同 IP 长周期低速扫描”识别，'
              '把时间窗口从一分钟扩展到一小时；其三，支持多文件批量导入与压缩包解析，'
              '贴近真实运维场景；其四，把异常明细做成可下钻的详情页，'
              '点开一个 IP 就能看到它完整的时间线，而不是只有一条证据。')

    body(doc, '这次实训最大的价值不在于做出一个能演示的页面，而在于完整走了一遍'
              '“读需求—拆模块—写实现—测边界—补文档”的流程。'
              '两周时间做不出完美的产品，但可以做出一个每一处都能解释清楚为什么这样做的作品，'
              '这是我对这次项目最满意的地方。')

    # ================= 九、参考资料 =================
    h1(doc, '九、参考资料')
    body(doc, '[1] 课程讲义：01-HTTP 协议基础-方法与状态码、02-Nginx 与 Apache 日志格式详解、'
              '03-Python 速成-文件处理正则与 Flask、04-ECharts 进阶-折线饼图柱状图、'
              '05-攻击日志特征库-SQL 注入扫描与爆破。')
    body(doc, '[2] 项目任务书《网站访问日志可视化分析工具开发》，2026 年。')
    p = doc.add_paragraph(style='Normal')
    p.add_run('[3] Flask 官方文档：')
    add_hyperlink(p, 'https://flask.palletsprojects.com/', 'https://flask.palletsprojects.com/')
    p2 = doc.add_paragraph(style='Normal')
    p2.add_run('[4] Apache ECharts 官方文档：')
    add_hyperlink(p2, 'https://echarts.apache.org/', 'https://echarts.apache.org/')


def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    run = OxmlElement('w:r')
    rpr = OxmlElement('w:rPr')
    rfonts = OxmlElement('w:rFonts')
    rfonts.set(qn('w:ascii'), FONT_EN)
    rfonts.set(qn('w:hAnsi'), FONT_EN)
    rfonts.set(qn('w:eastAsia'), FONT_CN)
    rpr.append(rfonts)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), '24')
    rpr.append(sz)
    color = OxmlElement('w:color')
    color.set(qn('w:val'), '0563C1')
    rpr.append(color)
    u = OxmlElement('w:u')
    u.set(qn('w:val'), 'single')
    rpr.append(u)
    run.append(rpr)
    t = OxmlElement('w:t')
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def main():
    doc = setup_document()
    build_cover(doc)
    build_content(doc)
    doc.core_properties.title = '网站访问日志可视化分析工具 项目报告'
    doc.core_properties.author = '【姓名】'
    doc.save(OUT)
    print('saved:', OUT)


if __name__ == '__main__':
    main()
