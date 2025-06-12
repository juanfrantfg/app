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

def jugador_stats(jugadores, part_minutos, part_accion, convocatorias, partidos):
    # Minutos jugados por jugador y partido
    min_por_part = part_minutos.groupby(["jugador_id", "partido_id"])["minutos"].sum().reset_index()
    # Goles
    goles = part_accion[part_accion["accion"] == "gol"].groupby("jugador_id").size().reset_index(name="goles")
    # Asistencias
    asistencias = part_accion[part_accion["accion"] == "asistencia"].groupby("jugador_id").size().reset_index(name="asistencias")
    # Lesiones
    lesiones = part_accion[part_accion["accion"] == "lesion"].groupby("jugador_id").size().reset_index(name="lesiones")
    # Amarillas
    amarillas = part_accion[part_accion["accion"] == "amarilla"].groupby("jugador_id").size().reset_index(name="amarillas")
    # Goles encajados (por portero)
    goles_encajados = part_accion[part_accion["accion"] == "gol_encajado"].groupby("jugador_id").size().reset_index(name="goles_encajados")
    # Convocatorias y valoración media
    convocados = convocatorias.groupby("jugador_id").size().reset_index(name="convocatorias")
    valoracion_media = convocatorias.groupby("jugador_id")["valoracion"].mean().reset_index(name="valoracion_media")
    min_totales = min_por_part.groupby("jugador_id")["minutos"].sum().reset_index(name="minutos_totales")
    partidos_jugados = min_por_part.groupby("jugador_id")["partido_id"].nunique().reset_index(name="partidos_jugados")
    partido_min = partidos["id"].nunique() * 62
    min_totales["porcentaje_min"] = 100 * min_totales["minutos_totales"] / partido_min

    # Merge todo con info del jugador y solo info relevante al final
    df = jugadores.merge(convocados, left_on="id", right_on="jugador_id", how="left") \
        .merge(valoracion_media, on="jugador_id", how="left") \
        .merge(min_totales, on="jugador_id", how="left") \
        .merge(partidos_jugados, on="jugador_id", how="left") \
        .merge(goles, on="jugador_id", how="left") \
        .merge(asistencias, on="jugador_id", how="left") \
        .merge(lesiones, on="jugador_id", how="left") \
        .merge(amarillas, on="jugador_id", how="left") \
        .merge(goles_encajados, on="jugador_id", how="left")

    df = df.fillna(0)
    # Solo columnas de interés; no mostramos 'jugador_id' ni 'id'
    df = df[["nombre", "alias", "dorsal", "demarcacion",
             "minutos_totales", "porcentaje_min", "goles", "asistencias",
             "lesiones", "amarillas", "goles_encajados", "valoracion_media", "convocatorias"]]
    return df

def asistencias_entreno_stats(asistencias, entrenamientos, convocatorias, partidos, jugadores):
    entreno_partido = []
    for idx, row in entrenamientos.iterrows():
        fecha = row["fecha"]
        partido = partidos[partidos["fecha"] >= fecha].sort_values("fecha").head(1)
        if not partido.empty:
            entreno_partido.append((row["id"], partido.iloc[0]["id"]))
    df_entreno_partido = pd.DataFrame(entreno_partido, columns=["entrenamiento_id", "partido_id"])
    df = asistencias.merge(df_entreno_partido, left_on="entrenamiento_id", right_on="entrenamiento_id", how="left")
    df = df.merge(convocatorias, left_on=["partido_id", "jugador_id"], right_on=["partido_id", "jugador_id"], how="left")
    df = df.merge(partidos[["id", "goles_favor", "goles_contra"]], left_on="partido_id", right_on="id", how="left")
    # Elimina columna "id" para evitar conflicto al mergear con jugadores
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    df = df.merge(jugadores[["id", "nombre", "alias", "dorsal"]], left_on="jugador_id", right_on="id", how="left")
    df["resultado"] = np.where(df["goles_favor"] > df["goles_contra"], "Gana",
                               np.where(df["goles_favor"] < df["goles_contra"], "Pierde", "Empata"))
    # Solo mostramos info relevante y no jugador_id ni id
    df = df[["nombre", "alias", "dorsal", "asiste", "rpe", "actitud", "valoracion", "resultado"]]
    return df

def globales_temp(jugadores, partidos, part_minutos, asistencias):
    min_totales = part_minutos.groupby("jugador_id")["minutos"].sum().reset_index(name="min_jugados")
    asistencias_ = asistencias.groupby("jugador_id")["asiste"].mean().reset_index(name="asistencia_pct")
    rpe = asistencias.groupby("jugador_id")["rpe"].mean().reset_index(name="rpe_media")
    actitud = asistencias.groupby("jugador_id")["actitud"].mean().reset_index(name="actitud_media")

    df = jugadores.copy()
    df = df.merge(min_totales, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(asistencias_, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(rpe, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.merge(actitud, left_on="id", right_on="jugador_id", how="left")
    df = df.drop(columns=["jugador_id"])
    df = df.fillna(0)
    # Solo mostramos nombre, alias, dorsal y métricas
    df = df[["nombre", "alias", "dorsal", "min_jugados", "asistencia_pct", "rpe_media", "actitud_media"]]
    return df

def main():
    st.title("Estadísticas del equipo - Temporada completa")
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
    st.dataframe(jugadores_df)

    st.header("Estadísticas por equipo")
    equipos_df = partidos.groupby("equipo_id").agg({
        "goles_favor":"sum",
        "goles_contra":"sum",
        "id":"count"
    }).rename(columns={"id":"partidos"}).reset_index()
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
    min_por_part = min_por_part.merge(jugadores[["id","nombre","alias","dorsal"]], left_on="jugador_id", right_on="id", how="left")
    min_por_part = min_por_part.merge(partidos[["id","fecha"]], left_on="partido_id", right_on="id", how="left")
    st.dataframe(min_por_part[["nombre","alias","dorsal","partido_id","fecha","minutos"]])

    st.header("Relación asistencia, RPE y actitud con resultados y valoración")
    entreno_stats = asistencias_entreno_stats(asistencias, entrenamientos, convocatorias, partidos, jugadores)
    st.dataframe(entreno_stats)
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

    st.markdown("**Todas las tablas y gráficos muestran nombre, alias y dorsal en vez de id de jugador.**")

if __name__ == "__main__":
    main()
