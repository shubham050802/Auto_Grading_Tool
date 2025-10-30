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

# --- Helper Functions ---
def convert_cloud_url(url):
    """Convert cloud storage URLs to direct download links"""
    import re

    # Google Sheets URL - convert to CSV export
    if 'docs.google.com/spreadsheets' in url:
        # Extract spreadsheet ID from various Google Sheets URL formats
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9_-]+)',  # /spreadsheets/d/SHEET_ID/edit
            r'spreadsheets/d/([a-zA-Z0-9_-]+)',   # Alternative pattern
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                sheet_id = match.group(1)
                # Export as CSV (first sheet by default)
                return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

    # Google Drive URL patterns
    elif 'drive.google.com' in url:
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
st.write("Let's grade some papers! Upload a file with student marks to begin.")

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
        placeholder="https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
        help="Paste a link to your Google Sheets, Google Drive, Dropbox, OneDrive, or direct CSV/Excel file URL"
    )
    if file_url:
        st.success("✅ Supported: Google Sheets, Google Drive, Dropbox, OneDrive, Direct URLs")
        with st.expander("📖 How to get shareable links from different platforms"):
            st.markdown("""
            **Google Sheets** ⭐ Easiest Option:
            1. Click "Share" button (top right corner)
            2. Set to "Anyone with the link can view"
            3. Copy and paste the entire URL here
            4. The tool will automatically export the first sheet as CSV

            **Google Drive Files:**
            1. Right-click your file → "Share" → "Get link"
            2. Set to "Anyone with the link can view"
            3. Copy and paste the entire URL here

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