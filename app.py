import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="JSON to Excel Filter Tool", layout="wide")

st.title("📊 Tool Lọc Dữ Liệu JSON & Xuất Excel")
st.write("Tải file JSON lên -> Chọn cột cần lọc -> Chọn giá trị -> Tải file Excel.")

# 1. Upload File
uploaded_file = st.file_uploader("Tải lên file JSON của bạn", type=["json"])

if uploaded_file is not None:
    try:
        # Đọc dữ liệu
        data = pd.read_json(uploaded_file)

        # Xử lý trường hợp cột _id là dictionary (đặc trưng của MongoDB)
        # Chuyển {'$oid': '...'} thành chuỗi văn bản để dễ nhìn và lọc
        if '_id' in data.columns:
            data['_id'] = data['_id'].apply(lambda x: x['$oid'] if isinstance(x, dict) and '$oid' in x else str(x))

        st.success("✅ Đã tải dữ liệu thành công!")
        
        # Giao diện lọc dữ liệu
        st.subheader("🔍 Bộ lọc dữ liệu")
        col1, col2 = st.columns(2)

        with col1:
            # Cho phép chọn Key (Cột) để lọc
            all_columns = data.columns.tolist()
            selected_column = st.selectbox("Chọn cột bạn muốn lọc (Key):", all_columns)

        with col2:
            # Lấy các giá trị duy nhất trong cột đã chọn
            unique_values = data[selected_column].unique().tolist()
            selected_values = st.multiselect(
                f"Chọn giá trị trong '{selected_column}':", 
                options=unique_values,
                default=unique_values
            )

        # 2. Thực hiện Lọc
        filtered_df = data[data[selected_column].isin(selected_values)]

        # Hiển thị kết quả
        st.write(f"Tìm thấy **{len(filtered_df)}** dòng thỏa mãn điều kiện.")
        st.dataframe(filtered_df, use_container_width=True)

        # 3. Xuất file Excel
        if not filtered_df.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='FilteredData')
            
            st.download_button(
                label="📥 Tải kết quả lọc về Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name=f"loc_{selected_column}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Không có dữ liệu nào khớp với lựa chọn của bạn.")

    except Exception as e:
        st.error(f"Lỗi: {e}")
