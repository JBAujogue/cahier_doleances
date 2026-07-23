"""Simulation Gradio — vue graphe des topics de JB (POC, lit les fichiers bruts).

Principe validé :
- filtre qualité : on écarte doublons de noms, isolés et cycles (86 % des
  détections conservées) — filtre de VUE, on ne modifie pas la donnée ;
- on n'affiche JAMAIS tout l'arbre (288 nœuds = illisible) : navigation par
  FOCUS + DÉPLIAGE. La vue montre le voisinage du nœud courant (profondeur 2,
  plafonné) ; on descend en choisissant un sous-thème, on remonte d'un bouton ;
- spatialisation Fruchterman-Reingold (force-directed, façon Gephi) via
  networkx.spring_layout, focus ancré au centre ;
- graphe à gauche, panneau détail à droite (description, occurrences).

Lancer :  uv run python analyse/simulation_graph.py
"""
import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

import gradio as gr
import networkx as nx
import pandas as pd
import plotly.graph_objects as go

RADIUS = 2      # profondeur du voisinage affiché autour du focus
CAP = 45        # plafond de nœuds : au-delà, FR devient illisible

DATA = Path(__file__).parent / "data"

# chargement
topics = json.loads((DATA / "analysis/structure/taxonomy_3.json").read_text())["topics"]
docs = json.loads((DATA / "analysis/label/instances.json").read_text())["documents"]
df = pd.read_csv(DATA / "dataset.csv")

noms = Counter(t["name"] for t in topics)
by_name = {t["name"]: t for t in topics}
content = {str(r.id): r.content for r in df.itertuples()}

occ = defaultdict(list)
for d in docs:
    for lab in d["labels"]:
        occ[lab["name"]].append((str(d["id"]), lab["rationale"], lab["extract"]))
own = {n: len(v) for n, v in occ.items()}
TOTAL_INST = sum(own.values())

#  filtre qualité (vue) ─
dup = {n for n, c in noms.items() if c > 1}
est_parent = {t["parent"] for t in topics if t["parent"]}
isoles = {t["name"] for t in topics if not t["parent"] and t["name"] not in est_parent}


def _cyclique(t, vus=None):
    vus = vus or set()
    if t["name"] in vus:
        return True
    vus.add(t["name"])
    p = t["parent"]
    return _cyclique(by_name[p], vus) if p and p in by_name and noms[p] == 1 else False


cycliques = {t["name"] for t in topics if _cyclique(t)}
propre = {t["name"] for t in topics if t["name"] not in dup | isoles | cycliques}

parent_de = {n: by_name[n]["parent"] for n in propre if by_name[n]["parent"] in propre}
enfants = defaultdict(list)
for n, p in parent_de.items():
    enfants[p].append(n)


def _rec(n, vus=None):
    """Instances propres + celles de toute la descendance (arbre acyclique)."""
    vus = vus or set()
    if n in vus:
        return 0
    vus.add(n)
    return own.get(n, 0) + sum(_rec(c, vus) for c in enfants[n])


#  composantes (arbres) du sous-ensemble propre
adj = defaultdict(set)
for n in propre:
    adj[n]
    if n in parent_de:
        adj[n].add(parent_de[n])
        adj[parent_de[n]].add(n)

vus, comps = set(), []
for depart in adj:
    if depart in vus:
        continue
    pile, c = [depart], []
    while pile:
        x = pile.pop()
        if x in vus:
            continue
        vus.add(x)
        c.append(x)
        pile.extend(adj[x] - vus)
    comps.append(c)

arbres = []
for c in sorted(comps, key=lambda c: -sum(own.get(n, 0) for n in c)):
    n_inst = sum(own.get(n, 0) for n in c)
    if n_inst == 0:
        continue
    racine = next((n for n in c if n not in parent_de), c[0])
    arbres.append((f"{racine[:45]} — {len(c)} topics · {n_inst} détections", racine))

LABELS = [a[0] for a in arbres]
RACINE = dict(arbres)


_hauteur_memo = {}


def _hauteur(n):
    """Hauteur au-dessus des feuilles (0 = feuille)."""
    if n in _hauteur_memo:
        return _hauteur_memo[n]
    h = 0 if not enfants[n] else 1 + max(_hauteur(c) for c in enfants[n])
    _hauteur_memo[n] = h
    return h


def _type(n):
    """Typologie (option B) selon la hauteur au-dessus des feuilles."""
    h = _hauteur(n)
    return "enfant" if h == 0 else "parent" if h == 1 else "grand-parent" if h == 2 else "racine"


# couleur STABLE par typologie — 4 teintes DISTINCTES (le rouge est réservé au focus)
COULEUR = {"racine": "#7c3aed",        # violet
           "grand-parent": "#2563eb",  # bleu
           "parent": "#f59e0b",        # ambre
           "enfant": "#10b981"}        # vert
ORDRE_TYPE = ["racine", "grand-parent", "parent", "enfant"]


# ──── voisinage (focus + rayon 2) ───
def _voisinage(focus):
    """BFS non orienté autour du focus, plafonné à CAP nœuds (les plus lourds
    d'abord à distance égale). Renvoie {nœud: distance au focus}."""
    dist = {focus: 0}
    file = deque([focus])
    while file:
        n = file.popleft()
        if dist[n] >= RADIUS:
            continue
        voisins = ([parent_de[n]] if n in parent_de else []) + enfants[n]
        for v in sorted(voisins, key=_rec, reverse=True):
            if v not in dist:
                dist[v] = dist[n] + 1
                file.append(v)
    if len(dist) <= CAP:
        return dist
    garde = sorted(dist, key=lambda n: (dist[n], -_rec(n)))[:CAP]
    return {n: dist[n] for n in garde}


#  vue : Fruchterman-Reingold (force-directed)
def _figure(focus):
    dist = _voisinage(focus)
    G = nx.Graph()
    G.add_nodes_from(dist)
    for n in dist:
        if n in parent_de and parent_de[n] in dist:
            G.add_edge(n, parent_de[n])

    # Fruchterman-Reingold, focus ancré au centre pour un rendu stable
    pos = nx.spring_layout(G, k=2.2 / (len(G) ** 0.5), seed=42,
                           pos={focus: (0, 0)}, fixed=[focus], iterations=200)

    ex, ey = [], []
    for a, b in G.edges():
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
    edges = go.Scatter(x=ex, y=ey, mode="lines",
                       line=dict(width=1, color="#d1d5db"), hoverinfo="none", showlegend=False)

    ordre = list(dist)
    seuil = sorted((_rec(n) for n in ordre), reverse=True)[:18][-1] if len(ordre) > 18 else 0

    def _label(n):                       # label seulement si lisible (focus, voisins, gros nœuds)
        if not (dist[n] <= 1 or _rec(n) >= seuil or n == focus):
            return ""
        return n[:24] + "…" if len(n) > 24 else n

    traces = [edges]
    # une trace par typologie présente : couleur STABLE + légende automatique
    for typ in ORDRE_TYPE:
        ns = [n for n in ordre if _type(n) == typ]
        if not ns:
            continue
        traces.append(go.Scatter(
            x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns],
            mode="markers+text", text=[_label(n) for n in ns],
            textposition="top center", textfont=dict(size=10, color="#334155"),
            name=typ,
            hovertext=[f"{n}<br>{_type(n)} · {_rec(n)} détections" for n in ns],
            hoverinfo="text",
            marker=dict(size=[12 + min(_rec(n), 24) for n in ns],
                        color=COULEUR[typ], line=dict(width=1.5, color="#ffffff")),
        ))
    # anneau rouge = « vous êtes ici » (la couleur du nœud continue de dire son type)
    traces.append(go.Scatter(
        x=[pos[focus][0]], y=[pos[focus][1]], mode="markers", name="sélection",
        marker=dict(size=20 + min(_rec(focus), 24), color="rgba(0,0,0,0)",
                    line=dict(width=3, color="#ef4444")),
        hoverinfo="skip",
    ))
    fig = go.Figure(traces)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", xanchor="right", x=1, yanchor="bottom", y=0,
                    bgcolor="rgba(255,255,255,0.75)", bordercolor="#e5e7eb", borderwidth=1),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=560,
    )
    return fig


def _figure_apercu(racines):
    """Vue d'ensemble : chaque arbre = un point (sa racine), sans arêtes.
    Taille = détections, couleur = type. Spirale phyllotaxique : les plus gros
    thèmes au centre, étalement régulier, déterministe."""
    ordre = sorted(racines, key=_rec, reverse=True)          # gros au centre
    angle = math.pi * (3 - math.sqrt(5))                     # angle d'or
    pos = {r: (math.sqrt(i) * math.cos(i * angle), math.sqrt(i) * math.sin(i * angle))
           for i, r in enumerate(ordre)}
    seuil = sorted((_rec(r) for r in racines), reverse=True)[:25][-1] if len(racines) > 25 else 0

    traces = []
    for typ in ORDRE_TYPE:
        ns = [r for r in racines if _type(r) == typ]
        if not ns:
            continue
        traces.append(go.Scatter(
            x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns],
            mode="markers+text",
            text=[(n[:22] + "…" if len(n) > 22 else n) if _rec(n) >= seuil else "" for n in ns],
            textposition="top center", textfont=dict(size=9, color="#334155"),
            name=typ,
            hovertext=[f"{n}<br>{_type(n)} · {_rec(n)} détections" for n in ns],
            hoverinfo="text",
            marker=dict(size=[6 + min(_rec(n), 42) for n in ns], color=COULEUR[typ],
                        line=dict(width=1, color="#ffffff")),
        ))
    fig = go.Figure(traces)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", xanchor="right", x=1, yanchor="bottom", y=0,
                    bgcolor="rgba(255,255,255,0.75)", bordercolor="#e5e7eb", borderwidth=1),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=560,
    )
    return fig


def _description(nom):
    """Bloc gauche : identité + description, identique quel que soit le type."""
    t = by_name[nom]
    sous = f"{len(enfants[nom])} sous-thèmes" if enfants[nom] else "aucun sous-thème (feuille)"
    return (
        f"### {nom}\n"
        f"**Type** : {_type(nom)} · **Parent** : {t['parent'] or '— (racine)'} · {sous}\n\n"
        f"**Détections** : {_rec(nom)} au total · {own.get(nom, 0)} sur ce topic\n\n"
        f"{t['description']}"
    )


def _occurrences(nom):
    """Bloc droit : où ce topic apparaît dans les textes citoyens."""
    lignes = []
    for doc_id, rationale, extract in occ.get(nom, [])[:8]:
        literal = extract[:40] in content.get(doc_id, "")
        cite = f"« {extract.strip()} »" if literal else f"*(reformulé)* {extract.strip()}"
        lignes.append(f"> {cite}\n>\n> — doc {doc_id} · {rationale}")
    corps = "\n\n".join(lignes) if lignes else (
        "*Ce thème regroupe des sous-thèmes ; les occurrences sont sur les topics feuilles.*"
        if enfants[nom] else "*Aucune occurrence sur ce topic.*"
    )
    return f"#### Occurrences dans les textes\n{corps}"


#  interface
BANNIERE = (
    f"### Cahiers de doléances — exploration des thèmes (POC)\n"
    f"**{len(docs)} documents analysés sur {len(df)}** · vue filtrée qualité : "
    f"**{len(propre)} topics propres** ({round(100 * sum(own.get(n, 0) for n in propre) / TOTAL_INST)} % "
    f"des détections) · {len(topics) - len(propre)} topics hors périmètre · "
    f"{len(LABELS)} arbres thématiques\n\n"
    f"*Sélection à 4 niveaux : **racine** (arbre) → **grand-parent** → **parent** → **enfant**. "
    f"La couleur d'un nœud dit toujours son type (voir la légende du graphe).*"
)

ROOTS = [root for _, root in arbres]            # racines d'arbres, triées par détections
APERCU = "— Vue d'ensemble —"                    # sentinel : carte de tous les arbres


def _kids(n):
    return sorted(enfants[n], key=_rec, reverse=True)


def _apercu_md():
    return (
        f"### Vue d'ensemble\n"
        f"**{len(ROOTS)} arbres thématiques**, {len(propre)} topics propres.\n\n"
        f"Chaque point = un arbre (sa racine). **Taille** = nombre de détections, "
        f"**couleur** = type. Sélectionne une racine dans le menu pour explorer son arbre."
    )


def on_racine(root):
    if not root or root == APERCU:               # retour à la carte d'ensemble
        return (
            _figure_apercu(ROOTS),
            gr.update(choices=[], value=None, label="Grand-parent"),
            gr.update(choices=[], value=None, label="Parent"),
            gr.update(choices=[], value=None, label="Enfant · topic"),
            _apercu_md(), "", None,
        )
    return (
        _figure(root),
        gr.update(choices=_kids(root), value=None, label="Grand-parent"),
        gr.update(choices=[], value=None, label="Parent"),
        gr.update(choices=[], value=None, label="Enfant · topic"),
        _description(root), _occurrences(root), root,
    )


def on_gp(node, focus):
    if not node:                                       # reset programmatique : on ne touche à rien
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), focus
    return (
        _figure(node),
        gr.update(choices=_kids(node), value=None, label="Parent"),
        gr.update(choices=[], value=None, label="Enfant · topic"),
        _description(node), _occurrences(node), node,
    )


def on_parent(node, focus):
    if not node:
        return gr.update(), gr.update(), gr.update(), gr.update(), focus
    return (
        _figure(node),
        gr.update(choices=_kids(node), value=None, label="Enfant · topic"),
        _description(node), _occurrences(node), node,
    )


def on_enfant(node, focus):
    if not node:
        return gr.update(), gr.update(), gr.update(), focus
    return _figure(node), _description(node), _occurrences(node), node


with gr.Blocks(title="Doléances — thèmes") as demo:
    gr.Markdown(BANNIERE)
    focus_state = gr.State()

    # ── sélection à 4 niveaux, en haut (sans stats : elles sont dans le panneau) ──
    with gr.Row():
        racine_dd = gr.Dropdown([APERCU] + ROOTS, value=APERCU, label="Racine · arbre",
                                filterable=True, scale=1)
        gp_dd = gr.Dropdown(label="Grand-parent", filterable=True, scale=1)
        parent_dd = gr.Dropdown(label="Parent", filterable=True, scale=1)
        enfant_dd = gr.Dropdown(label="Enfant · topic", filterable=True, scale=1)

    # ── graphe à gauche, détails (description + occurrences) à droite ──
    with gr.Row():
        with gr.Column(scale=2):
            plot = gr.Plot()
        with gr.Column(scale=1):
            description = gr.Markdown()
            occurrences = gr.Markdown()

    racine_dd.change(on_racine, racine_dd,
                     [plot, gp_dd, parent_dd, enfant_dd, description, occurrences, focus_state])
    gp_dd.change(on_gp, [gp_dd, focus_state],
                 [plot, parent_dd, enfant_dd, description, occurrences, focus_state])
    parent_dd.change(on_parent, [parent_dd, focus_state],
                     [plot, enfant_dd, description, occurrences, focus_state])
    enfant_dd.change(on_enfant, [enfant_dd, focus_state],
                     [plot, description, occurrences, focus_state])
    demo.load(on_racine, racine_dd,
              [plot, gp_dd, parent_dd, enfant_dd, description, occurrences, focus_state])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
