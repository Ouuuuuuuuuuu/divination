import streamlit as st
import datetime
import random
import time
import math
import os
from openai import OpenAI
# 修复 ImportError: 移除未使用的 GanZhi 导入
from lunar_python import Lunar, Solar

# ==========================================
# 配置与常量
# ==========================================
# 优先从 Streamlit Secrets 获取 Key，如果没有则尝试环境变量，最后为空
# 在本地运行时，请在 .streamlit/secrets.toml 中配置 SILICONFLOW_API_KEY
SILICONFLOW_API_KEY = st.secrets.get("SILICONFLOW_API_KEY", os.getenv("SILICONFLOW_API_KEY", ""))

BASE_URL = "https://api.siliconflow.cn/v1"

MODELS = {
    "DeepSeek-R1 (推理强)": "deepseek-ai/DeepSeek-R1",
    "Kimi-K2-Thinking (中文优)": "moonshotai/Kimi-K2-Thinking"
}

# 扩展城市经度数据库 (用于真太阳时校准)
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

# 基础时区
TZ_CN = datetime.timezone(datetime.timedelta(hours=8))

st.set_page_config(
    page_title="AI 易学决策系统 Pro",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入 CSS
st.markdown("""
<style>
    .stApp { background-color: #FAFAFA; color: #212121; }
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

# ==========================================
# 核心算法升级：真太阳时与干支
# ==========================================

def get_true_solar_time(dt, longitude):
    """
    根据经度计算真太阳时
    北京时间是东经120度的时间。每差1度，时间差4分钟。
    """
    offset_minutes = (longitude - 120.0) * 4
    # 加上真太阳时差（简化版，主要靠经度修正）
    return dt + datetime.timedelta(minutes=offset_minutes)

def get_ganzhi_info(dt_solar):
    """
    基于真太阳时计算干支、月令、空亡等专业信息
    """
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
        "hour_zhi": ganzhi_time[1], # 时支
        "day_gan": ganzhi_day[0],   # 日干
        "day_zhi": ganzhi_day[1],   # 日支
        "solar_term": lunar.getPrevJieQi().getName() if lunar.getPrevJieQi() else "非节气日"
    }
    
    dizhi_list = list("子丑寅卯辰巳午未申酉戌亥")
    info['hour_idx'] = dizhi_list.index(info['hour_zhi'])
    
    return info

# ==========================================
# 起卦引擎
# ==========================================
class DivinationEngine:
    @staticmethod
    def get_seed():
        # 使用当前微秒作为种子，捕捉当下的“机锋”
        return int(time.time() * 1000000)

    @staticmethod
    def cast_liuyao_coin():
        """线上金钱卦：基于时间机锋的随机映射"""
        random.seed(DivinationEngine.get_seed())
        results = []
        display_lines = []
        
        for _ in range(6):
            # 3枚铜钱，正面(字)与背面(花)的组合
            coins = [random.randint(0, 1) for _ in range(3)] 
            sum_val = sum(coins)
            
            # 传统算法：
            # 1个背 -> 少阳 (单)
            # 2个背 -> 少阴 (拆)
            # 3个背 -> 老阳 (重, 动)
            # 0个背 -> 老阴 (交, 动)
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
        """梅花易数：数理与时间感应"""
        upper = n1 % 8 or 8
        lower = n2 % 8 or 8
        moving = (n1 + n2 + time_num) % 6 or 6
        
        trigrams = {1:"乾", 2:"兑", 3:"离", 4:"震", 5:"巽", 6:"坎", 7:"艮", 8:"坤"}
        nature = {1:"天", 2:"泽", 3:"火", 4:"雷", 5:"风", 6:"水", 7:"山", 8:"地"}
        
        return {
            "upper": trigrams[upper],
            "upper_nature": nature[upper],
            "lower": trigrams[lower],
            "lower_nature": nature[lower],
            "moving": moving,
            "nums": (n1, n2)
        }

# ==========================================
# AI 交互逻辑
# ==========================================
def generate_system_prompt(method, user_profile, ganzhi_info):
    
    # 处理命主信息的描述
    gender_str = user_profile['gender'] if user_profile['gender'] != "未提供" else "未知"
    
    bazi_desc = "未提供"
    if user_profile['bazi_year'] or user_profile['bazi_day']:
        bazi_desc = f"年柱({user_profile['bazi_year']}) 月柱({user_profile['bazi_month']}) 日柱({user_profile['bazi_day']}) 时柱({user_profile['bazi_hour']})"
    elif user_profile['birth_year']:
         bazi_desc = f"出生年份: {user_profile['birth_year']}"

    base_prompt = f"""
    你是一位精通中国传统术数的大师。请基于以下严谨的时空与命主信息进行推演。
    
    【时空能量】
    - 真太阳时干支：{ganzhi_info['str']}
    - 农历：{ganzhi_info['lunar_str']}
    - 节气：{ganzhi_info['solar_term']}
    
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
        return base_prompt + """
        【六爻特化指令】
        1. 自动装卦：确定世爻、应爻、六亲。
        2. 取用神：根据问题选取用神，分析用神在月建、日辰下的旺衰。
        3. 分析动爻：动爻是变数，分析其回头生/克。
        """
    elif method == "梅花":
        return base_prompt + """
        【梅花易数特化指令】
        1. 区分体用：明确体卦（主）与用卦（客）。
        2. 分析五行生克：体克用（吉）、用克体（凶）、体生用（泄气）、用生体（进益）。
        3. 结合当下时间：分析起卦时空对卦气的影响。
        """
    elif method == "奇门":
        return base_prompt + """
        【奇门遁甲特化指令】
        1. 脑中排盘（时家奇门）。
        2. 找用神：根据问题类型找准用神落宫。
        3. 分析宫位：门、星、神、奇仪组合。
        4. 决策建议：利主利客，进退方向。
        """
    elif method == "大六壬":
        return base_prompt + """
        【大六壬特化指令】
        1. **确定月将**：根据当前节气确定月将（太阳过宫）。
        2. **排盘**：推演天地盘、四课、三传。
        3. **断课**：分析三传吉凶，结合十二神将判断。
        4. **人事应验**：分析事情的发展脉络。
        """
    elif method == "太乙":
        return base_prompt + """
        【太乙神数特化指令】
        1. **计算积年与太乙局**：基于当前干支时间，推算太乙积年（上元/中元/下元），确定阳遁或阴遁局数。
        2. **推演主客**：
           - **算主（Host）**：计算主算，定主大将、主参将落宫。
           - **算客（Guest）**：计算客算，定客大将、客参将落宫。
        3. **定格局**：分析太乙在天盘的位置，判断掩、迫、关、囚等格局。
        4. **断大势**：太乙重天道与宏观。分析命主问题的主客胜负、长远趋势。如果是个人问事，请结合“太乙命法”分析身命十二宫。
        """
    elif method == "小六壬":
        return base_prompt + """
        【小六壬特化指令】
        1. 结合年月日时推导三宫。
        2. 解释落宫深意，形成叙事链条。
        """
    return base_prompt

def stream_ai_analysis(prompt, system_prompt, model_key):
    if not SILICONFLOW_API_KEY:
        st.error("⚠️ 未检测到 API Key。请在 .streamlit/secrets.toml 中配置 SILICONFLOW_API_KEY。")
        return

    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    
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
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
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

# ==========================================
# 主界面
# ==========================================
def main():
    # --- Sidebar: 用户设置 ---
    st.sidebar.title("🛠️ 参数设置")
    
    # 1. 命主信息 (全部改为可选)
    with st.sidebar.expander("👤 命主信息 (可选)", expanded=False):
        st.caption("提供准确信息有助于 AI 结合年命分析，不填则按通用占测处理。")
        gender = st.selectbox("性别", ["未提供", "男", "女"], index=0)
        
        input_method = st.radio("输入方式", ["仅年份", "详细四柱(八字)"], index=0)
        
        birth_year = None
        bazi_year = bazi_month = bazi_day = bazi_hour = ""
        
        if input_method == "仅年份":
            use_year = st.checkbox("输入出生年份")
            if use_year:
                birth_year = st.number_input("出生年份", 1920, 2030, 1990)
        else:
            c1, c2 = st.columns(2)
            bazi_year = c1.text_input("年柱", placeholder="如: 甲子")
            bazi_month = c2.text_input("月柱", placeholder="如: 丙寅")
            bazi_day = c1.text_input("日柱", placeholder="如: 戊午")
            bazi_hour = c2.text_input("时柱", placeholder="如: 壬子")

    # 2. 时空校准
    with st.sidebar.expander("🌍 时空校准 (真太阳时)", expanded=True):
        st.caption("古法讲究'当地时间'，即太阳真正升起的时间，而非统一的北京时间。")
        city_name = st.selectbox("选择所在地", list(CITY_COORDINATES.keys()), index=4) # 默认武汉附近
        
        if city_name == "自定义/手动输入":
            longitude = st.number_input("请输入当地经度", value=116.40, format="%.2f")
        else:
            longitude = CITY_COORDINATES[city_name]
            st.info(f"📍 {city_name} 经度: {longitude}°")
        
        now = datetime.datetime.now(TZ_CN)
        true_solar_time = get_true_solar_time(now.replace(tzinfo=None), longitude)
        
        st.caption(f"⌚ 北京时间: {now.strftime('%H:%M:%S')}")
        st.caption(f"🌞 真太阳时: {true_solar_time.strftime('%H:%M:%S')}")

    # 计算干支
    ganzhi_info = get_ganzhi_info(true_solar_time)
    
    st.sidebar.markdown("---")
    st.sidebar.success(f"""
    **当前排盘能量**
    📅 {ganzhi_info['str']}
    🌙 {ganzhi_info['lunar_str']}
    🔥 月令: {ganzhi_info['month_num']}月 | 日干: {ganzhi_info['day_gan']}
    """)
    
    model_name = st.sidebar.selectbox("选择 AI 模型", list(MODELS.keys()), index=0)
    selected_model = MODELS[model_name]

    # --- Main Area ---
    st.title("☯️ AI 易学决策系统 Pro")
    
    st.markdown("""
    <div class="intro-text">
    <h4>👋 欢迎使用 AI 智能预测系统</h4>
    <p>本系统融合了<b>传统术数算法</b>与<b>现代大模型逻辑推理</b>技术。</p>
    <ul>
        <li><b>真太阳时校准</b>：摒弃粗糙的北京时间，根据您所在的经度，还原古人“日中为午”的天文实景。</li>
        <li><b>四柱命理结合</b>：如果提供了八字信息，AI 将结合年命纳音与太岁关系，进行更针对性的“千人千面”分析。</li>
        <li><b>深度思维链</b>：采用 DeepSeek 等推理模型，依据严谨的易学逻辑进行推导，拒绝万金油式的回复。</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    user_profile = {
        "gender": gender,
        "birth_year": birth_year,
        "bazi_year": bazi_year,
        "bazi_month": bazi_month,
        "bazi_day": bazi_day,
        "bazi_hour": bazi_hour,
        "longitude": longitude
    }

    tabs = st.tabs(["🪙 六爻纳甲", "🌸 梅花易数", "🛡️ 奇门遁甲", "🌊 大六壬", "🌌 太乙神数", "🖐️ 小六壬"])

    # --- 1. 六爻 ---
    with tabs[0]:
        st.subheader("六爻纳甲 - 针对具体事务的精细预测")
        col_q, col_btn = st.columns([3, 1])
        q_ly = col_q.text_input("请输入问题", placeholder="例如：下个月跳槽去A公司吉凶如何？", key="q_ly")
        
        if "ly_res" not in st.session_state:
            st.session_state.ly_res = None
            
        if col_btn.button("摇卦起盘", use_container_width=True):
            if not q_ly:
                st.toast("⚠️ 请先输入问题，心诚则灵")
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
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; align-items:center; margin: 4px 0;'>"
                    f"<span style='color:#999; font-size:12px; width:30px;'>六{i+1}</span>"
                    f"<span style='color:{color}; font-weight:bold; font-size:18px; letter-spacing: 2px;'>{line['symbol']}</span>"
                    f"<span style='color:#555; font-size:14px; width:80px; text-align:right;'>{line['name']}</span>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
            st.markdown("</div>", unsafe_allow_html=True)
            
            sys_prompt = generate_system_prompt("六爻", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{res['q']}\n卦象数据：{[line['name'] for line in res['display']]}\n请排盘并断卦。"
            if st.button("大师解卦", key="btn_ly_ai"):
                stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # --- 2. 梅花 ---
    with tabs[1]:
        st.subheader("梅花易数 - 快速洞察数理象意")
        c1, c2 = st.columns(2)
        # 修复：将 min_value 设为 0，允许用户不输入（默认为0）以触发自动感应
        n1 = c1.number_input("上卦数 (心中想一个数)", 0, 999, 0)
        n2 = c2.number_input("下卦数 (心中想另一个数)", 0, 999, 0)
        q_mh = st.text_input("所测之事", key="q_mh")
        
        if st.button("起卦", key="btn_mh"):
            if n1 == 0 or n2 == 0:
                n1 = random.randint(1, 100)
                n2 = random.randint(1, 100)
                st.info(f"自动感应数字：{n1}, {n2}")
            
            res = DivinationEngine.cast_meihua(n1, n2, ganzhi_info['hour_idx'] + 1)
            
            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("本卦 (体/用)", f"{res['upper']}{res['lower']}")
            col_res2.metric("动爻", f"第 {res['moving']} 爻")
            col_res3.metric("五行结构", f"上{res['upper_nature']} 下{res['lower_nature']}")
            
            sys_prompt = generate_system_prompt("梅花", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_mh}\n上卦：{res['upper']}\n下卦：{res['lower']}\n动爻：{res['moving']}\n请断吉凶。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # --- 3. 奇门 ---
    with tabs[2]:
        st.subheader("奇门遁甲 - 运筹决策的高维模型")
        q_qm = st.text_input("决策事项", placeholder="例如：明天去谈判能否成功？方位在西北。", key="q_qm")
        
        if st.button("排盘演局", key="btn_qm"):
            st.info(f"正在排盘... 时间基准：{ganzhi_info['str']} (真太阳时)")
            sys_prompt = generate_system_prompt("奇门", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_qm}\n当前真太阳时干支：{ganzhi_info['str']}\n请以时家奇门排盘分析。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)
    
    # --- 4. 大六壬 ---
    with tabs[3]:
        st.subheader("大六壬 - 细致入微的人事占卜")
        q_lr = st.text_input("六壬问事", placeholder="例如：这笔生意最终能成吗？阻力在哪？", key="q_lr")
        
        if st.button("起课分析", key="btn_lr"):
            st.info(f"正在起课... 时间基准：{ganzhi_info['str']} (真太阳时)")
            sys_prompt = generate_system_prompt("大六壬", user_profile, ganzhi_info)
            user_prompt = f"""
            用户问题：{q_lr}
            当前真太阳时干支：{ganzhi_info['str']}
            当前节气：{ganzhi_info['solar_term']}
            
            请根据节气确定月将（重要！），然后推导天地盘、四课、三传，最后断事。
            """
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # --- 5. 太乙 ---
    with tabs[4]:
        st.subheader("太乙神数 - 宏观大局与天道运数")
        st.caption("太乙神数掌管天道，常用于推演大势、国运、天灾或重大决策（亦含太乙命法）。")
        q_ty = st.text_input("太乙问测", placeholder="例如：未来五年行业发展大势如何？", key="q_ty")
        
        if st.button("太乙演局", key="btn_ty"):
             st.info(f"正在推演... 时间基准：{ganzhi_info['str']} (真太阳时)")
             sys_prompt = generate_system_prompt("太乙", user_profile, ganzhi_info)
             user_prompt = f"""
             用户问题：{q_ty}
             当前真太阳时干支：{ganzhi_info['str']}
             请进行太乙积年推算，定局数，分主客，论格局。
             """
             stream_ai_analysis(user_prompt, sys_prompt, selected_model)

    # --- 6. 小六壬 ---
    with tabs[5]:
        st.subheader("小六壬 - 掐指一算的应急预测")
        q_xlr = st.text_input("速问", key="q_xlr")
        if st.button("掐指一算", key="btn_xlr"):
            m = ganzhi_info['month_num']
            d = ganzhi_info['day_num']
            h = ganzhi_info['hour_idx'] + 1
            states = ["大安", "留连", "速喜", "赤口", "小吉", "空亡"]
            idx_m = (m - 1) % 6
            idx_d = (idx_m + d - 1) % 6
            idx_h = (idx_d + h - 1) % 6
            result = states[idx_h]
            seq = f"{states[idx_m]} -> {states[idx_d]} -> {states[idx_h]}"
            
            st.success(f"结果：{result}")
            st.caption(f"推演路径：{seq}")
            
            sys_prompt = generate_system_prompt("小六壬", user_profile, ganzhi_info)
            user_prompt = f"用户问题：{q_xlr}\n推演路径：{seq}\n最终落宫：{result}\n请解释含义。"
            stream_ai_analysis(user_prompt, sys_prompt, selected_model)

if __name__ == "__main__":
    main()
