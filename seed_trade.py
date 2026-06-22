"""给 TRADE 注入测试股票数据。跑 TRADE 测试前执行一遍。"""
import httpx

TRADE = "http://localhost:8001"

STOCKS = [
    {"stock_code": "600000", "stock_name": "浦发银行", "stock_type": "NORMAL", "previous_close_price": "12.50"},
    {"stock_code": "000001", "stock_name": "平安银行", "stock_type": "NORMAL", "previous_close_price": "10.80"},
    {"stock_code": "600036", "stock_name": "招商银行", "stock_type": "NORMAL", "previous_close_price": "38.20"},
    {"stock_code": "600519", "stock_name": "贵州茅台", "stock_type": "NORMAL", "previous_close_price": "1680.00"},
]

client = httpx.Client(timeout=10)

for s in STOCKS:
    resp = client.post(f"{TRADE}/api/v1/trade/stocks", json=s)
    body = resp.json()
    status = "OK" if body.get("success") else f"SKIP ({body.get('message','')[:40]})"
    print(f"  {s['stock_code']} {s['stock_name']}: {status}")

client.close()
print(f"\n{len(STOCKS)} 只测试股票已就绪")
