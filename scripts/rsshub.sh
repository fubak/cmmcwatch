#!/bin/bash
# RSSHub management script - simplified Docker commands

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

COMMAND="${1:-status}"

case "$COMMAND" in
  start)
    echo "🚀 Starting RSSHub..."
    docker-compose up -d rsshub
    echo "✅ RSSHub started at http://localhost:1200"
    echo "   Test it: curl http://localhost:1200/healthz"
    ;;

  stop)
    echo "⏸️  Stopping RSSHub..."
    docker-compose stop rsshub
    echo "✅ RSSHub stopped"
    ;;

  restart)
    echo "🔄 Restarting RSSHub..."
    docker-compose restart rsshub
    echo "✅ RSSHub restarted"
    ;;

  logs)
    echo "📋 RSSHub logs (Ctrl+C to exit):"
    docker-compose logs -f rsshub
    ;;

  status)
    echo "📊 RSSHub Status:"
    if docker-compose ps rsshub | grep -q "Up"; then
      echo "✅ RSSHub is running"
      echo "   URL: http://localhost:1200"
      
      # Test health endpoint
      if curl -sf http://localhost:1200/healthz > /dev/null 2>&1; then
        echo "   Health: ✅ OK"
      else
        echo "   Health: ⚠️  Not responding (may still be starting)"
      fi
    else
      echo "❌ RSSHub is not running"
      echo "   Start it: ./scripts/rsshub.sh start"
    fi
    ;;

  test)
    echo "🧪 Testing RSSHub connection..."
    
    # Check if running
    if ! docker-compose ps rsshub | grep -q "Up"; then
      echo "❌ RSSHub is not running"
      echo "   Start it: ./scripts/rsshub.sh start"
      exit 1
    fi
    
    # Test health endpoint
    echo "Testing health endpoint..."
    if curl -sf http://localhost:1200/healthz > /dev/null 2>&1; then
      echo "✅ Health check: OK"
    else
      echo "❌ Health check: Failed"
      exit 1
    fi
    
    # Test LinkedIn feed
    echo "Testing LinkedIn feed..."
    FEED_URL="http://localhost:1200/linkedin/in/katie-arrington-a6949425"
    if curl -sf "$FEED_URL" | grep -q "<rss"; then
      echo "✅ LinkedIn feed: OK"
      echo ""
      echo "🎉 RSSHub is working! You can now fetch LinkedIn posts."
      echo ""
      echo "Try: python3 scripts/rsshub_fetch.py --test"
    else
      echo "❌ LinkedIn feed: Failed"
      echo "   This might be a temporary LinkedIn block."
      exit 1
    fi
    ;;

  update)
    echo "🔄 Updating RSSHub to latest version..."
    docker-compose pull rsshub
    docker-compose up -d rsshub
    echo "✅ RSSHub updated and restarted"
    ;;

  clean)
    echo "🧹 Removing RSSHub container (keeps image)..."
    docker-compose down rsshub
    echo "✅ RSSHub container removed"
    ;;

  *)
    echo "RSSHub Management Script"
    echo ""
    echo "Usage: ./scripts/rsshub.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start RSSHub"
    echo "  stop     - Stop RSSHub"
    echo "  restart  - Restart RSSHub"
    echo "  status   - Check if RSSHub is running (default)"
    echo "  logs     - View RSSHub logs"
    echo "  test     - Test RSSHub connection and LinkedIn feed"
    echo "  update   - Update RSSHub to latest version"
    echo "  clean    - Remove RSSHub container"
    echo ""
    echo "Examples:"
    echo "  ./scripts/rsshub.sh start"
    echo "  ./scripts/rsshub.sh test"
    echo "  ./scripts/rsshub.sh logs"
    ;;
esac
