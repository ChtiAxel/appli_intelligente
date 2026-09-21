"""Gradio application entry point."""

import os
import base64
import gradio as gr
from .service.core import get_user_profile

# Load logo as base64 for embedding in HTML
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
try:
    with open(logo_path, "rb") as f:
        b64_logo = base64.b64encode(f.read()).decode("utf-8")
    logo_html = f'<div style="display: flex; align-items: center; gap: 10px;"><img src="data:image/png;base64,{b64_logo}" style="height: 32px;" /> <h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2></div>'
except Exception:
    b64_logo = ""
    logo_html = '<h2 style="margin:0; font-weight:600; color:black;">NaturSQL</h2>'

# Script to remove dark mode forcefully from Gradio
force_light_mode_js = """
function() {
    document.body.classList.remove('dark');
}
"""

custom_css = """
html, body {
    margin: 0 !important;
    padding: 0 !important;
    background-color: #f8f9fa !important;
    min-height: 100vh;
}
.gradio-container {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}
.gradio-container > .main, .gradio-container > .main > .wrap {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
}
.header {
    background: white;
    padding-top: 2.5rem !important;
    padding-bottom: 1.5rem !important;
    padding-left: 2rem;
    padding-right: 2rem;
    border-bottom: 1px solid #e5e7eb;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    margin-top: -1rem !important;
    box-sizing: border-box;
    margin-bottom: 3rem !important;
}
.main-content {
    min-height: calc(100vh - 320px); 
}
.profile-card {
    background: white;
    padding: 2.5rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    margin: 0 auto;
    max-width: 500px;
}
.footer {
    background: white;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem;
    padding-right: 2rem;
    border-top: 1px solid #e5e7eb;
    width: 100vw;
    margin-left: calc(-50vw + 50%) !important;
    margin-bottom: -1rem !important; 
    margin-top: auto !important;
    box-sizing: border-box;
}
footer.svelte-17lrt0r, footer.svelte-1rjryqp, footer {
    display: none !important;
}
"""

theme = gr.themes.Default(
    primary_hue="gray",
    neutral_hue="slate",
).set(
    body_background_fill="#f8f9fa",
    block_background_fill="#ffffff",
    block_border_color="#e5e7eb",
    block_border_width="1px",
    block_shadow="none",
    button_primary_background_fill="#374151",
    button_primary_background_fill_hover="#1f2937",
    button_primary_text_color="#ffffff",
    button_cancel_background_fill="#ef4444",
    button_cancel_background_fill_hover="#dc2626",
    button_cancel_text_color="#ffffff",
    color_accent_soft="#f3f4f6",
)

def load_profile():
    """Charge le profil par défaut à l'ouverture de la page."""
    result = get_user_profile()
    if result["success"]:
        user = result["user"]
        return f"**{user['first_name']} {user['last_name']}**\n\nEmail : {user['email']}"
    else:
        return "**Erreur**\n\nImpossible de charger le profil."

def build_app():
    with gr.Blocks(theme=theme, css=custom_css, js=force_light_mode_js, title="NaturSQL Profile") as demo:
        
        # En-tête (Header)
        with gr.Column(elem_classes=["header"]):
            gr.HTML(logo_html)
            
        # Contenu principal (Profil)
        with gr.Column(elem_classes=["main-content"]):
            
            with gr.Column(elem_classes=["profile-card"]):
                with gr.Row():
                    gr.HTML('<img src="https://ui-avatars.com/api/?name=User&background=random" style="border-radius: 50%; width: 80px; height: 80px;" />')
                    profile_info = gr.Markdown("Chargement du profil...")
                
                disconnect_btn = gr.Button("Disconnect", variant="stop")
        
        # Pied de page (Footer)
        with gr.Column(elem_classes=["footer"]):
            footer_logo = f'<img src="data:image/png;base64,{b64_logo}" style="height: 48px; margin-right: 4rem;" />' if b64_logo else ""
                
            gr.HTML(f"""
            <div style='display: flex; align-items: flex-start; padding-left: 2rem;'>
                <div>
                    {footer_logo}
                </div>
                <div style='line-height: 1.8; color: #1f2937;'>
                    <strong>Legal</strong><br>
                    Legal Notice<br>
                    Privacy Policy<br>
                    Cookie management<br>
                    General Terms of Use
                </div>
            </div>
            """)

        # Chargement des données du profil au lancement
        demo.load(
            fn=load_profile,
            inputs=[],
            outputs=[profile_info]
        )
        
    return demo

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860, share=False)
