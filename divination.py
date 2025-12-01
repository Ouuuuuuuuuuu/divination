import streamlit as st
import datetime
import random
import time
from openai import OpenAI

# ==========================================
# 配置与常量
# ==========================================
SILICONFLOW_API_KEY = "sk-lezqyzzxlcnarawzhmyddltuclijckeufnzzktmkizfslcje"
BASE_URL = "https://api.siliconflow.cn/v1"

MODELS = {
    "DeepSeek-R1": "deepseek-ai/DeepSeek-R1",
    "Kimi-K2-Thinking": "moonshotai/Kimi-K2-Thinking"
}

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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函数：干支历法（简化版）
# ==========================================
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

def get_ganzhi_time(dt=None):
    """简单的干支计算（仅作演示，专业排盘需更复杂的历法库）"""
    if dt is None:
        dt = datetime.datetime.now()
    
    # 简单的年柱
    year = dt.year
    y_idx = (year - 4) % 60
    y_gan = TIANGAN[y_idx % 10]
    y_zhi = DIZHI[y_idx % 12]
    
    # 简单的日柱 (使用参考点计算)
    base_date = datetime.date(1900, 1, 31) # 庚子日
    days = (dt.date() - base_date).days
    d_idx = (days + 36) % 60
    d_gan = TIANGAN[d_idx % 10]
    d_zhi = DIZHI[d_idx % 12]
    
    # 时柱 (日上起时)
    hour_zhi_idx = (dt.hour + 1) // 2 % 12
    start_h_gan_idx = (TIANGAN.index(d_gan) % 5) * 2
    h_gan = TIANGAN[(start_h_gan_idx + hour_zhi_idx) % 10]
    h_zhi = DIZHI[hour_zhi_idx]
    
    return f"{y_gan}{y_zhi}年 {dt.month}月 {d_gan}{d_zhi}日 {h_gan}{h_zhi}时", hour_zhi_idx

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
    def cast_xiaoliuren(month, day, hour_idx, method="time", nums=None):
        """
        小六壬起课
        states: 大安, 留连, 速喜, 赤口, 小吉, 空亡
        算法: (Month + Day + Hour - 2) % 6 (简化版) 或 递归步进
        这里采用递归步进法：
        月上起日，日上起时。
        """
        states = ["大安", "留连", "速喜", "赤口", "小吉", "空亡"]
        
        if method == "numbers" and nums:
            # 报数法：3个数字分别代表三个步骤
            idx_1 = (nums[0] - 1) % 6
            idx_2 = (idx_1 + nums[1] - 1) % 6
            idx_3 = (idx_2 + nums[2] - 1) % 6
            
            seq = [states[idx_1], states[idx_2], states[idx_3]]
            return {"result": states[idx_3], "sequence": seq, "method": "报数"}
            
        else:
            # 时间法
            # 1. 月: 从大安(0)起
            # 农历月大概近似公历月 (简化演示)
            idx_m = (month - 1) % 6
            
            # 2. 日: 从月上起
            idx_d = (idx_m + day - 1) % 6
            
            # 3. 时: 从日上起 (子时=1...亥时=12)
            # hour_idx 0=子, 11=亥 -> 实际步数为 hour_idx + 1
            idx_h = (idx_d + (hour_idx + 1) - 1) % 6
            
            seq = [states[idx_m], states[idx_d], states[idx_h]]
            return {"result": states[idx_h], "sequence": seq, "method": "时间"}

# ==========================================
# UI 组件
# ==========================================
def draw_hexagram(lines_data):
    """绘制六爻卦象"""
    st.markdown("### 卦象图示")
    # 使用自定义 CSS 类
    st.markdown('<div class="hexagram-container">', unsafe_allow_html=True)
    
    # 六爻是从下往上排，展示时倒序
    for i in range(5, -1, -1):
        line_type = lines_data[i]
        color = "#e57373" if line_type in [1, 3] else "#5c6bc0" # 柔和红/柔和蓝
        height = "8px"
        
        # 布局
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
# 主程序
# ==========================================

def main():
    # Sidebar
    st.sidebar.title("☯️ 控制台")
    model_name = st.sidebar.selectbox("选择 AI 模型", list(MODELS.keys()), index=0)
    selected_model = MODELS[model_name]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    ### 📅 当前干支
    """)
    now_dt = datetime.datetime.now()
    ganzhi_str, hour_idx = get_ganzhi_time(now_dt)
    st.sidebar.info(ganzhi_str)
    
    st.sidebar.markdown("---")
    with st.sidebar.expander("📖 帮助与说明"):
        st.markdown("""
        **如何使用本系统：**
        1. **选择预测门类**：点击上方标签页切换（六爻、梅花、奇门等）。
        2. **输入信息**：根据提示输入问题，选择起卦/起课方式。
        3. **获取结果**：系统会自动排盘并展示基础数据。
        4. **AI 分析**：点击“AI 大师解卦”，查看流式深度解析。
        
        **适用场景：**
        * **六爻**：具体事物的成败吉凶（如求财、问病）。
        * **梅花**：快速占断，灵动灵活。
        * **奇门遁甲**：运筹、方位、择时、复杂局势。
        * **大六壬**：人事复杂关系、职场、诉讼。
        * **小六壬**：极速断吉凶，寻找失物等。
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
                        "time": ganzhi_str
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
                
                if st.button("🤖 AI 深度解卦", key="ly_ai_btn", type="primary"):
                    prompt = f"""
                    你是一位精通六爻纳甲的易学大师。
                    用户问题：{question}
                    起卦时间：{res['time']}
                    卦象数据（从初爻到上爻）：{res['display']}
                    数字含义：0=少阴，1=少阳，2=老阴(变)，3=老阳(变)。
                    请分析本卦、变卦、世应关系及五行生克，给出吉凶判断。
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
                    n1 = now_dt.year + now_dt.month + now_dt.day
                    n2 = n1 + now_dt.hour
                else:
                    n1 = random.randint(1, 999)
                    n2 = random.randint(1, 999)
                
                st.session_state.mh_result = DivinationEngine.cast_meihua_numbers(n1, n2)
        
        if "mh_result" in st.session_state and st.session_state.mh_result:
            r = st.session_state.mh_result
            st.info(f"起卦数字: {r['nums']}")
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("上卦", r['upper'])
            col_g2.metric("下卦", r['lower'])
            col_g3.metric("动爻", f"第 {r['moving_line']} 爻")
            
            if st.button("🤖 AI 梅花断事", key="mh_ai", type="primary"):
                prompt = f"""
                你是一位梅花易数大师。用户问题：{mh_question}。
                卦象：上卦{r['upper']}，下卦{r['lower']}，动爻{r['moving_line']}。
                请根据体用生克理论，分析体卦、用卦、互卦、变卦，判断吉凶。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 3. 奇门遁甲
    # =======================
    with tabs[2]:
        st.subheader("奇门遁甲")
        st.caption("时家奇门排盘逻辑复杂，将由 AI 引擎进行全盘推演与分析。")
        
        c1, c2 = st.columns(2)
        with c1:
            qm_time = st.date_input("排盘日期", datetime.date.today())
        with c2:
            qm_hour = st.time_input("排盘时间", datetime.datetime.now().time())
            
        qm_question = st.text_input("🔮 奇门问测", key="qm_q")
        
        if st.button("奇门演局 & AI 分析", key="qm_btn", type="primary", use_container_width=True):
            if not qm_question:
                st.warning("请输入问题")
            else:
                full_dt = datetime.datetime.combine(qm_time, qm_hour)
                ganzhi, _ = get_ganzhi_time(full_dt)
                
                st.success(f"排盘时间：{full_dt} | 干支：{ganzhi}")
                
                prompt = f"""
                你是一位奇门遁甲大师。
                **信息**：时间 {full_dt}，干支 {ganzhi}。
                **问题**：{qm_question}。
                **任务**：
                1. 脑中排定该时辰的时家奇门盘（定局数、值符、值使）。
                2. 描述关键方位的星门神仪组合。
                3. 结合问题，通过奇门格局进行决策分析。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 4. 大六壬 (New)
    # =======================
    with tabs[3]:
        st.subheader("大六壬")
        st.caption("大六壬以月将加占时，推演天地盘、四课三传，为人事之王。")
        
        lr_q = st.text_input("🔮 六壬问事 (适合复杂人事、职场、官司)", key="lr_q")
        
        if st.button("六壬起课 & AI 分析", key="lr_btn", type="primary", use_container_width=True):
            if not lr_q:
                st.warning("请输入问题")
            else:
                full_dt = datetime.datetime.now()
                ganzhi, _ = get_ganzhi_time(full_dt)
                st.success(f"起课时间：{full_dt.strftime('%Y-%m-%d %H:%M')} | 干支：{ganzhi}")
                
                prompt = f"""
                你是一位精通大六壬金口诀的大师。
                **信息**：起课时间 {full_dt}，干支 {ganzhi}。
                **问题**：{lr_q}。
                **任务**：
                1. 确定月将（基于节气）。
                2. 推演天地盘关系，提取四课，试排三传（若能）。
                3. 分析干支关系、神煞。
                4. 针对用户的复杂人事问题给出详细推断。
                """
                stream_ai_response(prompt, selected_model)

    # =======================
    # 5. 小六壬 (New)
    # =======================
    with tabs[4]:
        st.subheader("小六壬")
        st.caption("马前课，即时速断，简单明了。")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            xlr_method = st.radio("起课方式", ["当前时间", "随机报数(3个)"], key="xlr_method")
        with c2:
            xlr_q = st.text_input("🔮 快速问测 (如: 钥匙丢哪了?)", key="xlr_q")
            
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
                
                # 计算
                res = DivinationEngine.cast_xiaoliuren(
                    now_dt.month, now_dt.day, hour_idx, method=method_code, nums=nums
                )
                
                # 结果展示
                st.markdown("### 课象结果")
                col_res1, col_res2 = st.columns([1, 2])
                with col_res1:
                    st.metric("最终落宫", res['result'])
                with col_res2:
                    st.text(f"推演路径: {' -> '.join(res['sequence'])}")
                
                # 解释卡片
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
                    推演结果：{res['sequence']} -> 最终落宫【{res['result']}】。
                    
                    请解释：
                    1. 最终落宫的含义（{res['result']}）。
                    2. 结合前两个步骤（{res['sequence'][0]}、{res['sequence'][1]}）的生克或过程含义。
                    3. 对用户问题的直接回答（吉/凶/方位/时间建议）。
                    """
                    stream_ai_response(prompt, selected_model)

# ==========================================
# AI 流式处理核心逻辑
# ==========================================
def stream_ai_response(prompt, model):
    """处理 SiliconFlow API 的流式返回，兼容思考模型"""
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    
    st.markdown("---")
    st.subheader("🤖 AI 大师分析中...")
    
    # 容器布局
    reasoning_expander = st.expander("👁️ 查看 AI 思考过程 (Reasoning)", expanded=True)
    reasoning_placeholder = reasoning_expander.empty()
    content_placeholder = st.empty()
    
    full_reasoning = ""
    full_content = ""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位精通中国传统术数（六爻、梅花、奇门、六壬）的易学专家，语气专业、平和，能将古文与现代白话结合解释。请根据不同的预测术数使用其专门的术语（如六爻讲世应、奇门讲星门、六壬讲课传）。"},
                {"role": "user", "content": prompt}
            ],
            stream=True
        )
        
        start_time = time.time()
        
        for chunk in response:
            delta = chunk.choices[0].delta
            
            # 处理思考过程
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                full_reasoning += delta.reasoning_content
                reasoning_placeholder.markdown(full_reasoning + "▌")
            
            # 处理正式回答
            if hasattr(delta, 'content') and delta.content:
                full_content += delta.content
                content_placeholder.markdown(full_content + "▌")
                
        # 结束流式输出
        reasoning_placeholder.markdown(full_reasoning)
        content_placeholder.markdown(full_content)
        
        end_time = time.time()
        st.caption(f"耗时: {end_time - start_time:.2f}秒")
        
    except Exception as e:
        st.error(f"AI 连接出错: {str(e)}")
        st.error("请检查 API Key 余额或网络连接。")

if __name__ == "__main__":
    main()
