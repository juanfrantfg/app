import streamlit as st
import pandas as pd
import numpy as np
import mysql.connector
import plotly.express as px

# CONEXIÓN BD
def get_connection():
    return mysql.connector.connect(
        host="185.14.58.24",
        user="tfgusu",
        password="t2V#zYufaA1^9crh",
        database="apptfg"
    )
try:
    conn = mysql.connector.connect(**DB_CONFIG)
    st.success("¡Conexión a MySQL OK!")
except Exception as e:
    st.error(f"Error conectando a MySQL: {e}")
