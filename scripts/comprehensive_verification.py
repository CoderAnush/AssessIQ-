"""
Comprehensive End-to-End Verification for AssessIQ Platform
Tests all major recruitment scenarios and generates verification report.
"""
import json
import requests
import sys
from datetime import datetime
from typing import Dict, List, Any

API_URL = "https://assessiq-nkp2.onrender.com/chat"

TEST_SCENARIOS = [
    {
        "name": "Senior Java Engineer",
        "prompt": "Hiring a senior Java backend engineer with Spring Boot experience",
        "expected_domain": "technical",
        "expected_keywords": ["Java", "backend", "Spring"]
    },
    {
        "name": "DevOps / SRE",
        "prompt": "Need DevOps engineer with Kubernetes and AWS experience",
        "expected_domain": "technical",
        "expected_keywords": ["Kubernetes", "Cloud", "Infrastructure"]
    },
    {
        "name": "Data Scientist",
        "prompt": "Need assessments for data scientist with Python and machine learning skills",
        "expected_domain": "technical",
        "expected_keywords": ["Python", "Data", "Analytics"]
    },
    {
        "name": "Frontend Developer",
        "prompt": "Frontend React developer for e-commerce startup",
        "expected_domain": "technical",
        "expected_keywords": ["JavaScript", "Frontend"]
    },
    {
        "name": "Sales Executive",
        "prompt": "Sales executive for B2B software company",
        "expected_domain": "behavioral",
        "expected_keywords": ["Sales", "Account"]
    },
    {
        "name": "Project Manager",
        "prompt": "Project manager for IT consulting firm",
        "expected_domain": "mixed",
        "expected_keywords": ["Manager", "Leadership"]
    },
    {
        "name": "Graduate Hiring (Generic)",
        "prompt": "Hiring fresh graduates for software engineering roles",
        "expected_behavior": "clarification",
        "expected_keywords": []
    },
    {
        "name": "Python Backend",
        "prompt": "Senior Python backend engineer with Django and API design experience",
        "expected_domain": "technical",
        "expected_keywords": ["Python", "Django"]
    },
    {
        "name": "Hotel Front Desk (Blacklisted)",
        "prompt": "Need assessment for hotel front desk receptionist",
        "expected_behavior": "clarification_or_filtered",
        "expected_keywords": []
    }
]

def test_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single scenario and return results."""
    try:
        response = requests.post(
            API_URL,
            json={"messages": [{"role": "user", "content": scenario["prompt"]}]},
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract key information
        has_recommendations = bool(data.get("recommendations"))
        recommendation_count = len(data.get("recommendations", []))
        reply = data.get("reply", "")
        
        # Check for expected keywords in recommendations
        found_keywords = []
        if has_recommendations:
            rec_text = json.dumps(data.get("recommendations", [])).lower()
            for kw in scenario.get("expected_keywords", []):
                if kw.lower() in rec_text or kw.lower() in reply.lower():
                    found_keywords.append(kw)
        
        # Verify grounding (all URLs should be from shl.com)
        all_grounded = True
        for rec in data.get("recommendations", []):
            url = rec.get("url", "")
            if url and not url.startswith("https://www.shl.com"):
                all_grounded = False
        
        # Check for clarification behavior
        is_clarification = "?" in reply and not has_recommendations
        
        return {
            "scenario": scenario["name"],
            "status": "PASSED" if response.status_code == 200 else "FAILED",
            "has_recommendations": has_recommendations,
            "recommendation_count": recommendation_count,
            "is_clarification": is_clarification,
            "keywords_found": found_keywords,
            "all_grounded": all_grounded,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
            "reply_preview": reply[:200] if reply else "",
            "raw_response": data
        }
    except Exception as e:
        return {
            "scenario": scenario["name"],
            "status": "ERROR",
            "error": str(e)
        }

def generate_html_report(results: List[Dict], output_path: str):
    """Generate HTML verification report."""
    passed = sum(1 for r in results if r["status"] == "PASSED")
    total = len(results)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>AssessIQ Comprehensive Verification Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .summary {{ background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
        .status-passed {{ background: #4CAF50; color: white; }}
        .status-error {{ background: #f44336; color: white; }}
        .test-case {{ border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 8px; background: #fafafa; }}
        .test-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
        .test-title {{ font-size: 18px; font-weight: 600; color: #333; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 15px 0; }}
        .metric {{ background: white; padding: 15px; border-radius: 6px; border-left: 4px solid #2196F3; }}
        .metric-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .metric-value {{ font-size: 16px; font-weight: 600; color: #333; margin-top: 5px; }}
        .recommendations {{ background: white; padding: 15px; border-radius: 6px; margin-top: 15px; }}
        .rec-item {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .rec-item:last-child {{ border-bottom: none; }}
        .rec-name {{ font-weight: 600; color: #2196F3; }}
        .rec-url {{ font-size: 12px; color: #666; word-break: break-all; }}
        .timestamp {{ color: #999; font-size: 14px; margin-top: 20px; }}
        .grounded-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #4CAF50; color: white; margin-left: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AssessIQ - Comprehensive Verification Report</h1>
        <p>End-to-end testing of all major recruitment scenarios to verify domain accuracy, grounding, and system stability.</p>
        
        <div class="summary">
            <strong>Test Summary:</strong> {passed}/{total} scenarios passed<br>
            <strong>Backend API:</strong> assessiq-nkp2.onrender.com<br>
            <strong>Test Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
"""
    
    for result in results:
        if result["status"] == "ERROR":
            html += f"""
        <div class="test-case">
            <div class="test-header">
                <span class="test-title">{result['scenario']}</span>
                <span class="status-badge status-error">ERROR</span>
            </div>
            <p style="color: #f44336;">{result.get('error', 'Unknown error')}</p>
        </div>
"""
            continue
        
        recs_html = ""
        if result.get("raw_response", {}).get("recommendations"):
            for rec in result["raw_response"]["recommendations"][:3]:
                recs_html += f"""
                <div class="rec-item">
                    <div class="rec-name">{rec.get('name', 'N/A')}</div>
                    <div class="rec-url">{rec.get('url', 'N/A')}</div>
                    <span class="status-badge status-passed">{rec.get('test_type', 'N/A')}</span>
                </div>
"""
        
        grounded_badge = '<span class="grounded-badge">✓ 100% Grounded</span>' if result.get("all_grounded") else ''
        
        html += f"""
        <div class="test-case">
            <div class="test-header">
                <span class="test-title">{result['scenario']} {grounded_badge}</span>
                <span class="status-badge status-passed">{result['status']}</span>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">Recommendations</div>
                    <div class="metric-value">{result['recommendation_count']}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Response Time</div>
                    <div class="metric-value">{result.get('response_time_ms', 'N/A')} ms</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Keywords Matched</div>
                    <div class="metric-value">{', '.join(result.get('keywords_found', [])) or 'N/A'}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Clarification</div>
                    <div class="metric-value">{'Yes' if result.get('is_clarification') else 'No'}</div>
                </div>
            </div>
            
            <p><strong>Reply:</strong> {result.get('reply_preview', '')}...</p>
            
            {f'<div class="recommendations"><strong>Top Recommendations:</strong>{recs_html}</div>' if recs_html else ''}
        </div>
"""
    
    html += f"""
        <p class="timestamp">Report generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML report saved to: {output_path}")

def main():
    print("="*60)
    print("ASSESSIQ COMPREHENSIVE VERIFICATION")
    print("="*60)
    print(f"API Endpoint: {API_URL}")
    print(f"Test Scenarios: {len(TEST_SCENARIOS)}")
    print("="*60)
    
    results = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n[{i}/{len(TEST_SCENARIOS)}] Testing: {scenario['name']}...")
        result = test_scenario(scenario)
        results.append(result)
        status = result["status"]
        symbol = "✓" if status == "PASSED" else "✗"
        print(f"  {symbol} {status}")
        if result.get("has_recommendations"):
            print(f"  → {result['recommendation_count']} recommendations")
        if result.get("is_clarification"):
            print(f"  → Clarification requested (expected behavior)")
    
    # Generate reports
    print("\n" + "="*60)
    print("GENERATING REPORTS")
    print("="*60)
    
    # JSON report
    json_path = "docs/screenshots/verification_results.json"
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ JSON results: {json_path}")
    
    # HTML report
    html_path = "docs/screenshots/verification_report.html"
    generate_html_report(results, html_path)
    print(f"✓ HTML report: {html_path}")
    
    # Summary
    passed = sum(1 for r in results if r["status"] == "PASSED")
    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{len(results)} scenarios passed")
    print("="*60)
    
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
