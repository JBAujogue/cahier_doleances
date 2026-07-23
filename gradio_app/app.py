from pathlib import Path

import gradio as gr
from data_helpers import PDF_DIR
from views import commune, graph, topic

STYLE = Path(__file__).parent / "views" / "style.css"

with gr.Blocks(title="Cahiers de doléances", theme=gr.themes.Soft(),
               css_paths=[STYLE]) as demo:
    gr.Markdown("# Visualisation des contributions")

    with gr.Tab("Par commune"):
        load_fn, load_outputs = commune.render()
    with gr.Tab("Par topic"):
        topic.render()
    with gr.Tab("Graphe"):
        graph.render()

    # l'affichage initial de la vue commune : événement du niveau application
    demo.load(load_fn, None, load_outputs)


if __name__ == "__main__":
    demo.launch(allowed_paths=[str(PDF_DIR)])
