import os
from flask import Flask, request, jsonify

# Catan core
from catanatron_core.catanatron.game import Game, Color

# If you prefer MCTS from catanatron_experimental:
from catanatron_experimental.players.mcts import MCTSPlayer

# If you want to also have AlphaBeta as an alternative:
# from catanatron_core.catanatron.players.alpha_beta import AlphaBetaPlayer

app = Flask(__name__)

current_game = None  # We'll store one game in memory for demonstration

class HumanProxyPlayer:
    """
    Represents a human seat. We'll let the front-end or /perform_action route
    pick actions from the possible_actions().
    """
    def __init__(self, color, name="HumanPlayer"):
        self.color = color
        self.name = name

    def decide(self, game, possible_actions):
        # Typically not called automatically for a human seat; we rely on the user to pick an action.
        return None

    def __str__(self):
        return f"<HumanProxyPlayer color={self.color} name={self.name}>"

@app.route('/')
def index():
    return "Welcome to the full mechanics server with MCTS support!"

@app.route('/start_game', methods=['POST'])
def start_game():
    """
    Expects JSON: {"numHumans": 2} 
    We'll create a 4-player game, with (numHumans) seats as HumanProxyPlayer
    and the rest as MCTS players.
    """
    global current_game
    data = request.json or {}
    num_humans = data.get("numHumans", 1)

    if num_humans < 0 or num_humans > 4:
        return jsonify({"error": "numHumans must be between 0..4"}), 400

    total_players = 4
    num_ai = total_players - num_humans

    # Some recognized color constants from Catanatron
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    players = []

    # Add the human seats
    for i in range(num_humans):
        players.append(HumanProxyPlayer(colors[i], f"Human{i+1}"))

    # Add the AI seats (MCTS)
    for j in range(num_ai):
        # If you also want alpha-beta, you can do a mix or pick:
        # players.append(AlphaBetaPlayer(colors[num_humans + j]))
        players.append(MCTSPlayer(colors[num_humans + j]))

    current_game = Game(players)

    return jsonify({
        "message": f"Started a new {total_players}-player game",
        "numHumans": num_humans,
        "numAI": num_ai,
        "currentPlayer": current_game.current_player_index
    })

@app.route('/get_state', methods=['GET'])
def get_state():
    """
    Basic overview: turn number, current player, etc.
    You can expand to show resources, roads, dev cards, etc.
    """
    global current_game
    if not current_game:
        return jsonify({"error": "No game in progress"}), 400

    players_info = []
    for idx, p in enumerate(current_game.players):
        # You can include more detail if you want:
        players_info.append({
            "index": idx,
            "class": str(p),
        })

    return jsonify({
        "turn": current_game.turn,
        "currentPlayerIndex": current_game.current_player_index,
        "players": players_info
    })

@app.route('/possible_actions', methods=['GET'])
def possible_actions():
    """
    Return all valid actions for the current player in JSON form.
    This includes rolling dice, trading, building roads, dev cards, etc.
    """
    global current_game
    if not current_game:
        return jsonify({"error": "No game in progress"}), 400

    actions = list(current_game.possible_actions())
    json_actions = []
    for i, action in enumerate(actions):
        action_json = {
            "index": i,
            "description": str(action),
        }
        json_actions.append(action_json)

    return jsonify({"actions": json_actions})

@app.route('/perform_action', methods=['POST'])
def perform_action():
    """
    For a human seat, the front-end picks an action index from /possible_actions
    and calls /perform_action with {"actionIndex": X}.
    We'll apply that action to the game state.
    """
    global current_game
    if not current_game:
        return jsonify({"error": "No game in progress"}), 400

    data = request.json or {}
    action_index = data.get("actionIndex")
    if action_index is None:
        return jsonify({"error": "Must provide actionIndex"}), 400

    actions = list(current_game.possible_actions())
    if action_index < 0 or action_index >= len(actions):
        return jsonify({"error": "actionIndex out of range"}), 400

    chosen_action = actions[action_index]
    current_game.step(chosen_action)

    return jsonify({
        "appliedAction": str(chosen_action),
        "nextPlayerIndex": current_game.current_player_index,
        "turn": current_game.turn
    })

@app.route('/auto_ai', methods=['POST'])
def auto_ai():
    """
    If it's an AI seat, we let the MCTS or alpha-beta decide the next action.
    Could call this repeatedly if the AI can do multiple moves in the same turn.
    """
    global current_game
    if not current_game:
        return jsonify({"error": "No game in progress"}), 400

    current_player = current_game.players[current_game.current_player_index]

    # If the seat is a human, we can't auto-play
    if isinstance(current_player, HumanProxyPlayer):
        return jsonify({"error": "It's a human seat's turn"}), 400

    possible_actions = list(current_game.possible_actions())
    if not possible_actions:
        return jsonify({"error": "No actions available for AI"}), 400

    ai_action = current_player.decide(current_game, possible_actions)
    if ai_action is None:
        ai_action = possible_actions[0]  # fallback if AI returned None

    current_game.step(ai_action)
    return jsonify({
        "chosenAction": str(ai_action),
        "nextPlayerIndex": current_game.current_player_index,
        "turn": current_game.turn
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
