import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# -----------------------------
# Google Sheets Setup
# -----------------------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
CLIENT = gspread.authorize(CREDS)
SHEET = CLIENT.open("Auditapp").sheet1  # replace with your sheet name


# -----------------------------
# Ensure header exists
# -----------------------------
def ensure_header():
    """Only set the header if the sheet is completely empty."""
    default_header = ["Date", "Description", "Closing Balance"]
    try:
        rows = SHEET.get_all_values()
        if not rows:  
            SHEET.insert_row(default_header, index=1)
        elif all(cell.strip() == "" for cell in rows[0]):
            SHEET.update('A1', [default_header])
    except Exception as e:
        print(f"Error initializing header: {e}")


# -----------------------------
# Add a new site
# -----------------------------
def add_site(new_site):
    new_site = new_site.strip()
    if not new_site:
        return "⚠️ Enter a site name first", None

    header = SHEET.row_values(1)
    if new_site in header:
        return "⚠️ Site already exists", tuple(header[2:-1]) if len(header) >= 4 else tuple()

    try:
        # Find the index of "Closing Balance" and insert before it
        closing_index = header.index("Closing Balance") + 1

        # Prepare one column's worth of values
        values_to_insert = [[new_site] + [""] * (SHEET.row_count - 1)]

        SHEET.insert_cols(values_to_insert, col=closing_index)

        updated_sites = tuple(SHEET.row_values(1)[2:-1])
        return f"✅ Site '{new_site}' added", updated_sites
    except ValueError:
        return "❌ 'Closing Balance' column not found", None
    except Exception as e:
        return f"❌ Failed to add site: {e}", None



# -----------------------------
# Update TOTAL row
# -----------------------------
def update_total_row():
    try:
        header = SHEET.row_values(1)
        site_columns = range(2, len(header) - 1)
        rows = SHEET.get_all_values()[1:]

        if rows and rows[-1][0].upper() == "TOTAL":
            SHEET.delete_rows(len(rows) + 1)
            rows = rows[:-1]

        totals = ["TOTAL", ""]
        closing_total = 0
        for col in site_columns:
            col_sum = sum(float(row[col]) if row[col] else 0 for row in rows)
            totals.append(col_sum)
            closing_total += col_sum
        totals.append(closing_total)

        SHEET.append_row(totals)
    except Exception as e:
        print(f"Error updating TOTAL row: {e}")


# -----------------------------
# Add transaction
# -----------------------------
def add_transaction(date, site, description, amount_text):
    date = date.strip()
    site = site.strip()
    description = description.strip()
    amount_text = amount_text.strip()

    if site == "Select Site" or site == "":
        return "⚠️ Please select a valid site"
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return "⚠️ Invalid date format"
    try:
        amount = float(amount_text)
    except ValueError:
        return "⚠️ Amount must be a number"

    try:
        header = SHEET.row_values(1)
        if site not in header:
            return "⚠️ Site column missing"
        site_col_index = header.index(site) + 1

        closing_index = len(header)
        rows = SHEET.get_all_values()[1:]
        total_closing = 0
        for row in rows:
            for i in range(2, closing_index):
                try:
                    total_closing += float(row[i])
                except:
                    continue

        total_closing += amount

        new_row = [date, description] + [""] * (closing_index - 2) + [total_closing]
        new_row[site_col_index - 1] = amount

        if rows and rows[-1][0].upper() == "TOTAL":
            SHEET.delete_rows(len(rows) + 1)

        SHEET.append_row(new_row)
        update_total_row()

        return f"✅ Transaction added: {date}, {site}, {description}, {amount}"

    except Exception as e:
        return f"❌ Failed to add transaction: {e}"


# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Ledger App", page_icon="🧾", layout="centered")
st.title("🧾 Ledger App")
st.caption("Google Sheets–backed ledger with sites, deposits, and payments.")

if "initialized" not in st.session_state:
    ensure_header()
    st.session_state.initialized = True

header = SHEET.row_values(1) or ["Date", "Description", "Site A", "Site B", "Closing Balance"]
site_values = header[2:-1] if len(header) >= 4 else []
site_options = ["Select Site"] + site_values

with st.form("transaction_form", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        date_input = st.text_input(
            "Date (YYYY-MM-DD)",
            value=datetime.today().strftime('%Y-%m-%d')
        )
        desc_input = st.text_input("Description", value="")
        amount_input = st.text_input("Amount", value="")
        txn_type = st.selectbox("Transaction Type", ["Deposit", "Payment"])
    with col2:
        site_selected = st.selectbox("Select Site", options=site_options, index=0)
        st.markdown("Add a new site:")
        new_site_input = st.text_input("New Site Name", value="")
        add_site_clicked = st.form_submit_button("Add Site")

    add_txn_clicked = st.form_submit_button("Add Transaction")

if add_site_clicked:
    msg, updated_sites = add_site(new_site_input)
    if updated_sites is not None:
        st.success(msg)
        st.rerun()
    else:
        if msg.startswith("✅"):
            st.success(msg)
        elif msg.startswith("⚠️"):
            st.warning(msg)
        else:
            st.info(msg)

if add_txn_clicked:
    signed_amount = amount_input
    if txn_type == "Payment" and amount_input.strip() != "":
        try:
            signed_amount = str(-abs(float(amount_input)))
        except ValueError:
            signed_amount = amount_input
    msg = add_transaction(date_input, site_selected, desc_input, signed_amount)
    if msg.startswith("✅"):
        st.success(msg)
    elif msg.startswith("⚠️"):
        st.warning(msg)
    else:
        st.error(msg)

st.divider()

with st.expander("View current sheet data"):
    try:
        data = SHEET.get_all_values()
        if data:
            st.write(f"Rows: {len(data)}")
            for i, row in enumerate(data, start=1):
                st.write(f"{i:>3}: {row}")
        else:
            st.info("Sheet is empty.")
    except Exception as e:
        st.error(f"Failed to load sheet: {e}")
