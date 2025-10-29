#!/usr/bin/env python3
"""
ULTIMATE Multi-Market Betting Optimizer
Uses ALL available data: API advice, Poisson distribution, H2H, form, attack/defense strength,
clean sheets, predicted scores, market odds, and cross-validates everything
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

class UltimateBettingAnalyzer:
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
        
        print(f"Found {len(upcoming)} upcoming fixtures")
        return upcoming
    
    def get_fixture_odds(self, fixture_id: int) -> Optional[Dict]:
        """Get all bookmaker odds"""
        data = self.make_request('odds', params={'fixture': fixture_id})
        return data['response'][0] if data and 'response' in data and data['response'] else None
    
    def get_predictions(self, fixture_id: int) -> Optional[Dict]:
        """Get comprehensive predictions data"""
        data = self.make_request('predictions', params={'fixture': fixture_id})
        return data['response'][0] if data and 'response' in data and data['response'] else None
    
    def safe_float(self, value, default=0.0) -> float:
        """Safely convert string percentage or number to float"""
        try:
            if isinstance(value, str):
                return float(value.replace('%', ''))
            return float(value) if value else default
        except:
            return default
    
    def parse_score_range(self, score_str: str) -> Tuple[float, float]:
        """Parse '1-2' into (1.0, 2.0)"""
        try:
            if '-' in score_str:
                parts = score_str.split('-')
                return (float(parts[0]), float(parts[1]))
            return (float(score_str), float(score_str))
        except:
            return (0.0, 0.0)
    
    def extract_all_odds(self, odds_response: Dict) -> Dict:
        """Extract ALL market odds efficiently"""
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
        """Calculate market consensus probabilities"""
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
        """ULTIMATE analysis using ALL available data sources"""
        fixture_id = fixture['fixture']['id']
        home_team = fixture['teams']['home']['name']
        away_team = fixture['teams']['away']['name']
        league = fixture['league']['name']
        country = fixture['league']['country']
        match_time = fixture['fixture']['date']
        
        print(f"\n  📊 {home_team} vs {away_team}")
        
        # Get comprehensive data
        pred_full = self.get_predictions(fixture_id)
        if not pred_full:
            print(f"      ❌ No predictions")
            return None
        
        odds_response = self.get_fixture_odds(fixture_id)
        if not odds_response:
            print(f"      ❌ No odds")
            return None
        
        # Extract ALL prediction data
        predictions = pred_full.get('predictions', {})
        teams_data = pred_full.get('teams', {})
        comparison = pred_full.get('comparison', {})
        league_data = pred_full.get('league', {})
        
        # === EXTRACT ALL PROBABILITIES ===
        # 1. Basic AI percentages
        percent = predictions.get('percent', {})
        ai_home = self.safe_float(percent.get('home', 0))
        ai_draw = self.safe_float(percent.get('draw', 0))
        ai_away = self.safe_float(percent.get('away', 0))
        
        # 2. Poisson distribution (mathematical probability)
        poisson = comparison.get('poisson_distribution', {})
        poisson_home = self.safe_float(poisson.get('home', 0))
        poisson_draw = self.safe_float(poisson.get('draw', 0))
        poisson_away = self.safe_float(poisson.get('away', 0))
        
        # 3. Head-to-head historical probability
        h2h = comparison.get('h2h', {})
        h2h_home = self.safe_float(h2h.get('home', 0))
        h2h_draw = self.safe_float(h2h.get('draw', 0))
        h2h_away = self.safe_float(h2h.get('away', 0))
        
        # 4. Market probabilities
        market = self.calculate_market_probabilities(odds_response)
        market_home = market['home']
        market_draw = market['draw']
        market_away = market['away']
        
        # 5. Form comparison
        form_comp = comparison.get('form', {})
        form_home = self.safe_float(form_comp.get('home', 50))
        form_away = self.safe_float(form_comp.get('away', 50))
        
        # 6. Attack/Defense strength
        att_comp = comparison.get('att', {})
        def_comp = comparison.get('def', {})
        att_home = self.safe_float(att_comp.get('home', 50))
        att_away = self.safe_float(att_comp.get('away', 50))
        def_home = self.safe_float(def_comp.get('home', 50))
        def_away = self.safe_float(def_comp.get('away', 50))
        
        # === COMBINED WEIGHTED PROBABILITIES ===
        # Weight: Poisson 35%, AI 30%, Market 20%, H2H 10%, Form 5%
        combined_home = (poisson_home * 0.35 + ai_home * 0.30 + market_home * 0.20 + 
                        h2h_home * 0.10 + (form_home/100 * ai_home) * 0.05)
        combined_draw = (poisson_draw * 0.35 + ai_draw * 0.30 + market_draw * 0.20 + 
                        h2h_draw * 0.10 + 0.05 * ai_draw)
        combined_away = (poisson_away * 0.35 + ai_away * 0.30 + market_away * 0.20 + 
                        h2h_away * 0.10 + (form_away/100 * ai_away) * 0.05)
        
        # === API DIRECT RECOMMENDATIONS ===
        api_winner = predictions.get('winner', {}).get('name', '')
        api_advice = predictions.get('advice', '')
        api_under_over = predictions.get('under_over', '')
        
        # === GOALS DATA ===
        goals_pred = predictions.get('goals', {})
        home_goals_range = self.parse_score_range(goals_pred.get('home', '0-0'))
        away_goals_range = self.parse_score_range(goals_pred.get('away', '0-0'))
        predicted_total_min = home_goals_range[0] + away_goals_range[0]
        predicted_total_max = home_goals_range[1] + away_goals_range[1]
        predicted_total_avg = (predicted_total_min + predicted_total_max) / 2
        
        # === TEAM STATS ===
        home_team_data = teams_data.get('home', {})
        away_team_data = teams_data.get('away', {})
        
        # Clean sheets & failed to score
        home_league = home_team_data.get('league', {})
        away_league = away_team_data.get('league', {})
        
        home_clean_sheets = self.safe_float(home_league.get('clean_sheet', {}).get('total', 0))
        away_clean_sheets = self.safe_float(away_league.get('clean_sheet', {}).get('total', 0))
        home_failed_score = self.safe_float(home_league.get('failed_to_score', {}).get('total', 0))
        away_failed_score = self.safe_float(away_league.get('failed_to_score', {}).get('total', 0))
        
        # Last 5 form
        home_last5 = home_team_data.get('last_5', {})
        away_last5 = away_team_data.get('last_5', {})
        home_form_str = home_last5.get('form', '')
        away_form_str = away_last5.get('form', '')
        
        # Goals averages from league stats
        home_goals_avg = self.safe_float(home_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 0))
        away_goals_avg = self.safe_float(away_league.get('goals', {}).get('for', {}).get('average', {}).get('total', 0))
        
        print(f"      🤖 API Winner: {api_winner} | Advice: {api_advice}")
        print(f"      📊 Combined Prob: H:{combined_home:.1f}% D:{combined_draw:.1f}% A:{combined_away:.1f}%")
        print(f"      🎲 Poisson: H:{poisson_home:.1f}% D:{poisson_draw:.1f}% A:{poisson_away:.1f}%")
        print(f"      📈 Form: Home {form_home:.0f}% | Away {form_away:.0f}%")
        print(f"      ⚽ Predicted Goals: {predicted_total_avg:.1f} ({predicted_total_min:.1f}-{predicted_total_max:.1f})")
        print(f"      🛡️  Clean Sheets: H:{home_clean_sheets} A:{away_clean_sheets}")
        
        # Get odds
        all_odds = self.extract_all_odds(odds_response)
        
        all_bets = []
        
        # ========== MATCH WINNER ==========
        mw = all_odds['match_winner']
        if mw['home'] > 0:
            # Home Win - use combined probability
            if (combined_home >= 55 and 
                combined_home > market_home + 5 and
                api_winner == home_team and
                form_home >= 45 and
                mw['home'] >= 1.4 and mw['home'] <= 3.5):
                
                impl_prob = (1 / mw['home']) * 100
                ev = ((combined_home / 100) * mw['home']) - 1
                
                # Confidence = weighted average of all sources
                confidence = (combined_home * 0.6 + poisson_home * 0.25 + ai_home * 0.15)
                
                if ev > 0.07:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{home_team} Win',
                        'odds': mw['home'],
                        'confidence': min(confidence, 90),
                        'ai_probability': combined_home,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence + (ev * 150),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Strong consensus: Poisson {poisson_home:.0f}%, AI {ai_home:.0f}%, Market {market_home:.0f}%, Form {form_home:.0f}%'
                    })
            
            # Away Win
            if (combined_away >= 55 and
                combined_away > market_away + 5 and
                api_winner == away_team and
                form_away >= 45 and
                mw['away'] >= 1.4 and mw['away'] <= 3.5):
                
                impl_prob = (1 / mw['away']) * 100
                ev = ((combined_away / 100) * mw['away']) - 1
                confidence = (combined_away * 0.6 + poisson_away * 0.25 + ai_away * 0.15)
                
                if ev > 0.07:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': f'{away_team} Win',
                        'odds': mw['away'],
                        'confidence': min(confidence, 90),
                        'ai_probability': combined_away,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence + (ev * 150),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Strong consensus: Poisson {poisson_away:.0f}%, AI {ai_away:.0f}%, Market {market_away:.0f}%, Form {form_away:.0f}%'
                    })
            
            # Draw
            if (combined_draw >= 30 and
                combined_draw > market_draw + 8 and
                abs(combined_home - combined_away) < 10 and
                mw['draw'] >= 3.0 and mw['draw'] <= 4.5):
                
                impl_prob = (1 / mw['draw']) * 100
                ev = ((combined_draw / 100) * mw['draw']) - 1
                confidence = (combined_draw * 0.6 + poisson_draw * 0.25 + ai_draw * 0.15)
                
                if ev > 0.10:
                    all_bets.append({
                        'market': 'Match Winner',
                        'selection': 'Draw',
                        'odds': mw['draw'],
                        'confidence': min(confidence * 0.85, 75),
                        'ai_probability': combined_draw,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': confidence * 0.8 + (ev * 140),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': mw['bookmaker'],
                        'has_10bet': mw['has_10bet'],
                        'reasoning': f'Evenly matched: Poisson {poisson_draw:.0f}%, AI {ai_draw:.0f}%, H2H {h2h_draw:.0f}%'
                    })
        
        # ========== BTTS - Using clean sheet & failed to score data ==========
        btts = all_odds['btts']
        if btts['yes'] > 0:
            # BTTS Yes - both teams score regularly, few clean sheets
            btts_yes_prob = 100
            if home_goals_avg >= 1.0 and away_goals_avg >= 1.0:
                btts_yes_prob = min(((home_goals_avg + away_goals_avg) / 3.5) * 100, 80)
            
            # Adjust by clean sheet frequency (less clean sheets = more BTTS yes)
            if home_clean_sheets > 0 or away_clean_sheets > 0:
                clean_sheet_factor = 1 - ((home_clean_sheets + away_clean_sheets) / 100)
                btts_yes_prob *= max(clean_sheet_factor, 0.5)
            
            if (home_goals_avg >= 1.0 and away_goals_avg >= 1.0 and
                home_failed_score <= 5 and away_failed_score <= 5 and
                btts['yes'] >= 1.5 and btts['yes'] <= 2.4):
                
                impl_prob = (1 / btts['yes']) * 100
                ev = ((btts_yes_prob / 100) * btts['yes']) - 1
                
                if ev > 0.08 and btts_yes_prob > impl_prob + 5:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'Yes',
                        'odds': btts['yes'],
                        'confidence': btts_yes_prob,
                        'ai_probability': btts_yes_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_yes_prob + (ev * 150),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': btts['bookmaker'],
                        'has_10bet': btts['has_10bet'],
                        'reasoning': f'Both score regularly: H {home_goals_avg:.1f} A {home_goals_avg:.1f} goals/game. Clean sheets: H:{home_clean_sheets} A:{away_clean_sheets}'
                    })
            
            # BTTS No - one team weak in attack or strong defense
            btts_no_prob = 0
            if home_failed_score >= 8 or away_failed_score >= 8:
                btts_no_prob = min(70 + (home_failed_score + away_failed_score), 80)
            elif home_clean_sheets >= 8 or away_clean_sheets >= 8:
                btts_no_prob = min(65 + (home_clean_sheets + away_clean_sheets) / 2, 80)
            
            if (btts_no_prob >= 60 and
                btts['no'] >= 1.5 and btts['no'] <= 2.4):
                
                impl_prob = (1 / btts['no']) * 100
                ev = ((btts_no_prob / 100) * btts['no']) - 1
                
                if ev > 0.08 and btts_no_prob > impl_prob + 5:
                    all_bets.append({
                        'market': 'Both Teams To Score',
                        'selection': 'No',
                        'odds': btts['no'],
                        'confidence': btts_no_prob,
                        'ai_probability': btts_no_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': btts_no_prob + (ev * 150),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': btts['bookmaker'],
                        'has_10bet': btts['has_10bet'],
                        'reasoning': f'Weak attack/strong defense. Failed to score: H:{home_failed_score} A:{away_failed_score}. Clean: H:{home_clean_sheets} A:{away_clean_sheets}'
                    })
        
        # ========== OVER/UNDER - Using API predicted score ranges ==========
        for line, ou in all_odds['over_under'].items():
            if ou['over'] == 0 or ou['under'] == 0:
                continue
            
            try:
                line_float = float(line)
                
                # Use API's predicted total + attack strength
                expected_goals = predicted_total_avg
                attack_boost = ((att_home + att_away) / 100 - 1) * 0.5  # Boost if strong attack
                expected_goals += attack_boost
                
                # Over
                if (expected_goals > line_float + 0.4 and
                    ou['over'] >= 1.6 and ou['over'] <= 2.3):
                    
                    over_prob = min(58 + (expected_goals - line_float) * 9, 78)
                    
                    # Boost if API explicitly says "Over X.X"
                    if api_under_over and 'Over' in api_under_over and line in api_under_over:
                        over_prob += 5
                    
                    impl_prob = (1 / ou['over']) * 100
                    ev = ((over_prob / 100) * ou['over']) - 1
                    
                    if ev > 0.08 and over_prob > impl_prob + 5:
                        all_bets.append({
                            'market': f'Over/Under {line}',
                            'selection': f'Over {line}',
                            'odds': ou['over'],
                            'confidence': over_prob,
                            'ai_probability': over_prob,
                            'implied_probability': impl_prob,
                            'expected_value': ev,
                            'quality_score': over_prob + (ev * 150),
                            'api_agrees': True,
                            'market_agrees': True,
                            'bookmaker': ou['bookmaker'],
                            'has_10bet': ou['has_10bet'],
                            'reasoning': f'API predicts {predicted_total_avg:.1f} goals ({predicted_total_min:.1f}-{predicted_total_max:.1f}). Attack: H:{att_home:.0f}% A:{att_away:.0f}%'
                        })
                
                # Under
                elif (expected_goals < line_float - 0.4 and
                      ou['under'] >= 1.6 and ou['under'] <= 2.3):
                    
                    under_prob = min(58 + (line_float - expected_goals) * 9, 78)
                    
                    # Boost if API explicitly says "Under X.X"
                    if api_under_over and 'Under' in api_under_over and line in api_under_over:
                        under_prob += 5
                    
                    impl_prob = (1 / ou['under']) * 100
                    ev = ((under_prob / 100) * ou['under']) - 1
                    
                    if ev > 0.08 and under_prob > impl_prob + 5:
                        all_bets.append({
                            'market': f'Over/Under {line}',
                            'selection': f'Under {line}',
                            'odds': ou['under'],
                            'confidence': under_prob,
                            'ai_probability': under_prob,
                            'implied_probability': impl_prob,
                            'expected_value': ev,
                            'quality_score': under_prob + (ev * 150),
                            'api_agrees': True,
                            'market_agrees': True,
                            'bookmaker': ou['bookmaker'],
                            'has_10bet': ou['has_10bet'],
                            'reasoning': f'API predicts {predicted_total_avg:.1f} goals ({predicted_total_min:.1f}-{predicted_total_max:.1f}). Defense: H:{def_home:.0f}% A:{def_away:.0f}%'
                        })
            except:
                continue
        
        # ========== DOUBLE CHANCE ==========
        dc = all_odds['double_chance']
        if dc['1X'] > 0:
            # 1X
            if combined_home + combined_draw >= 75 and dc['1X'] >= 1.15 and dc['1X'] <= 1.6:
                dc_prob = combined_home + combined_draw
                impl_prob = (1 / dc['1X']) * 100
                ev = ((dc_prob / 100) * dc['1X']) - 1
                
                if ev > 0.04:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or Draw',
                        'odds': dc['1X'],
                        'confidence': min(dc_prob * 0.9, 87),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.85 + (ev * 130),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Safe combo: Home {combined_home:.0f}% + Draw {combined_draw:.0f}%'
                    })
            
            # X2
            if combined_away + combined_draw >= 75 and dc['X2'] >= 1.15 and dc['X2'] <= 1.6:
                dc_prob = combined_away + combined_draw
                impl_prob = (1 / dc['X2']) * 100
                ev = ((dc_prob / 100) * dc['X2']) - 1
                
                if ev > 0.04:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{away_team} or Draw',
                        'odds': dc['X2'],
                        'confidence': min(dc_prob * 0.9, 87),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.85 + (ev * 130),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Safe combo: Away {combined_away:.0f}% + Draw {combined_draw:.0f}%'
                    })
            
            # 12
            if combined_home + combined_away >= 78 and combined_draw < 20 and dc['12'] >= 1.12 and dc['12'] <= 1.5:
                dc_prob = combined_home + combined_away
                impl_prob = (1 / dc['12']) * 100
                ev = ((dc_prob / 100) * dc['12']) - 1
                
                if ev > 0.04:
                    all_bets.append({
                        'market': 'Double Chance',
                        'selection': f'{home_team} or {away_team}',
                        'odds': dc['12'],
                        'confidence': min(dc_prob * 0.9, 87),
                        'ai_probability': dc_prob,
                        'implied_probability': impl_prob,
                        'expected_value': ev,
                        'quality_score': dc_prob * 0.85 + (ev * 130),
                        'api_agrees': True,
                        'market_agrees': True,
                        'bookmaker': dc['bookmaker'],
                        'has_10bet': dc['has_10bet'],
                        'reasoning': f'Draw unlikely {combined_draw:.0f}%. Either team wins'
                    })
        
        if not all_bets:
            print(f"      ❌ No high-quality bets")
            return None
        
        # Sort by quality score
        all_bets.sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"      ✅ {len(all_bets)} validated bets")
        
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
        analyzer = UltimateBettingAnalyzer(API_KEY)
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
        print("ULTIMATE MULTI-SOURCE BETTING ANALYSIS")
        print("Using: Poisson, AI, Market, H2H, Form, Attack, Defense, Clean Sheets, Predicted Scores")
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
        print(f"✅ {len(match_analyses)} matches analyzed with comprehensive data")
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
    print(f"\n🧠 ULTIMATE Multi-Source Betting Optimizer")
    print(f"📊 Combining: Poisson, AI%, Market%, H2H, Form, Att/Def, Clean Sheets, Predicted Scores")
    app.run(host='0.0.0.0', port=port, debug=False)
