import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- Page Configuration ---
st.set_page_config(
    page_title="Interactive Grading Tool",
    page_icon="🎓",
    layout="wide"
)

# --- Main Application Logic ---
st.title("🎓 Interactive Grading Tool")
st.write("Let's grade some papers! Upload a file with student marks to begin.")

# --- File Uploader ---
uploaded_file = st.file_uploader("Upload Student Marks File 📄", type=['csv','xlsx','xls'])

if uploaded_file is not None:
    with st.spinner('Analyzing your file... Hang tight! ⏳'):
        try:
            # --- File Loading Logic ---
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                st.error("Unsupported file format. Please upload a CSV or Excel file.")
                st.stop()

            st.success("✅ File loaded successfully!")
            with st.expander("Click to see the raw uploaded data"):
                st.dataframe(df, use_container_width=True)

            # --- Sidebar Configuration ---
            st.sidebar.header("⚙️ Configuration")
            marks_column = st.sidebar.selectbox(
                "Select the marks column:",
                df.select_dtypes(include=np.number).columns
            )

            bin = st.sidebar.number_input("Number of Bins:", value= 20)
            

            st.sidebar.subheader("Grade Boundaries")
            st.sidebar.info("Set the **minimum** mark for each grade.")
            a_grade_min = st.sidebar.slider("Grade A", 0.0, 100.0, 90.0, step=0.1)
            a_minus_grade_min = st.sidebar.slider("Grade A-", 0.0, 100.0, 80.0, step=0.1)
            b_grade_min = st.sidebar.slider("Grade B", 0.0, 100.0, 70.0, step=0.1)
            b_minus_grade_min = st.sidebar.slider("Grade B-", 0.0, 100.0, 60.0, step=0.1)
            c_grade_min = st.sidebar.slider("Grade C", 0.0, 100.0, 50.0, step=0.1)
            c_minus_grade_min = st.sidebar.slider("Grade C-", 0.0, 100.0, 40.0, step=0.1)
            d_grade_min = st.sidebar.slider("Grade D", 0.0, 100.0, 30.0, step=0.1)
            e_grade_min = st.sidebar.slider("Grade E", 0.0, 100.0, 20.0, step=0.1)

            # --- Grading Logic ---
            def assign_grade(mark):
                if mark >= a_grade_min: return 'A'
                elif mark >= a_minus_grade_min: return 'A-'
                elif mark >= b_grade_min: return 'B'
                elif mark >= b_minus_grade_min: return 'B-'
                elif mark >= c_grade_min: return 'C'
                elif mark >= c_minus_grade_min: return 'C-'
                elif mark >= d_grade_min: return 'D'
                elif mark >= e_grade_min: return 'E'
                else: return 'F'

            df['Grade'] = df[marks_column].apply(assign_grade)

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.stop()

    # --- Displaying the Results in Tabs ---
    st.header("📊 Results Dashboard")
    tab1, tab2, tab3 = st.tabs(["📊 Distribution & Stats", "📋 Graded List", "📈 Grade Summary"])

    with tab1:
        st.subheader("Marks Distribution")
        col1, col2 = st.columns([3, 2]) # Give more space to the histogram
        with col1:
            fig, ax = plt.subplots()
            ax.hist(df[marks_column].dropna(), bins= bin, color='royalblue', edgecolor='black')
            ax.set_title(f"Distribution of {marks_column}")
            ax.set_xlabel("Marks")
            ax.set_ylabel("Number of Students")
            ax.grid(axis='y', alpha=0.75)
            # Add vertical lines for grade boundaries
            ax.axvline(a_grade_min, color='green', linestyle='--', label=f'A ({a_grade_min})')
            ax.axvline(a_minus_grade_min, color='blue', linestyle='--', label=f'A- ({a_minus_grade_min})')
            ax.axvline(b_grade_min, color='orange', linestyle='--', label=f'B ({b_grade_min})')
            ax.axvline(b_minus_grade_min, color='red', linestyle='--', label=f'B- ({b_minus_grade_min})')
            ax.axvline(c_grade_min, color='green', linestyle='--', label=f'C ({c_grade_min})')
            ax.axvline(c_minus_grade_min, color='blue', linestyle='--', label=f'C- ({c_minus_grade_min})')
            ax.axvline(d_grade_min, color='red', linestyle='--', label=f'D ({d_grade_min})')
            ax.axvline(e_grade_min, color='orange', linestyle='--', label=f'E ({e_grade_min})')
            ax.legend()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Summary Statistics")
            data = df[marks_column].dropna()
            st.metric(label="Mean", value=f"{data.mean():.2f}")
            st.metric(label="Median", value=f"{data.median():.2f}")
            st.metric(label="Standard Deviation", value=f"{data.std():.2f}")
            st.metric(label="Highest Mark", value=f"{data.max():.2f}")
            st.metric(label="Lowest Mark", value=f"{data.min():.2f}")

    with tab2:
        st.subheader("Full Graded Student List")
        st.dataframe(df, use_container_width=True)

    with tab3:
        st.subheader("Summary of Grades Awarded")
        grade_counts = df['Grade'].value_counts().sort_index()
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(grade_counts, use_container_width=True)
        with col2:
            st.bar_chart(grade_counts)

else:
    st.header("☝️ Upload a file to get started!")