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
    min_por_part = part_minutos.groupby(["jugador_id", "partido_id"])["minutos"].sum().reset_index()
    goles = part_accion[part_accion["accion"] == "gol"].groupby("jugador_id").size().reset_index(name="goles")
    asistencias = part_accion[part_accion["accion"] == "asistencia"].groupby("jugador_id").size().reset_index(name="asistencias")
    lesiones = part_accion[part_accion["accion"] == "lesion"].groupby("jugador_id").size().reset_index(name="lesiones")
    amarillas = part_accion[part_accion["accion"] == "amarilla"].groupby("jugador_id").size().reset_index(name="amarillas")
    goles_encajados = part_accion[part_accion["accion"] == "gol_encajado"].groupby("jugador_id").size().reset_index(name="goles_encajados")
    convocados = convocatorias.groupby("jugador_id").size().reset_index(name="convocatorias")
    valoracion_media = convocatorias.groupby("jugador_id")["valoracion"].mean().reset_index(name="valoracion_media")
    min_totales = min_por_part.groupby("jugador_id")["minutos"].sum().reset_index(name="minutos_totales")
    partidos_jugados = min_por_part.groupby("jugador_id")["partido_id"].nunique().reset_index(name="partidos_jugados")
    partido_min = partidos["id"].nunique() * 62
    min_totales["porcentaje_min"] = 100 * min_totales["minutos_totales"] / partido_min

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
    # Redondear todos los números a dos decimales
    for col in ["minutos_totales", "goles", "asistencias", "lesiones", "amarillas", "goles_encajados", "valoracion_media", "convocatorias", "partidos_jugados"]:
        df[col] = df[col].astype(float).map(lambda x: f"{x:.2f}")
    # Formatear porcentaje_min con dos decimales y símbolo %
    df["porcentaje_min"] = df["porcentaje_min"].map(lambda x: f"{x:.2f} %")
    df = df[["nombre", "alias", "dorsal", "demarcacion",
             "minutos_totales", "porcentaje_min", "goles", "asistencias",
             "lesiones", "amarillas", "goles_encajados", "valoracion_media", "convocatorias", "partidos_jugados"]]
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
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    df = df.merge(jugadores[["id", "nombre", "alias", "dorsal"]], left_on="jugador_id", right_on="id", how="left")
    df["resultado"] = np.where(df["goles_favor"] > df["goles_contra"], "Gana",
                               np.where(df["goles_favor"] < df["goles_contra"], "Pierde", "Empata"))
    df = df[["nombre", "alias", "dorsal", "asiste", "rpe", "actitud", "valoracion", "resultado"]]
    # Si asiste es porcentaje (0/1), lo transformamos a %
    if df["asiste"].max() <= 1:
        df["asiste"] = (df["asiste"] * 100).map(lambda x: f"{x:.2f} %")
    else:
        df["asiste"] = df["asiste"].map(lambda x: f"{x:.2f} %")
    # Redondear rpe, actitud, valoracion a dos decimales
    for col in ["rpe", "actitud", "valoracion"]:
        df[col] = df[col].astype(float).map(lambda x: f"{x:.2f}")
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
    # Formatear asistencia_pct con dos decimales y símbolo %
    if df["asistencia_pct"].max() <= 1:
        df["asistencia_pct"] = (df["asistencia_pct"] * 100).map(lambda x: f"{x:.2f} %")
    else:
        df["asistencia_pct"] = df["asistencia_pct"].map(lambda x: f"{x:.2f} %")
    # Redondear min_jugados, rpe_media, actitud_media a dos decimales
    for col in ["min_jugados", "rpe_media", "actitud_media"]:
        df[col] = df[col].astype(float).map(lambda x: f"{x:.2f}")
    df = df[["nombre", "alias", "dorsal", "min_jugados", "asistencia_pct", "rpe_media", "actitud_media"]]
    return df

def equipo_stats(partidos, equipos):
    equipos_df = partidos.groupby("equipo_id").agg({
        "goles_favor":"sum",
        "goles_contra":"sum",
        "id":"count"
    }).rename(columns={"id":"partidos"}).reset_index()
    equipos_df = equipos_df.merge(equipos, left_on="equipo_id", right_on="id", how="left")
    equipos_df = equipos_df[["nombre", "partidos", "goles_favor", "goles_contra"]]
    # Redondear todos los números a dos decimales
    for col in ["partidos", "goles_favor", "goles_contra"]:
        equipos_df[col] = equipos_df[col].astype(float).map(lambda x: f"{x:.2f}")
    return equipos_df

def partidos_por_fecha(partidos):
    df = partidos.copy()
    df["goles_favor"] = df["goles_favor"].astype(float).map(lambda x: f"{x:.2f}")
    df["goles_contra"] = df["goles_contra"].astype(float).map(lambda x: f"{x:.2f}")
    df = df[["fecha", "goles_favor", "goles_contra"]]
    return df

def main():
    st.title("Estadísticas de fútbol - Temporada completa")
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
    # Redondear cantidad a dos decimales aunque sean enteros
    partidos_resumen["cantidad"] = partidos_resumen["cantidad"].astype(float).map(lambda x: f"{x:.2f}")
    st.dataframe(partidos_resumen)
    fig1 = px.bar(partidos_resumen, x="resultado", y="cantidad", title="Cantidad de partidos por resultado")
    st.plotly_chart(fig1)

    st.header("Estadísticas por jugador (temporada y por partido)")
    jugadores_df = jugador_stats(jugadores, part_minutos, part_accion, convocatorias, partidos)
    st.dataframe(jugadores_df)

    # Mostrar partidos jugados por jugador
    st.subheader("Partidos jugados por jugador")
    fig_pj = px.bar(jugadores_df, x="nombre", y="partidos_jugados", title="Partidos jugados por jugador", labels={"partidos_jugados": "Partidos jugados"})
    st.plotly_chart(fig_pj)

    st.header("Estadísticas por equipo")
    equipos_df = equipo_stats(partidos, equipos)
    st.dataframe(equipos_df)
    fig2 = px.bar(equipos_df, x="nombre", y="goles_favor", title="Goles a favor por equipo")
    st.plotly_chart(fig2)
    fig3 = px.bar(equipos_df, x="nombre", y="goles_contra", title="Goles en contra por equipo")
    st.plotly_chart(fig3)

    st.header("Gráficas de jugadores")
    # Convertir columnas a float para poder graficar
    jugadores_df_plot = jugadores_df.copy()
    jugadores_df_plot["minutos_totales"] = jugadores_df_plot["minutos_totales"].astype(float)
    jugadores_df_plot["goles"] = jugadores_df_plot["goles"].astype(float)
    jugadores_df_plot["asistencias"] = jugadores_df_plot["asistencias"].astype(float)
    jugadores_df_plot["porcentaje_min"] = jugadores_df_plot["porcentaje_min"].str.replace(" %","").astype(float)
    fig4 = px.bar(jugadores_df_plot, x="nombre", y="minutos_totales", title="Minutos jugados por jugador")
    st.plotly_chart(fig4)
    fig5 = px.bar(jugadores_df_plot, x="nombre", y="goles", title="Goles por jugador")
    st.plotly_chart(fig5)
    fig6 = px.bar(jugadores_df_plot, x="nombre", y="asistencias", title="Asistencias por jugador")
    st.plotly_chart(fig6)
    fig7 = px.bar(jugadores_df_plot, x="nombre", y="porcentaje_min", title="Porcentaje minutos jugados por jugador",
                  labels={"porcentaje_min": "Porcentaje minutos jugados (%)"})
    st.plotly_chart(fig7)

    st.header("Porcentaje de minutos jugados por partido y jugador")
    min_por_part = part_minutos.groupby(["jugador_id","partido_id"])["minutos"].sum().reset_index()
    min_por_part = min_por_part.merge(jugadores[["id","nombre","alias","dorsal"]], left_on="jugador_id", right_on="id", how="left")
    min_por_part = min_por_part.merge(partidos[["id","fecha"]], left_on="partido_id", right_on="id", how="left")
    min_por_part["minutos"] = min_por_part["minutos"].astype(float).map(lambda x: f"{x:.2f}")
    st.dataframe(min_por_part[["nombre","alias","dorsal","partido_id","fecha","minutos"]])

    # Tabla adicional: partidos por fecha
    st.subheader("Resultados por partido (fecha)")
    partidos_fecha = partidos_por_fecha(partidos)
    st.dataframe(partidos_fecha)

    st.header("Relación asistencia, RPE y actitud con resultados y valoración")
    entreno_stats = asistencias_entreno_stats(asistencias, entrenamientos, convocatorias, partidos, jugadores)
    st.dataframe(entreno_stats)
    entreno_stats_plot = entreno_stats.copy()
    if entreno_stats_plot["asiste"].dtype == object:
        entreno_stats_plot["asiste"] = entreno_stats_plot["asiste"].str.replace(" %","").astype(float)
    entreno_stats_plot["rpe"] = entreno_stats_plot["rpe"].astype(float)
    entreno_stats_plot["actitud"] = entreno_stats_plot["actitud"].astype(float)
    # Solo gráficas de barras (no boxplot)
    fig8 = px.bar(entreno_stats_plot.groupby("resultado")["asiste"].mean().reset_index(), x="resultado", y="asiste", title="Asistencia media a entrenos según resultado", labels={"asiste": "Asistencia media (%)"})
    st.plotly_chart(fig8)
    fig9 = px.bar(entreno_stats_plot.groupby("resultado")["rpe"].mean().reset_index(), x="resultado", y="rpe", title="RPE medio según resultado")
    st.plotly_chart(fig9)
    fig10 = px.bar(entreno_stats_plot.groupby("resultado")["actitud"].mean().reset_index(), x="resultado", y="actitud", title="Actitud media según resultado")
    st.plotly_chart(fig10)

    st.header("Globales de temporada")
    globales = globales_temp(jugadores, partidos, part_minutos, asistencias)
    st.dataframe(globales)

    st.header("Otras estadísticas y porcentajes interesantes")
    total_partidos = partidos["id"].nunique()
    total_goles = partidos["goles_favor"].sum()
    total_convocatorias = convocatorias["id"].count()
    st.metric("Total de partidos", f"{total_partidos:.2f}")
    st.metric("Total de goles a favor", f"{total_goles:.2f}")
    st.metric("Total de convocatorias", f"{total_convocatorias:.2f}")
    st.metric("Promedio de valoración", f"{convocatorias['valoracion'].mean():.2f}")
    st.metric("Promedio de RPE temporada", f"{asistencias['rpe'].mean():.2f}")
    st.metric("Promedio de actitud temporada", f"{asistencias['actitud'].mean():.2f}")

if __name__ == "__main__":
    main()
