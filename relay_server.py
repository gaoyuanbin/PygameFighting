"""
Relay server — run this on any machine reachable by all players.
Rooms support 2, 4, or 6 players.

Usage:  python relay_server.py
"""

import socket
import threading
import random

rooms = {}
lock  = threading.Lock()


def gen_code():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=6))


def read_line(sock):
    buf = b''
    while b'\n' not in buf:
        chunk = sock.recv(1)
        if not chunk:
            return None
        buf += chunk
    return buf.decode().strip()


def broadcast_from(sender_idx, conns):
    """Read complete lines from conns[sender_idx] and forward to all others."""
    src = conns[sender_idx]
    buf = b''
    try:
        while True:
            chunk = src.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                msg = line + b'\n'
                for i, dst in enumerate(conns):
                    if i != sender_idx:
                        try:
                            dst.sendall(msg)
                        except Exception:
                            pass
    except Exception:
        pass


def handle(conn, addr):
    try:
        cmd = read_line(conn)
        if not cmd:
            conn.close()
            return

        if cmd.startswith('HOST '):
            parts     = cmd.split()
            try:
                max_players = max(2, min(int(parts[1]), 6))
            except (IndexError, ValueError):
                max_players = 2

            code       = gen_code()
            room_lock  = threading.Lock()
            full_event = threading.Event()
            room = {
                'max':   max_players,
                'conns': [conn],
                'lock':  room_lock,
                'full':  full_event,
            }
            with lock:
                rooms[code] = room

            # Tell host: code, their player index (0), and max_players
            conn.sendall(f'{code} 0 {max_players}\n'.encode())
            print(f'[+] Room {code} ({max_players}p) opened by {addr}')

            # Wait up to 5 minutes for the room to fill
            full_event.wait(300)

            with lock:
                rooms.pop(code, None)

            conns = room['conns']
            if len(conns) < max_players:
                print(f'[-] Room {code} timed out ({len(conns)}/{max_players})')
                for c in conns:
                    try:
                        c.sendall(b'TIMEOUT\n')
                    except Exception:
                        pass
                    try:
                        c.close()
                    except Exception:
                        pass
                return

            print(f'[+] Room {code} full — starting {max_players}-player relay')
            for c in conns:
                try:
                    c.sendall(b'READY\n')
                except Exception:
                    pass

            # One broadcast thread per player
            threads = [
                threading.Thread(target=broadcast_from, args=(i, conns), daemon=True)
                for i in range(len(conns))
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            for c in conns:
                try:
                    c.close()
                except Exception:
                    pass

        elif cmd.startswith('JOIN '):
            code = cmd[5:].strip()
            with lock:
                room = rooms.get(code)
            if not room:
                conn.sendall(b'ERR no such room\n')
                conn.close()
                return

            with room['lock']:
                if len(room['conns']) >= room['max']:
                    conn.sendall(b'ERR room full\n')
                    conn.close()
                    return
                player_idx  = len(room['conns'])
                max_players = room['max']
                room['conns'].append(conn)

            # Tell joiner their index and the room size
            conn.sendall(f'{player_idx} {max_players}\n'.encode())

            # Notify host a new player joined (for lobby count display)
            try:
                room['conns'][0].sendall(f'PLAYER {player_idx}\n'.encode())
            except Exception:
                pass

            print(f'[+] {addr} joined room {code} as player {player_idx}')

            if len(room['conns']) == room['max']:
                room['full'].set()

            # Don't close — host handler owns this socket for the relay

        else:
            conn.sendall(b'ERR unknown command\n')
            conn.close()

    except Exception as e:
        print(f'Error {addr}: {e}')
        try:
            conn.close()
        except Exception:
            pass


def start(port=5555, ready_event=None):
    """Start the relay (blocking). Pass a threading.Event to signal when bound."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', port))
    server.listen(50)
    if ready_event:
        ready_event.set()
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


def main():
    port = 5555
    print(f'Relay server on port {port}')
    print('Share your IP with all players; set relay_host in game_settings.json')
    start(port)


if __name__ == '__main__':
    main()
