import json
import math
from collections import Counter, defaultdict, deque
from pathlib import Path

import gradio as gr
import networkx as nx
import pandas as pd
import plotly.graph_objects as go

RADIUS = 2 # profondeur du voisinage affiché autour du focus
CAP = 45 # plafond de nœuds : au-delà, FR devient illisible

DATA = Path(__file__).parent / "data"

# chargement
topics = json.loads((DATA / "analysis/structure/taxonomy_3.json").read_text())["topics"]
docs = json.loads((DATA / "analysis/label/instances.json").read_text())["documents"]
df = pd.read_csv(DATA / "dataset.csv")

noms = Counter(t["name"] for t in topics)
# R1  résolution canonique : parmi les homonymes on retient l'UUID le plus petit
# (déterministe). On ne les SUPPRIME pas : les supprimer orphelinait 620 topics.
by_name = {}
for t in sorted(topics, key=lambda t: t["id"]):
    by_name.setdefault(t["name"], t)
DOUBLONS = sum(1 for c in noms.values() if c > 1)
content = {str(r.id): r.content for r in df.itertuples()}

occ = defaultdict(list)
for d in docs:
    for lab in d["labels"]:
        occ[lab["name"]].append((str(d["id"]), lab["rationale"], lab["extract"]))
own = {n: len(v) for n, v in occ.items()}
TOTAL_INST = sum(own.values())

#  filtre qualité (vue) : on écarte seulement les isolés et les cycles
est_parent = {t["parent"] for t in topics if t["parent"] in by_name}
isoles = {n for n, t in by_name.items() if not t["parent"] and n not in est_parent}


def _cyclique(nom, vus=None):
    vus = vus or set()
    if nom in vus:
        return True
    vus.add(nom)
    p = by_name[nom]["parent"]
    return _cyclique(p, vus) if p and p in by_name else False


cycliques = {n for n in by_name if _cyclique(n)}
propre = set(by_name) - isoles - cycliques

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
    arbres.append((f"{racine[:45]}  {len(c)} topics · {n_inst} détections", racine))

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


# couleur STABLE par typologie  4 teintes DISTINCTES (le rouge est réservé au focus)
COULEUR = {"racine": "#7c3aed", # violet
           "grand-parent": "#2563eb", # bleu
           "parent": "#f59e0b", # ambre
           "enfant": "#10b981"} # vert
ORDRE_TYPE = ["racine", "grand-parent", "parent", "enfant"]


# voisinage (focus + rayon 2)
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

    def _label(n): # label seulement si lisible (focus, voisins, gros nœuds)
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


def _squelette(racines):
    """Nœuds non-feuilles des arbres retenus (racine d'un arbre plat incluse)."""
    keep = set()
    pile = list(racines)
    while pile:
        n = pile.pop()
        if _hauteur(n) >= 1 or n in racines:
            keep.add(n)
            pile.extend(c for c in enfants[n] if _hauteur(c) >= 1)
    return keep


def _layout_foret(keep):
    """Layout RADIAL de forêt : chaque arbre reçoit un secteur angulaire
    proportionnel à sa taille, la profondeur devient le rayon. Contrairement à
    un force-directed, deux arbres ne se chevauchent jamais et les nœuds d'un
    même niveau sont régulièrement espacés sur leur anneau."""
    enf = {n: sorted((c for c in enfants[n] if c in keep), key=_rec, reverse=True)
           for n in keep}
    racines = sorted((n for n in keep if parent_de.get(n) not in keep),
                     key=_rec, reverse=True)

    largeur = {}                       # nb de feuilles du squelette sous chaque nœud
    def compte(n):
        if n not in largeur:
            largeur[n] = 1 if not enf[n] else sum(compte(c) for c in enf[n])
        return largeur[n]

    total = sum(compte(r) for r in racines) or 1

    prof = {}
    def marque(n, d):
        prof[n] = d
        for c in enf[n]:
            marque(c, d + 1)
    for r in racines:
        marque(r, 1)

    # rayon de base : assez grand pour que l'anneau le plus chargé respire
    par_niveau = Counter(prof.values())
    R0 = max(1.0, max((c * 0.55) / (2 * math.pi * d) for d, c in par_niveau.items()))

    pos = {}
    def place(n, a0, a1):
        a = (a0 + a1) / 2
        r = R0 * prof[n]
        pos[n] = (r * math.cos(a), r * math.sin(a))
        curseur = a0
        for c in enf[n]:
            w = (a1 - a0) * largeur[c] / largeur[n]
            place(c, curseur, curseur + w)
            curseur += w

    curseur = 0.0
    for r0 in racines:
        w = 2 * math.pi * largeur[r0] / total
        place(r0, curseur, curseur + w)
        curseur += w
    return pos


def _figure_apercu(racines):
    """Vue d'ensemble : le SQUELETTE CONNECTÉ des arbres retenus  racines,
    grands-parents et parents, avec leurs arêtes. Les feuilles apparaissent au
    zoom. Layout radial de forêt, taille = détections agrégées."""
    keep = _squelette(racines)
    pos = _layout_foret(keep)

    ex, ey = [], []
    for n in keep:
        p = parent_de.get(n)
        if p in keep:
            ex += [pos[n][0], pos[p][0], None]
            ey += [pos[n][1], pos[p][1], None]
    traces = [go.Scatter(x=ex, y=ey, mode="lines",
                         line=dict(width=1, color="#d1d5db"),
                         hoverinfo="none", showlegend=False)]

    ordre = list(keep)
    seuil = sorted((_rec(n) for n in ordre), reverse=True)[:22][-1] if len(ordre) > 22 else 0
    for typ in ORDRE_TYPE:
        ns = [n for n in ordre if _type(n) == typ]
        if not ns:
            continue
        traces.append(go.Scatter(
            x=[pos[n][0] for n in ns], y=[pos[n][1] for n in ns],
            mode="markers+text",
            text=[(n[:24] + "…" if len(n) > 24 else n) if _rec(n) >= seuil else "" for n in ns],
            # label placé vers l'extérieur du cercle : évite de croiser le graphe
            textposition=["middle left" if pos[n][0] < 0 else "middle right" for n in ns],
            textfont=dict(size=9, color="#334155"),
            name=typ,
            hovertext=[f"{n}<br>{_type(n)} · {_rec(n)} détections" for n in ns],
            hoverinfo="text",
            marker=dict(size=[8 + min(round(_rec(n) ** 0.5) * 2, 30) for n in ns],
                        color=COULEUR[typ], line=dict(width=1, color="#ffffff")),
        ))
    fig = go.Figure(traces)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", xanchor="right", x=1, yanchor="bottom", y=0,
                    bgcolor="rgba(255,255,255,0.75)", bordercolor="#e5e7eb", borderwidth=1),
        xaxis=dict(visible=False),
        # 1:1  sans ça le radial est écrasé en ellipse
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=620,
    )
    return fig


def _description(nom):
    """Bloc gauche : identité + description, identique quel que soit le type."""
    t = by_name[nom]
    sous = f"{len(enfants[nom])} sous-thèmes" if enfants[nom] else "aucun sous-thème (feuille)"
    return (
        f"### {nom}\n"
        f"**Type** : {_type(nom)} · **Parent** : {t['parent'] or '(racine)'} · {sous}\n\n"
        f"**Détections** : {_rec(nom)} au total · {own.get(nom, 0)} sur ce topic\n\n"
        f"{t['description']}"
    )


def _occurrences(nom):
    """Bloc droit : où ce topic apparaît dans les textes citoyens."""
    lignes = []
    for doc_id, rationale, extract in occ.get(nom, [])[:8]:
        literal = extract[:40] in content.get(doc_id, "")
        cite = f"« {extract.strip()} »" if literal else f"*(reformulé)* {extract.strip()}"
        lignes.append(f"> {cite}\n>\n>  doc {doc_id} · {rationale}")
    corps = "\n\n".join(lignes) if lignes else (
        "*Ce thème regroupe des sous-thèmes ; les occurrences sont sur les topics feuilles.*"
        if enfants[nom] else "*Aucune occurrence sur ce topic.*"
    )
    return f"#### Occurrences dans les textes\n{corps}"


#  interface
ROOTS = [root for _, root in arbres]        # racines d'arbres, triées par détections
APERCU = "Vue d'ensemble"                   # sentinel : squelette des arbres retenus

# filtre Profondeur : le défaut n'expose que les arbres COMPLETS (les 4 niveaux
# présents)  la cascade tient alors sa promesse, aucun dropdown vide
PROF_CHOIX = ["Arbres complets (4 niveaux)", "Arbres ≥ 3 niveaux", "Tous les arbres"]
PROF_MIN = {PROF_CHOIX[0]: 3, PROF_CHOIX[1]: 2, PROF_CHOIX[2]: 0}


def roots_for(filtre):
    return [r for r in ROOTS if _hauteur(r) >= PROF_MIN.get(filtre, 3)]


def _kids(n):
    return sorted(enfants[n], key=_rec, reverse=True)


def _apercu_md(filtre):
    rs = roots_for(filtre)
    dets = sum(_rec(r) for r in rs)
    return (
        f"### Vue d'ensemble {filtre.lower()}\n"
        f"**{len(rs)} arbres · {dets} détections** ({round(100 * dets / TOTAL_INST)} % du total) · "
        f"{len(docs)} documents analysés sur {len(df)}\n\n"
        f"Le graphe montre le **squelette** (racines, grands-parents, parents reliés) ; "
        f"les topics feuilles apparaissent au zoom. **Taille** = détections agrégées, "
        f"**couleur** = type.\n\n"
        f"*Arbre complet = les 4 niveaux racine → grand-parent → parent → enfant. "
        f"Les arbres moins profonds restent accessibles via le filtre Profondeur.*\n\n"
        f"Sélectionne une racine pour explorer son arbre."
    )


def _vue_ensemble(filtre):
    return (
        _figure_apercu(roots_for(filtre)),
        gr.update(choices=[], value=None, label="Grand-parent"),
        gr.update(choices=[], value=None, label="Parent"),
        gr.update(choices=[], value=None, label="Enfant · topic"),
        _apercu_md(filtre), "", None,
    )


def on_prof(filtre):
    """Changement de profondeur : liste Racine refiltrée + retour à l'ensemble."""
    return (
        gr.update(choices=[APERCU] + roots_for(filtre), value=APERCU),
        *_vue_ensemble(filtre),
    )


def on_racine(root, filtre):
    if not root or root == APERCU:
        return _vue_ensemble(filtre)
    return (
        _figure(root),
        gr.update(choices=_kids(root), value=None, label="Grand-parent"),
        gr.update(choices=[], value=None, label="Parent"),
        gr.update(choices=[], value=None, label="Enfant · topic"),
        _description(root), _occurrences(root), root,
    )


def on_gp(node, focus):
    if not node: # reset programmatique : on ne touche à rien
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


with gr.Blocks(title="Doléances  thèmes") as demo:
    gr.Markdown("# Cahiers de doléances vue topic (POC)")
    focus_state = gr.State()

    # filtre Profondeur + sélection à 4 niveaux, en haut
    with gr.Row():
        prof_dd = gr.Dropdown(PROF_CHOIX, value=PROF_CHOIX[0], label="Profondeur",
                              filterable=False, scale=1)
        racine_dd = gr.Dropdown([APERCU] + roots_for(PROF_CHOIX[0]), value=APERCU,
                                label="Racine · arbre", filterable=True, scale=1)
        gp_dd = gr.Dropdown(label="Grand-parent", filterable=True, scale=1)
        parent_dd = gr.Dropdown(label="Parent", filterable=True, scale=1)
        enfant_dd = gr.Dropdown(label="Enfant · topic", filterable=True, scale=1)

    # graphe à gauche, détails (description + occurrences) à droite
    with gr.Row():
        with gr.Column(scale=2):
            plot = gr.Plot()
        with gr.Column(scale=1):
            description = gr.Markdown()
            occurrences = gr.Markdown()

    prof_dd.change(on_prof, prof_dd,
                   [racine_dd, plot, gp_dd, parent_dd, enfant_dd,
                    description, occurrences, focus_state])
    racine_dd.change(on_racine, [racine_dd, prof_dd],
                     [plot, gp_dd, parent_dd, enfant_dd, description, occurrences, focus_state])
    gp_dd.change(on_gp, [gp_dd, focus_state],
                 [plot, parent_dd, enfant_dd, description, occurrences, focus_state])
    parent_dd.change(on_parent, [parent_dd, focus_state],
                     [plot, enfant_dd, description, occurrences, focus_state])
    enfant_dd.change(on_enfant, [enfant_dd, focus_state],
                     [plot, description, occurrences, focus_state])
    demo.load(on_prof, prof_dd,
              [racine_dd, plot, gp_dd, parent_dd, enfant_dd,
               description, occurrences, focus_state])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
