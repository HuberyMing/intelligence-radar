# scripts/inspector.py
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Agent Pipeline Inspector",
    page_icon="📡",
    layout="wide"
)

# 1. 載入並快取追蹤紀錄
@st.cache_data
def load_trace_files() -> dict[str, Path]:
    log_dir = Path("logs/traces")
    if not log_dir.exists():
        return {}
    files = sorted(log_dir.glob("trace_*.jsonl"), reverse=True)
    return {f.stem.replace("trace_", ""): f for f in files}

def parse_trace_data(file_path: Path) -> list[dict]:
    records = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

# 2. 側邊欄：巡檢批次與條件過濾
st.sidebar.title("📡 Radar Inspector")
available_dates = load_trace_files()

if not available_dates:
    st.warning("⚠️ 尚未偵測到任何追蹤日誌 (logs/traces/trace_*.jsonl)！請先執行巡航管線。")
    st.stop()

selected_date = st.sidebar.selectbox("📅 選擇巡邏批次", list(available_dates.keys()))
raw_data = parse_trace_data(available_dates[selected_date])

status_filter = st.sidebar.multiselect(
    "🏷️ 狀態過濾",
    options=["PROCESSED", "ARCHIVED", "ERROR"],
    default=["PROCESSED", "ARCHIVED", "ERROR"]
)
search_query = st.sidebar.text_input("🔍 搜尋標題或 entry_id", "")

filtered_data = [
    item for item in raw_data
    if item.get("status") in status_filter
    and (search_query.lower() in item.get("source_title", "").lower() or search_query in item.get("entry_id", ""))
]

# 3. 主畫面：指標卡片概覽
st.title(f"巡航除錯檢視：{selected_date}")

col1, col2, col3, col4 = st.columns(4)
total_count = len(raw_data)
processed_count = sum(1 for d in raw_data if d.get("status") == "PROCESSED")
pass_rate = (processed_count / total_count * 100) if total_count > 0 else 0
avg_score = (
    sum(d.get("verified_score", 0) for d in raw_data if d.get("verified_score")) / total_count
) if total_count > 0 else 0

col1.metric("採集情資總數", f"{total_count} 筆")
col2.metric("通過初審 (PROCESSED)", f"{processed_count} 筆")
col3.metric("初審通過率", f"{pass_rate:.1f}%")
col4.metric("平均技術評分", f"{avg_score:.2f} / 5.0")

st.divider()

# 4. 條目列表與思考鏈明細
st.subheader("📑 情資審查串流與代理人思考鏈")

for item in filtered_data:
    status = item.get("status")
    score = item.get("verified_score", "N/A")
    title = item.get("source_title", "未命名標題")
    entry_id = item.get("entry_id", "未知ID")

    # 狀態標記與顏色區分
    badge = "🟢 [PROCESSED]" if status == "PROCESSED" else ("🟡 [ARCHIVED]" if status == "ARCHIVED" else "🔴 [ERROR]")
    
    with st.expander(f"{badge} (Score: {score}) | {title} [{entry_id}]"):
        st.markdown(f"**來源網址**：{item.get('source_url', '無')}")
        
        traces = item.get("traces", [])
        if not traces:
            st.info("此項目無代理人追蹤記錄。")
            continue

        # 呈現代理人依序執行的思考流
        st.markdown("#### 🧠 代理人思考時間軸")
        for idx, span in enumerate(traces, 1):
            agent_name = span.get("agent_name")
            duration = span.get("duration_ms", 0)
            decision = span.get("decision", "OK")
            thought = span.get("thought_process", "無詳細記錄")
            err = span.get("error")

            icon = "🤖"
            if agent_name == "Reviewer":
                icon = "⚖️"
            elif agent_name == "DomainExpert":
                icon = "🔬"
            elif agent_name == "Synthesizer":
                icon = "🔮"
            elif agent_name == "Editor":
                icon = "✍️"

            st.markdown(f"**Step {idx}：{icon} {agent_name}** `({duration} ms)` — 決策: `{decision}`")
            if err:
                st.error(f"執行錯誤：{err}")
            else:
                st.info(thought)