#!/usr/bin/env python3
"""
Smart Betting Optimizer - CORRECTED VERSION
Uses: API-Sports Prediction + Market Validation + Agreement Check
Only shows bets where AI recommendation AND market AGREE
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
        """Get API-Sports predictions with recommendation"""
        data = self.make_request('predictions', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]
    
    def extract_best_odds(self, odds_response: Dict) -> Tuple[float, float, float, str, bool]:
        """Get BEST odds across all bookmakers"""
        bookmakers = odds_response.get('bookmakers', [])
        
        best_home = 0.0
        best_draw = 0.0
        best_away = 0.0
        best_bookmaker = 'Unknown'
        has_10bet = False
        
        for bookmaker in bookmakers:
            bookmaker_name = bookmaker.get('name', '')
            bookmaker_id = bookmaker.get('id', 0)
            bets = bookmaker.get('bets', [])
            
            is_10bet = ('10bet' in bookmaker_name.lower() or bookmaker_id == 1)
            if is_10bet:
                has_10bet = True
            
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
                        if home > best_home:
                            best_home = home
                        if draw > best_draw:
                            best_draw = draw
                        if away > best_away:
                            best_away = away
                            best_bookmaker = bookmaker_name
        
        return (best_home, best_draw, best_away, best_bookmaker, has_10bet)
    
    def calculate_market_favorite(self, odds_response: Dict) -> str:
        """Calculate who the market thinks will win (lowest avg odds)"""
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
        
        # Average odds (lower = more likely)
        avg_home = sum(home_odds_list) / len(home_odds_list) if home_odds_list else 999
        avg_draw = sum(draw_odds_list) / len(draw_odds_list) if draw_odds_list else 999
        avg_away = sum(away_odds_list) / len(away_odds_list) if away_odds_list else 999
        
        # Market favorite = lowest odds
        if avg_home < avg_draw and avg_home < avg_away:
            return 'home'
        elif avg_away < avg_home and avg_away < avg_draw:
            return 'away'
        else:
            return 'draw'
    
    def analyze_fixture_smart(self, fixture: Dict) -> Optional[Dict]:
        """CORRECTED analysis using API recommendation + market validation"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        home_id = fixture['teams']['home']['id']
        away_id = fixture['teams']['away']['id']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        print(f"  📊 {home_team} vs {away_team}")
        
        # 1. Get API-Sports PREDICTIONS (with their recommendation!)
        predictions = self.get_predictions(fixture_id)
        if not predictions:
            print(f"      ❌ No predictions available")
            return None
        
        pred_data = predictions.get('predictions', {})
        
        # API's recommended winner
        winner_info = pred_data.get('winner', {})
        api_recommendation = winner_info.get('name', '')
        advice = pred_data.get('advice', 'No advice')
        
        # Get percentages
        percentages = pred_data.get('percent', {})
        ai_home = float(str(percentages.get('home', '0')).replace('%', ''))
        ai_draw = float(str(percentages.get('draw', '0')).replace('%', ''))
        ai_away = float(str(percentages.get('away', '0')).replace('%', ''))
        
        print(f"      🤖 API Recommends: {api_recommendation}")
        print(f"      📊 Probabilities: H:{ai_home}% D:{ai_draw}% A:{ai_away}%")
        
        # 2. Get MARKET odds and favorite
        odds_response = self.get_fixture_odds(fixture_id)
        if not odds_response:
            print(f"      ❌ No odds available")
            return None
        
        best_home, best_draw, best_away, best_bookmaker, has_10bet = self.extract_best_odds(odds_response)
        
        if best_home == 0.0 or best_draw == 0.0 or best_away == 0.0:
            print(f"      ❌ Incomplete odds")
            return None
        
        market_favorite = self.calculate_market_favorite(odds_response)
        
        print(f"      💰 Market Favorite: {market_favorite}")
        print(f"      💵 Best Odds: H:{best_home} D:{best_draw} A:{best_away}")
        
        # 3. DETERMINE SELECTION
        # Map API recommendation to home/draw/away
        api_pick = None
        if api_recommendation == home_team:
            api_pick = 'home'
        elif api_recommendation == away_team:
            api_pick = 'away'
        elif 'draw' in advice.lower() or 'double chance' in advice.lower():
            # If advice mentions draw, it's uncertain
            api_pick = None
        else:
            # Use highest probability
            if ai_home >= ai_draw and ai_home >= ai_away:
                api_pick = 'home'
            elif ai_away >= ai_home and ai_away >= ai_draw:
                api_pick = 'away'
            else:
                api_pick = 'draw'
        
        # 4. CHECK AGREEMENT between API and Market
        if api_pick is None:
            print(f"      ⚠️  API uncertain - Skipped")
            return None
        
        if api_pick != market_favorite:
            print(f"      ❌ Disagreement: API={api_pick} vs Market={market_favorite} - Skipped")
            return None
        
        print(f"      ✅ AGREEMENT! Both say: {api_pick}")
        
        # 5. CALCULATE CONFIDENCE
        # When both agree, it's a strong signal!
        selection_type = api_pick
        
        if selection_type == 'home':
            selection_name = home_team
            selection_prob = ai_home
            selection_odds = best_home
        elif selection_type == 'away':
            selection_name = away_team
            selection_prob = ai_away
            selection_odds = best_away
        else:
            selection_name = 'Draw'
            selection_prob = ai_draw
            selection_odds = best_draw
        
        # Base confidence from AI probability
        confidence = selection_prob
        
        # BONUS: When API and Market agree
        confidence += 20  # Strong trust bonus!
        
        # BONUS: Higher AI probability
        if selection_prob >= 60:
            confidence += 15
        elif selection_prob >= 50:
            confidence += 10
        elif selection_prob >= 40:
            confidence += 5
        
        # BONUS: Reasonable odds (favorites more reliable)
        if selection_odds < 2.0:
            confidence += 10  # Strong favorite
        elif selection_odds < 2.5:
            confidence += 5
        elif selection_odds > 4.0:
            confidence -= 10  # Long shot
        
        # Calculate EV
        ev = (selection_prob / 100 * selection_odds) - 1
        
        # BONUS: Positive EV
        if ev > 0.20:
            confidence += 15
        elif ev > 0.10:
            confidence += 10
        elif ev > 0.05:
            confidence += 5
        
        confidence = min(100, max(0, confidence))
        
        # 6. QUALITY FILTER - must be 70%+ when both agree
        if confidence < 70:
            print(f"      ⚠️  Confidence too low: {confidence:.0f}% - Skipped")
            return None
        
        print(f"      ✅ HIGH QUALITY: {selection_name} @ {selection_odds:.2f} ({confidence:.0f}% conf)")
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': f"{league} ({country})",
            'match_time': match_time,
            'selection': selection_name,
            'selection_type': selection_type,
            'odds': selection_odds,
            'best_bookmaker': best_bookmaker,
            'has_10bet': has_10bet,
            'ai_probability': selection_prob,
            'confidence': confidence,
            'expected_value': ev,
            'api_recommendation': api_recommendation,
            'advice': advice,
            'market_agrees': True,  # Always true when we get here
            'all_odds': {
                'home': best_home,
                'draw': best_draw,
                'away': best_away
            },
            'all_ai_probs': {
                'home': ai_home,
                'draw': ai_draw,
                'away': ai_away
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
        print("SMART PREDICTION ANALYSIS (API + Market Agreement)")
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
            print(f"\n[{i}/{len(fixtures)}]")
            
            analysis = get_analyzer().analyze_fixture_smart(fixture)
            
            if analysis:
                opportunities.append(analysis)
            
            # Rate limiting
            if i % 5 == 0:
                import time
                time.sleep(0.5)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"\n{'='*80}")
        print(f"✅ Found {len(opportunities)} HIGH-QUALITY bets (API + Market agree)")
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
        min_confidence = 75.0  # HIGH QUALITY ONLY
        
        print(f"\nGenerating HIGH-QUALITY accumulators (min {min_confidence}%)")
        
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
                'message': f'Need 2+ bets at {min_confidence}%+ confidence (found {len(opportunities)})'
            })
        
        accumulators = []
        
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
                realistic_conf = (avg_conf / 100) ** num_legs * 100
                potential_return = stake * combined_odds
                
                if avg_conf >= 85 and num_legs == 2 and combined_odds <= 4.0:
                    risk = 'LOW'
                elif avg_conf >= 80 and num_legs <= 2 and combined_odds <= 6.0:
                    risk = 'MEDIUM'
                elif avg_conf >= 75 and num_legs <= 3 and combined_odds <= 10.0:
                    risk = 'MEDIUM'
                else:
                    risk = 'HIGH'
                
                if combined_odds <= 15.0 and avg_conf >= 75:
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
        
        accumulators.sort(key=lambda x: x['realistic_confidence'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(accumulators),
            'accumulators': accumulators[:15]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🧠 Starting CORRECTED Betting Optimizer on port {port}")
    print(f"✅ API Key configured: {bool(API_KEY)}")
    print(f"📊 Method: API Recommendation + Market Agreement ONLY")
    app.run(host='0.0.0.0', port=port, debug=False)
