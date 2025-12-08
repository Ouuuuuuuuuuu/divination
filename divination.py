import streamlit as st
import datetime
import random
import time
from openai import OpenAI

# 引入专业的农历库
# 必须先执行: pip install lunar_python
from lunar_python import Lunar, Solar

# ==========================================
# 配置与常量
# ==========================================
SILICONFLOW_API_KEY = "sk-lezqyzzxlcnarawzhmyddltuclijckeufnzzktmkizfslcje"  # 请确保Key安全
BASE_URL = "https://api.siliconflow.cn/v1"

MODELS = {
    "DeepSeek-R1": "deepseek-ai/DeepSeek-R1",
    "Kimi-K2-Thinking": "moonshotai/Kimi-K2-Thinking"
}

# 估算价格表 (单位：元/百万 Tokens)
MODEL_PRICING = {
    "deepseek-ai/DeepSeek-R1": {"input": 4.0, "output": 16.0},
    "moonshotai/Kimi-K2-Thinking": {"input": 4.0, "output": 16.0}
}

# 设置 UTC+8 时区
TZ_CN = datetime.timezone(datetime.timedelta(hours=8))

st.set_page_config(
    page_title="AI 智能易学预测系统",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入浅色系 CSS 样式
st.markdown("""
<style>
    /* 强制浅色背景，营造清爽氛围 */
    .stApp {
        background-color: #FAFAFA;
        color: #333333;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 5px 5px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        border: 1px solid #E0E0E0;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        background-color: #E6F3FF !important;
        color: #0066CC !important;
        border-top: 3px solid #0066CC !important;
    }
    div[data-testid="stExpander"] {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
    }
    /* 卦象容器样式 */
    .hexagram-container {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #F0F0F0;
    }
    .algo-desc {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        font-size: 0.9em;
        color: #555;
        margin-top: 10px;
        border-left: 4px solid #0066CC;
    }
    /* 费用统计样式 */
    .cost-box {
        background-color: #e8f5e9;
        border: 1px solid #c8e6c9;
        color: #2e7d32;
        padding: 10px;
        border-radius: 5px;
        font-size: 0.85em;
        margin-top: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函数：干支与农历核心逻辑 (已修正)
# ==========================================

def get_ganzhi_time(dt=None):
    """
    计算干支及农历信息 (使用 lunar_python 库)
    返回: 
    - gregorian_str: 公历字符串
    - ganzhi_str: 干支字符串 (含农历月日)
    - hour_idx: 时辰索引 (0-11)
    - lunar_month: 农历月份 (数字)
    - lunar_day: 农历日期 (数字)
    """
    if dt is None:
        dt = datetime.datetime.now(TZ_CN)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_CN)

    # 1. 转换为 Solar 对象 (lunar_python 需要)
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    
    # 2. 转为 Lunar 对象
    lunar = solar.getLunar()
    
    # 3. 获取干支 (库自动处理了节气交换，比如立春换年柱，节气换月柱)
    y_ganzhi = lunar.getYearInGanZhi()
    m_ganzhi = lunar.getMonthInGanZhi()
    d_ganzhi = lunar.getDayInGanZhi()
    h_ganzhi = lunar.getTimeInGanZhi()
    
    # 4. 获取农历中文描述
    lunar_month_cn = lunar.getMonthInChinese() + "月"
    lunar_day_cn = lunar.getDayInChinese()
    
    # 5. 获取农历数字 (用于梅花易数和小六壬计算)
    lunar_month_num = lunar.getMonth()
    lunar_day_num = lunar.getDay()
    
    # 6. 计算时辰索引 (子=0, 丑=1...)
    # 地支列表: 子丑寅卯辰巳午未申酉戌亥
    dizhi_list = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    h_zhi = h_ganzhi[1] # 取地支字符
    hour_idx = dizhi_list.index(h_zhi)

    gregorian_str = dt.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # 格式：乙巳年 戊子月 庚子日 丙子时 (农历十月十九)
    ganzhi_str = f"{y_ganzhi}年 {m_ganzhi}月 {d_ganzhi}日 {h_ganzhi}时 (农历{lunar_month_cn}{lunar_day_cn})"
    
    return gregorian_str, ganzhi_str, hour_idx, lunar_month_num, lunar_day_num

# ==========================================
# 核心逻辑：起卦引擎
# ==========================================
class DivinationEngine:
    @staticmethod
    def cast_liuyao_coin():
        """模拟金钱卦：3枚铜钱摇6次"""
        results = []
        display_lines = []
        
        for _ in range(6):
            coins = [random.randint(0, 1) for _ in range(3)]
            s = sum(coins)
            # sum=0(3背)->老阳(O,动), sum=1(2背1字)->少阴(--), sum=2(1背2字)->少阳(—), sum=3(3字)->老阴(X,动)
            if s == 0:
                val, name = 3, "老阳 O (动)"
            elif s == 1:
                val, name = 0, "少阴 --"
            elif s == 2:
                val, name = 1, "少阳 ——"
            else:
                val, name = 2, "老阴 X (动)"
            
            results.append(val)
            display_lines.append(name)
            
        return results, display_lines

    @staticmethod
    def cast_meihua_numbers(n1, n2):
        """梅花易数：数字起卦"""
        upper = n1 % 8
        if upper == 0: upper = 8
        
        lower = n2 % 8
        if lower == 0: lower = 8
        
        moving = (n1 + n2) % 6
        if moving == 0: moving = 6
        
        trigrams = {1:"乾", 2:"兑", 3:"离", 4:"震", 5:"巽", 6:"坎", 7:"艮", 8:"坤"}
        
        return {
            "upper": trigrams[upper],
            "lower": trigrams[lower],
            "moving_line": moving,
            "nums": (n1, n2)
        }

    @staticmethod
    def cast_xiaoliuren(lunar_month, lunar_day, hour_idx, method="time", nums=None):
        """
        小六壬起课 (逻辑修正：使用农历月份和日期)
        """
        states = ["大安", "留连", "速喜", "赤口", "小吉", "空亡"]
        
        if method == "numbers" and nums:
            # 报数法
            idx_1 = (nums[0] - 1) % 6
            idx_2 = (idx_1 + nums[1] - 1) % 6
            idx_3 = (idx_2 + nums[2] - 1) % 6
            seq = [states[idx_1], states[idx_2], states[idx_3]]
            return {"result": states[idx_3], "sequence": seq, "method": "报数"}
        else:
            # 时间法 (核心修正：使用农历数值)
            # 1. 月: 从大安起 (农历一月=1)
            idx_m = (lunar_month - 1) % 6
            
            # 2. 日: 从月上起 (农历初一=1)
            idx_d = (idx_m + lunar_day - 1) % 6
            
            # 3. 时: 从日上起 (子时=1...亥时=12)
            # hour_idx 0=子 -> 实际上通常子时算作1
            idx_h = (idx_d + (hour_idx + 1) - 1) % 6
            
            seq = [states[idx_m], states[idx_d], states[idx_h]]
            return {"result": states[idx_h], "sequence": seq, "method": "时间"}

# ==========================================
# UI 组件
# ==========================================
def draw_hexagram(lines_data):
    """绘制六爻卦象"""
    st.markdown("### 卦象图示")
    st.markdown('<div class="hexagram-container">', unsafe_allow_html=True)
    
    # 六爻是从下往上排，展示时倒序
    for i in range(5, -1, -1):
        line_type = lines_data[i]
        color = "#e57373" if line_type in [1, 3] else "#5c6bc0" # 柔和红/柔和蓝
        height = "8px"
        
        cols = st.columns([1, 6])
        with cols[0]:
            st.markdown(f"<span style='color:#888; font-size:12px;'>六{i+1}</span>", unsafe_allow_html=True)
        with cols[1]:
            if line_type in [1, 3]: # 阳
                st.markdown(f"<div style='background-color:{color}; height:{height}; border-radius:4px; width:100%; margin-bottom:8px;'></div>", unsafe_allow_html=True)
            else: # 阴
                st.markdown(f"""
                <div style='display:flex; justify-content:space-between; width:100%; margin-bottom:8px;'>
                    <div style='background-color:{color}; height:{height}; border-radius:4px; width:42%;'></div>
                    <div style='background-color:{color}; height:{height}; border-radius:4px; width:42%;'></div>
                </div>
                """, unsafe_allow_html=True)
            
            # 动爻标记
            if line_type == 3:
                st.markdown(f"<div style='text-align:center; font-size:10px; color:{color}; margin-top:-5px;'>O (老阳)</div>", unsafe_allow_html=True)
            elif line_type == 2:
                st.markdown(f"<div style='text-align:center; font-size:10px; color:{color}; margin-top:-5px;'>X (老阴)</div>", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# AI 流式处理核心逻辑
# ==========================================
def stream_ai_response(prompt, model):
    """处理 SiliconFlow API 的流式返回"""
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    
    st.markdown("---")
    st.subheader("🤖 AI 大师分析中...")
    
    reasoning_expander = st.expander("👁️ 查看 AI 思考过程 (Reasoning)", expanded=True)
    reasoning_placeholder = reasoning_expander.empty()
    content_placeholder = st.empty()
    
    full_reasoning = ""
    full_content = ""
    
    price_config = MODEL_PRICING.get(model, {"input": 10.0, "output": 10.0})
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位精通中国传统术数（六爻、梅花、奇门、六壬）的易学专家。请基于用户提供的【真实农历干支时间】进行分析。"},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            stream_options={"include_usage": True}
        )
        
        start_time = time.time()
        final_usage = None
        
        for chunk in response:
            if hasattr(chunk, 'usage') and chunk.usage:
                final_usage = chunk.usage
            
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    full_reasoning += delta.reasoning_content
                    reasoning_placeholder.markdown(full_reasoning + "▌")
                if hasattr(delta, 'content') and delta.content:
                    full_content += delta.content
                    content_placeholder.markdown(full_content + "▌")
        
        reasoning_placeholder.markdown(full_reasoning)
        content_placeholder.markdown(full_content)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if final_usage:
            in_tokens = final_usage.prompt_tokens
            out_tokens = final_usage.completion_tokens
            total_tokens = final_usage.total_tokens
            cost = (in_tokens * price_config['input'] + out_tokens * price_config['output']) / 1_000_000
            
            st.markdown(f"""
            <div class='cost-box'>
                <span>⏱️ 耗时: {duration:.2f}s</span>
                <span>📊 Tokens: {in_tokens} + {out_tokens} = {total_tokens}</span>
                <span>💰 预估费用: ¥{cost:.6f}</span>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"AI 连接出错: {str(e)}")

# ==========================================
# 主程序
# ==========================================
def main():
    # Sidebar
    st.sidebar.title("☯️ 控制台")
    model_name = st.sidebar.selectbox("选择 AI 模型", list(MODELS.keys()), index=0)
    selected_model = MODELS[model_name]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    📅 **当前时空能量**
    """)
    
    now_dt = datetime.datetime.now(TZ_CN)
    # 调用更新后的时间函数
    greg_str, ganzhi_str, hour_idx, lunar_month, lunar_day = get_ganzhi_time(now_dt)
    
    st.sidebar.info(f"📆 公历：{greg_str}")
    st.sidebar.warning(f"🌙 农历：{ganzhi_str}")
    st.sidebar.caption(f"注：所有起卦逻辑均已校准为农历 ({lunar_month}月{lunar_day}日)")
    
    st.sidebar.markdown("---")
    with st.sidebar.expander("📖 帮助与说明"):
        st.markdown("""
        **系统更新说明：**
        逻辑内核已升级，现采用天文算法计算农历与干支。
        
        **使用步骤：**
        1. 切换预测门类。
        2. 输入问题。
        3. 点击起卦/分析。
        """)

    # Main Area
    st.title("AI 智能易学预测系统")
    st.caption("融合传统术数算法与现代大模型推理技术的智能预测平台")
    
    # Tabs
    tabs = st.tabs(["🪙 六爻纳甲", "🌸 梅花易数", "🛡️ 奇门遁甲", "🌊 大六壬", "🖐️ 小六壬"])
    
    # =======================
    # 1. 六爻纳甲
    # =======================
    with tabs[0]:
        st.subheader("六爻纳甲")
        col1, col2 = st.columns([1, 2])
        with col1:
            ly_method = st.radio("起卦方式", ["在线摇卦", "手动装卦"], key="ly_method")
        with col2:
            question = st.text_input("🔮 你的问题 (如: 下个月跳槽是否顺利?)", key="ly_q")

        if "liuyao_result" not in st.session_state:
            st.session_state.liuyao_result = None

        if st.button("开始起卦", key="ly_btn", use_container_width=True):
            if not question:
                st.warning("请先输入问题。")
            else:
                with st.spinner("心诚则灵，正在摇卦..."):
                    time.sleep(1.5)
                    raw_lines, display_lines = DivinationEngine.cast_liuyao_coin()
                    st.session_state.liuyao_result = {
                        "raw": raw_lines,
                        "display": display_lines,
                        "time": ganzhi_str # 存储包含农历的干支时间
                    }

        if st.session_state.liuyao_result:
            res = st.session_state.liuyao_result
            c1, c2 = st.columns([1, 1])
            with c1:
                draw_hexagram(res['raw'])
            with c2:
                st.markdown(f"**起卦时间**: {res['time']}")
                st.markdown("**爻象记录**:")
                for i, l in enumerate(res['display']):
                    st.text(f"第 {i+1} 爻: {l}")
                
                run_ai = st.button("🤖 AI 深度解卦", key="ly_ai_btn", type="primary")

            if run_ai:
                line_details = []
                for idx, val in enumerate(res['raw']):
                    status = "阴" if val in [0, 2] else "阳"
                    movement = "静爻"
                    change_to = ""
                    if val == 2:
                        movement = "动爻"
                        change_to = " -> 变为阳"
                    elif val == 3:
                        movement = "动爻"
                        change_to = " -> 变为阴"
                    line_details.append(f"第{idx+1}爻（从下往上）：{status}（{movement}）{change_to}")

                prompt = f"""
                你是一位精通六爻纳甲的易学大师。
                【用户问题】：{question}
                【起卦时间】：{res['time']} (请特别注意月令、日辰的生克)
                【卦象结构】：
                {chr(10).join(line_details)}
                
                请直接进行深度逻辑推演，断吉凶与应期。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 2. 梅花易数
    # =======================
    with tabs[1]:
        st.subheader("梅花易数")
        c1, c2 = st.columns([1, 2])
        with c1:
            mh_method = st.radio("起卦方式", ["时间起卦", "随机报数"], key="mh_method")
        with c2:
            mh_question = st.text_input("🔮 所测之事", key="mh_q")
            
        if st.button("梅花起卦", key="mh_btn", use_container_width=True):
            if not mh_question:
                st.warning("请输入问题")
            else:
                n1, n2 = 0, 0
                if mh_method == "时间起卦":
                    # 修正：梅花易数时间起卦应当使用农历年月日
                    # 公式：(农历年支数 + 农历月数 + 农历日数) % 8 = 上卦
                    # 公式：(农历年支数 + 农历月数 + 农历日数 + 时支数) % 8 = 下卦
                    # 这里为了简化展示，我们把年、月、日、时都转化为数字叠加
                    # 年支数: 子=1...亥=12. 
                    # 简化逻辑：直接用 lunar_month 和 lunar_day 参与运算
                    year_zhi_idx = (now_dt.year - 4) % 12 + 1 # 简化的年支序数
                    
                    n1 = year_zhi_idx + lunar_month + lunar_day
                    n2 = n1 + (hour_idx + 1)
                    st.info(f"逻辑：农历{lunar_month}月{lunar_day}日 + 时辰数")
                else:
                    n1 = random.randint(1, 999)
                    n2 = random.randint(1, 999)
                
                st.session_state.mh_result = DivinationEngine.cast_meihua_numbers(n1, n2)

        if "mh_result" in st.session_state and st.session_state.mh_result:
            r = st.session_state.mh_result
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("上卦", r['upper'])
            col_g2.metric("下卦", r['lower'])
            col_g3.metric("动爻", f"第 {r['moving_line']} 爻")
            
            if st.button("🤖 AI 梅花断事", key="mh_ai", type="primary"):
                prompt = f"""
                你是一位梅花易数大师。
                【用户问题】：{mh_question}
                【起卦时间】：{ganzhi_str}
                【本卦】：上{r['upper']}下{r['lower']}
                【动爻】：{r['moving_line']}
                请依据体用生克与五行旺衰进行推断。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 3. 奇门遁甲
    # =======================
    with tabs[2]:
        st.subheader("奇门遁甲")
        c1, c2 = st.columns(2)
        with c1:
            qm_time = st.date_input("排盘日期", datetime.datetime.now(TZ_CN).date())
        with c2:
            qm_hour = st.time_input("排盘时间", datetime.datetime.now(TZ_CN).time())
            
        qm_question = st.text_input("🔮 奇门问测", key="qm_q")

        if st.button("奇门演局 & AI 分析", key="qm_btn", type="primary", use_container_width=True):
            if not qm_question:
                st.warning("请输入问题")
            else:
                full_dt = datetime.datetime.combine(qm_time, qm_hour)
                # 获取该特定时间的准确干支
                _, qm_ganzhi, _, _, _ = get_ganzhi_time(full_dt)
                
                st.success(f"排盘信息：{qm_ganzhi}")
                
                prompt = f"""
                你是一位奇门遁甲大师。
                **信息**：{qm_ganzhi}。
                **问题**：{qm_question}。
                请脑排盘（时家奇门），定局数、值符、值使，分析格局并给出决策建议。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 4. 大六壬
    # =======================
    with tabs[3]:
        st.subheader("大六壬")
        lr_q = st.text_input("🔮 六壬问事", key="lr_q")

        if st.button("六壬起课 & AI 分析", key="lr_btn", type="primary", use_container_width=True):
            if not lr_q:
                st.warning("请输入问题")
            else:
                st.success(f"起课信息：{ganzhi_str}")
                prompt = f"""
                你是一位精通大六壬的大师。
                **信息**：{ganzhi_str}。
                **问题**：{lr_q}。
                请确定月将，推演天地盘、四课三传，进行详细推断。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 5. 小六壬 (已修正)
    # =======================
    with tabs[4]:
        st.subheader("小六壬")
        c1, c2 = st.columns([1, 2])
        with c1:
            xlr_method = st.radio("起课方式", ["当前时间", "随机报数(3个)"], key="xlr_method")
        with c2:
            xlr_q = st.text_input("🔮 快速问测", key="xlr_q")
            
        if st.button("小六壬掐指一算", key="xlr_btn", type="primary", use_container_width=True):
            if not xlr_q:
                st.warning("请输入问题")
            else:
                nums = None
                method_code = "time"
                if "随机报数" in xlr_method:
                    method_code = "numbers"
                    nums = [random.randint(1, 9) for _ in range(3)]
                    st.info(f"随机报数: {nums}")
                else:
                    st.info(f"时间起课：农历{lunar_month}月 + 农历{lunar_day}日 + 时辰({hour_idx+1})")
                
                # 传入修正后的农历参数
                res = DivinationEngine.cast_xiaoliuren(
                    lunar_month, lunar_day, hour_idx, method=method_code, nums=nums
                )
                
                st.markdown("### 课象结果")
                col_res1, col_res2 = st.columns([1, 2])
                with col_res1:
                    st.metric("最终落宫", res['result'])
                with col_res2:
                    st.text(f"推演路径: {' -> '.join(res['sequence'])}")
                
                explanations = {
                    "大安": "大安事事昌，求财在坤方，失物去不远，宅舍保安康。",
                    "留连": "留连事难成，求谋日未明，官事只宜缓，去者未回程。",
                    "速喜": "速喜喜来临，求财向南行，失物申午未，逢人路上寻。",
                    "赤口": "赤口主口舌，官非切要防，失物速速讨，行人有惊慌。",
                    "小吉": "小吉最吉昌，路上好商量，阴人来报喜，失物在坤方。",
                    "空亡": "空亡事不长，阴人小乖张，求财无利益，行人有灾殃。"
                }
                st.info(explanations.get(res['result'], ""))
                
                if st.button("🤖 AI 详解", key="xlr_ai"):
                    prompt = f"""
                    你是一位精通小六壬的易学专家。
                    用户问题：{xlr_q}
                    起课时间：{ganzhi_str}
                    推演结果：{res['sequence']} -> 最终落宫【{res['result']}】。
                    请结合问题详解吉凶。
                    """
                    stream_ai_response(prompt, selected_model)

if __name__ == "__main__":
    main()
