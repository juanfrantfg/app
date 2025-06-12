import streamlit as st
import pandas as pd
import numpy as np
import mysql.connector
import plotly.express as px

# CONFIGURAR AQUÍ TUS DATOS DE CONEXIÓN
DB_CONFIG = {
    "host": "185.14.58.24",
    "user": "tfgusu",
    "password": "t2V#zYufaA1^9crh",
    "database": "apptfg"
}

@st.cache_data(ttl=600)
def load_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    tablas = [
        "equipos", "jugadores", "partidos", "convocatorias",
        "part_accion", "part_titulares", "part_asistencias", "part_minutos",
        "entrenamientos_registro", "asistencias"
    ]
    dfs = {}
    for tabla in tablas:
        try:
            dfs[tabla] = pd.read_sql(f"SELECT * FROM {tabla}", conn)
        except Exception as e:
            st.warning(f"Error cargando {tabla}: {e}")
    conn.close()
    return dfs

def partidos_stats(df_partidos):
    df = df_partidos.copy()
    df["resultado"] = np.where(df["goles_favor"] > df["goles_contra"], "Ganado",
                            np.where(df["goles_favor"] < df["goles_contra"], "Perdido", "Empatado"))
    resumen = df.groupby("resultado").size().reset_index(name="cantidad")
    return df, resumen

def jugador_stats(df_jugadores, df_part_minutos, df_part_accion, df_convocatorias, df_partidos):
    min_por_part = df_part_minutos.groupby(["jugador_id", "partido_id"])["minutos"].sum().reset_index()
    goles = df_part_accion[df_part_accion["accion"] == "gol"].groupby("jugador_id").size().reset_index(name="goles")
    asistencias = df_part_accion[df_part_accion["accion"] == "asistencia"].groupby("jugador_id").size().reset_index(name="asistencias")
    lesiones = df_part_accion[df_part_accion["accion"] == "lesion"].groupby("jugador_id").size().reset_index(name="lesiones")
    amarillas = df_part_accion[df_part_accion["accion"] == "amarilla"].groupby("jugador_id").size().reset_index(name="amarillas")
    goles_encajados = df_part_accion[df_part_accion["accion"] == "gol_encajado"].groupby("jugador_id").size().reset_index(name="goles_encajados")
    convocados = df_convocatorias.groupby("jugador_id").size().reset_index(name="convocatorias")
    valoracion_media = df_convocatorias.groupby("jugador_id")["valoracion"].mean().reset_index(name="valoracion_media")
    min_totales = min_por_part.groupby("jugador_id")["minutos"].sum().reset_index(name="minutos_totales")
    partidos_jugados = min_por_part.groupby("jugador_id")["partido_id"].nunique().reset_index(name="partidos_jugados")
    partido_min = df_partidos["id"].nunique() * 62
    min_totales["porcentaje_min"] = 100 * min_totales["minutos_totales"] / partido_min

    df = df_jugadores.merge(convocados, left_on="id", right_on="jugador_id", how="left") \
        .merge(valoracion_media, on="jugador_id", how="left") \
        .merge(min_totales, on="jugador_id", how="left") \
        .merge(partidos_jugados, on="jugador_id", how="left") \
        .merge(goles, on="jugador_id", how="left") \
        .merge(asistencias, on="jugador_id", how="left") \
        .merge(lesiones, on="jugador_id", how="left") \
        .merge(amarillas, on="jugador_id", how="left") \
        .merge(goles_encajados, on="jugador_id", how="left")
    df = df.fillna(0)
    return df

def equipo_stats(df_partidos):
    df = df_partidos.copy()
    resumen = df.groupby("equipo_id").agg({
        "goles_favor":"sum",
        "goles_contra":"sum",
        "id":"count"
    }).rename(columns={"id":"partidos"}).reset_index()
    return resumen

def asistencias_entreno_stats(df_asistencias, df_entrenamientos, df_convocatorias, df_partidos):
    entreno_partido = []
    for idx, row in df_entrenamientos.iterrows():
        fecha = row["fecha"]
        partido = df_partidos[df_partidos["fecha"] >= fecha].sort_values("fecha").head(1)
        if not partido.empty:
            entreno_partido.append((row["id"], partido.iloc[0]["id"]))
    df_entreno_partido = pd.DataFrame(entreno_partido, columns=["entrenamiento_id", "partido_id"])
    df = df_asistencias.merge(df_entreno_partido, left_on="entrenamiento_id", right_on="entrenamiento_id", how="left")
    df = df.merge(df_convocatorias, left_on=["partido_id", "jugador_id"], right_on=["partido_id", "jugador_id"], how="left")
    df = df.merge(df_partidos[["id", "goles_favor","goles_contra"]], left_on="partido_id", right_on="id", how="left")
    df["resultado"] = np.where(df["goles_favor"] > df["goles_contra"], "Gana",
                               np.where(df["goles_favor"] < df["goles_contra"], "Pierde", "Empata"))
    return df

def globales_temp(df_jugadores, df_partidos, df_part_minutos, df_asistencias):
    min_totales = df_part_minutos.groupby("jugador_id")["minutos"].sum().reset_index(name="min_jugados")
    asistencias = df_asistencias.groupby("jugador_id")["asiste"].mean().reset_index(name="asistencia_pct")
    rpe = df_asistencias.groupby("jugador_id")["rpe"].mean().reset_index(name="rpe_media")
    actitud = df_asistencias.groupby("jugador_id")["actitud"].mean().reset_index(name="actitud_media")

    df = df_jugadores.copy()
    # Merge cada vez y elimina la columna duplicada 'jugador_id' después de cada merge
    df = df.merge(min_totales, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(asistencias, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(rpe, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(actitud, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.fillna(0)
    return df

def main():
    st.title("Estadísticas de fútbol - Temporada completa (MySQL)")
    dfs = load_data()
    jugadores = dfs["jugadores"]
    partidos = dfs["partidos"]
    part_accion = dfs["part_accion"]
    convocatorias = dfs["convocatorias"]
    part_minutos = dfs["part_minutos"]
    equipos = dfs["equipos"]
    entrenamientos = dfs["entrenamientos_registro"]
    asistencias = dfs["asistencias"]

    st.header("Estadísticas globales por partido")
    partidos_df, partidos_resumen = partidos_stats(partidos)
    st.dataframe(partidos_resumen)
    st.bar_chart(partidos_resumen.set_index("resultado")["cantidad"])

    st.header("Estadísticas por jugador (temporada y por partido)")
    jugadores_df = jugador_stats(jugadores, part_minutos, part_accion, convocatorias, partidos)
    st.dataframe(jugadores_df[["nombre","alias","dorsal","demarcacion","minutos_totales","porcentaje_min",
                               "goles","asistencias","lesiones","amarillas","goles_encajados","valoracion_media","convocatorias"]])

    st.header("Estadísticas por equipo")
    equipos_df = equipo_stats(partidos)
    st.dataframe(equipos_df)

    st.header("Gráficas de jugadores")
    fig1 = px.bar(jugadores_df, x="nombre", y="minutos_totales", title="Minutos jugados por jugador")
    st.plotly_chart(fig1)
    fig2 = px.bar(jugadores_df, x="nombre", y="goles", title="Goles por jugador")
    st.plotly_chart(fig2)
    fig3 = px.bar(jugadores_df, x="nombre", y="asistencias", title="Asistencias por jugador")
    st.plotly_chart(fig3)
    fig4 = px.bar(jugadores_df, x="nombre", y="porcentaje_min", title="Porcentaje minutos jugados por jugador")
    st.plotly_chart(fig4)

    st.header("Porcentaje de minutos jugados por partido y jugador")
    min_por_part = part_minutos.groupby(["jugador_id","partido_id"])["minutos"].sum().reset_index()
    partidos_min = partidos[["id","fecha"]]
    min_por_part = min_por_part.merge(jugadores[["id","nombre"]], left_on="jugador_id", right_on="id", how="left") \
                               .merge(partidos_min, left_on="partido_id", right_on="id", how="left")
    st.dataframe(min_por_part[["nombre","partido_id","fecha","minutos"]])

    st.header("Relación asistencia, RPE y actitud con resultados y valoración")
    entreno_stats = asistencias_entreno_stats(asistencias, entrenamientos, convocatorias, partidos)
    st.dataframe(entreno_stats[["jugador_id","asiste","rpe","actitud","valoracion","resultado"]])
    fig5 = px.box(entreno_stats, x="resultado", y="rpe", points="all", title="RPE según resultado")
    st.plotly_chart(fig5)
    fig6 = px.box(entreno_stats, x="resultado", y="actitud", points="all", title="Actitud según resultado")
    st.plotly_chart(fig6)
    fig7 = px.box(entreno_stats, x="resultado", y="asiste", points="all", title="Asistencia a entrenos según resultado")
    st.plotly_chart(fig7)

    st.header("Globales de temporada")
    globales = globales_temp(jugadores, partidos, part_minutos, asistencias)
    st.dataframe(globales)

    st.header("Otras estadísticas y porcentajes interesantes")
    total_partidos = partidos["id"].nunique()
    total_goles = partidos["goles_favor"].sum()
    total_convocatorias = convocatorias["id"].count()
    st.metric("Total de partidos", total_partidos)
    st.metric("Total de goles a favor", total_goles)
    st.metric("Total de convocatorias", total_convocatorias)
    st.metric("Promedio de valoración", convocatorias["valoracion"].mean())
    st.metric("Promedio de RPE temporada", asistencias["rpe"].mean())
    st.metric("Promedio de actitud temporada", asistencias["actitud"].mean())

    st.markdown("**Puedes filtrar, ordenar y exportar las tablas desde Streamlit.**")

if __name__ == "__main__":
    main()
