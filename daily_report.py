#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日股票理财报告 - 自动抓取市场数据并推送到微信
支持早盘(8:00)和晚盘(22:00)两种模式
数据来源：新浪财经（免费、无需Key）
推送通道：推送加 PushPlus（推送到微信）
"""

import requests
import os
import re
from datetime import datetime, timezone, timedelta

# ==================== 配置 ====================
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN', '')
PUSHPLUS_URL = 'https://www.pushplus.plus/send'

SINA_URL = 'https://hq.sinajs.cn/list={}'
SINA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://finance.sina.com.cn',
}

INDICES = {
    'A股': [
        ('sh000001', '上证指数'),
        ('sz399001', '深证成指'),
        ('sz399006', '创业板指'),
        ('sh000300', '沪深300'),
    ],
    '美股': [
        ('gb_dji', '道琼斯'),
        ('gb_inx', '标普500'),
        ('gb_ixic', '纳斯达克'),
    ],
    '港股': [
        ('rt_hkHSI', '恒生指数'),
        ('rt_hkHSCEI', '恒生国企'),
    ],
}

COMMODITIES = [
    ('hf_CL', 'WTI原油'),
    ('hf_GC', 'COMEX黄金'),
    ('fx_susdcny', '美元/人民币'),
]

VALUE_STOCKS = [
    ('sh601398', '工商银行', '银行'),
    ('sh601288', '农业银行', '银行'),
    ('sh600036', '招商银行', '银行'),
    ('sh600519', '贵州茅台', '食品饮料'),
    ('sz000858', '五粮液', '食品饮料'),
    ('sh601088', '中国神华', '煤炭'),
    ('sh600900', '长江电力', '公用事业'),
    ('sh601318', '中国平安', '保险'),
    ('sz000333', '美的集团', '家电'),
    ('sh600276', '恒瑞医药', '医药'),
]

NEWS_URL = 'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=20&page=1'

# ==================== 样式常量 ====================
COLOR_UP = '#e74c3c'
COLOR_DOWN = '#27ae60'
COLOR_GRAY = '#95a5a6'
BG_MAIN = '#f0f2f5'
CARD_BG = '#ffffff'
TITLE_RED = '#c0392b'
TITLE_GREEN = '#1e8449'
ACCENT_BLUE = '#2980b9'
ACCENT_ORANGE = '#e67e22'
ACCENT_PURPLE = '#8e44ad'

# ==================== 数据抓取 ====================

def fetch_sina_data(symbols):
    if not symbols:
        return {}
    url = SINA_URL.format(','.join(symbols))
    try:
        r = requests.get(url, timeout=15, headers=SINA_HEADERS)
        r.encoding = 'gbk'
        results = {}
        for line in r.text.strip().split('\n'):
            m = re.match(r'var hq_str_(\S+?)="(.*)"', line.strip())
            if not m:
                continue
            sym = m.group(1)
            data_str = m.group(2)
            if data_str:
                results[sym] = data_str.split(',')
        return results
    except Exception as e:
        print(f'[新浪] 抓取失败: {e}')
        return {}


def parse_index(parts, prefix):
    if not parts or len(parts) < 4:
        return None
    try:
        if prefix in ('sh', 'sz'):
            name = parts[0]
            price = float(parts[1]) if parts[1] else 0
            change = float(parts[2]) if parts[2] else 0
            change_pct = float(parts[3]) if parts[3] else 0
            amount = float(parts[5]) if len(parts) > 5 and parts[5] else 0
            return {'name': name, 'price': price, 'change': change, 'change_pct': change_pct, 'amount': amount}
        elif prefix == 'gb':
            name = parts[0]
            price = float(parts[1]) if parts[1] else 0
            change_pct = float(parts[2]) if parts[2] else 0
            change = float(parts[4]) if len(parts) > 4 and parts[4] else 0
            return {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}
        elif prefix == 'rt_hk':
            name = parts[1] if len(parts) > 1 else parts[0]
            price = float(parts[2]) if parts[2] else 0
            change = float(parts[3]) if parts[3] else 0
            change_pct = float(parts[4]) if parts[4] else 0
            return {'name': name, 'price': price, 'change': change, 'change_pct': change_pct}
    except Exception as e:
        print(f'解析失败: {e}')
    return None


def parse_stock(parts):
    if not parts or len(parts) < 4:
        return None
    try:
        name = parts[0]
        prev_close = float(parts[2]) if parts[2] else 0
        price = float(parts[3]) if parts[3] else 0
        high = float(parts[4]) if len(parts) > 4 and parts[4] else 0
        low = float(parts[5]) if len(parts) > 5 and parts[5] else 0
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {'name': name, 'price': price, 'change': change, 'change_pct': change_pct, 'high': high, 'low': low}
    except Exception as e:
        print(f'个股解析失败: {e}')
    return None


def parse_commodity(parts, sym):
    if not parts or len(parts) < 2:
        return None
    try:
        if sym.startswith('hf_'):
            price = float(parts[0]) if parts[0] else 0
            change_pct = float(parts[1]) if parts[1] else 0
            return {'price': price, 'change_pct': change_pct}
        elif sym.startswith('fx_'):
            price = float(parts[0]) if parts[0] else 0
            change_pct = float(parts[7]) if len(parts) > 7 and parts[7] else 0
            return {'price': price, 'change_pct': change_pct}
    except:
        pass
    return None


def fetch_news():
    try:
        r = requests.get(NEWS_URL, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        data = r.json()
        news_list = data.get('result', {}).get('data', [])
        return [n.get('title', '').strip() for n in news_list if n.get('title')][:8]
    except Exception as e:
        print(f'[新闻] 抓取失败: {e}')
        return []
      

# ==================== 样式辅助函数 ====================

def color_for(pct):
    if pct > 0:
        return COLOR_UP
    elif pct < 0:
        return COLOR_DOWN
    return COLOR_GRAY


def arrow_for(pct):
    if pct > 0:
        return '▲'
    elif pct < 0:
        return '▼'
    return '—'


def fmt_price_change(data):
    if not data:
        return f'<span style="color:{COLOR_GRAY}">--</span>'
    pct = data.get('change_pct', 0)
    color = color_for(pct)
    arrow = arrow_for(pct)
    price = data.get('price', 0)
    return f'<span style="color:{color};font-weight:700;font-size:15px;">{price:,.2f}</span> <span style="color:{color};font-weight:600;font-size:13px;">{arrow}{abs(pct):.2f}%</span>'


def card_start(title, icon, accent_color):
    return f'''
    <div style="background:{CARD_BG};border-radius:14px;margin:16px 0;box-shadow:0 2px 12px rgba(0,0,0,0.06);overflow:hidden;">
      <div style="background:linear-gradient(135deg,{accent_color} 0%,{accent_color}dd 100%);padding:14px 18px;display:flex;align-items:center;">
        <span style="font-size:20px;margin-right:10px;">{icon}</span>
        <span style="color:#fff;font-size:17px;font-weight:700;letter-spacing:0.5px;">{title}</span>
      </div>
      <div style="padding:16px 18px;">
    '''


def card_end():
    return '</div></div>'


# ==================== 报告生成 ====================

def get_beijing_time():
    return datetime.now(timezone.utc) + timedelta(hours=8)


def is_morning_session():
    return get_beijing_time().hour < 12


def generate_header(title, subtitle, accent_color):
    bj = get_beijing_time()
    date_str = bj.strftime('%Y年%m月%d日')
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekdays[bj.weekday()]
    time_str = bj.strftime('%H:%M')
    return f'''
    <div style="background:linear-gradient(135deg,{accent_color} 0%,{accent_color}cc 50%,{accent_color}99 100%);padding:28px 20px 24px;text-align:center;border-radius:0 0 20px 20px;position:relative;overflow:hidden;">
      <div style="position:absolute;top:-30px;right:-20px;font-size:80px;opacity:0.08;">📈</div>
      <div style="position:absolute;bottom:-20px;left:-10px;font-size:60px;opacity:0.08;">💰</div>
      <h1 style="margin:0;color:#fff;font-size:26px;font-weight:800;letter-spacing:2px;text-shadow:0 2px 8px rgba(0,0,0,0.15);">{title}</h1>
      <p style="margin:10px 0 0;color:#ffffffdd;font-size:14px;font-weight:500;">{date_str} {weekday} · {time_str} 更新</p>
      <p style="margin:6px 0 0;color:#ffffffaa;font-size:12px;">{subtitle}</p>
    </div>
    '''
      


def generate_index_grid(indices_data, title, icon, accent):
    html = card_start(title, icon, accent)
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
    for sym, name in indices_data:
        prefix = sym.split('_')[0] if '_' in sym else sym[:2]
        data = parse_index(fetch_sina_data([sym]).get(sym, []), prefix)
        if data:
            pct = data['change_pct']
            color = color_for(pct)
            arrow = arrow_for(pct)
            bg_color = '#fdf2f2' if pct > 0 else ('#f0faf4' if pct < 0 else '#f5f5f5')
            html += f'''
            <div style="background:{bg_color};border-radius:10px;padding:14px 12px;text-align:center;border:1px solid {color}22;">
              <div style="font-size:13px;color:#666;font-weight:600;margin-bottom:6px;">{name}</div>
              <div style="font-size:18px;font-weight:800;color:{color};">{data["price"]:,.2f}</div>
              <div style="font-size:13px;font-weight:700;color:{color};margin-top:4px;">{arrow}{abs(pct):.2f}%</div>
            </div>
            '''
        else:
            html += f'''
            <div style="background:#f9f9f9;border-radius:10px;padding:14px 12px;text-align:center;border:1px solid #eee;">
              <div style="font-size:13px;color:#999;font-weight:600;margin-bottom:6px;">{name}</div>
              <div style="font-size:18px;font-weight:800;color:#ccc;">--</div>
              <div style="font-size:13px;color:#ccc;margin-top:4px;">休市</div>
            </div>
            '''
    html += '</div>' + card_end()
    return html


def generate_commodity_row():
    html = card_start('大宗商品 & 汇率', '🛢️', ACCENT_ORANGE)
    html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">'
    all_data = fetch_sina_data([c[0] for c in COMMODITIES])
    for sym, name in COMMODITIES:
        data = parse_commodity(all_data.get(sym, []), sym)
        if data:
            pct = data['change_pct']
            color = color_for(pct)
            arrow = arrow_for(pct)
            html += f'''
            <div style="text-align:center;padding:10px 4px;background:#fafafa;border-radius:8px;">
              <div style="font-size:11px;color:#888;font-weight:600;">{name}</div>
              <div style="font-size:15px;font-weight:800;color:{color};margin-top:4px;">{data["price"]:,.2f}</div>
              <div style="font-size:11px;color:{color};font-weight:600;">{arrow}{abs(pct):.2f}%</div>
            </div>
            '''
        else:
            html += f'''
            <div style="text-align:center;padding:10px 4px;background:#fafafa;border-radius:8px;">
              <div style="font-size:11px;color:#888;font-weight:600;">{name}</div>
              <div style="font-size:15px;color:#ccc;margin-top:4px;">--</div>
            </div>
            '''
    html += '</div>' + card_end()
    return html


def generate_news_card():
    news = fetch_news()
    html = card_start('财经要闻', '📰', ACCENT_BLUE)
    if news:
        for i, title in enumerate(news):
            html += f'''
            <div style="display:flex;align-items:flex-start;padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="background:{ACCENT_BLUE};color:#fff;font-size:11px;font-weight:700;width:22px;height:22px;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-right:12px;margin-top:1px;">{i+1}</span>
              <span style="font-size:14px;color:#444;line-height:1.6;flex:1;">{title}</span>
            </div>
            '''
    else:
        html += '<div style="text-align:center;color:#999;padding:20px;">暂无新闻数据</div>'
    html += card_end()
    return html
  


def generate_value_stocks_table():
    html = card_start('价值股观察池', '💎', ACCENT_PURPLE)
    html += '<p style="font-size:12px;color:#888;margin:0 0 12px;">低估值 · 高ROE · 高股息 · 行业龙头，仅供长期投资参考</p>'
    html += '''
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#f8f9fa;">
          <th style="padding:10px 6px;text-align:left;color:#666;font-weight:700;border-bottom:2px solid #e0e0e0;">股票</th>
          <th style="padding:10px 6px;text-align:left;color:#666;font-weight:700;border-bottom:2px solid #e0e0e0;">行业</th>
          <th style="padding:10px 6px;text-align:right;color:#666;font-weight:700;border-bottom:2px solid #e0e0e0;">现价</th>
          <th style="padding:10px 6px;text-align:right;color:#666;font-weight:700;border-bottom:2px solid #e0e0e0;">涨跌幅</th>
        </tr>
      </thead>
      <tbody>
    '''
    all_data = fetch_sina_data([s[0] for s in VALUE_STOCKS])
    for i, (sym, name, industry) in enumerate(VALUE_STOCKS):
        sd = parse_stock(all_data.get(sym, []))
        bg = '#fafbfc' if i % 2 == 0 else '#ffffff'
        if sd:
            pct = sd['change_pct']
            color = color_for(pct)
            arrow = arrow_for(pct)
            html += f'''
            <tr style="background:{bg};">
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;color:#333;font-weight:600;">{name}</td>
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;color:#999;font-size:12px;">{industry}</td>
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;text-align:right;color:#333;font-weight:600;">{sd["price"]:.2f}</td>
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;text-align:right;color:{color};font-weight:800;">{arrow}{abs(pct):.2f}%</td>
            </tr>
            '''
        else:
            html += f'''
            <tr style="background:{bg};">
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;color:#333;font-weight:600;">{name}</td>
              <td style="padding:10px 6px;border-bottom:1px solid #f0f0f0;color:#999;font-size:12px;">{industry}</td>
              <td colspan="2" style="padding:10px 6px;border-bottom:1px solid #f0f0f0;text-align:right;color:#ccc;">--</td>
            </tr>
            '''
    html += '</tbody></table></div>' + card_end()
    return html


def generate_tip_card(title, icon, accent, tips):
    html = card_start(title, icon, accent)
    html += '<ul style="margin:0;padding-left:0;list-style:none;">'
    for tip in tips:
        html += f'''
        <li style="display:flex;align-items:flex-start;padding:8px 0;font-size:14px;color:#555;line-height:1.7;">
          <span style="color:{accent};font-weight:800;margin-right:8px;flex-shrink:0;">✓</span>
          <span>{tip}</span>
        </li>
        '''
    html += '</ul>' + card_end()
    return html


def generate_footer():
    return '''
    <div style="background:linear-gradient(135deg,#2c3e50 0%,#34495e 100%);padding:20px;text-align:center;border-radius:14px;margin:16px 0;">
      <p style="margin:0;color:#ecf0f1;font-size:13px;line-height:1.8;">
        ⚠️ 本内容由程序自动生成，数据来源新浪财经<br>
        仅供学习参考，不构成任何投资建议<br>
        <span style="color:#95a5a6;font-size:12px;">股市有风险，投资需谨慎</span>
      </p>
    </div>
    '''
  


def generate_morning_report():
    bj = get_beijing_time()
    date_str = bj.strftime('%Y年%m月%d日')
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekdays[bj.weekday()]

    html = f'<div style="background:{BG_MAIN};padding:0 0 20px;max-width:100%;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'Helvetica Neue\',Arial,sans-serif;">'
    html += generate_header('早盘前瞻', '隔夜市场扫描 · 今日投资关注', TITLE_RED)

    html += generate_index_grid(INDICES['美股'], '隔夜美股', '🇺🇸', ACCENT_BLUE)
    html += generate_index_grid(INDICES['港股'], '港股表现', '🇭🇰', '#16a085')
    html += generate_commodity_row()
    html += generate_news_card()
    html += generate_value_stocks_table()
    html += generate_tip_card('今日关注', '📅', ACCENT_ORANGE, [
        '关注隔夜美股走势对A股开盘的影响',
        '查看交易软件确认今日新股申购',
        '关注是否有重要经济数据发布',
        '价值投资原则：不追涨杀跌，逢低布局优质标的',
    ])
    html += generate_footer()
    html += '</div>'

    title = f'📊 早盘前瞻 - {date_str} {weekday}'
    return html, title


def generate_evening_report():
    bj = get_beijing_time()
    date_str = bj.strftime('%Y年%m月%d日')
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday = weekdays[bj.weekday()]

    html = f'<div style="background:{BG_MAIN};padding:0 0 20px;max-width:100%;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,\'Helvetica Neue\',Arial,sans-serif;">'
    html += generate_header('收盘总结', 'A股全天回顾 · 次日投资展望', TITLE_GREEN)

    a_symbols = [s[0] for s in INDICES['A股']]
    a_data = fetch_sina_data(a_symbols)
    total_amount = 0
    for sym, name in INDICES['A股'][:2]:
        idx = parse_index(a_data.get(sym, []), sym[:2])
        if idx and idx.get('amount'):
            total_amount += idx['amount']

    html += card_start('A股收盘', '🇨🇳', TITLE_GREEN)
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
    for sym, name in INDICES['A股']:
        data = parse_index(a_data.get(sym, []), sym[:2])
        if data:
            pct = data['change_pct']
            color = color_for(pct)
            arrow = arrow_for(pct)
            bg_color = '#fdf2f2' if pct > 0 else ('#f0faf4' if pct < 0 else '#f5f5f5')
            html += f'''
            <div style="background:{bg_color};border-radius:10px;padding:14px 12px;text-align:center;border:1px solid {color}22;">
              <div style="font-size:13px;color:#666;font-weight:600;margin-bottom:6px;">{name}</div>
              <div style="font-size:18px;font-weight:800;color:{color};">{data["price"]:,.2f}</div>
              <div style="font-size:13px;font-weight:700;color:{color};margin-top:4px;">{arrow}{abs(pct):.2f}%</div>
            </div>
            '''
    html += '</div>'
    if total_amount > 0:
        html += f'<div style="text-align:center;margin-top:14px;padding:10px;background:#f8f9fa;border-radius:8px;font-size:13px;color:#666;">💰 沪深两市成交额约 <span style="font-weight:800;color:{TITLE_GREEN};">{total_amount/100000000:.0f}</span> 亿元</div>'
    html += card_end()

    html += generate_value_stocks_table()
    html += generate_news_card()
    html += generate_tip_card('次日展望', '🔮', TITLE_GREEN, [
        '关注晚间美股开盘走势及中概股表现',
        '关注是否有重要政策文件夜间发布',
        '优质标的逢回调可分批建仓，不追高',
        '保持合理仓位，不满仓不恐慌',
        '长期持有基本面优秀公司，忽略短期波动',
    ])
    html += generate_tip_card('理财小贴士', '💰', ACCENT_BLUE, [
        '股票类资产不超过总资产60%，分散投资降低风险',
        '保留3-6个月生活费作为应急资金（货币基金）',
        '指数基金定投是普通人分享经济增长的最佳方式',
        '不把所有资金投入单一标的，资产配置是王道',
    ])
    html += generate_footer()
    html += '</div>'

    title = f'📈 收盘总结 - {date_str} {weekday}'
    return html, title


# ==================== 推送 ====================

def push_to_wechat(html_content, title):
    if not PUSHPLUS_TOKEN:
        print('⚠️ 未设置 PUSHPLUS_TOKEN 环境变量')
        return False
    payload = {
        'token': PUSHPLUS_TOKEN,
        'title': title,
        'content': html_content,
        'template': 'html',
    }
    try:
        r = requests.post(PUSHPLUS_URL, json=payload, timeout=30)
        res = r.json()
        if res.get('code') == 200:
            print(f'✅ 推送成功: {title}')
            return True
        else:
            print(f'❌ 推送失败: {res}')
            return False
    except Exception as e:
        print(f'❌ 推送异常: {e}')
        return False


def main():
    print(f'=== 每日股票理财报告 ===')
    print(f'北京时间: {get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")}')

    if is_morning_session():
        print('模式: 早盘前瞻')
        html, title = generate_morning_report()
    else:
        print('模式: 收盘总结')
        html, title = generate_evening_report()

    with open('report.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('报告已保存到 report.html')

    success = push_to_wechat(html, title)
    if not success:
        print('推送失败，请检查 PUSHPLUS_TOKEN 配置')
        exit(1)


if __name__ == '__main__':
    main()
          






