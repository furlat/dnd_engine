#!/bin/bash
# Test script for session-based API
# Run server first: python -m server.event_server --force

set -e
BASE_URL="http://localhost:8000"

echo "=== SESSION API TEST ==="
echo ""

# 1. Start PvP game
echo "1. Starting PvP game..."
START_RESPONSE=$(curl -s -X POST "$BASE_URL/simulation/start-pvp")
echo "Response: $START_RESPONSE"
HERO_UUID=$(echo $START_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('hero_uuid', ''))")
SKELETON_UUID=$(echo $START_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('skeleton_uuid', ''))")
echo "Hero UUID: $HERO_UUID"
echo "Skeleton UUID: $SKELETON_UUID"
echo ""

# 2. Create human session
echo "2. Creating human session..."
HUMAN_SESSION=$(curl -s -X POST "$BASE_URL/session/create" \
  -H "Content-Type: application/json" \
  -d '{"player_type": "human", "name": "Player1"}')
echo "Response: $HUMAN_SESSION"
HUMAN_SESSION_ID=$(echo $HUMAN_SESSION | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', ''))")
echo "Human Session ID: $HUMAN_SESSION_ID"
echo ""

# 3. Create claude session
echo "3. Creating claude session..."
CLAUDE_SESSION=$(curl -s -X POST "$BASE_URL/session/create" \
  -H "Content-Type: application/json" \
  -d '{"player_type": "claude", "name": "ClaudeBot"}')
echo "Response: $CLAUDE_SESSION"
CLAUDE_SESSION_ID=$(echo $CLAUDE_SESSION | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', ''))")
echo "Claude Session ID: $CLAUDE_SESSION_ID"
echo ""

# 4. Join game with human session (auto-assigns Hero)
echo "4. Human joining game..."
JOIN_HUMAN=$(curl -s -X POST "$BASE_URL/game/join" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$HUMAN_SESSION_ID\"}")
echo "Response: $JOIN_HUMAN"
echo ""

# 5. Join game with claude session (auto-assigns Skeleton)
echo "5. Claude joining game..."
JOIN_CLAUDE=$(curl -s -X POST "$BASE_URL/game/join" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$CLAUDE_SESSION_ID\"}")
echo "Response: $JOIN_CLAUDE"
echo ""

# 6. Check game status
echo "6. Checking game status..."
GAME_STATUS=$(curl -s "$BASE_URL/game/status")
echo "Response: $GAME_STATUS"
echo ""

# 7. Ping human session
echo "7. Pinging human session..."
PING_HUMAN=$(curl -s -X POST "$BASE_URL/session/$HUMAN_SESSION_ID/ping")
echo "Response: $PING_HUMAN"
IS_MY_TURN=$(echo $PING_HUMAN | python3 -c "import sys, json; print(json.load(sys.stdin).get('is_my_turn', False))")
echo "Is human's turn: $IS_MY_TURN"
echo ""

# 8. Check current turn
echo "8. Checking current turn..."
TURN_INFO=$(curl -s "$BASE_URL/encounter/current-turn")
echo "Response: $TURN_INFO"
CURRENT_NAME=$(echo $TURN_INFO | python3 -c "import sys, json; print(json.load(sys.stdin).get('current_entity_name', ''))")
echo "Current turn: $CURRENT_NAME"
echo ""

# 9. Try to move (with appropriate session)
echo "9. Testing move action..."
if [ "$CURRENT_NAME" = "Hero" ]; then
  echo "Hero's turn - using human session"
  ACTIVE_SESSION="$HUMAN_SESSION_ID"
  ACTIVE_UUID="$HERO_UUID"
else
  echo "Skeleton's turn - using claude session"
  ACTIVE_SESSION="$CLAUDE_SESSION_ID"
  ACTIVE_UUID="$SKELETON_UUID"
fi

# Get available actions first
echo "Getting available actions for $CURRENT_NAME..."
ACTIONS=$(curl -s "$BASE_URL/entity/$ACTIVE_UUID/available-actions")
echo "Can move: $(echo $ACTIONS | python3 -c "import sys, json; print(json.load(sys.stdin).get('can_move', False))")"
echo ""

# Try a move (position 3,7 for Hero, 11,7 for Skeleton)
if [ "$CURRENT_NAME" = "Hero" ]; then
  MOVE_POS="[3, 7]"
else
  MOVE_POS="[11, 7]"
fi

echo "Attempting move to $MOVE_POS..."
MOVE_RESULT=$(curl -s -X POST "$BASE_URL/action/move" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$ACTIVE_SESSION\", \"entity_uuid\": \"$ACTIVE_UUID\", \"position\": $MOVE_POS}")
echo "Move result: $MOVE_RESULT"
echo ""

# 10. Try with WRONG session (should fail)
echo "10. Testing wrong session (should fail)..."
if [ "$CURRENT_NAME" = "Hero" ]; then
  WRONG_SESSION="$CLAUDE_SESSION_ID"
else
  WRONG_SESSION="$HUMAN_SESSION_ID"
fi

WRONG_RESULT=$(curl -s -X POST "$BASE_URL/action/move" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$WRONG_SESSION\", \"entity_uuid\": \"$ACTIVE_UUID\", \"position\": $MOVE_POS}")
echo "Wrong session result (should be error): $WRONG_RESULT"
echo ""

echo "=== TEST COMPLETE ==="
