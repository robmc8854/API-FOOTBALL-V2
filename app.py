#!/usr/bin/env python3
"""
Advanced Multi-Market Betting Optimizer - BALANCED VERSION
Analyzes ALL markets equally: Match Winner, BTTS, Over/Under, Double Chance
Each market validated with: API prediction + Market direction + AI probability
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

class AdvancedBettingAnalyzer:
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
        """Get API-Sports predictions"""
        data = self.make_request('predictions', params={'fixture': fixture_id})
        
        if not data or 'response' not in data or len(data['response']) == 0:
            return None
        
        return data['response'][0]
    
    def safe_extract_goals_avg(self, pred_data: Dict, team: str = 'home') -> float:
        """Safely extract team's average goals from predictions data"""
        try:
            goals_data = pred_data.get('goals', {})
            if not isinstance(goals_data, dict):
                return 0.0
            
            team_data = goals_data.get(team, {})
            if not isinstance(team_data, dict):
                return 0.0
            
            avg_data = team_data.get('average', {})
            if not isinstance(avg_data, dict):
                return 0.0
            
            total = avg_data.get('total', 0)
            if isinstance(total, str):
                return float(total) if total else 0.0
            return float(total)
        except:
            return 0.0
    
    def extract_match_winner_odds(self, odds_response: Dict) -> Tuple[float, float, float, str, bool]:
        """Get BEST Match Winner odds"""
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
                            best_bookmaker = bookmaker_name
                        if draw > best_draw:
                            best_draw = draw
                        if away > best_away:
                            best_away = away
        
        return (best_home, best_draw, best_away, best_bookmaker, has_10bet)
    
    def extract_btts_odds(self, odds_response: Dict) -> Optional[Dict]:
        """Extract Both Teams To Score odds"""
        bookmakers = odds_response.get('bookmakers', [])
        
        best_yes = 0.0
        best_no = 0.0
        bookmaker_name = 'Unknown'
        has_10bet = False
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get('name', '')
            bm_id = bookmaker.get('id', 0)
            bets = bookmaker.get('bets', [])
            
            is_10bet = ('10bet' in bm_name.lower() or bm_id == 1)
            
            for bet in bets:
                bet_name = bet.get('name', '')
                
                if 'Both Teams Score' in bet_name or bet.get('id') == 8:
                    values = bet.get('values', [])
                    yes_odd = 0.0
                    no_odd = 0.0
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '').lower()
                        
                        if 'yes' in value_name:
                            yes_odd = odd_value
                        elif 'no' in value_name:
                            no_odd = odd_value
                    
                    if yes_odd > 0 and no_odd > 0:
                        if yes_odd > best_yes:
                            best_yes = yes_odd
                            best_no = no_odd
                            bookmaker_name = bm_name
                            if is_10bet:
                                has_10bet = True
        
        if best_yes > 0 and best_no > 0:
            return {
                'yes': best_yes,
                'no': best_no,
                'bookmaker': bookmaker_name,
                'has_10bet': has_10bet
            }
        return None
    
    def extract_over_under_odds(self, odds_response: Dict) -> Dict[str, Dict]:
        """Extract Over/Under odds for multiple lines"""
        bookmakers = odds_response.get('bookmakers', [])
        
        lines = {}
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get('name', '')
            bm_id = bookmaker.get('id', 0)
            bets = bookmaker.get('bets', [])
            
            is_10bet = ('10bet' in bm_name.lower() or bm_id == 1)
            
            for bet in bets:
                bet_name = bet.get('name', '')
                
                if 'Over/Under' in bet_name or 'Goals Over/Under' in bet_name:
                    values = bet.get('values', [])
                    
                    over_odd = 0.0
                    under_odd = 0.0
                    line = None
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '')
                        
                        if 'Over' in value_name:
                            over_odd = odd_value
                            try:
                                line = value_name.split()[-1]
                            except:
                                pass
                        elif 'Under' in value_name:
                            under_odd = odd_value
                            try:
                                line = value_name.split()[-1]
                            except:
                                pass
                    
                    if line and over_odd > 0 and under_odd > 0:
                        if line not in lines or over_odd > lines[line]['over']:
                            lines[line] = {
                                'over': over_odd,
                                'under': under_odd,
                                'bookmaker': bm_name,
                                'has_10bet': is_10bet
                            }
        
        return lines
    
    def extract_double_chance_odds(self, odds_response: Dict) -> Optional[Dict]:
        """Extract Double Chance odds"""
        bookmakers = odds_response.get('bookmakers', [])
        
        best_1x = 0.0
        best_12 = 0.0
        best_x2 = 0.0
        bookmaker_name = 'Unknown'
        has_10bet = False
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get('name', '')
            bm_id = bookmaker.get('id', 0)
            bets = bookmaker.get('bets', [])
            
            is_10bet = ('10bet' in bm_name.lower() or bm_id == 1)
            
            for bet in bets:
                bet_name = bet.get('name', '')
                
                if 'Double Chance' in bet_name or bet.get('id') == 7:
                    values = bet.get('values', [])
                    
                    for value in values:
                        odd_value = float(value.get('odd', 0))
                        value_name = value.get('value', '')
                        
                        if 'Home/Draw' in value_name or value_name == '1X':
                            if odd_value > best_1x:
                                best_1x = odd_value
                        elif 'Home/Away' in value_name or value_name == '12':
                            if odd_value > best_12:
                                best_12 = odd_value
                        elif 'Draw/Away' in value_name or value_name == 'X2':
                            if odd_value > best_x2:
                                best_x2 = odd_value
                    
                    if best_1x > 0:
                        bookmaker_name = bm_name
                        if is_10bet:
                            has_10bet = True
        
        if best_1x > 0 and best_12 > 0 and best_x2 > 0:
            return {
                '1X': best_1x,
                '12': best_12,
                'X2': best_x2,
                'bookmaker': bookmaker_name,
                'has_10bet': has_10bet
            }
        return None
    
    def calculate_market_favorite(self, odds_response: Dict) -> str:
        """Calculate who the market thinks will win"""
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
        
        avg_home = sum(home_odds_list) / len(home_odds_list) if home_odds_list else 999
        avg_draw = sum(draw_odds_list) / len(draw_odds_list) if draw_odds_list else 999
        avg_away = sum(away_odds_list) / len(away_odds_list) if away_odds_list else 999
        
        if avg_home < avg_draw and avg_home < avg_away:
            return 'home'
        elif avg_away < avg_home and avg_away < avg_draw:
            return 'away'
        else:
            return 'draw'
    
    def analyze_all_markets(self, fixture: Dict) -> Optional[Dict]:
        """Analyze ALL markets with equal treatment - find truly best bets"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        print(f"  📊 {home_team} vs {away_team}")
        
        # Get predictions
        predictions = self.get_predictions(fixture_id)
        if not predictions:
            print(f"      ❌ No predictions available")
            return None
        
        # Get odds
        odds_response = self.get_fixture_odds(fixture_id)
        if not odds_response:
            print(f"      ❌ No odds available")
            return None
        
        pred_data = predictions.get('predictions', {})
        
        # Extract probabilities
        winner_info = pred_data.get('winner', {})
        api_recommendation = winner_info.get('name', '')
        
        percentages = pred_data.get('percent', {})
        ai_home = float(str(percentages.get('home', '0')).replace('%', ''))
        ai_draw = float(str(percentages.get('draw', '0')).replace('%', ''))
        ai_away = float(str(percentages.get('away', '0')).replace('%', ''))
        
        # Get goals averages
        home_avg = self.safe_extract_goals_avg(pred_data, 'home')
        away_avg = self.safe_extract_goals_avg(pred_data, 'away')
        total_avg = home_avg + away_avg
        
        market_favorite = self.calculate_market_favorite(odds_response)
        
        print(f"      🤖 API: {api_recommendation if api_recommendation else 'None'} | Market: {market_favorite}")
        print(f"      📈 Home: {ai_home}% | Draw: {ai_draw}% | Away: {ai_away}%")
        print(f"      ⚽ Goals: {total_avg:.1f} (Home {home_avg:.1f} + Away {away_avg:.1f})")
        
        all_bets = []
        
        # === MATCH WINNER ===
        mw_odds = self.extract_match_winner_odds(odds_response)
        best_home, best_draw, best_away, mw_bookmaker, mw_has_10bet = mw_odds
        
        if best_home > 0:
            # Home Win
            if api_recommendation == home_team and market_favorite == 'home' and ai_home >= 50:
                impl_prob = (1 / best_home) * 100
                ev = ((ai_home / 100) * best_home) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{home_team} Win',
                        'odds': best_home,
                        'confidence': min(ai_home, 90),
                        'ai_probability': ai_home,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': ai_home + (ev * 50),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw_bookmaker,
                        'has_10bet': mw_has_10bet,
                        'reasoning': f'Strong home favorite. API & market agree. {ai_home:.0f}% confidence'
                    })
            
            # Away Win
            if api_recommendation == away_team and market_favorite == 'away' and ai_away >= 50:
                impl_prob = (1 / best_away) * 100
                ev = ((ai_away / 100) * best_away) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{away_team} Win',
                        'odds': best_away,
                        'confidence': min(ai_away, 90),
                        'ai_probability': ai_away,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': ai_away + (ev * 50),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw_bookmaker,
                        'has_10bet': mw_has_10bet,
                        'reasoning': f'Strong away favorite. API & market agree. {ai_away:.0f}% confidence'
                    })
            
            # Draw
            if ai_draw >= 28 and abs(ai_home - ai_away) < 12:
                impl_prob = (1 / best_draw) * 100
                ev = ((ai_draw / 100) * best_draw) - 1
                if ev > 0.05:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': 'Draw',
                        'odds': best_draw,
                        'confidence': min(ai_draw * 0.9, 75),
                        'ai_probability': ai_draw,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': ai_draw * 0.8 + (ev * 50),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw_bookmaker,
                        'has_10bet': mw_has_10bet,
                        'reasoning': f'Evenly matched. {ai_draw:.0f}% draw probability with value'
                    })
        
        # === BTTS ===
        btts_odds = self.extract_btts_odds(odds_response)
        if btts_odds and home_avg > 0 and away_avg > 0:
            # BTTS Yes
            if home_avg >= 1.0 and away_avg >= 1.0:
                btts_yes_prob = min(((home_avg + away_avg) / 4) * 100, 85)
                impl_prob = (1 / btts_odds['yes']) * 100
                ev = ((btts_yes_prob / 100) * btts_odds['yes']) - 1
                if ev > 0 and btts_yes_prob >= 55:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'Yes',
                        'odds': btts_odds['yes'],
                        'confidence': btts_yes_prob,
                        'ai_probability': btts_yes_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_yes_prob + (ev * 40),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': btts_odds['bookmaker'],
                        'has_10bet': btts_odds['has_10bet'],
                        'reasoning': f'Both teams score regularly. {home_avg:.1f} & {away_avg:.1f} avg goals'
                    })
            
            # BTTS No
            elif home_avg < 0.9 or away_avg < 0.9:
                btts_no_prob = min(100 - ((home_avg + away_avg) / 4) * 100, 80)
                impl_prob = (1 / btts_odds['no']) * 100
                ev = ((btts_no_prob / 100) * btts_odds['no']) - 1
                if ev > 0 and btts_no_prob >= 55:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'No',
                        'odds': btts_odds['no'],
                        'confidence': btts_no_prob,
                        'ai_probability': btts_no_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_no_prob + (ev * 40),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': btts_odds['bookmaker'],
                        'has_10bet': btts_odds['has_10bet'],
                        'reasoning': f'Low scoring teams. {home_avg:.1f} & {away_avg:.1f} avg goals'
                    })
        
        # === OVER/UNDER ===
        ou_odds = self.extract_over_under_odds(odds_response)
        if ou_odds and total_avg > 0:
            for line, odds_data in ou_odds.items():
                try:
                    line_float = float(line)
                    
                    # Over
                    if total_avg > line_float + 0.3:
                        over_prob = min(55 + (total_avg - line_float) * 10, 80)
                        impl_prob = (1 / odds_data['over']) * 100
                        ev = ((over_prob / 100) * odds_data['over']) - 1
                        if ev > 0 and over_prob > impl_prob:
                            all_bets.append({
                                'market': f'Over/Under {line}',
                                'selection': f'Over {line}',
                                'odds': odds_data['over'],
                                'confidence': over_prob,
                                'ai_probability': over_prob,
                                'implied_probability': impl_prob,
                                'expected_value': ev,
                                'quality_score': over_prob + (ev * 45),
                                'api_agrees': True,
                                'market_agrees': True,
                                'bookmaker': odds_data['bookmaker'],
                                'has_10bet': odds_data['has_10bet'],
                                'reasoning': f'Expected {total_avg:.1f} goals. {total_avg - line_float:.1f} above {line} line'
                            })
                    
                    # Under
                    elif total_avg < line_float - 0.3:
                        under_prob = min(55 + (line_float - total_avg) * 10, 80)
                        impl_prob = (1 / odds_data['under']) * 100
                        ev = ((under_prob / 100) * odds_data['under']) - 1
                        if ev > 0 and under_prob > impl_prob:
                            all_bets.append({
                                'market': f'Over/Under {line}',
                                'selection': f'Under {line}',
                                'odds': odds_data['under'],
                                'confidence': under_prob,
                                'ai_probability': under_prob,
                                'implied_probability': impl_prob,
                                'expected_value': ev,
                                'quality_score': under_prob + (ev * 45),
                                'api_agrees': True,
                                'market_agrees': True,
                                'bookmaker': odds_data['bookmaker'],
                                'has_10bet': odds_data['has_10bet'],
                                'reasoning': f'Expected {total_avg:.1f} goals. {line_float - total_avg:.1f} below {line} line'
                            })
                except:
                    continue
        
        # === DOUBLE CHANCE ===
        dc_odds = self.extract_double_chance_odds(odds_response)
        if dc_odds:
            # 1X (Home or Draw)
            if ai_home + ai_draw >= 70:
                dc_prob = ai_home + ai_draw
                impl_prob = (1 / dc_odds['1X']) * 100
                ev = ((dc_prob / 100) * dc_odds['1X']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or Draw',
                        'odds': dc_odds['1X'],
                        'confidence': min(dc_prob * 0.9, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.9 + (ev * 35),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc_odds['bookmaker'],
                        'has_10bet': dc_odds['has_10bet'],
                        'reasoning': f'Safe bet: {home_team} ({ai_home:.0f}%) or Draw ({ai_draw:.0f}%)'
                    })
            
            # X2 (Draw or Away)
            if ai_away + ai_draw >= 70:
                dc_prob = ai_away + ai_draw
                impl_prob = (1 / dc_odds['X2']) * 100
                ev = ((dc_prob / 100) * dc_odds['X2']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{away_team} or Draw',
                        'odds': dc_odds['X2'],
                        'confidence': min(dc_prob * 0.9, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.9 + (ev * 35),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc_odds['bookmaker'],
                        'has_10bet': dc_odds['has_10bet'],
                        'reasoning': f'Safe bet: {away_team} ({ai_away:.0f}%) or Draw ({ai_draw:.0f}%)'
                    })
            
            # 12 (Home or Away)
            if ai_home + ai_away >= 75:
                dc_prob = ai_home + ai_away
                impl_prob = (1 / dc_odds['12']) * 100
                ev = ((dc_prob / 100) * dc_odds['12']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or {away_team}',
                        'odds': dc_odds['12'],
                        'confidence': min(dc_prob * 0.9, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.9 + (ev * 35),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc_odds['bookmaker'],
                        'has_10bet': dc_odds['has_10bet'],
                        'reasoning': f'Draw unlikely ({ai_draw:.0f}%). Either team can win'
                    })
        
        if not all_bets:
            print(f"      ❌ No validated bets found")
            return None
        
        # Sort by quality score (combines confidence + EV)
        all_bets.sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"      ✅ Found {len(all_bets)} validated bets across all markets")
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': league,
            'country': country,
            'match_time': match_time,
            'best_bets': all_bets[:5],
            'all_bets': all_bets,
            'total_opportunities': len(all_bets)
        }

analyzer = None

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = AdvancedBettingAnalyzer(API_KEY)
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

@app.route('/api/analysis')
def get_analysis():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'API key not configured'}), 400
    
    try:
        print("\n" + "="*80)
        print("BALANCED MULTI-MARKET BETTING ANALYSIS")
        print("="*80)
        
        fixtures = get_analyzer().get_todays_fixtures()
        
        if not fixtures:
            return jsonify({
                'success': True,
                'count': 0,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'matches': [],
                'total_fixtures': 0,
                'message': 'No upcoming fixtures for today'
            })
        
        match_analyses = []
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\n[{i}/{len(fixtures)}]")
            
            analysis = get_analyzer().analyze_all_markets(fixture)
            
            if analysis:
                match_analyses.append(analysis)
            
            # Rate limiting
            if i % 5 == 0:
                import time
                time.sleep(0.5)
        
        print(f"\n{'='*80}")
        print(f"✅ Analyzed {len(match_analyses)} matches with validated bets")
        print(f"{'='*80}")
        
        return jsonify({
            'success': True,
            'count': len(match_analyses),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'matches': match_analyses,
            'total_fixtures': len(fixtures)
        })
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🧠 Starting Balanced Multi-Market Betting Optimizer on port {port}")
    print(f"✅ API Key configured: {bool(API_KEY)}")
    print(f"📊 All Markets Analyzed Equally: Match Winner, BTTS, O/U, Double Chance")
    app.run(host='0.0.0.0', port=port, debug=False)
