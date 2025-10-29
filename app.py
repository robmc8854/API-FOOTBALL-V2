#!/usr/bin/env python3
"""
COMPLETE Multi-Source Betting Analyzer
ACTUALLY uses ALL available data: API advice, form trends, H2H patterns, momentum, everything
"""

from flask import Flask, render_template, jsonify, request
import requests
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import re

app = Flask(__name__)

API_KEY = os.environ.get('API_SPORTS_KEY', '')
BASE_URL = "https://v3.football.api-sports.io"

class CompleteBettingAnalyzer:
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
        
        now = datetime.now(timezone.utc)
        upcoming = []
        
        for fixture in data['response']:
            try:
                fixture_time = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
                status = fixture['fixture']['status']['long']
                if fixture_time > now and status in ['Not Started', 'Time to be defined', 'NS']:
                    upcoming.append(fixture)
            except:
                continue
        
        print(f"Found {len(upcoming)} upcoming fixtures")
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
    
    def analyze_form_string(self, form_str: str) -> Dict:
        """Analyze form string like 'WWDLL' to get momentum"""
        if not form_str:
            return {'wins': 0, 'draws': 0, 'losses': 0, 'points': 0, 'momentum': 0}
        
        wins = form_str.count('W')
        draws = form_str.count('D')
        losses = form_str.count('L')
        points = wins * 3 + draws
        
        # Momentum: recent results weighted more (last match = 5x, first match = 1x)
        momentum = 0
        weights = [1, 2, 3, 4, 5]  # Earlier to later
        for i, result in enumerate(form_str[:5]):
            weight = weights[i] if i < len(weights) else 5
            if result == 'W':
                momentum += 3 * weight
            elif result == 'D':
                momentum += 1 * weight
        
        momentum = momentum / 45 * 100  # Normalize to percentage
        
        return {
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'points': points,
            'momentum': momentum,
            'string': form_str
        }
    
    def parse_api_advice(self, advice: str) -> Dict:
        """Parse API advice to boost relevant markets"""
        advice_lower = advice.lower() if advice else ''
        
        return {
            'suggests_home': 'home' in advice_lower or '1' in advice_lower,
            'suggests_away': 'away' in advice_lower or '2' in advice_lower,
            'suggests_draw': 'draw' in advice_lower or 'x' in advice_lower,
            'suggests_btts': 'both' in advice_lower or 'btts' in advice_lower,
            'suggests_over': 'over' in advice_lower,
            'suggests_under': 'under' in advice_lower,
            'suggests_double': 'double' in advice_lower or 'combo' in advice_lower,
            'raw': advice
        }
    
    def extract_all_odds(self, odds_response: Dict) -> Dict:
        """Extract all market odds"""
        bookmakers = odds_response.get('bookmakers', [])
        
        result = {
            'match_winner': {'home': 0, 'draw': 0, 'away': 0, 'bookmaker': '', 'has_10bet': False},
            'btts': {'yes': 0, 'no': 0, 'bookmaker': '', 'has_10bet': False},
            'over_under': {},
            'double_chance': {'1X': 0, '12': 0, 'X2': 0, 'bookmaker': '', 'has_10bet': False}
        }
        
        for bookmaker in bookmakers:
            bm_name = bookmaker.get('name', '')
            is_10bet = '10bet' in bm_name.lower() or bookmaker.get('id', 0) == 1
            
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
    
    def analyze_comprehensive(self, fixture: Dict) -> Optional[Dict]:
        """COMPLETE analysis using ALL data properly"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        country = fixture['league']['country']
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
        teams_data = pred_full.get('teams', {})
        comparison = pred_full.get('comparison', {})
        
        # === ALL PROBABILITIES ===
        percent = predictions.get('percent', {})
        ai_home = self.safe_float(percent.get('home', 0))
        ai_draw = self.safe_float(percent.get('draw', 0))
        ai_away = self.safe_float(percent.get('away', 0))
        
        poisson = comparison.get('poisson_distribution', {})
        poisson_home = self.safe_float(poisson.get('home', 0))
        poisson_draw = self.safe_float(poisson.get('draw', 0))
        poisson_away = self.safe_float(poisson.get('away', 0))
        
        h2h = comparison.get('h2h', {})
        h2h_home = self.safe_float(h2h.get('home', 0))
        h2h_draw = self.safe_float(h2h.get('draw', 0))
        h2h_away = self.safe_float(h2h.get('away', 0))
        
        market = self.calculate_market_probabilities(odds_response)
        
        # === FORM ANALYSIS (NEW!) ===
        home_team_data = teams_data.get('home', {})
        away_team_data = teams_data.get('away', {})
        
        home_last5 = home_team_data.get('last_5', {})
        away_last5 = away_team_data.get('last_5', {})
        
        home_form = self.analyze_form_string(home_last5.get('form', ''))
        away_form = self.analyze_form_string(away_last5.get('form', ''))
        
        home_last5_att = self.safe_float(home_last5.get('att', 50))
        away_last5_att = self.safe_float(away_last5.get('att', 50))
        home_last5_def = self.safe_float(home_last5.get('def', 50))
        away_last5_def = self.safe_float(away_last5.get('def', 50))
        
        # === COMPARISON STATS (NEW!) ===
        form_comp = comparison.get('form', {})
        att_comp = comparison.get('att', {})
        def_comp = comparison.get('def', {})
        total_comp = comparison.get('total', {})
        
        form_home_pct = self.safe_float(form_comp.get('home', 50))
        form_away_pct = self.safe_float(form_comp.get('away', 50))
        att_home = self.safe_float(att_comp.get('home', 50))
        att_away = self.safe_float(att_comp.get('away', 50))
        def_home = self.safe_float(def_comp.get('home', 50))
        def_away = self.safe_float(def_comp.get('away', 50))
        total_home = self.safe_float(total_comp.get('home', 50))
        total_away = self.safe_float(total_comp.get('away', 50))
        
        # === API RECOMMENDATIONS (NEW!) ===
        api_winner = predictions.get('winner', {}).get('name', '')
        api_advice_raw = predictions.get('advice', '')
        api_advice = self.parse_api_advice(api_advice_raw)
        api_under_over = predictions.get('under_over', '')
        win_or_draw = predictions.get('win_or_draw', False)
        
        # === GOALS DATA ===
        goals_pred = predictions.get('goals', {})
        home_goals_str = goals_pred.get('home', '0-0')
        away_goals_str = goals_pred.get('away', '0-0')
        
        home_goals_parts = home_goals_str.split('-')
        away_goals_parts = away_goals_str.split('-')
        home_goals_avg = (self.safe_float(home_goals_parts[0]) + self.safe_float(home_goals_parts[1] if len(home_goals_parts) > 1 else home_goals_parts[0])) / 2
        away_goals_avg_pred = (self.safe_float(away_goals_parts[0]) + self.safe_float(away_goals_parts[1] if len(away_goals_parts) > 1 else away_goals_parts[0])) / 2
        predicted_total = home_goals_avg + away_goals_avg_pred
        
        # === TEAM LEAGUE STATS ===
        home_league = home_team_data.get('league', {})
        away_league = away_team_data.get('league', {})
        
        home_clean_sheets = self.safe_float(home_league.get('clean_sheet', {}).get('total', 0))
        away_clean_sheets = self.safe_float(away_league.get('clean_sheet', {}).get('total', 0))
        home_failed_score = self.safe_float(home_league.get('failed_to_score', {}).get('total', 0))
        away_failed_score = self.safe_float(away_league.get('failed_to_score', {}).get('total', 0))
        
        home_goals_for_avg = self.safe_float(home_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 0))
        away_goals_for_avg = self.safe_float(away_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 0))
        
        # === WEIGHTED COMBINED PROBABILITY (Using momentum!) ===
        # Base: Poisson 30%, AI 25%, Market 20%, H2H 10%
        # Momentum boost: Up to 15% shift based on form
        momentum_diff = (home_form['momentum'] - away_form['momentum']) / 100 * 15
        
        combined_home = (poisson_home * 0.30 + ai_home * 0.25 + market['home'] * 0.20 + 
                        h2h_home * 0.10 + form_home_pct * 0.15) + momentum_diff
        combined_draw = (poisson_draw * 0.30 + ai_draw * 0.25 + market['draw'] * 0.20 + 
                        h2h_draw * 0.10 + (100 - abs(form_home_pct - form_away_pct)) * 0.15)
        combined_away = (poisson_away * 0.30 + ai_away * 0.25 + market['away'] * 0.20 + 
                        h2h_away * 0.10 + form_away_pct * 0.15) - momentum_diff
        
        # Normalize
        total_prob = combined_home + combined_draw + combined_away
        if total_prob > 0:
            combined_home = (combined_home / total_prob) * 100
            combined_draw = (combined_draw / total_prob) * 100
            combined_away = (combined_away / total_prob) * 100
        
        print(f"      🤖 API: {api_winner} | Advice: '{api_advice_raw}'")
        print(f"      📊 Combined: H:{combined_home:.1f}% D:{combined_draw:.1f}% A:{combined_away:.1f}%")
        print(f"      🔥 Momentum: H:{home_form['momentum']:.0f}% ({home_form['string']}) | A:{away_form['momentum']:.0f}% ({away_form['string']})")
        print(f"      ⚽ Predicted: {predicted_total:.1f} goals")
        
        all_odds = self.extract_all_odds(odds_response)
        all_bets = []
        
        # ========== MATCH WINNER (With API advice boost!) ==========
        mw = all_odds['match_winner']
        if mw['home'] > 0:
            # Home Win
            home_boost = 10 if api_advice['suggests_home'] else 0
            if (combined_home >= 42 and 
                combined_home > market['home'] and
                mw['home'] >= 1.3 and mw['home'] <= 5.0):
                
                confidence = min(combined_home + home_boost, 90)
                impl_prob = (1 / mw['home']) * 100
                ev = ((confidence / 100) * mw['home']) - 1
                
                if ev > 0.02:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{home_team} Win',
                        'odds': mw['home'],
                        'confidence': confidence,
                        'ai_probability': combined_home,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence + (ev * 150) + home_boost,
                        'api_agrees': api_advice['suggests_home'],
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Weighted: Poisson {poisson_home:.0f}% + AI {ai_home:.0f}% + Market {market["home"]:.0f}% + Momentum {home_form["momentum"]:.0f}%{" + API BOOST" if api_advice["suggests_home"] else ""}'
                    })
            
            # Away Win
            away_boost = 10 if api_advice['suggests_away'] else 0
            if (combined_away >= 42 and
                combined_away > market['away'] and
                mw['away'] >= 1.3 and mw['away'] <= 5.0):
                
                confidence = min(combined_away + away_boost, 90)
                impl_prob = (1 / mw['away']) * 100
                ev = ((confidence / 100) * mw['away']) - 1
                
                if ev > 0.02:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{away_team} Win',
                        'odds': mw['away'],
                        'confidence': confidence,
                        'ai_probability': combined_away,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence + (ev * 150) + away_boost,
                        'api_agrees': api_advice['suggests_away'],
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Weighted: Poisson {poisson_away:.0f}% + AI {ai_away:.0f}% + Market {market["away"]:.0f}% + Momentum {away_form["momentum"]:.0f}%{" + API BOOST" if api_advice["suggests_away"] else ""}'
                    })
            
            # Draw
            draw_boost = 10 if api_advice['suggests_draw'] else 0
            if (combined_draw >= 23 and
                combined_draw > market['draw'] + 2 and
                mw['draw'] >= 2.8 and mw['draw'] <= 5.5):
                
                confidence = min((combined_draw + draw_boost) * 0.9, 78)
                impl_prob = (1 / mw['draw']) * 100
                ev = ((confidence / 100) * mw['draw']) - 1
                
                if ev > 0.04:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': 'Draw',
                        'odds': mw['draw'],
                        'confidence': confidence,
                        'ai_probability': combined_draw,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence * 0.9 + (ev * 140) + draw_boost,
                        'api_agrees': api_advice['suggests_draw'],
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Evenly matched. Poisson {poisson_draw:.0f}% + H2H {h2h_draw:.0f}%{" + API BOOST" if api_advice["suggests_draw"] else ""}'
                    })
        
        # ========== BTTS (With API boost!) ==========
        btts = all_odds['btts']
        if btts['yes'] > 0:
            btts_boost = 8 if api_advice['suggests_btts'] else 0
            
            # BTTS Yes - using ALL stats
            btts_yes_prob = 50
            if home_goals_for_avg >= 0.7 and away_goals_for_avg >= 0.7:
                scoring_factor = ((home_goals_for_avg + away_goals_for_avg) / 3.0) * 100
                clean_factor = 100 - ((home_clean_sheets + away_clean_sheets) * 2)
                attack_factor = ((home_last5_att + away_last5_att) / 200) * 100
                btts_yes_prob = min((scoring_factor * 0.5 + clean_factor * 0.3 + attack_factor * 0.2), 80) + btts_boost
            
            if (btts_yes_prob >= 50 and
                home_failed_score <= 8 and away_failed_score <= 8 and
                btts['yes'] >= 1.4 and btts['yes'] <= 3.0):
                
                impl_prob = (1 / btts['yes']) * 100
                ev = ((btts_yes_prob / 100) * btts['yes']) - 1
                
                if ev > 0.02:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'Yes',
                        'odds': btts['yes'],
                        'confidence': min(btts_yes_prob, 82),
                        'ai_probability': btts_yes_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_yes_prob + (ev * 150) + btts_boost,
                        'api_agrees': api_advice['suggests_btts'],
                        'market_agrees': True,
                        'bookmaker': btts['bookmaker'],
                        'has_10bet': btts['has_10bet'],
                        'reasoning': f'Goals: H{home_goals_for_avg:.1f} A{away_goals_for_avg:.1f}. Attack: H{home_last5_att:.0f}% A{away_last5_att:.0f}%. Failed: H:{home_failed_score} A:{away_failed_score}{" + API" if api_advice["suggests_btts"] else ""}'
                    })
            
            # BTTS No
            btts_no_prob = 50
            if home_failed_score >= 5 or away_failed_score >= 5 or home_clean_sheets >= 5 or away_clean_sheets >= 5:
                defensive_factor = ((home_clean_sheets + away_clean_sheets) * 3)
                weak_attack = ((home_failed_score + away_failed_score) * 2)
                btts_no_prob = min(50 + defensive_factor + weak_attack, 80)
            
            if (btts_no_prob >= 52 and
                btts['no'] >= 1.4 and btts['no'] <= 3.0):
                
                impl_prob = (1 / btts['no']) * 100
                ev = ((btts_no_prob / 100) * btts['no']) - 1
                
                if ev > 0.02:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'No',
                        'odds': btts['no'],
                        'confidence': min(btts_no_prob, 80),
                        'ai_probability': btts_no_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_no_prob + (ev * 150),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': btts['bookmaker'],
                        'has_10bet': btts['has_10bet'],
                        'reasoning': f'Strong defense/weak attack. Clean: H{home_clean_sheets} A{away_clean_sheets}. Failed: H{home_failed_score} A{away_failed_score}'
                    })
        
        # ========== OVER/UNDER (With API boost!) ==========
        for line, ou in all_odds['over_under'].items():
            if ou['over'] == 0 or ou['under'] == 0:
                continue
            
            try:
                line_float = float(line)
                
                # Use predicted total + attack strength
                expected_goals = predicted_total
                attack_boost = ((att_home + att_away) / 100 - 1) * 0.4
                expected_goals += attack_boost
                
                # API boost
                ou_boost = 0
                if api_under_over:
                    if 'Over' in api_under_over and line in api_under_over:
                        ou_boost = 8
                    elif 'Under' in api_under_over and line in api_under_over:
                        ou_boost = 8
                
                # Over
                if expected_goals > line_float + 0.25:
                    over_prob = min(52 + (expected_goals - line_float) * 11, 80)
                    if 'Over' in str(api_under_over) and line in str(api_under_over):
                        over_prob += ou_boost
                    
                    if ou['over'] >= 1.5 and ou['over'] <= 2.6:
                        impl_prob = (1 / ou['over']) * 100
                        ev = ((over_prob / 100) * ou['over']) - 1
                        
                        if ev > 0.02:
                            all_bets.append({
                                'market': f'Over/Under {line}',
                                'selection': f'Over {line}',
                                'odds': ou['over'],
                                'confidence': min(over_prob, 82),
                                'ai_probability': over_prob,
                                'implied_probability': impl_prob,
                                'expected_value': ev,
                                'quality_score': over_prob + (ev * 150) + ou_boost,
                                'api_agrees': 'Over' in str(api_under_over),
                                'market_agrees': True,
                                'bookmaker': ou['bookmaker'],
                                'has_10bet': ou['has_10bet'],
                                'reasoning': f'Expected {expected_goals:.1f} goals. Attack: H{att_home:.0f}% A{att_away:.0f}%. Recent: H{home_last5_att:.0f}% A{away_last5_att:.0f}%{" + API" if ou_boost > 0 else ""}'
                            })
                
                # Under
                elif expected_goals < line_float - 0.25:
                    under_prob = min(52 + (line_float - expected_goals) * 11, 80)
                    if 'Under' in str(api_under_over) and line in str(api_under_over):
                        under_prob += ou_boost
                    
                    if ou['under'] >= 1.5 and ou['under'] <= 2.6:
                        impl_prob = (1 / ou['under']) * 100
                        ev = ((under_prob / 100) * ou['under']) - 1
                        
                        if ev > 0.02:
                            all_bets.append({
                                'market': f'Over/Under {line}',
                                'selection': f'Under {line}',
                                'odds': ou['under'],
                                'confidence': min(under_prob, 82),
                                'ai_probability': under_prob,
                                'implied_probability': impl_prob,
                                'expected_value': ev,
                                'quality_score': under_prob + (ev * 150) + ou_boost,
                                'api_agrees': 'Under' in str(api_under_over),
                                'market_agrees': True,
                                'bookmaker': ou['bookmaker'],
                                'has_10bet': ou['has_10bet'],
                                'reasoning': f'Expected {expected_goals:.1f} goals. Defense: H{def_home:.0f}% A{def_away:.0f}%. Recent: H{home_last5_def:.0f}% A{away_last5_def:.0f}%{" + API" if ou_boost > 0 else ""}'
                            })
            except:
                continue
        
        # ========== DOUBLE CHANCE (With API boost!) ==========
        dc = all_odds['double_chance']
        if dc['1X'] > 0:
            dc_boost = 8 if api_advice['suggests_double'] else 0
            
            # 1X
            if combined_home + combined_draw >= 62 and dc['1X'] >= 1.08 and dc['1X'] <= 1.9:
                dc_prob = combined_home + combined_draw + dc_boost
                impl_prob = (1 / dc['1X']) * 100
                ev = ((dc_prob / 100) * dc['1X']) - 1
                
                if ev > 0.01:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or Draw',
                        'odds': dc['1X'],
                        'confidence': min(dc_prob * 0.92, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.88 + (ev * 130) + dc_boost,
                        'api_agrees': api_advice['suggests_double'],
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Safe: Home {combined_home:.0f}% + Draw {combined_draw:.0f}%{" + API DOUBLE" if api_advice["suggests_double"] else ""}'
                    })
            
            # X2
            if combined_away + combined_draw >= 62 and dc['X2'] >= 1.08 and dc['X2'] <= 1.9:
                dc_prob = combined_away + combined_draw + dc_boost
                impl_prob = (1 / dc['X2']) * 100
                ev = ((dc_prob / 100) * dc['X2']) - 1
                
                if ev > 0.01:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{away_team} or Draw',
                        'odds': dc['X2'],
                        'confidence': min(dc_prob * 0.92, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.88 + (ev * 130) + dc_boost,
                        'api_agrees': api_advice['suggests_double'],
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Safe: Away {combined_away:.0f}% + Draw {combined_draw:.0f}%{" + API DOUBLE" if api_advice["suggests_double"] else ""}'
                    })
            
            # 12
            if combined_home + combined_away >= 68 and combined_draw < 27 and dc['12'] >= 1.06 and dc['12'] <= 1.7:
                dc_prob = combined_home + combined_away
                impl_prob = (1 / dc['12']) * 100
                ev = ((dc_prob / 100) * dc['12']) - 1
                
                if ev > 0.01:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or {away_team}',
                        'odds': dc['12'],
                        'confidence': min(dc_prob * 0.92, 88),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.88 + (ev * 130),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Draw unlikely {combined_draw:.0f}%. Either team wins'
                    })
        
        if not all_bets:
            print(f"      ❌ No quality bets")
            return None
        
        all_bets.sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"      ✅ {len(all_bets)} bets found")
        
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
        analyzer = CompleteBettingAnalyzer(API_KEY)
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
        print("COMPLETE ANALYSIS - USING ALL DATA PROPERLY")
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
            analysis = get_analyzer().analyze_comprehensive(fixture)
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
    print(f"\n🧠 COMPLETE Multi-Source Betting Analyzer")
    print(f"📊 Using: Poisson, AI, Market, H2H, Form Momentum, Attack/Defense, API Advice")
    app.run(host='0.0.0.0', port=port, debug=False)
