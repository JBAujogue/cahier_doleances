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


def _est_pliable(n):
    return len(enfants[n]) > 0


_hauteur_memo = {}


def _hauteur(n):
    """Hauteur au-dessus des feuilles (0 = feuille)."""
    if n in _hauteur_memo:
        return _hauteur_memo[n]
    h = 0 if not enfants[n] else 1 + max(_hauteur(c) for c in enfants[n])
    _hauteur_memo[n] = h
    return h


def _type(n):
    """Rôle structurel, vocabulaire de la réunion (au lieu du level numérique)."""
    h = _hauteur(n)
    return "enfant" if h == 0 else "parent" if h == 1 else "grand-parent"


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
                       line=dict(width=1, color="#d1d5db"), hoverinfo="none")

    # couleur par distance au focus ; label seulement si lisible (focus, voisins directs, gros nœuds)
    teinte = {0: "#ef4444", 1: "#6366f1", 2: "#a5b4fc"}
    ordre = list(dist)
    seuil = sorted((_rec(n) for n in ordre), reverse=True)[:18][-1] if len(ordre) > 18 else 0
    labels = []
    for n in ordre:
        montrer = dist[n] <= 1 or _rec(n) >= seuil
        if not montrer:
            labels.append("")
            continue
        prefixe = "▸ " if _est_pliable(n) and n != focus else ""
        labels.append(prefixe + (n[:24] + "…" if len(n) > 24 else n))
    nodes = go.Scatter(
        x=[pos[n][0] for n in ordre], y=[pos[n][1] for n in ordre],
        mode="markers+text", text=labels, textposition="top center",
        textfont=dict(size=10, color="#334155"),
        hovertext=[f"{n}<br>{_rec(n)} détections"
                   + (f" · {len(enfants[n])} sous-thèmes" if enfants[n] else "") for n in ordre],
        hoverinfo="text",
        marker=dict(size=[24 if n == focus else 12 + min(_rec(n), 24) for n in ordre],
                    color=[teinte[dist[n]] for n in ordre],
                    line=dict(width=2, color="#ffffff")),
    )
    fig = go.Figure([edges, nodes])
    fig.update_layout(
        showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False),
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


def _feuilles(n):
    """Topics feuilles (enfants) sous un nœud."""
    if not enfants[n]:
        return [n]
    out = []
    for c in enfants[n]:
        out.extend(_feuilles(c))
    return out


#  interface
BANNIERE = (
    f"### Cahiers de doléances — exploration des thèmes (POC)\n"
    f"**{len(docs)} documents analysés sur {len(df)}** · vue filtrée qualité : "
    f"**{len(propre)} topics propres** ({round(100 * sum(own.get(n, 0) for n in propre) / TOTAL_INST)} % "
    f"des détections) · {len(topics) - len(propre)} topics hors périmètre · "
    f"{len(LABELS)} arbres thématiques\n\n"
    f"*Sélection en fil d'Ariane : **grand-parent** (arbre) → **parent** (sous-thème) → **topic**.*"
)

GP_CHOICES = [(lbl, RACINE[lbl]) for lbl in LABELS]
DEFAULT_ROOT = RACINE[LABELS[0]]


def on_grandparent(root):
    kids = sorted(enfants[root], key=_rec, reverse=True)
    pchoices = [(f"{k} · {_rec(k)} détections", k) for k in kids]
    return (
        _figure(root),
        gr.update(choices=pchoices, value=None, label=f"Parent · sous-thème ({len(kids)})"),
        gr.update(choices=[], value=None, label="Topic"),
        _description(root), _occurrences(root), root,
    )


def on_parent(parent, focus):
    if not parent:                                    # reset programmatique : no-op
        return _figure(focus), gr.update(), _description(focus), _occurrences(focus), focus
    leaves = sorted(_feuilles(parent), key=_rec, reverse=True)
    tchoices = [(f"{lf} · {_rec(lf)} détections", lf) for lf in leaves]
    return (
        _figure(parent),
        gr.update(choices=tchoices, value=None, label=f"Topic ({len(leaves)})"),
        _description(parent), _occurrences(parent), parent,
    )


def on_topic(topic, focus):
    cible = topic or focus
    return _figure(cible), _description(cible), _occurrences(cible), cible


with gr.Blocks(title="Doléances — thèmes") as demo:
    gr.Markdown(BANNIERE)
    focus_state = gr.State()

    # ── sélection fil d'Ariane à 3 niveaux, en haut ──
    with gr.Row():
        gp = gr.Dropdown(GP_CHOICES, value=DEFAULT_ROOT, label="Grand-parent · arbre",
                         filterable=True, scale=1)
        parent_dd = gr.Dropdown(label="Parent · sous-thème", filterable=True, scale=1)
        topic_dd = gr.Dropdown(label="Topic", filterable=True, scale=1)

    # ── graphe à gauche, détails (description + occurrences) à droite ──
    with gr.Row():
        with gr.Column(scale=2):
            plot = gr.Plot()
        with gr.Column(scale=1):
            description = gr.Markdown()
            occurrences = gr.Markdown()

    gp.change(on_grandparent, gp,
              [plot, parent_dd, topic_dd, description, occurrences, focus_state])
    parent_dd.change(on_parent, [parent_dd, focus_state],
                     [plot, topic_dd, description, occurrences, focus_state])
    topic_dd.change(on_topic, [topic_dd, focus_state],
                    [plot, description, occurrences, focus_state])
    demo.load(on_grandparent, gp,
              [plot, parent_dd, topic_dd, description, occurrences, focus_state])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
