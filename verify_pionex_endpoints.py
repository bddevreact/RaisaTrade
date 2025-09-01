#!/usr/bin/env python3
"""
Script to verify Pionex API endpoints and identify working ones
"""

import requests
import time
import json

# Base URL
BASE_URL = "https://api.pionex.com"

# Test endpoints (both authenticated and non-authenticated)
ENDPOINTS_TO_TEST = [
    # Market Data Endpoints (No Auth Required)
    {'method': 'GET', 'endpoint': '/api/v1/market/tickers', 'auth': False},
    {'method': 'GET', 'endpoint': '/api/v1/market/klines', 'auth': False, 'params': {'symbol': 'BTC_USDT', 'interval': '1H', 'limit': 10}},
    {'method': 'GET', 'endpoint': '/api/v1/market/depth', 'auth': False, 'params': {'symbol': 'BTC_USDT', 'limit': 10}},
    {'method': 'GET', 'endpoint': '/api/v1/market/trades', 'auth': False, 'params': {'symbol': 'BTC_USDT', 'limit': 10}},
    
    # Account Endpoints (Auth Required)
    {'method': 'GET', 'endpoint': '/api/v1/account/balance', 'auth': True},
    {'method': 'GET', 'endpoint': '/api/v1/account/balances', 'auth': True},
    {'method': 'GET', 'endpoint': '/api/v1/account/assets', 'auth': True},
    {'method': 'GET', 'endpoint': '/api/v1/account/account', 'auth': True},
    
    # Order Endpoints (Auth Required)
    {'method': 'GET', 'endpoint': '/api/v1/trade/openOrders', 'auth': True},
    {'method': 'GET', 'endpoint': '/api/v1/trade/allOrders', 'auth': True},
    {'method': 'GET', 'endpoint': '/api/v1/trade/fills', 'auth': True},
    
    # Grid Bot Endpoints (Auth Required)
    {'method': 'GET', 'endpoint': '/api/v1/grid/order/list', 'auth': True},
]

def test_endpoint(method, endpoint, auth=False, params=None):
    """Test a single endpoint"""
    url = f"{BASE_URL}{endpoint}"
    
    if params is None:
        params = {}
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'PionexTradingBot/1.0'
    }
    
    try:
        if method == 'GET':
            response = requests.get(url, params=params, headers=headers, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=params, headers=headers, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, params=params, headers=headers, timeout=10)
        else:
            return {'status': 'error', 'message': f'Unsupported method: {method}'}
        
        return {
            'status': 'success',
            'status_code': response.status_code,
            'response': response.text[:200] + '...' if len(response.text) > 200 else response.text
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

def verify_endpoints():
    """Verify all Pionex API endpoints"""
    
    print("🔧 Verifying Pionex API Endpoints...")
    print("=" * 60)
    
    results = {
        'working': [],
        'not_working': [],
        'auth_required': []
    }
    
    for i, endpoint_info in enumerate(ENDPOINTS_TO_TEST, 1):
        method = endpoint_info['method']
        endpoint = endpoint_info['endpoint']
        auth = endpoint_info.get('auth', False)
        params = endpoint_info.get('params', {})
        
        print(f"\n{i:2d}. Testing {method} {endpoint}")
        print(f"    Auth Required: {auth}")
        if params:
            print(f"    Params: {params}")
        
        result = test_endpoint(method, endpoint, auth, params)
        
        if result['status'] == 'success':
            if result['status_code'] == 200:
                print(f"    ✅ Working (200)")
                results['working'].append({
                    'method': method,
                    'endpoint': endpoint,
                    'auth': auth,
                    'params': params
                })
            elif result['status_code'] == 401:
                print(f"    🔐 Auth Required (401)")
                results['auth_required'].append({
                    'method': method,
                    'endpoint': endpoint,
                    'auth': auth,
                    'params': params
                })
            else:
                print(f"    ❌ Not Working ({result['status_code']})")
                print(f"    Response: {result['response']}")
                results['not_working'].append({
                    'method': method,
                    'endpoint': endpoint,
                    'auth': auth,
                    'params': params,
                    'status_code': result['status_code'],
                    'response': result['response']
                })
        else:
            print(f"    ❌ Error: {result['message']}")
            results['not_working'].append({
                'method': method,
                'endpoint': endpoint,
                'auth': auth,
                'params': params,
                'error': result['message']
            })
        
        # Rate limiting
        time.sleep(0.1)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    print(f"\n✅ Working Endpoints ({len(results['working'])}):")
    for endpoint in results['working']:
        print(f"  - {endpoint['method']} {endpoint['endpoint']}")
    
    print(f"\n🔐 Auth Required Endpoints ({len(results['auth_required'])}):")
    for endpoint in results['auth_required']:
        print(f"  - {endpoint['method']} {endpoint['endpoint']}")
    
    print(f"\n❌ Not Working Endpoints ({len(results['not_working'])}):")
    for endpoint in results['not_working']:
        print(f"  - {endpoint['method']} {endpoint['endpoint']}")
        if 'status_code' in endpoint:
            print(f"    Status: {endpoint['status_code']}")
        if 'error' in endpoint:
            print(f"    Error: {endpoint['error']}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print(f"1. Use working endpoints for market data")
    print(f"2. Test auth endpoints with valid API credentials")
    print(f"3. Check Pionex API documentation for correct endpoints")
    print(f"4. Verify API base URL: {BASE_URL}")
    
    return results

if __name__ == "__main__":
    verify_endpoints() 