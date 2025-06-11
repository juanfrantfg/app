import streamlit as st
import pandas as pd
import mysql.connector

st.set_page_config(page_title="Informes Fútbol Base", layout="wide")

# CONEXIÓN BD
def get_connection():
    return mysql.connector.connect(
        host="185.14.58.24",
        user="tfgusu",
        password="t2V#zYufaA1^9crh",
        database="apptfg"
    )

@st.cache_data
def load_jugadores():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM jugadores", conn)
    conn.close()
    return df

@st.cache_data
def load_partidos():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM partidos WHERE en_juego=9", conn)
    conn.close()
    return df

@st.cache_data
def load_minutos():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM part_minutos", conn)
    conn.close()
    return df

@st.cache_data
def load_acciones():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM part_accion", conn)
    conn.close()
    return df

@st.cache_data
def load_asistencias():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM part_asistencias", conn)
    conn.close()
    return df

@st.cache_data
def load_convocatorias():
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM convocatorias", conn)
    conn.close()
    return df

jugadores = load_jugadores()
partidos = load_partidos()
minutos = load_minutos()
acciones = load_acciones()
asistencias = load_asistencias()
convocatorias = load_convocatorias()

# Utilidad: partidos convocados por jugador
partidos_convocados_jugador = convocatorias.groupby("jugador_id")["partido_id"].apply(set).to_dict()

def filtrar_minutos(jugador_id):
    if jugador_id in partidos_convocados_jugador:
        ids_partidos = partidos_convocados_jugador[jugador_id]
        return minutos[(minutos["jugador_id"] == jugador_id) & (minutos["partido_id"].isin(ids_partidos))]
    else:
        return pd.DataFrame(columns=minutos.columns)

def filtrar_acciones(jugador_id, accion_tipo=None):
    if jugador_id in partidos_convocados_jugador:
        ids_partidos = partidos_convocados_jugador[jugador_id]
        df = acciones[(acciones["jugador_id"] == jugador_id) & (acciones["partido_id"].isin(ids_partidos))]
        if accion_tipo is not None:
            df = df[df["accion"] == accion_tipo]
        return df
    else:
        return pd.DataFrame(columns=acciones.columns)

def filtrar_asistencias(jugador_id):
    if jugador_id in partidos_convocados_jugador:
        ids_partidos = partidos_convocados_jugador[jugador_id]
        return asistencias[(asistencias["asistente_id"] == jugador_id) & (asistencias["partido_id"].isin(ids_partidos))]
    else:
        return pd.DataFrame(columns=asistencias.columns)

st.title("Informes y Estadísticas de Fútbol Base")

vista = st.sidebar.radio("¿Qué deseas ver?", [
    "Tablas comparativas del equipo",
    "Informe individual por jugador",
    "Gráficas"
])

if vista == "Tablas comparativas del equipo":
    st.header("Estadísticas globales (solo jugadores convocados)")

    jugadores_convocados = convocatorias["jugador_id"].unique()
    df_jug = jugadores[jugadores["id"].isin(jugadores_convocados)].copy()

    # Solo partidos en los que el jugador ha sido convocado
    minutos_totales = []
    partidos_jugados = []
    for _, row in df_jug.iterrows():
        mins = filtrar_minutos(row["id"])
        minutos_totales.append(mins["minutos"].sum())
        partidos_jugados.append(len(mins["partido_id"].unique()))
    df_jug["minutos"] = minutos_totales
    df_jug["partidos_jugados"] = partidos_jugados

    # Goles, asistencias, amonestaciones, lesiones solo de partidos convocados
    df_jug["goles"] = df_jug["id"].apply(lambda x: filtrar_acciones(x, "gol").shape[0])
    df_jug["asistencias"] = df_jug["id"].apply(lambda x: filtrar_asistencias(x).shape[0])
    df_jug["amarillas"] = df_jug["id"].apply(lambda x: filtrar_acciones(x, "amarilla").shape[0])
    df_jug["lesiones"] = df_jug["id"].apply(lambda x: filtrar_acciones(x, "lesion").shape[0])
    df_jug["media_valoracion"] = df_jug["id"].apply(lambda x: convocatorias[convocatorias["jugador_id"] == x]["valoracion"].mean())

    tabla_completa = df_jug[["nombre", "dorsal", "demarcacion", "minutos", "partidos_jugados", "goles", "asistencias", "amarillas", "lesiones", "media_valoracion"]].copy()
    tabla_completa = tabla_completa.sort_values("minutos", ascending=False)
    st.subheader("Estadísticas globales de jugadores convocados")
    st.dataframe(tabla_completa, hide_index=True)

    # Porcentajes y estadísticas
    st.header("Estadísticas destacadas del equipo (convocados)")
    total_min = tabla_completa["minutos"].sum()
    total_gol = tabla_completa["goles"].sum()
    total_asi = tabla_completa["asistencias"].sum()
    total_ama = tabla_completa["amarillas"].sum()
    total_les = tabla_completa["lesiones"].sum()
    media_val = tabla_completa["media_valoracion"].mean()

    st.metric("Minutos totales jugados", int(total_min))
    st.metric("Goles totales", int(total_gol))
    st.metric("Asistencias totales", int(total_asi))
    st.metric("Amonestaciones totales", int(total_ama))
    st.metric("Lesiones totales", int(total_les))
    st.metric("Valoración media (convocados)", round(media_val,2))

    # Porcentaje de minutos, goles y asistencias por jugador
    st.subheader("Porcentaje de minutos jugados por jugador")
    tabla_completa["% minutos"] = tabla_completa["minutos"] / total_min * 100 if total_min > 0 else 0
    st.dataframe(tabla_completa[["nombre", "minutos", "% minutos"]].sort_values("% minutos", ascending=False), hide_index=True)

    st.subheader("Porcentaje de goles por jugador")
    if total_gol > 0:
        tabla_completa["% goles"] = tabla_completa["goles"] / total_gol * 100
        st.dataframe(tabla_completa[["nombre", "goles", "% goles"]].sort_values("% goles", ascending=False), hide_index=True)

elif vista == "Informe individual por jugador":
    jugadores_convocados = convocatorias["jugador_id"].unique()
    jugador_sel = st.sidebar.selectbox("Selecciona un jugador", jugadores[jugadores["id"].isin(jugadores_convocados)]["nombre"])
    jugador_id = jugadores[jugadores["nombre"] == jugador_sel]["id"].values[0]
    st.header(f"Informe individual de {jugador_sel}")

    # Solo partidos convocado
    partidos_convocados = partidos_convocados_jugador.get(jugador_id, set())
    min_jug = minutos[(minutos["jugador_id"] == jugador_id) & (minutos["partido_id"].isin(partidos_convocados))]
    min_por_part = min_jug.groupby("partido_id")["minutos"].sum().reset_index()
    min_por_part = min_por_part.merge(partidos[["id", "fecha"]], left_on="partido_id", right_on="id", how="left")
    st.subheader("Minutos jugados por partido (solo partidos convocado)")
    st.dataframe(min_por_part[["fecha", "minutos"]], hide_index=True)

    # Acciones por partido
    goles_jug = filtrar_acciones(jugador_id, "gol")
    asist_jug = filtrar_asistencias(jugador_id)
    amos_jug = filtrar_acciones(jugador_id, "amarilla")
    les_jug = filtrar_acciones(jugador_id, "lesion")
    val_jug = convocatorias[convocatorias["jugador_id"] == jugador_id]["valoracion"].mean()

    tabla_ind = min_por_part[["fecha", "minutos"]].copy()
    tabla_ind["goles"] = tabla_ind["fecha"].apply(
        lambda f: goles_jug[goles_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
    )
    tabla_ind["asistencias"] = tabla_ind["fecha"].apply(
        lambda f: asist_jug[asist_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
    )
    tabla_ind["amarillas"] = tabla_ind["fecha"].apply(
        lambda f: amos_jug[amos_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
    )
    tabla_ind["lesiones"] = tabla_ind["fecha"].apply(
        lambda f: les_jug[les_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
    )
    st.subheader("Tabla comparativa individual por partido (solo convocado)")
    st.dataframe(tabla_ind, hide_index=True)

    # Resumen global
    total_min = min_jug["minutos"].sum()
    total_gol = goles_jug.shape[0]
    total_asi = asist_jug.shape[0]
    total_ama = amos_jug.shape[0]
    total_les = les_jug.shape[0]

    st.markdown("### Resumen global")
    st.table(pd.DataFrame({
        "Estadística": ["Minutos jugados", "Goles", "Asistencias", "Amonestaciones", "Lesiones", "Valoración media"],
        "Total": [total_min, total_gol, total_asi, total_ama, total_les, round(val_jug,2) if not pd.isna(val_jug) else "-"]
    }))

    # Porcentajes individuales
    if total_min > 0:
        st.metric("Goles por minuto jugado (%)", round(100*total_gol/total_min,2) if total_gol > 0 else 0)
        st.metric("Asistencias por minuto jugado (%)", round(100*total_asi/total_min,2) if total_asi > 0 else 0)

elif vista == "Gráficas":
    import matplotlib.pyplot as plt
    import seaborn as sns

    jugadores_convocados = convocatorias["jugador_id"].unique()
    df_jug = jugadores[jugadores["id"].isin(jugadores_convocados)].copy()

    st.header("Gráficas de estadísticas (solo convocados)")
    graf = st.selectbox("Selecciona gráfica", [
        "Minutos jugados por jugador (temporada convocados)",
        "Goles y asistencias por jugador (temporada convocados)",
        "Minutos jugados por partido (solo convocados)",
        "Goles y asistencias por partido (jugador individual convocado)"
    ])

    if graf == "Minutos jugados por jugador (temporada convocados)":
        data = []
        for _, row in df_jug.iterrows():
            mins = filtrar_minutos(row["id"])
            data.append({"jugador": row["nombre"], "minutos": mins["minutos"].sum()})
        tabla = pd.DataFrame(data).sort_values("minutos", ascending=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(x="minutos", y="jugador", data=tabla, palette="Blues_r", ax=ax)
        ax.set_xlabel("Minutos totales jugados")
        ax.set_ylabel("Jugador")
        st.pyplot(fig)

    elif graf == "Goles y asistencias por jugador (temporada convocados)":
        data = []
        for _, row in df_jug.iterrows():
            goles = filtrar_acciones(row["id"], "gol").shape[0]
            asist = filtrar_asistencias(row["id"]).shape[0]
            data.append({"jugador": row["nombre"], "goles": goles, "asistencias": asist})
        df = pd.DataFrame(data).set_index("jugador")
        fig, ax = plt.subplots(figsize=(10, 5))
        df.plot(kind="bar", ax=ax)
        plt.xticks(rotation=45)
        ax.set_ylabel("Total")
        st.pyplot(fig)

    elif graf == "Minutos jugados por partido (solo convocados)":
        # Suma minutos por partido y jugador solo si convocado en ese partido
        lista = []
        for _, row in df_jug.iterrows():
            mins = filtrar_minutos(row["id"])
            for _, m in mins.iterrows():
                fecha = partidos[partidos["id"] == m["partido_id"]]["fecha"]
                if not fecha.empty:
                    lista.append({"fecha": fecha.iloc[0], "jugador": row["nombre"], "minutos": m["minutos"]})
        tabla = pd.DataFrame(lista)
        if not tabla.empty:
            tabla_pivot = tabla.pivot_table(index="fecha", columns="jugador", values="minutos", fill_value=0)
            st.dataframe(tabla_pivot, hide_index=True)
            fig, ax = plt.subplots(figsize=(12, 6))
            tabla_pivot.plot(ax=ax)
            plt.xticks(rotation=45)
            ax.set_ylabel("Minutos")
            ax.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
            st.pyplot(fig)
        else:
            st.info("No hay datos para mostrar.")

    elif graf == "Goles y asistencias por partido (jugador individual convocado)":
        jugador_sel = st.selectbox("Selecciona jugador", df_jug["nombre"])
        jugador_id = df_jug[df_jug["nombre"] == jugador_sel]["id"].values[0]
        partidos_convocados = partidos_convocados_jugador.get(jugador_id, set())
        goles_jug = filtrar_acciones(jugador_id, "gol")
        asist_jug = filtrar_asistencias(jugador_id)
        fechas = partidos[partidos["id"].isin(partidos_convocados)]["fecha"].astype(str).tolist()
        df = pd.DataFrame({"fecha": fechas})
        df["goles"] = df["fecha"].apply(
            lambda f: goles_jug[goles_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
        )
        df["asistencias"] = df["fecha"].apply(
            lambda f: asist_jug[asist_jug["partido_id"] == partidos[partidos["fecha"] == f]["id"].iloc[0]].shape[0] if not partidos[partidos["fecha"] == f].empty else 0
        )
        fig, ax = plt.subplots()
        ax.plot(df["fecha"], df["goles"], marker="o", label="Goles")
        ax.plot(df["fecha"], df["asistencias"], marker="s", label="Asistencias")
        plt.xticks(rotation=45)
        ax.set_ylabel("Total")
        ax.legend()
        st.pyplot(fig)

st.sidebar.markdown("---")
st.sidebar.info("App desarrollada por Coditeca para TFG - Fútbol Base")
