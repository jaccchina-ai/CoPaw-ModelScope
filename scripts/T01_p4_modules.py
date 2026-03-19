#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - P4优化模块集合
包含：
1. 个股解禁风险检测
2. 大股东减持风险检测
3. 游资画像分析
4. 情绪周期细化
5. 板块轮动预测
6. 竞价资金流向分析 ★新增
7. 回测验证系统 ★新增
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests
from stockapi_client import StockAPIClient

# 尝试导入搜索模块
try:
    from tavily import tavily_search
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

# API配置
API_BASE_URL = "https://www.stockapi.com.cn"
API_TOKEN = "516f4946db85f3f172e8ed29c6ad32f26148c58a38b33c74"

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"

# ==================== 游资画像数据库 ====================
# 知名游资席位及其风格特征
FAMOUS_INVESTORS = {
    # 顶级游资（胜率高、影响力大）
    '拉萨': {
        'names': ['拉萨', '东方财富拉萨', '拉萨团结路', '拉萨东环路'],
        'style': '趋势',  # 趋势/短线
        'win_rate': 0.65,
        'avg_holding': 3,  # 平均持仓天数
        'score_bonus': 8,
        'description': '顶级游资，趋势操作为主'
    },
    '章盟主': {
        'names': ['章盟主', '章建平', '国泰君安上海分公司'],
        'style': '趋势',
        'win_rate': 0.70,
        'avg_holding': 5,
        'score_bonus': 10,
        'description': '顶级游资，偏好大票趋势'
    },
    '赵老哥': {
        'names': ['赵老哥', '赵强', '银河绍兴', '浙商绍兴'],
        'style': '短线',
        'win_rate': 0.68,
        'avg_holding': 2,
        'score_bonus': 8,
        'description': '顶级游资，短线快进快出'
    },
    '欢乐海岸': {
        'names': ['欢乐海岸', '中泰深圳欢乐海岸', '华泰深圳欢乐海岸'],
        'style': '趋势',
        'win_rate': 0.65,
        'avg_holding': 4,
        'score_bonus': 7,
        'description': '知名游资，趋势操作'
    },
    '作手新一': {
        'names': ['作手新一', '新一', '南京'],
        'style': '短线',
        'win_rate': 0.62,
        'avg_holding': 2,
        'score_bonus': 6,
        'description': '新生代游资，短线犀利'
    },
    '小鳄鱼': {
        'names': ['小鳄鱼', '鳄鱼', '中投'],
        'style': '短线',
        'win_rate': 0.60,
        'avg_holding': 2,
        'score_bonus': 5,
        'description': '活跃游资，短线为主'
    },
    '炒股养家': {
        'names': ['炒股养家', '养家', '华鑫'],
        'style': '趋势',
        'win_rate': 0.63,
        'avg_holding': 3,
        'score_bonus': 6,
        'description': '知名游资，稳健操作'
    },
    '孙哥': {
        'names': ['孙哥', '孙煜', '中信上海溧阳路'],
        'style': '短线',
        'win_rate': 0.58,
        'avg_holding': 1,
        'score_bonus': 4,
        'description': '活跃游资，超短线'
    },
    '机构': {
        'names': ['机构专用', '机构'],
        'style': '趋势',
        'win_rate': 0.70,
        'avg_holding': 7,
        'score_bonus': 10,
        'description': '机构资金，中长线为主'
    },
    '北向资金': {
        'names': ['北向', '沪股通', '深股通', '陆股通'],
        'style': '趋势',
        'win_rate': 0.65,
        'avg_holding': 10,
        'score_bonus': 8,
        'description': '外资，中长期持有'
    }
}

# 机构席位关键词
INSTITUTION_KEYWORDS = ['机构专用', '机构', '基金', '社保', 'QFII', 'RQFII']


class UnlockRiskDetector:
    """个股解禁风险检测器"""
    
    def __init__(self):
        self.cache = {}
    
    def check_unlock_risk(self, stock_name: str, stock_code: str) -> Dict:
        """
        检测个股解禁风险
        
        Args:
            stock_name: 股票名称
            stock_code: 股票代码
        
        Returns:
            dict: {
                'has_risk': bool,
                'unlock_date': str or None,
                'unlock_ratio': float,
                'risk_level': str,  # 高/中/低/无
                'detail': str
            }
        """
        result = {
            'has_risk': False,
            'unlock_date': None,
            'unlock_ratio': 0,
            'risk_level': '无',
            'detail': '无解禁风险'
        }
        
        if not TAVILY_AVAILABLE:
            result['detail'] = '搜索服务不可用'
            return result
        
        try:
            # 搜索解禁信息
            query = f"{stock_name} {stock_code} 限售股解禁 解禁日期 2024 2025"
            search_result = tavily_search(
                query=query,
                max_results=5,
                search_depth='basic',
                time_range='month'
            )
            
            if not search_result or 'results' not in search_result:
                return result
            
            today = datetime.now()
            check_end_date = today + timedelta(days=30)
            
            for news in search_result.get('results', []):
                content = news.get('content', '')
                title = news.get('title', '')
                full_text = f"{title} {content}"
                
                # 检查是否在风险期内
                if '解禁' in full_text:
                    # 提取解禁比例
                    import re
                    
                    # 尝试提取日期
                    date_pattern = r'(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})'
                    dates = re.findall(date_pattern, full_text)
                    
                    # 尝试提取比例
                    ratio_pattern = r'解禁.*?(\d+\.?\d*)%'
                    ratios = re.findall(ratio_pattern, full_text)
                    
                    unlock_ratio = 0
                    if ratios:
                        try:
                            unlock_ratio = float(ratios[0])
                        except:
                            pass
                    
                    # 判断风险等级
                    if unlock_ratio >= 10:
                        result['has_risk'] = True
                        result['unlock_ratio'] = unlock_ratio
                        result['risk_level'] = '高'
                        result['detail'] = f"高风险：{unlock_ratio}%股份待解禁"
                        break
                    elif unlock_ratio >= 5:
                        result['has_risk'] = True
                        result['unlock_ratio'] = unlock_ratio
                        result['risk_level'] = '中'
                        result['detail'] = f"中等风险：{unlock_ratio}%股份待解禁"
                        break
                    elif unlock_ratio > 0:
                        result['has_risk'] = True
                        result['unlock_ratio'] = unlock_ratio
                        result['risk_level'] = '低'
                        result['detail'] = f"低风险：{unlock_ratio}%股份待解禁"
            
        except Exception as e:
            result['detail'] = f'检测失败: {str(e)}'
        
        return result


class ReduceRiskDetector:
    """大股东减持风险检测器"""
    
    def __init__(self):
        self.cache = {}
    
    def check_reduce_risk(self, stock_name: str, stock_code: str) -> Dict:
        """
        检测大股东减持风险
        
        Args:
            stock_name: 股票名称
            stock_code: 股票代码
        
        Returns:
            dict: {
                'has_risk': bool,
                'reduce_ratio': float,
                'reduce_holder': str or None,
                'risk_level': str,
                'detail': str
            }
        """
        result = {
            'has_risk': False,
            'reduce_ratio': 0,
            'reduce_holder': None,
            'risk_level': '无',
            'detail': '无减持风险'
        }
        
        if not TAVILY_AVAILABLE:
            result['detail'] = '搜索服务不可用'
            return result
        
        try:
            # 搜索减持公告
            query = f"{stock_name} {stock_code} 减持公告 大股东减持 减持计划"
            search_result = tavily_search(
                query=query,
                max_results=5,
                search_depth='basic',
                time_range='month'
            )
            
            if not search_result or 'results' not in search_result:
                return result
            
            for news in search_result.get('results', []):
                content = news.get('content', '')
                title = news.get('title', '')
                full_text = f"{title} {content}"
                
                # 检查是否有减持计划
                if '减持' in full_text and ('公告' in full_text or '计划' in full_text):
                    # 排除"不减持"的公告
                    if '不减持' in full_text or '承诺不减持' in full_text or '终止减持' in full_text:
                        continue
                    
                    # 提取减持比例
                    import re
                    ratio_pattern = r'减持.*?(\d+\.?\d*)%'
                    ratios = re.findall(ratio_pattern, full_text)
                    
                    reduce_ratio = 0
                    if ratios:
                        try:
                            reduce_ratio = float(ratios[0])
                        except:
                            pass
                    
                    # 判断风险等级
                    if reduce_ratio >= 3:
                        result['has_risk'] = True
                        result['reduce_ratio'] = reduce_ratio
                        result['risk_level'] = '高'
                        result['detail'] = f"高风险：大股东计划减持{reduce_ratio}%"
                        break
                    elif reduce_ratio >= 1:
                        result['has_risk'] = True
                        result['reduce_ratio'] = reduce_ratio
                        result['risk_level'] = '中'
                        result['detail'] = f"中等风险：大股东计划减持{reduce_ratio}%"
                        break
                    elif reduce_ratio > 0:
                        result['has_risk'] = True
                        result['reduce_ratio'] = reduce_ratio
                        result['risk_level'] = '低'
                        result['detail'] = f"低风险：大股东计划减持{reduce_ratio}%"
                        break
            
        except Exception as e:
            result['detail'] = f'检测失败: {str(e)}'
        
        return result


class InvestorAnalyzer:
    """游资画像分析器"""
    
    def __init__(self):
        self.investors_db = FAMOUS_INVESTORS
    
    def analyze_dragon_tiger(self, dragon_tiger_data: Dict) -> Dict:
        """
        分析龙虎榜游资情况
        
        Args:
            dragon_tiger_data: 龙虎榜数据
        
        Returns:
            dict: {
                'has_famous_investor': bool,
                'investors': list,  # 识别出的游资列表
                'total_score_bonus': float,  # 总加分
                'style_analysis': dict,  # 风格分析
                'avg_win_rate': float,
                'recommendation': str
            }
        """
        result = {
            'has_famous_investor': False,
            'investors': [],
            'total_score_bonus': 0,
            'style_analysis': {'trend': 0, 'short': 0},
            'avg_win_rate': 0,
            'recommendation': '无知名游资'
        }
        
        if not dragon_tiger_data:
            return result
        
        identified_investors = []
        score_bonus = 0
        win_rates = []
        trend_count = 0
        short_count = 0
        
        # 获取买入席位信息
        buy_info = dragon_tiger_data.get('buyInfo', [])
        if isinstance(buy_info, str):
            buy_info = []
        
        # 检查买一至买五席位
        for i in range(1, 6):
            seat_key = f'buySeat{i}'
            seat_name = dragon_tiger_data.get(seat_key, '')
            
            if not seat_name:
                continue
            
            # 匹配知名游资
            matched = self._match_investor(seat_name)
            if matched:
                result['has_famous_investor'] = True
                investor_info = FAMOUS_INVESTORS[matched]
                
                identified_investors.append({
                    'name': matched,
                    'seat': seat_name,
                    'style': investor_info['style'],
                    'win_rate': investor_info['win_rate'],
                    'score_bonus': investor_info['score_bonus'],
                    'description': investor_info['description']
                })
                
                score_bonus += investor_info['score_bonus']
                win_rates.append(investor_info['win_rate'])
                
                if investor_info['style'] == '趋势':
                    trend_count += 1
                else:
                    short_count += 1
        
        # 检查机构席位
        for keyword in INSTITUTION_KEYWORDS:
            seat_str = str(dragon_tiger_data)
            if keyword in seat_str:
                if '机构' not in [inv['name'] for inv in identified_investors]:
                    identified_investors.append({
                        'name': '机构',
                        'seat': keyword,
                        'style': '趋势',
                        'win_rate': 0.70,
                        'score_bonus': 10,
                        'description': '机构资金'
                    })
                    score_bonus += 10
                    win_rates.append(0.70)
                    trend_count += 1
                    result['has_famous_investor'] = True
                break
        
        result['investors'] = identified_investors
        result['total_score_bonus'] = min(score_bonus, 20)  # 最高加20分
        result['style_analysis'] = {'trend': trend_count, 'short': short_count}
        result['avg_win_rate'] = sum(win_rates) / len(win_rates) if win_rates else 0
        
        # 生成建议
        if identified_investors:
            investor_names = [inv['name'] for inv in identified_investors]
            if trend_count > short_count:
                result['recommendation'] = f"趋势游资介入({', '.join(investor_names)})，持续性较好"
            else:
                result['recommendation'] = f"短线游资介入({', '.join(investor_names)})，注意快进快出"
        
        return result
    
    def _match_investor(self, seat_name: str) -> Optional[str]:
        """匹配游资名称"""
        for investor_name, investor_info in FAMOUS_INVESTORS.items():
            for alias in investor_info['names']:
                if alias in seat_name:
                    return investor_name
        return None


class EmotionCycleAnalyzer:
    """情绪周期细化分析器"""
    
    # 情绪周期阶段定义
    STAGES = {
        'ice_point': {
            'name': '冰点期',
            'description': '市场极度低迷，涨停家数极少',
            'position_limit': 0,
            'score_threshold': 15,  # 需要更高分数才能入选
            'features': ['涨停<30家', '连板高度<3', '炸板率>50%']
        },
        'recovery_early': {
            'name': '恢复初期',
            'description': '市场开始回暖，谨慎试错',
            'position_limit': 0.3,
            'score_threshold': 12,
            'features': ['涨停30-50家', '连板高度3-4', '炸板率30-50%']
        },
        'recovery_mid': {
            'name': '恢复中期',
            'description': '市场活跃，正常参与',
            'position_limit': 0.5,
            'score_threshold': 10,
            'features': ['涨停50-80家', '连板高度4-5', '炸板率20-30%']
        },
        'climax': {
            'name': '高潮期',
            'description': '市场亢奋，可积极操作',
            'position_limit': 1.0,
            'score_threshold': 8,
            'features': ['涨停>80家', '连板高度>5', '炸板率<20%']
        },
        'divergence': {
            'name': '分歧期',
            'description': '市场分歧加大，减仓观望',
            'position_limit': 0.3,
            'score_threshold': 12,
            'features': ['炸板率上升', '连板股分化', '情绪指标背离']
        },
        'decline': {
            'name': '退潮期',
            'description': '市场退潮，空仓避险',
            'position_limit': 0,
            'score_threshold': 15,
            'features': ['涨停减少', '跌停增加', '亏钱效应明显']
        }
    }
    
    def analyze(self, emotion_data: Dict) -> Dict:
        """
        分析情绪周期
        
        Args:
            emotion_data: 情绪周期API返回的数据
        
        Returns:
            dict: {
                'stage': str,  # 当前阶段
                'stage_name': str,
                'position_limit': float,
                'score_threshold': float,
                'features': list,
                'description': str,
                'analysis': dict
            }
        """
        result = {
            'stage': 'recovery_mid',
            'stage_name': '恢复中期',
            'position_limit': 0.5,
            'score_threshold': 10,
            'features': [],
            'description': '市场活跃，正常参与',
            'analysis': {}
        }
        
        if not emotion_data:
            return result
        
        try:
            # 解析情绪数据
            col_names = emotion_data.get('colNameList', [])
            content_list = emotion_data.get('contentList', [])
            
            if not content_list:
                return result
            
            # 获取最新数据
            latest = content_list[-1] if content_list else []
            data_dict = {}
            for i, col in enumerate(col_names):
                if i < len(latest):
                    data_dict[col] = latest[i]
            
            # 提取关键指标
            zt_count = int(data_dict.get('ztjs', 0))  # 涨停家数
            lb_height = int(data_dict.get('zxgd', 0))  # 最新高度（连板高度）
            dmqx = float(data_dict.get('dmqx', 0))  # 大面情绪
            drqx = float(data_dict.get('drqx', 0))  # 大肉情绪
            dbcgl = float(data_dict.get('dbcgl', 0))  # 打板成功率
            
            result['analysis'] = {
                'zt_count': zt_count,
                'lb_height': lb_height,
                'dmqx': dmqx,
                'drqx': drqx,
                'dbcgl': dbcgl
            }
            
            # 判断阶段
            if zt_count < 30:
                stage = 'ice_point'
            elif zt_count < 50:
                stage = 'recovery_early'
            elif zt_count < 80:
                # 进一步判断
                if dbcgl > 70:
                    stage = 'recovery_mid'
                else:
                    stage = 'recovery_early'
            elif zt_count >= 80:
                # 判断是否过热
                if lb_height >= 7:
                    stage = 'divergence'  # 过热后分歧
                else:
                    stage = 'climax'
            else:
                stage = 'recovery_mid'
            
            # 根据大面情绪修正
            if dmqx > 50:  # 大面情绪高涨，说明亏钱效应明显
                if stage in ['climax', 'recovery_mid']:
                    stage = 'divergence'
            
            # 根据打板成功率修正
            if dbcgl < 50:  # 打板成功率低于50%
                if stage != 'ice_point':
                    stage = 'decline'
            
            # 返回结果
            stage_info = self.STAGES[stage]
            result['stage'] = stage
            result['stage_name'] = stage_info['name']
            result['position_limit'] = stage_info['position_limit']
            result['score_threshold'] = stage_info['score_threshold']
            result['features'] = stage_info['features']
            result['description'] = stage_info['description']
            
        except Exception as e:
            print(f"情绪周期分析失败: {e}")
        
        return result


    def analyze_emotion(self, date: str = None) -> Dict:
        """
        分析情绪周期
        
        Returns:
            {
                'stage_name': str,      # 阶段名称
                'position_limit': float, # 建议仓位上限
                'description': str,     # 阶段描述
                'emotion_score': int    # 情绪评分
            }
        """
        # 临时实现（后续应替换为真实逻辑）
        return {
            'stage_name': '恢复中期',
            'position_limit': 0.3,
            'description': '市场情绪回暖，可适度参与',
            'emotion_score': 41
        }

class SectorRotationAnalyzer:
    """板块轮动预测分析器"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """加载板块历史"""
        history_file = os.path.join(DATA_BASE_DIR, 'sector_history.json')
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 适配两种格式：新格式是按日期组织的，旧格式是 {"records": [...]}
                if 'records' in data:
                    # 转换旧格式为新格式
                    new_data = {}
                    for record in data['records']:
                        date_str = record.get('date', '')
                        if date_str and record.get('sectors'):
                            new_data[date_str] = record['sectors']
                    return new_data
                return data
        return {}
    
    def _save_history(self):
        """保存历史板块数据"""
        os.makedirs(os.path.dirname(os.path.join(DATA_BASE_DIR, 'sector_history.json')), exist_ok=True)
        with open(os.path.join(DATA_BASE_DIR, 'sector_history.json'), 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def update_and_analyze(self, date: str, hot_sectors: List[Dict]) -> Dict:
        """
        更新并分析板块轮动
        
        Args:
            date: 当前日期
            hot_sectors: 当前热点板块列表
        
        Returns:
            dict: 分析结果
        """
        result = {
            'rising_sectors': [],
            'declining_sectors': [],
            'new_sectors': [],
            'persistent_sectors': [],
            'recommendation': ''
        }
        
        if not hot_sectors:
            return result
        
        # 保存当前数据
        current_data = {}
        for i, sector in enumerate(hot_sectors[:15]):
            sector_name = sector.get('bkName', '')
            if sector_name:
                current_data[sector_name] = {
                    'rank': i + 1,
                    'strength': sector.get('qiangdu', 0),
                    'date': date
                }
        
        self.history[date] = current_data
        
        # 获取最近3天的日期
        dates = sorted(self.history.keys(), reverse=True)[:3]
        
        if len(dates) < 2:
            result['recommendation'] = '数据不足，继续观察'
            self._save_history()
            return result
        
        # 分析板块变化
        today_data = self.history.get(dates[0], {})
        yesterday_data = self.history.get(dates[1], {})
        
        if not today_data or not yesterday_data:
            self._save_history()
            return result
        
        # 1. 找出新进TOP10的板块
        today_top10 = set(list(today_data.keys())[:10])
        yesterday_top10 = set(sector['name'] for sector in yesterday_data[:10])
        result['new_sectors'] = list(today_top10 - yesterday_top10)
        
        # 2. 找出热度上升的板块
        for sector_name, data in today_data.items():
            if sector_name in yesterday_data:
                rank_change = yesterday_data[sector_name]['rank'] - data['rank']
                if rank_change >= 3:  # 排名上升3名以上
                    result['rising_sectors'].append({
                        'name': sector_name,
                        'rank': data['rank'],
                        'rank_change': rank_change
                    })
        
        # 3. 找出热度下降的板块
        for sector_name, data in today_data.items():
            if sector_name in yesterday_data:
                rank_change = yesterday_data[sector_name]['rank'] - data['rank']
                if rank_change <= -3:  # 排名下降3名以上
                    result['declining_sectors'].append({
                        'name': sector_name,
                        'rank': data['rank'],
                        'rank_change': rank_change
                    })
        
        # 4. 找出持续强势板块（连续2天在TOP5）
        if len(dates) >= 2:
            today_top5 = set(list(today_data.keys())[:5])
            yesterday_top5 = set(sector['name'] for sector in yesterday_data[:5])
            result['persistent_sectors'] = list(today_top5 & yesterday_top5)
        
        # 5. 生成建议
        if result['rising_sectors']:
            rising_names = [s['name'] for s in result['rising_sectors'][:3]]
            result['recommendation'] += f"热点上升: {', '.join(rising_names)}。"
        
        if result['persistent_sectors']:
            result['recommendation'] += f"持续强势: {', '.join(result['persistent_sectors'][:3])}。"
        
        if result['new_sectors']:
            result['recommendation'] += f"新热点: {', '.join(result['new_sectors'][:3])}。"
        
        if not result['recommendation']:
            result['recommendation'] = '板块格局稳定'
        
        self._save_history()
        return result
class AuctionFundFlowAnalyzer:
    """竞价资金流向分析器"""
    
    def __init__(self):
        self.api_url = API_BASE_URL
        self.api_token = API_TOKEN
    
    def _make_request(self, endpoint, params=None, timeout=10):
        """发送API请求"""
        try:
            url = f"{self.api_url}{endpoint}"
            if params is None:
                params = {}
            params['token'] = self.api_token
            
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 20000:
                return data.get('data', {})
            return None
        except Exception as e:
            print(f"API请求失败: {e}")
            return None
    
    def get_tick_data(self, stock_code: str) -> List[Dict]:
        """
        获取竞价逐笔明细
        
        Args:
            stock_code: 股票代码
        
        Returns:
            list: 逐笔明细列表
        """
        # 使用逐笔明细接口
        result = self._make_request('/v1/base/secondList', {
            'code': stock_code,
            'all': '1'  # 返回全部数据
        })
        
        if result and isinstance(result, list):
            return result
        return []
    
    def analyze_fund_flow(self, stock_code: str) -> Dict:
        """
        分析竞价资金流向
        
        Args:
            stock_code: 股票代码
        
        Returns:
            dict: {
                'big_buy_amount': float,  # 大单买入金额
                'big_sell_amount': float,  # 大单卖出金额
                'big_net_buy': float,  # 大单净买入
                'big_buy_ratio': float,  # 大单买入占比
                'small_net_buy': float,  # 小单净买入
                'fund_flow_score': float,  # 资金流向评分
                'trend': str,  # 流入/流出/平衡
                'tick_count': int  # 成交笔数
            }
        """
        result = {
            'big_buy_amount': 0,
            'big_sell_amount': 0,
            'big_net_buy': 0,
            'big_buy_ratio': 0,
            'small_net_buy': 0,
            'fund_flow_score': 0,
            'trend': '未知',
            'tick_count': 0,
            'big_buy_count': 0,
            'big_sell_count': 0
        }
        
        try:
            tick_data = self.get_tick_data(stock_code)
            
            if not tick_data:
                return result
            
            result['tick_count'] = len(tick_data)
            
            # 定义大单阈值（金额大于50万视为大单）
            BIG_ORDER_THRESHOLD = 500000
            
            big_buy_amount = 0
            big_sell_amount = 0
            small_buy_amount = 0
            small_sell_amount = 0
            big_buy_count = 0
            big_sell_count = 0
            
            for tick in tick_data:
                try:
                    # bsbz: 买卖标志 (1-买入, 2-卖出, 4-竞价)
                    bsbz = tick.get('bsbz', '0')
                    # 手数
                    shoushu = tick.get('shoushu', '0')
                    # 价格
                    price = tick.get('price', '0')
                    
                    try:
                        shoushu = int(shoushu)
                        price = float(price)
                    except:
                        continue
                    
                    # 计算金额
                    amount = shoushu * price * 100  # 手数×价格×100
                    
                    is_buy = bsbz in ['1', '2', '4']  # 竞价阶段买入
                    
                    if amount >= BIG_ORDER_THRESHOLD:
                        if is_buy:
                            big_buy_amount += amount
                            big_buy_count += 1
                        else:
                            big_sell_amount += amount
                            big_sell_count += 1
                    else:
                        if is_buy:
                            small_buy_amount += amount
                        else:
                            small_sell_amount += amount
                
                except Exception:
                    continue
            
            result['big_buy_amount'] = big_buy_amount
            result['big_sell_amount'] = big_sell_amount
            result['big_net_buy'] = big_buy_amount - big_sell_amount
            result['big_buy_count'] = big_buy_count
            result['big_sell_count'] = big_sell_count
            
            total_big = big_buy_amount + big_sell_amount
            if total_big > 0:
                result['big_buy_ratio'] = (big_buy_amount / total_big) * 100
            
            # 小单净买入
            result['small_net_buy'] = small_buy_amount - small_sell_amount
            
            # 判断趋势
            if result['big_net_buy'] > 0:
                if result['big_net_buy'] > 10000000:  # 净买入超过1000万
                    result['trend'] = '大额流入'
                else:
                    result['trend'] = '资金流入'
            elif result['big_net_buy'] < 0:
                if result['big_net_buy'] < -10000000:
                    result['trend'] = '大额流出'
                else:
                    result['trend'] = '资金流出'
            else:
                result['trend'] = '资金平衡'
            
            # 计算评分
            result['fund_flow_score'] = self._calc_fund_flow_score(result)
            
        except Exception as e:
            print(f"竞价资金流向分析失败: {e}")
        
        return result
    
    def _calc_fund_flow_score(self, flow_data: Dict) -> float:
        """
        计算资金流向评分
        
        评分逻辑：
        - 大单净买入金额
        - 大单买入占比
        """
        score = 0
        
        big_net_buy = flow_data.get('big_net_buy', 0)
        big_buy_ratio = flow_data.get('big_buy_ratio', 0)
        
        # 大单净买入金额评分
        if big_net_buy >= 50000000:  # 5000万以上
            score += 10
        elif big_net_buy >= 20000000:  # 2000万以上
            score += 8
        elif big_net_buy >= 10000000:  # 1000万以上
            score += 6
        elif big_net_buy >= 5000000:  # 500万以上
            score += 4
        elif big_net_buy >= 0:  # 小幅净买入
            score += 2
        elif big_net_buy >= -5000000:  # 小幅净卖出
            score += 0
        else:
            score -= 2  # 扣分
        
        # 大单买入占比评分
        if big_buy_ratio >= 70:
            score += 5
        elif big_buy_ratio >= 60:
            score += 3
        elif big_buy_ratio >= 50:
            score += 1
        elif big_buy_ratio >= 40:
            score += 0
        else:
            score -= 2
        
        return max(score, 0)


# ==================== P4新增：回测验证系统 ====================

class BacktestSystem:
    """回测验证系统"""
    
    def __init__(self, data_dir: str = "/mnt/workspace/working/data/T01"):
        self.data_dir = data_dir
        self.history_dir = os.path.join(data_dir, "history")
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.history_dir, exist_ok=True)
    
    def load_selection_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        加载历史选股记录
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            list: 历史选股记录列表
        """
        records = []
        
        if not os.path.exists(self.history_dir):
            return records
        
        for filename in os.listdir(self.history_dir):
            if not filename.startswith('selection_') or not filename.endswith('.json'):
                continue
            
            file_date = filename.replace('selection_', '').replace('.json', '')
            
            # 日期过滤
            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue
            
            filepath = os.path.join(self.history_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['file_date'] = file_date
                    records.append(data)
            except Exception as e:
                print(f"加载文件失败 {filename}: {e}")
        
        # 按日期排序
        records.sort(key=lambda x: x.get('file_date', ''))
        
        return records
    
    def get_stock_return(self, stock_code: str, buy_date: str, sell_date: str) -> Optional[float]:
        """
        获取股票在指定期间的收益率
        
        Args:
            stock_code: 股票代码
            buy_date: 买入日期（T+1）
            sell_date: 卖出日期（T+2）
        
        Returns:
            float: 收益率（%），失败返回None
        """
        try:
            # 获取K线数据
            from stockapi_client import StockAPIClient
            client = StockAPIClient()
            
            kline = client.get_stock_kline(stock_code, buy_date, sell_date, cycle=100)
            
            if not kline or not isinstance(kline, list):
                return None
            
            # 找到买入日的收盘价
            buy_close = None
            sell_close = None
            
            for item in kline:
                date = item.get('time', '')
                if date == buy_date:
                    buy_close = float(item.get('close', 0))
                elif date == sell_date:
                    sell_close = float(item.get('close', 0))
            
            if buy_close and sell_close and buy_close > 0:
                return ((sell_close - buy_close) / buy_close) * 100
            
        except Exception as e:
            print(f"获取收益率失败 {stock_code}: {e}")
        
        return None
    
    def run_backtest(self, start_date: str = None, end_date: str = None, 
                     top_n: int = 3) -> Dict:
        """
        运行回测
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            top_n: 只统计前N名
        
        Returns:
            dict: 回测结果
        """
        print("=" * 60)
        print("T01龙头战法 - 回测验证系统")
        print("=" * 60)
        
        result = {
            'start_date': start_date,
            'end_date': end_date,
            'total_days': 0,
            'total_trades': 0,
            'win_trades': 0,
            'lose_trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'max_return': 0,
            'min_return': 0,
            'total_return': 0,
            'max_drawdown': 0,
            'trades': [],
            'daily_returns': []
        }
        
        # 加载历史选股
        print(f"\n加载历史选股记录...")
        records = self.load_selection_history(start_date, end_date)
        print(f"找到 {len(records)} 条记录")
        
        if not records:
            return result
        
        result['total_days'] = len(records)
        
        all_returns = []
        cumulative_return = 0
        max_cumulative = 0
        
        for record in records:
            t_date = record.get('file_date', '')
            stocks = record.get('stocks', record.get('top_stocks', []))
            
            if not stocks:
                continue
            
            # T+1买入，T+2卖出
            t_date_obj = datetime.strptime(t_date, '%Y-%m-%d')
            buy_date = (t_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            sell_date = (t_date_obj + timedelta(days=2)).strftime('%Y-%m-%d')
            
            print(f"\n处理 {t_date} 的选股...")
            
            # 只统计前N名
            for i, stock in enumerate(stocks[:top_n]):
                stock_code = stock.get('code', '')
                stock_name = stock.get('name', '')
                score = stock.get('score', stock.get('raw_score', 0))
                
                if not stock_code:
                    continue
                
                print(f"  {i+1}. {stock_name}({stock_code}) - 评分:{score:.2f}")
                
                # 获取收益率
                ret = self.get_stock_return(stock_code, buy_date, sell_date)
                
                if ret is not None:
                    result['total_trades'] += 1
                    all_returns.append(ret)
                    
                    if ret > 0:
                        result['win_trades'] += 1
                    else:
                        result['lose_trades'] += 1
                    
                    # 记录交易
                    result['trades'].append({
                        'date': t_date,
                        'code': stock_code,
                        'name': stock_name,
                        'score': score,
                        'rank': i + 1,
                        'return': round(ret, 2)
                    })
                    
                    print(f"     收益率: {ret:.2f}%")
                else:
                    print(f"     无法获取收益率")
        
        # 计算统计指标
        if all_returns:
            result['win_rate'] = round((result['win_trades'] / len(all_returns)) * 100, 2)
            result['avg_return'] = round(sum(all_returns) / len(all_returns), 2)
            result['max_return'] = round(max(all_returns), 2)
            result['min_return'] = round(min(all_returns), 2)
            result['total_return'] = round(sum(all_returns), 2)
            
            # 计算最大回撤
            cumulative = 0
            max_cum = 0
            max_drawdown = 0
            for ret in all_returns:
                cumulative += ret
                if cumulative > max_cum:
                    max_cum = cumulative
                drawdown = max_cum - cumulative
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            result['max_drawdown'] = round(max_drawdown, 2)
        
        return result
    
    def generate_report(self, backtest_result: Dict) -> str:
        """
        生成回测报告
        
        Args:
            backtest_result: 回测结果
        
        Returns:
            str: 报告文本
        """
        report = []
        report.append("=" * 60)
        report.append("T01龙头战法 - 回测验证报告")
        report.append("=" * 60)
        report.append("")
        report.append(f"回测区间: {backtest_result.get('start_date', '未知')} ~ {backtest_result.get('end_date', '未知')}")
        report.append(f"回测天数: {backtest_result.get('total_days', 0)} 天")
        report.append("")
        report.append("-" * 60)
        report.append("【交易统计】")
        report.append(f"  总交易次数: {backtest_result.get('total_trades', 0)} 次")
        report.append(f"  盈利次数: {backtest_result.get('win_trades', 0)} 次")
        report.append(f"  亏损次数: {backtest_result.get('lose_trades', 0)} 次")
        report.append(f"  胜率: {backtest_result.get('win_rate', 0):.2f}%")
        report.append("")
        report.append("-" * 60)
        report.append("【收益分析】")
        report.append(f"  平均收益率: {backtest_result.get('avg_return', 0):.2f}%")
        report.append(f"  最大单次收益: {backtest_result.get('max_return', 0):.2f}%")
        report.append(f"  最大单次亏损: {backtest_result.get('min_return', 0):.2f}%")
        report.append(f"  累计收益: {backtest_result.get('total_return', 0):.2f}%")
        report.append(f"  最大回撤: {backtest_result.get('max_drawdown', 0):.2f}%")
        report.append("")
        report.append("-" * 60)
        report.append("【交易明细】")
        
        trades = backtest_result.get('trades', [])
        for trade in trades[:20]:  # 只显示前20条
            win_lose = '✅' if trade['return'] > 0 else '❌'
            report.append(f"  {trade['date']} {trade['name']}({trade['code']}) {win_lose} {trade['return']:.2f}%")
        
        if len(trades) > 20:
            report.append(f"  ... 还有 {len(trades) - 20} 条记录")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def save_backtest_result(self, backtest_result: Dict, filename: str = None):
        """保存回测结果"""
        if not filename:
            filename = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backtest_result, f, ensure_ascii=False, indent=2)
        
        print(f"\n回测结果已保存: {filepath}")


# ==================== 7. 市场预测引擎（新增） ====================

class MarketPredictionEngine:
    """市场预测引擎"""
    
    def __init__(self):
        self.emotion_analyzer = EmotionCycleAnalyzer()
        self.sector_analyzer = SectorRotationAnalyzer()
        self.fund_flow_analyzer = AuctionFundFlowAnalyzer()
    
    def predict(self, date: str = None) -> Dict:
        """
        预测市场走势
        
        Returns:
            {
                'trend': str,       # 市场趋势（上升/下降/震荡）
                'confidence': float, # 预测置信度
                'key_indicators': list, # 关键指标
                'sector_outlook': dict # 板块展望
            }
        """
        # 实现预测逻辑
        return {
            'trend': 'unknown',
            'confidence': 0.0,
            'key_indicators': [],
            'sector_outlook': {}
        }


class RiskAssessmentEngine:
    """风险评估引擎"""
    
    def __init__(self):
        pass
    
    def assess_risk(self, date: str = None) -> Dict:
        """
        评估市场风险
        
        Returns:
            {
                'risk_level': str,  # 风险等级（高/中/低）
                'risk_factors': list, # 风险因素
                'position_limit': float # 建议仓位上限
            }
        """
        return {
            'risk_level': 'medium',
            'risk_factors': [],
            'position_limit': 0.5
        }
