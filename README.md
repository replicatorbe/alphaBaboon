# 🐒 AlphaBaboon - Bot de Modération IRC

**Bot de modération automatique 100% autonome** pour la communauté Baboon qui surveille le canal #francophonie sur irc.baboon.fr. 

## 🎯 Qu'est-ce que ce bot ?

AlphaBaboon est un **modérateur IRC intelligent** qui :

✨ **Analyse automatiquement** tous les messages sur #francophonie  
🔍 **Détecte le contenu adulte/sexuel** avec l'IA d'OpenAI  
🚀 **Déplace poliment** les utilisateurs vers #adultes  
🆓 **Coût zéro** grâce à l'API Moderation gratuite d'OpenAI  
⚡ **Performance optimale** avec cache intelligent et détection rapide  

### 🎭 Comment ça marche ?

1. **Surveillance** : Le bot écoute tous les messages sur #francophonie
2. **Analyse IA** : Chaque message est analysé pour détecter du contenu adulte
3. **Action sympathique** : Si détecté → message d'explication + déplacement vers #adultes
4. **Accueil** : Message d'accueil personnalisé sur #adultes selon l'heure

### 💡 Pourquoi AlphaBaboon ?

- **🛡️ Protection** : Garde #francophonie familial et accueillant
- **😊 Bienveillant** : Messages toujours sympathiques et accueillants  
- **🔄 Intelligent** : Apprend des messages répétitifs (cache)
- **👥 Respectueux** : Whitelist pour les admins/modérateurs
- **📊 Transparent** : Logs détaillés de toutes les actions

---

## ⚡ Démarrage rapide

**Pressé ?** → Voir le **[Guide de démarrage en 3 minutes](QUICKSTART.md)** 🚀

---

## 🚀 Installation

### Prérequis
- Python 3.8+
- Clé API OpenAI
- Accès au serveur IRC irc.baboon.fr

### Installation des dépendances
```bash
pip install -r requirements.txt
```

### Configuration

1. **Créer le fichier de configuration secrète**
   
   Copiez le fichier d'exemple et configurez vos données sensibles :
   ```bash
   cp config_secret.json.example config_secret.json
   ```
   
   Éditez `config_secret.json` avec vos vraies informations :
   ```json
   {
     "irc": {
       "ircop_login": "votre_login_ircop",
       "ircop_password": "votre_password_ircop",
       "channels": ["#francophonie", "#adultes"],
       "monitored_channel": "#francophonie",
       "redirect_channel": "#adultes",
       "is_ircop": true,
       "preferred_server_index": 0
     },
     "openai": {
       "api_key": "sk-votre-vraie-cle-api-openai"
     }
   }
   ```

2. **Configuration des serveurs IRC** (optionnel)
   
   Dans `config.json`, vous pouvez modifier les serveurs :
   ```json
   {
     "irc": {
       "servers": [
         {
           "hostname": "irc.baboon.fr",
           "port": 6667,
           "ssl": false
         },
         {
           "hostname": "irc.baboon.fr", 
           "port": 6697,
           "ssl": true
         }
       ],
       "connect_timeout": 30,
       "retry_delay": 60
     }
   }
   ```

3. **Personnaliser les canaux** (optionnel)
   
   Dans `config_secret.json`, vous pouvez modifier :
   - `monitored_channel` : canal à surveiller (défaut: "#francophonie")
   - `redirect_channel` : canal de redirection (défaut: "#adultes")
   - `channels` : liste des canaux à rejoindre
   - `preferred_server_index` : serveur préféré (0 = premier de la liste)

4. **Ajuster les paramètres de modération** (optionnel)
   
   Dans `config.json` :
   ```json
   {
     "moderation": {
       "sensitivity": 7,                // Score seuil 0-10 (7 = assez strict)
       "reset_hours": 24,               // Reset du compteur après 24h
       "cooldown_minutes": 2,           // Cooldown entre actions de modération
       "move_delay_seconds": 3,         // Délai avant déplacement
       "welcome_delay_seconds": 5,      // Délai avant message d'accueil
       "cache_hours": 24,               // Durée du cache (économies)
       "cache_size": 1000,              // Taille max du cache
       "trusted_users": ["admin1", "mod2"]  // Whitelist (à configurer)
     }
   }
   ```

5. **Configuration du monitoring** (optionnel)
   
   Dans `config.json` :
   ```json
   {
     "healthcheck": {
       "interval_minutes": 5,           // Fréquence des vérifications
       "openai_timeout_seconds": 10,    // Timeout tests OpenAI
       "max_failures": 3                // Seuil avant alerte
     }
   }
   ```

## 🚀 Comment lancer le bot

### **Méthode 1 : Démarrage simple**
```bash
# Dans le dossier alphaBaboon
python alphababoon.py
```

### **Méthode 2 : Avec configuration personnalisée**
```bash
python alphababoon.py config_perso.json config_secret_perso.json
```

### **Méthode 3 : En arrière-plan (production)**
```bash
# Lancer en arrière-plan
nohup python alphababoon.py > bot.log 2>&1 &

# Voir les logs en temps réel
tail -f bot.log

# Arrêter le bot
pkill -f alphababoon.py
```

### **Méthode 4 : Avec systemd (recommandé pour serveur)**

Créer le fichier `/etc/systemd/system/alphababoon.service` :
```ini
[Unit]
Description=AlphaBaboon IRC Bot
After=network.target

[Service]
Type=simple
User=votre_user
WorkingDirectory=/chemin/vers/alphaBaboon
ExecStart=/usr/bin/python3 alphababoon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Puis :
```bash
sudo systemctl daemon-reload
sudo systemctl enable alphababoon
sudo systemctl start alphababoon
sudo systemctl status alphababoon
```

### **🛑 Arrêt propre**
- `Ctrl+C` pour un arrêt propre en mode interactif
- `sudo systemctl stop alphababoon` avec systemd
- Le bot sauvegarde son état et ferme les connexions correctement

### **📊 Surveillance**
```bash
# Voir les logs principaux
tail -f logs/alphababoon.log

# Voir les actions de modération  
tail -f logs/moderation.log

# Voir les erreurs
tail -f logs/errors.log

# Statistiques IRC
tail -f logs/irc_stats.log
```

## 🔧 Fonctionnalités

### 🚀 **Quick Wins Implémentés**

✅ **API Moderation d'OpenAI** - **100% GRATUITE** au lieu de Chat API payante !  
✅ **Cache OpenAI intelligent** - Économise les requêtes répétées  
✅ **Whitelist utilisateurs de confiance** - Admins/modos exemptés  
✅ **Détection mots-clés rapide** - Analyse instantanée avant OpenAI  
✅ **Healthcheck automatique** - Monitoring IRC/OpenAI en continu  
✅ **Messages dynamiques** - Rotation anti-répétition + messages horaires  
✅ **Statistiques temps réel** - Cache, économies, santé des services  

### Système de déplacement automatique et accueillant

Le bot utilise ses **privilèges IRCop** pour un nettoyage efficace et sympathique :

1. **Détection intelligente multi-niveaux** :
   - **Whitelist** : Utilisateurs de confiance ignorés
   - **Cache** : Messages déjà analysés (économie requêtes)
   - **Mots-clés** : Détection instantanée (français optimisé)
   - **OpenAI Moderation API** : Analyse contextuelle **GRATUITE** !

2. **Déplacement bienveillant** :
   - Messages variés selon l'heure de la journée
   - **SAJOIN** automatique vers le canal de redirection
   - **KICK** sympathique du canal surveillé

3. **Accueil personnalisé** (après 5 secondes) :
   - Messages d'accueil contextuels (matin/soir/nuit)
   - Ton toujours accueillant pour maintenir l'esprit communautaire

### Reset automatique
- Compteur remis à zéro après 24h sans incident
- Permet une seconde chance aux utilisateurs

### Analyse intelligente
- Utilise l'API OpenAI pour analyser le contexte français
- Évite les faux positifs sur les discussions médicales/culturelles
- Score de confiance configurable

## 📊 Logs et Surveillance

### Fichiers de logs créés automatiquement :
- `logs/alphababoon.log` - Log principal avec rotation
- `logs/errors.log` - Erreurs uniquement  
- `logs/moderation.log` - Actions de modération
- `logs/irc_stats.log` - Statistiques IRC

### Monitoring en temps réel
```bash
# Surveiller les actions de modération
tail -f logs/moderation.log

# Surveiller les erreurs
tail -f logs/errors.log

# Voir les statistiques
tail -f logs/irc_stats.log
```

## 🛡️ Sécurité et Éthique

- **Défensif uniquement** : Le bot protège la communauté, ne nuit pas
- **Logging complet** : Toutes les actions sont tracées
- **Transparence** : Messages publics, pas d'actions cachées  
- **Respect de la vie privée** : Pas de stockage permanent des messages
- **API OpenAI** : Analyse contextuelle respectueuse

## 🐛 Dépannage

### Bot ne se connecte pas
```bash
# Vérifier la configuration IRC
ping irc.baboon.fr

# Vérifier les logs
tail -f logs/alphababoon.log
```

### Erreurs OpenAI
- Vérifier que la clé API est valide
- Vérifier les quotas/limites de l'API OpenAI
- Voir `logs/errors.log` pour plus de détails

### Problèmes de permissions IRC
- Le bot a besoin des **privilèges IRCop** pour utiliser SAJOIN
- Contacter les administrateurs pour les permissions IRCop
- Vérifier que `"is_ircop": true` dans config.json

## 📋 Structure du Projet

```
alphaBaboon/
├── config.json                    # Configuration publique (à versionner)
├── config_secret.json             # Configuration secrète (non versionnée)
├── config_secret.json.example     # Modèle de configuration secrète
├── requirements.txt               # Dépendances Python
├── alphababoon.py                # Script principal
├── irc_client.py                 # Client IRC avec reconnexion
├── content_analyzer.py           # Analyse OpenAI du contenu
├── moderation_handler.py         # Système de sanctions
├── logger_config.py              # Configuration des logs
├── .gitignore                    # Fichiers exclus du versioning
├── logs/                         # Dossier des logs (créé auto)
└── README.md                     # Documentation
```

## 🔒 Sécurité des Données

- **config.json** : Configuration publique, safe pour GitHub
- **config_secret.json** : Données sensibles, **JAMAIS** sur GitHub  
- **config_secret.json.example** : Modèle pour la configuration secrète
- **.gitignore** : Protège automatiquement les fichiers sensibles

## 📈 Performances et Limites

- **Rate limiting** : 10 requêtes OpenAI par seconde (API Moderation plus rapide)
- **Cooldown** : 2 minutes entre actions de modération par utilisateur
- **Mémoire** : Faible usage, stockage temporaire uniquement
- **Réseau** : Reconnexion automatique IRC
- **Coût** : **0.00$ par message** (API Moderation gratuite !)

## 🤝 Support

Pour les problèmes techniques :
1. Vérifier les logs dans `logs/`
2. S'assurer que la configuration est correcte
3. Tester la connectivité IRC et OpenAI
4. Contacter l'équipe Baboon si problème persistant

---

**AlphaBaboon v1.0** - Bot de modération automatique pour la communauté Baboon 🐒