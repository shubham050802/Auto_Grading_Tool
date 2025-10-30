import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io
import requests

# --- Page Configuration ---
st.set_page_config(
    page_title="Interactive Grading Tool",
    page_icon="🎓",
    layout="wide"
)

# --- Helper Functions ---
def convert_cloud_url(url):
    """Convert cloud storage URLs to direct download links"""
    import re

    # Google Drive URL patterns
    if 'drive.google.com' in url:
        # Extract file ID from various Google Drive URL formats
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID/view
            r'id=([a-zA-Z0-9_-]+)',        # ?id=FILE_ID
            r'/open\?id=([a-zA-Z0-9_-]+)'  # /open?id=FILE_ID
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                return f"https://drive.google.com/uc?export=download&id={file_id}"

    # Dropbox URL - just add dl=1 parameter
    elif 'dropbox.com' in url:
        if '?' in url:
            return url.replace('dl=0', 'dl=1') if 'dl=0' in url else url + '&dl=1'
        else:
            return url + '?dl=1'

    # OneDrive URL - replace 'view' with 'download'
    elif 'onedrive.live.com' in url or '1drv.ms' in url:
        return url.replace('view.aspx', 'download.aspx') if 'view.aspx' in url else url

    # Return original URL if no conversion needed
    return url

def load_file_from_url(url):
    """Load CSV or Excel file from URL with size limits and validation"""
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit for grading files

    try:
        # Convert cloud storage URLs to direct download links
        download_url = convert_cloud_url(url)

        # Add headers to mimic browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # First, make a HEAD request to check file size
        try:
            head_response = requests.head(download_url, headers=headers, timeout=10, allow_redirects=True)
            content_length = head_response.headers.get('Content-Length')
            if content_length:
                file_size = int(content_length)
                if file_size > MAX_FILE_SIZE:
                    raise Exception(f"File is too large ({file_size / (1024*1024):.1f} MB). Maximum allowed size is 50 MB. Please use a smaller file or upload directly.")
        except:
            # If HEAD request fails, continue with GET (some servers don't support HEAD)
            pass

        # Download the file with streaming to avoid memory issues
        response = requests.get(download_url, headers=headers, timeout=30, allow_redirects=True, stream=True)
        response.raise_for_status()

        # Check content type to detect Google Drive virus scan page
        content_type = response.headers.get('Content-Type', '').lower()

        # If we get HTML from Google Drive, it's likely the virus scan warning page
        if 'text/html' in content_type and 'drive.google.com' in url:
            raise Exception("Google Drive returned an HTML page instead of the file. This usually happens with large files.\n\n" +
                          "Solutions:\n" +
                          "1. Try downloading the file first, then use 'Upload File' option\n" +
                          "2. Make sure the file is small enough (< 50MB)\n" +
                          "3. Check that link sharing is enabled ('Anyone with the link can view')")

        # Read content with size limit
        content_bytes = b''
        downloaded_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                downloaded_size += len(chunk)
                if downloaded_size > MAX_FILE_SIZE:
                    raise Exception(f"File exceeds 50 MB size limit. Please use a smaller file or the 'Upload File' option.")
                content_bytes += chunk

        # Check if we got an HTML page (common with Google Drive issues)
        if content_bytes.startswith(b'<!DOCTYPE') or content_bytes.startswith(b'<html'):
            raise Exception("Received an HTML page instead of a data file. Please check:\n" +
                          "- The file sharing permissions are set correctly\n" +
                          "- The file is not too large (< 50MB recommended)\n" +
                          "- Try downloading the file manually first, then use 'Upload File'")

        # Detect file type and parse
        if url.endswith('.csv') or 'text/csv' in content_type or 'csv' in download_url:
            df = pd.read_csv(io.BytesIO(content_bytes))
        elif url.endswith(('.xlsx', '.xls')) or 'spreadsheet' in content_type or 'excel' in content_type:
            df = pd.read_excel(io.BytesIO(content_bytes), engine='openpyxl')
        else:
            # Try CSV first, then Excel
            try:
                df = pd.read_csv(io.BytesIO(content_bytes))
            except:
                try:
                    df = pd.read_excel(io.BytesIO(content_bytes), engine='openpyxl')
                except:
                    raise Exception("Could not parse file. Please ensure it's a valid CSV or Excel file.")

        # Validate that we got actual data
        if df.empty:
            raise Exception("File appears to be empty. Please check the file and try again.")

        return df

    except requests.exceptions.Timeout:
        raise Exception("Download timed out. The file might be too large or the connection is slow. Try:\n" +
                      "1. Using a smaller file\n" +
                      "2. Downloading the file first, then using 'Upload File' option")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to download file from URL. Please check:\n" +
                      "- The URL is accessible and not password-protected\n" +
                      "- You have an internet connection\n" +
                      "- For Google Drive: Make sure link sharing is enabled\n\nError: {str(e)}")
    except pd.errors.EmptyDataError:
        raise Exception("The file is empty or could not be read. Please check the file format.")
    except Exception as e:
        raise Exception(f"Failed to load file: {str(e)}")

def validate_data(df, marks_column):
    """Validate the loaded data"""
    errors = []
    warnings = []

    # Check if dataframe is empty
    if df.empty:
        errors.append("The file is empty. Please upload a file with data.")
        return errors, warnings

    # Check if marks column has data
    if marks_column not in df.columns:
        errors.append(f"Column '{marks_column}' not found in the file.")
        return errors, warnings

    # Check for numeric data in marks column
    if not pd.api.types.is_numeric_dtype(df[marks_column]):
        errors.append(f"The '{marks_column}' column must contain numeric values only.")

    # Check for marks out of range
    marks_data = df[marks_column].dropna()
    if len(marks_data) == 0:
        errors.append(f"No valid marks found in '{marks_column}' column.")
    else:
        if marks_data.min() < 0:
            warnings.append(f"Warning: Found negative marks (minimum: {marks_data.min():.2f})")
        if marks_data.max() > 100:
            warnings.append(f"Warning: Found marks above 100 (maximum: {marks_data.max():.2f})")

    return errors, warnings

def validate_grade_boundaries(boundaries):
    """Validate that grade boundaries are in descending order"""
    errors = []
    boundary_list = [
        ('A', boundaries['A']),
        ('A-', boundaries['A-']),
        ('B', boundaries['B']),
        ('B-', boundaries['B-']),
        ('C', boundaries['C']),
        ('C-', boundaries['C-']),
        ('D', boundaries['D']),
        ('E', boundaries['E'])
    ]

    for i in range(len(boundary_list) - 1):
        current_grade, current_val = boundary_list[i]
        next_grade, next_val = boundary_list[i + 1]
        if current_val <= next_val:
            errors.append(f"Grade {current_grade} boundary ({current_val}) must be greater than Grade {next_grade} boundary ({next_val})")

    return errors

# --- Main Application Logic ---
st.title("🎓 Interactive Grading Tool")
st.write("Grade student marks easily! Choose to upload a file or load from a URL.")

# --- Input Method Selection ---
st.info("📝 **File Format Requirements**: Your file should contain at least one numeric column with student marks (0-100). Supported formats: CSV, Excel (.xlsx, .xls)")

input_method = st.radio(
    "Choose input method:",
    ["📁 Upload File", "🔗 Load from URL", "🎯 Try Sample Data"],
    horizontal=True
)

uploaded_file = None
file_url = None
use_sample = False

if input_method == "📁 Upload File":
    uploaded_file = st.file_uploader(
        "Upload Student Marks File 📄",
        type=['csv','xlsx','xls'],
        help="Upload a CSV or Excel file containing student names and marks"
    )
elif input_method == "🔗 Load from URL":
    st.warning("⚠️ **File Size Limit**: Maximum 50 MB for URL loading. For larger files, please use 'Upload File' option.")
    file_url = st.text_input(
        "Enter file URL:",
        placeholder="https://drive.google.com/file/d/YOUR_FILE_ID/view",
        help="Paste a link to your CSV or Excel file from Google Drive, Dropbox, OneDrive, or any direct URL"
    )
    if file_url:
        st.success("✅ Cloud storage URLs supported: Google Drive, Dropbox, OneDrive")
        with st.expander("📖 How to get shareable links from different platforms"):
            st.markdown("""
            **Google Drive:**
            1. Right-click your file → "Share" → "Get link"
            2. Set to "Anyone with the link can view"
            3. Copy and paste the entire URL here

            **Dropbox:**
            1. Right-click your file → "Share" → "Create link"
            2. Copy and paste the link here

            **OneDrive:**
            1. Right-click your file → "Share" → "Copy link"
            2. Paste the link here

            **Direct URLs:**
            - Any publicly accessible CSV or Excel file URL will work
            - GitHub: Use the "Raw" file URL
            """)
else:  # Sample Data
    use_sample = True
    st.success("✨ Using sample data with 50 students. Try adjusting the grade boundaries!")

if uploaded_file is not None or file_url or use_sample:
    with st.spinner('Analyzing your file... Hang tight! ⏳'):
        try:
            # --- File Loading Logic ---
            if use_sample:
                # Load sample data
                df = pd.read_csv('student_data.csv')
                st.success("✅ Sample data loaded successfully!")
            elif file_url:
                # Load from URL
                df = load_file_from_url(file_url)
                st.success("✅ File loaded from URL successfully!")
            elif uploaded_file is not None:
                # Load uploaded file
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                else:
                    st.error("Unsupported file format. Please upload a CSV or Excel file.")
                    st.stop()
                st.success("✅ File uploaded successfully!")

            # Show data preview
            with st.expander("📋 Click to see the raw uploaded data"):
                st.dataframe(df, use_container_width=True)
                st.caption(f"Total rows: {len(df)} | Total columns: {len(df.columns)}")

            # --- Sidebar Configuration ---
            st.sidebar.header("⚙️ Configuration")

            # Check for numeric columns
            numeric_cols = df.select_dtypes(include=np.number).columns
            if len(numeric_cols) == 0:
                st.error("❌ No numeric columns found in the file. Please ensure your file has at least one column with numeric marks.")
                st.stop()

            marks_column = st.sidebar.selectbox(
                "Select the marks column:",
                numeric_cols,
                help="Choose the column containing student marks"
            )

            # Validate data
            errors, warnings = validate_data(df, marks_column)

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
                st.stop()

            if warnings:
                for warning in warnings:
                    st.warning(f"⚠️ {warning}")

            bin_count = st.sidebar.number_input(
                "Number of Bins:",
                min_value=5,
                max_value=50,
                value=20,
                help="Number of bins for the histogram visualization"
            )

            st.sidebar.subheader("📊 Grade Boundaries")
            st.sidebar.info("Set the **minimum** mark for each grade. Boundaries must be in descending order.")

            a_grade_min = st.sidebar.slider("Grade A", 0.0, 100.0, 90.0, step=0.1, help="Minimum mark for grade A")
            a_minus_grade_min = st.sidebar.slider("Grade A-", 0.0, 100.0, 80.0, step=0.1, help="Minimum mark for grade A-")
            b_grade_min = st.sidebar.slider("Grade B", 0.0, 100.0, 70.0, step=0.1, help="Minimum mark for grade B")
            b_minus_grade_min = st.sidebar.slider("Grade B-", 0.0, 100.0, 60.0, step=0.1, help="Minimum mark for grade B-")
            c_grade_min = st.sidebar.slider("Grade C", 0.0, 100.0, 50.0, step=0.1, help="Minimum mark for grade C")
            c_minus_grade_min = st.sidebar.slider("Grade C-", 0.0, 100.0, 40.0, step=0.1, help="Minimum mark for grade C-")
            d_grade_min = st.sidebar.slider("Grade D", 0.0, 100.0, 30.0, step=0.1, help="Minimum mark for grade D")
            e_grade_min = st.sidebar.slider("Grade E", 0.0, 100.0, 20.0, step=0.1, help="Minimum mark for grade E")

            # Validate grade boundaries
            boundaries = {
                'A': a_grade_min,
                'A-': a_minus_grade_min,
                'B': b_grade_min,
                'B-': b_minus_grade_min,
                'C': c_grade_min,
                'C-': c_minus_grade_min,
                'D': d_grade_min,
                'E': e_grade_min
            }

            boundary_errors = validate_grade_boundaries(boundaries)
            if boundary_errors:
                st.sidebar.error("⚠️ **Grade Boundary Issues:**")
                for error in boundary_errors:
                    st.sidebar.error(f"• {error}")
                st.warning("⚠️ Please adjust grade boundaries in the sidebar. They must be in descending order (A > A- > B > B- > C > C- > D > E).")

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

            # Add download button in sidebar
            st.sidebar.subheader("💾 Export Results")
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button(
                label="📥 Download Graded CSV",
                data=csv_data,
                file_name="graded_results.csv",
                mime="text/csv",
                help="Download the graded student list as a CSV file"
            )

        except Exception as e:
            st.error(f"❌ An error occurred: {e}")
            st.error("💡 **Troubleshooting tips:**")
            st.markdown("""
            - Ensure your file contains at least one numeric column
            - Check that the file URL is accessible and not password-protected
            - Verify the file format is CSV or Excel (.xlsx, .xls)
            - Make sure marks are numeric values (not text)
            """)
            st.stop()

    # --- Displaying the Results in Tabs ---
    st.header("📊 Results Dashboard")
    tab1, tab2, tab3 = st.tabs(["📊 Distribution & Stats", "📋 Graded List", "📈 Grade Summary"])

    with tab1:
        st.subheader("Marks Distribution")
        col1, col2 = st.columns([3, 2]) # Give more space to the histogram
        with col1:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(df[marks_column].dropna(), bins=bin_count, color='royalblue', edgecolor='black', alpha=0.7)
            ax.set_title(f"Distribution of {marks_column}", fontsize=14, fontweight='bold')
            ax.set_xlabel("Marks", fontsize=12)
            ax.set_ylabel("Number of Students", fontsize=12)
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # Add vertical lines for grade boundaries with distinct colors
            grade_colors = {
                'A': '#2ecc71',    # Green
                'A-': '#27ae60',   # Dark Green
                'B': '#3498db',    # Blue
                'B-': '#2980b9',   # Dark Blue
                'C': '#f39c12',    # Orange
                'C-': '#e67e22',   # Dark Orange
                'D': '#e74c3c',    # Red
                'E': '#c0392b',    # Dark Red
            }

            ax.axvline(a_grade_min, color=grade_colors['A'], linestyle='--', linewidth=2, alpha=0.8, label=f'A: {a_grade_min}')
            ax.axvline(a_minus_grade_min, color=grade_colors['A-'], linestyle='--', linewidth=2, alpha=0.8, label=f'A-: {a_minus_grade_min}')
            ax.axvline(b_grade_min, color=grade_colors['B'], linestyle='--', linewidth=2, alpha=0.8, label=f'B: {b_grade_min}')
            ax.axvline(b_minus_grade_min, color=grade_colors['B-'], linestyle='--', linewidth=2, alpha=0.8, label=f'B-: {b_minus_grade_min}')
            ax.axvline(c_grade_min, color=grade_colors['C'], linestyle='--', linewidth=2, alpha=0.8, label=f'C: {c_grade_min}')
            ax.axvline(c_minus_grade_min, color=grade_colors['C-'], linestyle='--', linewidth=2, alpha=0.8, label=f'C-: {c_minus_grade_min}')
            ax.axvline(d_grade_min, color=grade_colors['D'], linestyle='--', linewidth=2, alpha=0.8, label=f'D: {d_grade_min}')
            ax.axvline(e_grade_min, color=grade_colors['E'], linestyle='--', linewidth=2, alpha=0.8, label=f'E: {e_grade_min}')

            ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Summary Statistics")
            data = df[marks_column].dropna()
            st.metric(label="📊 Mean", value=f"{data.mean():.2f}")
            st.metric(label="📍 Median", value=f"{data.median():.2f}")
            st.metric(label="📈 Standard Deviation", value=f"{data.std():.2f}")
            st.metric(label="🏆 Highest Mark", value=f"{data.max():.2f}")
            st.metric(label="📉 Lowest Mark", value=f"{data.min():.2f}")
            st.metric(label="👥 Total Students", value=f"{len(data)}")

    with tab2:
        st.subheader("Full Graded Student List")
        st.caption("This table shows all students with their assigned grades. You can sort by clicking column headers.")

        # Color-code grades for better visualization
        def highlight_grades(row):
            grade = row['Grade']
            color_map = {
                'A': 'background-color: #d5f4e6; color: #0e6655',
                'A-': 'background-color: #d5f4e6; color: #0e6655',
                'B': 'background-color: #d6eaf8; color: #1b4f72',
                'B-': 'background-color: #d6eaf8; color: #1b4f72',
                'C': 'background-color: #fdeaa7; color: #875a12',
                'C-': 'background-color: #fdeaa7; color: #875a12',
                'D': 'background-color: #fadbd8; color: #78281f',
                'E': 'background-color: #fadbd8; color: #78281f',
                'F': 'background-color: #f5b7b1; color: #641e16'
            }
            return [color_map.get(grade, '')] * len(row)

        styled_df = df.style.apply(highlight_grades, axis=1)
        st.dataframe(styled_df, use_container_width=True)

        # Add export button here too
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download This Table as CSV",
            data=csv,
            file_name="graded_student_list.csv",
            mime="text/csv",
        )

    with tab3:
        st.subheader("Summary of Grades Awarded")
        grade_counts = df['Grade'].value_counts().reindex(['A', 'A-', 'B', 'B-', 'C', 'C-', 'D', 'E', 'F'], fill_value=0)

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("#### Grade Distribution Table")
            grade_df = pd.DataFrame({
                'Grade': grade_counts.index,
                'Count': grade_counts.values,
                'Percentage': (grade_counts.values / len(df) * 100).round(2)
            })
            st.dataframe(grade_df, use_container_width=True, hide_index=True)

            # Pass/Fail Summary
            st.markdown("#### Pass/Fail Summary")
            pass_count = df[df['Grade'] != 'F'].shape[0]
            fail_count = df[df['Grade'] == 'F'].shape[0]
            pass_rate = (pass_count / len(df) * 100)

            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("✅ Pass", pass_count, f"{pass_rate:.1f}%")
            with col_b:
                st.metric("❌ Fail", fail_count, f"{100-pass_rate:.1f}%")

        with col2:
            st.markdown("#### Grade Distribution Chart")
            fig2, ax2 = plt.subplots(figsize=(8, 5))
            colors = ['#2ecc71', '#27ae60', '#3498db', '#2980b9', '#f39c12', '#e67e22', '#e74c3c', '#c0392b', '#95a5a6']
            ax2.bar(grade_counts.index, grade_counts.values, color=colors, edgecolor='black', alpha=0.8)
            ax2.set_xlabel('Grade', fontsize=12)
            ax2.set_ylabel('Number of Students', fontsize=12)
            ax2.set_title('Distribution of Grades', fontsize=14, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3, linestyle='--')

            # Add value labels on bars
            for i, (grade, count) in enumerate(zip(grade_counts.index, grade_counts.values)):
                ax2.text(i, count + 0.5, str(count), ha='center', va='bottom', fontweight='bold')

            plt.tight_layout()
            st.pyplot(fig2)

else:
    st.header("☝️ Upload a file to get started!")
    st.markdown("""
    ### 🚀 Quick Start Guide

    **Option 1: Upload a File**
    - Prepare a CSV or Excel file with student marks
    - Click on "Upload File" and select your file

    **Option 2: Load from URL**
    - Get a direct link to your CSV or Excel file
    - Paste the URL in the input field

    **Option 3: Try Sample Data**
    - Click "Try Sample Data" to see how it works
    - Experiment with grade boundaries using the sliders

    ---

    ### 📋 File Format Example

    Your file should have columns like this:

    | Name | Roll No | Marks |
    |------|---------|-------|
    | John | 101 | 85 |
    | Jane | 102 | 92 |
    | Bob | 103 | 78 |

    ✅ At least one numeric column with marks is required.
    """)