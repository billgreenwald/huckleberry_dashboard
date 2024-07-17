import streamlit as st
from breast_milk_page import breast_milk_page

st.set_page_config("Juicer Dashboard", layout="wide")

pages = {
    "Breast Milk": breast_milk_page,
}

st.sidebar.title("Navigation")
selection = st.sidebar.radio("Go to", list(pages.keys()))

pages[selection]()