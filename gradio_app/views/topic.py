import html

import gradio as gr
import pandas as pd
from data_helpers import list_ref_topics, ref_topic_counts, topic_rows

# Les styles (classes tv-*) vivent dans views/style.css, chargé par app.py (css_paths)


def _name(label: str) -> str:
    """'fiscalité (4)' -> 'fiscalité' (rsplit : robuste aux parenthèses du nom)."""
    return label.rsplit(" (", 1)[0]


def _kpis(rows: pd.DataFrame) -> str:
    tiles = [
        ("Instances", len(rows)),
        ("Contributions", rows["contribution_id"].nunique()),
        ("Communes", rows["city"].nunique()),
    ]
    return '<div class="tv-kpis">' + "".join(
        f'<div class="tv-kpi"><div class="l">{label}</div><div class="v">{value}</div></div>'
        for label, value in tiles
    ) + "</div>"


def _card(r, topic_name: str) -> str:
    doc = html.escape(str(r.pdf_file)) if pd.notna(r.pdf_file) else "N/C"
    corps = (
        f'<div class="tv-quote">« {html.escape(r.verbatim)} »</div>'
        + (f'<div class="tv-sum">{html.escape(r.summary)}</div>' if pd.notna(r.summary) else "")
        if pd.notna(r.verbatim)
        else '<div class="tv-sum">pas encore analysée</div>'
    )
    badges = f'<span class="tv-badge topic">{html.escape(topic_name)}</span>'
    if pd.notna(r.feelings):
        badges += f'<span class="tv-badge">{html.escape(r.feelings)}</span>'
    return (
        '<div class="tv-card">'
        f'<div class="tv-doc">{doc}</div>'
        f'<div class="tv-head">{html.escape(r.city)} — contribution {r.pos}/{r.total}</div>'
        f"{corps}"
        f'<div class="tv-badges">{badges}</div>'
        "</div>"
    )


def render():
    """Construit l'onglet 'Par thème' : dropdown -> KPI + grille de cartes (lecture seule)."""
    labels = list_ref_topics()

    with gr.Row():
        with gr.Column(scale=1):
            theme = gr.Dropdown(
                labels, value=labels[0] if labels else None,
                label="Thème", filterable=True,
            )

            # répartition du corpus, thème sélectionné en évidence
            @gr.render(inputs=theme)
            def repartition(label):
                counts = ref_topic_counts()
                if counts.empty:
                    return
                current = _name(label) if label else None
                mx = max(int(counts["n"].max()), 1)
                lignes = []
                for r in counts.sort_values(["n", "name"], ascending=[False, True]).itertuples():
                    sel = " current" if r.name == current else ""
                    pct = round(int(r.n) / mx * 100)
                    lignes.append(
                        f'<div><div class="tv-dist-label{sel}">'
                        f"<span>{html.escape(r.name)}</span><span class=\"n\">{r.n}</span></div>"
                        f'<div class="tv-dist-track"><div class="tv-dist-fill{sel}" '
                        f'style="width:{pct}%"></div></div></div>'
                    )
                gr.HTML(
                    '<div class="tv-dist">'
                    '<div class="tv-dist-title">Répartition des topics</div>'
                    + "".join(lignes) + "</div>"
                )

        with gr.Column(scale=3):
            # @gr.render : reconstruit le HTML à chaque changement de thème (et au chargement)
            @gr.render(inputs=theme)
            def fiches(label):
                if not label:
                    gr.Markdown("Aucun thème en base : lancer le seed ou attendre l'équipe analyse.")
                    return
                name = _name(label)
                rows = topic_rows(name)
                if rows.empty:
                    gr.Markdown(f"Aucune instance pour **{name}** (pas encore analysé).")
                    return
                cards = "".join(_card(r, name) for r in rows.itertuples())
                gr.HTML(_kpis(rows) + f'<div class="tv-grid">{cards}</div>')
