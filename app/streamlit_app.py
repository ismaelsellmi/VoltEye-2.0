"""Tableau de bord VoltEye : streamlit run app/streamlit_app.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit import runtime

if not runtime.exists():
    sys.exit("Ce fichier est une application Streamlit. Depuis le dossier volteye, avec l'environnement .venv activé :\n"
             "    streamlit run app/streamlit_app.py")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from volteye import config as C  # noqa: E402
from volteye.gaf import gasf, rgb_image, to_display  # noqa: E402
from volteye.optimization import TASKS, schedule_profile  # noqa: E402
from volteye.recognition import Recognizer, event_waveform  # noqa: E402
from volteye.signals import CLASSES, MACHINE_TYPES, feature_sequences, harmonic_spectrum, measurements, sample_instance, time_axis  # noqa: E402

st.set_page_config(page_title="VoltEye", page_icon="⚡", layout="wide")
A = C.ARTIFACTS
COLORS = {m: MACHINE_TYPES[m].color for m in CLASSES}
LABELS = {m: MACHINE_TYPES[m].label for m in CLASSES}

if not (A / "optimization.json").exists():
    st.error("Les modèles ne sont pas encore entraînés. Lancez d'abord : `python -m volteye.pipeline`")
    st.stop()


# --- Chargement des artefacts -----------------------------------------------------

@st.cache_data
def load_json(name):
    return json.loads((A / name).read_text(encoding="utf-8"))


@st.cache_data
def load_parquet(name):
    return pd.read_parquet(A / name)


@st.cache_resource
def recognizer():
    return Recognizer.load(A / "gaf_cnn.pt")


def kpi_row(items):
    for col, (label, value, help_) in zip(st.columns(len(items)), items):
        col.metric(label, value, help=help_)


def fmt(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ")


# --- Barre latérale ----------------------------------------------------------------

st.sidebar.markdown("# ⚡👁️ VoltEye")
st.sidebar.caption("See the invisible energy of smart cities")
PAGES = ["Vue d'ensemble", "Surveillance en direct", "Reconnaissance IA (GAF)", "Anomalies & maintenance",
         "Prévision & optimisation", "Vue ville", "Évaluation des modèles", "Architecture"]
page = st.sidebar.radio("Navigation", PAGES)
st.sidebar.divider()
st.sidebar.caption("Smart City Challenge 2026 · Track 2 : Intelligent Energy\n\n"
                   "Données simulées documentées (docs/donnees.md). Tarifs et facteur d'émission : hypothèses à confirmer avec STEG.")

hist = load_parquet("history.parquet")
anom = load_parquet("anomalies_daily.parquet")
health = load_parquet("health_daily.parquet")
opt = load_json("optimization.json")
am = load_json("anomaly_metrics.json")
rm = load_json("recognition_metrics.json")
sm = load_json("stream_metrics.json")
fm = load_json("forecast_metrics.json")


# =============================================================================
if page == "Vue d'ensemble":
    st.title("VoltEye : l'énergie invisible de l'usine, rendue visible")
    st.markdown("**Un seul point de mesure, aucune modification des machines** : l'IA reconnaît chaque machine "
                "à sa signature électrique, détecte les gaspillages, anticipe les pannes et optimise le planning "
                "selon le tarif horaire.")
    year_kwh = hist["E_total"].sum()
    price = np.array([C.tariff(h, m) for h, m in zip(hist.index.hour, hist.index.month)])
    year_tnd = float((hist["E_total"].to_numpy() * price).sum())
    imp = am["impact_anomalies_detectees"]
    kpi_row([
        ("Consommation annuelle", f"{fmt(year_kwh / 1000)} MWh", "Site de référence, 7 machines"),
        ("Facture énergie estimée", f"{fmt(year_tnd)} TND", "Tarif horaire indicatif"),
        ("Émissions", f"{fmt(year_kwh * C.EMISSION_FACTOR / 1000, 1)} t CO₂", f"{C.EMISSION_FACTOR} kg CO₂/kWh"),
        ("Gaspillage détecté", f"{fmt(imp['kWh_gaspilles_detectes'])} kWh",
         f"{fmt(imp['TND'])} TND · {fmt(imp['kg_CO2'])} kg CO₂"),
        ("Gain planification", f"{opt['resume']['gain_annuel_estime_TND'] / 1000:.1f} k TND/an",
         f"{opt['resume']['gain_moyen_%']:.1f} % de la facture des jours ouvrés"),
    ])
    st.subheader("Ce que voit VoltEye")
    c1, c2 = st.columns([3, 2])
    share = pd.Series({LABELS[m]: hist[f"E_{m}"].sum() for m in CLASSES})
    c1.plotly_chart(px.pie(values=share.values, names=share.index, hole=0.5, color=share.index,
                           color_discrete_map={LABELS[m]: COLORS[m] for m in CLASSES},
                           title="Répartition de la consommation par machine (désagrégée)"), use_container_width=True)
    best = rm["models"]["D - VoltEye : fusion CNN GAF + spectre FFT"]
    anomaly_best = am["models"]["VoltEye - résidus + score robuste (MAD)"]
    fc_best = fm["models"]["VoltEye - gradient boosting"]
    c2.markdown(f"""
| Fonction IA | Résultat (test) |
|---|---|
| Reconnaissance des machines | **{best['accuracy'] * 100:.1f} %** d'exactitude |
| Désagrégation du flux | **{sm['precision_energetique'] * 100:.1f} %** de précision énergétique |
| Prévision J+1 | **MAPE {fc_best['MAPE_%_heures_actives']:.1f} %** |
| Détection d'anomalies | **F1 {anomaly_best['f1']:.2f}** (précision {anomaly_best['precision']:.2f}) |
| Maintenance prédictive | panne anticipée **{am['maintenance']['anticipation_panne_convoyeur_jours']} jours** avant |
| Optimisation tarifaire | **-{opt['resume']['gain_moyen_%']:.1f} %** sur la facture journalière |
""")
    st.subheader("Alertes récentes")
    recent = anom[anom["alerte"]].sort_index().tail(8).reset_index()
    for _, r in recent.iloc[::-1].iterrows():
        st.warning(f"**{r['time'].date()} · {LABELS[r['machine']]}** : {am['recommandations'][r['cause']]} "
                   f"(excès {r['exces_production'] + r['exces_hors_production']:.0f} kWh, {r['cout_exces_TND']:.0f} TND)")


# =============================================================================
elif page == "Surveillance en direct":
    st.title("Surveillance en direct : un capteur, toutes les machines")
    df = load_parquet("stream.parquet")
    events = load_json("stream_events.json")
    if "pos" not in st.session_state:
        st.session_state.pos = 900
    c1, c2, c3 = st.columns([1, 1, 4])
    if c1.button("▶ Lecture" if not st.session_state.get("play") else "⏸ Pause"):
        st.session_state.play = not st.session_state.get("play", False)
    speed = c2.selectbox("Vitesse", [10, 30, 60], index=1, format_func=lambda s: f"x{s}")
    pos = c3.slider("Instant", 60, len(df) - 1, st.session_state.pos, step=10,
                    format="%d s")
    st.session_state.pos = pos
    now = df.iloc[pos]
    win = df.iloc[max(0, pos - 900):pos + 1]
    est_now = {m: now[f"estime_{m}_kW"] for m in CLASSES}
    kpi_row([
        ("Heure", str(now["time"].time()), None),
        ("Puissance totale", f"{now['P_kW']:.1f} kW", "Mesurée au point unique"),
        ("Facteur de puissance", f"{now['PF']:.2f}", None),
        ("THD courant", f"{now['THD'] * 100:.1f} %", "Distorsion harmonique totale"),
        ("Machines en marche", f"{sum(v > 0 for v in est_now.values())} / {len(CLASSES)}", "Estimé par l'IA"),
        ("CO₂ instantané", f"{now['P_kW'] * C.EMISSION_FACTOR:.1f} kg/h", None),
    ])
    fig = go.Figure()
    for m in CLASSES:
        fig.add_trace(go.Scatter(x=win["time"], y=win[f"estime_{m}_kW"], stackgroup="one", name=LABELS[m],
                                 line=dict(width=0, shape="hv"), fillcolor=COLORS[m]))
    fig.add_trace(go.Scatter(x=win["time"], y=win["P_kW"], name="Mesure totale", line=dict(color="black", width=1)))
    fig.update_layout(height=380, title="15 dernières minutes : mesure totale et désagrégation par machine",
                      yaxis_title="kW", legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([2, 3])
    states = pd.DataFrame({
        "Machine": [LABELS[m] for m in CLASSES],
        "État estimé": ["🟢 marche" if est_now[m] > 0 else "⚪ arrêt" for m in CLASSES],
        "Puissance estimée (kW)": [round(est_now[m], 1) for m in CLASSES],
        "Puissance réelle (kW)": [round(now[f"vrai_{m}_kW"], 1) for m in CLASSES],
    })
    c1.markdown("**État des machines**")
    c1.dataframe(states, hide_index=True, use_container_width=True)
    past = [e for e in events if e["t"] <= pos][-8:][::-1]
    c2.markdown("**Journal des événements reconnus**")
    c2.dataframe(pd.DataFrame([{
        "Heure": e["time"][11:], "Événement": e["direction"], "ΔP (kW)": round(e["delta_kW"], 1),
        "Machine reconnue": LABELS[e["prediction"]], "Confiance": f"{e['confiance'] * 100:.0f} %",
        "Vérité": "✅" if e["correct"] else f"❌ {e['verite']}"} for e in past]),
        hide_index=True, use_container_width=True)
    if past:
        waves = np.load(A / "stream_event_waves.npy")
        e = past[0]
        k = events.index(e)
        st.markdown(f"**Dernier événement ({e['time'][11:]}) : signature isolée et image GAF analysée par le CNN**")
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.plotly_chart(go.Figure(go.Scatter(x=time_axis() * 1000, y=waves[k], line=dict(color=COLORS[e["prediction"]])))
                        .update_layout(height=250, xaxis_title="ms", yaxis_title="A", margin=dict(t=10)),
                        use_container_width=True)
        c2.image(to_display(rgb_image(waves[k])), caption="Image GAF (RVB)", use_container_width=True)
        pr = pd.Series(e["proba"]).rename(index=LABELS).sort_values()
        c3.plotly_chart(px.bar(pr, orientation="h", range_x=[0, 1]).update_layout(
            height=250, showlegend=False, xaxis_title="probabilité", yaxis_title="", margin=dict(t=10)),
            use_container_width=True)
    st.caption(f"Sur les 4 h simulées : {sm['evenements_detectes']} événements détectés pour {sm['evenements_reels']} réels "
               f"(F1 {sm['detection_f1']:.2f}), {sm['classification_exactitude'] * 100:.1f} % correctement reconnus, "
               f"précision énergétique {sm['precision_energetique'] * 100:.1f} %.")
    if st.session_state.get("play"):
        time.sleep(1.0)
        st.session_state.pos = min(pos + speed, len(df) - 1)
        st.rerun()


# =============================================================================
elif page == "Reconnaissance IA (GAF)":
    st.title("Reconnaissance des machines par leur signature électrique")
    st.markdown("Chaque machine déforme le courant à sa manière. VoltEye transforme cette signature en **image** "
                "(transformée en ondelettes, spectre harmonique, *Gramian Angular Field*) puis un **CNN** la reconnaît.")
    c1, c2, c3, c4 = st.columns(4)
    m = c1.selectbox("Machine", CLASSES, format_func=lambda k: LABELS[k])
    load = c2.slider("Taux de charge", 0.35, 1.0, 0.8)
    noise = c3.slider("Niveau de bruit de mesure", 0.0, 4.0, 1.0, help="1 = conditions nominales")
    if c4.button("🎲 Nouvelle machine"):
        st.session_state.seed = int(np.random.randint(1e6))
    rng = np.random.default_rng(st.session_state.get("seed", 1))
    inst = sample_instance(m, rng)
    wave = event_waveform(inst, load, rng, noise=max(noise, 1e-3))
    meas = measurements(wave)
    kpi_row([("P", f"{meas['P_kW']:.1f} kW", None), ("Q", f"{meas['Q_kvar']:.1f} kvar", None),
             ("Facteur de puissance", f"{meas['PF']:.2f}", None), ("THD", f"{meas['THD'] * 100:.1f} %", None)])
    c1, c2 = st.columns(2)
    c1.plotly_chart(go.Figure(go.Scatter(x=time_axis() * 1000, y=wave, line=dict(color=COLORS[m])))
                    .update_layout(height=260, title="1. Courant de l'événement (2 périodes)", xaxis_title="ms",
                                   yaxis_title="A"), use_container_width=True)
    h = harmonic_spectrum(wave)[:15]
    c2.plotly_chart(px.bar(x=np.arange(1, 16), y=h / h[0], color_discrete_sequence=[COLORS[m]])
                    .update_layout(height=260, title="2. Spectre harmonique (FFT)", xaxis_title="rang",
                                   yaxis_title="/ fondamental"), use_container_width=True)
    st.markdown("**3. Les trois séquences deviennent trois images GAF, fusionnées en une image couleur**")
    seq = feature_sequences(wave)
    cols = st.columns(4)
    for col, (name, s) in zip(cols, seq.items()):
        img = ((gasf(s) + 1) * 127.5).astype(np.uint8)
        col.image(img, caption=f"GAF : {name}", use_container_width=True, clamp=True)
    cols[3].image(to_display(rgb_image(wave)), caption="Image RVB fusionnée", use_container_width=True)
    rec = recognizer()
    p_fused = rec.predict_proba([wave])[0]
    p_cnn = rec.predict_proba_cnn([wave])[0]
    pred = CLASSES[int(p_fused.argmax())]
    st.markdown("**4. Décision du modèle**")
    (st.success if pred == m else st.error)(
        f"Machine reconnue : **{LABELS[pred]}** (confiance {p_fused.max() * 100:.1f} %) · "
        f"machine réelle : {LABELS[m]}")
    probs = pd.DataFrame({"Machine": [LABELS[k] for k in CLASSES], "CNN GAF": p_cnn, "VoltEye (fusion)": p_fused})
    st.plotly_chart(px.bar(probs.melt("Machine", var_name="Modèle", value_name="probabilité"), x="probabilité",
                           y="Machine", color="Modèle", barmode="group", orientation="h", range_x=[0, 1])
                    .update_layout(height=380), use_container_width=True)


# =============================================================================
elif page == "Anomalies & maintenance":
    st.title("Détection des gaspillages et maintenance prédictive")
    tab1, tab2 = st.tabs(["⚠️ Anomalies énergétiques", "🛠️ Santé des machines"])
    with tab1:
        m = st.selectbox("Machine", CLASSES, index=1, format_func=lambda k: LABELS[k])
        d = anom[anom["machine"] == m]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d.index, y=d["energie_kWh"], name="Énergie journalière", line=dict(color=COLORS[m])))
        fig.add_trace(go.Scatter(x=d.index, y=d["attendu_kWh"], name="Attendue (modèle)", line=dict(color="gray", dash="dot")))
        lab = d[d["verite"].isin(["veille", "fuite_air", "pic", "eclairage_weekend", "panne"])]
        fig.add_trace(go.Scatter(x=lab.index, y=lab["energie_kWh"], mode="markers", name="Anomalie réelle (vérité)",
                                 marker=dict(symbol="square-open", size=11, color="orange")))
        al = d[d["alerte"]]
        fig.add_trace(go.Scatter(x=al.index, y=al["energie_kWh"], mode="markers", name="Alerte VoltEye",
                                 marker=dict(color="red", size=7)))
        fig.update_layout(height=380, yaxis_title="kWh / jour", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)
        rows = al.reset_index()
        st.markdown(f"**{len(rows)} alertes pour cette machine**")
        if len(rows):
            st.dataframe(pd.DataFrame({
                "Date": rows["time"].dt.date, "Score": rows["score"].round(1),
                "Cause": rows["cause"], "Recommandation": rows["cause"].map(am["recommandations"]),
                "Excès (kWh)": (rows["exces_production"] + rows["exces_hors_production"]).clip(lower=0).round(0),
                "Coût (TND)": rows["cout_exces_TND"].round(1),
                "CO₂ (kg)": ((rows["exces_production"] + rows["exces_hors_production"]).clip(lower=0) * C.EMISSION_FACTOR).round(0),
                "Vérité": rows["verite"].replace("", "-")}), hide_index=True, use_container_width=True)
    with tab2:
        day = st.slider("Situation au", value=pd.Timestamp("2026-05-01").to_pydatetime(),
                        min_value=pd.Timestamp("2026-01-01").to_pydatetime(),
                        max_value=pd.Timestamp("2026-10-31").to_pydatetime(), format="DD/MM/YYYY")
        snap = health[health.index == pd.Timestamp(day).normalize()]
        cols = st.columns(len(CLASSES))
        for col, (_, r) in zip(cols, snap.iterrows()):
            col.metric(LABELS[r["machine"]].split(" (")[0], f"{r['sante']:.0f}/100",
                       f"THD +{r['derive'] * 100:.0f} %" if r["derive"] > 0.05 else "stable",
                       delta_color="inverse" if r["derive"] > 0.05 else "off")
            if r["alerte"]:
                left = r["jours_avant_seuil"]
                col.error("Alerte maintenance" + (f" · seuil critique dans ~{left:.0f} j" if pd.notna(left) else ""))
        m = st.selectbox("Historique de santé", CLASSES, index=3, format_func=lambda k: LABELS[k])
        v = health[health["machine"] == m]
        fig = go.Figure(go.Scatter(x=v.index, y=v["sante"], name="Score de santé", line=dict(color=COLORS[m])))
        fig.add_hline(y=75, line_dash="dot", annotation_text="seuil d'alerte (THD +25 %)")
        fig.add_vline(x=pd.Timestamp(day), line_color="gray")
        fig.update_layout(height=320, yaxis_title="santé /100", yaxis_range=[0, 105])
        st.plotly_chart(fig, use_container_width=True)
        mt = am["maintenance"]
        st.info(f"Sur l'historique, la dégradation du moteur de convoyeur est signalée le "
                f"**{mt['convoyeur']['premiere_alerte']}**, soit **{mt['anticipation_panne_convoyeur_jours']} jours** "
                f"avant la panne, avec {mt['fausses_alertes_autres_machines_jours']} jour(s) de fausse alerte sur les autres machines.")


# =============================================================================
elif page == "Prévision & optimisation":
    st.title("Prévoir la consommation et optimiser le planning")
    tab1, tab2 = st.tabs(["📈 Prévision J+1", "🧮 Optimisation tarifaire"])
    with tab1:
        fc = load_parquet("forecast_test.parquet")
        days = sorted({d for d in fc.index.date})
        start = st.select_slider("Début de la fenêtre", days, value=days[14])
        w = fc[(fc.index.date >= start) & (fc.index.date < start + pd.Timedelta(days=7))]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=w.index, y=w["reel"], name="Réel", line=dict(color="black")))
        fig.add_trace(go.Scatter(x=w.index, y=w["prevision"], name="Prévision VoltEye", line=dict(color="#2a6fdb")))
        fig.add_trace(go.Scatter(x=w.index, y=w["baseline_semaine"], name="Baseline semaine précédente",
                                 line=dict(color="#e4572e", dash="dot")))
        fig.update_layout(height=380, yaxis_title="kWh / heure", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(pd.DataFrame(fm["models"]).T.round(2), use_container_width=True)
        st.caption(f"Période de test (jamais vue à l'entraînement) : {fm['periode_test'][0][:10]} → {fm['periode_test'][1][:10]}")
    with tab2:
        res = opt["resume"]
        kpi_row([("Gain moyen", f"{res['gain_moyen_TND_par_jour']:.1f} TND/jour", None),
                 ("Réduction de facture", f"{res['gain_moyen_%']:.1f} %", None),
                 ("Pointe évitée", f"{res['reduction_pointe_moyenne_kW']:.0f} kW", None),
                 ("Gain annuel estimé", f"{fmt(res['gain_annuel_estime_TND'])} TND", "≈ 290 jours ouvrés")])
        names = [d["jour"] for d in opt["jours"]]
        day = st.selectbox("Jour", names, index=len(names) // 2)
        d = next(x for x in opt["jours"] if x["jour"] == day)
        base = np.array(d["base"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(24)), y=base + schedule_profile(d["ref"]), name="Planning actuel",
                                 line=dict(shape="hv", color="#e4572e")))
        fig.add_trace(go.Scatter(x=list(range(24)), y=base + schedule_profile(d["opt"]), name="Planning optimisé",
                                 line=dict(shape="hv", color="#29a36a", width=3)))
        fig.add_trace(go.Scatter(x=list(range(24)), y=d["prix"], name="Tarif (TND/kWh)", yaxis="y2",
                                 line=dict(shape="hv", color="gray", dash="dot")))
        fig.update_layout(height=380, xaxis_title="heure", yaxis_title="kW",
                          yaxis2=dict(overlaying="y", side="right", title="TND/kWh"), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(pd.DataFrame([{"Tâche flexible": t["nom"], "Puissance (kW)": t["kW"], "Durée (h)": t["duree"],
                                    "Actuel": f"{r} h", "Optimisé": f"{o} h"}
                                   for t, r, o in zip(TASKS, d["ref"], d["opt"])]), hide_index=True, use_container_width=True)
        st.success(f"Facture du jour : {d['facture_ref_TND']:.0f} TND → **{d['facture_opt_TND']:.0f} TND** · "
                   f"pointe {d['pointe_ref_kW']:.0f} kW → **{d['pointe_opt_kW']:.0f} kW**")
        op = res.get("reference_operateur_averti")
        if op:
            st.info(f"Face à un opérateur qui connaît déjà le tarif (chaque tâche à l'heure la moins chère, sans "
                    f"coordination), l'optimiseur gagne encore **{op['gain_moyen_%']:.1f} %** "
                    f"({op['gain_moyen_TND_par_jour']:.1f} TND/jour) et **{op['reduction_pointe_moyenne_kW']:.0f} kW** "
                    f"de pointe, grâce à la coordination des tâches.")


# =============================================================================
elif page == "Vue ville":
    st.title("VoltEye à l'échelle de la ville")
    st.markdown("Chaque site équipé d'un terminal VoltEye remonte ses indicateurs vers le cloud : la ville et le "
                "distributeur d'énergie disposent d'une **carte de la charge industrielle**, des gaspillages et des "
                "gisements d'économies. *(Sites fictifs extrapolés du site de référence.)*")
    sites = pd.DataFrame(load_json("city_sites.json"))
    kpi_row([("Sites connectés", str(len(sites)), None),
             ("Consommation", f"{fmt(sites['consommation_MWh_an'].sum())} MWh/an", None),
             ("Gaspillage détecté", f"{fmt(sites['gaspillage_detecte_MWh_an'].sum())} MWh/an", None),
             ("CO₂ évitable", f"{fmt(sites['co2_evitable_t_an'].sum(), 1)} t/an", None),
             ("Gain planification", f"{fmt(sites['gain_planification_TND_an'].sum())} TND/an", None)])
    fig = px.scatter_map(sites, lat="lat", lon="lon", size="consommation_MWh_an", color="sante_moyenne",
                         color_continuous_scale="RdYlGn", range_color=[70, 100], hover_name="site",
                         hover_data={"secteur": True, "alertes_actives": True, "lat": False, "lon": False},
                         center=dict(lat=35.6, lon=10.0), zoom=5.8, height=560, map_style="open-street-map")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar_title="santé")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(sites.drop(columns=["lat", "lon"]).round(1), hide_index=True, use_container_width=True)


# =============================================================================
elif page == "Évaluation des modèles":
    st.title("Évaluation : données, méthodes, résultats")
    st.markdown("Toutes les métriques sont calculées sur des données **jamais vues à l'entraînement**, et chaque "
                "modèle est comparé à au moins une **baseline** simple.")
    st.subheader("1. Reconnaissance des machines")
    st.caption(f"{rm['n_train']} événements d'entraînement, {rm['n_val']} de validation, {rm['n_test']} de test (7 classes)")
    st.dataframe(pd.DataFrame(rm["models"]).T.rename(columns={
        "accuracy": "Exactitude", "f1_macro": "F1 macro", "ms_par_evenement": "ms / événement",
        "accuracy_bruit_x3": "Exactitude bruit x3"}).round(3), use_container_width=True)
    cm = np.array(rm["confusion_volteye"])
    st.plotly_chart(px.imshow(cm, x=CLASSES, y=CLASSES, text_auto=True, color_continuous_scale="Blues",
                              labels=dict(x="prédit", y="réel"), title="Matrice de confusion VoltEye")
                    .update_layout(height=420), use_container_width=True)
    st.subheader("2. Désagrégation du flux temps réel (4 h, 1 mesure/s)")
    st.dataframe(pd.DataFrame([{k: v for k, v in sm.items() if not isinstance(v, (list, dict))}]).round(3),
                 hide_index=True, use_container_width=True)
    if "scenario_dense" in sm:
        dn = sm["scenario_dense"]
        st.caption(f"Scénario dense ({dn['duree_min']} min, {dn['evenements_reels']} événements dont "
                   f"{dn['evenements_a_moins_de_4_s']} à moins de 4 s d'écart) : détection F1 {dn['detection_f1']:.3f}, "
                   f"reconnaissance {dn['classification_exactitude'] * 100:.1f} %.")
    st.dataframe(pd.DataFrame(sm["par_machine"]).T.round(3), use_container_width=True)
    st.subheader("3. Prévision J+1")
    st.dataframe(pd.DataFrame(fm["models"]).T.round(2), use_container_width=True)
    st.subheader("4. Détection d'anomalies (jours-machine)")
    pr = am.get("protocole")
    if pr:
        st.caption(f"Backtest glissant : modèle réentraîné chaque mois sur le passé uniquement. Seuils réglés sur la "
                   f"validation ({pr['validation'][0]} → {pr['validation'][1]}), score publié sur le test "
                   f"({pr['test'][0]} → {pr['test'][1]}) : {pr['jours_test']} jours-machine, "
                   f"dont {pr['jours_anormaux_test']} anormaux.")
    st.dataframe(pd.DataFrame(am["models"]).T.round(3), use_container_width=True)
    st.dataframe(pd.DataFrame(am["rappel_par_type"]).T.round(2), use_container_width=True)
    st.subheader("5. Maintenance prédictive")
    st.json(am["maintenance"], expanded=False)
    st.subheader("6. Optimisation")
    st.json({k: v for k, v in opt["resume"].items() if k != "taches"})
    if (A / "hipe_metrics.json").exists():
        hm = load_json("hipe_metrics.json")
        st.subheader("7. Validation sur données industrielles réelles (HIPE, KIT)")
        st.caption(hm["source"])
        sig = {k: v for k, v in hm["signatures"].items() if k != "machines"}
        st.markdown("**Reconnaissance des signatures réelles de 7 machines**")
        st.dataframe(pd.DataFrame(sig).T[["exactitude", "f1_macro"]].round(4), use_container_width=True)
        det, rec = hm["detection"], hm["reconnaissance"]
        kpi_row([("Événements retrouvés au point unique", f"{det['rappel'] * 100:.1f} %",
                  f"{det['evenements_machines_suivies']} événements des machines suivies"),
                 ("Attribution des événements", f"{rec['VoltEye - ΔP, ΔQ + harmoniques + forêt aléatoire']['exactitude'] * 100:.1f} %",
                  "avec harmoniques, arrivée générale"),
                 ("Prévision à 1 h (MAPE)", f"{hm['prevision_1h']['VoltEye - gradient boosting']['MAPE_%']:.1f} %",
                  f"persistance : {hm['prevision_1h']['Baseline - valeur d' + chr(39) + 'il y a 1 h']['MAPE_%']:.1f} %"),
                 ("Énergie hors production", f"{hm['hors_production']['MainTerminal']['part_hors_production'] * 100:.0f} %",
                  f"talon de {hm['hors_production']['talon_site_kW']:.1f} kW la nuit et le week-end")])


# =============================================================================
elif page == "Architecture":
    st.title("Architecture de VoltEye")
    st.markdown("""
```
 Machines ──► point de mesure unique ──► capteur de puissance ──► passerelle edge ──► cloud ──► tableau de bord
 (charges)    (arrivée électrique)       (V, I, harmoniques)     (Raspberry Pi 5)    (NB-IoT/5G)  (ville, STEG, usine)
```
| Couche | Rôle | MVP | Cible de déploiement |
|---|---|---|---|
| **Charge** | Machines du site | Simulateur de 7 types de machines | Machines réelles |
| **Terminal** | Mesure du courant, détection des événements, inférence IA | Simulateur de flux + PC | Capteur triphasé + Raspberry Pi 5 (< 100 $/site) |
| **Réseau** | Remontée des indicateurs | — | NB-IoT / 4G-5G |
| **Cloud** | Historique, prévision, anomalies, optimisation, vue ville | Python + fichiers Parquet | Serveur + MongoDB |
| **Présentation** | Tableau de bord, alertes, rapports | Streamlit | Web + notifications |

**Chaîne IA**
1. **Détection d'événements** : marche de puissance au point de mesure ;
2. **Signature** : courant « après − avant », transformée en ondelettes (db4) et spectre harmonique (FFT) ;
3. **Image GAF** : trois *Gramian Angular Fields* fusionnés en RVB ;
4. **Reconnaissance** : CNN + grandeurs électriques, fusionné avec une forêt aléatoire sur le spectre ;
5. **Analyse** : prévision J+1 (gradient boosting), anomalies (résidus + score robuste), santé (dérive du THD),
   optimisation (programme linéaire en nombres entiers, HiGHS).

La méthode signal → GAF → CNN s'inspire des travaux publiés sur la reconnaissance de charges par images GAF
(voir les références du rapport).
""")
