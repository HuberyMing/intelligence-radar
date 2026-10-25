# scripts/inspector.py
import json
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Radar Inspector", 
    page_icon="📡", 
    layout="wide")

st.sidebar.title("📡 Radar Inspector")

# 1. 動態掃描 logs/traces 目錄下的所有批次
trace_dir = Path("logs/traces")
trace_files = sorted(list(trace_dir.glob("trace_*.jsonl")), reverse=True)

if not trace_files:
    st.warning("⚠️ 尚未找到任何 Trace 紀錄檔，請先執行 pipeline 產生日誌。")
    st.stop()

# 提取日期列表
date_options = [f.stem.replace("trace_", "") for f in trace_files]
selected_date = st.sidebar.selectbox("📅 選擇巡邏批次", date_options)

selected_file = trace_dir / f"trace_{selected_date}.jsonl"

# 2. 讀取並將同一情資的 Spans 聚合（以 entry_id 為單位）
raw_spans = []
if selected_file.exists():
    with open(selected_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    raw_spans.append(json.loads(line))
                except Exception:
                    continue

# 聚合邏輯：將同一個 entry_id 的所有 Span 打包在一起
aggregated_items = {}
for entry in raw_spans:
    eid = entry.get("entry_id")
    if not eid:
        continue
    if eid not in aggregated_items:
        aggregated_items[eid] = {
            "entry_id": eid,
            "source_title": entry.get("source_title", "Untitled"),
            "spans": [],
            "status": "ARCHIVED",  # 預設
        }
    
    # 支援讀取 span 或舊格式 traces
    if "span" in entry:
        aggregated_items[eid]["spans"].append(entry["span"])
    elif "traces" in entry:
        aggregated_items[eid]["spans"].extend(entry.get("traces", []))

# 判定情資最終狀態：如果跑過了 Editor 且成功，代表是 PROCESSED
for eid, item in aggregated_items.items():
    stage_names = [s.get("stage") for s in item["spans"]]
    if "Editor" in stage_names:
        item["status"] = "PROCESSED"
    elif any(s.get("status") == "ERROR" for s in item["spans"]):
        item["status"] = "ERROR"
    else:
        item["status"] = "ARCHIVED"

items_list = list(aggregated_items.values())

# 3. 側邊欄過濾控制項
status_filter = st.sidebar.multiselect(
    "🏷️ 狀態過濾",
    options=["PROCESSED", "ARCHIVED", "ERROR"],
    default=["PROCESSED", "ARCHIVED", "ERROR"]  # 預設全選，絕不漏看
)

search_query = st.sidebar.text_input("🔍 搜尋標題或 entry_id", "")

filtered_items = [
    item for item in items_list
    if item["status"] in status_filter
    and (search_query.lower() in item["source_title"].lower() or search_query.lower() in item["entry_id"].lower())
]

# 4. 頂部儀表板指標 (Metrics)
st.title(f"巡航除錯檢視：{selected_date}")

total_count = len(items_list)
processed_count = sum(1 for i in items_list if i["status"] == "PROCESSED")
pass_rate = (processed_count / total_count * 100) if total_count > 0 else 0.0

col1, col2, col3 = st.columns(3)
col1.metric("採集情資總數", f"{total_count} 筆")
col2.metric("通過初審 (PROCESSED)", f"{processed_count} 筆")
col3.metric("初審通過率", f"{pass_rate:.1f}%")

st.divider()

# 5. 情資審查串流與代理人思考鏈渲染
st.subheader("📄 情資審查串流與代理人思考鏈")

if not filtered_items:
    st.info("💡 目前篩選條件下無符合的情資項目，請調整側邊欄的過濾條件。")
else:
    for item in filtered_items:
        with st.expander(f"【{item['status']}】 [{item['entry_id']}] {item['source_title']}", expanded=(item["status"] == "PROCESSED")):
            st.markdown(f"**項目識別碼 (Entry ID):** `{item['entry_id']}`")
            
            # 依序展示該情資跑過的各個 Agent 階段
            stages = item["spans"]
            if not stages:
                st.write("尚無詳細思考鏈軌跡。")
            else:
                for idx, span in enumerate(stages, 1):
                    stage_name = span.get("stage", f"Step {idx}")
                    duration = span.get("duration_sec", 0)
                    status_icon = "✅" if span.get("status") == "SUCCESS" else "❌"
                    
                    # 依階段賦予專屬圖示
                    icons = {
                        "Reviewer": "⚖️ Reviewer 初審守門員",
                        "DomainExpert": "🔬 Domain Expert 領域提煉",
                        "Synthesizer": "🔮 Synthesizer 跨領域推演",
                        "Editor": "✍️ Editor 總編排版定稿",
                    }
                    display_title = icons.get(stage_name, f"階段: {stage_name}")
                    
                    st.markdown(f"#### Step {idx}: {display_title} ({status_icon} 耗時: `{duration}s`)")
                    
                    if span.get("error"):
                        st.error(f"遭遇錯誤: {span.get('error')}")
                    else:
                        st.caption(f"執行時間: {span.get('timestamp')}")
                        
                        # 🌟 渲染各 Agent 的思考摘要與推演文字
                        output_content = span.get("output_preview")
                        if output_content:
                            st.markdown("**🧠 代理人思考與萃取摘要：**")
                            st.info(output_content)
                        else:
                            st.caption("*(此批次執行時尚未擷取文字預覽)*")
                            
                    st.write("---")