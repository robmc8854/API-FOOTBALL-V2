#!/usr/bin/env python3
"""
10bet Betting Optimizer - Railway Web App
Flask web interface for betting analysis and recommendations
"""

from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import itertools
from functools import lru_cache

app = Flask(__name__)

# Configuration
API_TOKEN = os.environ.get('SPORTMONKS_API_TOKEN', '')
TENBET_ID = 2  # 10bet bookmaker ID
BASE_URL = "https://api.sportmonks.com/v3/football"

class BettingAnalyzer:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.params = {'api_token': api_token}
        self.tenbet_id = TENBET_ID
    
    def make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request with error handling"""
        try:
            full_params = {'api_token': self.api_token}
            if params:
                full_params.update(params)
            
            response = self.session.get(url, params=full_params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def get_todays_fixtures(self) -> List[Dict]:
        """Get all fixtures for today"""
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{self.base_url}/fixtures/date/{today}"
        params = {
            'include': 'participants;league;venue;state'
        }
        
        data = self.make_request(url, params)
        return data.get('data', []) if data else []
    
    def get_10bet_odds(self, fixture_id: int) -> Tuple[float, float, float]:
        """Get 10bet 1X2 odds"""
        url = f"{self.base_url}/odds/pre-match/fixtures/{fixture_id}"
        params = {
            'include': 'bookmaker;market',
            'filters': f'bookmakers:{self.tenbet_id}'
        }
        
        data = self.make_request(url, params)
        if not data or 'data' not in data:
            return (0.0, 0.0, 0.0)
        
        for odd in data['data']:
            market = odd.get('market', {})
            if market.get('name') == '1X2' or market.get('id') == 1:
                bookmaker = odd.get('bookmaker', {})
                if bookmaker.get('id') == self.tenbet_id:
                    odds = odd.get('odds', [])
                    home_odds = 0.0
                    draw_odds = 0.0
                    away_odds = 0.0
                    
                    for selection in odds:
                        label = selection.get('label', '').lower()
                        value = float(selection.get('value', 0))
                        
                        if '1' in label or 'home' in label:
                            home_odds = value
                        elif 'x' in label or 'draw' in label:
                            draw_odds = value
                        elif '2' in label or 'away' in label:
                            away_odds = value
                    
                    return (home_odds, draw_odds, away_odds)
        
        return (0.0, 0.0, 0.0)
    
    def get_all_bookmaker_odds(self, fixture_id: int) -> List[Dict]:
        """Get odds from all bookmakers"""
        url = f"{self.base_url}/odds/pre-match/fixtures/{fixture_id}"
        params = {'include': 'bookmaker;market'}
        
        data = self.make_request(url, params)
        if not data or 'data' not in data:
            return []
        
        odds_list = []
        seen_bookmakers = set()
        
        for odd in data['data']:
            market = odd.get('market', {})
            bookmaker = odd.get('bookmaker', {})
            
            if market.get('name') == '1X2' or market.get('id') == 1:
                bookmaker_id = bookmaker.get('id')
                bookmaker_name = bookmaker.get('name', 'Unknown')
                
                if bookmaker_id in seen_bookmakers:
                    continue
                seen_bookmakers.add(bookmaker_id)
                
                odds = odd.get('odds', [])
                home_odds = 0.0
                draw_odds = 0.0
                away_odds = 0.0
                
                for selection in odds:
                    label = selection.get('label', '').lower()
                    value = float(selection.get('value', 0))
                    
                    if '1' in label or 'home' in label:
                        home_odds = value
                    elif 'x' in label or 'draw' in label:
                        draw_odds = value
                    elif '2' in label or 'away' in label:
                        away_odds = value
                
                if home_odds > 0 or draw_odds > 0 or away_odds > 0:
                    odds_list.append({
                        'bookmaker': bookmaker_name,
                        'home': home_odds,
                        'draw': draw_odds,
                        'away': away_odds
                    })
        
        return odds_list
    
    def get_predictions(self, fixture_id: int) -> Tuple[float, float, float]:
        """Get prediction probabilities"""
        url = f"{self.base_url}/predictions/probabilities/fixtures/{fixture_id}"
        data = self.make_request(url)
        
        if not data or 'data' not in data:
            return (0.0, 0.0, 0.0)
        
        try:
            predictions = data['data'].get('predictions', [])
            for pred in predictions:
                if pred.get('type', {}).get('name') == '1X2':
                    home_prob = float(pred.get('home', 0))
                    draw_prob = float(pred.get('draw', 0))
                    away_prob = float(pred.get('away', 0))
                    return (home_prob, draw_prob, away_prob)
        except:
            pass
        
        return (0.0, 0.0, 0.0)
    
    def get_value_bets(self, fixture_id: int) -> float:
        """Get value bet score"""
        url = f"{self.base_url}/predictions/valuebets/fixtures/{fixture_id}"
        data = self.make_request(url)
        
        if not data or 'data' not in data:
            return 0.0
        
        try:
            value_bets = data['data'].get('predictions', [])
            for vb in value_bets:
                if vb.get('type', {}).get('name') == '1X2':
                    return float(vb.get('value', 0))
        except:
            pass
        
        return 0.0
    
    def calculate_market_average(self, all_odds: List[Dict], selection: str) -> float:
        """Calculate average odds across bookmakers"""
        valid_odds = [odd[selection] for odd in all_odds if odd[selection] > 0]
        return sum(valid_odds) / len(valid_odds) if valid_odds else 0.0
    
    def analyze_fixture(self, fixture: Dict) -> Optional[Dict]:
        """Analyze a single fixture"""
        fixture_id = fixture.get('id')
        participants = fixture.get('participants', [])
        
        if len(participants) < 2:
            return None
        
        home_team = participants[0].get('name', 'Unknown')
        away_team = participants[1].get('name', 'Unknown')
        league = fixture.get('league', {}).get('name', 'Unknown')
        match_time = fixture.get('starting_at', 'Unknown')
        
        # Get 10bet odds
        home_odds, draw_odds, away_odds = self.get_10bet_odds(fixture_id)
        
        if home_odds == 0.0 and draw_odds == 0.0 and away_odds == 0.0:
            return None
        
        # Get predictions
        home_prob, draw_prob, away_prob = self.get_predictions(fixture_id)
        
        # Get all bookmaker odds for comparison
        all_odds = self.get_all_bookmaker_odds(fixture_id)
        
        # Calculate market averages
        avg_home = self.calculate_market_average(all_odds, 'home')
        avg_draw = self.calculate_market_average(all_odds, 'draw')
        avg_away = self.calculate_market_average(all_odds, 'away')
        
        # Get value bet score
        value_score = self.get_value_bets(fixture_id)
        
        # Determine best selection
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
            return None
        
        # Calculate metrics
        odds_value = ((best_sel['odds'] - best_sel['avg_odds']) / best_sel['avg_odds'] * 100) if best_sel['avg_odds'] > 0 else 0
        expected_value = (best_sel['prob'] / 100 * best_sel['odds']) - 1
        confidence = best_sel['prob']
        
        # Boost confidence for value bets
        if odds_value > 5:
            confidence += 10
        if expected_value > 0.1:
            confidence += 10
        
        confidence = min(100, confidence)
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': league,
            'match_time': match_time,
            'selection': best_sel['name'],
            'selection_type': best_sel['type'],
            'odds': best_sel['odds'],
            'probability': best_sel['prob'],
            'avg_market_odds': best_sel['avg_odds'],
            'odds_value': odds_value,
            'expected_value': expected_value,
            'confidence': confidence,
            'value_score': value_score,
            'all_odds': {
                'home': home_odds,
                'draw': draw_odds,
                'away': away_odds
            },
            'all_probabilities': {
                'home': home_prob,
                'draw': draw_prob,
                'away': away_prob
            },
            'bookmaker_comparison': all_odds[:5]  # Top 5 bookmakers
        }

# Initialize analyzer
analyzer = BettingAnalyzer(API_TOKEN)

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Check API status"""
    if not API_TOKEN:
        return jsonify({
            'success': False,
            'error': 'API token not configured'
        }), 400
    
    return jsonify({
        'success': True,
        'api_configured': True,
        'tenbet_id': TENBET_ID
    })

@app.route('/api/predictions')
def get_predictions():
    """Get all predictions with 10bet odds"""
    if not API_TOKEN:
        return jsonify({
            'success': False,
            'error': 'API token not configured'
        }), 400
    
    try:
        fixtures = analyzer.get_todays_fixtures()
        opportunities = []
        
        for fixture in fixtures:
            analysis = analyzer.analyze_fixture(fixture)
            if analysis:
                opportunities.append(analysis)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(opportunities),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'predictions': opportunities,
            'total_fixtures': len(fixtures)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/accumulators')
def get_accumulators():
    """Generate accumulator bets"""
    if not API_TOKEN:
        return jsonify({
            'success': False,
            'error': 'API token not configured'
        }), 400
    
    try:
        stake = float(request.args.get('stake', 10.0))
        max_legs = int(request.args.get('max_legs', 3))
        
        fixtures = analyzer.get_todays_fixtures()
        opportunities = []
        
        for fixture in fixtures:
            analysis = analyzer.analyze_fixture(fixture)
            if analysis and analysis['confidence'] >= 60:
                opportunities.append(analysis)
        
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
        
        return jsonify({
            'success': True,
            'count': len(accumulators),
            'accumulators': accumulators[:20]  # Top 20
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/fixture/<int:fixture_id>')
def get_fixture_detail(fixture_id):
    """Get detailed analysis for specific fixture"""
    if not API_TOKEN:
        return jsonify({
            'success': False,
            'error': 'API token not configured'
        }), 400
    
    try:
        # This would need to fetch and analyze specific fixture
        return jsonify({
            'success': True,
            'fixture_id': fixture_id,
            'message': 'Detailed analysis endpoint'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
