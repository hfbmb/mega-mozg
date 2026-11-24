import math
import sys

import chess

DEPTH = 3

# A mate is worth more than any material advantage you could ever have.
MATE_SCORE = 100_000

NODES = 0  # how many positions the last search looked at


PIECE_TYPE_COST = {
    chess.KING: 0,  # both kings are always on the board, so they always cancel out
    chess.QUEEN: 900,
    chess.ROOK: 500,
    chess.BISHOP: 300,
    chess.KNIGHT: 300,
    chess.PAWN: 100,
}


def uci() -> None:
    board = chess.Board()

    while True:
        line = sys.stdin.readline()
        if not line:  # stdin closed
            break
        command = line.strip()

        if command == "uci":
            print("id name python-chess-starter")
            print("id author your-name-here")
            print("uciok")
        elif command == "isready":
            print("readyok")
        elif command == "ucinewgame":
            board.reset()
        elif command.startswith("position"):
            board = parse_position(command)
        elif command.startswith("go"):
            move = choose_move(board)
            print(f"bestmove {move.uci()}")
        elif command == "quit":
            break

        sys.stdout.flush()


def choose_move(board: chess.Board) -> chess.Move:
    global NODES
    NODES = 0

    best_move = None
    best_score = -math.inf

    for move in board.legal_moves:
        board.push(move)
        # After the push it is the opponent's turn, so their score is our score
        # with the sign flipped.
        score = -negamax(board, DEPTH - 1)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move

    if best_move is None:
        raise ValueError("choose_move is called on board without legal moves")

    print(f"info depth {DEPTH} nodes {NODES} score cp {int(best_score)} pv {best_move.uci()}")

    return best_move


def negamax(board: chess.Board, depth: int) -> float:
    """Score `board` from the point of view of the side to move.

    Same search as `minimax`, but because the score always belongs to whoever is
    to move, both players are maximizing and the two branches collapse into one.
    """
    global NODES
    NODES += 1

    outcome = board.outcome()
    if outcome is not None:
        # A winner means the side to move has just been mated, and we are
        # scoring for the side to move, so there is no colour to ask about.
        return 0 if outcome.winner is None else -MATE_SCORE

    if depth == 0:
        return evaluate_relative(board)

    best = -math.inf
    for move in board.legal_moves:
        board.push(move)
        best = max(best, -negamax(board, depth - 1))
        board.pop()

    return best


def evaluate(board: chess.Board) -> int:
    """Material balance, always from white's point of view.

    Positive means white is ahead, negative means black is ahead.
    """
    white_score = 0
    black_score = 0

    for square in chess.SQUARES:
        if piece := board.piece_at(square):
            if piece.color == chess.WHITE:
                white_score += PIECE_TYPE_COST[piece.piece_type]
            else:
                black_score += PIECE_TYPE_COST[piece.piece_type]

    return white_score - black_score


def evaluate_relative(board: chess.Board) -> int:
    """The same score, from the point of view of whoever is to move."""
    return evaluate(board) if board.turn == chess.WHITE else -evaluate(board)


def parse_position(command: str) -> chess.Board:
    """Build a board from a UCI ``position`` command.

    Handles the two forms the protocol allows:

        position startpos
        position startpos moves e2e4 e7e5
    """
    tokens = command.split()

    if tokens[1] == "startpos":
        board = chess.Board()
        moves_index = 2
    else:
        raise ValueError("Only `startpos` implemented")

    if len(tokens) > moves_index and tokens[moves_index] == "moves":
        for uci in tokens[moves_index + 1 :]:
            board.push_uci(uci)

    return board


if __name__ == "__main__":
    uci()
