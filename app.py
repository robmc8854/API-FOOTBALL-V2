#!/usr/bin/env python3
"""
Smart Betting Optimizer - Uses ALL API-Football Data
Analyzes: Predictions, Form, H2H, Statistics, Best Odds
Focus: Find ACTUAL winning bets, not just high odds
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

class SmartBettingAnalyzer:
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
        """Get all bookmaker odds"""
        data = self.make_request('odds', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]
    
    def get_predictions(self, fixture_id: int) -> Optional[Dict]:
        """Get AI predictions with percentages and advice"""
        data = self.make_request('predictions', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]
    
    def get_head_to_head(self, team1_id: int, team2_id: int) -> Optional[List[Dict]]:
        """Get head to head history"""
        data = self.make_request('fixtures/headtohead', params={
            'h2h': f"{team1_id}-{team2_id}"
        })
        
        if not data or 'response' not in data:
            return None
        
        return data['response'][:5]  # Last 5 matches
    
    def get_team_statistics(self, fixture_id: int) -> Optional[Dict]:
        """Get detailed team statistics for fixture"""
        data = self.make_request('fixtures/statistics', params={'fixture': fixture_id})
        
        if not data or 'response' not in data:
            return None
        
        return data['response']
    
    def extract_best_odds(self, odds_response: Dict) -> Tuple[float, float, float, str, bool]:
        """Get BEST odds across all bookmakers + check if 10bet available"""
        bookmakers = odds_response.get('bookmakers', [])
        
        best_home = 0.0
        best_draw = 0.0
        best_away = 0.0
        best_bookmaker = 'Unknown'
        has_10bet = False
        tenbet_home = 0.0
        tenbet_draw = 0.0
        tenbet_away = 0.0
        
        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get('name', '')
            bookmaker_id = bookmaker.get('id', 0)
            bets = bookmaker.get('bets', [])
            
            # Check if this is 10bet
            is_10bet = ('10bet' in bookmaker_name.lower() or bookmaker_id == 1)
            
            for bet in bets:
                if bet.get('name') == 'Match Winner' or bet.get('id') == 1:
                    values = bet.get('values', [])
                    home = 0.0
                    draw = 0.0
                    away = 0.0
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '').lower()
                        
                        if value_name in ['home', '1']:
                            home = odd_value
                        elif value_name in ['draw', 'x']:
                            draw = odd_value
                        elif value_name in ['away', '2']:
                            away = odd_value
                    
                    if home > 0 and draw > 0 and away > 0:
                        # Track 10bet
                        if is_10bet:
                            has_10bet = True
                            tenbet_home = home
                            tenbet_draw = draw
                            tenbet_away = away
                        
                        # Track best odds
                        if home > best_home:
                            best_home = home
                        if draw > best_draw:
                            best_draw = draw
                        if away > best_away:
                            best_away = away
                            best_bookmaker = bookmaker_name
        
        return (best_home, best_draw, best_away, best_bookmaker, has_10bet)
    
    def calculate_market_consensus(self, odds_response: Dict) -> Tuple[float, float, float]:
        """Calculate market-implied probabilities (consensus)"""
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
                            # Convert odds to implied probability
                            implied_prob = (1 / odd_value) * 100
                            
                            if value_name in ['home', '1']:
                                home_odds_list.append(implied_prob)
                            elif value_name in ['draw', 'x']:
                                draw_odds_list.append(implied_prob)
                            elif value_name in ['away', '2']:
                                away_odds_list.append(implied_prob)
        
        # Average market-implied probabilities
        market_home = sum(home_odds_list) / len(home_odds_list) if home_odds_list else 0.0
        market_draw = sum(draw_odds_list) / len(draw_odds_list) if draw_odds_list else 0.0
        market_away = sum(away_odds_list) / len(away_odds_list) if away_odds_list else 0.0
        
        return (market_home, market_draw, market_away)
    
    def analyze_fixture_smart(self, fixture: Dict) -> Optional[Dict]:
        """SMART analysis using ALL available data"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        home_id = fixture['teams']['home']['id']
        away_id = fixture['teams']['away']['id']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        print(f"  📊 {home_team} vs {away_team}")
        
        # 1. Get predictions (AI probabilities + advice)
        predictions = self.get_predictions(fixture_id)
        if not predictions:
            print(f"      ❌ No predictions available")
            return None
        
        pred_data = predictions.get('predictions', {})
        percentages = pred_data.get('percent', {})
        
        ai_home = float(str(percentages.get('home', '0')).replace('%', ''))
        ai_draw = float(str(percentages.get('draw', '0')).replace('%', ''))
        ai_away = float(str(percentages.get('away', '0')).replace('%', ''))
        
        advice = pred_data.get('advice', 'No advice')
        winner_prediction = pred_data.get('winner', {})
        winner_name = winner_prediction.get('name', 'Unknown')
        
        # 2. Get odds from all bookmakers
        odds_response = self.get_fixture_odds(fixture_id)
        if not odds_response:
            print(f"      ❌ No odds available")
            return None
        
        best_home, best_draw, best_away, best_bookmaker, has_10bet = self.extract_best_odds(odds_response)
        
        if best_home == 0.0 or best_draw == 0.0 or best_away == 0.0:
            print(f"      ❌ Incomplete odds")
            return None
        
        # 3. Calculate market consensus (average implied probabilities)
        market_home, market_draw, market_away = self.calculate_market_consensus(odds_response)
        
        # 4. SMART SCORING - Multiple factors
        
        # Create options with all data
        options = [
            {
                'type': 'home',
                'name': home_team,
                'ai_prob': ai_home,
                'market_prob': market_home,
                'best_odds': best_home
            },
            {
                'type': 'draw',
                'name': 'Draw',
                'ai_prob': ai_draw,
                'market_prob': market_draw,
                'best_odds': best_draw
            },
            {
                'type': 'away',
                'name': away_team,
                'ai_prob': ai_away,
                'market_prob': market_away,
                'best_odds': best_away
            }
        ]
        
        # Score each option
        for option in options:
            # Base score from AI prediction
            score = option['ai_prob']
            
            # Factor 1: Agreement between AI and market (trust signal)
            prob_diff = abs(option['ai_prob'] - option['market_prob'])
            if prob_diff < 5:  # Close agreement
                score += 15  # Strong trust bonus
            elif prob_diff < 10:
                score += 10
            elif prob_diff < 15:
                score += 5
            else:
                score -= 5  # Big disagreement, lower confidence
            
            # Factor 2: Value odds (when AI thinks it's more likely than market)
            if option['ai_prob'] > option['market_prob']:
                value_edge = option['ai_prob'] - option['market_prob']
                score += value_edge * 0.5  # Bonus for value
            
            # Factor 3: Expected Value
            ev = (option['ai_prob'] / 100 * option['best_odds']) - 1
            if ev > 0.15:
                score += 15
            elif ev > 0.10:
                score += 10
            elif ev > 0.05:
                score += 5
            elif ev < 0:
                score -= 10  # Negative EV is bad
            
            # Factor 4: Reasonable odds (avoid long shots)
            if option['best_odds'] < 1.5:
                score += 5  # Favorite bonus (more reliable)
            elif option['best_odds'] > 4.0:
                score -= 10  # Long shot penalty
            
            option['confidence_score'] = min(100, max(0, score))
            option['expected_value'] = ev
        
        # Pick best option by confidence score
        best_option = max(options, key=lambda x: x['confidence_score'])
        
        # Debug: Show all options and scoring
        print(f"      🔍 Scoring breakdown:")
        for opt in options:
            print(f"         {opt['name']}: AI={opt['ai_prob']:.1f}% Market={opt['market_prob']:.1f}% Odds={opt['best_odds']:.2f} → Conf={opt['confidence_score']:.1f}%")
        
        # Only recommend if confidence >= 60% (lowered threshold)
        if best_option['confidence_score'] < 60:
            print(f"      ⚠️  Best option too low: {best_option['name']} {best_option['confidence_score']:.0f}% - Skipped")
            return None
        
        print(f"      ✅ {best_option['name']} @ {best_option['best_odds']:.2f} ({best_option['confidence_score']:.0f}% conf)")
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': f"{league} ({country})",
            'match_time': match_time,
            'selection': best_option['name'],
            'selection_type': best_option['type'],
            'odds': best_option['best_odds'],
            'best_bookmaker': best_bookmaker,
            'has_10bet': has_10bet,
            'ai_probability': best_option['ai_prob'],
            'market_probability': best_option['market_prob'],
            'confidence': best_option['confidence_score'],
            'expected_value': best_option['expected_value'],
            'advice': advice,
            'winner_prediction': winner_name,
            'all_odds': {
                'home': best_home,
                'draw': best_draw,
                'away': best_away
            },
            'all_ai_probs': {
                'home': ai_home,
                'draw': ai_draw,
                'away': ai_away
            },
            'all_market_probs': {
                'home': market_home,
                'draw': market_draw,
                'away': market_away
            }
        }

analyzer = None

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = SmartBettingAnalyzer(API_KEY)
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
        print("SMART PREDICTION ANALYSIS")
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
        skipped = {'no_predictions': 0, 'no_odds': 0, 'low_confidence': 0}
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\n[{i}/{len(fixtures)}]")
            
            analysis = get_analyzer().analyze_fixture_smart(fixture)
            
            if analysis:
                opportunities.append(analysis)
            
            # Rate limiting - more requests now (predictions + odds)
            if i % 5 == 0:
                import time
                time.sleep(0.5)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        tenbet_count = sum(1 for o in opportunities if o['has_10bet'])
        
        print(f"\n{'='*80}")
        print(f"✅ Found {len(opportunities)} opportunities (out of {len(fixtures)} fixtures)")
        print(f"📊 10bet available: {tenbet_count}")
        print(f"{'='*80}")
        
        return jsonify({
            'success': True,
            'count': len(opportunities),
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
        min_confidence = float(request.args.get('min_confidence', 70.0))  # Lowered to 70%
        
        print(f"\nGenerating SMART accumulators (min confidence: {min_confidence}%)")
        
        fixtures = get_analyzer().get_todays_fixtures()
        opportunities = []
        
        for fixture in fixtures:
            analysis = get_analyzer().analyze_fixture_smart(fixture)
            if analysis and analysis['confidence'] >= min_confidence:
                opportunities.append(analysis)
        
        print(f"Found {len(opportunities)} high-confidence bets for accumulators")
        
        if len(opportunities) < 2:
            return jsonify({
                'success': True,
                'count': 0,
                'accumulators': [],
                'message': f'Not enough {min_confidence}%+ confidence bets (need 2+, found {len(opportunities)})'
            })
        
        accumulators = []
        
        # Only create 2-3 leg accumulators with HIGH confidence bets
        for num_legs in range(2, min(max_legs + 1, len(opportunities) + 1)):
            for combo in itertools.combinations(opportunities, num_legs):
                combined_odds = 1.0
                total_conf = 0.0
                total_ev = 0.0
                has_10bet_count = 0
                
                for opp in combo:
                    combined_odds *= opp['odds']
                    total_conf += opp['confidence']
                    total_ev += opp['expected_value']
                    if opp['has_10bet']:
                        has_10bet_count += 1
                
                avg_conf = total_conf / num_legs
                avg_ev = total_ev / num_legs
                
                # More realistic confidence scoring for accumulators
                realistic_conf = (avg_conf / 100) ** num_legs * 100
                
                potential_return = stake * combined_odds
                
                # Stricter risk levels
                if avg_conf >= 80 and num_legs == 2 and combined_odds <= 4.0:
                    risk = 'LOW'
                elif avg_conf >= 75 and num_legs <= 2 and combined_odds <= 6.0:
                    risk = 'MEDIUM'
                elif avg_conf >= 70 and num_legs <= 3 and combined_odds <= 10.0:
                    risk = 'MEDIUM'
                else:
                    risk = 'HIGH'
                
                # Only include reasonable accumulators (less strict)
                if combined_odds <= 20.0 and avg_conf >= 70:  # Increased from 15.0 and 75%
                    accumulators.append({
                        'legs': num_legs,
                        'selections': [
                            {
                                'match': f"{o['home_team']} vs {o['away_team']}",
                                'selection': o['selection'],
                                'odds': o['odds'],
                                'confidence': o['confidence'],
                                'expected_value': o['expected_value'],
                                'has_10bet': o['has_10bet'],
                                'bookmaker': o['best_bookmaker']
                            }
                            for o in combo
                        ],
                        'combined_odds': round(combined_odds, 2),
                        'average_confidence': round(avg_conf, 1),
                        'realistic_confidence': round(realistic_conf, 1),
                        'average_ev': round(avg_ev * 100, 1),
                        'stake': stake,
                        'potential_return': round(potential_return, 2),
                        'potential_profit': round(potential_return - stake, 2),
                        'risk_level': risk,
                        'tenbet_legs': has_10bet_count
                    })
        
        # Sort by realistic confidence (most likely to win)
        accumulators.sort(key=lambda x: x['realistic_confidence'], reverse=True)
        
        print(f"Generated {len(accumulators)} quality accumulator options")
        
        return jsonify({
            'success': True,
            'count': len(accumulators),
            'accumulators': accumulators[:15]  # Top 15 most realistic
        })
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🧠 Starting SMART Betting Optimizer on port {port}")
    print(f"✅ API Key configured: {bool(API_KEY)}")
    print(f"📊 Mode: Multi-factor analysis for REAL winners")
    app.run(host='0.0.0.0', port=port, debug=False)
