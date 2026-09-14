"""Gradio application entry point."""


def build_app():
    """Build the UI when Gradio is installed."""
    import gradio as gr

    return gr.Interface(
        fn=lambda prompt: prompt,
        inputs=gr.Textbox(label="Prompt"),
        outputs=gr.Textbox(label="Réponse"),
        title="NaturSQL",
    )


if __name__ == "__main__":
    build_app().launch()
