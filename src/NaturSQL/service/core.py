"""Public business-logic entry points."""

from ..storage.base import Storage

def health_check() -> bool:
    """Return whether the application service is available."""
    storage = Storage()
    return storage.health_check()

def get_user_profile(email: str = None) -> dict:
    """
    Récupère le profil d'un utilisateur.
    Si aucun email n'est fourni, récupère le premier utilisateur de la base pour la démonstration.
    """
    storage = Storage()
    
    if email:
        user = storage.get_user_by_email(email)
    else:
        user = storage.get_first_user()
    
    if user:
        return {
            "success": True, 
            "user": {
                "first_name": user.get('prenom_ens', ''),
                "last_name": user.get('nom_ens', ''),
                "email": user.get('mail_ens', '')
            }
        }
    else:
        return {"success": False, "message": "Utilisateur introuvable."}
