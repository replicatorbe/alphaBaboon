#!/bin/bash
#
# Script de gestion du bot AlphaBaboon
# Usage: ./start.sh {start|stop|restart|status}
#

BOT_DIR="/home/jerome/alphaBaboon"
BOT_SCRIPT="alphababoon.py"
PID_FILE="$BOT_DIR/alphababoon.pid"
LOG_FILE="$BOT_DIR/logs/alphababoon.log"

cd "$BOT_DIR" || exit 1

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        echo ""
    fi
}

is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

start_bot() {
    if is_running; then
        echo "AlphaBaboon est déjà en cours d'exécution (PID: $(get_pid))"
        return 1
    fi

    echo "Démarrage d'AlphaBaboon..."

    # Créer le dossier logs si nécessaire
    mkdir -p "$BOT_DIR/logs"

    # Lancer le bot en arrière-plan avec nohup
    nohup python3 "$BOT_DIR/$BOT_SCRIPT" >> "$LOG_FILE" 2>&1 &
    local pid=$!

    # Sauvegarder le PID
    echo "$pid" > "$PID_FILE"

    # Attendre un peu et vérifier que le processus tourne
    sleep 2
    if is_running; then
        echo "AlphaBaboon démarré avec succès (PID: $pid)"
        return 0
    else
        echo "Erreur: AlphaBaboon n'a pas pu démarrer. Consultez les logs:"
        echo "  tail -f $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_bot() {
    if ! is_running; then
        echo "AlphaBaboon n'est pas en cours d'exécution"
        rm -f "$PID_FILE"
        return 0
    fi

    local pid=$(get_pid)
    echo "Arrêt d'AlphaBaboon (PID: $pid)..."

    # Envoyer SIGTERM pour un arrêt propre
    kill -TERM "$pid" 2>/dev/null

    # Attendre l'arrêt (max 10 secondes)
    local count=0
    while is_running && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo ""

    if is_running; then
        echo "Le bot ne répond pas, envoi de SIGKILL..."
        kill -KILL "$pid" 2>/dev/null
        sleep 1
    fi

    rm -f "$PID_FILE"
    echo "AlphaBaboon arrêté"
    return 0
}

restart_bot() {
    echo "Redémarrage d'AlphaBaboon..."
    stop_bot
    sleep 1
    start_bot
}

status_bot() {
    if is_running; then
        local pid=$(get_pid)
        echo "AlphaBaboon est en cours d'exécution (PID: $pid)"
        echo ""
        echo "Infos processus:"
        ps -p "$pid" -o pid,ppid,user,%cpu,%mem,etime,cmd --no-headers 2>/dev/null
        echo ""
        echo "Dernières lignes du log:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "(pas de logs disponibles)"
    else
        echo "AlphaBaboon n'est pas en cours d'exécution"
        if [ -f "$PID_FILE" ]; then
            echo "(fichier PID obsolète supprimé)"
            rm -f "$PID_FILE"
        fi
    fi
}

show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "Aucun fichier de log trouvé: $LOG_FILE"
    fi
}

# Menu principal
case "$1" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "  start   - Démarre le bot en arrière-plan"
        echo "  stop    - Arrête le bot proprement"
        echo "  restart - Redémarre le bot"
        echo "  status  - Affiche l'état du bot"
        echo "  logs    - Affiche les logs en temps réel (Ctrl+C pour quitter)"
        exit 1
        ;;
esac

exit $?
