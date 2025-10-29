#!/usr/bin/env python3
"""
FINAL Balanced Multi-Market Betting Analyzer
Shows the TOP 3 best bets per game across ALL markets with CORRECT odds
"""

from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

app = Flask(__name__)

API_KEY = os.environ.get('API_SPORTS_KEY', '')
BASE_URL = "https://v3.football.api-sports.io"

class FinalBettingAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
    
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def get_todays_fixtures(self) -> List[Dict]:
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"Fetching fixtures for {today}...")
        data = self.make_request('fixtures', params={'date': today})
        
        if not data or 'response' not in data:
            return []
        
        fixtures = data['response']
        print(f"Found {len(fixtures)} total fixtures")
        
        upcoming = []
        for fixture in fixtures:
            try:
                status = fixture['fixture']['status']['long']
                if status in ['Not Started', 'Time to be defined', 'NS', 'TBD']:
                    upcoming.append(fixture)
            except:
                continue
        
        print(f"Upcoming fixtures: {len(upcoming)}")
        return upcoming
    
    def get_fixture_odds(self, fixture_id: int) -> Optional[Dict]:
        data = self.make_request('odds', params={'fixture': fixture_id})
        return data['response'][0] if data and 'response' in data and data['response'] else None
    
    def get_predictions(self, fixture_id: int) -> Optional[Dict]:
        data = self.make_request('predictions', params={'fixture': fixture_id})
        return data['response'][0] if data and 'response' in data and data['response'] else None
    
    def safe_float(self, value, default=0.0) -> float:
        try:
            if isinstance(value, str):
                return float(value.replace('%', ''))
            return float(value) if value else default
        except:
            return default
    
    def extract_all_odds(self, odds_response: Dict) -> Dict:
        """Extract ACTUAL bookmaker odds"""
        bookmakers = odds_response.get('bookmakers', [])
        
        result = {
            'match_winner': {'home': 0, 'draw': 0, 'away': 0, 'bookmaker': '', 'has_10bet': False},
            'btts': {'yes': 0, 'no': 0, 'bookmaker': '', 'has_10bet': False},
            'over_under': {},
            'double_chance': {'1X': 0, '12': 0, 'X2': 0, 'bookmaker': '', 'has_10bet': False}
        }
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get('name', '')
            is_10bet = '10bet' in bm_name.lower()
            
            for bet in bookmaker.get('bets', []):
                bet_name = bet.get('name', '')
                values = bet.get('values', [])
                
                if 'Match Winner' in bet_name:
                    for value in values:
                        odd = self.safe_float(value.get('odd', 0))
                        val_name = value.get('value', '').lower()
                        if 'home' in val_name or val_name == '1':
                            if odd > result['match_winner']['home']:
                                result['match_winner'].update({'home': odd, 'bookmaker': bm_name, 'has_10bet': is_10bet})
                        elif 'draw' in val_name or val_name == 'x':
                            if odd > result['match_winner']['draw']:
                                result['match_winner']['draw'] = odd
                        elif 'away' in val_name or val_name == '2':
                            if odd > result['match_winner']['away']:
                                result['match_winner']['away'] = odd
                
                elif 'Both Teams Score' in bet_name:
                    for value in values:
                        odd = self.safe_float(value.get('odd', 0))
                        val_name = value.get('value', '').lower()
                        if 'yes' in val_name and odd > result['btts']['yes']:
                            result['btts'].update({'yes': odd, 'bookmaker': bm_name, 'has_10bet': is_10bet})
                        elif 'no' in val_name and odd > result['btts']['no']:
                            result['btts']['no'] = odd
                
                elif 'Over/Under' in bet_name or 'Goals Over/Under' in bet_name:
                    for value in values:
                        odd = self.safe_float(value.get('odd', 0))
                        val_name = value.get('value', '')
                        if 'Over' in val_name:
                            line = val_name.split()[-1]
                            if line not in result['over_under']:
                                result['over_under'][line] = {'over': 0, 'under': 0, 'bookmaker': '', 'has_10bet': False}
                            if odd > result['over_under'][line]['over']:
                                result['over_under'][line].update({'over': odd, 'bookmaker': bm_name, 'has_10bet': is_10bet})
                        elif 'Under' in val_name:
                            line = val_name.split()[-1]
                            if line not in result['over_under']:
                                result['over_under'][line] = {'over': 0, 'under': 0, 'bookmaker': '', 'has_10bet': False}
                            if odd > result['over_under'][line]['under']:
                                result['over_under'][line]['under'] = odd
                
                elif 'Double Chance' in bet_name:
                    for value in values:
                        odd = self.safe_float(value.get('odd', 0))
                        val_name = value.get('value', '')
                        if 'Home/Draw' in val_name or val_name == '1X':
                            if odd > result['double_chance']['1X']:
                                result['double_chance'].update({'1X': odd, 'bookmaker': bm_name, 'has_10bet': is_10bet})
                        elif 'Home/Away' in val_name or val_name == '12':
                            if odd > result['double_chance']['12']:
                                result['double_chance']['12'] = odd
                        elif 'Draw/Away' in val_name or val_name == 'X2':
                            if odd > result['double_chance']['X2']:
                                result['double_chance']['X2'] = odd
        
        return result
    
    def calculate_market_probabilities(self, odds_response: Dict) -> Dict:
        bookmakers = odds_response.get('bookmakers', [])
        home_odds, draw_odds, away_odds = [], [], []
        
        for bookmaker in bookmakers:
            for bet in bookmaker.get('bets', []):
                if 'Match Winner' in bet.get('name', ''):
                    for value in bet.get('values', []):
                        odd = self.safe_float(value.get('odd', 0))
                        val_name = value.get('value', '').lower()
                        if odd > 0:
                            if 'home' in val_name or val_name == '1':
                                home_odds.append(odd)
                            elif 'draw' in val_name or val_name == 'x':
                                draw_odds.append(odd)
                            elif 'away' in val_name or val_name == '2':
                                away_odds.append(odd)
        
        avg_home = sum(home_odds) / len(home_odds) if home_odds else 999
        avg_draw = sum(draw_odds) / len(draw_odds) if draw_odds else 999
        avg_away = sum(away_odds) / len(away_odds) if away_odds else 999
        
        total = (1/avg_home if avg_home < 999 else 0) + (1/avg_draw if avg_draw < 999 else 0) + (1/avg_away if avg_away < 999 else 0)
        
        if total > 0:
            return {
                'home': (1/avg_home) / total * 100,
                'draw': (1/avg_draw) / total * 100,
                'away': (1/avg_away) / total * 100
            }
        return {'home': 33.3, 'draw': 33.3, 'away': 33.3}
    
    def analyze_match(self, fixture: Dict) -> Optional[Dict]:
        """Analyze and return TOP 3 bets across ALL markets"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        match_time = fixture['fixture']['date']
        
        print(f"\n  📊 {home_team} vs {away_team}")
        
        pred_full = self.get_predictions(fixture_id)
        if not pred_full:
            print(f"      ❌ No predictions")
            return None
        
        odds_response = self.get_fixture_odds(fixture_id)
        if not odds_response:
            print(f"      ❌ No odds")
            return None
        
        predictions = pred_full.get('predictions', {})
        comparison = pred_full.get('comparison', {})
        teams_data = pred_full.get('teams', {})
        
        # Get AI probabilities
        percent = predictions.get('percent', {})
        ai_home = self.safe_float(percent.get('home', 0))
        ai_draw = self.safe_float(percent.get('draw', 0))
        ai_away = self.safe_float(percent.get('away', 0))
        
        # Get Poisson
        poisson = comparison.get('poisson_distribution', {})
        poisson_home = self.safe_float(poisson.get('home', 0))
        poisson_draw = self.safe_float(poisson.get('draw', 0))
        poisson_away = self.safe_float(poisson.get('away', 0))
        
        # Get market
        market = self.calculate_market_probabilities(odds_response)
        
        # Combined probability (simple weighted average)
        combined_home = (poisson_home * 0.4 + ai_home * 0.4 + market['home'] * 0.2)
        combined_draw = (poisson_draw * 0.4 + ai_draw * 0.4 + market['draw'] * 0.2)
        combined_away = (poisson_away * 0.4 + ai_away * 0.4 + market['away'] * 0.2)
        
        # Goals data
        home_league = teams_data.get('home', {}).get('league', {})
        away_league = teams_data.get('away', {}).get('league', {})
        home_goals_avg = self.safe_float(home_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 1.0))
        away_goals_avg = self.safe_float(away_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 1.0))
        total_goals_avg = home_goals_avg + away_goals_avg
        
        home_clean = self.safe_float(home_league.get('clean_sheet', {}).get('total', 0))
        away_clean = self.safe_float(away_league.get('clean_sheet', {}).get('total', 0))
        
        print(f"      AI: H:{ai_home:.0f}% D:{ai_draw:.0f}% A:{ai_away:.0f}%")
        print(f"      Goals avg: {total_goals_avg:.1f}")
        
        # Get all odds
        all_odds = self.extract_all_odds(odds_response)
        all_bets = []
        
        # === MATCH WINNER ===
        mw = all_odds['match_winner']
        if mw['home'] > 0:
            # Home
            if combined_home >= 40 and mw['home'] >= 1.3 and mw['home'] <= 4.0:
                impl_prob = (1 / mw['home']) * 100
                ev = ((combined_home / 100) * mw['home']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{home_team} Win',
                        'odds': round(mw['home'], 2),  # ACTUAL bookmaker odds
                        'confidence': min(combined_home, 85),
                        'expected_value': ev,
                        'quality_score': combined_home + (ev * 100),
                        'bookmaker': mw['bookmaker'],
                        'reasoning': f'{combined_home:.0f}% probability (Poisson {poisson_home:.0f}% + AI {ai_home:.0f}%)'
                    })
            
            # Away
            if combined_away >= 40 and mw['away'] >= 1.3 and mw['away'] <= 4.0:
                impl_prob = (1 / mw['away']) * 100
                ev = ((combined_away / 100) * mw['away']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{away_team} Win',
                        'odds': round(mw['away'], 2),
                        'confidence': min(combined_away, 85),
                        'expected_value': ev,
                        'quality_score': combined_away + (ev * 100),
                        'bookmaker': mw['bookmaker'],
                        'reasoning': f'{combined_away:.0f}% probability (Poisson {poisson_away:.0f}% + AI {ai_away:.0f}%)'
                    })
            
            # Draw
            if combined_draw >= 22 and mw['draw'] >= 2.5 and mw['draw'] <= 5.0:
                impl_prob = (1 / mw['draw']) * 100
                ev = ((combined_draw / 100) * mw['draw']) - 1
                if ev > 0.03:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': 'Draw',
                        'odds': round(mw['draw'], 2),
                        'confidence': min(combined_draw * 0.9, 75),
                        'expected_value': ev,
                        'quality_score': combined_draw * 0.9 + (ev * 90),
                        'bookmaker': mw['bookmaker'],
                        'reasoning': f'{combined_draw:.0f}% probability. Evenly matched teams'
                    })
        
        # === BTTS ===
        btts = all_odds['btts']
        if btts['yes'] > 0:
            # Yes
            if home_goals_avg >= 0.8 and away_goals_avg >= 0.8:
                btts_prob = min(50 + (home_goals_avg + away_goals_avg - 1.6) * 15, 75)
                impl_prob = (1 / btts['yes']) * 100
                ev = ((btts_prob / 100) * btts['yes']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'Yes',
                        'odds': round(btts['yes'], 2),
                        'confidence': btts_prob,
                        'expected_value': ev,
                        'quality_score': btts_prob + (ev * 100),
                        'bookmaker': btts['bookmaker'],
                        'reasoning': f'Both teams score regularly. Home {home_goals_avg:.1f} | Away {away_goals_avg:.1f} goals/game'
                    })
            
            # No
            if home_clean >= 5 or away_clean >= 5 or home_goals_avg < 0.8 or away_goals_avg < 0.8:
                btts_no_prob = min(50 + (home_clean + away_clean), 75)
                impl_prob = (1 / btts['no']) * 100
                ev = ((btts_no_prob / 100) * btts['no']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'No',
                        'odds': round(btts['no'], 2),
                        'confidence': btts_no_prob,
                        'expected_value': ev,
                        'quality_score': btts_no_prob + (ev * 100),
                        'bookmaker': btts['bookmaker'],
                        'reasoning': f'Strong defense or weak attack. Clean sheets: H:{home_clean:.0f} A:{away_clean:.0f}'
                    })
        
        # === OVER/UNDER ===
        for line, ou in all_odds['over_under'].items():
            if ou['over'] == 0 or ou['under'] == 0:
                continue
            
            try:
                line_float = float(line)
                
                # Over
                if total_goals_avg > line_float + 0.25:
                    over_prob = min(50 + (total_goals_avg - line_float) * 12, 75)
                    ev = ((over_prob / 100) * ou['over']) - 1
                    if ev > 0:
                        all_bets.append({
                            'market': f'Over/Under {line}',
                            'selection': f'Over {line}',
                            'odds': round(ou['over'], 2),
                            'confidence': over_prob,
                            'expected_value': ev,
                            'quality_score': over_prob + (ev * 100),
                            'bookmaker': ou['bookmaker'],
                            'reasoning': f'Expected {total_goals_avg:.1f} goals. {total_goals_avg - line_float:.1f} above {line}'
                        })
                
                # Under
                elif total_goals_avg < line_float - 0.25:
                    under_prob = min(50 + (line_float - total_goals_avg) * 12, 75)
                    ev = ((under_prob / 100) * ou['under']) - 1
                    if ev > 0:
                        all_bets.append({
                            'market': f'Over/Under {line}',
                            'selection': f'Under {line}',
                            'odds': round(ou['under'], 2),
                            'confidence': under_prob,
                            'expected_value': ev,
                            'quality_score': under_prob + (ev * 100),
                            'bookmaker': ou['bookmaker'],
                            'reasoning': f'Expected {total_goals_avg:.1f} goals. {line_float - total_goals_avg:.1f} below {line}'
                        })
            except:
                continue
        
        # === DOUBLE CHANCE ===
        dc = all_odds['double_chance']
        if dc['1X'] > 0:
            # 1X
            if combined_home + combined_draw >= 60 and dc['1X'] >= 1.08 and dc['1X'] <= 1.8:
                dc_prob = combined_home + combined_draw
                ev = ((dc_prob / 100) * dc['1X']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or Draw',
                        'odds': round(dc['1X'], 2),
                        'confidence': min(dc_prob * 0.92, 85),
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.85 + (ev * 80),
                        'bookmaker': dc['bookmaker'],
                        'reasoning': f'Safe bet: {combined_home:.0f}% home + {combined_draw:.0f}% draw'
                    })
            
            # X2
            if combined_away + combined_draw >= 60 and dc['X2'] >= 1.08 and dc['X2'] <= 1.8:
                dc_prob = combined_away + combined_draw
                ev = ((dc_prob / 100) * dc['X2']) - 1
                if ev > 0:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{away_team} or Draw',
                        'odds': round(dc['X2'], 2),
                        'confidence': min(dc_prob * 0.92, 85),
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.85 + (ev * 80),
                        'bookmaker': dc['bookmaker'],
                        'reasoning': f'Safe bet: {combined_away:.0f}% away + {combined_draw:.0f}% draw'
                    })
        
        if not all_bets:
            print(f"      ❌ No quality bets")
            return None
        
        # Sort by quality score and take TOP 3
        all_bets.sort(key=lambda x: x['quality_score'], reverse=True)
        top_3_bets = all_bets[:3]
        
        print(f"      ✅ Top 3 bets: {', '.join([b['selection'] for b in top_3_bets])}")
        
        return {
            'fixture_id': fixture_id,
            'home_team': home_team,
            'away_team': away_team,
            'league': league,
            'country': fixture['league']['country'],
            'match_time': match_time,
            'best_bets': top_3_bets,
            'all_bets': all_bets,
            'total_opportunities': len(all_bets)
        }

analyzer = None

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = FinalBettingAnalyzer(API_KEY)
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
        return jsonify({'success': False, 'error': 'Unable to connect'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis')
def get_analysis():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'API key not configured'}), 400
    
    try:
        print("\n" + "="*80)
        print("FINAL ANALYSIS - TOP 3 BETS PER MATCH ACROSS ALL MARKETS")
        print("="*80)
        
        fixtures = get_analyzer().get_todays_fixtures()
        
        if not fixtures:
            return jsonify({
                'success': True,
                'count': 0,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'matches': [],
                'total_fixtures': 0,
                'message': 'No upcoming fixtures'
            })
        
        match_analyses = []
        
        for i, fixture in enumerate(fixtures, 1):
            print(f"\n[{i}/{len(fixtures)}]")
            analysis = get_analyzer().analyze_match(fixture)
            if analysis:
                match_analyses.append(analysis)
            if i % 5 == 0:
                import time
                time.sleep(0.5)
        
        print(f"\n{'='*80}")
        print(f"✅ {len(match_analyses)} matches with bets")
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
    print(f"\n🎯 FINAL Multi-Market Betting Analyzer")
    print(f"📊 Showing TOP 3 bets per match with CORRECT odds")
    app.run(host='0.0.0.0', port=port, debug=False)
