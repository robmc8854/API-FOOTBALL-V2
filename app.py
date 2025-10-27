#!/usr/bin/env python3
"""
10bet Betting Optimizer - FIXED VERSION
Working with correct API-Football data structure
"""

from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import itertools

app = Flask(__name__)

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
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error for {endpoint}: {e}")
            return None
    
    def get_todays_fixtures(self) -> List[Dict]:
        """Get all fixtures for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        print(f"Fetching fixtures for {today}...")
        data = self.make_request('fixtures', params={'date': today})
        
        if not data or 'response' not in data:
            return []
        
        fixtures = data['response']
        print(f"Total fixtures found: {len(fixtures)}")
        
        now = datetime.now(timezone.utc)
        upcoming = []
        
        for fixture in fixtures:
            try:
                fixture_date = fixture['fixture']['date']
                fixture_time = datetime.fromisoformat(fixture_date.replace('Z', '+00:00'))
                status = fixture['fixture']['status']['long']
                
                if fixture_time > now and status in ['Not Started', 'Time to be defined', 'NS']:
                    upcoming.append(fixture)
            except:
                continue
        
        print(f"Upcoming fixtures: {len(upcoming)}")
        return upcoming
    
    def get_fixture_odds(self, fixture_id: int) -> Optional[Dict]:
        """Get odds for specific fixture - returns the odds response object"""
        data = self.make_request('odds', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]  # Return first odds object
    
    def get_fixture_predictions(self, fixture_id: int) -> Optional[Dict]:
        """Get predictions for specific fixture"""
        data = self.make_request('predictions', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]
    
    def find_10bet_odds(self, odds_response: Dict) -> Tuple[float, float, float, bool]:
        """Extract 10bet odds from odds response - FIXED structure"""
        bookmakers = odds_response.get('bookmakers', [])
        
        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get('name', '').lower()
            bookmaker_id = bookmaker.get('id', 0)
            
            # Look for 10bet
            if '10bet' in bookmaker_name or bookmaker_id == 1:
                bets = bookmaker.get('bets', [])
                
                for bet in bets:
                    # Find Match Winner market (ID: 1)
                    if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                        values = bet.get('values', [])
                        home_odds = 0.0
                        draw_odds = 0.0
                        away_odds = 0.0
                        
                        for value in values:
                            odd_value = float(value.get('odd', 0))
                            value_name = value.get('value', '').lower()
                            
                            if value_name in ['home', '1']:
                                home_odds = odd_value
                            elif value_name in ['draw', 'x']:
                                draw_odds = odd_value
                            elif value_name in ['away', '2']:
                                away_odds = odd_value
                        
                        if home_odds > 0 and draw_odds > 0 and away_odds > 0:
                            print(f"    ✅ Found 10bet: H:{home_odds} D:{draw_odds} A:{away_odds}")
                            return (home_odds, draw_odds, away_odds, True)
        
        return (0.0, 0.0, 0.0, False)
    
    def get_best_odds(self, odds_response: Dict) -> Tuple[float, float, float, str]:
        """Get best available odds from any bookmaker"""
        bookmakers = odds_response.get('bookmakers', [])
        
        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get('name', 'Unknown')
            bets = bookmaker.get('bets', [])
            
            for bet in bets:
                if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                    values = bet.get('values', [])
                    home_odds = 0.0
                    draw_odds = 0.0
                    away_odds = 0.0
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '').lower()
                        
                        if value_name in ['home', '1']:
                            home_odds = odd_value
                        elif value_name in ['draw', 'x']:
                            draw_odds = odd_value
                        elif value_name in ['away', '2']:
                            away_odds = odd_value
                    
                    if home_odds > 0 and draw_odds > 0 and away_odds > 0:
                        return (home_odds, draw_odds, away_odds, bookmaker_name)
        
        return (0.0, 0.0, 0.0, 'Unknown')
    
    def calculate_market_average(self, odds_response: Dict) -> Tuple[float, float, float]:
        """Calculate average odds across all bookmakers"""
        bookmakers = odds_response.get('bookmakers', [])
        
        home_odds_list = []
        draw_odds_list = []
        away_odds_list = []
        
        for bookmaker in bookmakers:
            bets = bookmaker.get('bets', [])
            
            for bet in bets:
                if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                    values = bet.get('values', [])
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '').lower()
                        
                        if odd_value > 0:
                            if value_name in ['home', '1']:
                                home_odds_list.append(odd_value)
                            elif value_name in ['draw', 'x']:
                                draw_odds_list.append(odd_value)
                            elif value_name in ['away', '2']:
                                away_odds_list.append(odd_value)
        
        avg_home = sum(home_odds_list) / len(home_odds_list) if home_odds_list else 0.0
        avg_draw = sum(draw_odds_list) / len(draw_odds_list) if draw_odds_list else 0.0
        avg_away = sum(away_odds_list) / len(away_odds_list) if away_odds_list else 0.0
        
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
            
            return (home_prob, draw_prob, away_prob)
        except:
            return (0.0, 0.0, 0.0)
    
    def analyze_fixture(self, fixture: Dict) -> Optional[Dict]:
        """Analyze a single fixture"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        # Get odds
        odds_response = self.get_fixture_odds(fixture_id)
        
        if not odds_response:
            return None
        
        # Check for 10bet odds
        tenbet_home, tenbet_draw, tenbet_away, has_10bet = self.find_10bet_odds(odds_response)
        
        # Get best available odds
        best_home, best_draw, best_away, bookmaker_name = self.get_best_odds(odds_response)
        
        if best_home == 0.0 or best_draw == 0.0 or best_away == 0.0:
            return None
        
        # Use 10bet if available, otherwise use best odds
        if has_10bet:
            home_odds = tenbet_home
            draw_odds = tenbet_draw
            away_odds = tenbet_away
            odds_source = "10bet"
        else:
            home_odds = best_home
            draw_odds = best_draw
            away_odds = best_away
            odds_source = bookmaker_name
        
        # Get market averages
        avg_home, avg_draw, avg_away = self.calculate_market_average(odds_response)
        
        # Get predictions
        prediction_data = self.get_fixture_predictions(fixture_id)
        home_prob, draw_prob, away_prob = self.get_prediction_probabilities(prediction_data)
        
        # Determine best selection
        selections = [
            {'type': 'home', 'name': home_team, 'prob': home_prob, 'odds': home_odds, 'avg_odds': avg_home},
            {'type': 'draw', 'name': 'Draw', 'prob': draw_prob, 'odds': draw_odds, 'avg_odds': avg_draw},
            {'type': 'away', 'name': away_team, 'prob': away_prob, 'odds': away_odds, 'avg_odds': avg_away}
        ]
        
        best_sel = max(selections, key=lambda x: x['prob'])
        
        # Calculate metrics
        odds_value = ((best_sel['odds'] - best_sel['avg_odds']) / best_sel['avg_odds'] * 100) if best_sel['avg_odds'] > 0 else 0
        expected_value = (best_sel['prob'] / 100 * best_sel['odds']) - 1
        confidence = best_sel['prob']
        
        # Boost confidence
        if odds_value > 5:
            confidence += 10
        if expected_value > 0.1:
            confidence += 10
        if has_10bet:
            confidence += 5
        
        confidence = min(100, confidence)
        
        # Get advice
        advice = "No advice available"
        if prediction_data:
            advice = prediction_data.get('predictions', {}).get('advice', 'No advice available')
        
        print(f"    ✅ {home_team} vs {away_team} - {odds_source} - Conf: {confidence:.0f}%")
        
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
            'odds_source': odds_source,
            'has_10bet': has_10bet,
            'all_odds': {'home': home_odds, 'draw': draw_odds, 'away': away_odds},
            'tenbet_odds': {
                'home': tenbet_home if has_10bet else 0.0,
                'draw': tenbet_draw if has_10bet else 0.0,
                'away': tenbet_away if has_10bet else 0.0
            },
            'all_probabilities': {'home': home_prob, 'draw': draw_prob, 'away': away_prob}
        }

analyzer = None

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = BettingAnalyzer(API_KEY)
    return analyzer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'API key not configured'}), 400
    
    try:
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
            return jsonify({'success': False, 'error': 'Unable to connect'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/predictions')
def get_predictions():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'API key not configured'}), 400
    
    try:
        print("\n" + "="*80)
        print("FETCHING PREDICTIONS")
        print("="*80)
        
        fixtures = get_analyzer().get_todays_fixtures()
        
        if not fixtures:
            return jsonify({
                'success': True,
                'count': 0,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'predictions': [],
                'total_fixtures': 0,
                'message': 'No upcoming fixtures for today'
            })
        
        opportunities = []
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\n[{i}/{len(fixtures)}] {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}")
            
            analysis = get_analyzer().analyze_fixture(fixture)
            
            if analysis:
                opportunities.append(analysis)
            
            # Rate limiting
            if i % 5 == 0:
                import time
                time.sleep(0.5)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        tenbet_count = sum(1 for o in opportunities if o['has_10bet'])
        
        print(f"\n✅ Found {len(opportunities)} opportunities ({tenbet_count} with 10bet)")
        
        return jsonify({
            'success': True,
            'count': len(opportunities),
            'tenbet_count': tenbet_count,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'predictions': opportunities,
            'total_fixtures': len(fixtures)
        })
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accumulators')
def get_accumulators():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'API key not configured'}), 400
    
    try:
        stake = float(request.args.get('stake', 10.0))
        max_legs = int(request.args.get('max_legs', 3))
        
        fixtures = get_analyzer().get_todays_fixtures()
        opportunities = []
        
        for fixture in fixtures:
            analysis = get_analyzer().analyze_fixture(fixture)
            if analysis and analysis['confidence'] >= 60:
                opportunities.append(analysis)
        
        if len(opportunities) < 2:
            return jsonify({
                'success': True,
                'count': 0,
                'accumulators': [],
                'message': 'Not enough high-confidence bets'
            })
        
        accumulators = []
        
        for num_legs in range(2, min(max_legs + 1, len(opportunities) + 1)):
            for combo in itertools.combinations(opportunities, num_legs):
                combined_odds = 1.0
                total_conf = 0.0
                has_10bet_count = 0
                
                for opp in combo:
                    combined_odds *= opp['odds']
                    total_conf += opp['confidence']
                    if opp['has_10bet']:
                        has_10bet_count += 1
                
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
                            'confidence': o['confidence'],
                            'has_10bet': o['has_10bet'],
                            'odds_source': o['odds_source']
                        }
                        for o in combo
                    ],
                    'combined_odds': round(combined_odds, 2),
                    'average_confidence': round(avg_conf, 1),
                    'confidence_score': round(conf_score, 1),
                    'stake': stake,
                    'potential_return': round(potential_return, 2),
                    'potential_profit': round(potential_return - stake, 2),
                    'risk_level': risk,
                    'tenbet_legs': has_10bet_count
                })
        
        accumulators.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(accumulators),
            'accumulators': accumulators[:20]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🚀 Starting server on port {port}")
    print(f"✅ API Key configured: {bool(API_KEY)}")
    print(f"📊 Mode: All bookmakers (10bet highlighted)")
    app.run(host='0.0.0.0', port=port, debug=False)
