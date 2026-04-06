"""Network client for pygamefighting online mode."""

import socket
import threading
import json

DISCOVERY_PORT = 5556
_BEACON_MSG_PREFIX = "PYGAMEFIGHTING:"


def start_host_beacon(relay_port, stop_event):
    """Broadcast host IP on the LAN every second until stop_event is set."""
    import time
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"{_BEACON_MSG_PREFIX}{relay_port}".encode()
    while not stop_event.is_set():
        try:
            sock.sendto(msg, ('255.255.255.255', DISCOVERY_PORT))
        except Exception:
            pass
        stop_event.wait(1)
    sock.close()


def discover_host(timeout=8):
    """Listen for a host beacon on the LAN. Returns (host_ip, relay_port) or None."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)
    try:
        sock.bind(('', DISCOVERY_PORT))
        data, addr = sock.recvfrom(256)
        text = data.decode()
        if text.startswith(_BEACON_MSG_PREFIX):
            port = int(text.split(':')[1])
            return addr[0], port
    except Exception:
        pass
    finally:
        sock.close()
    return None


class Network:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(10)
        self.sock.connect((host, port))
        self.sock.settimeout(None)
        self._buf            = b''
        self._updates        = []
        self._lock           = threading.Lock()
        self.connected       = False
        self.error           = None
        self.player_id       = None   # assigned by relay
        self.max_players     = None   # total players in this room
        self.players_connected = 1    # how many have joined so far (host counts themselves)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_line(self):
        """Blocking read of one newline-terminated message (before recv loop starts)."""
        while b'\n' not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('Disconnected')
            self._buf += chunk
        line, self._buf = self._buf.split(b'\n', 1)
        return line.decode().strip()

    def _recv_loop(self):
        buf = b''
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    try:
                        with self._lock:
                            self._updates.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            pass
        self.connected = False

    # ------------------------------------------------------------------
    # Handshake (called from background thread before recv loop starts)
    # ------------------------------------------------------------------

    def request_host(self, max_players=2):
        """Send HOST command. Returns room code, or None on error."""
        self.max_players = max_players
        self.sock.sendall(f'HOST {max_players}\n'.encode())
        response = self._read_line()          # "CODE 0 4"
        parts    = response.split()
        if len(parts) >= 2 and not parts[0].startswith('ERR'):
            self.player_id   = int(parts[1])
            if len(parts) >= 3:
                self.max_players = int(parts[2])
            return parts[0]                   # room code
        self.error = response or 'no response'
        return None

    def wait_ready(self):
        """Block until READY. Handles intermediate PLAYER-joined messages.
        Returns True on success. Starts recv loop."""
        while True:
            msg = self._read_line()
            if msg == 'READY':
                self.connected = True
                threading.Thread(target=self._recv_loop, daemon=True).start()
                return True
            elif msg.startswith('PLAYER '):
                # Relay tells host how many players have joined
                try:
                    self.players_connected = int(msg.split()[1]) + 1
                except ValueError:
                    pass
            elif msg == 'TIMEOUT':
                self.error = 'Timed out waiting for players'
                return False
            else:
                self.error = msg or 'unexpected response'
                return False

    def join(self, code):
        """Join a room by code. Returns True on success. Starts recv loop."""
        self.sock.sendall(f'JOIN {code.upper()}\n'.encode())
        response = self._read_line()          # "2 4" or "ERR ..."
        if response.startswith('ERR'):
            self.error = response
            return False
        parts = response.split()
        try:
            self.player_id   = int(parts[0])
            self.max_players = int(parts[1]) if len(parts) > 1 else 2
            self.players_connected = self.player_id + 1
        except (ValueError, IndexError):
            self.error = f'unexpected response: {response}'
            return False

        msg = self._read_line()               # READY or TIMEOUT
        if msg == 'READY':
            self.connected = True
            threading.Thread(target=self._recv_loop, daemon=True).start()
            return True
        self.error = msg or 'no READY signal'
        return False

    # ------------------------------------------------------------------
    # In-game messaging
    # ------------------------------------------------------------------

    def send(self, data: dict):
        try:
            self.sock.sendall((json.dumps(data) + '\n').encode())
        except Exception:
            self.connected = False

    def get_updates(self):
        """Return and clear all buffered incoming messages."""
        with self._lock:
            updates, self._updates = self._updates, []
        return updates

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
