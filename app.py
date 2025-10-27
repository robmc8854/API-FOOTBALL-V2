#!/usr/bin/env python3
"""
API-Football Odds Diagnostic Tool
This will show us exactly what the API returns
"""

from flask import Flask, render_template, jsonify
import requests
import os
from datetime import datetime, timezone

app = Flask(__name__)

API_KEY = os.environ.get('API_SPORTS_KEY', '')
BASE_URL = "https://v3.football.api-sports.io"

headers = {
    'x-rapidapi-key': API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>API-Football Diagnostic Tool</title>
        <style>
            body { font-family: Arial; padding: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            h1 { color: #333; }
            .test-btn { 
                background: #667eea; 
                color: white; 
                padding: 15px 30px; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer; 
                font-size: 16px;
                margin: 10px;
            }
            .test-btn:hover { background: #5568d3; }
            pre { background: #f8f8f8; padding: 20px; border-radius: 5px; overflow-x: auto; }
            .error { color: red; }
            .success { color: green; }
            .info { color: blue; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 API-Football Diagnostic Tool</h1>
            <p>This will test your API and show exactly what data it returns.</p>
            
            <h2>Tests:</h2>
            <button class="test-btn" onclick="runTest('/api/test-connection')">1. Test API Connection</button>
            <button class="test-btn" onclick="runTest('/api/test-fixtures')">2. Test Fixtures</button>
            <button class="test-btn" onclick="runTest('/api/test-odds')">3. Test Odds Structure</button>
            
            <h2>Results:</h2>
            <div id="results"></div>
        </div>
        
        <script>
            async function runTest(endpoint) {
                const resultsDiv = document.getElementById('results');
                resultsDiv.innerHTML = '<p class="info">Running test...</p>';
                
                try {
                    const response = await fetch(endpoint);
                    const data = await response.json();
                    resultsDiv.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                } catch (error) {
                    resultsDiv.innerHTML = '<p class="error">Error: ' + error.message + '</p>';
                }
            }
        </script>
    </body>
    </html>
    """

@app.route('/api/test-connection')
def test_connection():
    """Test basic API connection"""
    if not API_KEY:
        return jsonify({
            'success': False,
            'error': 'API_SPORTS_KEY not configured in Railway environment variables'
        })
    
    try:
        response = requests.get(
            f"{BASE_URL}/status",
            headers=headers,
            timeout=30
        )
        
        data = response.json()
        
        if 'response' in data:
            account = data['response']
            return jsonify({
                'success': True,
                'message': 'API connection working!',
                'subscription': account.get('subscription', {}).get('plan', 'Unknown'),
                'requests_today': f"{account.get('requests', {}).get('current', 0)}/{account.get('requests', {}).get('limit_day', 0)}"
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unexpected API response',
                'raw_response': data
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/test-fixtures')
def test_fixtures():
    """Test getting today's fixtures"""
    if not API_KEY:
        return jsonify({'error': 'API_SPORTS_KEY not configured'})
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{BASE_URL}/fixtures",
            headers=headers,
            params={'date': today},
            timeout=30
        )
        
        data = response.json()
        
        if data.get('results', 0) > 0:
            fixtures = data['response']
            
            # Get first 3 fixtures for testing
            sample_fixtures = []
            for fixture in fixtures[:3]:
                sample_fixtures.append({
                    'id': fixture['fixture']['id'],
                    'home': fixture['teams']['home']['name'],
                    'away': fixture['teams']['away']['name'],
                    'league': fixture['league']['name'],
                    'time': fixture['fixture']['date']
                })
            
            return jsonify({
                'success': True,
                'total_fixtures': len(fixtures),
                'sample_fixtures': sample_fixtures,
                'message': 'Use these fixture IDs to test odds'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No fixtures found for today',
                'date': today
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/test-odds')
def test_odds():
    """Test odds endpoint with a real fixture"""
    if not API_KEY:
        return jsonify({'error': 'API_SPORTS_KEY not configured'})
    
    try:
        # First get a fixture ID from today
        today = datetime.now().strftime('%Y-%m-%d')
        
        fixtures_response = requests.get(
            f"{BASE_URL}/fixtures",
            headers=headers,
            params={'date': today},
            timeout=30
        )
        
        fixtures_data = fixtures_response.json()
        
        if fixtures_data.get('results', 0) == 0:
            return jsonify({
                'success': False,
                'error': 'No fixtures found for today to test with'
            })
        
        # Get first fixture
        fixture = fixtures_data['response'][0]
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        
        # Now test odds
        odds_response = requests.get(
            f"{BASE_URL}/odds",
            headers=headers,
            params={'fixture': fixture_id},
            timeout=30
        )
        
        odds_data = odds_response.json()
        
        result = {
            'success': True,
            'fixture_id': fixture_id,
            'match': f"{home_team} vs {away_team}",
            'odds_results': odds_data.get('results', 0),
        }
        
        if odds_data.get('results', 0) > 0:
            odds_response_data = odds_data['response'][0]
            
            bookmakers = odds_response_data.get('bookmakers', [])
            result['bookmakers_count'] = len(bookmakers)
            
            if len(bookmakers) > 0:
                first_bookmaker = bookmakers[0]
                result['first_bookmaker'] = first_bookmaker.get('name')
                result['bookmaker_id'] = first_bookmaker.get('id')
                
                bets = first_bookmaker.get('bets', [])
                result['bet_types_count'] = len(bets)
                
                if len(bets) > 0:
                    # List all bet types
                    result['available_bet_types'] = [
                        {'name': bet.get('name'), 'id': bet.get('id')} 
                        for bet in bets
                    ]
                    
                    # Check for Match Winner
                    match_winner = None
                    for bet in bets:
                        if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                            match_winner = bet
                            break
                    
                    if match_winner:
                        result['match_winner_found'] = True
                        result['match_winner_odds'] = {
                            value.get('value'): value.get('odd')
                            for value in match_winner.get('values', [])
                        }
                    else:
                        result['match_winner_found'] = False
                        result['note'] = 'Match Winner market not found!'
                        result['first_bet_sample'] = bets[0]  # Show what we got instead
                else:
                    result['error'] = 'No bets found in bookmaker data'
            else:
                result['error'] = 'No bookmakers found in odds response'
        else:
            result['error'] = 'No odds data returned from API'
            result['note'] = 'Your subscription may not include odds, or odds are not available for this fixture'
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🔍 Starting Diagnostic Tool on port {port}")
    print(f"API Key configured: {bool(API_KEY)}")
    app.run(host='0.0.0.0', port=port, debug=False)
