import streamlit as st
from openai import OpenAI
import concurrent.futures
from typing import List, Dict, Any
import datetime
import random
import time
import math
import os
# 需要先安装 lunar_python: pip install lunar_python
try:
    from lunar_python import Lunar, Solar
except ImportError:
    st.error("请安装依赖: pip install lunar_python")
    Solar = None
    Lunar = None

# --- Global Setup ---
st.set_page_config(page_title="AI 综合智能平台", page_icon="🤖", layout="wide")

# Custom CSS (Merged)
st.markdown("""
<style>
    .model-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        background-color: #f9f9f9;
        height: 100%;
    }
    .stChatMessage {
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #fff; border-radius: 5px;
        border: 1px solid #ddd; padding: 0 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E3F2FD !important; color: #1565C0 !important;
        border: 1px solid #1565C0 !important; font-weight: bold;
    }
    .hexagram-box {
        background: white; padding: 20px; border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee;
    }
    .info-card {
        background: #f8f9fa; border-left: 4px solid #1565C0;
        padding: 10px 15px; margin-bottom: 10px; border-radius: 4px; font-size: 0.9em;
    }
    .intro-text {
        background-color: #FFFFFF; padding: 20px; border-radius: 10px;
        border: 1px solid #E0E0E0; margin-bottom: 20px; color: #444;
    }
</style>
""", unsafe_allow_html=True)

# --- Shared Helpers ---

def get_api_key():
    """Unified API key retrieval."""
    # Try secrets first
    try:
        return st.secrets["api_keys"]["silicon_flow"]
    except (KeyError, FileNotFoundError):
        pass
    
    # Try explicit environment variable
    env_key = os.getenv("SILICONFLOW_API_KEY")
    if env_key:
        return env_key
        
    # Fallback to sidebar input
    return st.sidebar.text_input("SiliconFlow API Key", type="password", key="global_api_key_input")

def get_client(api_key):
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

# ==========================================
# APP 1: AI Roundtable (AI 众议院)
# ==========================================

def app_roundtable(api_key):
    PAGE_TITLE = "AI 众议院 (AI Roundtable)"
    
    # Updated Model List as requested
    PANEL_MODELS = [
        "deepseek-ai/DeepSeek-V3.2",
        "deepseek-ai/DeepSeek-R1",
        "moonshotai/Kimi-K2-Thinking",
        "zai-org/GLM-4.6", 
        "MiniMaxAI/MiniMax-M2"
    ]
    SECRETARY_MODEL = "deepseek-ai/DeepSeek-V3"

    # State Management for Roundtable
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_models" not in st.session_state:
        st.session_state.selected_models = PANEL_MODELS

    st.title(f"🤖 {PAGE_TITLE}")
    st.markdown("这里是 **SiliconFlow** 驱动的 AI 圆桌会议。所有模型将同时回答您的问题，或者您可以指定模型进行辩论。")

    if not api_key:
        st.warning("请在侧边栏输入 API Key 或在 `.streamlit/secrets.toml` 中配置。")
        return

    client = get_client(api_key)

    # Roundtable specific sidebar controls
    with st.sidebar:
        st.divider()
        st.header("🎮 会议控制")
        mode = st.radio("模式", ["全员发言 (Broadcast)", "指定讨论 (Discussion)"])
        
        if mode == "指定讨论 (Discussion)":
            st.subheader("唤醒指定模型")
            selected = st.multiselect(
                "选择参与下一轮对话的 AI:",
                PANEL_MODELS,
                default=PANEL_MODELS[:2]
            )
            st.session_state.selected_models = selected
        else:
            st.session_state.selected_models = PANEL_MODELS
        
        use_secretary = st.checkbox("启用秘书摘要 (Secretary)", value=False, help="启用后，DeepSeek-V3 将在每轮对话前总结历史。")
        
        if st.button("清空历史"):
            st.session_state.messages = []
            st.rerun()

    # Chat Display
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            role = msg["role"]
            name = msg.get("name", "")
            content = msg["content"]
            
            if role == "user":
                with st.chat_message("user"):
                    st.write(content)
            elif role == "assistant":
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(f"**{name}**")
                    st.markdown(content)
            elif role == "system":
                with st.expander(f"📋 会议纪要 (由 {name} 提供)", expanded=False):
                    st.markdown(content)

    # Input & Logic
    user_input = st.chat_input("输入问题或指令...")

    def generate_response_rt(client, model_name, history, system_prompt=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=False,
                temperature=0.7,
            )
            return {"model": model_name, "content": response.choices[0].message.content, "error": None}
        except Exception as e:
            return {"model": model_name, "content": None, "error": str(e)}

    def summarize_context_rt(client, history):
        prompt = "请作为会议秘书，简要总结上述所有AI模型的讨论要点和用户的核心问题。保留关键分歧和共识。"
        temp_msgs = [{"role": m["role"], "content": f"[{m.get('name', 'User')}]: {m['content']}"} for m in history]
        temp_msgs.append({"role": "user", "content": prompt})
        try:
            response = client.chat.completions.create(model=SECRETARY_MODEL, messages=temp_msgs, temperature=0.5)
            return response.choices[0].message.content
        except Exception as e:
            return f"秘书模型无法总结: {e}"

    if user_input:
        st.session_state.messages.append({"role": "user", "name": "User", "content": user_input})
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        active_models = st.session_state.selected_models
        if not active_models:
            st.error("请至少选择一个模型进行回答！")
            st.stop()
            
        current_history = st.session_state.messages
        if use_secretary and len(current_history) > 5:
            with st.status("👩‍💼 秘书 (DeepSeek-V3) 正在整理会议背景...", expanded=True) as status:
                summary = summarize_context_rt(client, current_history[:-1])
                st.session_state.messages.insert(-1, {"role": "system", "name": "Secretary", "content": f"**背景摘要**: {summary}"})
                status.update(label="背景整理完毕", state="complete", expanded=False)
        
        st.markdown("### 🎙️ AI 正在思考中...")
        results = []
        cols = st.columns(len(active_models))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_models)) as executor:
            future_to_model = {}
            for i, model in enumerate(active_models):
                with cols[i]:
                    st.markdown(f"**{model.split('/')[-1]}**")
                    spinner = st.spinner("思考中...")
                clean_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] != "system"]
                future = executor.submit(generate_response_rt, client, model, clean_history)
                future_to_model[future] = model
                
            for future in concurrent.futures.as_completed(future_to_model):
                res = future.result()
                results.append(res)
        
        for res in results:
            if res["error"]:
                st.error(f"{res['model']} Error: {res['error']}")
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "name": res["model"],
                    "content": res["content"]
                })
        st.rerun()


# ==========================================
# APP 2: AI Yi Jing (AI 易学决策系统)
# ==========================================

def app_yijing(api_key):
    st.title("☯️ AI 易学决策系统 Pro")

    # 配置与常量
    MODELS = {
        "DeepSeek-R1 (推理强)": "deepseek-ai/DeepSeek-R1",
        "Kimi-K2-Thinking (中文优)": "moonshotai/Kimi-K2-Thinking"
    }
    
    CITY_COORDINATES = {
        "北京": 116.40, "上海": 121.47, "广州": 113.26, "深圳": 114.05,
        "武汉": 114.30, "成都": 104.06, "西安": 108.93, "沈阳": 123.43,
        "重庆": 106.55, "天津": 117.20, "杭州": 120.15, "南京": 118.79,
        "郑州": 113.62, "长沙": 112.93, "福州": 119.30, "昆明": 102.71,
        "贵阳": 106.63, "兰州": 103.82, "南宁": 108.32, "哈尔滨": 126.63,
        "长春": 125.32, "石家庄": 114.48, "太原": 112.53, "呼和浩特": 111.65,
        "合肥": 117.28, "南昌": 115.89, "济南": 117.00, "海口": 110.35,
        "拉萨": 91.11, "西宁": 101.74, "银川": 106.27, "乌鲁木齐": 87.62,
        "台北": 121.50, "香港": 114.17, "澳门": 113.54,
        "自定义/手动输入": 0.0
    }
    TZ_CN = datetime.timezone(datetime.timedelta(hours=8))

    # --- 易学 Helpers ---
    def get_true_solar_time(dt, longitude):
        offset_minutes = (longitude - 120.0) * 4
        return dt + datetime.timedelta(minutes=offset_minutes)

    def get_ganzhi_info(dt_solar):
        if not Solar: return {}
        solar = Solar.fromYmdHms(dt_solar.year, dt_solar.month, dt_solar.day, dt_solar.hour, dt_solar.minute, dt_solar.second)
        lunar = solar.getLunar()
        ganzhi_year = lunar.getYearInGanZhi()
        ganzhi_month = lunar.getMonthInGanZhi()
        ganzhi_day = lunar.getDayInGanZhi()
        ganzhi_time = lunar.getTimeInGanZhi()
        info = {
            "str": f"{ganzhi_year}年 {ganzhi_month}月 {ganzhi_day}日 {ganzhi_time}时",
            "lunar_str": f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
            "month_num": lunar.getMonth(),
            "day_num": lunar.getDay(),
            "hour_zhi": ganzhi_time[1],
            "day_gan": ganzhi_day[0],
            "day_zhi": ganzhi_day[1],
            "solar_term": lunar.getPrevJieQi().getName() if lunar.getPrevJieQi() else "非节气日"
        }
        dizhi_list = list("子丑寅卯辰巳午未申酉戌亥")
        info['hour_idx'] = dizhi_list.index(info['hour_zhi'])
        return info

    class DivinationEngine:
        @staticmethod
        def get_seed():
            return int(time.time() * 1000000)

        @staticmethod
        def cast_liuyao_coin():
            random.seed(DivinationEngine.get_seed())
            results = []
            display_lines = []
            for _ in range(6):
                coins = [random.randint(0, 1) for _ in range(3)] 
                sum_val = sum(coins)
                if sum_val == 1:
                    val, name, symbol = 1, "少阳", "▅▅▅▅▅"
                elif sum_val == 2:
                    val, name, symbol = 0, "少阴", "▅▅　▅▅"
                elif sum_val == 3:
                    val, name, symbol = 3, "老阳 O", "▅▅▅▅▅ O"
                else:
                    val, name, symbol = 2, "老阴 X", "▅▅　▅▅ X"
                results.append(val)
                display_lines.append({"name": name, "symbol": symbol, "val": val})
            return results, display_lines

        @staticmethod
        def cast_meihua(n1, n2, time_num):
            upper = n1 % 8 or 8
            lower = n2 % 8 or 8
            moving = (n1 + n2 + time_num) % 6 or 6
            trigrams = {1:"乾", 2:"兑", 3:"离", 4:"震", 5:"巽", 6:"坎", 7:"艮", 8:"坤"}
            nature = {1:"天", 2:"泽", 3:"火", 4:"雷", 5:"风", 6:"水", 7:"山", 8:"地"}
            return {
                "upper": trigrams[upper], "upper_nature": nature[upper],
                "lower": trigrams[lower], "lower_nature": nature[lower],
                "moving": moving, "nums": (n1, n2)
            }

    def generate_system_prompt(method, user_profile, ganzhi_info):
        gender_str = user_profile['gender'] if user_profile['gender'] != "未提供" else "未知"
        bazi_desc = "未提供"
        if user_profile['bazi_year'] or user_profile['bazi_day']:
            bazi_desc = f"年柱({user_profile['bazi_year']}) 月柱({user_profile['bazi_month']}) 日柱({user_profile['bazi_day']}) 时柱({user_profile['bazi_hour']})"
        elif user_profile['birth_year']:
             bazi_desc = f"出生年份: {user_profile['birth_year']}"

        base_prompt = f"""
        你是一位精通中国传统术数的大师。请基于以下严谨的时空与命主信息进行推演。
        【时空能量】
        - 真太阳时干支：{ganzhi_info.get('str', '未知')}
        - 农历：{ganzhi_info.get('lunar_str', '未知')}
        - 节气：{ganzhi_info.get('solar_term', '未知')}
        【命主信息】
        - 性别：{gender_str}
        - 命理八字/年命：{bazi_desc}
        - 所在经度：{user_profile['longitude']}
        【核心原则】
        1. **拒绝模棱两可**：请根据五行旺衰给出倾向性判断。
        2. **专业术语**：必须分析月令（旺相休囚死）、日辰（生克冲合）、空亡、神煞。
        3. **结合真太阳时**：排盘依据的是当地真实的太阳位置，而非标准北京时间。
        """
        if method == "六爻":
            return base_prompt + "\n【六爻特化指令】1. 自动装卦：确定世爻、应爻、六亲。2. 取用神：根据问题选取用神。3. 分析动爻。"
        elif method == "梅花":
            return base_prompt + "\n【梅花易数特化指令】1. 区分体用。2. 分析五行生克。3. 结合当下时间。"
        elif method == "奇门":
            return base_prompt + "\n【奇门遁甲特化指令】1. 脑中排盘（时家奇门）。2. 找用神。3. 分析宫位。4. 决策建议。"
        elif method == "大六壬":
            return base_prompt + "\n【大六壬特化指令】1. 确定月将。2. 排盘（天地盘、四课、三传）。3. 断课。"
        elif method == "太乙":
            return base_prompt + "\n【太乙神数特化指令】1. 计算积年与太乙局。2. 推演主客。3. 定格局。4. 断大势。"
        elif method == "小六壬":
            return base_prompt + "\n【小六壬特化指令】1. 结合年月日时推导三宫。2. 解释落宫深意。"
        return base_prompt

    def stream_ai_analysis(prompt, system_prompt, model_key):
        if not api_key:
            st.error("⚠️ 未检测到 API Key。")
            return
        
        client = get_client(api_key)
        
        st.markdown("---")
        st.markdown("#### 📜 大师批断")
        reasoning_expander = st.expander("👁️ 凝神推演 (AI 思考过程)", expanded=True)
        reasoning_area = reasoning_expander.empty()
        content_area = st.empty()
        full_reasoning = ""
        full_content = ""
        
        try:
            response = client.chat.completions.create(
                model=model_key,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                stream=True
            )
            for chunk in response:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    full_reasoning += delta.reasoning_content
                    reasoning_area.markdown(f"*{full_reasoning}*")
                if hasattr(delta, 'content') and delta.content:
                    full_content += delta.content
                    content_area.markdown(full_content + "▌")
            content_area.markdown(full_content)
        except Exception as e:
            st.error(f"连接中断: {str(e)}")

    # --- Sidebar: User Settings ---
    with st.sidebar:
        st.divider()
        st.header("🛠️ 易学参数")
        with st.expander("👤 命主信息 (可选)", expanded=False):
            gender = st.selectbox("性别", ["未提供", "男", "女"], index=0)
            input_method = st.radio("输入方式", ["仅年份", "详细四柱(八字)"], index=0)
            birth_year = None
            bazi_year = bazi_month = bazi_day = bazi_hour = ""
            if input_method == "仅年份":
                if st.checkbox("输入出生年份"):
                    birth_year = st.number_input("出生年份", 1920, 2030, 1990)
            else:
                c1, c2 = st.columns(2)
                bazi_year = c1.text_input("年柱", placeholder="如: 甲子")
                bazi_month = c2.text_input("月柱", placeholder="如: 丙寅")
                bazi_day = c1.text_input("日柱", placeholder="如: 戊午")
                bazi_hour = c2.text_input("时柱", placeholder="如: 壬子")

        with st.expander("🌍 时空校准 (真太阳时)", expanded=True):
            city_name = st.selectbox("选择所在地", list(CITY_COORDINATES.keys()), index=4) 
            if city_name == "自定义/手动输入":
                longitude = st.number_input("请输入当地经度", value=116.40, format="%.2f")
            else:
                longitude = CITY_COORDINATES[city_name]
                st.caption(f"📍 {city_name} 经度: {longitude}°")
            
            now = datetime.datetime.now(TZ_CN)
            true_solar_time = get_true_solar_time(now.replace(tzinfo=None), longitude)
            st.caption(f"🌞 真太阳时: {true_solar_time.strftime('%H:%M:%S')}")

        ganzhi_info = get_ganzhi_info(true_solar_time) if Solar else {}
        if ganzhi_info:
            st.success(f"📅 {ganzhi_info['str']}\n\n🌙 {ganzhi_info['lunar_str']}")
        
        model_name = st.selectbox("选择易学 AI 模型", list(MODELS.keys()), index=0)
        selected_model = MODELS[model_name]

    # --- Main Yi Jing Content ---
    st.markdown("""
    <div class="intro-text">
    <h4>👋 欢迎使用 AI 智能预测系统</h4>
    <p>融合<b>传统术数</b>与<b>深度推理 AI</b> (DeepSeek-R1/Kimi-K2)。采用真太阳时与经度校准。</p>
    </div>
    """, unsafe_allow_html=True)

    if not Solar:
        st.error("⚠️ 缺少 `lunar_python` 库，无法进行排盘计算。")
        return

    user_profile = {
        "gender": gender, "birth_year": birth_year,
        "bazi_year": bazi_year, "bazi_month": bazi_month, "bazi_day": bazi_day, "bazi_hour": bazi_hour,
        "longitude": longitude
    }

    tabs = st.tabs(["🪙 六爻纳甲", "🌸 梅花易数", "🛡️ 奇门遁甲", "🌊 大六壬", "🌌 太乙神数", "🖐️ 小六壬"])

    # 1. 六爻
    with tabs[0]:
        st.subheader("六爻纳甲")
        col_q, col_btn = st.columns([3, 1])
        q_ly = col_q.text_input("请输入问题", placeholder="例如：下个月跳槽去A公司吉凶如何？", key="q_ly")
        if "ly_res" not in st.session_state: st.session_state.ly_res = None
        if col_btn.button("摇卦起盘", use_container_width=True):
            if not q_ly: st.toast("⚠️ 请先输入问题")
            else:
                with st.spinner("凝神摇卦中..."):
                    time.sleep(1)
                    raw, display = DivinationEngine.cast_liuyao_coin()
                    st.session_state.ly_res = {"raw": raw, "display": display, "q": q_ly}
        
        if st.session_state.ly_res:
            res = st.session_state.ly_res
            st.markdown("<div class='hexagram-box'>", unsafe_allow_html=True)
            for i in range(5, -1, -1):
                line = res['display'][i]
                color = "#D32F2F" if "阳" in line['name'] else "#1976D2"
                st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center; margin: 4px 0;'><span style='color:#999; font-size:12px; width:30px;'>六{i+1}</span><span style='color:{color}; font-weight:bold; font-size:18px; letter-spacing: 2px;'>{line['symbol']}</span><span style='color:#555; font-size:14px; width:80px; text-align:right;'>{line['name']}</span></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            if st.button("大师解卦", key="btn_ly_ai"):
                sys_prompt = generate_system_prompt("六爻", user_profile, ganzhi_info)
                user_prompt = f"用户问题：{res['q']}\n卦象数据：{[line['name'] for line in res['display']]}\n请排盘并断卦。"
                stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # 2. 梅花
    with tabs[1]:
        st.subheader("梅花易数")
        c1, c2 = st.columns(2)
        n1 = c1.number_input("上卦数", 0, 999, 0)
        n2 = c2.number_input("下卦数", 0, 999, 0)
        q_mh = st.text_input("所测之事", key="q_mh")
        if st.button("起卦", key="btn_mh"):
            if n1 == 0 or n2 == 0:
                n1, n2 = random.randint(1, 100), random.randint(1, 100)
                st.info(f"自动感应数字：{n1}, {n2}")
            res = DivinationEngine.cast_meihua(n1, n2, ganzhi_info['hour_idx'] + 1)
            c_a, c_b, c_c = st.columns(3)
            c_a.metric("本卦", f"{res['upper']}{res['lower']}")
            c_b.metric("动爻", f"第 {res['moving']} 爻")
            c_c.metric("五行", f"上{res['upper_nature']} 下{res['lower_nature']}")
            sys_prompt = generate_system_prompt("梅花", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_mh}\n上卦：{res['upper']}\n下卦：{res['lower']}\n动爻：{res['moving']}\n请断吉凶。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # 3. 奇门
    with tabs[2]:
        st.subheader("奇门遁甲")
        q_qm = st.text_input("决策事项", placeholder="例如：明天去谈判能否成功？方位在西北。", key="q_qm")
        if st.button("排盘演局", key="btn_qm"):
            sys_prompt = generate_system_prompt("奇门", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_qm}\n当前真太阳时干支：{ganzhi_info['str']}\n请以时家奇门排盘分析。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # 4. 大六壬
    with tabs[3]:
        st.subheader("大六壬")
        q_lr = st.text_input("六壬问事", key="q_lr")
        if st.button("起课分析", key="btn_lr"):
            sys_prompt = generate_system_prompt("大六壬", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_lr}\n当前真太阳时干支：{ganzhi_info['str']}\n当前节气：{ganzhi_info.get('solar_term','')}\n请确定月将，推导天地盘、四课、三传，最后断事。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # 5. 太乙
    with tabs[4]:
        st.subheader("太乙神数")
        q_ty = st.text_input("太乙问测", placeholder="例如：未来五年行业发展大势如何？", key="q_ty")
        if st.button("太乙演局", key="btn_ty"):
            sys_prompt = generate_system_prompt("太乙", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_ty}\n当前真太阳时干支：{ganzhi_info['str']}\n请进行太乙积年推算，定局数，分主客，论格局。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # 6. 小六壬
    with tabs[5]:
        st.subheader("小六壬")
        q_xlr = st.text_input("速问", key="q_xlr")
        if st.button("掐指一算", key="btn_xlr"):
            m, d, h = ganzhi_info['month_num'], ganzhi_info['day_num'], ganzhi_info['hour_idx'] + 1
            states = ["大安", "留连", "速喜", "赤口", "小吉", "空亡"]
            idx_m = (m - 1) % 6
            idx_d = (idx_m + d - 1) % 6
            idx_h = (idx_d + h - 1) % 6
            result = states[idx_h]
            seq = f"{states[idx_m]} -> {states[idx_d]} -> {states[idx_h]}"
            st.success(f"结果：{result}")
            st.caption(f"路径：{seq}")
            sys_prompt = generate_system_prompt("小六壬", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_xlr}\n推演路径：{seq}\n最终落宫：{result}\n请解释含义。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

# ==========================================
# Main Navigation
# ==========================================

def main():
    st.sidebar.title("🔮 功能导航")
    app_mode = st.sidebar.radio("选择应用", ["AI 众议院 (Roundtable)", "AI 易学决策 (Yi Jing)"])
    
    # Unified Key Retrieval
    api_key = get_api_key()

    if app_mode == "AI 众议院 (Roundtable)":
        app_roundtable(api_key)
    elif app_mode == "AI 易学决策 (Yi Jing)":
        app_yijing(api_key)

if __name__ == "__main__":
    main()
