#!/bin/bash

# Script de supervision pour AlphaBaboon - Redémarrage automatique
# Usage: ./supervise_bot.sh

BOT_SCRIPT="alphababoon.py"
LOG_FILE="supervision.log"
RESTART_DELAY=30
MAX_RESTARTS_PER_HOUR=10

# Compteurs
RESTART_COUNT=0
HOUR_START=$(date +%s)

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

cleanup() {
    log_message "Signal d'arrêt reçu, arrêt de la supervision..."
    if [ ! -z "$BOT_PID" ]; then
        kill $BOT_PID 2>/dev/null
    fi
    exit 0
}

# Gestion des signaux
trap cleanup SIGINT SIGTERM

log_message "=== Démarrage de la supervision AlphaBaboon ==="
log_message "Script bot: $BOT_SCRIPT"
log_message "Délai de redémarrage: ${RESTART_DELAY}s"
log_message "Limite: $MAX_RESTARTS_PER_HOUR redémarrages/heure"

while true; do
    # Vérifier si on doit réinitialiser le compteur horaire
    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - HOUR_START)) -gt 3600 ]; then
        RESTART_COUNT=0
        HOUR_START=$CURRENT_TIME
        log_message "Compteur horaire réinitialisé"
    fi
    
    # Vérifier la limite de redémarrages
    if [ $RESTART_COUNT -ge $MAX_RESTARTS_PER_HOUR ]; then
        log_message "ALERTE: Limite de redémarrages atteinte ($RESTART_COUNT/$MAX_RESTARTS_PER_HOUR)"
        log_message "Attente d'une heure avant nouveau redémarrage..."
        sleep 3600
        RESTART_COUNT=0
        HOUR_START=$(date +%s)
    fi
    
    log_message "Démarrage du bot AlphaBaboon..."
    
    # Démarrer le bot
    python3 "$BOT_SCRIPT" &
    BOT_PID=$!
    
    log_message "Bot démarré avec PID: $BOT_PID"
    
    # Attendre que le processus se termine
    wait $BOT_PID
    EXIT_CODE=$?
    
    log_message "Bot arrêté (code de sortie: $EXIT_CODE)"
    
    # Analyser le code de sortie
    case $EXIT_CODE in
        0)
            log_message "Arrêt normal du bot"
            break
            ;;
        130)
            log_message "Interruption par signal (Ctrl+C)"
            break
            ;;
        *)
            RESTART_COUNT=$((RESTART_COUNT + 1))
            log_message "Crash détecté! Redémarrage #$RESTART_COUNT dans ${RESTART_DELAY}s..."
            sleep $RESTART_DELAY
            ;;
    esac
done

log_message "=== Fin de la supervision AlphaBaboon ==="