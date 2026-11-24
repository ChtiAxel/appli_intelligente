"""Bouton « œil » : afficher / masquer le mot de passe sur tous les champs mot de passe."""

from __future__ import annotations

import re
from pathlib import Path

from NaturSQL import ui_gradio


def test_script_adds_an_eye_button_to_every_password_input():
    js = ui_gradio.force_light_mode_js
    assert 'input[type="password"]' in js
    assert "nsql-eye-btn" in js and "MutationObserver" in js  # champs affichés plus tard (inscription, profil)
    assert "Afficher le mot de passe" in js and "Masquer le mot de passe" in js
    assert "input.type = show ? 'text' : 'password'" in js


def test_eye_is_crossed_while_the_password_is_hidden():
    js = ui_gradio.force_light_mode_js
    # L'œil barré (trait diagonal) est dessiné par défaut ; l'œil ouvert après le clic.
    assert 'paintEye(button, false)' in js
    assert 'button.innerHTML = visible ? EYE_OPEN : EYE_CROSSED' in js
    assert '<line x1="1" y1="1" x2="23" y2="23"/>' in js  # le trait qui barre l'œil


def test_button_never_submits_a_form_nor_steals_the_focus():
    js = ui_gradio.force_light_mode_js
    assert "button.type = 'button'" in js
    assert "mousedown" in js and "preventDefault" in js


def test_eye_is_drawn_above_the_input():
    css = ui_gradio.custom_css
    assert ".nsql-eye-btn" in css
    assert re.search(r"\.nsql-eye-btn \{[^}]*z-index: 5", css)  # le champ Gradio a z-index: 1
    assert "padding-right: 44px" in css  # le texte ne passe pas sous l'icône


def test_all_password_fields_of_the_app_are_plain_password_textboxes():
    """Le script cible input[type=password] : aucun champ mot de passe ne doit y échapper."""
    source = Path(ui_gradio.__file__).read_text(encoding="utf-8")
    password_fields = re.findall(r'gr\.Textbox\([^)]*?type="password"', source, flags=re.S)
    assert len(password_fields) >= 7  # connexion, inscription x2, changement x3, suppression
    assert "type='password'" not in source.replace("input.type = show ? 'text' : 'password'", "")
