from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
import os

app = Flask(__name__)

CSV_PATH = "/app/data/kia.csv"
PLOTS_DIR = "/app/data/plots"
PLOT_KM = os.path.join(PLOTS_DIR, "km_acumulados.png")
PLOT_GASTO = os.path.join(PLOTS_DIR, "gasto_mensual.png")

COLS = ["Fecha", "Km_totales", "Consumo_repostaje", "Consumo_total", "Precio_L", "Precio"]


def asegurar_estructura():
    os.makedirs("/app/data", exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)


def cargar_datos():
    asegurar_estructura()
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
    asegurar_estructura()
    out = df.copy()
    out["Fecha"] = pd.to_datetime(out["Fecha"], errors="coerce").dt.strftime("%d/%m/%Y")
    out.to_csv(CSV_PATH, index=False)


def generar_plots(df):
    asegurar_estructura()

    # Plot KM acumulados
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
    plt.tight_layout()
    plt.savefig(PLOT_KM, dpi=120)
    plt.close()

    # Plot gasto mensual
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
    plt.tight_layout()
    plt.savefig(PLOT_GASTO, dpi=120)
    plt.close()


def asegurar_plots_iniciales():
    # Si no existen plots (primer arranque), los crea una vez
    if not os.path.exists(PLOT_KM) or not os.path.exists(PLOT_GASTO):
        df = cargar_datos()
        generar_plots(df)


@app.route("/")
def index():
    asegurar_plots_iniciales()
    ts = int(datetime.now().timestamp())  # cache-buster visual
    return render_template(
        "index.html",
        km_plot_url=url_for("static_plot", filename="km_acumulados.png", v=ts),
        gasto_plot_url=url_for("static_plot", filename="gasto_mensual.png", v=ts),
    )


@app.route("/plots/<path:filename>")
def static_plot(filename):
    # Sirve archivos de /app/data/plots
    from flask import send_from_directory
    return send_from_directory(PLOTS_DIR, filename)


@app.route("/datos")
def datos():
    df = cargar_datos().copy()
    if not df.empty:
        df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")
    tabla_html = df.to_html(index=False, classes="tabla-datos", border=0, justify="center")
    return render_template("datos.html", tabla_html=tabla_html)


@app.route("/replotear", methods=["POST"])
def replotear():
    df = cargar_datos()
    generar_plots(df)
    return redirect(url_for("datos"))


@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        fecha = request.form.get("fecha", "").strip()
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

        if pd.isna(nueva["Fecha"]):
            return render_template("nuevo.html", error="La fecha es obligatoria y debe ser válida.")

        df = cargar_datos()
        df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True).sort_values("Fecha")
        guardar_csv(df)

        # IMPORTANTE: replot automático al añadir dato
        generar_plots(df)

        return redirect(url_for("datos"))

    return render_template("nuevo.html", error=None)


if __name__ == "__main__":
    asegurar_estructura()
    app.run(host="0.0.0.0", port=8080, debug=False)
