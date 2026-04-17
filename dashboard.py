import streamlit as st
import json
import os
import pandas as pd

# إعدادات الصفحة
st.set_page_config(page_title="SiteSentry Dashboard", page_icon="🚧", layout="wide")
st.title("🚧 SiteSentry Live Dashboard")
st.markdown("Live monitoring of autonomous construction inspection (Sockets & Structural Walls).")

if os.path.exists('final_site_report.json'):
    with open('final_site_report.json', 'r') as f:
        data = json.load(f)
        
    project_name = data['summary'].get('project_name', 'SiteSentry Inspection')
    st.subheader(f"Project: {project_name}")
    
    # 1. قسم الإحصائيات (Metrics)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Targets", data['summary']['total_targets'])
    col2.metric("Completed Inspections", data['summary']['completed'])
    
    # محاولة جلب الوقت بشكل آمن
    time_str = data['summary']['timestamp']
    time_display = time_str.split()[3] if len(time_str.split()) > 3 else time_str
    col3.metric("Last Update", time_display)
    
    st.divider()
    
    # فصل البيانات برمجياً إلى قائمتين (مقابس وجدران)
    details = data.get('details', [])
    sockets_data = [d for d in details if d.get('type') == 'socket']
    walls_data = [d for d in details if d.get('type') == 'wall_tilt']
    
    # ==========================================
    # القسم الأول: جدول المقابس الكهربائية
    # ==========================================
    st.header("🔌 Electrical Sockets Inspection")
    if sockets_data:
        df_sockets = pd.DataFrame(sockets_data)
        
        # درع الحماية: إذا لم يتم إنشاء تقرير ذكاء اصطناعي، ضع قيمة افتراضية
        if 'ai_report' not in df_sockets.columns:
            df_sockets['ai_report'] = 'N/A'
            
        # إخفاء الإحداثيات لتبسيط الجدول
        df_sockets = df_sockets[['id', 'status', 'ai_report']]
        
        # تلوين الحالات
        def color_socket_status(val):
            if val == 'Verified': return 'color: #27ae60; font-weight: bold' # أخضر
            elif val in ['Issue Detected', 'Camera Error']: return 'color: #c0392b; font-weight: bold' # أحمر
            return 'color: gray'
            
        st.dataframe(df_sockets.style.map(color_socket_status, subset=['status']), use_container_width=True)
    else:
        st.info("No sockets data available in this mission.")

    st.divider()

    # ==========================================
    # القسم الثاني: جدول تحليل الجدران
    # ==========================================
    st.header("🧱 Structural Wall Tilt Analysis")
    if walls_data:
        df_walls = pd.DataFrame(walls_data)
        
        # درع الحماية: إذا لم يسجل الروبوت أي ميلان لعدم وصوله، نضع عموداً فارغاً
        if 'tilt_degrees' not in df_walls.columns:
            df_walls['tilt_degrees'] = None
            
        df_walls = df_walls[['wall_name', 'id', 'status', 'tilt_degrees']]
        
        # تلوين زاوية الميلان (إذا زاد عن 0.5 يعتبر خطأ هندسي)
        def color_tilt(val):
            try:
                if float(val) > 0.5:
                    return 'color: #c0392b; font-weight: bold' # أحمر للخطأ
                return 'color: #27ae60' # أخضر للسليم
            except:
                return ''

        # عرض التقرير المجمع (متوسط ميلان كل جدار)
        st.subheader("Wall Summaries (Average Tilt)")
        # نجمع البيانات حسب اسم الجدار ونأخذ المتوسط
        wall_summary = df_walls.groupby('wall_name')['tilt_degrees'].mean().reset_index()
        wall_summary.rename(columns={'tilt_degrees': 'Average Tilt (°)'}, inplace=True)
        st.dataframe(wall_summary.style.map(color_tilt, subset=['Average Tilt (°)']), use_container_width=True)

        # عرض القراءات التفصيلية لكل نقطة
        with st.expander("Show detailed points reading"):
            st.dataframe(df_walls.style.map(color_tilt, subset=['tilt_degrees']), use_container_width=True)

    else:
        st.info("No wall tilt data available in this mission.")

else:
    st.warning("⏳ Waiting for robot to start mission... (No JSON file found yet)")