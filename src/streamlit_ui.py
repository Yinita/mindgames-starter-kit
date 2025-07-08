#!/usr/bin/env python
"""
Streamlit 版 Mind Games 界面
支持配置不同的LLM实例
"""

import streamlit as st
import os
import sys
import time
from typing import Dict, List, Optional, Any

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.game_manager import GameManager
from src.agent import HumanAgent, LLMAgent, OpenAIAgent

# 设置页面配置
st.set_page_config(
    page_title="Mind Games",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 会话状态初始化
if 'manager' not in st.session_state:
    st.session_state.manager = None
if 'game_state' not in st.session_state:
    st.session_state.game_state = None
if 'game_log' not in st.session_state:
    st.session_state.game_log = []
if 'current_observation' not in st.session_state:
    st.session_state.current_observation = ""
if 'waiting_for_action' not in st.session_state:
    st.session_state.waiting_for_action = False
if 'game_over' not in st.session_state:
    st.session_state.game_over = False

def setup_game(game_name: str, human_players: int, agent_configs: List[Dict]):
    """
    设置游戏环境和玩家
    
    Args:
        game_name: 游戏名称
        human_players: 人类玩家数量
        agent_configs: LLM代理配置列表
    """
    st.session_state.manager = GameManager()
    st.session_state.manager.setup_game(game_name)
    st.session_state.game_log = []
    st.session_state.current_observation = ""
    st.session_state.waiting_for_action = False
    st.session_state.game_over = False
    
    # 添加人类玩家
    for i in range(human_players):
        st.session_state.manager.add_human_player()
        
    # 添加AI玩家
    total_players = st.session_state.manager.get_required_player_count()
    ai_players_needed = total_players - human_players
    
    for i in range(min(ai_players_needed, len(agent_configs))):
        config = agent_configs[i]
        agent_type = config['agent_type']
        
        if agent_type == 'openai':
            # 创建 OpenAI 代理
            agent = OpenAIAgent(
                model_name=config['model_name'],
                api_key=config['api_key'],
                base_url=config['base_url'],
                api_type=config['api_type']
            )
            st.session_state.manager.add_agent(agent)
        
        elif agent_type == 'local':
            # 创建本地 LLM 代理
            agent = LLMAgent(
                model_name=config['model_name'],
                device=config.get('device', 'auto'),
                quantize=config.get('quantize', False)
            )
            st.session_state.manager.add_agent(agent)
    
    # 如果还需要更多玩家，添加默认OpenAI玩家
    for i in range(ai_players_needed - len(agent_configs)):
        # 使用默认配置
        agent = OpenAIAgent(model_name="gpt-3.5-turbo")
        st.session_state.manager.add_agent(agent)

def start_game():
    """开始游戏"""
    if st.session_state.manager:
        # 设置回调函数
        callbacks = {
            "on_observation": on_observation,
            "on_action": on_action,
            "on_step_complete": on_step_complete
        }
        
        # 开始游戏
        st.session_state.manager.start_game()
        
        # 启动游戏线程
        st.session_state.manager.play_game(callbacks=callbacks)

def on_observation(player_id: int, observation: str):
    """观察回调"""
    if player_id in st.session_state.manager.human_player_ids:
        st.session_state.current_observation = observation
        st.session_state.waiting_for_action = True
    
    message = f"[Player {player_id}] 收到观察: {observation[:50]}..." if len(observation) > 50 else observation
    st.session_state.game_log.append(message)

def on_action(player_id: int, action: str):
    """动作回调"""
    message = f"[Player {player_id}] 执行动作: {action}"
    st.session_state.game_log.append(message)
    
    # 如果是人类玩家提交了动作，更新状态
    if player_id in st.session_state.manager.human_player_ids:
        st.session_state.waiting_for_action = False

def on_step_complete(done: bool, info: Dict[str, Any]):
    """步骤完成回调"""
    if done:
        st.session_state.game_over = True
        st.session_state.game_log.append("===== 游戏结束 =====")
        
        # 添加游戏结果到日志
        if 'scores' in info:
            st.session_state.game_log.append("得分:")
            for player_id, score in info['scores'].items():
                st.session_state.game_log.append(f"玩家 {player_id}: {score}")
        
        if 'winners' in info:
            winners = ", ".join([str(w) for w in info['winners']])
            st.session_state.game_log.append(f"获胜者: {winners}")

def submit_action(action: str):
    """提交人类玩家动作"""
    if st.session_state.manager and st.session_state.waiting_for_action:
        # 获取第一个人类玩家ID
        if st.session_state.manager.human_player_ids:
            human_player_id = st.session_state.manager.human_player_ids[0]
            st.session_state.manager.submit_action(human_player_id, action)
            st.session_state.waiting_for_action = False
            return True
    return False

def render_sidebar():
    """渲染侧边栏设置"""
    st.sidebar.title("Mind Games")
    st.sidebar.markdown("---")
    st.sidebar.subheader("游戏设置")
    
    # 游戏选择
    game_options = {
        "secret_mafia": "Secret Mafia",
        "three_player_ipd": "三人囚徒困境",
        "colonel_blotto": "Colonel Blotto",
        "codenames": "Codenames"
    }
    selected_game = st.sidebar.selectbox(
        "选择游戏", 
        options=list(game_options.keys()),
        format_func=lambda x: game_options[x],
        index=1  # 默认选择三人囚徒困境
    )
    
    # 人类玩家数量
    if selected_game == "three_player_ipd":
        max_humans = 3
    elif selected_game == "secret_mafia":
        max_humans = 7
    elif selected_game == "colonel_blotto":
        max_humans = 2
    else:  # codenames
        max_humans = 4
        
    human_count = st.sidebar.slider("人类玩家数量", 1, max_humans, 1)
    
    # AI代理配置
    st.sidebar.markdown("---")
    st.sidebar.subheader("AI代理配置")
    
    agent_configs = []
    ai_count = st.sidebar.number_input("AI代理数量", 1, 10, 1)
    
    for i in range(ai_count):
        with st.sidebar.expander(f"AI #{i+1} 配置"):
            agent_type = st.selectbox(
                "代理类型", 
                options=["openai", "local"],
                index=0,
                key=f"agent_type_{i}"
            )
            
            if agent_type == "openai":
                model_name = st.text_input("模型名称", "gpt-3.5-turbo", key=f"model_{i}")
                api_type = st.selectbox(
                    "API类型", 
                    options=["standard", "azure_key"],
                    format_func=lambda x: "Azure OpenAI" if x == "azure_key" else "标准 OpenAI",
                    key=f"api_type_{i}"
                )
                api_key = st.text_input("API密钥", "", type="password", key=f"api_key_{i}")
                
                if api_type == "azure_key":
                    base_url = st.text_input("Azure端点", "https://your-resource.openai.azure.com", key=f"base_url_{i}")
                else:
                    base_url = st.text_input("API基础URL", "https://api.openai.com/v1", key=f"base_url_{i}")
                
                agent_configs.append({
                    'agent_type': 'openai',
                    'model_name': model_name,
                    'api_key': api_key,
                    'base_url': base_url,
                    'api_type': api_type
                })
                
            else:  # local
                model_name = st.text_input("模型名称", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", key=f"model_{i}")
                device = st.selectbox(
                    "设备", 
                    options=["auto", "cpu", "cuda:0"],
                    key=f"device_{i}"
                )
                quantize = st.checkbox("量化模型", False, key=f"quantize_{i}")
                
                agent_configs.append({
                    'agent_type': 'local',
                    'model_name': model_name,
                    'device': device,
                    'quantize': quantize
                })
    
    # 游戏控制按钮
    st.sidebar.markdown("---")
    start_button = st.sidebar.button("开始游戏")
    
    # 检查是否点击了开始按钮
    if start_button:
        with st.spinner("正在设置游戏环境..."):
            setup_game(selected_game, human_count, agent_configs)
            start_game()
            st.sidebar.success("游戏已开始!")
    
    # 重置按钮
    if st.sidebar.button("重置游戏"):
        for key in ['manager', 'game_state', 'game_log', 'current_observation', 
                    'waiting_for_action', 'game_over']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def render_main():
    """渲染主界面"""
    st.title("🧠 Mind Games")
    
    # 分为两列
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.subheader("游戏日志")
        # 创建一个容器来显示日志，使用固定高度
        log_container = st.container(height=400)
        with log_container:
            for log in st.session_state.game_log:
                st.markdown(log)
    
    with col2:
        st.subheader("游戏界面")
        
        # 显示当前观察
        if st.session_state.current_observation:
            st.markdown("#### 当前观察")
            st.text_area("观察", st.session_state.current_observation, height=200, disabled=True)
            
            # 如果在等待人类玩家输入
            if st.session_state.waiting_for_action:
                st.markdown("#### 你的行动")
                action = st.text_area("输入你的行动", height=100)
                
                if st.button("提交行动"):
                    if action:
                        if submit_action(action):
                            st.success("行动已提交!")
                            # 重新加载页面以刷新状态
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("无法提交行动，请检查游戏状态")
                    else:
                        st.warning("请输入行动内容")
            
            # 游戏结束
            elif st.session_state.game_over:
                st.markdown("### 🎮 游戏结束!")
                if st.button("开始新游戏"):
                    # 重置状态
                    for key in ['manager', 'game_state', 'game_log', 'current_observation', 
                                'waiting_for_action', 'game_over']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
        
        # 如果游戏尚未开始
        elif not st.session_state.manager:
            st.info("👈 请在左侧设置游戏参数并点击「开始游戏」按钮")
            
            with st.expander("游戏说明"):
                st.markdown("""
                **Mind Games**是一个多人智力博弈平台，目前支持以下游戏:
                
                1. **三人囚徒困境** - 经典囚徒困境的三人版本
                2. **Secret Mafia** - 基于社交推理的隐藏身份游戏
                3. **Colonel Blotto** - 资源分配策略游戏
                4. **Codenames** - 团队词汇关联游戏
                
                您可以设置人类玩家数量和AI代理配置，包括使用OpenAI API或本地大语言模型。
                """)

def main():
    """主函数"""
    # 检查是否安装了必要的依赖
    try:
        import streamlit
    except ImportError:
        st.error("请先安装Streamlit: pip install streamlit")
        return
        
    try:
        import openai
    except ImportError:
        st.warning("请安装OpenAI库以使用OpenAI功能: pip install openai")
    
    # 渲染侧边栏和主界面
    render_sidebar()
    render_main()

if __name__ == "__main__":
    main()
