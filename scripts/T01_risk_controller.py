#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 风控系统模块（简化版）
功能：
1. 情绪周期风控
2. 大盘走势风控
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
RISK_CONFIG_FILE = os.path.join(DATA_BASE_DIR, "risk_config.json")
RISK_STATUS_FILE = os.path.join(DATA_BASE_DIR, "risk_status.json")


class RiskController:
    """风控管理器（简化版）"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.config = self._load_or_create_config()
        self.status = self._load_or_create_status()
    
    def _load_or_create_config(self) -> Dict:
        """加载或创建风控配置"""
        if os.path.exists(RISK_CONFIG_FILE):
            with open(RISK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 简化的风控配置
        default_config = {
            'version': 2,
            'created_at': datetime.now().isoformat(),
            'description': '简化版风控：情绪周期 + 大盘走势',
            
            # 情绪周期风控
            'emotion': {
                'ice_point': {'min': 0, 'max': 20, 'position': 0.0, 'name': '冰点期'},
                'depression': {'min': 20, 'max': 40, 'position': 0.2, 'name': '低迷期'},
                'stable': {'min': 40, 'max': 60, 'position': 0.5, 'name': '平稳期'},
                'good': {'min': 60, 'max': 80, 'position': 0.8, 'name': '良好期'},
                'euphoria': {'min': 80, 'max': 100, 'position': 1.0, 'name': '高涨期'}
            },
            
            # 大盘风控
            'market': {
                'enabled': True,
                'rules': {
                    'break_ma20': {'position': 0.3, 'name': '跌破20日均线'},
                    'break_ma10': {'position': 0.5, 'name': '跌破10日均线'},
                    'break_ma5': {'position': 0.7, 'name': '跌破5日均线'},
                    'above_all': {'position': 1.0, 'name': '站上所有均线'}
                }
            }
        }
        
        with open(RISK_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        
        return default_config
    
    def _load_or_create_status(self) -> Dict:
        """加载或创建风控状态"""
        if os.path.exists(RISK_STATUS_FILE):
            with open(RISK_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        default_status = {
            'last_check_time': None,
            'last_position': 1.0
        }
        
        with open(RISK_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_status, f, ensure_ascii=False, indent=2)
        
        return default_status
    
    def _save_status(self):
        """保存风控状态"""
        with open(RISK_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=2)
    
    # ==================== 情绪周期风控 ====================
    
    def check_emotion_risk(self, date: str = None) -> Dict:
        """
        检查情绪周期风险
        
        Args:
            date: 日期
        
        Returns:
            Dict: 风控结果
        """
        emotion_data = self.client.get_emotional_cycle()
        
        if not emotion_data or not isinstance(emotion_data, list):
            return {
                'status': 'unknown',
                'score': 50,
                'position_limit': 0.5,
                'stage': '未知',
                'message': '无法获取情绪周期数据，使用默认值'
            }
        
        # 使用最新数据
        latest = emotion_data[0] if emotion_data else {}
        
        # 尝试获取评分
        score = latest.get('score')
        if score is None:
            # 根据涨停家数估算
            ztjs = latest.get('ztjs', 50)
            try:
                ztjs_val = int(ztjs) if ztjs else 50
                score = min(100, max(0, ztjs_val))
            except:
                score = 50
        
        # 根据评分确定阶段和仓位
        if score < 20:
            stage = '冰点期'
            position_limit = 0.0
            message = f'情绪冰点({score}分)，建议空仓观望'
        elif score < 40:
            stage = '低迷期'
            position_limit = 0.2
            message = f'情绪低迷({score}分)，建议轻仓试错'
        elif score < 60:
            stage = '平稳期'
            position_limit = 0.5
            message = f'情绪平稳({score}分)，正常操作'
        elif score < 80:
            stage = '良好期'
            position_limit = 0.8
            message = f'情绪良好({score}分)，可积极操作'
        else:
            stage = '高涨期'
            position_limit = 1.0
            message = f'情绪高涨({score}分)，满仓但警惕回调'
        
        return {
            'status': 'normal' if position_limit > 0 else 'critical',
            'score': score,
            'position_limit': position_limit,
            'stage': stage,
            'message': message,
            'raw_data': latest
        }
    
    # ==================== 大盘走势风控 ====================
    
    def check_market_risk(self, date: str = None) -> Dict:
        """
        检查大盘走势风险
        
        Args:
            date: 日期
        
        Returns:
            Dict: 风控结果
        """
        if not self.config['market']['enabled']:
            return {
                'status': 'disabled',
                'position_limit': 1.0,
                'message': '大盘风控已禁用'
            }
        
        try:
            # 获取上证指数最近30天数据
            if date:
                end_date = date
                start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
            else:
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            index_data = self.client.get_index_sh(start_date, end_date)
            
            if not index_data or len(index_data) < 20:
                return {
                    'status': 'unknown',
                    'position_limit': 0.5,
                    'message': '无法获取大盘数据，使用默认值'
                }
            
            # 计算均线
            closes = [float(d.get('close', 0)) for d in index_data[-20:] if d.get('close')]
            
            if len(closes) < 20:
                return {
                    'status': 'unknown',
                    'position_limit': 0.5,
                    'message': '数据不足，使用默认值'
                }
            
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10
            ma20 = sum(closes[-20:]) / 20
            current_close = closes[-1]
            
            # 判断均线位置
            above_ma5 = current_close > ma5
            above_ma10 = current_close > ma10
            above_ma20 = current_close > ma20
            
            # 计算仓位限制
            signals = []
            
            if not above_ma20:
                position_limit = 0.3
                signals.append('跌破20日均线')
            elif not above_ma10:
                position_limit = 0.5
                signals.append('跌破10日均线')
            elif not above_ma5:
                position_limit = 0.7
                signals.append('跌破5日均线')
            else:
                position_limit = 1.0
                signals.append('站上所有均线')
            
            # 判断趋势
            if above_ma5 and above_ma10:
                trend = 'up'
            elif not above_ma10 and not above_ma20:
                trend = 'down'
            else:
                trend = 'sideways'
            
            return {
                'status': 'normal' if position_limit >= 0.5 else 'warning',
                'current_price': round(current_close, 2),
                'ma5': round(ma5, 2),
                'ma10': round(ma10, 2),
                'ma20': round(ma20, 2),
                'above_ma5': above_ma5,
                'above_ma10': above_ma10,
                'above_ma20': above_ma20,
                'trend': trend,
                'position_limit': position_limit,
                'signals': signals,
                'message': f"上证指数{current_close:.2f}，{signals[0]}"
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'position_limit': 0.5,
                'message': f'大盘数据获取失败: {e}'
            }
    
    # ==================== 综合风控评估 ====================
    
    def full_risk_assessment(self, date: str = None) -> Dict:
        """
        综合风控评估
        
        Args:
            date: 日期
        
        Returns:
            Dict: 综合评估结果
        """
        print("\n" + "=" * 60)
        print("综合风控评估")
        print("=" * 60)
        
        # 1. 情绪周期风控
        print("\n【1. 情绪周期风控】")
        emotion_risk = self.check_emotion_risk(date)
        print(f"  情绪评分: {emotion_risk.get('score', 'N/A')} 分")
        print(f"  市场阶段: {emotion_risk.get('stage', 'N/A')}")
        print(f"  仓位限制: {emotion_risk['position_limit'] * 100:.0f}%")
        print(f"  说明: {emotion_risk['message']}")
        
        # 2. 大盘风控
        print("\n【2. 大盘走势风控】")
        market_risk = self.check_market_risk(date)
        print(f"  上证指数: {market_risk.get('current_price', 'N/A')}")
        print(f"  MA5: {market_risk.get('ma5', 'N/A')}")
        print(f"  MA10: {market_risk.get('ma10', 'N/A')}")
        print(f"  MA20: {market_risk.get('ma20', 'N/A')}")
        print(f"  趋势判断: {market_risk.get('trend', 'N/A')}")
        print(f"  仓位限制: {market_risk['position_limit'] * 100:.0f}%")
        print(f"  说明: {market_risk['message']}")
        
        # 综合计算：取最小值
        final_position = min(
            emotion_risk['position_limit'],
            market_risk['position_limit']
        )
        
        trading_allowed = final_position > 0
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'date': date,
            'trading_allowed': trading_allowed,
            'final_position_limit': round(final_position, 2),
            'emotion_risk': emotion_risk,
            'market_risk': market_risk,
            'recommendation': self._generate_recommendation(
                trading_allowed, final_position, emotion_risk, market_risk
            )
        }
        
        # 保存状态
        self.status['last_check_time'] = datetime.now().isoformat()
        self.status['last_position'] = final_position
        self._save_status()
        
        print("\n" + "=" * 60)
        print("【综合评估结果】")
        print("=" * 60)
        print(f"  允许交易: {'✅ 是' if trading_allowed else '❌ 否'}")
        print(f"  建议仓位: {final_position * 100:.0f}%")
        print(f"\n  {result['recommendation']}")
        
        return result
    
    def _generate_recommendation(self, trading_allowed, position, emotion, market):
        """生成操作建议"""
        if not trading_allowed:
            return "⛔ 建议空仓观望"
        
        if position <= 0:
            return "⛔ 建议空仓观望"
        elif position < 0.3:
            return f"📉 建议轻仓({position*100:.0f}%)试错"
        elif position < 0.6:
            return f"📊 建议半仓({position*100:.0f}%)操作"
        else:
            return f"📈 建议重仓({position*100:.0f}%)操作"


def main():
    """测试风控系统"""
    risk = RiskController()
    
    # 综合风控评估
    result = risk.full_risk_assessment('2026-02-13')
    
    print("\n" + "=" * 60)
    print("风控结果JSON")
    print("=" * 60)
    
    # 简化输出
    output = {
        'trading_allowed': result['trading_allowed'],
        'final_position': result['final_position_limit'],
        'emotion': {
            'score': result['emotion_risk'].get('score'),
            'stage': result['emotion_risk'].get('stage'),
            'position': result['emotion_risk']['position_limit']
        },
        'market': {
            'price': result['market_risk'].get('current_price'),
            'trend': result['market_risk'].get('trend'),
            'position': result['market_risk']['position_limit']
        }
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
