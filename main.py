import sys

import chess


def uci() -> None:
    board = chess.Board()

    while True:
        line = sys.stdin.readline()
        if not line:  # stdin closed
            break
        command = line.strip()

        if command == "uci":
            print("id name mega-mozg")
            print("id author hfbmb")
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
    score = None
    best_move = None
    for move in board.legal_moves:
        board.push(move)
        eval = evaluate(board)
        board.pop()

        if best_move is None:
            score = eval
            best_move = move
            continue

        if board.turn and eval > score:
            score = eval
            best_move = move
        elif not board.turn and eval < score:
            score = eval
            best_move = move

    return best_move


def evaluate(board: chess.Board) -> int:
    piece_costs = {"K": 0, "Q": 9, "R": 5, "B": 3, "N": 3, "P": 1, "k": 0, "q": -9, "r": -5, "b": -3, "n": -3, "p": -1}
    sum = 0
    for s in chess.SQUARES:
        piece = board.piece_at(s).symbol() if board.piece_at(s) else "k"
        sum += piece_costs[piece]
    return sum


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
