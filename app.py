from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
import os

app = Flask(__name__)

CSV_PATH = "/app/data/kia.csv"
COLS = ["Fecha", "Km_totales", "Consumo_repostaje", "Consumo_total", "Precio_L", "Precio"]


def cargar_datos():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame(columns=COLS)

    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]

    for c in COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLS]

    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    for col in ["Km_totales", "Consumo_repostaje", "Consumo_total", "Precio_L", "Precio"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Fecha"]).sort_values("Fecha")
    return df


def guardar_csv(df):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    out = df.copy()
    out["Fecha"] = pd.to_datetime(out["Fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
    out.to_csv(CSV_PATH, index=False)


def fig_to_base64():
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    plt.close()
    return img_b64


def generar_grafico_km(df):
    plt.figure(figsize=(10, 5))
    tmp = df.dropna(subset=["Km_totales"])
    if not tmp.empty:
        plt.plot(tmp["Fecha"], tmp["Km_totales"], marker="o", linestyle="-", color="blue")
    else:
        plt.text(0.5, 0.5, "Sin datos de Km_totales", ha="center", va="center", transform=plt.gca().transAxes)

    plt.title(f'Kia km acumulados. Updated: {datetime.now().strftime("%d/%m/%y %H:%M")}', fontsize=13)
    plt.xlabel("Fecha")
    plt.ylabel("Kilómetros acumulados")
    plt.grid(True, alpha=0.3)
    return fig_to_base64()


def generar_grafico_gasto_mensual(df):
    plt.figure(figsize=(12, 5))
    tmp = df.dropna(subset=["Precio"]).copy()
    if not tmp.empty:
        tmp["mes"] = tmp["Fecha"].dt.to_period("M").dt.to_timestamp()
        mensual = tmp.groupby("mes", as_index=False)["Precio"].sum()
        if not mensual.empty:
            plt.bar(mensual["mes"].dt.strftime("%Y-%m"), mensual["Precio"], color="steelblue")
            plt.xticks(rotation=45)
        else:
            plt.text(0.5, 0.5, "Sin datos mensuales", ha="center", va="center", transform=plt.gca().transAxes)
    else:
        plt.text(0.5, 0.5, "Sin datos de Precio", ha="center", va="center", transform=plt.gca().transAxes)

    plt.title(f'Gasto mensual en gasolina. Updated: {datetime.now().strftime("%d/%m/%y %H:%M")}', fontsize=13)
    plt.xlabel("Mes")
    plt.ylabel("Gasto (€)")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    return fig_to_base64()


@app.route("/")
def index():
    df = cargar_datos()
    return render_template(
        "index.html",
        grafico_km=generar_grafico_km(df),
        grafico_gasto=generar_grafico_gasto_mensual(df)
    )


@app.route("/datos")
def datos():
    df = cargar_datos().copy()
    if not df.empty:
        df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")
    tabla_html = df.to_html(index=False, classes="tabla-datos", border=0, justify="center")
    return render_template("datos.html", tabla_html=tabla_html)


@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        fecha = request.form.get("fecha", "").strip()  # yyyy-mm-dd
        km_totales = request.form.get("km_totales", "").strip()
        consumo_repostaje = request.form.get("consumo_repostaje", "").strip()
        consumo_total = request.form.get("consumo_total", "").strip()
        precio_l = request.form.get("precio_l", "").strip()
        precio = request.form.get("precio", "").strip()

        nueva = {
            "Fecha": pd.to_datetime(fecha, errors="coerce"),
            "Km_totales": pd.to_numeric(km_totales, errors="coerce"),
            "Consumo_repostaje": pd.to_numeric(consumo_repostaje, errors="coerce"),
            "Consumo_total": pd.to_numeric(consumo_total, errors="coerce"),
            "Precio_L": pd.to_numeric(precio_l, errors="coerce"),
            "Precio": pd.to_numeric(precio, errors="coerce"),
        }

        # Validación mínima
        if pd.isna(nueva["Fecha"]):
            return render_template("nuevo.html", error="La fecha es obligatoria y debe ser válida.")

        df = cargar_datos()
        df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
        df = df.sort_values("Fecha")
        guardar_csv(df)

        # Al volver a index/datos se recalculan plots y tabla automáticamente
        return redirect(url_for("datos"))

    return render_template("nuevo.html", error=None)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
