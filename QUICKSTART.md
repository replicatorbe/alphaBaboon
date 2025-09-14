# 🚀 Guide de Démarrage Rapide - AlphaBaboon

## ⚡ Lancement en 3 minutes

### 1. **Installation des dépendances**
```bash
cd alphaBaboon
pip install -r requirements.txt
```

### 2. **Configuration de base**
```bash
# Copier le fichier exemple
cp config_secret.json.example config_secret.json

# Éditer avec vos informations
nano config_secret.json
```

**Minimum requis dans `config_secret.json` :**
```json
{
  "openai": {
    "api_key": "sk-votre-vraie-cle-api-openai"
  },
  "irc": {
    "ircop_login": "votre_login_ircop",
    "ircop_password": "votre_password_ircop"
  }
}
```

### 3. **Lancer le bot** 
```bash
python alphababoon.py
```

**✅ C'est tout !** Le bot démarre et se connecte automatiquement.

---

## 🔧 Configuration rapide

### **Pour changer les canaux :**
```json
"irc": {
  "monitored_channel": "#votre-canal-surveille",
  "redirect_channel": "#votre-canal-adultes",
  "channels": ["#canal1", "#canal2"]
}
```

### **Pour ajouter des utilisateurs de confiance :**
```json
"moderation": {
  "trusted_users": ["admin1", "modo2", "votre_nick"]
}
```

### **Pour ajuster la sensibilité :**
```json
"moderation": {
  "sensitivity": 6  // Plus bas = moins strict (1-10)
}
```

---

## 📊 Vérification que ça marche

### **Logs de démarrage :**
```
AlphaBaboon Bot - Démarrage
Serveur principal: irc.baboon.fr:6667 (non-SSL)
Canaux rejoints: #francophonie, #adultes
Mode IRCop: Activé
Monitoring de santé démarré
```

### **Test rapide :**
1. Le bot rejoint #francophonie et #adultes ✅
2. Écrivez un message test avec contenu adulte sur #francophonie
3. Le bot doit vous déplacer vers #adultes avec un message sympa
4. Vérifiez les logs : `tail -f logs/alphababoon.log`

---

## ❌ Problèmes courants

**Bot ne se connecte pas :**
- Vérifier `ircop_login` et `ircop_password`
- Vérifier que le serveur IRC est accessible

**Erreur OpenAI :**
- Vérifier que la clé API est valide et active
- Vérifier que vous avez des crédits (l'API Moderation est gratuite)

**Bot ne modère pas :**
- Vérifier que le bot a les privilèges IRCop sur le serveur
- Vérifier que `is_ircop: true` dans la config

---

## 🆘 Support rapide

```bash
# Voir toutes les erreurs
tail -f logs/errors.log

# Voir les actions de modération
tail -f logs/moderation.log

# Redémarrer le bot
Ctrl+C puis python alphababoon.py
```

**Pour plus d'aide :** Voir le README.md complet 📖