#!/usr/bin/env python3
"""
10bet Betting Optimizer - API-Football.com Version
Flask web interface using API-Football from api-football.com
"""

from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import itertools

app = Flask(__name__)

# Configuration - API-Football uses RapidAPI
API_KEY = os.environ.get('API_SPORTS_KEY', '')
BASE_URL = "https://v3.football.api-sports.io"

class BettingAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
    
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request with error handling"""
        try:
            url = f"{self.base_url}/{endpoint}"
            print(f"Making request to: {endpoint} with params: {params}")
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            print(f"Response received: {data.get('results', 0)} results")
            
            return data
        except Exception as e:
            print(f"API Error for {endpoint}: {e}")
            return None
    
    def get_todays_fixtures(self) -> List[Dict]:
        """Get all fixtures for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        print(f"Fetching fixtures for {today}...")
        data = self.make_request('fixtures', params={'date': today})
        
        if not data or 'response' not in data:
            print("No data received from API")
            return []
        
        fixtures = data['response']
        print(f"Total fixtures found: {len(fixtures)}")
        
        # Filter for upcoming fixtures only
        now = datetime.now()
        upcoming = []
        
        for fixture in fixtures:
            try:
                fixture_date = fixture['fixture']['date']
                fixture_time = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
                status = fixture['fixture']['status']['long']
                
                # Only upcoming matches
                if fixture_time > now and status in ['Not Started', 'Time to be defined', 'NS']:
                    upcoming.append(fixture)
            except Exception as e:
                print(f"Error parsing fixture: {e}")
                continue
        
        print(f"Upcoming fixtures: {len(upcoming)}")
        return upcoming
    
    def get_fixture_odds(self, fixture_id: int) -> Optional[List[Dict]]:
        """Get odds for specific fixture"""
        print(f"  Fetching odds for fixture {fixture_id}...")
        data = self.make_request('odds', params={'fixture': fixture_id})
        
        if not data or 'response' not in data:
            print(f"  No odds data received")
            return None
        
        odds_response = data['response']
        print(f"  Found odds from {len(odds_response)} bookmakers")
        
        return odds_response
    
    def get_fixture_predictions(self, fixture_id: int) -> Optional[Dict]:
        """Get predictions for specific fixture"""
        print(f"  Fetching predictions for fixture {fixture_id}...")
        data = self.make_request('predictions', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            print(f"  No predictions available")
            return None
        
        print(f"  Predictions received")
        return data['response'][0]
    
    def find_10bet_odds(self, odds_data: List[Dict]) -> Tuple[float, float, float]:
        """Extract 10bet odds from odds data"""
        if not odds_data:
            return (0.0, 0.0, 0.0)
        
        for bookmaker_data in odds_data:
            bookmaker_name = bookmaker_data.get('bookmaker', {}).get('name', '').lower()
            bookmaker_id = bookmaker_data.get('bookmaker', {}).get('id', 0)
            
            # Look for 10bet (ID is usually 24, but check name too)
            if '10bet' in bookmaker_name or '10 bet' in bookmaker_name or bookmaker_id == 24:
                print(f"  Found 10bet: {bookmaker_data.get('bookmaker', {}).get('name')}")
                
                bets = bookmaker_data.get('bets', [])
                
                for bet in bets:
                    bet_name = bet.get('name', '')
                    # Find Match Winner (1X2) market
                    if bet_name == 'Match Winner' or bet.get('id') == 1:
                        values = bet.get('values', [])
                        home_odds = 0.0
                        draw_odds = 0.0
                        away_odds = 0.0
                        
                        for value in values:
                            odd_value = float(value.get('odd', 0))
                            value_name = value.get('value', '').lower()
                            
                            if value_name == 'home' or value_name == '1':
                                home_odds = odd_value
                            elif value_name == 'draw' or value_name == 'x':
                                draw_odds = odd_value
                            elif value_name == 'away' or value_name == '2':
                                away_odds = odd_value
                        
                        print(f"  10bet odds: Home={home_odds}, Draw={draw_odds}, Away={away_odds}")
                        
                        if home_odds > 0 or draw_odds > 0 or away_odds > 0:
                            return (home_odds, draw_odds, away_odds)
        
        print(f"  No 10bet odds found")
        return (0.0, 0.0, 0.0)
    
    def calculate_market_average(self, odds_data: List[Dict]) -> Tuple[float, float, float]:
        """Calculate average odds across all bookmakers"""
        if not odds_data:
            return (0.0, 0.0, 0.0)
        
        home_odds_list = []
        draw_odds_list = []
        away_odds_list = []
        
        for bookmaker_data in odds_data:
            bets = bookmaker_data.get('bets', [])
            
            for bet in bets:
                if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                    values = bet.get('values', [])
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '').lower()
                        
                        if odd_value > 0:
                            if value_name == 'home' or value_name == '1':
                                home_odds_list.append(odd_value)
                            elif value_name == 'draw' or value_name == 'x':
                                draw_odds_list.append(odd_value)
                            elif value_name == 'away' or value_name == '2':
                                away_odds_list.append(odd_value)
        
        avg_home = sum(home_odds_list) / len(home_odds_list) if home_odds_list else 0.0
        avg_draw = sum(draw_odds_list) / len(draw_odds_list) if draw_odds_list else 0.0
        avg_away = sum(away_odds_list) / len(away_odds_list) if away_odds_list else 0.0
        
        print(f"  Market avg: Home={avg_home:.2f}, Draw={avg_draw:.2f}, Away={avg_away:.2f}")
        
        return (avg_home, avg_draw, avg_away)
    
    def get_prediction_probabilities(self, prediction_data: Optional[Dict]) -> Tuple[float, float, float]:
        """Extract prediction probabilities"""
        if not prediction_data:
            return (0.0, 0.0, 0.0)
        
        try:
            predictions = prediction_data.get('predictions', {})
            percent = predictions.get('percent', {})
            
            home_prob = float(str(percent.get('home', '0')).replace('%', ''))
            draw_prob = float(str(percent.get('draw', '0')).replace('%', ''))
            away_prob = float(str(percent.get('away', '0')).replace('%', ''))
            
            print(f"  Predictions: Home={home_prob}%, Draw={draw_prob}%, Away={away_prob}%")
            
            return (home_prob, draw_prob, away_prob)
        except Exception as e:
            print(f"  Error parsing predictions: {e}")
            return (0.0, 0.0, 0.0)
    
    def analyze_fixture(self, fixture: Dict) -> Optional[Dict]:
        """Analyze a single fixture"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        print(f"\n🔍 Analyzing: {home_team} vs {away_team}")
        
        # Get odds
        odds_data = self.get_fixture_odds(fixture_id)
        
        if not odds_data:
            print(f"  ❌ No odds data available")
            return None
        
        # Get 10bet odds
        home_odds, draw_odds, away_odds = self.find_10bet_odds(odds_data)
        
        if home_odds == 0.0 and draw_odds == 0.0 and away_odds == 0.0:
            print(f"  ❌ No 10bet odds available")
            return None  # No 10bet odds available
        
        # Get market averages
        avg_home, avg_draw, avg_away = self.calculate_market_average(odds_data)
        
        # Get predictions
        prediction_data = self.get_fixture_predictions(fixture_id)
        home_prob, draw_prob, away_prob = self.get_prediction_probabilities(prediction_data)
        
        # Determine best selection based on probabilities
        selections = [
            {
                'type': 'home',
                'name': home_team,
                'prob': home_prob,
                'odds': home_odds,
                'avg_odds': avg_home
            },
            {
                'type': 'draw',
                'name': 'Draw',
                'prob': draw_prob,
                'odds': draw_odds,
                'avg_odds': avg_draw
            },
            {
                'type': 'away',
                'name': away_team,
                'prob': away_prob,
                'odds': away_odds,
                'avg_odds': avg_away
            }
        ]
        
        best_sel = max(selections, key=lambda x: x['prob'])
        
        if best_sel['odds'] == 0:
            print(f"  ❌ Best selection has no odds")
            return None
        
        # Calculate metrics
        odds_value = ((best_sel['odds'] - best_sel['avg_odds']) / best_sel['avg_odds'] * 100) if best_sel['avg_odds'] > 0 else 0
        expected_value = (best_sel['prob'] / 100 * best_sel['odds']) - 1
        confidence = best_sel['prob']
        
        # Boost confidence for value bets
        if odds_value > 5:
            confidence += 10
            print(f"  💎 Value bet bonus: +10% confidence")
        if expected_value > 0.1:
            confidence += 10
            print(f"  💚 Positive EV bonus: +10% confidence")
        
        confidence = min(100, confidence)
        
        # Get advice from predictions
        advice = "No advice available"
        if prediction_data:
            advice = prediction_data.get('predictions', {}).get('advice', 'No advice available')
        
        print(f"  ✅ Recommendation: {best_sel['name']} @ {best_sel['odds']:.2f}")
        print(f"  📊 Confidence: {confidence:.1f}%")
        print(f"  💰 Expected Value: {expected_value:+.2%}")
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': f"{league} ({country})",
            'match_time': match_time,
            'selection': best_sel['name'],
            'selection_type': best_sel['type'],
            'odds': best_sel['odds'],
            'probability': best_sel['prob'],
            'avg_market_odds': best_sel['avg_odds'],
            'odds_value': odds_value,
            'expected_value': expected_value,
            'confidence': confidence,
            'advice': advice,
            'all_odds': {
                'home': home_odds,
                'draw': draw_odds,
                'away': away_odds
            },
            'all_probabilities': {
                'home': home_prob,
                'draw': draw_prob,
                'away': away_prob
            }
        }

# Initialize analyzer
analyzer = None

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = BettingAnalyzer(API_KEY)
    return analyzer

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Check API status"""
    if not API_KEY:
        return jsonify({
            'success': False,
            'error': 'API key not configured. Add API_SPORTS_KEY environment variable in Railway.'
        }), 400
    
    try:
        # Test API connection
        print("Testing API connection...")
        test_data = get_analyzer().make_request('status')
        
        if test_data and 'response' in test_data:
            account = test_data['response']
            
            return jsonify({
                'success': True,
                'api_configured': True,
                'account': {
                    'requests_limit': account.get('requests', {}).get('limit_day', 0),
                    'requests_current': account.get('requests', {}).get('current', 0),
                    'subscription': account.get('subscription', {}).get('plan', 'Unknown')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unable to connect to API-Football'
            }), 500
            
    except Exception as e:
        print(f"Status check error: {e}")
        return jsonify({
            'success': False,
            'error': f'API connection error: {str(e)}'
        }), 500

@app.route('/api/predictions')
def get_predictions():
    """Get all predictions with 10bet odds"""
    if not API_KEY:
        return jsonify({
            'success': False,
            'error': 'API key not configured. Add API_SPORTS_KEY environment variable in Railway.'
        }), 400
    
    try:
        print("\n" + "="*80)
        print("STARTING PREDICTIONS FETCH")
        print("="*80)
        
        fixtures = get_analyzer().get_todays_fixtures()
        
        if not fixtures:
            print("No upcoming fixtures found for today")
            return jsonify({
                'success': True,
                'count': 0,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'predictions': [],
                'total_fixtures': 0,
                'message': 'No upcoming fixtures for today'
            })
        
        print(f"\n📋 Processing {len(fixtures)} fixtures...")
        
        opportunities = []
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\n--- Fixture {i}/{len(fixtures)} ---")
            
            analysis = get_analyzer().analyze_fixture(fixture)
            
            if analysis:
                opportunities.append(analysis)
            
            # Small delay to avoid rate limiting
            if i < len(fixtures):
                import time
                time.sleep(0.5)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        print("\n" + "="*80)
        print(f"RESULTS: Found {len(opportunities)} opportunities with 10bet odds")
        print("="*80)
        
        return jsonify({
            'success': True,
            'count': len(opportunities),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'predictions': opportunities,
            'total_fixtures': len(fixtures)
        })
    
    except Exception as e:
        print(f"\n❌ ERROR in get_predictions: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/accumulators')
def get_accumulators():
    """Generate accumulator bets"""
    if not API_KEY:
        return jsonify({
            'success': False,
            'error': 'API key not configured'
        }), 400
    
    try:
        stake = float(request.args.get('stake', 10.0))
        max_legs = int(request.args.get('max_legs', 3))
        
        print(f"Generating accumulators with stake={stake}, max_legs={max_legs}")
        
        fixtures = get_analyzer().get_todays_fixtures()
        opportunities = []
        
        for fixture in fixtures:
            analysis = get_analyzer().analyze_fixture(fixture)
            if analysis and analysis['confidence'] >= 60:
                opportunities.append(analysis)
        
        print(f"Found {len(opportunities)} high-confidence opportunities")
        
        if len(opportunities) < 2:
            return jsonify({
                'success': True,
                'count': 0,
                'accumulators': [],
                'message': 'Not enough high-confidence bets for accumulators'
            })
        
        # Create accumulators
        accumulators = []
        
        for num_legs in range(2, min(max_legs + 1, len(opportunities) + 1)):
            for combo in itertools.combinations(opportunities, num_legs):
                combined_odds = 1.0
                total_conf = 0.0
                
                for opp in combo:
                    combined_odds *= opp['odds']
                    total_conf += opp['confidence']
                
                avg_conf = total_conf / num_legs
                conf_score = (avg_conf / 100) ** num_legs * 100
                
                potential_return = stake * combined_odds
                
                if avg_conf >= 75 and num_legs <= 2:
                    risk = 'LOW'
                elif avg_conf >= 65 and num_legs <= 3:
                    risk = 'MEDIUM'
                else:
                    risk = 'HIGH'
                
                accumulators.append({
                    'legs': num_legs,
                    'selections': [
                        {
                            'match': f"{o['home_team']} vs {o['away_team']}",
                            'selection': o['selection'],
                            'odds': o['odds'],
                            'confidence': o['confidence']
                        }
                        for o in combo
                    ],
                    'combined_odds': round(combined_odds, 2),
                    'average_confidence': round(avg_conf, 1),
                    'confidence_score': round(conf_score, 1),
                    'stake': stake,
                    'potential_return': round(potential_return, 2),
                    'potential_profit': round(potential_return - stake, 2),
                    'risk_level': risk
                })
        
        # Sort by confidence score
        accumulators.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        print(f"Generated {len(accumulators)} accumulator combinations")
        
        return jsonify({
            'success': True,
            'count': len(accumulators),
            'accumulators': accumulators[:20]  # Top 20
        })
    
    except Exception as e:
        print(f"Error in accumulators: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"Starting server on port {port}")
    print(f"API Key configured: {bool(API_KEY)}")
    app.run(host='0.0.0.0', port=port, debug=False)
